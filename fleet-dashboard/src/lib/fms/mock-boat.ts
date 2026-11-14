import { makeEnvelope, type Envelope, type GeoPosition, type MessageType, type MissionAssignmentPayload,
  type MissionStatus, type OperatingMode, type SafeStateCommandPayload, type ObstacleTrack } from "./contracts";
import { CoverageSearch, SEARCH_CELL_COUNT, clampToSearchArea } from "./search-area";
import { distanceMetres, HANDOFF_DISTANCE_M, type DeliveryState } from "./delivery";
import { navigate, type NavigationObstacle } from "./navigation";

/** Browser stand-in for an AI box built from mock adapters. */
export class MockBoat {
  mode: OperatingMode = "idle";
  pos: GeoPosition; heading = Math.random() * 360; speed = 0; battery = 0.6 + Math.random() * 0.4;
  mission: { id: string; status: MissionStatus; fraction: number } | null = null;
  searched = 0; known = SEARCH_CELL_COUNT; tracks: ObstacleTrack[] = [];
  coverage = new CoverageSearch();
  delivery: DeliveryState | null = null;
  private seq = 0; private handled = new Set<string>(); private tick = 0;
  constructor(public id: string, public home: GeoPosition, private recipientPosition: (id: string) => GeoPosition | undefined = () => undefined, private surroundings: () => NavigationObstacle[] = () => []) { this.pos = { ...home }; }

  private travel(target: GeoPosition, metres: number, geofenced = false) {
    const next = navigate(this.pos, target, metres, this.surroundings(), geofenced);
    this.speed = distanceMetres(this.pos, next.position) / 4;
    this.pos = next.position; this.heading = next.heading;
  }

  private stepDelivery(out: Envelope[], now: number) {
    const delivery = this.delivery, mission = this.mission;
    if (!delivery || mission?.status !== "in_progress") return;
    if (delivery.phase === "returning") {
      this.mode = "returning_home"; this.speed = 3;
      this.travel(this.home, 12);
      if (distanceMetres(this.pos, this.home) <= 2) {
        this.pos = { ...this.home }; this.speed = 0; this.mode = "idle";
        delivery.phase = "completed"; mission.status = "completed"; mission.fraction = 1;
        out.push(this.env("operational_event", { severity: "info", code: "delivery.completed", message: `${delivery.item} delivered to ${delivery.recipientId}; arrived home` }, now));
      }
    } else {
      const target = this.recipientPosition(delivery.recipientId);
      if (!target) {
        mission.status = "aborted"; this.mode = "returning_home"; this.speed = 0;
        out.push(this.env("mission_progress", { status: "aborted", completion_fraction: mission.fraction, detail: "Recipient unavailable; returning home" }, now));
        return;
      }
      const distance = distanceMetres(this.pos, target);
      if (distance > HANDOFF_DISTANCE_M + 0.01) {
        delivery.phase = "outbound"; delivery.handoffTicks = 0; this.speed = 3;
        this.travel(target, Math.min(12, distance - HANDOFF_DISTANCE_M));
        mission.fraction = 0.25;
      } else {
        this.speed = 0; delivery.phase = "handoff"; delivery.handoffTicks++;
        mission.fraction = 0.5;
        if (delivery.handoffTicks >= 3) {
          delivery.handedOver = true; delivery.phase = "returning";
          this.mode = "returning_home"; mission.fraction = 0.75;
          out.push(this.env("operational_event", { severity: "info", code: "delivery.handoff", message: `Simulated handoff: ${delivery.item} to ${delivery.recipientId}` }, now));
        }
      }
    }
    const detail = delivery.phase === "outbound" ? `Delivering ${delivery.item} to ${delivery.recipientId}` :
      delivery.phase === "handoff" ? `Simulated handoff of ${delivery.item}` :
      delivery.phase === "returning" ? `${delivery.item} handed over; returning home` : `${delivery.item} delivered; home reached`;
    out.push(this.env("mission_progress", { status: mission.status, completion_fraction: mission.fraction, detail }, now));
  }

  private env(t: MessageType, payload: unknown, now: number): Envelope {
    return makeEnvelope({ boat_id: this.id, message_type: t, payload, mission_id: this.mission?.id ?? null, sequence_number: this.seq++, timestamp: now });
  }

  step(now: number): Envelope[] {
    this.tick++;
    const out: Envelope[] = [];
    const dt = 1;
    const delivering = this.delivery !== null && this.mission?.status === "in_progress";
    if (delivering) {
      this.stepDelivery(out, now);
    } else if (this.mode === "autonomous") {
      this.speed = 2.5;
      const next = this.coverage.advance(this.pos, this.speed * dt * 4, (from, target, metres) => navigate(from, target, metres, this.surroundings(), true));
      this.speed = distanceMetres(this.pos, next.position) / 4;
      this.pos = next.position; this.heading = next.heading;
    } else if (this.mode === "returning_home") {
      this.travel(this.home, 12);
      if (distanceMetres(this.pos, this.home) <= 2) { this.pos = { ...this.home }; this.mode = "idle"; this.speed = 0; out.push(this.env("operational_event", { severity: "info", code: "home.reached", message: "Arrived at home position" }, now)); }
    } else this.speed = 0;
    if (this.speed > 0) this.battery = Math.max(0, this.battery - 0.00005);
    if (!this.delivery && this.mission?.status === "in_progress" && this.mode === "autonomous") {
      this.searched = this.coverage.visited.size;
      this.mission.fraction = this.searched / this.known;
      if (this.tick % 3 === 0)
        out.push(this.env("mission_progress", { status: "in_progress", completion_fraction: this.mission.fraction, detail: this.mission.fraction >= 1 ? "Area covered; holding position without repeating search" : "Independent recon; targeting unsearched cells" }, now));
    }
    if (this.battery < 0.15 && this.mode === "autonomous") {
      this.mode = "returning_home";
      if (this.mission?.status === "in_progress") {
        this.mission.status = "aborted";
        out.push(this.env("mission_progress", { status: "aborted", completion_fraction: this.mission.fraction, detail: "Low-battery safety return" }, now));
      }
      out.push(this.env("operational_event", { severity: "warning", code: "battery.low", message: "Battery below 15%, returning home" }, now));
    }
    out.push(this.env("boat_state", { operating_mode: this.mode, position: this.pos, speed_over_ground_mps: this.speed, heading_deg: this.heading, battery_state_of_charge: this.battery }, now));
    if (this.tick % 2 === 0) {
      this.tracks = this.surroundings().filter((o) => distanceMetres(this.pos, o.position) < 200).map((o) => {
        const range = distanceMetres(this.pos, o.position);
        const bearing = Math.atan2((o.position.longitude_deg - this.pos.longitude_deg) * Math.cos(this.pos.latitude_deg * Math.PI / 180), o.position.latitude_deg - this.pos.latitude_deg) * 180 / Math.PI;
        return { track_id: o.id, category: "unspecified" as const, relative_bearing_deg: ((bearing - this.heading + 540) % 360) - 180, range_m: Math.round(range), collision_risk: Math.max(0, 1 - range / 100), confidence: 1 };
      });
      out.push(this.env("obstacle_summary", { tracks: this.tracks }, now));
      out.push(this.env("environment_progress", { searched_region_count: this.searched, known_region_count: this.known, coverage_fraction: this.searched / this.known }, now));
    }
    if (this.tick % 5 === 1)
      out.push(this.env("service_health", { services: ["perception", "environment", "motion", "telemetry"].map((n) => ({ name: n, status: this.battery < 0.15 && n === "motion" ? "degraded" : "ok", detail: "" })) }, now));
    return out;
  }

  /** Receive an FMS command; always acknowledges (re-acks duplicates without re-applying). */
  handle(cmd: Envelope, now: number): Envelope[] {
    if (cmd.message_type === "acknowledgement") return [];
    let accepted = true, reason: string | null = null;
    if (!this.handled.has(cmd.message_id)) {
      this.handled.add(cmd.message_id);
      if (cmd.message_type === "mission_assignment") {
        const p = cmd.payload as MissionAssignmentPayload;
        if (this.mission?.status === "in_progress") { accepted = false; reason = "mission already in progress"; }
        else if (this.battery < 0.2) { accepted = false; reason = "battery too low"; }
        else if (!cmd.mission_id) { accepted = false; reason = "mission ID is required"; }
        else if (p.delivery && (!p.delivery.item.trim() || p.delivery.recipient_boat_id === this.id || !this.recipientPosition(p.delivery.recipient_boat_id))) { accepted = false; reason = "invalid delivery recipient or item"; }
        else {
          this.mission = { id: cmd.mission_id, status: "in_progress", fraction: 0 };
          this.delivery = p.delivery ? { item: p.delivery.item.trim(), recipientId: p.delivery.recipient_boat_id, phase: "outbound", handoffTicks: 0, handedOver: false } : null;
          if (!this.delivery) { this.searched = this.coverage.visited.size; this.mission.fraction = this.searched / this.known; this.pos = clampToSearchArea(this.pos); }
          this.mode = "autonomous";
        }
      } else if (cmd.message_type === "mission_cancellation") {
        if (this.mission?.id === cmd.mission_id && this.mission.status === "in_progress") { this.mission.status = "aborted"; this.mode = "idle"; }
      } else if (cmd.message_type === "safe_state_command") {
        const a = (cmd.payload as SafeStateCommandPayload).action;
        if (this.mission?.status === "in_progress") this.mission.status = "aborted";
        this.mode = a === "return_home" ? "returning_home" : "safe_state";
      }
    }
    const ack = this.env("acknowledgement", { acknowledged_message_id: cmd.message_id, accepted, reason }, now);
    const extra: Envelope[] = [];
    if (cmd.message_type === "mission_assignment" && accepted && this.mission?.id === cmd.mission_id)
      extra.push(this.env("mission_progress", { status: "accepted", completion_fraction: 0, detail: "" }, now));
    if (cmd.message_type === "mission_cancellation" || (cmd.message_type === "safe_state_command" && this.mission?.status === "aborted"))
      if (this.mission) extra.push(this.env("mission_progress", { status: "aborted", completion_fraction: this.mission.fraction, detail: "Stopped by FMS" }, now));
    return [ack, ...extra];
  }
}
