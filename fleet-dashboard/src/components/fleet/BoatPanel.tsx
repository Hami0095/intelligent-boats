import { useState } from "react";
import type { EnvironmentProgressPayload, MissionProgressPayload, ObstacleSummaryPayload, ServiceHealthPayload } from "@/lib/fms/contracts";
import type { FleetController } from "@/lib/fms/fleet";
import { activityLabel, modeTone, pct } from "./format";
import { SEARCH_AREA_KM2 } from "@/lib/fms/search-area";
import { distanceMetres } from "@/lib/fms/delivery";
import { Button } from "@/components/ui/button";

function Stat({ label, value }: { label: string; value: string }) {
  return <div><div className="panel-title">{label}</div><div className="mt-1 font-mono text-lg">{value}</div></div>;
}

export function BoatPanel({ fleet, boatId }: { fleet: FleetController; boatId: string }) {
  const id = fleet.registry.require(boatId), s = fleet.latestState(boatId);
  const mp = fleet.store.latest(boatId, "mission_progress");
  const prog = mp?.envelope.payload as MissionProgressPayload | undefined;
  const env = fleet.store.latest(boatId, "environment_progress")?.envelope.payload as EnvironmentProgressPayload | undefined;
  const obs = fleet.store.latest(boatId, "obstacle_summary")?.envelope.payload as ObstacleSummaryPayload | undefined;
  const health = fleet.store.latest(boatId, "service_health")?.envelope.payload as ServiceHealthPayload | undefined;
  const pending = fleet.outbox.unacknowledged(boatId).length;
  const active = prog && (prog.status === "in_progress" || prog.status === "accepted") ? mp?.envelope.mission_id : null;
  const [objective, setObjective] = useState("Locate survey buoy");
  const [area, setArea] = useState("area-a");
  const [missionType, setMissionType] = useState<"search" | "delivery">("search");
  const [item, setItem] = useState("Sensor");
  const recipients = fleet.registry.all().filter((b) => b.boat_id !== boatId);
  const [recipient, setRecipient] = useState(recipients[0]?.boat_id ?? "");
  const delivery = fleet.boats.get(boatId)?.delivery;
  const targetPosition = delivery ? fleet.latestState(delivery.recipientId)?.position : null;
  const targetDistance = s?.position && targetPosition ? distanceMetres(s.position, targetPosition) : null;

  return (
    <div className="panel flex flex-col gap-5 p-4">
      <div className="flex items-baseline justify-between">
        <div><div className="text-xl font-semibold">{id.display_name}</div><div className="font-mono text-xs text-muted-foreground">{boatId}</div></div>
        <div className={`font-mono text-sm ${s ? modeTone[s.operating_mode] : ""}`}>{s ? activityLabel(s.operating_mode, delivery) : "No signal"}</div>
      </div>
      <div className="grid grid-cols-3 gap-4">
        <Stat label="Battery" value={pct(s?.battery_state_of_charge)} />
        <Stat label="Speed" value={s?.speed_over_ground_mps != null ? `${s.speed_over_ground_mps.toFixed(1)} m/s` : "—"} />
        <Stat label="Heading" value={s?.heading_deg != null ? `${Math.round(s.heading_deg)}°` : "—"} />
      </div>
      <div>
        {!delivery && <>
        <div className="flex justify-between"><span className="panel-title">Simulated area coverage</span><span className="font-mono text-xs">{pct(env?.coverage_fraction)}</span></div>
        <div className="mt-2 h-1.5 rounded-full bg-muted"><div className="h-full rounded-full bg-accent transition-all" style={{ width: pct(env?.coverage_fraction ?? 0) }} /></div>
        <div className="mt-2 font-mono text-xs text-muted-foreground">{((env?.coverage_fraction ?? 0) * SEARCH_AREA_KM2).toFixed(2)} / {SEARCH_AREA_KM2.toFixed(2)} km² · {env?.searched_region_count ?? 0} / {env?.known_region_count ?? 240} cells visited</div>
        </>}
        <div className="mt-2 font-mono text-xs text-muted-foreground">Mission: {mp ? `${mp.envelope.mission_id} · ${prog?.status.replace("_", " ")} · ${pct(prog?.completion_fraction)}` : "none"}</div>
        {delivery && <div className="mt-2 font-mono text-xs text-accent">{delivery.item} → {fleet.registry.require(delivery.recipientId).display_name} · {delivery.phase}</div>}
        {prog?.detail && <div className="mt-1 font-mono text-xs text-muted-foreground">{prog.detail}</div>}
        {delivery && targetPosition && <div className="mt-3 grid gap-1 font-mono text-xs">
          <span className="panel-title">Receiving boat · simulated GPS</span>
          <span>{targetPosition.latitude_deg.toFixed(5)}° N · {targetPosition.longitude_deg.toFixed(5)}° E</span>
          <span className="text-muted-foreground">Distance to boat: {targetDistance?.toFixed(0) ?? "—"} m</span>
        </div>}
      </div>

      <div className="flex flex-col gap-2 border-t border-border pt-4">
        <div className="panel-title">Assign mission</div>
        <div className="flex gap-1" role="group" aria-label="Mission type">
          <Button size="sm" variant={missionType === "search" ? "default" : "outline"} aria-pressed={missionType === "search"} onClick={() => setMissionType("search")}>Independent recon</Button>
          <Button size="sm" variant={missionType === "delivery" ? "default" : "outline"} aria-pressed={missionType === "delivery"} onClick={() => setMissionType("delivery")}>Delivery</Button>
        </div>
        {missionType === "search" ? <>
          <input className="field" aria-label="Objective" value={objective} onChange={(e) => setObjective(e.target.value)} placeholder="Objective" />
          <input className="field font-mono" aria-label="Search area ID" value={area} onChange={(e) => setArea(e.target.value)} placeholder="Search area ID" />
        </> : <>
          <label className="panel-title" htmlFor="delivery-item">Item</label>
          <input id="delivery-item" className="field" value={item} onChange={(e) => setItem(e.target.value)} placeholder="Sensor, equipment…" />
          <label className="panel-title" htmlFor="delivery-recipient">Receiving boat</label>
          <select id="delivery-recipient" className="field" value={recipient} onChange={(e) => setRecipient(e.target.value)}>
            {recipients.map((b) => <option key={b.boat_id} value={b.boat_id}>{b.display_name}</option>)}
          </select>
        </>}
        <div className="flex flex-wrap gap-2">
          <Button size="sm" disabled={!!active || (missionType === "search" ? !objective.trim() || !area.trim() : !item.trim() || !recipient)} onClick={() => fleet.assign(boatId, { objective: missionType === "search" ? objective.trim() : `Deliver ${item.trim()} to ${fleet.registry.require(recipient).display_name}`, search_area_id: area.trim(), time_limit_s: null, reward_reference: null, ...(missionType === "delivery" ? { delivery: { item: item.trim(), recipient_boat_id: recipient } } : {}) })}>Send mission</Button>
          <Button size="sm" variant="outline" disabled={!active} onClick={() => active && fleet.cancel(boatId, active, "operator cancelled")}>Cancel mission</Button>
        </div>
      </div>
      <div className="flex flex-col gap-2">
        <div className="panel-title">Safe state</div>
        <div className="flex flex-wrap gap-2">
          <button className="btn" onClick={() => fleet.safeState(boatId, "hold_position")}>Hold position</button>
          <button className="btn btn-danger" onClick={() => fleet.safeState(boatId, "stop_propulsion")}>Stop propulsion</button>
          <button className="btn" onClick={() => fleet.safeState(boatId, "return_home")}>Return home</button>
        </div>
        <div className="font-mono text-xs text-muted-foreground">{pending ? `${pending} command(s) awaiting acknowledgement` : "All commands acknowledged"}</div>
      </div>

      <div className="grid grid-cols-2 gap-4 border-t border-border pt-4">
        <div>
          <div className="panel-title">Obstacles</div>
          {obs?.tracks.length ? obs.tracks.map((t) => (
            <div key={t.track_id} className="mt-1 font-mono text-xs">{t.range_m}m @ {t.relative_bearing_deg}° · <span className={(t.collision_risk ?? 0) > 0.6 ? "text-destructive" : "text-muted-foreground"}>risk {pct(t.collision_risk)}</span></div>
          )) : <div className="mt-1 font-mono text-xs text-muted-foreground">Clear</div>}
        </div>
        <div>
          <div className="panel-title">Services</div>
          {health?.services.map((h) => (
            <div key={h.name} className="mt-1 flex justify-between font-mono text-xs"><span>{h.name}</span><span className={h.status === "ok" ? "text-success" : "text-warning"}>{h.status}</span></div>
          ))}
        </div>
      </div>
    </div>
  );
}
