# Intelligent Boats Fleet Dashboard

Hackathon fleet-management dashboard with two explicit data sources. Normal development and deployment keep the existing TypeScript fleet simulation. The research mode reads reports received by the Python FMS from mock AI Boxes over REST.

## Run locally

Install Bun, then from this directory:

```sh
bun install --frozen-lockfile
bun run dev
```

Open the local address printed by Vite. Run tests with `bun run test` and create a deployment build with `bun run build`.

## Research mode

Start the local Python research FMS backend on `127.0.0.1:8765`, then run:

```sh
bun run dev:research
```

This binds the research dashboard to `127.0.0.1:5174`. It polls `GET /api/v1/boats` every 1.5 seconds. The development proxy forwards only boat-read routes to the local Python backend and refuses non-GET requests; it never proxies the message-ingestion write endpoint. Starting the dashboard does not start mock producers or create boat telemetry. Until reports arrive, the page shows a waiting state. Failed requests show an error and retain the last received values with their actual receipt timestamps; they never start the simulator.

The repository introduces these explicit, public build settings:

| Setting                  | Default                       | Meaning                                                                                  |
| ------------------------ | ----------------------------- | ---------------------------------------------------------------------------------------- |
| Vite mode `research`     | REST source                   | Selected by `dev:research` and `build:research`; cannot use simulation                   |
| `VITE_FLEET_DATA_SOURCE` | `simulation` outside research | Optional explicit `rest` source selection for a separately configured deployment         |
| `VITE_FMS_API_BASE_URL`  | `/api/v1`                     | Read API base URL; set an actual configured backend URL for a remote research deployment |

Create a research build with `bun run build:research`. Normal `bun run dev` and `bun run build` retain simulation by default. The research development proxy is not a production reverse proxy: remote research hosting must separately provide the read API URL or same-origin routing and any required origin policy. These settings are new repository configuration, not assertions that a remote service or deployment exists. Never put ingestion tokens, vessel credentials or other secrets in `VITE_*` variables. No deployment command is run by these scripts.

Research reuses the existing cards, boat panel, chart and logs. Boat identities, state, mission/environment progress, health, obstacles and latest operational events come from backend snapshots. The client preserves raw Python envelopes and adapts their dotted message names/ISO timestamps only for the existing browser view. It applies only declared contract defaults to a separate view copy and does not fabricate missing measurements.

The research interface is read-only. Delivery, command sending, home return, simulated coverage cells, static hazards and temperature readings are unavailable. Geographic markers require an actual received `position`; local coordinates are never converted to GPS. The chart remains the existing Saltsjön reference chart, so other geographic positions can be outside its view. A marker is not evidence of autonomous movement, real hardware or collision avoidance.

Frontend checks:

```sh
bun run build:research  # also generates the route tree in a fresh checkout
bun run test
bun run lint
bunx tsc --noEmit
bun run test:research:e2e
```

The separately selected live integration test requires the repository Python virtual environment. It starts a real local Python HTTP backend and mock AI Box producer and renders the actual React dashboard using API responses. The normal unit test command has no Python dependency. The live test does not replace visual browser QA or demonstrate a remotely deployed service.

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

## Integration boundary

The default source is a standalone simulation, not a connection to real AI boxes. Fleet state, search coverage and trails reset on reload; delivery history alone survives in browser storage. Chart shading is a simulated visited-cell estimate, not verified sensor coverage. Temperature values come from a simulated spatial field, not a waterproof sensor, and are labeled as simulation in the interface. These simulated records and browser delivery history are not loaded by the research source.

Research connects reporting through the Python AI Boxes' existing FmsLink boundary and FMS received-message storage. It does not add a dashboard command transport. The browser simulator's delivery, home-return, temperature and coverage features must not be assumed to exist onboard. Operational recovery, authenticated boat identity, durable transport/storage and production navigation remain separate decisions.
