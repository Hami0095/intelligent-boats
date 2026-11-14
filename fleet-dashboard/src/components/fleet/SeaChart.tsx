import type { FleetController } from "@/lib/fms/fleet";
import { modeFill } from "./format";
import { SEARCH_AREA, cellBounds } from "@/lib/fms/search-area";
import { BOAT_CLEARANCE_M } from "@/lib/fms/navigation";

const C = { lat: 59.33, lon: 18.11 }, SPAN_LAT = 0.03, SPAN_LON = 0.06;
const xy = (lat: number, lon: number) => ({ x: ((lon - C.lon) / SPAN_LON + 0.5) * 1000, y: (0.5 - (lat - C.lat) / SPAN_LAT) * 600 });

export function SeaChart({ fleet, selected, onSelect }: { fleet: FleetController; selected: string; onSelect: (id: string) => void }) {
  const topLeft = xy(SEARCH_AREA.maxLat, SEARCH_AREA.minLon), bottomRight = xy(SEARCH_AREA.minLat, SEARCH_AREA.maxLon);
  const boat = fleet.boats.get(selected);
  const coverage = fleet.coverage.visited;
  const delivery = boat?.mission?.status === "in_progress" ? boat.delivery : null;
  const destination = delivery?.phase === "returning" ? boat?.home : delivery ? fleet.latestState(delivery.recipientId)?.position : null;
  const position = fleet.latestState(selected)?.position;
  const routeStart = position ? xy(position.latitude_deg, position.longitude_deg) : null;
  const routeEnd = destination ? xy(destination.latitude_deg, destination.longitude_deg) : null;
  return (
    <div className="panel relative overflow-hidden">
      <div className="absolute left-3 top-3 z-10 panel-title">Operating area · Saltsjön</div>
      <svg viewBox="0 0 1000 600" className="sea-grid block aspect-[5/3] w-full">
        <path d="M0,0 L180,0 C160,90 120,140 60,200 C30,240 10,300 0,320 Z" className="fill-land" />
        <path d="M1000,600 L760,600 C800,520 880,500 920,430 C950,380 990,360 1000,350 Z" className="fill-land" />
        {[...fleet.boats.values()].map((b) => <polyline key={b.id} aria-label={`Recorded recon route ${b.id}`} points={b.coverage.trail.map((p) => { const point = xy(p.latitude_deg, p.longitude_deg); return `${point.x},${point.y}`; }).join(" ")} className={b.id === selected ? "fill-none stroke-accent/70" : "fill-none stroke-muted-foreground/40"} strokeWidth={1.5} />)}
        {[...(fleet.coverage.sections.get(selected) ?? [])].map((index) => { const cell = cellBounds(index), a = xy(cell.maxLat, cell.minLon), b = xy(cell.minLat, cell.maxLon); return <rect key={`assigned-${index}`} x={a.x} y={a.y} width={b.x-a.x} height={b.y-a.y} className="fill-primary/10 stroke-primary/20" strokeWidth={0.5} />; })}
        {Array.from(coverage ?? []).map((index) => {
          const cell = cellBounds(index), a = xy(cell.maxLat, cell.minLon), b = xy(cell.minLat, cell.maxLon);
          return <rect key={index} x={a.x} y={a.y} width={b.x - a.x} height={b.y - a.y} className="fill-accent/25 stroke-accent/20" strokeWidth={0.5} />;
        })}
        <rect x={topLeft.x} y={topLeft.y} width={bottomRight.x - topLeft.x} height={bottomRight.y - topLeft.y} className="fill-none stroke-primary/40" strokeDasharray="6 6" />
        <text x="438" y="168" className="fill-primary/60 font-mono text-[12px]">SEARCH AREA A</text>
        {fleet.obstacles.map((o) => {
          const p = xy(o.position.latitude_deg, o.position.longitude_deg);
          const radius = o.radiusM / 111000 / SPAN_LAT * 600;
          const eastRadius = radius * SPAN_LAT / (SPAN_LON * Math.cos(o.position.latitude_deg * Math.PI / 180)) * 1000 / 600;
          return <g key={o.id} aria-label={`Simulated obstacle ${o.id}`}>
            <title>{o.id} · {Math.round(o.radiusM)} m radius</title>
            <ellipse cx={p.x} cy={p.y} rx={eastRadius * (1 + BOAT_CLEARANCE_M / o.radiusM)} ry={radius * (1 + BOAT_CLEARANCE_M / o.radiusM)} className="fill-warning/10 stroke-warning/50" strokeDasharray="2 2" />
            <ellipse cx={p.x} cy={p.y} rx={eastRadius} ry={radius} className="fill-warning/70 stroke-warning" />
          </g>;
        })}
        {routeStart && routeEnd && <g aria-label="Delivery destination">
          <line x1={routeStart.x} y1={routeStart.y} x2={routeEnd.x} y2={routeEnd.y} className="stroke-accent" strokeWidth={2} strokeDasharray="5 4" />
          <circle cx={routeEnd.x} cy={routeEnd.y} r={15} className="fill-none stroke-accent" strokeWidth={2} />
        </g>}
        {[...fleet.boats.values()].map((b) => {
          const s = fleet.latestState(b.id); if (!s?.position) return null;
          const p = xy(s.position.latitude_deg, s.position.longitude_deg), h = xy(b.home.latitude_deg, b.home.longitude_deg);
          const name = fleet.registry.require(b.id).display_name, sel = b.id === selected;
          return (
            <g key={b.id} className="cursor-pointer" onClick={() => onSelect(b.id)}>
              <circle cx={h.x} cy={h.y} r={4} className="fill-none stroke-muted-foreground" />
              {sel && <circle cx={p.x} cy={p.y} r={10} className="animate-ping-soft fill-none stroke-primary" strokeWidth={2} />}
              <g transform={`translate(${p.x} ${p.y}) rotate(${s.heading_deg ?? 0})`}>
                <path d="M0,-11 L7,8 L0,4 L-7,8 Z" className={`${modeFill[s.operating_mode]} ${sel ? "stroke-foreground" : "stroke-background"}`} strokeWidth={1.5} />
              </g>
              <text x={p.x + 12} y={p.y + 4} className={`font-mono text-[13px] ${sel ? "fill-foreground" : "fill-muted-foreground"}`}>{name}</text>
            </g>
          );
        })}
      </svg>
      <div className="flex flex-wrap gap-4 border-t border-border px-3 py-2 font-mono text-xs text-muted-foreground">
        <span className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-warning" />{fleet.obstacles.length} simulated obstacles</span>
        <span>Boat clearance · {BOAT_CLEARANCE_M} m</span>
        <span className="text-accent">Searched · fleet</span><span className="text-primary">Assigned · selected boat</span>
      </div>
    </div>
  );
}
