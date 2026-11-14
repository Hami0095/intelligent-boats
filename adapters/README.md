# adapters

Every device, network and simulator dependency lives here. The AI Box and the FMS stay independent of all of them.

| Package | Status | Implements |
|---|---|---|
| `sensors/` | Mock sensor and position sources | `SensorSource`, `PositionSource` |
| `propulsion/` | Mock sink | `PropulsionSink` |
| `fms/` | In-process loopback link | `FmsLink` |
| `simulation/mock_vessel.py` | Deterministic, explicit-step mock vessel | `PositionSource`, `PropulsionSink` |
| `simulation/isaac_sim/` | Placeholder, raises `NotImplementedError` | Sensor and propulsion ports |
| `hardware/` | Not started | Real devices |

Rule: an adapter may import `ai_box.core.ports`. Nothing in `ai_box/` may import an adapter.

`MockVessel` is isolated test infrastructure, not a physical model. Its constructor requires explicit mock-only speed and turn-rate parameters. For its synthetic local frame, heading `0` points along `+x`, and positive heading and rudder turn counterclockwise. For each step, `distance = thrust * speed_mps_at_full_thrust * duration_s` and `heading_delta = rudder * abs(thrust) * turn_rate_deg_s_at_full_command * duration_s`; position is advanced along the updated heading. Each `apply()` command is consumed by one explicit `step(duration_s)`. No scheduler, inertia, drag, current, braking or command expiry is modeled. It returns only local position and heading, leaving geographic position, speed and uncertainty unavailable. It is not wired by default into `build_boat` and cannot enable real actuation.

Run the isolated state-response and AI Box/FMS safe-state checks with:

```bash
python -m pytest tests/integration/test_boat_fms_roundtrip.py adapters/tests/test_adapters.py -k mock_vessel
```

These tests demonstrate deterministic mock state updates and zero-default inhibition, not autonomous waypoint navigation or realistic vessel dynamics.
