import { useState } from "react";
import type { FleetController } from "@/lib/fms/fleet";
import { time } from "./format";

export function Logs({ fleet }: { fleet: FleetController }) {
  const [tab, setTab] = useState<"audit" | "traffic" | "deliveries">("audit");
  const name = (id: string) => { try { return fleet.registry.require(id).display_name; } catch { return id; } };
  const audit = [...fleet.audit.entries].reverse().slice(0, 60);
  return (
    <div className="panel flex min-h-0 flex-col">
      <div className="flex gap-4 border-b border-border px-4 pt-3">
        {(["audit", "traffic", "deliveries"] as const).map((t) => (
          <button key={t} onClick={() => setTab(t)} className={`panel-title border-b-2 pb-2 ${tab === t ? "border-primary text-foreground" : "border-transparent"}`}>{t === "audit" ? "Audit log" : t === "traffic" ? "Message traffic" : "Delivery history"}</button>
        ))}
      </div>
      <div className="h-72 overflow-y-auto px-4 py-2 font-mono text-xs">
        {tab === "deliveries" ? (fleet.deliveries.records.length ? fleet.deliveries.records.map((r) => (
          <div key={r.mission_id} className="border-b border-border py-2">
            <div className="flex gap-3"><span className="text-primary">{r.mission_id}</span><span>{name(r.boat_id)} → {name(r.recipient_boat_id)}</span><span className="truncate">{r.item}</span><span className="ml-auto text-accent">{r.status}</span></div>
            {r.events.map((e, i) => <div key={i} className="flex gap-3 pl-4 text-muted-foreground"><span>{new Date(e.at).toLocaleString()}</span><span className="text-foreground">{e.status}</span><span className="truncate">{e.detail}</span></div>)}
          </div>
        )) : <div className="text-muted-foreground">No deliveries yet</div>) : tab === "audit" ? (audit.length ? audit.map((a, i) => (
          <div key={i} className="flex gap-3 py-0.5"><span className="text-muted-foreground">{time(a.recorded_at)}</span><span className={a.category === "command" ? "text-primary" : a.category === "ack" ? "text-success" : "text-warning"}>{a.category}</span><span className="text-muted-foreground">{a.boat_id}</span><span className="truncate">{a.message}</span></div>
        )) : <div className="text-muted-foreground">No entries yet</div>) :
          fleet.traffic.slice(0, 80).map((t, i) => (
            <div key={i} className="flex gap-3 py-0.5"><span className="text-muted-foreground">{time(t.at)}</span><span className={t.dir === "in" ? "text-accent" : "text-primary"}>{t.dir === "in" ? "← boat" : "→ boat"}</span><span className="text-muted-foreground">{t.e.boat_id}</span><span>{t.e.message_type}</span><span className="text-muted-foreground">#{t.e.sequence_number}</span></div>
          ))}
      </div>
    </div>
  );
}
