import { describe, expect, it } from "vitest";
import { FleetController } from "./fleet";
import { FleetCoverage, CoverageSearch, SEARCH_CELL_COUNT, SEARCH_AREA } from "./search-area";
import { connectionStatus } from "./connection";

const mission = { objective: "Independent recon", search_area_id: "A", time_limit_s: null, reward_reference: null };

describe("shared fleet search", () => {
  it("allocates different unsearched sections to all four boats", () => {
    const f = new FleetController(); f.obstacles = [];
    for (const b of f.boats.values()) { b.battery = 1; f.assign(b.id, mission); }
    f.tick();
    const assigned = new Set<number>();
    expect(f.coverage.sections.size).toBe(4);
    for (const cells of f.coverage.sections.values()) {
      expect(cells.size).toBe(60);
      for (const cell of cells) { expect(assigned.has(cell)).toBe(false); assigned.add(cell); }
    }
    expect(assigned.size).toBe(240);
  });
  it("counts overlapping visits once and skips a cell searched by another boat", () => {
    const shared = new FleetCoverage();
    const a = new CoverageSearch(shared, "a"), b = new CoverageSearch(shared, "b");
    const pos = { latitude_deg: SEARCH_AREA.minLat, longitude_deg: SEARCH_AREA.minLon };
    a.advance(pos, 0); b.advance(pos, 0);
    expect(a.visited.size).toBe(1); expect(b.visited.size).toBe(1); expect(shared.visited.size).toBe(1);
    for (let i = 0; i < 20; i++) shared.visited.add(i);
    shared.allocate([{ id: "b", pos }]);
    let destination = pos;
    b.advance(pos, 10, (from, target) => { destination = target; return { position: from, heading: 0 }; });
    expect(destination.latitude_deg).toBeGreaterThan(SEARCH_AREA.minLat + (SEARCH_AREA.maxLat - SEARCH_AREA.minLat) / 12);
  });
  it("releases stopped boat sections to remaining recon boats", () => {
    const f = new FleetController(); f.obstacles = [];
    f.assign("usv-01", mission); f.assign("usv-04", mission); f.tick();
    f.safeState("usv-04", "stop_propulsion"); f.tick();
    expect(f.coverage.sections.has("usv-04")).toBe(false);
    expect(f.coverage.sections.get("usv-01")?.size).toBe(SEARCH_CELL_COUNT - f.coverage.visited.size);
  });
  it("covers the entire area together and holds without repeat sweeps", () => {
    const f = new FleetController(); f.obstacles = [];
    for (const b of f.boats.values()) { b.battery = 1; f.assign(b.id, mission); }
    for (let i = 0; i < 2200; i++) f.tick();
    expect(f.coverage.visited.size).toBe(240);
    const positions = [...f.boats.values()].map((b) => ({ ...b.pos }));
    for (let i = 0; i < 10; i++) f.tick();
    expect([...f.boats.values()].map((b) => b.pos)).toEqual(positions);
  });
});

describe("connection freshness", () => {
  it("marks telemetry stale at 10 seconds, not before", () => {
    expect(connectionStatus("simulation", 1000, 10999).state).toBe("live");
    expect(connectionStatus("simulation", 1000, 11000).state).toBe("stale");
  });
  it("distinguishes source independently of freshness and waits without telemetry", () => {
    expect(connectionStatus("ai-box", null, 10000)).toMatchObject({ source: "ai-box", state: "waiting", lastUpdate: null });
    expect(connectionStatus("ai-box", 1000, 1001)).toMatchObject({ source: "ai-box", state: "live" });
    const f = new FleetController(); f.tick();
    for (const b of f.boats.values()) expect(f.connection(b.id).source).toBe("simulation");
  });
});