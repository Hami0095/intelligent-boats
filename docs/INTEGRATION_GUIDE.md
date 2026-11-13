# Integration guide

## Adding an adapter

1. Pick the port in `ai_box/core/ports.py` that the device or simulator fulfils.
2. Create a module under `adapters/src/adapters/<kind>/`. Keep all vendor imports inside this package.
3. Convert device data to `SensorSample` or `VehicleState`, and convert `PropulsionCommand` into device commands. Do not pass vendor types across the port.
4. Add tests that exercise the adapter through the port, using the same assertions the mock adapters satisfy.
5. Wire it in a composition script, or pass it to `build_boat()`. The AI Box itself is not edited.

## Isaac Sim (final demonstration)

**STATUS: PROPOSED.** Isaac Sim is only reachable through `adapters/src/adapters/simulation/isaac_sim/`.

Plan:

1. Implement `IsaacSimAdapter` so that it provides simulated sensor samples and applies propulsion commands. It replaces the placeholder that raises `NotImplementedError`.
2. Run the AI Box unchanged, with the Isaac Sim adapter in place of the hardware adapters.
3. Keep Isaac Sim imports out of every other package. `tests/contracts/test_boundaries.py` enforces this.
4. Run the simulator scenarios as integration tests, outside the default unit suite, because they need the simulator installed. Their setup is OPEN.

The simulator version, licensing, host requirements and how the CAD model is imported are OPEN (`OPEN_DECISIONS.md`).

## Adding real hardware

Follow the same pattern: one adapter per device, behind the existing port. The sensor, GPS/IMU and motor-controller choices are OPEN and depend on the CAD and hardware decisions.

## Connecting the FMS transport

Implement `FmsLink` (send and receive envelopes, raise `ConnectionError` while offline). The transport is OPEN; the loopback link in `adapters/src/adapters/fms/` shows the expected behaviour.
