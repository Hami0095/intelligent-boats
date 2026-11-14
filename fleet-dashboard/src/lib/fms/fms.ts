import {
  MESSAGE_SPECS, makeEnvelope, type AcknowledgementPayload, type Envelope, type MessageType,
  type MissionAssignmentPayload, type SafeStateAction,
} from "./contracts";

export interface BoatIdentity { boat_id: string; display_name: string }
export class UnregisteredBoatError extends Error {}
export class OutboxFullError extends Error {}

export class FleetRegistry {
  private boats = new Map<string, BoatIdentity>();
  register(id: BoatIdentity) {
    if (this.boats.has(id.boat_id)) throw new Error(`boat '${id.boat_id}' is already registered`);
    this.boats.set(id.boat_id, id);
  }
  require(boatId: string) {
    const b = this.boats.get(boatId);
    if (!b) throw new UnregisteredBoatError(`unknown boat '${boatId}'`);
    return b;
  }
  all() { return [...this.boats.values()]; }
}

export class Outbox {
  private pending = new Map<string, Map<string, Envelope>>();
  private seq = new Map<string, number>();
  constructor(private limit: number) { if (limit <= 0) throw new Error("limit_per_boat must be positive"); }
  nextSequence(boatId: string) { const v = this.seq.get(boatId) ?? 0; this.seq.set(boatId, v + 1); return v; }
  enqueue(e: Envelope) {
    const q = this.pending.get(e.boat_id) ?? new Map();
    if (q.size >= this.limit) throw new OutboxFullError(`outbox for '${e.boat_id}' is full (${this.limit})`);
    q.set(e.message_id, e); this.pending.set(e.boat_id, q);
  }
  unacknowledged(boatId: string) { return [...(this.pending.get(boatId)?.values() ?? [])]; }
  acknowledge(boatId: string, messageId: string) { return this.pending.get(boatId)?.delete(messageId) ?? false; }
}

export interface AuditEntry { recorded_at: number; category: string; boat_id: string | null; message: string }
export class AuditLog {
  entries: AuditEntry[] = [];
  record(at: number, category: string, boatId: string | null, message: string) {
    this.entries.push({ recorded_at: at, category, boat_id: boatId, message });
    if (this.entries.length > 500) this.entries.shift();
  }
}

export interface ReceivedMessage { envelope: Envelope; received_at: number }
export class InMemoryFleetStore {
  private history = new Map<string, ReceivedMessage[]>();
  record(e: Envelope, at: number) {
    const k = `${e.boat_id}|${e.message_type}`;
    const list = this.history.get(k) ?? [];
    list.push({ envelope: e, received_at: at });
    if (list.length > 200) list.shift();
    this.history.set(k, list);
  }
  history_(boatId: string, t: MessageType) { return this.history.get(`${boatId}|${t}`) ?? []; }
  latest(boatId: string, t: MessageType) { const l = this.history_(boatId, t); return l[l.length - 1] ?? null; }
}

export class FmsEndpoint {
  private seen = new Map<string, Set<string>>();
  private lastSeq = new Map<string, number>();
  constructor(
    private d: { registry: FleetRegistry; store: InMemoryFleetStore; audit: AuditLog; outbox: Outbox; clock?: () => number; dedupeWindow?: number },
  ) {}
  private now() { return (this.d.clock ?? Date.now)(); }

  /** Process one boat message; returns replies to send back to that boat. */
  receive(e: Envelope): Envelope[] {
    this.d.registry.require(e.boat_id);
    if (e.message_type === "acknowledgement") {
      const p = e.payload as AcknowledgementPayload;
      const removed = this.d.outbox.acknowledge(e.boat_id, p.acknowledged_message_id);
      this.d.audit.record(this.now(), "ack", e.boat_id,
        `${p.acknowledged_message_id.slice(0, 8)} ${p.accepted ? "accepted" : `rejected (${p.reason})`}; queue cleared=${removed}`);
      return [];
    }
    if (MESSAGE_SPECS[e.message_type].direction !== "boat_to_fms") {
      this.d.audit.record(this.now(), "rejected", e.boat_id, `${e.message_type} is not a boat-originated message`);
      return [];
    }
    const seen = this.seen.get(e.boat_id) ?? new Set<string>();
    this.seen.set(e.boat_id, seen);
    if (seen.has(e.message_id)) { this.d.audit.record(this.now(), "duplicate", e.boat_id, e.message_id); return []; }
    seen.add(e.message_id);
    const win = this.d.dedupeWindow ?? 10000;
    while (seen.size > win) seen.delete(seen.values().next().value as string);

    const last = this.lastSeq.get(e.boat_id);
    if (last !== undefined && e.sequence_number <= last)
      this.d.audit.record(this.now(), "out_of_order", e.boat_id, `sequence ${e.sequence_number} after ${last}`);
    this.lastSeq.set(e.boat_id, Math.max(e.sequence_number, last ?? 0));

    this.d.store.record(e, this.now());
    if (!MESSAGE_SPECS[e.message_type].critical) return [];
    return [makeEnvelope<AcknowledgementPayload>({
      boat_id: e.boat_id, message_type: "acknowledgement", mission_id: e.mission_id,
      sequence_number: this.d.outbox.nextSequence(e.boat_id), timestamp: this.now(),
      payload: { acknowledged_message_id: e.message_id, accepted: true, reason: null },
    })];
  }
}

export class MissionService {
  constructor(private registry: FleetRegistry, private outbox: Outbox, private clock: () => number = Date.now) {}
  assign(boatId: string, missionId: string, p: MissionAssignmentPayload) { return this.queue(boatId, "mission_assignment", p, missionId); }
  cancel(boatId: string, missionId: string, reason: string) { return this.queue(boatId, "mission_cancellation", { reason }, missionId); }
  safeState(boatId: string, action: SafeStateAction, reason = "") { return this.queue(boatId, "safe_state_command", { action, reason }, null); }
  private queue(boatId: string, t: MessageType, payload: unknown, missionId: string | null) {
    this.registry.require(boatId);
    const e = makeEnvelope({ boat_id: boatId, message_type: t, payload, mission_id: missionId,
      sequence_number: this.outbox.nextSequence(boatId), timestamp: this.clock() });
    this.outbox.enqueue(e);
    return e;
  }
}
