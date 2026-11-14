import type { GeoPosition } from "./contracts";

/** Shared geographic bounds match the search rectangle on the chart. */
export const SEARCH_AREA = {
  minLat: 59.3225, maxLat: 59.3375,
  minLon: 18.1058, maxLon: 18.1286,
  columns: 20, rows: 12,
};
export const SEARCH_CELL_COUNT = SEARCH_AREA.columns * SEARCH_AREA.rows;
const latSize = (SEARCH_AREA.maxLat - SEARCH_AREA.minLat) / SEARCH_AREA.rows;
const lonSize = (SEARCH_AREA.maxLon - SEARCH_AREA.minLon) / SEARCH_AREA.columns;
const lonMetres = 111000 * Math.cos(59.33 * Math.PI / 180);
export const SEARCH_AREA_KM2 = (SEARCH_AREA.maxLat - SEARCH_AREA.minLat) * 111000 *
  (SEARCH_AREA.maxLon - SEARCH_AREA.minLon) * lonMetres / 1e6;

export function insideSearchArea(p: GeoPosition) {
  return p.latitude_deg >= SEARCH_AREA.minLat && p.latitude_deg <= SEARCH_AREA.maxLat &&
    p.longitude_deg >= SEARCH_AREA.minLon && p.longitude_deg <= SEARCH_AREA.maxLon;
}
export function clampToSearchArea(p: GeoPosition): GeoPosition {
  return {
    latitude_deg: Math.max(SEARCH_AREA.minLat, Math.min(SEARCH_AREA.maxLat, p.latitude_deg)),
    longitude_deg: Math.max(SEARCH_AREA.minLon, Math.min(SEARCH_AREA.maxLon, p.longitude_deg)),
  };
}
export function cellBounds(index: number) {
  const col = index % SEARCH_AREA.columns, row = Math.floor(index / SEARCH_AREA.columns);
  return { minLat: SEARCH_AREA.minLat + row * latSize, maxLat: SEARCH_AREA.minLat + (row + 1) * latSize,
    minLon: SEARCH_AREA.minLon + col * lonSize, maxLon: SEARCH_AREA.minLon + (col + 1) * lonSize };
}
function cellAt(p: GeoPosition) {
  const col = Math.min(SEARCH_AREA.columns - 1, Math.floor((p.longitude_deg - SEARCH_AREA.minLon) / lonSize));
  const row = Math.min(SEARCH_AREA.rows - 1, Math.floor((p.latitude_deg - SEARCH_AREA.minLat) / latSize));
  return row * SEARCH_AREA.columns + col;
}

/** Visit unsearched lane cells; coverage and travel stay in memory for this boat. */
export class CoverageSearch {
  visited = new Set<number>();
  trail: GeoPosition[] = [];
  private targetIndex = 0;
  private targets = Array.from({ length: SEARCH_CELL_COUNT }, (_, i) => {
    const row = Math.floor(i / SEARCH_AREA.columns), offset = i % SEARCH_AREA.columns;
    const col = row % 2 === 0 ? offset : SEARCH_AREA.columns - 1 - offset;
    const bounds = cellBounds(row * SEARCH_AREA.columns + col);
    return { latitude_deg: (bounds.minLat + bounds.maxLat) / 2, longitude_deg: (bounds.minLon + bounds.maxLon) / 2 };
  });

  advance(position: GeoPosition, distanceM: number, steer?: (from: GeoPosition, target: GeoPosition, metres: number) => { position: GeoPosition; heading: number }) {
    let p = clampToSearchArea(position), remaining = Math.max(0, distanceM), heading = 0;
    this.visited.add(cellAt(p));
    if (this.trail.length === 0) this.trail.push({ ...p });
    while (remaining > 0) {
      // Covered destinations are never selected again. Transit may still cross
      // visited water when reaching an unsearched cell or avoiding a hazard.
      let examined = 0;
      while (examined < this.targets.length) {
        const candidate = this.targets[this.targetIndex];
        if (candidate && !this.visited.has(cellAt(candidate))) break;
        this.targetIndex = (this.targetIndex + 1) % this.targets.length;
        examined++;
      }
      if (examined === this.targets.length) break;
      const target = this.targets[this.targetIndex];
      if (!target) break;
      const north = (target.latitude_deg - p.latitude_deg) * 111000;
      const east = (target.longitude_deg - p.longitude_deg) * lonMetres;
      const distance = Math.hypot(north, east);
      if (distance < 0.00001) {
        this.visited.add(cellAt(target));
        this.targetIndex = (this.targetIndex + 1) % this.targets.length;
        continue;
      }
      heading = (Math.atan2(east, north) * 180 / Math.PI + 360) % 360;
      const travel = Math.min(remaining, distance, 20);
      const next = steer?.(p, target, travel);
      if (next) {
        const moved = Math.hypot((next.position.latitude_deg - p.latitude_deg) * 111000, (next.position.longitude_deg - p.longitude_deg) * lonMetres);
        p = next.position; heading = next.heading;
        // A permanently blocked cell centre is skipped, not marked as visited.
        if (moved < 0.001) this.targetIndex = (this.targetIndex + 1) % this.targets.length;
      } else p = clampToSearchArea({ latitude_deg: p.latitude_deg + (target.latitude_deg - p.latitude_deg) * travel / distance,
        longitude_deg: p.longitude_deg + (target.longitude_deg - p.longitude_deg) * travel / distance });
      this.visited.add(cellAt(p));
      const last = this.trail.at(-1);
      if (!last || last.latitude_deg !== p.latitude_deg || last.longitude_deg !== p.longitude_deg) this.trail.push({ ...p });
      remaining -= travel;
    }
    return { position: p, heading };
  }
}