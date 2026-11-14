# ADR-0003: Isaac Sim only at the integration boundary

**Status:** ACCEPTED

## Context

Isaac Sim is the final simulation and demonstration environment. It is not the development environment or the runtime architecture. Importing it into core code would tie the boat software to a simulator and make hardware use harder.

## Decision

- Isaac Sim imports exist only in `adapters/src/adapters/simulation/isaac_sim/`.
- No other package may import a simulator. This is enforced by `tests/contracts/test_boundaries.py`, with the simulator-folder exemption in ADR-0009.
- The adapter talks to the simulator only through a `SimulatorBackend` protocol. Without a backend it raises `SimulatorUnavailableError`, and the AI Box reports the sensor as degraded.

## Consequences

- The AI Box runs unchanged with mocks, simulators or hardware.
- The simulator version and setup remain open until the integration work starts.
