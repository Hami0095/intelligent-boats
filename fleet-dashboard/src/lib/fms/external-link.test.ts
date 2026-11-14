import { describe, expect, it } from "vitest";
import { pythonToTsEnvelope, tsToPythonEnvelope, SCHEMA_VERSION } from "./external-link";
import { makeEnvelope, type BoatStatePayload, type MissionAssignmentPayload } from "./contracts";

const pythonBoatState = {
  schema_version: "1.0.0",
  message_id: "3f6b1c2e-0000-4000-8000-0000000000ab",
  boat_id: "usv-05",
  mission_id: null,
  message_type: "boat_state",
  timestamp: "2026-11-14T12:00:00.000Z",
  sequence_number: 7,
  payload: { operating_mode: "autonomous", position: { latitude_deg: 59.33, longitude_deg: 18.12 }, speed_over_ground_mps: 2.5, heading_deg: 90, battery_state_of_charge: 0.8 },
};

describe("pythonToTsEnvelope", () => {
  it("converts an ISO timestamp to epoch ms and keeps the payload", () => {
    const e = pythonToTsEnvelope(pythonBoatState);
    expect(e).not.toBeNull();
    expect(e!.timestamp).toBe(Date.parse("2026-11-14T12:00:00.000Z"));
    expect(e!.boat_id).toBe("usv-05");
    expect(e!.sequence_number).toBe(7);
    expect((e!.payload as BoatStatePayload).operating_mode).toBe("autonomous");
  });

  it("rejects unknown message types, bad boat ids and bad timestamps", () => {
    expect(pythonToTsEnvelope({ ...pythonBoatState, message_type: "nope" })).toBeNull();
    expect(pythonToTsEnvelope({ ...pythonBoatState, boat_id: "Bad Id" })).toBeNull();
    expect(pythonToTsEnvelope({ ...pythonBoatState, timestamp: "not a date" })).toBeNull();
  });
});

describe("tsToPythonEnvelope", () => {
  it("adds the schema version and an ISO timestamp", () => {
    const e = makeEnvelope<BoatStatePayload>({
      boat_id: "usv-05", message_type: "boat_state", mission_id: null, sequence_number: 3,
      timestamp: Date.parse("2026-11-14T12:00:00.000Z"),
      payload: { operating_mode: "idle", position: null, speed_over_ground_mps: null, heading_deg: null, battery_state_of_charge: null },
    });
    const raw = tsToPythonEnvelope(e);
    expect(raw["schema_version"]).toBe(SCHEMA_VERSION);
    expect(raw["timestamp"]).toBe("2026-11-14T12:00:00.000Z");
  });

  it("strips the simulated delivery extension from mission assignments", () => {
    const e = makeEnvelope<MissionAssignmentPayload>({
      boat_id: "usv-05", message_type: "mission_assignment", mission_id: "m-001", sequence_number: 1,
      timestamp: 1700000000000,
      payload: { objective: "Recon", search_area_id: "A", time_limit_s: null, reward_reference: null, delivery: { item: "sensor", recipient_boat_id: "usv-06" } },
    });
    const raw = tsToPythonEnvelope(e);
    expect(raw["payload"]).toEqual({ objective: "Recon", search_area_id: "A", time_limit_s: null, reward_reference: null });
  });
});
