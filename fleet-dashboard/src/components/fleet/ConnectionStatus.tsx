import { useEffect, useState } from "react";
import type { FleetController } from "@/lib/fms/fleet";

export function ConnectionStatus({ fleet, boatId }: { fleet: FleetController; boatId: string }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => { const timer = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(timer); }, []);
  const status = fleet.connection(boatId, now);
  return <div className="mt-2 space-y-1 font-mono text-[11px]" aria-live="polite">
    <div className="flex flex-wrap items-center gap-1.5"><span className={`h-1.5 w-1.5 shrink-0 rounded-full ${status.state === "live" ? "bg-success" : "bg-warning"}`} />
      <span>{status.source === "simulation" ? "Simulation" : "Real AI box"}</span>
      <span className={status.state === "live" ? "text-success" : "text-warning"}>{status.state === "live" ? "Live" : status.state === "stale" ? "Stale data" : "Awaiting data"}</span>
    </div>
    <div className="text-muted-foreground">Last update: {status.lastUpdate === null ? "none" : `${new Date(status.lastUpdate).toISOString().slice(11, 19)} UTC · ${Math.floor((status.ageMs ?? 0) / 1000)}s ago`}</div>
    {status.state === "stale" && <div className="text-warning" role="status">No telemetry for 10s or more</div>}
  </div>;
}