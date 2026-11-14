import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useFleet } from "@/components/fleet/use-fleet";
import { SeaChart } from "@/components/fleet/SeaChart";
import { BoatPanel } from "@/components/fleet/BoatPanel";
import { Logs } from "@/components/fleet/Logs";
import { activityLabel, modeTone, pct } from "@/components/fleet/format";

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
        <div className="flex items-center gap-2 font-mono text-xs text-muted-foreground"><span className="h-2 w-2 rounded-full bg-success" />Mock link · {boats.length} boats</div>
      </header>
      <main className="grid gap-4 p-4 lg:grid-cols-[1fr_380px]">
        <div className="flex min-w-0 flex-col gap-4">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            {boats.map((b) => {
              const s = fleet.latestState(b.boat_id);
              return (
                <button key={b.boat_id} onClick={() => setSelected(b.boat_id)} className={`panel p-3 text-left transition-colors ${selected === b.boat_id ? "border-primary" : "hover:border-muted-foreground"}`}>
                  <div className="flex justify-between"><span className="font-medium">{b.display_name}</span><span className="font-mono text-xs text-muted-foreground">{pct(s?.battery_state_of_charge)}</span></div>
                  <div className={`mt-1 font-mono text-xs ${s ? modeTone[s.operating_mode] : ""}`}>{s ? activityLabel(s.operating_mode, fleet.boats.get(b.boat_id)?.delivery) : "—"}</div>
                </button>
              );
            })}
          </div>
          <SeaChart fleet={fleet} selected={selected} onSelect={setSelected} />
          <Logs fleet={fleet} />
        </div>
        <BoatPanel key={selected} fleet={fleet} boatId={selected} />
      </main>
    </div>
  );
}
