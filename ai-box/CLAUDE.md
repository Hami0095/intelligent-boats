# CLAUDE.md - AI Box

The AI Box is the onboard software environment of one boat. It is a set of independent Services, not one model. Read the root `CLAUDE.md` first.

## Responsibilities

- Start, stop and monitor its services; deliver events between them.
- Ingest sensor samples and detect collision-relevant obstacles.
- Record visited and searched regions; choose where to search next.
- Hold short-term, mission and persistent memory, with timestamps and provenance.
- Turn goals into normalised propulsion commands.
- Report state, progress, obstacles, events and health to the FMS, and act on FMS commands.

## Structure (`src/ai_box/`)

| Package | Role |
|---|---|
| `core/` | Service lifecycle, event bus, ports, operating state |
| `config/` | `AIBOX_*` configuration |
| `health/` | Aggregating health |
| `services/` | Sensor ingest, FMS bridge (the only FMS I/O), command router |
| `perception/` | Detection, obstacle summary, tracking interface |
| `environment/` | Regions, observations, search status |
| `memory/` | Records, mission memory, persistent store interface |
| `decision/` | Mission service, exploration policy, reward interface |
| `motion/` | Goals, vehicle state, commands, controller interface |
| `telemetry/` | Boat state and health messages |
| `bootstrap.py` | Composition root |

## Rules for this module

- Import only the standard library, `pydantic`, `marine_contracts` and `ai_box`. The architecture tests enforce this.
- Never import an adapter, a simulator or `fms`. Devices arrive through ports in `core/ports.py`.
- A service declares `name` and `depends_on`, and implements `start`, `stop`, and optionally `tick` and `health_detail`.
- Do not sleep or block in `tick`. Sensor polling must return promptly.
- Use `None` for unknown values. Never fabricate a risk, position or reward.
- Refuse unsupported commands explicitly, with a reason.
- Motion safe-stop/fault inhibition is latched for the instance lifetime (accepted ADR-0007 H1-H3). Goals, ticks, service restarts and assignments cannot rearm; a new runtime is required. Set SAFE_STATE/inhibition before fallible safe-state handling.
- Ordinary goal clearing attempts zero immediately without latching on success. Cancellation must finish local cleanup despite stop failure and acknowledge failed zero application accurately. Clock failure may use the last validated timestamp only for an emergency zero, reported as not fresh; no valid timestamp means inhibit/report without inventing one. Bound zero attempts to one per event/tick and keep fault health degraded after callback recovery.

## Open items that touch this module

Localisation and geographic-to-local transform, search coverage model, reward definition, tracker and risk estimator, return-home, runtime scheduling, exception policy for safety handlers. See `docs/OPEN_DECISIONS.md`.

## Tests

`python -m pytest ai-box/tests` for unit tests. Cross-module behaviour belongs in `tests/integration/`.
