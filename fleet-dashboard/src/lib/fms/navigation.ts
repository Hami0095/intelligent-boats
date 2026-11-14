import PF from "pathfinding";
import type { GeoPosition } from "./contracts";
import { SEARCH_AREA, insideSearchArea } from "./search-area";
import { distanceMetres, moveToward } from "./delivery";

export interface NavigationObstacle { id: string; position: GeoPosition; radiusM: number; kind: "obstacle" | "boat" }
export const BOAT_CLEARANCE_M = 10;
const EAST_SCALE = 111000 * Math.cos(59.33 * Math.PI / 180);
const GRID_M = 10;
const local = (p: GeoPosition) => ({ x: (p.longitude_deg - SEARCH_AREA.minLon) * EAST_SCALE, y: (p.latitude_deg - SEARCH_AREA.minLat) * 111000 });
const geographic = (x: number, y: number): GeoPosition => ({ latitude_deg: SEARCH_AREA.minLat + y / 111000, longitude_deg: SEARCH_AREA.minLon + x / EAST_SCALE });
export const clearance = (o: NavigationObstacle) => o.kind === "boat" ? BOAT_CLEARANCE_M : o.radiusM + BOAT_CLEARANCE_M;

export function segmentClear(a: GeoPosition, b: GeoPosition, obstacles: NavigationObstacle[]) {
  const start = local(a), end = local(b), dx = end.x - start.x, dy = end.y - start.y;
  return obstacles.every((o) => {
    const c = local(o.position), denom = dx * dx + dy * dy;
    const t = denom ? Math.max(0, Math.min(1, ((c.x - start.x) * dx + (c.y - start.y) * dy) / denom)) : 0;
    return Math.hypot(start.x + t * dx - c.x, start.y + t * dy - c.y) >= clearance(o) - 0.001;
  });
}

/** Random simulated hazards, spaced apart and away from initial boat positions. */
export function createObstacles(homes: GeoPosition[], random = Math.random): NavigationObstacle[] {
  const result: NavigationObstacle[] = [];
  for (let attempt = 0; attempt < 200 && result.length < 3; attempt++) {
    const position = {
      latitude_deg: SEARCH_AREA.minLat + (0.12 + random() * 0.76) * (SEARCH_AREA.maxLat - SEARCH_AREA.minLat),
      longitude_deg: SEARCH_AREA.minLon + (0.12 + random() * 0.76) * (SEARCH_AREA.maxLon - SEARCH_AREA.minLon),
    };
    const radiusM = 22 + random() * 13;
    if (homes.some((p) => distanceMetres(p, position) < 100) || result.some((o) => distanceMetres(o.position, position) < 160)) continue;
    result.push({ id: `obstacle-${result.length + 1}`, position, radiusM, kind: "obstacle" });
  }
  return result;
}

/** Replan around live GPS obstacles; stop rather than move through an unsafe segment. */
export function navigate(a: GeoPosition, target: GeoPosition, metres: number, obstacles: NavigationObstacle[], geofenced = false) {
  const valid = (p: GeoPosition) => (!geofenced || insideSearchArea(p)) && segmentClear(p, p, obstacles);
  const direct = moveToward(a, target, metres);
  const targetOccupiedByBoat = obstacles.some((o) => o.kind === "boat" && distanceMetres(o.position, target) < 0.01);
  const routeObstacles = targetOccupiedByBoat ? obstacles.filter((o) => o.kind !== "boat" || distanceMetres(o.position, target) >= 0.01) : obstacles;
  if (valid(direct.position) && segmentClear(a, direct.position, obstacles) && segmentClear(a, target, routeObstacles)) return direct;
  if (!valid(a)) return { position: a, heading: direct.heading };
  const start = local(a), goal = local(target);
  const minX = Math.floor(Math.min(0, start.x, goal.x) / GRID_M) * GRID_M - 100;
  const minY = Math.floor(Math.min(0, start.y, goal.y) / GRID_M) * GRID_M - 100;
  const max = local({ latitude_deg: SEARCH_AREA.maxLat, longitude_deg: SEARCH_AREA.maxLon });
  const width = Math.ceil((Math.max(max.x, start.x, goal.x) - minX + 100) / GRID_M) + 1;
  const height = Math.ceil((Math.max(max.y, start.y, goal.y) - minY + 100) / GRID_M) + 1;
  const point = (x: number, y: number) => geographic(minX + x * GRID_M, minY + y * GRID_M);
  const grid = new PF.Grid(width, height);
  for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
    const p = point(x, y);
    // Exact segment checks below protect every diagonal and shortcut.
    grid.setWalkableAt(x, y, (!geofenced || insideSearchArea(p)) && obstacles.every((o) => distanceMetres(p, o.position) >= clearance(o)));
  }
  const sx = Math.round((start.x - minX) / GRID_M), sy = Math.round((start.y - minY) / GRID_M);
  const goalX = Math.round((goal.x - minX) / GRID_M), goalY = Math.round((goal.y - minY) / GRID_M);
  let gx = goalX, gy = goalY;
  // A recipient or obstacle can occupy the exact goal: choose a safe nearby approach.
  let best = Infinity;
  for (let y = Math.max(0, goalY - 8); y <= Math.min(height - 1, goalY + 8); y++) for (let x = Math.max(0, goalX - 8); x <= Math.min(width - 1, goalX + 8); x++) {
    if (!grid.isWalkableAt(x, y)) continue;
    const d = distanceMetres(point(x, y), target);
    if (d < best) { best = d; gx = x; gy = y; }
  }
  grid.setWalkableAt(sx, sy, true);
  const path = new PF.AStarFinder({ allowDiagonal: true, dontCrossCorners: true }).findPath(sx, sy, gx, gy, grid);
  for (let i = path.length - 1; i >= 1; i--) {
    const node = path[i];
    const x = node?.[0], y = node?.[1];
    if (x === undefined || y === undefined) continue;
    const waypoint = point(x, y);
    if (!segmentClear(a, waypoint, obstacles)) continue;
    const next = moveToward(a, waypoint, metres);
    if (valid(next.position)) return next;
  }
  return { position: a, heading: direct.heading };
}