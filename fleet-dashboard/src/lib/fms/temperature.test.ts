import { describe, expect, it } from "vitest";
import { FleetController } from "./fleet";
import { TemperatureLog, simulatedWaterTemperature } from "./temperature";

describe("water-temperature readings", () => {
  it("records degrees Celsius with boat, GPS, time and explicit simulated source", () => {
    const f = new FleetController(); f.tick();
    const s = f.latestState("usv-01");
    expect(f.temperatures.records).toHaveLength(4);
    expect(f.temperatures.records.find((r) => r.boatId === "usv-01")).toMatchObject({ celsius: s?.water_temperature_c, position: s?.position, source: "simulation", at: f.connection("usv-01").lastUpdate });
    expect(simulatedWaterTemperature({ latitude_deg: 59.33, longitude_deg: 18.12 })).toBe(9.4);
  });
  it("does not record missing or stale temperature telemetry", () => {
    const f = new FleetController();
    expect(f.recordTemperature("usv-01")).toBe(false);
    f.tick();
    const at = f.connection("usv-01").lastUpdate ?? 0;
    expect(f.recordTemperature("usv-01", at + 10000)).toBe(false);
    expect(f.temperatures.records).toHaveLength(4);
  });
  it("exports concrete values and snapshots GPS rather than a mutable boat position", () => {
    const log = new TemperatureLog(), position = { latitude_deg: 59.33, longitude_deg: 18.12 };
    log.record({ boatId: "usv-01", celsius: 9.4, at: 0, source: "simulation", position });
    position.latitude_deg = 0;
    expect(log.csv()).toContain("usv-01,9.4,1970-01-01T00:00:00.000Z,59.33,18.12,simulation");
    expect(log.record({ boatId: "usv-01", celsius: NaN, at: 0, source: "simulation", position })).toBe(false);
  });
});