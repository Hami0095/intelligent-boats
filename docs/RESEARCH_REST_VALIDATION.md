# Research REST integration: validation and review record

## Outcome and initial assessment

The local reporting path is complete: two independent mock AI Box runtimes send existing envelopes over real HTTP to the existing Python FMS, and the existing React dashboard displays the received data in research mode. No PR targets main, no PR is merged, and no deployment settings or remote services are changed.

The baseline dashboard uses React 19, TanStack Start/Router, Vite 8 and Bun. Its framework-free TypeScript `FleetController` creates browser mock boats and advances synthetic state. Python FMS was not connected to that dashboard. The implementation reuses the dashboard components and view store, Python bootstrap/reporting/bridge, `FmsLink`, contract encoders/decoders, FMS registry/endpoint/store, and mock position/propulsion ports. No new runtime dependency or shared contract is introduced.

`research` was published at `3863f1256abece591b1dee60340c7ca32d3764a1`. The fetched main ref remained at the same commit; the original worktree and its uncommitted waypoint work were preserved. Normal frontend builds still select simulation by default. Research mode requires REST and has no simulated fallback.

## Executed local checks

Python checks ran from the isolated research repository root with Python 3.13.6 in its own `.venv`, avoiding editable imports from the original checkout.

| Check | Exact result |
|---|---|
| `.venv/bin/python3 -m pytest --cov=interfaces/src --cov=ai-box/src --cov=fms/src --cov=adapters/src --cov-report=term-missing --cov-fail-under=90` | **284 passed in 2.70s**, **94.56%** total coverage; 90% gate passed |
| Architecture tests | **9 passed**; unchanged boundary tests also pass in the full suite |
| `.venv/bin/python3 -m ruff check .` | All checks passed |
| `.venv/bin/python3 -m ruff format --check .` | **157 files already formatted** |
| `.venv/bin/python3 -m mypy ai-box/src fms/src interfaces/src adapters/src` | Success: **78 source files** |
| `.venv/bin/python3 scripts/validate_repo_structure.py` | Passed |
| `git diff --check` | Passed |
| `bun run test` | **49 passed**, **9 test files**, **1.32s** |
| `bun run test:research:e2e` | **1 passed**, **1 test file**, **1.42s** |
| `bunx tsc --noEmit` | Passed |
| `bun run build` | Passed; normal simulation build |
| `bun run build:research` | Passed; separate REST build |
| ESLint on task-touched frontend files | Passed |
| Full frontend ESLint | **Fails: 277 errors, 6 warnings**, all errors in 15 untouched baseline files |

The baseline frontend lint audit had 455 errors and 6 warnings. Each remaining error file has exactly its baseline error count; the new work adds no lint errors. Existing formatting debt is left outside this integration's scope. This is not a claim that repository-wide frontend lint is green.

The real HTTP tests cover envelope validation, unknown identities, wrong directions, nonfinite JSON rejection before storage, metadata, null reports, per-boat isolation and two actual AI Box runtimes. The live DOM test starts the actual Python backend and mock producer processes, performs native network fetches, renders `FleetDashboardView`, checks exact positions/headings/mission/health, then verifies new data, missing GPS and backend failure without simulated fallback. API responses are not mocked in that end-to-end test.

A separate local development check started Python on port 8765 and the research Vite server on 5174. The proxy returned an empty fleet before producers, then exact reports from both AI Boxes; the page returned 200, non-GET reads returned 405, and browser-side ingestion was not proxied (404, with backend storage unchanged). Both development servers were stopped afterward.

No interactive browser was available, so visual inspection remains manual. No GitHub Actions result is claimed. The current workflow automatically targets PRs to main, not this research review series; local checks above do not imply remote CI execution. Dependency vulnerability and secret-scanner workflow results were not claimed or substituted with local test results.

## Review series

The repository targets at most about 400 changed lines per PR. This work is split into dependent review branches; the first targets `research`, each later branch targets the preceding research task branch, and the last contains the complete runnable prototype. Review the series in order. A human must coordinate any eventual merges/retargeting so changes flow into research only; none of these branches should be merged into main.

| Order | Branch | Change |
|---|---|---|
| 1 | `docs/docs-research-rest-design` | ADR-0009, responsibilities, protocol, runbook and open questions |
| 2 | `feat/adapters-rest-reporting-link` | REST `FmsLink`, pure latest-report projection and unit tests |
| 3 | `feat/adapters-research-http-api` | Injected loopback HTTP API and validation tests |
| 4 | `feat/fms-research-mock-producers` | Server composition, two mock runtimes and actual HTTP round trips |
| 5 | `feat/fms-research-source-profile` | Explicit source selection, connection display and GET-only proxy |
| 6 | `feat/fms-decode-research-reports` | Wire validation and a view-only compatibility adapter |
| 7 | `feat/fms-read-research-fleet` | Read-only research fleet controller and isolation tests |
| 8 | `feat/fms-present-research-boat` | Existing panel presents received values and unsupported controls |
| 9 | `feat/fms-chart-received-positions` | Existing chart uses received positions |
| 10 | `feat/fms-connect-research-dashboard` | Research polling, page states and unavailable feature presentation |
| 11 | `feat/fms-research-rest-integration` | Presentation tests, live end-to-end test and explicit research commands |

## Changed files and responsibilities

- `adapters/src/adapters/fms/rest.py`, `rest_server.py`, `adapters/tests/test_rest_link.py`: HTTP transport outside core services.
- `fms/src/fms/data/research.py`, `fms/tests/test_research_projection.py`: pure latest-envelope projection.
- `scripts/research_fms_server.py`, `scripts/demo_research_boats.py`: explicit software-only composition roots and deterministic fixtures.
- `tests/integration/test_research_rest_api.py`, `test_research_rest_roundtrip.py`: real HTTP contract/storage/runtime checks.
- `fleet-dashboard/src/lib/fms/data-source.ts`, `fleet-view.ts`, `research-api.ts`, `research-fleet.ts`, `fleet.ts`: source selection and reuse of the existing view model; simulation remains the normal default.
- Frontend source/config/controller/presentation test files, `research-fixtures.ts`, `src/test/research-live.e2e.tsx`, `vitest.research.config.ts`: unit and actual network-to-view verification.
- `fleet-dashboard/src/components/fleet/{BoatPanel,ConnectionStatus,Logs,SeaChart,TemperatureLog}.tsx`, `use-fleet.ts`, `src/routes/index.tsx`: reused UI with actual data, waiting/error states and explicit unavailable fields.
- `fleet-dashboard/{research-proxy.ts,vite.config.ts,package.json,.gitignore}`: local GET routing, research commands and generated-route exclusion. Dependency declarations and `bun.lock` are unchanged.
- Root `CLAUDE.md`, `fms/CLAUDE.md`, module/frontend READMEs and frontend `AGENTS.md`, `docs/{COMMUNICATION_PROTOCOL,DATA_FLOW,MODULE_RESPONSIBILITIES,OPEN_DECISIONS}.md`, ADR index/ADR-0009, integration runbook and this record: responsibilities, limitations and operational instructions.

## Decisions, assumptions and unfinished work

ADR-0009 records the owner's explicit research-only REST request. Constructor injection, import boundaries, in-memory storage and the default zero controller are preserved. Local and geographic readings are independently scripted fixtures, not a geographic transform or propulsion simulation. The producer's local scripted mission assignment exercises reports; it is not a network command dispatcher.

OPEN_DECISIONS #1 keeps production transport open; #34 leaves remote research hosting, read routing and write access restrictions unresolved; #35 records dashboard/contract parity gaps. Unknown fields remain null/unavailable. The chart retains its existing reference extent; positions outside it may be off-canvas, while exact numeric reports remain available. No automatic rescaling or coordinate conversion is claimed.

No code blocker remains for the local prototype. Interactive visual review, owner reviews and any research merges remain manual. Remote deployment needs a separate authorized project/service and reviewed access restrictions; the development server binds only IPv4 loopback and no public URL is supplied. Authentication, persistence, command dispatch, retries, autonomous navigation, collision avoidance, hardware and simulator work are unfinished and outside this milestone. See [local startup commands and API details](RESEARCH_REST_INTEGRATION.md).
