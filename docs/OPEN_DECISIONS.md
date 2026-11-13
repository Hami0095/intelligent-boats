# Open decisions

Each entry says what is undecided, why it matters, what the foundation does meanwhile, and who should decide. Nothing here is a confirmed requirement.

| # | Decision | Status | Foundation behaviour meanwhile | Needs input from |
|---|---|---|---|---|
| 1 | Transport between boat and FMS (MQTT, WebSocket, ROS 2 bridge, other) | OPEN | `FmsLink` protocol; in-process loopback only | Communications, FMS |
| 2 | FMS database technology, and which data is stored where | OPEN | In-memory store; boat data kept as received | FMS, data |
| 3 | Ownership of boat-originated data after it reaches the FMS (retention, correction, deletion) | OPEN | Store keeps everything in memory; nothing is persisted | FMS, data |
| 4 | Local frame origin and axes, and the geographic-to-local transform | OPEN | Position is held in local metres; geographic goals are rejected | Motion, localisation |
| 5 | Position estimation and sensor fusion (GPS, IMU, odometry, camera) | OPEN | Position source is a port; confidence is a fixed placeholder (0.5) | Perception, hardware |
| 6 | Reward definition and what counts as "found" or "search complete" | OPEN | `RewardSignal` returns no reward; no completion logic | Mission owners |
| 7 | How search coverage is measured from sensors (sweep model) | OPEN | Only visits are recorded; no region becomes "searched" | Perception, environment |
| 8 | Region partitioning scheme for the environment model | OPEN | `GridIndexer` with a placeholder cell size of 10 m | Environment |
| 9 | Obstacle tracking across frames | OPEN | Frame-local identifiers only | Perception |
| 10 | Collision-risk estimation (method, inputs, units) | OPEN | `collision_risk` is always unset | Perception, motion |
| 11 | Mapping from normalised thrust and rudder to physical propulsion | OPEN (depends on CAD) | Mock sink only | CAD, hardware, motion |
| 12 | Operating modes beyond the current set, and the return-home behaviour | OPEN | `return_home` is rejected | Operations, motion |
| 13 | Schema compatibility: whether MINOR versions may add optional fields | OPEN | Strict models, so receivers must be upgraded first | Interfaces owner |
| 14 | Runtime scheduling model (single thread, threads, asyncio) | OPEN | Services are ticked by the caller (`app.tick()`) | Core |
| 15 | Offline buffer size and policy for telemetry and events | PROPOSED limit (1000), policy OPEN | Drop-oldest in the boat bridge | Communications |
| 16 | Which message types are critical (require acknowledgement) | PROPOSED | Set per type in `MESSAGE_SPECS` | Communications, FMS |
| 17 | Duplicate-detection window and sequence-number semantics | PROPOSED (window 10,000 per boat) | Implemented in the FMS endpoint | FMS |
| 18 | Handling of exceptions in safety-relevant event handlers | OPEN | Errors are logged and isolated | Core, safety |
| 19 | Meaning of mission search-area identifiers, and who defines areas | OPEN | Areas are supplied to the boat locally | FMS, mission owners |
| 20 | Durability of the audit log | OPEN | In memory, mirrored to logging | FMS |
| 21 | Configuration update semantics (validation, rollout, rollback) | OPEN | Rejected with a reason | Operations |
| 22 | Dependency policy (which libraries are approved) | PROPOSED: pydantic only | Enforced by the architecture tests | Team |

When a decision is made, write an ADR in `decisions/`, update this table, and change the relevant code and tests.
