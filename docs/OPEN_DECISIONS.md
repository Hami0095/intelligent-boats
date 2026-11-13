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
| 23 | Reference navigation controller conventions and normalised parameters: heading zero/rotation relative to local axes, rudder sign, gains and thrust | PROPOSED; production conventions OPEN | Zero controller remains default; no navigation implementation. Explicit mock conversion/sign and parameters only are proposed | Motion, localisation, hardware, system architect |
| 24 | Persistent motion inhibition, cancellation timing and authority to resume after safe state or fault | OPEN; hardening prerequisite PROPOSED | `safe_stop` emits zero once; an active mission can regenerate a goal. Cancellation only clears the goal. Proposed first PR latches stop/fault inhibition, stops immediately on goal clearing and adds no automatic/remote rearming | Motion, integration, operations, system architect |
| 25 | Navigation state validity: age/future tolerance, heading/position coherence, uncertainty requirements and clock-failure timestamp policy | OPEN | One state timestamp, no freshness guard. Proposed fixture policy rejects stale/future state; last-validated timestamp for emergency zero is a proposal only, with no delivery or freshness guarantee | Localisation, motion, core, hardware |
| 26 | Reference-controller arrival semantics and unsupported speed-cap handling | PROPOSED | Default controller always emits zero. Proposed reference stops at/below goal radius and for any supplied speed cap; normalised thrust has no confirmed speed meaning | Motion, mission owners, hardware |

## Navigation milestone proposals

The [design and readiness assessment](NAVIGATION_CONTROLLER_READINESS.md) and [ADR-0007](decisions/ADR-0007-opt-in-local-navigation-controller.md) are PROPOSED, not accepted requirements. Items #4, #5, #11, #12, #14 and #18 remain OPEN. No controller or runtime behaviour was changed by this assessment.

Explicit mock assumptions only: state and target share one consistent local frame; heading conversion and rudder sign are declared by the fixture; state samples are coherent for the scripted test; parameters are test inputs. These assumptions establish no localisation capability, hull dynamics, propulsion mapping or production threshold. Missing speed, geographic position and uncertainty remain unknown. A command-generation test with scripted positions is not evidence that commands caused movement or that zero propulsion physically stops a vessel.

When a decision is made, write an ADR in `decisions/`, update this table, and change the relevant code and tests.
