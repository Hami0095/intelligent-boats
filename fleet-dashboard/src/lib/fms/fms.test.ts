import { describe, expect, it } from "vitest";
import { makeEnvelope } from "./contracts";
import { AuditLog, FleetRegistry, FmsEndpoint, InMemoryFleetStore, MissionService, Outbox, OutboxFullError, UnregisteredBoatError } from "./fms";
import { FleetController } from "./fleet";
import { CoverageSearch, SEARCH_CELL_COUNT, SEARCH_AREA, insideSearchArea } from "./search-area";
import { distanceMetres, HANDOFF_DISTANCE_M } from "./delivery";

function setup() {
  const registry = new FleetRegistry(); registry.register({ boat_id: "b1", display_name: "B1" });
  const store = new InMemoryFleetStore(), audit = new AuditLog(), outbox = new Outbox(2);
  return { registry, store, audit, outbox, endpoint: new FmsEndpoint({ registry, store, audit, outbox, clock: () => 0 }), missions: new MissionService(registry, outbox, () => 0) };
}
const msg = (t: "boat_state" | "mission_progress" | "mission_assignment", seq: number, id?: string) =>
  makeEnvelope({ boat_id: "b1", message_type: t, mission_id: null, sequence_number: seq, timestamp: 0, payload: {}, message_id: id });

describe("FMS endpoint", () => {
  it("rejects unregistered boats", () => {
    const { endpoint } = setup();
    expect(() => endpoint.receive({ ...msg("boat_state", 0), boat_id: "ghost" })).toThrow(UnregisteredBoatError);
  });
  it("acknowledges critical messages only", () => {
    const { endpoint } = setup();
    expect(endpoint.receive(msg("boat_state", 0))).toHaveLength(0);
    expect(endpoint.receive(msg("mission_progress", 1))[0]?.message_type).toBe("acknowledgement");
  });
  it("drops duplicates", () => {
    const { endpoint, store, audit } = setup();
    endpoint.receive(msg("boat_state", 0, "x")); endpoint.receive(msg("boat_state", 0, "x"));
    expect(store.history_("b1", "boat_state")).toHaveLength(1);
    expect(audit.entries.at(-1)?.category).toBe("duplicate");
  });
  it("rejects FMS-originated messages from boats", () => {
    const { endpoint, store } = setup();
    endpoint.receive(msg("mission_assignment", 0));
    expect(store.history_("b1", "mission_assignment")).toHaveLength(0);
  });
  it("clears outbox on boat ack and fails loudly when full", () => {
    const { endpoint, missions, outbox } = setup();
    const cmd = missions.safeState("b1", "hold_position");
    missions.safeState("b1", "stop_propulsion");
    expect(() => missions.safeState("b1", "return_home")).toThrow(OutboxFullError);
    endpoint.receive(makeEnvelope({ boat_id: "b1", message_type: "acknowledgement", mission_id: null, sequence_number: 5, timestamp: 0, payload: { acknowledged_message_id: cmd.message_id, accepted: true, reason: null } }));
    expect(outbox.unacknowledged("b1")).toHaveLength(1);
  });
});

describe("fleet loopback", () => {
  function searchingFleet() {
    const f = new FleetController();
    f.obstacles = [];
    const boat = f.boats.get("usv-01");
    if (!boat) throw new Error("Expected demo boat");
    boat.battery = 1;
    const missionId = f.assign("usv-01", { objective: "continuous search", search_area_id: "A", time_limit_s: null, reward_reference: null });
    f.tick();
    return { f, boat, missionId };
  }
  it("keeps searching after the entire area is covered", () => {
    const { f, boat } = searchingFleet();
    for (let i = 0; i < 3500; i++) f.tick();
    expect(boat.searched).toBe(SEARCH_CELL_COUNT);
    expect(boat.mission?.fraction).toBe(1);
    expect(boat.mission?.status).toBe("in_progress");
    expect(f.latestState("usv-01")?.operating_mode).toBe("autonomous");
    const position = { ...boat.pos };
    for (let i = 0; i < 100; i++) f.tick();
    expect(boat.pos).toEqual(position);
    expect(boat.speed).toBe(0);
  });
  it("retains visited locations and route when recon is reassigned", () => {
    const { f, boat, missionId } = searchingFleet();
    for (let i = 0; i < 100; i++) f.tick();
    const visited = [...boat.coverage.visited], coverage = boat.coverage;
    expect(visited.length).toBeGreaterThan(1);
    expect(coverage.trail.length).toBeGreaterThan(1);
    f.cancel(boat.id, missionId, "operator cancelled"); f.tick();
    f.assign(boat.id, { objective: "Independent recon", search_area_id: "A", time_limit_s: null, reward_reference: null });
    f.tick();
    expect(boat.coverage).toBe(coverage);
    for (const cell of visited) expect(boat.coverage.visited.has(cell)).toBe(true);
  });
  it("ends continuous search when the operator cancels", () => {
    const { f, boat, missionId } = searchingFleet();
    f.cancel("usv-01", missionId, "operator cancelled"); f.tick(); f.tick();
    expect(boat.mission?.status).toBe("aborted");
    expect(boat.mode).toBe("idle");
    expect(boat.speed).toBe(0);
  });
  it("ends continuous search and stops propulsion", () => {
    const { f, boat } = searchingFleet();
    f.safeState("usv-01", "stop_propulsion"); f.tick(); f.tick();
    expect(boat.mission?.status).toBe("aborted");
    expect(boat.mode).toBe("safe_state");
    expect(boat.speed).toBe(0);
  });
  it("ends continuous search on return home", () => {
    const { f, boat } = searchingFleet();
    boat.pos = { latitude_deg: boat.home.latitude_deg + 0.01, longitude_deg: boat.home.longitude_deg };
    f.safeState("usv-01", "return_home"); f.tick(); f.tick();
    expect(boat.mission?.status).toBe("aborted");
    expect(boat.mode).toBe("returning_home");
  });
  it("preserves the automatic safety return below 15% battery", () => {
    const { f, boat } = searchingFleet();
    boat.battery = 0.149;
    f.tick();
    expect(boat.mission?.status).toBe("aborted");
    expect(boat.mode).toBe("returning_home");
  });
  it("assigned mission is acknowledged and progresses", () => {
    const f = new FleetController();
    f.assign("usv-01", { objective: "find buoy", search_area_id: "A", time_limit_s: null, reward_reference: null });
    f.tick(); f.tick();
    expect(f.outbox.unacknowledged("usv-01")).toHaveLength(0);
    expect(f.latestState("usv-01")?.operating_mode).toBe("autonomous");
  });
});

describe("area coverage", () => {
  it("skips an already searched lane instead of steering back to it", () => {
    const search = new CoverageSearch();
    for (let i = 0; i < 20; i++) search.visited.add(i);
    const position = { latitude_deg: SEARCH_AREA.minLat, longitude_deg: SEARCH_AREA.minLon };
    let destination = position;
    search.advance(position, 10, (from, target) => { destination = target; return { position: from, heading: 0 }; });
    expect(destination.latitude_deg).toBeGreaterThan(SEARCH_AREA.minLat + (SEARCH_AREA.maxLat - SEARCH_AREA.minLat) / SEARCH_AREA.rows);
  });
  it("keeps every search step inside the boundary, even starting outside", () => {
    const search = new CoverageSearch();
    let position = { latitude_deg: SEARCH_AREA.maxLat + 0.01, longitude_deg: SEARCH_AREA.maxLon + 0.01 };
    for (let i = 0; i < 4000; i++) {
      position = search.advance(position, 10).position;
      expect(insideSearchArea(position)).toBe(true);
    }
  });
  it("turns from an eastbound lane to the next westbound lane", () => {
    const search = new CoverageSearch();
    let position = { latitude_deg: SEARCH_AREA.minLat, longitude_deg: SEARCH_AREA.minLon };
    let east = false, west = false;
    for (let i = 0; i < 500; i++) {
      const next = search.advance(position, 10); position = next.position;
      if (Math.abs(next.heading - 90) < 1) east = true;
      if (east && Math.abs(next.heading - 270) < 1) west = true;
    }
    expect(east).toBe(true); expect(west).toBe(true);
  });
  it("counts unique visited cells, not elapsed time or repeated visits", () => {
    const search = new CoverageSearch();
    const position = { latitude_deg: SEARCH_AREA.minLat, longitude_deg: SEARCH_AREA.minLon };
    search.advance(position, 0);
    for (let i = 0; i < 100; i++) search.advance(position, 0);
    expect(search.visited.size).toBe(1);
  });
});

describe("delivery missions", () => {
  function setupDelivery() {
    const f = new FleetController(), boat = f.boats.get("usv-01"), target = f.boats.get("usv-02");
    f.obstacles = [];
    if (!boat || !target) throw new Error("Expected demo boats");
    boat.battery = 1;
    const missionId = f.assign(boat.id, { objective: "Deliver sensor to Tärna", search_area_id: "area-a", time_limit_s: null, reward_reference: null, delivery: { item: "Sensor", recipient_boat_id: target.id } });
    f.tick();
    return { f, boat, target, missionId };
  }
  it("hands over a sensor nearby and completes only after returning to its own home", () => {
    const { f, boat, target } = setupDelivery();
    let handoff = false;
    for (let i = 0; i < 200; i++) {
      f.tick();
      if (boat.delivery?.phase === "handoff") {
        expect(distanceMetres(boat.pos, target.pos)).toBeLessThanOrEqual(HANDOFF_DISTANCE_M + 0.01);
        expect(boat.speed).toBe(0); handoff = true;
      }
    }
    expect(handoff).toBe(true);
    expect(boat.delivery?.handedOver).toBe(true);
    expect(boat.delivery?.item).toBe("Sensor");
    expect(boat.mission?.status).toBe("completed");
    expect(boat.pos).toEqual(boat.home);
    expect(boat.mode).toBe("idle");
    expect(boat.searched).toBe(0);
  });
  it("tracks a recipient that changes position", () => {
    const { f, boat, target } = setupDelivery();
    target.pos = { latitude_deg: target.pos.latitude_deg + 0.003, longitude_deg: target.pos.longitude_deg + 0.002 };
    for (let i = 0; i < 200 && !boat.delivery?.handedOver; i++) f.tick();
    expect(boat.delivery?.handedOver).toBe(true);
    expect(distanceMetres(boat.pos, target.pos)).toBeLessThanOrEqual(HANDOFF_DISTANCE_M + 0.01);
  });
  it("steers directly to updated GPS positions each tick without sweeping search cells", () => {
    const { f, boat, target } = setupDelivery();
    const visitedBefore = [...boat.coverage.visited];
    for (let i = 0; i < 30; i++) {
      target.pos = { latitude_deg: boat.pos.latitude_deg + (i % 2 === 0 ? 0.004 : -0.004), longitude_deg: boat.pos.longitude_deg };
      const before = distanceMetres(boat.pos, target.pos);
      const longitude = boat.pos.longitude_deg;
      f.tick();
      expect(before - distanceMetres(boat.pos, target.pos)).toBeCloseTo(12, 3);
      expect(boat.pos.longitude_deg).toBeCloseTo(longitude, 8);
      expect(boat.heading).toBe(i % 2 === 0 ? 0 : 180);
      expect([...boat.coverage.visited]).toEqual(visitedBefore);
      expect(boat.delivery?.phase).toBe("outbound");
    }
  });
  it.each(["stop_propulsion", "return_home"] as const)("aborts delivery on %s without handing over", (action) => {
    const { f, boat } = setupDelivery();
    f.safeState(boat.id, action); f.tick(); f.tick();
    expect(boat.mission?.status).toBe("aborted");
    expect(boat.delivery?.handedOver).toBe(false);
    if (action === "stop_propulsion") expect(boat.speed).toBe(0);
  });
  it("cancels delivery before handoff", () => {
    const { f, boat, missionId } = setupDelivery();
    f.cancel(boat.id, missionId, "operator cancelled"); f.tick(); f.tick();
    expect(boat.mission?.status).toBe("aborted"); expect(boat.speed).toBe(0);
    expect(boat.delivery?.handedOver).toBe(false);
  });
  it("rejects self-delivery", () => {
    const f = new FleetController();
    expect(() => f.assign("usv-01", { objective: "Delivery", search_area_id: "area-a", time_limit_s: null, reward_reference: null, delivery: { item: "Sensor", recipient_boat_id: "usv-01" } })).toThrow("another boat");
  });
});

import { DeliveryHistory as DH } from "./delivery-history";
describe("delivery history persistence", () => {
  it("records phase changes once and survives serialize/parse", () => {
    const h = new DH();
    h.start({ mission_id: "m-007", boat_id: "usv-01", item: "Sensor", recipient_boat_id: "usv-02", created_at: 1 });
    expect(h.update("m-007", "outbound", "", 2)).toBe(true);
    expect(h.update("m-007", "outbound", "", 3)).toBe(false);
    h.update("m-007", "completed", "", 4);
    const back = DH.parse(h.serialize());
    expect(back.records[0]?.events.map((e) => e.status)).toEqual(["assigned", "outbound", "completed"]);
    expect(back.maxSequence()).toBe(7);
  });
});
