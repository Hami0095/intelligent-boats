export type FleetDataSource = { kind: "simulation" } | { kind: "rest"; apiBaseUrl: string };

export function resolveFleetDataSource(
  mode: string,
  requested?: string,
  apiBaseUrl = "/api/v1",
): FleetDataSource {
  const source = requested ?? (mode === "research" ? "rest" : "simulation");
  if (mode === "research" && source !== "rest") {
    throw new Error("Research mode requires the REST data source");
  }
  if (source === "simulation") return { kind: "simulation" };
  if (source !== "rest") throw new Error(`Unknown fleet data source: ${source}`);
  const base = apiBaseUrl.replace(/\/+$/, "");
  if (!base.startsWith("/") && !/^https?:\/\//.test(base)) {
    throw new Error("The FMS API base must be an HTTP URL or an absolute path");
  }
  if (base.startsWith("//") || /[?#]/.test(base)) {
    throw new Error("The FMS API base must not contain a query, fragment or protocol-relative URL");
  }
  return { kind: "rest", apiBaseUrl: base };
}

export function configuredFleetDataSource(): FleetDataSource {
  return resolveFleetDataSource(
    import.meta.env.MODE,
    import.meta.env["VITE_FLEET_DATA_SOURCE"],
    import.meta.env["VITE_FMS_API_BASE_URL"] ?? "/api/v1",
  );
}
