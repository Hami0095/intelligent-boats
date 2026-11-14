export interface DeliveryHistoryEvent { at: number; status: string; detail: string }
export interface DeliveryHistoryRecord {
  mission_id: string; boat_id: string; item: string; recipient_boat_id: string;
  created_at: number; status: string; events: DeliveryHistoryEvent[];
}
export const DELIVERY_HISTORY_KEY = "fms.delivery-history.v1";

/** Persistable delivery log; records a new event only when the status/phase changes. */
export class DeliveryHistory {
  constructor(public records: DeliveryHistoryRecord[] = []) {}
  start(r: Omit<DeliveryHistoryRecord, "status" | "events">) {
    this.records.unshift({ ...r, status: "assigned", events: [{ at: r.created_at, status: "assigned", detail: `${r.item} → ${r.recipient_boat_id}` }] });
    if (this.records.length > 100) this.records.pop();
  }
  update(missionId: string, status: string, detail: string, at: number) {
    const r = this.records.find((x) => x.mission_id === missionId);
    if (!r || r.status === status) return false;
    r.status = status; r.events.push({ at, status, detail }); return true;
  }
  /** Highest numeric mission sequence so new IDs never collide after a reload. */
  maxSequence() { return this.records.reduce((m, r) => Math.max(m, Number(r.mission_id.replace(/\D/g, "")) || 0), 0); }
  static parse(raw: string | null) {
    try { const v = raw ? JSON.parse(raw) : []; return new DeliveryHistory(Array.isArray(v) ? v : []); } catch { return new DeliveryHistory(); }
  }
  serialize() { return JSON.stringify(this.records); }
}
