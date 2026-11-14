import { describe, expect, it } from "vitest";
import { navigate, createObstacles, clearance, segmentClear, BOAT_CLEARANCE_M, type NavigationObstacle } from "./navigation";
import { distanceMetres } from "./delivery";
import { FleetController } from "./fleet";
import { insideSearchArea } from "./search-area";

const origin = { latitude_deg: 59.33, longitude_deg: 18.12 };
const north = (metres: number) => ({ ...origin, latitude_deg: origin.latitude_deg + metres / 111000 });
describe("simulated collision avoidance", () => {
  it("places random hazards inside the area and away from homes", () => {
    let seed = 123;
    const random = () => ((seed = (seed * 16807) % 2147483647) - 1) / 2147483646;
    const obstacles = createObstacles([origin], random);
    expect(obstacles).toHaveLength(3);
    for (const obstacle of obstacles) {
      expect(insideSearchArea(obstacle.position)).toBe(true);
      expect(distanceMetres(origin, obstacle.position)).toBeGreaterThanOrEqual(100);
    }
  });
  it("detours around an obstacle without crossing its exclusion zone", () => {
    const obstacle: NavigationObstacle = { id: "rock", position: origin, radiusM: 30, kind: "obstacle" };
    let position = north(-150);
    const target = north(150);
    let detoured = false;
    for (let i = 0; i < 100 && distanceMetres(position, target) > 0.1; i++) {
      const next = navigate(position, target, 10, [obstacle], true);
      expect(segmentClear(position, next.position, [obstacle])).toBe(true);
      expect(distanceMetres(next.position, origin)).toBeGreaterThanOrEqual(clearance(obstacle) - 0.001);
      expect(insideSearchArea(next.position)).toBe(true);
      if (Math.abs(next.position.longitude_deg - origin.longitude_deg) > 0.0001) detoured = true;
      position = next.position;
    }
    expect(detoured).toBe(true);
    expect(distanceMetres(position, target)).toBeLessThan(0.1);
  });
  it("treats another boat as an obstacle and keeps 10 metres clear", () => {
    const obstacle: NavigationObstacle = { id: "other", position: origin, radiusM: 5, kind: "boat" };
    let position = north(-80);
    for (let i = 0; i < 50; i++) {
      const next = navigate(position, north(80), 12, [obstacle]);
      expect(segmentClear(position, next.position, [obstacle])).toBe(true);
      expect(distanceMetres(next.position, origin)).toBeGreaterThanOrEqual(BOAT_CLEARANCE_M - 0.001);
      position = next.position;
    }
    expect(distanceMetres(position, north(80))).toBeLessThan(0.1);
  });
  it("keeps working boats separated and searches within the boundary", () => {
    const fleet = new FleetController();
    const rock: NavigationObstacle = { id: "rock", position: { latitude_deg: 59.323125, longitude_deg: 18.11 }, radiusM: 30, kind: "obstacle" };
    fleet.obstacles = [rock];
    for (const b of fleet.boats.values()) {
      b.battery = 1;
      fleet.assign(b.id, { objective: "Independent recon", search_area_id: "A", time_limit_s: null, reward_reference: null });
    }
    fleet.tick();
    for (let i = 0; i < 250; i++) {
      fleet.tick();
      const boats = [...fleet.boats.values()];
      for (const b of boats) {
        expect(insideSearchArea(b.pos)).toBe(true);
        expect(distanceMetres(b.pos, rock.position)).toBeGreaterThanOrEqual(40 - 0.001);
        for (const other of boats) if (other.id !== b.id) expect(distanceMetres(b.pos, other.pos)).toBeGreaterThanOrEqual(10 - 0.001);
      }
    }
    for (const b of fleet.boats.values()) expect(b.searched).toBeGreaterThan(1);
  });
  it("avoids obstacles on both the delivery and home-return legs", () => {
    const fleet = new FleetController(), boat = fleet.boats.get("usv-01"), target = fleet.boats.get("usv-02");
    if (!boat || !target) throw new Error("Missing boats");
    const obstacle: NavigationObstacle = { id: "rock", position: { latitude_deg: (boat.pos.latitude_deg + target.pos.latitude_deg) / 2, longitude_deg: boat.pos.longitude_deg }, radiusM: 30, kind: "obstacle" };
    fleet.obstacles = [obstacle]; boat.battery = 1;
    fleet.assign(boat.id, { objective: "Deliver sensor", search_area_id: "A", time_limit_s: null, reward_reference: null, delivery: { item: "Sensor", recipient_boat_id: target.id } });
    for (let i = 0; i < 180; i++) {
      const before = boat.pos; fleet.tick();
      expect(segmentClear(before, boat.pos, [obstacle])).toBe(true);
      expect(distanceMetres(boat.pos, target.pos)).toBeGreaterThanOrEqual(10 - 0.001);
    }
    expect(boat.delivery?.handedOver).toBe(true);
    expect(boat.mission?.status).toBe("completed");
    expect(boat.pos).toEqual(boat.home);
  });
});