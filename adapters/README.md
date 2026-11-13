# adapters

Every device, network and simulator dependency lives here. The AI Box and the FMS stay independent of all of them.

| Package | Status | Implements |
|---|---|---|
| `sensors/` | Mock sensor and position sources | `SensorSource`, `PositionSource` |
| `propulsion/` | Mock sink | `PropulsionSink` |
| `fms/` | In-process loopback link | `FmsLink` |
| `simulation/isaac_sim/` | Placeholder, raises `NotImplementedError` | Sensor and propulsion ports |
| `hardware/` | Not started | Real devices |

Rule: an adapter may import `ai_box.core.ports`. Nothing in `ai_box/` may import an adapter.
