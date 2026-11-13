# Communication protocol

**STATUS: message families and envelope are ACCEPTED for the foundation. Transport and delivery guarantees are PROPOSED or OPEN** (see `interfaces/protocols/README.md`).

The authoritative definitions are the Python models in `interfaces/src/marine_contracts/`. This document is the human-readable summary.

## Envelope

Every boat <-> FMS message is wrapped in an envelope:

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | `MAJOR.MINOR.PATCH` | Contract version. This build supports major version 1. |
| `message_id` | UUID | Unique per message. Used for de-duplication and acknowledgement. |
| `boat_id` | string | Matches `^[a-z0-9][a-z0-9-]{1,62}$`. |
| `mission_id` | string or null | Required for mission-related messages. |
| `message_type` | enum | Selects the payload model. |
| `timestamp` | UTC datetime | When the message was created. |
| `sequence_number` | integer >= 0 | Monotonic per sender, per boat. |
| `payload` | object | Validated against the model for `message_type`. Unknown fields are rejected. |

Encoding is JSON. No transport library is imported by the contracts.

## Boat -> FMS

| Message type | Payload | Critical (ack required) |
|---|---|---|
| `boat.state` | `BoatStatePayload`: mode, optional position and uncertainty, speed, heading, battery | No |
| `boat.mission_progress` | `MissionProgressPayload`: status, optional completion fraction, detail | Yes |
| `boat.obstacle_summary` | `ObstacleSummaryPayload`: list of tracks with range, bearing, confidence, optional risk | No |
| `boat.environment_progress` | `EnvironmentProgressPayload`: searched and known region counts, coverage | No |
| `boat.operational_event` | `OperationalEventPayload`: severity, machine code, message, context | Yes |
| `boat.service_health` | `ServiceHealthPayload`: per-service status | No |

## FMS -> Boat

| Message type | Payload | Critical |
|---|---|---|
| `fms.mission_assignment` | objective, opaque search area ID, optional time limit and reward reference | Yes |
| `fms.navigation_goal` | goal ID, geographic target, optional speed limit and acceptance radius | Yes |
| `fms.mission_cancellation` | reason | Yes |
| `fms.configuration_update` | version, parameters (string, int, float or bool) | Yes |
| `fms.safe_state_command` | action: `hold_position`, `stop_propulsion` or `return_home`, reason | Yes |

## Either direction

| Message type | Payload |
|---|---|
| `ack` | acknowledged message ID, accepted flag, optional reason |

## Current behaviour of the boat

- Mission assignment: accepted if no other mission is active and the search area is known; otherwise rejected with a reason.
- Mission cancellation: accepted if it matches the active mission.
- Safe-state command: `hold_position` and `stop_propulsion` are accepted and both stop propulsion in the foundation. `return_home` is rejected: not implemented.
- Navigation goal: rejected. Geographic-to-local conversion is OPEN.
- Configuration update: rejected. Not implemented.

## Proposed delivery behaviour

| Concern | Proposal | Status |
|---|---|---|
| Duplicates | Receiver drops a `message_id` it has processed. The FMS keeps a bounded window (default 10,000 per boat). | PROPOSED |
| Ordering | Sequence numbers are monotonic per sender. Out-of-order messages are processed and flagged. | PROPOSED |
| Acknowledgement | Critical messages are acknowledged. The sender keeps unacknowledged commands for re-offer after reconnection. | PROPOSED |
| Disconnection | The boat keeps outbound messages in a bounded queue (drop-oldest). The FMS refuses new commands for a boat when its queue is full. | PROPOSED, limits OPEN |
| Refused messages | If the link refuses one message (not a connection failure), the boat drops it so the queue does not stall. | PROPOSED |
| Stale data | Receivers keep the timestamp. Staleness thresholds are decided by consumers. | PROPOSED |
| Schema compatibility | Strict models mean a new field needs a coordinated upgrade. Whether to allow additive changes is OPEN. | OPEN |
| Transport | MQTT, WebSocket, ROS 2 bridge or another option is OPEN. | OPEN |
