import type { BoatStatePayload, MissionAssignmentPayload, SafeStateAction } from "./contracts";
import { connectionStatus } from "./connection";
import { DeliveryHistory } from "./delivery-history";
import { AuditLog, FleetRegistry, InMemoryFleetStore, Outbox } from "./fms";
import type { FleetView } from "./fleet-view";
import type { MockBoat } from "./mock-boat";
import type { NavigationObstacle } from "./navigation";
import { fetchFleetSnapshots, reportForView, type BoatSnapshot } from "./research-api";
import { FleetCoverage } from "./search-area";
import { TemperatureLog } from "./temperature";

/** A read model of received API reports, with no browser boat simulation. */
export class ResearchFleetController implements FleetView {
  readonly dataSource = "rest" as const;
  loading = true;
  error: string | null = null;
  registry = new FleetRegistry();
  store = new InMemoryFleetStore();
  audit = new AuditLog();
  outbox = new Outbox(1);
  boats = new Map<string, MockBoat>();
  coverage = new FleetCoverage();
  temperatures = new TemperatureLog();
  obstacles: NavigationObstacle[] = [];
  deliveries = new DeliveryHistory();
  traffic: FleetView["traffic"] = [];
  snapshots: BoatSnapshot[] = [];
  private version = 0;
  private listeners = new Set<() => void>();
  private pending = false;
  private disposed = false;
  private abortController: AbortController | null = null;

  constructor(
    private apiBaseUrl: string,
    private fetcher: typeof fetch = fetch,
  ) {}

  subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };
  getVersion = () => this.version;
  private emit() {
    this.version++;
    this.listeners.forEach((listener) => listener());
  }

  async refresh(): Promise<void> {
    if (this.pending || this.disposed) return;
    this.pending = true;
    this.abortController = new AbortController();
    try {
      const snapshots = await fetchFleetSnapshots(
        this.apiBaseUrl,
        this.abortController.signal,
        this.fetcher,
      );
      if (this.disposed) return;
      this.registry = new FleetRegistry();
      this.store = new InMemoryFleetStore();
      this.audit = new AuditLog();
      this.traffic = [];
      this.snapshots = snapshots;
      for (const boat of snapshots) {
        this.registry.register({ boat_id: boat.boat_id, display_name: boat.display_name });
        for (const received of Object.values(boat.messages)) {
          if (!received) continue;
          const envelope = reportForView(received);
          const at = Date.parse(received.received_at);
          this.store.record(envelope, at);
          this.traffic.push({ at, dir: "in", e: envelope });
          if (received.envelope.message_type === "boat.operational_event") {
            const payload = received.envelope.payload;
            this.audit.record(
              at,
              String(payload["severity"]),
              boat.boat_id,
              `${payload["code"]}: ${payload["message"]}`,
            );
          }
        }
      }
      this.traffic.sort((a, b) => b.at - a.at);
      this.error = null;
    } catch (error) {
      if (!this.disposed)
        this.error = error instanceof Error ? error.message : "Unable to read FMS reports";
    } finally {
      this.pending = false;
      if (!this.disposed) {
        this.loading = false;
        this.emit();
      }
    }
  }

  dispose(): void {
    this.disposed = true;
    this.abortController?.abort();
    this.listeners.clear();
  }
  latestState(boatId: string): BoatStatePayload | undefined {
    return this.store.latest(boatId, "boat_state")?.envelope.payload as
      BoatStatePayload | undefined;
  }
  connection(boatId: string, now = Date.now()) {
    this.registry.require(boatId);
    return connectionStatus(
      "ai-box",
      this.store.latest(boatId, "boat_state")?.received_at ?? null,
      now,
    );
  }
  assign(_boatId: string, _payload: MissionAssignmentPayload): never {
    throw new Error("Research reporting is read-only");
  }
  cancel(_boatId: string, _missionId: string, _reason: string): never {
    throw new Error("Research reporting is read-only");
  }
  safeState(_boatId: string, _action: SafeStateAction): never {
    throw new Error("Research reporting is read-only");
  }
  recordTemperature(): boolean {
    return false;
  }
}
