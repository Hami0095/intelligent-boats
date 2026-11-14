# Integration guide

## Adding an adapter

1. Pick the port in `ai_box/core/ports.py` that the device or simulator fulfils.
2. Create a module under `adapters/src/adapters/<kind>/`. Keep all vendor imports inside this package.
3. Convert device data to `SensorSample` or `VehicleState`, and convert `PropulsionCommand` into device commands. Do not pass vendor types across the port.
4. Add tests that exercise the adapter through the port, using the same assertions the mock adapters satisfy.
5. Wire it in a composition script, or pass it to `build_boat()`. The AI Box itself is not edited.

## Isaac Sim (final demonstration)

**STATUS: PROPOSED.** Isaac Sim is only reachable through `adapters/src/adapters/simulation/isaac_sim/`.

What exists now:

- `IsaacSimAdapter` implements the sensor, position and propulsion ports on top of a `SimulatorBackend` protocol (`backend.py`). It imports no simulator code.
- Without a backend, every call raises `SimulatorUnavailableError`. The AI Box reports the sensor as degraded and keeps running.
- `isaac_backend.py` is the only module that imports `isaacsim`. `open_isaac_backend(usd_path)` starts the simulator headless. It raises `SimulatorUnavailableError` when `isaacsim` is missing.
- Reading the boat pose and writing commands in the real backend are NOT implemented yet. They raise `SimulatorUnavailableError` with an explicit message. They need the CAD boat asset and the articulation API of the installed Isaac Sim version.
- Tests use a fake backend (`adapters/tests/test_isaac_sim_adapter.py`) and run without a simulator.

Next steps:

1. Set `AIBOX_SIM_USD_PATH` to the CAD boat asset, once it is available.
2. Implement pose reading and command writing in `IsaacSimBackend` against the installed Isaac Sim version.
3. Run the AI Box unchanged, with the Isaac Sim adapter in place of the hardware adapters. Pass the adapter as both `sensors` and `position`.
4. Keep Isaac Sim imports out of every other package. `tests/contracts/test_boundaries.py` enforces this, with the exemption in ADR-0009.
5. Run the simulator scenarios as integration tests, outside the default unit suite, because they need the simulator installed.

The simulator version, licensing, host requirements and how the CAD model is imported are OPEN (`OPEN_DECISIONS.md`).

## Adding real hardware

Follow the same pattern: one adapter per device, behind the existing port. The sensor, GPS/IMU and motor-controller choices are OPEN and depend on the CAD and hardware decisions.

## Connecting the FMS transport

Implement `FmsLink` (send and receive envelopes, raise `ConnectionError` while offline). The transport is OPEN; the loopback link in `adapters/src/adapters/fms/` shows the expected behaviour.
