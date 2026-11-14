export type Direction = "boat_to_fms" | "fms_to_boat" | "either";
export type MessageType =
  | "boat_state" | "mission_progress" | "obstacle_summary" | "environment_progress"
  | "operational_event" | "service_health" | "mission_assignment" | "navigation_goal"
  | "mission_cancellation" | "configuration_update" | "safe_state_command" | "acknowledgement";

export const MESSAGE_SPECS: Record<MessageType, { direction: Direction; critical: boolean }> = {
  boat_state: { direction: "boat_to_fms", critical: false },
  mission_progress: { direction: "boat_to_fms", critical: true },
  obstacle_summary: { direction: "boat_to_fms", critical: false },
  environment_progress: { direction: "boat_to_fms", critical: false },
  operational_event: { direction: "boat_to_fms", critical: true },
  service_health: { direction: "boat_to_fms", critical: false },
  mission_assignment: { direction: "fms_to_boat", critical: true },
  navigation_goal: { direction: "fms_to_boat", critical: true },
  mission_cancellation: { direction: "fms_to_boat", critical: true },
  configuration_update: { direction: "fms_to_boat", critical: true },
  safe_state_command: { direction: "fms_to_boat", critical: true },
  acknowledgement: { direction: "either", critical: false },
};

export type OperatingMode = "idle" | "autonomous" | "safe_state" | "returning_home" | "fault";
export type Severity = "info" | "warning" | "error" | "critical";
export type HealthStatus = "not_started" | "ok" | "degraded" | "failed" | "stopped";
export type MissionStatus = "accepted" | "rejected" | "in_progress" | "completed" | "aborted";
export type SafeStateAction = "hold_position" | "stop_propulsion" | "return_home";
export interface GeoPosition { latitude_deg: number; longitude_deg: number }

export interface BoatStatePayload {
  operating_mode: OperatingMode; position: GeoPosition | null;
  speed_over_ground_mps: number | null; heading_deg: number | null; battery_state_of_charge: number | null;
}
export interface MissionProgressPayload { status: MissionStatus; completion_fraction: number | null; detail: string }
export interface ObstacleTrack { track_id: string; category: string; relative_bearing_deg: number; range_m: number | null; collision_risk: number | null; confidence: number }
export interface ObstacleSummaryPayload { tracks: ObstacleTrack[] }
export interface EnvironmentProgressPayload { searched_region_count: number; known_region_count: number; coverage_fraction: number | null }
export interface OperationalEventPayload { severity: Severity; code: string; message: string }
export interface ServiceHealthPayload { services: { name: string; status: HealthStatus; detail: string }[] }
export interface MissionAssignmentPayload { objective: string; search_area_id: string; time_limit_s: number | null; reward_reference: string | null; delivery?: { item: string; recipient_boat_id: string } }
export interface MissionCancellationPayload { reason: string }
export interface SafeStateCommandPayload { action: SafeStateAction; reason: string }
export interface AcknowledgementPayload { acknowledged_message_id: string; accepted: boolean; reason: string | null }

export interface Envelope<P = unknown> {
  message_id: string; boat_id: string; message_type: MessageType; mission_id: string | null;
  sequence_number: number; timestamp: number; payload: P;
}

export function makeEnvelope<P>(e: Omit<Envelope<P>, "message_id"> & { message_id?: string | undefined }): Envelope<P> {
  return { ...e, message_id: e.message_id ?? crypto.randomUUID() };
}
