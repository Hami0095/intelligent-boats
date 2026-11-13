# Autonomous Marine System

Software foundation for a fleet of autonomous unmanned surface vessels (USVs). Each boat searches an assigned area for a target or reward, avoids collisions and reports to a central Fleet Management System (FMS). There is no boat-to-boat communication.

This repository is an **engineering foundation**, not a finished autonomous boat. It establishes module boundaries, typed contracts, working mock integration and tests, so that several engineers and their AI tools can build on it without breaking each other's work.

## Architecture at a glance

```
            +-----------------------+                     +-----------------------+
            |        FMS            |   marine_contracts  |        AI Box         |
            |  identities, storage, |<------ envelopes -->|  services, perception |
            |  mission dispatch     |   (JSON, versioned) |  environment, memory, |
            +-----------------------+                     |  decision, motion     |
                                                          +-----------+-----------+
                                                                      |
                                                     ports (ai_box.core.ports)
                                                                      |
                                                          +-----------v-----------+
                                                          |       adapters        |
                                                          | sensors, propulsion,  |
                                                          | FMS link, Isaac Sim   |
                                                          +-----------------------+
```

- **Perception** handles collision avoidance only. **Environment knowledge** handles search progress. They are separate modules.
- **Isaac Sim** is only the final demonstration environment, behind an adapter. It is not imported by the core.

## Repository layout

| Path | Contents |
|---|---|
| `interfaces/` | Shared message contracts (`marine_contracts`) |
| `ai-box/` | Onboard software (`ai_box`) |
| `fms/` | Fleet management foundation (`fms`) |
| `adapters/` | Mock and placeholder adapters |
| `tests/` | Contract, architecture-boundary and integration tests |
| `docs/` | System documentation, ADRs, open decisions |
| `agents/`, `.claude/agents/`, `CLAUDE.md`, `AGENTS.md` | Instructions for AI coding assistants |
| `scripts/` | Developer utilities, including a runnable demo |

## Setup

Requires Python 3.10 or newer.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e interfaces -e ai-box -e fms -e adapters pytest
```

Tests also run without installing, because `pytest.ini` puts the source packages on the path:

```bash
python -m pytest
```

## Run the demo

A boat built entirely from mock adapters runs a few control cycles and reports to the FMS:

```bash
python scripts/demo_mock_boat.py
```

## Status

| Area | Status |
|---|---|
| Contracts (envelope, payloads, versioning, validation) | Implemented, tested |
| AI Box services, lifecycle, bus, bridge, command routing | Implemented, tested with mocks |
| Environment knowledge (regions, visits, search status) | Implemented with placeholder grid indexer |
| Exploration policy and reward interface | Reference baseline policy; reward is a placeholder |
| Perception | Pipeline and interfaces; no detector, no tracking, no risk estimate |
| Motion | Interfaces and a safe hold-position controller; no navigation algorithm |
| FMS | Identities, endpoint, outbox, mission dispatch, in-memory store; no dashboard |
| Adapters | Mock sensors, position, propulsion, loopback link; Isaac Sim is a stub; no hardware |

Unresolved decisions are listed in `docs/OPEN_DECISIONS.md`.

## Documentation

- `docs/SYSTEM_OVERVIEW.md` - what the system does
- `docs/SYSTEM_ARCHITECTURE.md` - boundaries and modules
- `docs/COMMUNICATION_PROTOCOL.md` - message families and envelope
- `docs/DEVELOPMENT_WORKFLOW.md` - how to contribute and test
- `docs/INTEGRATION_GUIDE.md` - adding adapters and the Isaac Sim path
- `docs/decisions/` - architecture decision records

For contributors, start with `CONTRIBUTING.md`, then `agents/GIT_AND_PR_STANDARD.md` for branch and PR rules. For AI coding assistants, start with `CLAUDE.md` and `AGENTS.md`.
