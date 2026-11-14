# Research: mock AI Box reports to the existing FMS dashboard

This is a local, software-only reporting prototype. It preserves the existing main dashboard simulation and default zero-command controller. No production deployment or remotely reachable write endpoint is created.

## Baseline and environments

The research baseline is `3863f12`, including merged dashboard PRs #12/#14 and merged MockVessel PR #13. The original checkout's uncommitted waypoint-controller changes are not part of this baseline. `research` did not exist locally or remotely, so it was created and published from the refreshed main. Implementation is on a dependent review series ending at `feat/fms-research-rest-integration`, ultimately targeting research. No PR targets main. The original worktree remains untouched. See [the validation and review record](RESEARCH_REST_VALIDATION.md).

| Environment | Source | Build/start | Behaviour |
|---|---|---|---|
| Main demonstration | Existing browser `FleetController` / `MockBoat` simulation | Existing `bun run dev` / `bun run build` | Existing simulated vessels, search, temperature and delivery features |
| Research | Python AI Box envelopes received/stored by Python FMS | `bun run dev:research` / `bun run build:research` | Read-only received reports, explicit waiting/error/unavailable states, no simulated fallback |

The repository shows a Lovable connection and a Vite/TanStack/Nitro configuration whose comments describe Cloudflare as the default target. It contains no actual deployment URL, research project binding, credentials or Python hosting configuration. None is assumed or changed here.

## Actual data path

```text
two independent MockPositionSource + MockPropulsionSink instances
  -> existing AI Box telemetry / mission / health services
  -> existing FMS bridge -> marine_contracts envelopes
  -> RestFmsLink (one HTTP POST per send)
  -> injected loopback HTTP server -> existing FmsEndpoint
  -> existing InMemoryFleetStore
  -> ResearchFleet latest-message projection -> GET dashboard API
  -> research fetch/decoder/view adapter -> existing React dashboard components
```

Neither AI Box nor FMS imports the other's implementation. Contracts remain data-only. The client/server adapters contain HTTP I/O; a script composes the server with FMS. The single-thread server avoids adding concurrent access to the existing unlocked in-memory store.

## API

All routes are under `/api/v1` on the explicitly loopback-bound development server. JSON responses are not cached.

| Method and route | Result |
|---|---|
| `POST /api/v1/boat-messages` | Validate one existing envelope, known boat and boat-originated/either direction, then call FMS. Return `{ "replies": [existing reply envelopes] }` |
| `GET /api/v1/boats` | `{ "boats": [...] }` containing only registered identities with received reports; empty before any reports arrive |
| `GET /api/v1/boats/{id}/state` | Latest received boat-state wrapper, or `null` before that report arrives |
| `GET /api/v1/boats/{id}/progress` | `{ "mission": wrapper-or-null, "environment": wrapper-or-null }` |
| `GET /api/v1/boats/{id}/health` | Latest received service-health wrapper, or `null` |

A stored wrapper is `{ "envelope": <the existing envelope>, "received_at": <FMS receipt timestamp> }`. A boat snapshot contains `boat_id`, `display_name`, `last_received_at`, and `messages`, keyed by the six existing dotted boat report types. Each missing report is null. Header IDs, sequence, version, mission association and timestamps remain available in the raw snapshots. Browser-only adaptation converts message names and timestamps for the existing UI without rewriting the shared Python contracts.

Valid ingestion returns HTTP 200. Malformed JSON returns 400; invalid envelopes/direction return 422; unknown sender IDs return 403; unknown read IDs/routes return 404. POST requires `application/json` and a positive Content-Length; oversized bodies are refused. This is validation, not authenticated peer identity.

The REST link queues actual reply envelopes for `receive()`; it does not manufacture mission acceptance. Network/timeouts/5xx use the bridge's existing connection-failure path; explicit HTTP refusals or malformed replies are errors. The adapter contains no retry loop or durable queue. Existing FMS deduplication, ACK and in-memory lifetime limitations remain as documented in `COMMUNICATION_PROTOCOL.md`.

## Run locally

Use the research checkout/worktree, not an editable environment pointing at another checkout. A separate virtual environment prevents accidental imports from uncommitted work elsewhere.

```bash
python3 -m venv .venv
.venv/bin/python3 -m pip install 'pydantic>=2.5,<3' pytest pytest-cov ruff mypy
```

Terminal 1, from the repository root:

```bash
.venv/bin/python3 scripts/research_fms_server.py
```

The server binds `127.0.0.1:8765` and registers `mock-01` and `mock-02`. `--port` changes the local port; `--boat ID[:NAME]` can register explicit identities. The factory refuses non-loopback binds. These are development defaults, not discovered hosting settings.

Terminal 2:

```bash
cd fleet-dashboard
bun install --frozen-lockfile
bun run dev:research
```

Research development runs at `http://127.0.0.1:5174`. Its GET-only proxy reaches the loopback backend at port 8765. That URL is a local development address, not a remote deployment. Before producers start, the dashboard shows a waiting/no-data state.

Terminal 3, from the repository root:

```bash
.venv/bin/python3 scripts/demo_research_boats.py
```

This starts two separately identified AI Boxes and steps their explicitly scripted sources once a second. Existing reporting sends boat state, mission/environment progress and health (every tenth telemetry tick). Each has its own link, state and command-recording sink. A one-time local scripted mission-assignment event exercises the existing command router; dashboard commands and a REST command dispatcher are outside this milestone.

For a finite deterministic sequence, use `--ticks 10 --interval 0`. Use `--no-geographic-position` to verify that local-only state stays geographically unknown. Inspect actual received data with:

```bash
curl http://127.0.0.1:8765/api/v1/boats
curl http://127.0.0.1:8765/api/v1/boats/mock-01/state
```

The explicit geographic fixture sequences start at `(59.3300, 18.1120)` and `(59.3340, 18.1200)`, within the existing chart view. They are synthetic source readings independent of the local search coordinates. No geographic conversion is implemented. All propulsion commands remain zero; changed displayed positions are scripted inputs, not autonomous travel or physical dynamics.

## Data-source configuration and unsupported fields

`--mode research` selects REST and refuses a simulation override. Normal builds retain simulation as their default. Newly introduced, optional configuration is `VITE_FLEET_DATA_SOURCE` (`simulation` or `rest`, with research requiring rest) and `VITE_FMS_API_BASE_URL` (default `/api/v1`). These names are defined by this implementation; no remote value or secret is assumed. A different API origin requires its own explicitly configured read routing/CORS; the local server does not enable public cross-origin access.

Research never constructs browser mock vessels, advances their simulation, restores simulated delivery history, creates hazards, infers chart coverage cells, or falls back to random data. It labels the source `Mock AI Box · REST`. Polling errors are shown explicitly; previously received data remains recognizable as old/stale, rather than becoming replacement telemetry.

Unknown geographic position, battery, speed, heading, coverage or unreceived reports remain unknown. Python has no temperature or delivery payload parity with this UI; those functions are labelled unavailable. Mission/stop controls are read-only/unavailable until a real command API is separately implemented and reviewed. Environment aggregates are not geographic coverage geometry, searched evidence or mission completion.

## Tests and verification

```bash
source .venv/bin/activate
python -m pytest
python -m pytest --cov=interfaces/src --cov=ai-box/src --cov=fms/src --cov=adapters/src --cov-report=term-missing --cov-fail-under=90
python -m ruff check .
python -m ruff format --check .
python -m mypy ai-box/src fms/src interfaces/src adapters/src
python -m pytest tests/contracts/test_boundaries.py
python scripts/validate_repo_structure.py
cd fleet-dashboard
bun run build
bun run build:research
bun run test
bun run test:research:e2e
bun run lint
bunx tsc --noEmit
```

The HTTP/API tests start real loopback servers, check validation and identities, and retrieve actual stored messages. The round-trip tests run two actual AI Box runtimes through the REST link and assert exact source positions, heading, mission association, health, isolation and null geographic data. The separate research live DOM test starts a real Python backend and producer process, fetches actual API data, and renders the real dashboard view. It does not mock network responses and is separate from simulation unit tests. Tests requiring local sockets need execution permission in restricted environments.

An interactive browser connection was unavailable in the development session; manual visual verification uses the three startup commands above. Exact executed test/build results are reported in the task/PR validation record; do not infer a completed GitHub Actions run from local checks.

## Separate remote deployment: manual, not performed

1. Keep the existing main/Lovable deployment's branch, build command and simulator configuration unchanged.
2. Create a separate research deployment/project only with explicit service access and authorization, using the research branch and `build:research` (or explicit REST source configuration). No hosting provider, project URL or branch binding is invented here.
3. Provision a separately reviewed Python service outside the frontend worker runtime. The repository currently supplies a loopback-only development server, not production hosting infrastructure.
4. Configure read routing to that backend in the separate environment. Do not expose `/api/v1/boat-messages` through a public unauthenticated proxy. A remotely reachable write path requires access restrictions, TLS/network configuration and reviewed credentials; this implementation supplies none and refuses a public bind.
5. Keep all real vessel credentials and production sensor/hardware use out of the prototype. Persistence, durable delivery, automatic command dispatch and operational recovery remain unresolved.

The repository-side local integration and separate build are complete when validation passes. Remote deployment, authentication and interactive visual confirmation remain explicit manual work, not claimed deliverables.
