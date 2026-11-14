import type { BoatStatePayload, Envelope, MissionAssignmentPayload, SafeStateAction } from "./contracts";
import { AuditLog, FleetRegistry, FmsEndpoint, InMemoryFleetStore, MissionService, Outbox } from "./fms";
import { MockBoat } from "./mock-boat";
import { DeliveryHistory } from "./delivery-history";
import { createObstacles, type NavigationObstacle } from "./navigation";
import { CoverageSearch, FleetCoverage } from "./search-area";
import { connectionStatus, type ConnectionSource } from "./connection";

export interface MissionRecord { mission_id: string; boat_id: string; objective: string; search_area_id: string; created_at: number }

/** Wires the FMS to mock boats over an in-process loopback link (like adapters/fms/loopback.py). */
export class FleetController {
  registry = new FleetRegistry(); store = new InMemoryFleetStore(); audit = new AuditLog(); outbox = new Outbox(32);
  endpoint = new FmsEndpoint({ registry: this.registry, store: this.store, audit: this.audit, outbox: this.outbox });
  missions = new MissionService(this.registry, this.outbox);
  boats = new Map<string, MockBoat>();
  coverage = new FleetCoverage();
  private sources = new Map<string, ConnectionSource>();
  obstacles: NavigationObstacle[] = [];
  missionLog: MissionRecord[] = [];
  traffic: { at: number; dir: "in" | "out"; e: Envelope }[] = [];
  version = 0; private listeners = new Set<() => void>(); private missionSeq = 1;

  deliveries: DeliveryHistory;
  constructor(history = new DeliveryHistory(), random = Math.random) {
    this.deliveries = history; this.missionSeq = history.maxSequence() + 1;
    const base = { latitude_deg: 59.33, longitude_deg: 18.12 };
    ([["usv-01", "Skarv"], ["usv-02", "Tärna"], ["usv-03", "Ejder"], ["usv-04", "Lom"]] as const).forEach(([id, name], i) => {
      this.registry.register({ boat_id: id, display_name: name });
      this.boats.set(id, new MockBoat(id, { latitude_deg: base.latitude_deg + (i - 1.5) * 0.004, longitude_deg: base.longitude_deg - 0.01 }, (targetId) => this.boats.get(targetId)?.pos,
        () => [...this.obstacles, ...[...this.boats.values()].filter((b) => b.id !== id).map((b): NavigationObstacle => ({ id: b.id, position: b.pos, radiusM: 5, kind: "boat" }))]));
      const boat = this.boats.get(id);
      if (boat) boat.coverage = new CoverageSearch(this.coverage, id);
      this.sources.set(id, "simulation");
    });
    this.obstacles = createObstacles([...this.boats.values()].map((b) => b.home), random);
  }
  subscribe = (l: () => void) => { this.listeners.add(l); return () => this.listeners.delete(l); };
  getVersion = () => this.version;
  private emit() { this.version++; this.listeners.forEach((l) => l()); }
  private log(dir: "in" | "out", e: Envelope) { this.traffic.unshift({ at: Date.now(), dir, e }); if (this.traffic.length > 150) this.traffic.pop(); }

  private deliverFromBoat(boat: MockBoat, msgs: Envelope[], now: number) {
    for (const m of msgs) {
      this.log("in", m);
      for (const reply of this.endpoint.receive(m)) { this.log("out", reply); boat.handle(reply, now); }
    }
  }

  tick() {
    const now = Date.now();
    // Apply all commands before allocating work so simultaneous assignments
    // receive distinct sections and stopped boats relinquish their work.
    for (const boat of this.boats.values()) {
      for (const cmd of this.outbox.unacknowledged(boat.id)) { this.log("out", cmd); this.deliverFromBoat(boat, boat.handle(cmd, now), now); }
    }
    this.coverage.allocate([...this.boats.values()].filter((b) => b.mode === "autonomous" && b.mission?.status === "in_progress" && !b.delivery));
    for (const boat of this.boats.values()) {
      this.deliverFromBoat(boat, boat.step(now), now);
      for (const cmd of this.outbox.unacknowledged(boat.id)) { this.log("out", cmd); this.deliverFromBoat(boat, boat.handle(cmd, now), now); }
      this.trackDelivery(boat.id, now);
    }
    this.emit();
  }

  private trackDelivery(boatId: string, now: number) {
    const boat = this.boats.get(boatId), m = boat?.mission;
    if (!boat || !m) return;
    const status = m.status === "in_progress" && boat.delivery ? boat.delivery.phase : m.status;
    const detail = (this.store.latest(boatId, "mission_progress")?.envelope.payload as { detail?: string } | undefined)?.detail ?? "";
    this.deliveries.update(m.id, status, detail, now);
  }

  assign(boatId: string, p: MissionAssignmentPayload) {
    if (p.delivery) {
      this.registry.require(p.delivery.recipient_boat_id);
      if (p.delivery.recipient_boat_id === boatId) throw new Error("Choose another boat as recipient");
      if (!p.delivery.item.trim()) throw new Error("An item is required");
    }
    const id = `m-${String(this.missionSeq++).padStart(3, "0")}`;
    this.missions.assign(boatId, id, p);
    this.missionLog.unshift({ mission_id: id, boat_id: boatId, objective: p.objective, search_area_id: p.search_area_id, created_at: Date.now() });
    if (p.delivery) this.deliveries.start({ mission_id: id, boat_id: boatId, item: p.delivery.item.trim(), recipient_boat_id: p.delivery.recipient_boat_id, created_at: Date.now() });
    this.audit.record(Date.now(), "command", boatId, `mission ${id} assigned`);
    this.emit(); return id;
  }
  cancel(boatId: string, missionId: string, reason: string) { this.deliveries.update(missionId, "cancel requested", reason, Date.now()); this.missions.cancel(boatId, missionId, reason); this.audit.record(Date.now(), "command", boatId, `mission ${missionId} cancelled`); this.emit(); }
  safeState(boatId: string, a: SafeStateAction) { this.missions.safeState(boatId, a, "operator"); this.audit.record(Date.now(), "command", boatId, `safe state: ${a}`); this.emit(); }

  latestState(boatId: string) { return this.store.latest(boatId, "boat_state")?.envelope.payload as BoatStatePayload | undefined; }
  connection(boatId: string, now = Date.now()) {
    this.registry.require(boatId);
    return connectionStatus(this.sources.get(boatId) ?? "simulation", this.store.latest(boatId, "boat_state")?.received_at ?? null, now);
  }
}
