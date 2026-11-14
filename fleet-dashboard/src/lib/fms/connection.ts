export type ConnectionSource = "simulation" | "ai-box";
export const STALE_AFTER_MS = 10000;

export function connectionStatus(source: ConnectionSource, lastUpdate: number | null, now: number) {
  const ageMs = lastUpdate === null ? null : Math.max(0, now - lastUpdate);
  return { source, lastUpdate, ageMs, state: ageMs === null ? "waiting" as const : ageMs >= STALE_AFTER_MS ? "stale" as const : "live" as const };
}