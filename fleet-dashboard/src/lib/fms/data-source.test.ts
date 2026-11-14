import { describe, expect, it } from "vitest";
import { resolveFleetDataSource } from "./data-source";
import { isResearchReadRoute } from "../../../research-proxy";

describe("research source selection", () => {
  it("keeps normal development and deployment in simulation by default", () => {
    expect(resolveFleetDataSource("development")).toEqual({ kind: "simulation" });
    expect(resolveFleetDataSource("production")).toEqual({ kind: "simulation" });
  });

  it("requires REST in research mode and rejects invalid configuration rather than falling back", () => {
    expect(resolveFleetDataSource("research")).toEqual({ kind: "rest", apiBaseUrl: "/api/v1" });
    expect(() => resolveFleetDataSource("research", "simulation")).toThrow("requires the REST");
    expect(() => resolveFleetDataSource("production", "unknown")).toThrow("Unknown fleet");
    expect(resolveFleetDataSource("production", "rest", "http://127.0.0.1:8765/api/v1/")).toEqual({
      kind: "rest",
      apiBaseUrl: "http://127.0.0.1:8765/api/v1",
    });
  });

  it("does not route the write ingestion endpoint through the research read proxy", () => {
    expect(isResearchReadRoute("/api/v1/boats")).toBe(true);
    expect(isResearchReadRoute("/api/v1/boats/research-01/state")).toBe(true);
    expect(isResearchReadRoute("/api/v1/boat-messages")).toBe(false);
    expect(isResearchReadRoute("/api/v1/boats-other")).toBe(false);
  });
});
