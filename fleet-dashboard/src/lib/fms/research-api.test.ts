import { describe, expect, it } from "vitest";
import { decodeFleetResponse, reportForView } from "./research-api";
import { report, snapshot } from "./research-fixtures";

describe("research wire decoding", () => {
  it("accepts contract defaults without altering raw minimal payloads or inventing heading", () => {
    const minimal = snapshot();
    minimal.messages = {
      "boat.state": report(minimal.boat_id, "boat.state", { operating_mode: "idle" }),
      "boat.mission_progress": report(minimal.boat_id, "boat.mission_progress", {
        status: "accepted",
      }),
      "boat.environment_progress": report(minimal.boat_id, "boat.environment_progress", {
        searched_region_count: 0,
        known_region_count: 0,
      }),
      "boat.service_health": report(minimal.boat_id, "boat.service_health", {
        services: [{ name: "motion", status: "ok" }],
      }),
      "boat.obstacle_summary": report(minimal.boat_id, "boat.obstacle_summary", {}),
    };
    const parsed = decodeFleetResponse({ boats: [minimal] })[0];
    const raw = parsed?.messages["boat.state"];
    if (!raw) throw new Error("Missing test state");
    expect(raw.envelope.payload).toEqual({ operating_mode: "idle" });
    expect(reportForView(raw).payload).toMatchObject({
      position: null,
      heading_deg: null,
      speed_over_ground_mps: null,
      battery_state_of_charge: null,
    });
    expect(raw.envelope.payload).toEqual({ operating_mode: "idle" });
    expect(() =>
      decodeFleetResponse({
        boats: [
          { ...minimal, messages: { "boat.state": report(minimal.boat_id, "boat.state", {}) } },
        ],
      }),
    ).toThrow();
  });

  it("rejects mismatched identities and report types", () => {
    const wrongBoat = snapshot();
    wrongBoat.messages["boat.state"] = report("different-boat", "boat.state", {
      operating_mode: "idle",
    });
    expect(() => decodeFleetResponse({ boats: [wrongBoat] })).toThrow("Mismatched boat");
    const wrongType = snapshot();
    wrongType.messages["boat.state"] = report(wrongType.boat_id, "boat.mission_progress", {
      status: "accepted",
    });
    expect(() => decodeFleetResponse({ boats: [wrongType] })).toThrow("Mismatched boat");
  });
});
