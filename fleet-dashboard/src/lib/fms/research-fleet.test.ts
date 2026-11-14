import { afterEach, describe, expect, it, vi } from "vitest";
import { FleetController } from "./fleet";
import { ResearchFleetController } from "./research-fleet";
import { NOW, response, snapshot } from "./research-fixtures";

afterEach(() => vi.restoreAllMocks());

describe("research controller", () => {
  it("keeps independent identities and raw envelope fields while adapting the view", async () => {
    const simulation = new FleetController();
    expect(simulation.registry.all()).toHaveLength(4);
    expect(simulation.dataSource).toBe("simulation");
    const first = snapshot();
    const second = snapshot("research-02", "Research Bravo", null);
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(response([first, second]));
    const random = vi.spyOn(Math, "random");
    const fleet = new ResearchFleetController("/api/v1", fetcher);
    await fleet.refresh();
    expect(random).not.toHaveBeenCalled();
    expect(fetcher).toHaveBeenCalledWith(
      "/api/v1/boats",
      expect.objectContaining({ method: "GET" }),
    );
    expect(fleet.registry.all().map((boat) => boat.boat_id)).toEqual([
      "research-01",
      "research-02",
    ]);
    expect(fleet.boats.size).toBe(0);
    expect(fleet.latestState("research-01")?.position).toEqual({
      latitude_deg: 59.331,
      longitude_deg: 18.115,
    });
    expect(fleet.latestState("research-02")?.position).toBeNull();
    expect(fleet.snapshots[0]?.messages["boat.state"]?.envelope).toEqual(
      first.messages["boat.state"]?.envelope,
    );
    expect(fleet.store.latest("research-01", "boat_state")?.envelope.timestamp).toBe(
      Date.parse(NOW),
    );
    expect(fleet.connection("research-01", Date.parse(NOW)).state).toBe("live");
  });

  it("retains last received data on API failure without generating a fallback", async () => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(response([snapshot()]))
      .mockRejectedValueOnce(new Error("offline"));
    const fleet = new ResearchFleetController("/api/v1", fetcher);
    await fleet.refresh();
    const state = fleet.latestState("research-01");
    await fleet.refresh();
    expect(fleet.error).toBe("offline");
    expect(fleet.latestState("research-01")).toEqual(state);
    expect(fleet.registry.all()).toHaveLength(1);
    expect(fleet.boats.size).toBe(0);
    expect(() => fleet.safeState("research-01", "return_home")).toThrow("read-only");
  });
});
