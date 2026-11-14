import type { GeoPosition } from "./contracts";
import type { ConnectionSource } from "./connection";

export interface TemperatureReading {
  boatId: string;
  celsius: number;
  at: number;
  position: GeoPosition;
  source: ConnectionSource;
}

/** A spatial demo field, not measured water or a calibrated sensor model. */
export function simulatedWaterTemperature(position: GeoPosition) {
  return Math.round((9 + Math.sin((position.latitude_deg - 59.33) * 100) * 0.8 + Math.cos((position.longitude_deg - 18.12) * 100) * 0.4) * 10) / 10;
}

export class TemperatureLog {
  records: TemperatureReading[] = [];
  record(reading: TemperatureReading) {
    if (!Number.isFinite(reading.celsius) || !Number.isFinite(reading.at) ||
      !Number.isFinite(reading.position.latitude_deg) || !Number.isFinite(reading.position.longitude_deg)) return false;
    this.records.unshift({ ...reading, position: { ...reading.position } });
    if (this.records.length > 2000) this.records.pop();
    return true;
  }
  csv() {
    return ["boat_id,temperature_c,recorded_at_utc,latitude_deg,longitude_deg,source",
      ...this.records.map((r) => [r.boatId, r.celsius, new Date(r.at).toISOString(), r.position.latitude_deg, r.position.longitude_deg, r.source].join(","))].join("\n");
  }
}