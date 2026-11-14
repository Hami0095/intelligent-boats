import type { OperatingMode } from "@/lib/fms/contracts";
import type { DeliveryState } from "@/lib/fms/delivery";
export const modeLabel: Record<OperatingMode, string> = { idle: "Idle", autonomous: "Searching", safe_state: "Safe state", returning_home: "Returning", fault: "Fault" };
export const activityLabel = (mode: OperatingMode, delivery?: DeliveryState | null) =>
  mode === "autonomous" && delivery ? (delivery.phase === "handoff" ? "Handing over" : "Delivering") : modeLabel[mode];
export const modeTone: Record<OperatingMode, string> = { idle: "text-muted-foreground", autonomous: "text-accent", safe_state: "text-warning", returning_home: "text-primary", fault: "text-destructive" };
export const modeFill: Record<OperatingMode, string> = { idle: "fill-muted-foreground", autonomous: "fill-accent", safe_state: "fill-warning", returning_home: "fill-primary", fault: "fill-destructive" };
export const time = (t: number) => new Date(t).toLocaleTimeString([], { hour12: false });
export const pct = (v: number | null | undefined) => (v == null ? "—" : `${Math.round(v * 100)}%`);
