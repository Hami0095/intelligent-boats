import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useFleet } from "@/components/fleet/use-fleet";
import { SeaChart } from "@/components/fleet/SeaChart";
import { BoatPanel } from "@/components/fleet/BoatPanel";
import { Logs } from "@/components/fleet/Logs";
import { activityLabel, modeTone, pct } from "@/components/fleet/format";
import { ConnectionStatus } from "@/components/fleet/ConnectionStatus";
import { Button } from "@/components/ui/button";
import { SEARCH_AREA_KM2, SEARCH_CELL_COUNT } from "@/lib/fms/search-area";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Fleet Control — Intelligent Boats" },
      { name: "description", content: "Monitor autonomous surface vessels, assign search missions and issue safe-state commands." },
      { property: "og:title", content: "Fleet Control — Intelligent Boats" },
      { property: "og:description", content: "Monitor autonomous surface vessels, assign search missions and issue safe-state commands." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Index,
});

function Index() {
  const fleet = useFleet();
  const [selected, setSelected] = useState("usv-01");
  if (!fleet) return <div className="flex min-h-screen items-center justify-center font-mono text-sm text-muted-foreground">Connecting to fleet…</div>;
  const boats = fleet.registry.all();
  return (
    <div className="min-h-screen">
      <header className="flex items-center justify-between border-b border-border px-6 py-3">
        <div className="flex items-baseline gap-3"><h1 className="text-lg font-semibold tracking-tight">Intelligent Boats</h1><span className="panel-title">Fleet Management System</span></div>
        <div className="flex items-center gap-2 font-mono text-xs text-muted-foreground">Simulation · no real AI boxes connected</div>
      </header>
      <main className="grid gap-4 p-4 lg:grid-cols-[1fr_380px]">
        <div className="flex min-w-0 flex-col gap-4">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            {boats.map((b) => {
              const s = fleet.latestState(b.boat_id);
              return (
                <Button variant="outline" aria-label={`Select ${b.display_name}`} key={b.boat_id} onClick={() => setSelected(b.boat_id)} className={`panel block h-auto min-w-0 whitespace-normal p-3 text-left transition-colors ${selected === b.boat_id ? "border-primary" : "hover:border-muted-foreground"}`}>
                  <div className="flex justify-between"><span className="font-medium">{b.display_name}</span><span className="font-mono text-xs text-muted-foreground">{pct(s?.battery_state_of_charge)}</span></div>
                  <div className={`mt-1 font-mono text-xs ${s ? modeTone[s.operating_mode] : ""}`}>{s ? activityLabel(s.operating_mode, fleet.boats.get(b.boat_id)?.delivery) : "—"}</div>
                  <ConnectionStatus fleet={fleet} boatId={b.boat_id} />
                </Button>
              );
            })}
          </div>
          <section className="space-y-2 border-y border-border py-3" aria-label="Fleet-wide coverage">
            <div className="flex items-baseline justify-between gap-2"><h2 className="panel-title">Fleet-wide simulated coverage · Area A</h2><span className="font-mono text-lg text-accent">{pct(fleet.coverage.visited.size / SEARCH_CELL_COUNT)}</span></div>
            <progress className="h-2 w-full accent-accent" value={fleet.coverage.visited.size} max={SEARCH_CELL_COUNT} aria-label="Combined searched cells" />
            <div className="font-mono text-xs text-muted-foreground">{fleet.coverage.visited.size} / {SEARCH_CELL_COUNT} unique cells · {(fleet.coverage.visited.size / SEARCH_CELL_COUNT * SEARCH_AREA_KM2).toFixed(2)} / {SEARCH_AREA_KM2.toFixed(2)} km²</div>
            <div className="flex flex-wrap gap-x-4 gap-y-1 font-mono text-xs">{boats.map((b) => <span key={b.boat_id}>{b.display_name}: {fleet.coverage.sections.get(b.boat_id)?.size ?? 0} cells assigned</span>)}</div>
          </section>
          <SeaChart fleet={fleet} selected={selected} onSelect={setSelected} />
          <Logs fleet={fleet} />
        </div>
        <BoatPanel key={selected} fleet={fleet} boatId={selected} />
      </main>
    </div>
  );
}
