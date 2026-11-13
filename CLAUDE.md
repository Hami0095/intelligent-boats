# CLAUDE.md - project-wide instructions

Read this file before changing anything in this repository. Other AI assistants should read `AGENTS.md`, which states the same rules.

## What the system is

We are building the software for a fleet of **autonomous unmanned surface vessels (USVs)**. Each boat works independently. A central **Fleet Management System (FMS)** assigns missions and receives telemetry. **There is no boat-to-boat communication and no swarm behaviour.**

Each boat must: receive missions from the FMS, understand its surroundings, search an assigned area for a target or reward, avoid collisions, control its own propulsion through defined interfaces, keep memory of what it has searched, and report telemetry, progress, observations and events to the FMS.

## How the boat works (two separate concerns)

1. **Obstacle detection and collision avoidance.** Detection exists to prevent collisions with rocks, large fish, other boats and similar objects. It is NOT semantic object recognition. It produces collision-relevant information (range, bearing, risk) for the navigation system. A camera alone does not give reliable distance or coordinates. Sensor calibration, fusion and position estimation are explicit concerns.
2. **Environment knowledge and reward-seeking exploration.** This is a different responsibility. It records where the boat has been and what it has searched, so the boat does not circle the same ground. The reward definition is not yet known. The boat does not know where the reward is.

**Never merge these two.** Obstacle perception lives in `ai-box/src/ai_box/perception/`. Environment knowledge lives in `ai-box/src/ai_box/environment/`. They communicate only through the event bus and typed messages.

## The AI Box

The AI Box is the onboard software environment: a set of independent **Services** managed by a `ServiceManager`, not one large model. Modules:

- `core/`: lifecycle, event bus, abstract ports (`ports.py`) and the composition-independent app handle
- `config/`, `health/`: configuration and health aggregation
- `services/`: sensor ingest, FMS bridge, command router
- `perception/`: collision-relevant detection
- `environment/`: region knowledge, independent of any mapping algorithm
- `memory/`: short-term, mission and persistent memory. Records carry timestamps, provenance and confidence.
- `decision/`: mission handling, exploration policy interface, reward interface
- `motion/`: goals, desired motion, control and normalised propulsion commands
- `telemetry/`: boat state and service health messages
- `bootstrap.py`: the only composition root. It wires adapters into the AI Box.

## The FMS

The FMS is separate from the AI Box and talks only to boats, through `marine_contracts` envelopes. It manages boat identities, stores boat-originated data, queues commands with acknowledgement tracking and keeps an audit log. It does not implement a dashboard, optimiser or production backend yet. Database technology and ownership of stored data are OPEN decisions (`docs/OPEN_DECISIONS.md`).

## Why Isaac Sim is only a final integration environment

NVIDIA Isaac Sim is used for the final simulation and demonstration. It is **not** our development environment, **not** the runtime architecture and **not** a dependency of the core software. Simulator code exists only in `adapters/src/adapters/simulation/isaac_sim/`. `tests/contracts/test_boundaries.py` fails the build if any core package imports a simulator.

## Repository structure

```
interfaces/   shared, versioned message contracts (marine_contracts). Pure data, no I/O.
ai-box/       onboard software (ai_box). Depends on interfaces only.
fms/          fleet management (fms). Depends on interfaces only.
adapters/     device, network and simulator adapters. Implement ai_box.core.ports.
tests/        cross-cutting contract, boundary and integration tests
docs/         system documentation and ADRs (docs/decisions/)
agents/       engineering context for agents (read agents/CLAUDE.md)
.claude/agents/  subagent definitions per engineering role
scripts/      developer utilities
```

Each Python package uses a `src/` layout. This is ADR-0001.

## Coding conventions

- Python 3.10+, type hints on every public function, `from __future__ import annotations`.
- Pydantic models for messages (frozen, `extra="forbid"`). Plain frozen dataclasses for in-process value types.
- Dependency injection through constructors. Services receive their collaborators; they do not import concrete adapters.
- Standard `logging` with logger names under `ai_box.*` or `fms.*`.
- Configuration comes from environment variables (`AIBOX_*`, `FMS_*`). No secrets in the repository.
- No new third-party dependency without an ADR. The current runtime dependency set is pydantic only.

## Testing expectations

- Run `python -m pytest` from the repository root. It must pass before any change is considered done.
- Every contract change needs a test in `tests/contracts/`. Every new behaviour needs a unit test in its module's `tests/`. Cross-module behaviour needs an integration test in `tests/integration/`.
- Tests must use the mock adapters, never real hardware or a simulator.

## Architectural constraints

- The AI Box must not import `fms`, `adapters` or any simulator. The FMS must not import AI Box internals. Both communicate only through `marine_contracts`.
- Hardware, transport and database choices are OPEN. Do not commit to one by writing code that depends on it.
- Do not invent hardware capabilities, sensor specifications, motor specifications or mission requirements. If a value is not in the brief or in a confirmed decision, mark it as an assumption in the code and in `docs/OPEN_DECISIONS.md`.
- Do not implement a navigation algorithm, object detector, trained model, reward learning or production database unless a task explicitly asks for it.

## How agents should update documentation

- A change to a message, payload or envelope field updates `docs/COMMUNICATION_PROTOCOL.md` and bumps `interfaces/contracts/README.md` rules if compatibility changes.
- A change to a module's responsibility updates that module's `CLAUDE.md` and `docs/MODULE_RESPONSIBILITIES.md`.
- A significant choice gets an ADR in `docs/decisions/`. Use the template there.
- An unresolved question goes in `docs/OPEN_DECISIONS.md`, marked `STATUS: OPEN` or `STATUS: PROPOSED`. Never present an assumption as a confirmed requirement.

## Git and pull requests

Branch names, commit messages, PR format, review and merge rules are in `agents/GIT_AND_PR_STANDARD.md`. Agents must follow it.

## Commands

```bash
python -m pytest                     # all tests (run from the repository root)
python scripts/demo_mock_boat.py     # runnable end-to-end demo with mock adapters
python scripts/export_schemas.py     # export JSON Schema for the contracts
```

See `CONTRIBUTING.md` for the workflow and `agents/CLAUDE.md` for agent-specific rules.
