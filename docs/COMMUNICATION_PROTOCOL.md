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

- Mission assignment: accepted if motion is not inhibited, no other mission is active and the search area is known; otherwise rejected with a reason. Assignment never rearms inhibition.
- Mission cancellation: a matching mission is cleared locally and zero is attempted immediately. Accepted only when that application succeeds; otherwise a rejected ACK explains that local cancellation completed but zero application failed. Ordinary successful cancellation does not latch inhibition; stop/fault inhibition remains latched.
- Safe-state command: `hold_position` and `stop_propulsion` set SAFE_STATE and latch motion inhibition before fallible work. Accepted only when zero application succeeds; otherwise rejected with a failure reason, without releasing inhibition. Cancellation scope remains matching-only when a mission ID is supplied. `return_home` is rejected: not implemented.
- Navigation goal: rejected. Geographic-to-local conversion is OPEN.
- Configuration update: rejected. Not implemented.

These are the accepted software stop/fault policies in ADR-0007 H1-H3. No fields or message versions changed. Successful sink application is not an assertion of physical stopping; timestamp acceptance and device watchdog semantics remain unresolved.

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
