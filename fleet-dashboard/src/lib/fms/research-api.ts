import { z } from "zod";
import type { Envelope } from "./contracts";

export const REPORT_TYPES = {
  "boat.state": "boat_state",
  "boat.mission_progress": "mission_progress",
  "boat.environment_progress": "environment_progress",
  "boat.service_health": "service_health",
  "boat.obstacle_summary": "obstacle_summary",
  "boat.operational_event": "operational_event",
} as const;

export type ReportType = keyof typeof REPORT_TYPES;
export interface PythonEnvelope {
  schema_version: string;
  message_id: string;
  boat_id: string;
  mission_id: string | null;
  message_type: ReportType;
  timestamp: string;
  sequence_number: number;
  payload: Record<string, unknown>;
}
export interface ReceivedReport {
  envelope: PythonEnvelope;
  received_at: string;
}
export interface BoatSnapshot {
  boat_id: string;
  display_name: string;
  last_received_at: string | null;
  messages: Partial<Record<ReportType, ReceivedReport | null>>;
}

const timestamp = z
  .string()
  .refine((value) => Number.isFinite(Date.parse(value)), "Invalid timestamp");
const number = z.number().finite();
const fraction = number.min(0).max(1).nullable().optional().default(null);
const mode = z.enum(["idle", "autonomous", "safe_state", "returning_home", "fault"]);
const healthStatus = z.enum(["not_started", "ok", "degraded", "failed", "stopped"]);
const payloads = {
  "boat.state": z
    .object({
      operating_mode: mode,
      position: z
        .object({ latitude_deg: number.min(-90).max(90), longitude_deg: number.min(-180).max(180) })
        .nullable()
        .optional()
        .default(null),
      speed_over_ground_mps: number.min(0).nullable().optional().default(null),
      heading_deg: number.min(0).lt(360).nullable().optional().default(null),
      battery_state_of_charge: fraction,
    })
    .passthrough(),
  "boat.mission_progress": z
    .object({
      status: z.enum(["accepted", "rejected", "in_progress", "completed", "aborted"]),
      completion_fraction: fraction,
      detail: z.string().optional().default(""),
    })
    .passthrough(),
  "boat.environment_progress": z
    .object({
      searched_region_count: number.int().min(0),
      known_region_count: number.int().min(0),
      coverage_fraction: fraction,
    })
    .passthrough(),
  "boat.service_health": z
    .object({
      services: z.array(
        z
          .object({
            name: z.string(),
            status: healthStatus,
            detail: z.string().optional().default(""),
          })
          .passthrough(),
      ),
    })
    .passthrough(),
  "boat.obstacle_summary": z
    .object({
      tracks: z
        .array(
          z
            .object({
              track_id: z.string(),
              range_m: number.min(0).nullable().optional().default(null),
              relative_bearing_deg: number,
              collision_risk: fraction,
            })
            .passthrough(),
        )
        .optional()
        .default([]),
    })
    .passthrough(),
  "boat.operational_event": z
    .object({
      severity: z.enum(["info", "warning", "error", "critical"]),
      code: z.string(),
      message: z.string(),
    })
    .passthrough(),
};
const report = z.object({
  envelope: z
    .object({
      schema_version: z.string().regex(/^1\.\d+\.\d+$/),
      message_id: z.string().min(1),
      boat_id: z.string().min(1),
      mission_id: z.string().nullable(),
      message_type: z.enum(Object.keys(REPORT_TYPES) as [ReportType, ...ReportType[]]),
      timestamp,
      sequence_number: number.int().min(0),
      payload: z.record(z.unknown()),
    })
    .passthrough(),
  received_at: timestamp,
});
const responseSchema = z.object({
  boats: z.array(
    z.object({
      boat_id: z.string().min(1),
      display_name: z.string().min(1),
      last_received_at: timestamp.nullable(),
      messages: z.record(report.nullable()),
    }),
  ),
});

export function decodeFleetResponse(value: unknown): BoatSnapshot[] {
  const snapshots = responseSchema.parse(value).boats;
  const identities = new Set<string>();
  for (const boat of snapshots) {
    if (identities.has(boat.boat_id)) throw new Error("Duplicate boat identity in FMS response");
    identities.add(boat.boat_id);
    for (const [type, received] of Object.entries(boat.messages)) {
      if (!(type in REPORT_TYPES)) throw new Error(`Unsupported FMS report: ${type}`);
      if (received === null) continue;
      if (received.envelope.boat_id !== boat.boat_id || received.envelope.message_type !== type) {
        throw new Error("Mismatched boat identity or message type in FMS response");
      }
      payloads[type as ReportType].parse(received.envelope.payload);
    }
  }
  return snapshots as BoatSnapshot[];
}

export async function fetchFleetSnapshots(
  apiBaseUrl: string,
  signal?: AbortSignal,
  fetcher: typeof fetch = fetch,
): Promise<BoatSnapshot[]> {
  const response = await fetcher(`${apiBaseUrl}/boats`, {
    method: "GET",
    headers: { Accept: "application/json" },
    ...(signal ? { signal } : {}),
  });
  if (!response.ok) throw new Error(`FMS API returned HTTP ${response.status}`);
  return decodeFleetResponse(await response.json());
}

/** View-only adaptation; raw Python envelopes remain available in snapshots. */
export function reportForView(received: ReceivedReport): Envelope {
  return {
    ...received.envelope,
    message_type: REPORT_TYPES[received.envelope.message_type],
    timestamp: Date.parse(received.envelope.timestamp),
    payload: payloads[received.envelope.message_type].parse(received.envelope.payload),
  };
}
