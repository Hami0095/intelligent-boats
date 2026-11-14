/** Real Python HTTP server and producers -> REST view -> existing React page. */
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import path from "node:path";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import { ResearchFleetController } from "@/lib/fms/research-fleet";
import { FleetDashboardView } from "@/routes/index";

const root = path.resolve(process.cwd(), "..");
const python = path.join(root, ".venv", "bin", "python3");
let server: ChildProcessWithoutNullStreams;
let baseUrl = "";

function exited(child: ChildProcessWithoutNullStreams): Promise<void> {
  if (child.exitCode !== null || child.signalCode !== null) return Promise.resolve();
  return new Promise((resolve) => child.once("exit", () => resolve()));
}

async function produce(ticks: number, localOnly = false): Promise<void> {
  const child = spawn(
    python,
    [
      "scripts/demo_research_boats.py",
      "--api-url",
      baseUrl,
      "--ticks",
      String(ticks),
      "--interval",
      "0",
      ...(localOnly ? ["--no-geographic-position"] : []),
    ],
    { cwd: root, stdio: "pipe" },
  );
  let errors = "";
  child.stdout.resume();
  child.stderr.on("data", (chunk) => {
    errors += String(chunk);
  });
  await new Promise<void>((resolve, reject) => {
    child.once("error", reject);
    child.once("exit", (code) =>
      code === 0 ? resolve() : reject(new Error(errors || `Producer exited ${code}`)),
    );
  });
}

beforeAll(async () => {
  server = spawn(python, ["scripts/research_fms_server.py", "--port", "0"], {
    cwd: root,
    stdio: "pipe",
  });
  let output = "";
  let errors = "";
  server.stderr.on("data", (chunk) => {
    errors += String(chunk);
  });
  await new Promise<void>((resolve, reject) => {
    const timeout = setTimeout(() => {
      server.kill("SIGINT");
      reject(new Error(`Backend startup timed out: ${errors}`));
    }, 10000);
    server.once("error", (error) => {
      clearTimeout(timeout);
      reject(error);
    });
    server.once("exit", (code) => {
      if (!baseUrl) {
        clearTimeout(timeout);
        reject(new Error(`Backend exited ${code}: ${errors}`));
      }
    });
    server.stdout.on("data", (chunk) => {
      output += String(chunk);
      const url = output.match(/http:\/\/127\.0\.0\.1:\d+/)?.[0];
      if (url) {
        baseUrl = url;
        clearTimeout(timeout);
        resolve();
      }
    });
  });
});

afterEach(cleanup);
afterAll(async () => {
  server?.kill("SIGINT");
  if (server) await exited(server);
});

describe("research live reporting", () => {
  it("renders real received values, updates them, preserves missing GPS, and never substitutes simulation", async () => {
    // This is the platform fetch, not a test response or intercepted request.
    const fleet = new ResearchFleetController(`${baseUrl}/api/v1`);
    await fleet.refresh();
    expect(fleet.snapshots).toEqual([]);
    const view = render(<FleetDashboardView fleet={fleet} />);
    expect(screen.getByText(/Waiting for AI Box reports/)).toBeInTheDocument();
    expect(view.container.querySelectorAll('[aria-label^="Reported position"]')).toHaveLength(0);

    await produce(10);
    await act(async () => {
      await fleet.refresh();
    });
    view.rerender(<FleetDashboardView fleet={fleet} />);
    expect(screen.queryByText(/Waiting for AI Box reports/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Select mock-01" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Select mock-02" })).toBeInTheDocument();
    expect(screen.getByText("59.33000, 18.11200")).toBeInTheDocument();
    expect(screen.getByText("90°")).toBeInTheDocument();
    expect(screen.getAllByText("Mock AI Box · REST").length).toBeGreaterThan(0);
    expect(screen.getByText("fms-bridge")).toBeInTheDocument();
    expect(screen.getByText(/research-mock-01 · accepted/)).toBeInTheDocument();
    expect(view.container.querySelectorAll('[aria-label^="Reported position"]')).toHaveLength(2);
    expect(fleet.boats.size).toBe(0);
    expect(fleet.obstacles).toEqual([]);
    expect(screen.queryByRole("button", { name: "Send mission" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Select mock-02" }));
    expect(screen.getByText("59.33400, 18.12000")).toBeInTheDocument();
    expect(screen.getByText("180°")).toBeInTheDocument();
    expect(fleet.snapshots.map((boat) => boat.boat_id)).toEqual(["mock-01", "mock-02"]);

    await produce(2);
    await act(async () => {
      await fleet.refresh();
    });
    view.rerender(<FleetDashboardView fleet={fleet} />);
    expect(screen.getByText("59.33380, 18.12050")).toBeInTheDocument();

    await produce(1, true);
    await act(async () => {
      await fleet.refresh();
    });
    view.rerender(<FleetDashboardView fleet={fleet} />);
    expect(screen.getByText("Not supplied")).toBeInTheDocument();
    expect(view.container.querySelectorAll('[aria-label^="Reported position"]')).toHaveLength(0);
    expect(fleet.registry.all()).toHaveLength(2);

    const lastReports = JSON.stringify(fleet.snapshots);
    server.kill("SIGINT");
    await exited(server);
    await act(async () => {
      await fleet.refresh();
    });
    view.rerender(<FleetDashboardView fleet={fleet} />);
    expect(screen.getByRole("alert")).toHaveTextContent("FMS API unavailable");
    expect(JSON.stringify(fleet.snapshots)).toBe(lastReports);
    expect(fleet.boats.size).toBe(0);
    expect(fleet.registry.all()).toHaveLength(2);
    fleet.dispose();
  });
});
