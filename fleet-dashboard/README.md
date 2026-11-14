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
- Independent recon inside search area A; unique visited-cell coverage and a recorded chart trail.
- Searched targets are skipped; boats hold after full coverage without completing the mission. Recon reassignment retains coverage in memory. Necessary transit or safety returns may cross visited water.
- Three simulated hazards and shared A* collision avoidance for search, delivery and home returns.
- Simulated delivery to a moving recipient, nearby automatic handoff, then own-home return.
- Hold, stop propulsion, return home and mission cancellation controls.
- Delivery history saved in this browser.

## Integration boundary

This is currently a standalone simulation, not a connection to real AI boxes. Fleet state, search coverage and trails reset on reload; delivery history alone survives in browser storage. Chart shading is a simulated visited-cell estimate, not verified sensor coverage.

To connect the Python AI boxes, implement a shared network transport for their existing FmsLink send/receive interface and replace the dashboard loopback transport with command publishing and telemetry reception. Verify mission payload parity first; dashboard delivery and home-return behavior must not be assumed to exist onboard. Keep physical emergency stop and onboard collision protection independent of the dashboard, and test with motors disconnected first.
