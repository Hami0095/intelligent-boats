# System architecture

**Status:** PROPOSED for the detailed module split, ACCEPTED for the boundary rules (see ADR-0002, ADR-0003, ADR-0005).

## Boundaries

```
  FMS  <---- marine_contracts (envelopes over a transport, OPEN) ---->  AI Box
                                                                          |
                                                                  ai_box.core.ports
                                                                          |
                                                                     adapters
                                                                          |
                              hardware devices | simulator (Isaac Sim, final demo only)
```

- **interfaces (`marine_contracts`)**: the only code shared by the AI Box and the FMS. Pure data definitions.
- **ai-box (`ai_box`)**: onboard intelligence and services. Knows nothing about the FMS implementation or any device.
- **fms (`fms`)**: fleet management. Knows boats only through contracts. Never imports AI Box internals.
- **adapters**: implement the AI Box ports, and the FMS link. The only place devices, networks and simulators are touched.

## AI Box internal modules

| Module | Responsibility |
|---|---|
| `core` | Service lifecycle (`ServiceManager`), event bus, abstract ports, operating state |
| `config`, `health` | Environment configuration; health aggregation |
| `services` | Sensor ingest, FMS bridge (the only sender/receiver of FMS traffic), command router |
| `perception` | Collision-relevant detection, frame to summary conversion, tracking interface (OPEN) |
| `environment` | Region indexing, observations, per-region search status. Mapping-independent interface |
| `memory` | Short-term records, mission memory, persistent store interface. All records timestamped with provenance and confidence |
| `decision` | Mission lifecycle, exploration policy interface and reference policy, reward interface |
| `motion` | Vehicle state, navigation goals, normalised propulsion commands, control interface and a safe default controller |
| `telemetry` | Boat state and service health messages |
| `bootstrap` | Composition root. The only place where adapters are wired in |

## Obstacle avoidance data flow

```
Sensor adapter -> SensorSample -> sensor-ingest -> perception
                                                     |
                               Detection (bearing, range, category, confidence)
                                                     |
                           ObstacleSummary (no risk value yet) -> FMS bridge -> FMS
```

The collision-risk estimator and cross-frame tracker are OPEN. Until they exist, `collision_risk` is always `None`. The navigation controller does not yet consume obstacle data.

## Environment and search data flow

```
Position source -> VehicleState -> search-mission
                                     |  record VISITED observation
                                     v
                             environment knowledge  <-- SEARCHED observations (sensor coverage model OPEN)
                                     |
                       exploration policy (unsearched, prefer never-visited, nearest)
                                     |
                              NavigationGoal -> motion
```

A visit does not count as a search. Only a SEARCHED observation changes a region to searched. How search coverage is measured is OPEN.

## Motion and propulsion data flow

```
NavigationGoal + VehicleState -> MotionController -> PropulsionCommand (thrust, rudder in [-1, 1])
                                                            |
                                                    PropulsionSink (adapter)
```

Normalised commands cross the port. The mapping to motors and thrusters is adapter-specific and depends on CAD and hardware decisions (OPEN).

## Memory responsibilities

- **Short-term operational memory**: recent records, bounded in size, with an age limit. Stale records are not presented as current.
- **Mission memory**: regions covered during one mission. Cleared when the mission ends.
- **Persistent environment knowledge**: observations kept across missions. Backing store is OPEN.

## Adapter architecture

Each external dependency sits behind a Protocol in `ai_box/core/ports.py`:

| Port | Purpose | Mock | Real |
|---|---|---|---|
| `SensorSource` | Normalised sensor samples | `MockSensorAdapter` | OPEN |
| `PositionSource` | Vehicle state estimate | `MockPositionSource` | OPEN (GPS/IMU/fusion) |
| `PropulsionSink` | Normalised propulsion commands | `MockPropulsionSink` | OPEN |
| `FmsLink` | Envelope transport | `LoopbackFmsLink` | OPEN (transport not chosen) |
| `ObstacleDetector` | Detections from one sample | `NullObstacleDetector` | OPEN |

Contract tests in `tests/` run the same behaviour against each implementation.

## Final Isaac Sim workflow

See `INTEGRATION_GUIDE.md`. In short: an Isaac Sim adapter implements the same sensor and propulsion ports; the AI Box is unchanged.
