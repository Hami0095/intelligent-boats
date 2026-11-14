# Intelligent Boats Fleet Dashboard

Hackathon fleet-management dashboard migrated from the Python FMS contracts into TypeScript. The existing Python AI-box and adapter packages remain unchanged.

## Run locally

Install Bun, then from this directory:

```sh
bun install --frozen-lockfile
bun run dev
```

Open the local address printed by Vite. Run tests with `bun run test` and create a deployment build with `bun run build`.

## Included

- Four simulated boats with position, battery, telemetry and command acknowledgements.
- Independent recon inside search area A; fleet-wide shared visited-cell coverage, distinct unsearched sections for active boats and recorded per-boat chart trails.
- Live reassignment of remaining search work when boats stop or switch missions.
- Per-boat connection source, last telemetry update time and a stale-data warning after 10 seconds. Current boats are explicitly labeled simulation, not real AI-box connections.
- Searched targets are skipped; boats hold after full coverage without completing the mission. Recon reassignment retains coverage in memory. Necessary transit or safety returns may cross visited water.
- Three simulated hazards and shared A* collision avoidance for search, delivery and home returns.
- Simulated delivery to a moving recipient, nearby automatic handoff, then own-home return.
- Simulated water-temperature readings logged with boat name, degrees Celsius, UTC time and GPS location; 10-second sampling, session-only log and CSV export.
- Hold, stop propulsion, return home and mission cancellation controls.
- Delivery history saved in this browser.

## Connecting a real AI box

The dashboard exposes an HTTP relay at `/api/public/fms-link` and this repo now ships a matching Python adapter, `adapters/src/adapters/fms/http_link.py` (`HttpFmsLink`), which implements the existing `FmsLink` send/receive protocol — plug it into `FmsBridgeService` in place of the loopback link:

```python
from adapters.fms.http_link import HttpFmsLink

link = HttpFmsLink(
    base_url="https://<your-dashboard-host>",
    boat_id="usv-05",
    token="<FMS_LINK_TOKEN>",
)
```

- `send` POSTs one boat-originated envelope; `receive` GETs and drains the FMS commands waiting for that boat. Both raise `ConnectionError` while unreachable, as the bridge expects.
- Every request carries `Authorization: Bearer <token>`; the token must match the dashboard's `FMS_LINK_TOKEN` secret. Calls without it are rejected.
- A boat is registered by the dashboard on first contact and labeled as a real AI-box connection, with last-update time and the 10-second stale-data warning.
- The relay is an in-memory mailbox per server process: messages are lost on restart and while the dashboard tab is closed. This is a hackathon demo link, not durable transport.

## Integration boundary

Fleet state, search coverage and trails reset on reload; delivery history alone survives in browser storage. Chart shading is a simulated visited-cell estimate, not verified sensor coverage. Temperature values come from a simulated spatial field, not a waterproof sensor, and are labeled as simulation in the interface.

Verify mission payload parity before relying on the link: the dashboard's simulated delivery extension is stripped from mission assignments before crossing to the boat, and dashboard home-return behavior must not be assumed to exist onboard. Keep physical emergency stop and onboard collision protection independent of the dashboard, and test with motors disconnected first.
