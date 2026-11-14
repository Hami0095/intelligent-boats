import { cleanup, render, renderHook, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { BoatPanel } from "@/components/fleet/BoatPanel";
import { SeaChart } from "@/components/fleet/SeaChart";
import { useFleet } from "@/components/fleet/use-fleet";
import { Route } from "@/routes/index";
import { FleetController } from "./fleet";
import { ResearchFleetController } from "./research-fleet";
import { report, response, snapshot } from "./research-fixtures";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("research presentation", () => {
  it("does not draw an invented heading when GPS is present but heading was omitted", async () => {
    const boat = snapshot();
    boat.messages = {
      "boat.state": report(boat.boat_id, "boat.state", {
        operating_mode: "idle",
        position: { latitude_deg: 59.331, longitude_deg: 18.115 },
      }),
    };
    const fleet = new ResearchFleetController(
      "/api/v1",
      vi.fn<typeof fetch>().mockResolvedValue(response([boat])),
    );
    await fleet.refresh();
    render(<SeaChart fleet={fleet} selected={boat.boat_id} onSelect={() => {}} />);
    expect(fleet.latestState(boat.boat_id)?.heading_deg).toBeNull();
    expect(
      screen.getByLabelText(`Reported position ${boat.boat_id}`).querySelector("path"),
    ).toBeNull();
  });

  it("uses the research controller and displays waiting when the backend has no reports", async () => {
    vi.stubEnv("MODE", "research");
    vi.stubEnv("VITE_FLEET_DATA_SOURCE", "rest");
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockResolvedValue(response([])));
    const tick = vi.spyOn(FleetController.prototype, "tick");
    const hook = renderHook(() => useFleet());
    await waitFor(() => expect(hook.result.current?.loading).toBe(false));
    expect(hook.result.current).toBeInstanceOf(ResearchFleetController);
    expect(hook.result.current?.registry.all()).toHaveLength(0);
    expect(tick).not.toHaveBeenCalled();
    hook.unmount();
    const Page = Route.options.component;
    if (!Page) throw new Error("Missing dashboard page");
    render(<Page />);
    expect(
      await screen.findByText("Waiting for AI Box reports. No boat data has arrived."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Select Skarv" })).not.toBeInTheDocument();
  });

  it("reuses the panel/chart for actual values and missing geographic data without simulated features", async () => {
    const boats = [snapshot(), snapshot("research-02", "Research Bravo", null)];
    const fleet = new ResearchFleetController(
      "/api/v1",
      vi.fn<typeof fetch>().mockResolvedValue(response(boats)),
    );
    await fleet.refresh();
    render(
      <>
        <BoatPanel fleet={fleet} boatId="research-02" />
        <SeaChart fleet={fleet} selected="research-02" onSelect={() => {}} />
      </>,
    );
    expect(screen.getByText("42°")).toBeInTheDocument();
    expect(screen.getByText("Not supplied")).toBeInTheDocument();
    expect(screen.getByText("Mock AI Box · REST")).toBeInTheDocument();
    expect(
      screen.getByText(/Searched regions: 2 · Known regions: 8 · Coverage: 25%/),
    ).toBeInTheDocument();
    expect(screen.getByText(/Read-only research reporting/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Send mission" })).not.toBeInTheDocument();
    expect(screen.getByLabelText("Reported position research-01")).toBeInTheDocument();
    expect(screen.queryByLabelText("Reported position research-02")).not.toBeInTheDocument();
    expect(screen.queryByText("Clear")).not.toBeInTheDocument();
    expect(screen.queryByText("SEARCH AREA A")).not.toBeInTheDocument();
  });
});
