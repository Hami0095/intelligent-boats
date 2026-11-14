import type { FleetController } from "./fleet";

/** The existing dashboard's read model; research commands remain unavailable. */
export type FleetView = Pick<
  FleetController,
  | "registry"
  | "store"
  | "audit"
  | "outbox"
  | "boats"
  | "coverage"
  | "temperatures"
  | "obstacles"
  | "deliveries"
  | "traffic"
  | "subscribe"
  | "getVersion"
  | "latestState"
  | "connection"
  | "assign"
  | "cancel"
  | "safeState"
  | "recordTemperature"
> & {
  dataSource: "simulation" | "rest";
  loading: boolean;
  error: string | null;
};
