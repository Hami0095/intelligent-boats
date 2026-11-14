import type { BoatSnapshot, ReceivedReport, ReportType } from "./research-api";

export const NOW = "2026-11-14T09:30:00+00:00";
let messageNumber = 1;
export function report(
  boatId: string,
  messageType: ReportType,
  payload: Record<string, unknown>,
): ReceivedReport {
  return {
    envelope: {
      schema_version: "1.0.0",
      message_id: `00000000-0000-4000-8000-${String(messageNumber++).padStart(12, "0")}`,
      boat_id: boatId,
      mission_id: messageType === "boat.mission_progress" ? "research-mission" : null,
      message_type: messageType,
      timestamp: NOW,
      sequence_number: messageNumber,
      payload,
    },
    received_at: NOW,
  };
}
export function snapshot(
  boatId = "research-01",
  displayName = "Research Alpha",
  position: unknown = { latitude_deg: 59.331, longitude_deg: 18.115 },
): BoatSnapshot {
  return {
    boat_id: boatId,
    display_name: displayName,
    last_received_at: NOW,
    messages: {
      "boat.state": report(boatId, "boat.state", {
        operating_mode: "idle",
        position,
        speed_over_ground_mps: 1.2,
        heading_deg: 42,
        battery_state_of_charge: 0.73,
      }),
      "boat.mission_progress": report(boatId, "boat.mission_progress", {
        status: "accepted",
        completion_fraction: null,
        detail: "Received from mock AI Box",
      }),
      "boat.environment_progress": report(boatId, "boat.environment_progress", {
        searched_region_count: 2,
        known_region_count: 8,
        coverage_fraction: 0.25,
      }),
      "boat.service_health": report(boatId, "boat.service_health", {
        services: [{ name: "motion", status: "ok", detail: "" }],
      }),
    },
  };
}
export const response = (boats: BoatSnapshot[]) =>
  new Response(JSON.stringify({ boats }), { status: 200 });
