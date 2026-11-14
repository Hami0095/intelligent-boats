import type { GeoPosition } from "./contracts";

export const HANDOFF_DISTANCE_M = 15;
export function distanceMetres(a: GeoPosition, b: GeoPosition) {
  return Math.hypot((b.latitude_deg - a.latitude_deg) * 111000,
    (b.longitude_deg - a.longitude_deg) * 111000 * Math.cos(a.latitude_deg * Math.PI / 180));
}
export function moveToward(a: GeoPosition, b: GeoPosition, metres: number) {
  const distance = distanceMetres(a, b), ratio = distance > 0 ? Math.min(1, Math.max(0, metres) / distance) : 0;
  const north = (b.latitude_deg - a.latitude_deg) * 111000;
  const east = (b.longitude_deg - a.longitude_deg) * 111000 * Math.cos(a.latitude_deg * Math.PI / 180);
  return { position: { latitude_deg: a.latitude_deg + (b.latitude_deg - a.latitude_deg) * ratio,
    longitude_deg: a.longitude_deg + (b.longitude_deg - a.longitude_deg) * ratio },
    heading: (Math.atan2(east, north) * 180 / Math.PI + 360) % 360 };
}
export interface DeliveryState {
  item: string; recipientId: string;
  phase: "outbound" | "handoff" | "returning" | "completed";
  handoffTicks: number; handedOver: boolean;
}