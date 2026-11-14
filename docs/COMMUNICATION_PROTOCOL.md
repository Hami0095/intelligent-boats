# Communication protocol

**STATUS: message families and envelope are ACCEPTED for the foundation. Transport and delivery guarantees are PROPOSED or OPEN** (see `interfaces/protocols/README.md`).

The authoritative definitions are the Python models in `interfaces/src/marine_contracts/`. This document is the human-readable summary.

## Envelope

Every boat <-> FMS message is wrapped in an envelope:

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | `MAJOR.MINOR.PATCH` | Contract version. This build supports major version 1. |
| `message_id` | UUID | Unique per message. Used for ACK correlation; the FMS currently de-duplicates boat-originated non-ACK messages. |
| `boat_id` | string | Matches `^[a-z0-9][a-z0-9-]{1,62}$`. |
| `mission_id` | string or null | Required for mission-related messages. |
| `message_type` | enum | Selects the payload model. |
| `timestamp` | timezone-aware datetime | When the message was created. Current producers use UTC; validation accepts any timezone-aware offset without normalization. |
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

## Verified foundation behaviour

These are capabilities observed in the current code and mock integration tests. They do not imply a deployed transport or stronger delivery guarantees.

- `Envelope` validates the payload for its message type, rejects unknown payload fields, requires a timezone-aware timestamp and supports schema major version 1. `decode_envelope()` validates raw JSON; the loopback link passes already-validated `Envelope` objects.
- The FMS endpoint requires a registered `boat_id`, rejects boat-originated traffic with an FMS-to-boat message type, stores valid boat messages in memory and replies to critical boat messages. Its bounded duplicate window (default 10,000 IDs per boat) applies to boat-originated non-ACK messages. Out-of-order messages are stored and audited, not rejected. ACKs are correlated by `acknowledged_message_id`; a matching accepted or rejected ACK clears the queued FMS command.
- The FMS outbox assigns per-boat sequence numbers, rejects enqueueing when that boat's queue is full, and exposes unacknowledged envelopes for a caller to re-offer. Enqueueing the same envelope ID again for that boat is a no-op; reusing that pending ID for a different envelope raises an error and preserves the original command. There is no FMS command dispatcher or reconnect scheduler in this foundation; the loopback integration tests manually deliver queued commands.
- The AI Box bridge creates outbound envelopes using its configured boat ID and increasing sequence numbers. Its bounded buffer drops the oldest message when full, retains messages after `ConnectionError` for a later tick, and drops other link-send errors. It removes an outbound message when `send()` returns; it does not retain critical boat messages until their FMS ACK arrives. A temporarily queued message alone does not make the bridge health report degraded; a connection failure, drop, or rejected inbound message does.
- The AI Box bridge rejects inbound envelopes with a different boat ID or a boat-to-FMS-only message type, logs the rejection, and reports degraded health without replying with an ACK. The FMS endpoint can verify that an envelope names a registered boat, but the current link does not provide authenticated peer identity to prove which boat sent it.
- Boat-state telemetry is emitted each application tick; service health is emitted every 10 telemetry ticks. Environment progress is emitted when a mission is active, with the active mission ID in the envelope. The summary contains aggregate counts and coverage only; FMS stores the received envelope and payload by boat and message type, not region-level records. The mission service records `VISITED` observations from the position source, but no current service produces `SEARCHED` or sensor-derived `OBSERVED` environment records. There is no standalone environment-observation message. Obstacle summaries are emitted only when detections exist, and their collision risk remains unset unless a risk estimator provides one. Forwarding obstacle summaries is not evidence that collision avoidance is functional. Operational events are forwarded when an AI Box service publishes them.
- Mission assignment is accepted only when the boat is not motion-inhibited, has no active mission, and knows the referenced local search area. The AI Box currently uses `search_area_id`; it does not interpret `objective`, `time_limit_s` or `reward_reference`. Mission progress reports acceptance, rejection and aborts; mission-completion semantics are not implemented.
- FMS boat data and audit records are in-memory only. The mock link is in-process; no network transport is implemented.

### Duplicate commands and acknowledgement lifecycle

- The FMS de-duplicates boat-originated non-ACK envelopes by `message_id` and boat within its configured bounded window. A duplicate is audited and not stored or acknowledged again, even if the original was critical and its ACK was lost. The same ID with a changed payload is also treated as a duplicate.
- The AI Box does not de-duplicate FMS commands. Re-delivery of an assignment is processed again (an already-active mission causes a rejection); cancellation of a mission already cancelled is rejected; repeated safe-state commands each run the existing safe-stop path. The current safe-state path remains inhibited, but no exactly-once or command-idempotency guarantee exists.
- A matching ACK removes an FMS command whether it says accepted or rejected. Unknown IDs and ACKs bearing another registered boat's ID do not clear the command and are recorded with `queue cleared=False`; an unregistered boat ID is rejected by the registry. ACK envelopes themselves are not deduplicated or sequence-checked: an identical duplicate after the first removal is harmless to queue state and is audited with `queue cleared=False`. Whether conflicting reuse of an ACK envelope ID should be rejected remains open. ACK outcomes are in the in-memory audit, not a durable command-status ledger.
- There is no ACK timeout, retry interval, expiration, or automatic re-offer scheduler. A command without an ACK remains in the in-memory outbox until a matching ACK is received or the FMS process exits. `unacknowledged()` permits a caller to re-offer it, but replaying that command can cause the AI Box to process it again.
- FMS command sequence numbers are maintained per boat. The FMS endpoint audits and stores out-of-order boat-originated data per boat; the AI Box does not enforce an inbound command ordering rule.

## Proposed delivery behaviour

The table describes protocol-level proposals, not end-to-end guarantees already provided by the foundation above.

| Concern | Proposal | Status |
|---|---|---|
| Duplicates | Receivers drop a processed `message_id`; define whether this also applies to repeated FMS-to-boat commands. | Partially implemented: bounded FMS inbound window; boat command de-duplication OPEN |
| Ordering | Sequence numbers are monotonic per sender; specify how out-of-order traffic is handled. | Partially implemented: FMS audits and stores out-of-order boat messages; broader rules OPEN |
| Acknowledgement | Critical messages are acknowledged, and senders retain them until the required acknowledgement is received. | Partially implemented: FMS replies to critical boat messages and holds commands until ACK; AI Box does not retain critical outbound messages until ACK |
| Disconnection | Define queue limits, persistence and reconnect/re-offer behavior on both sides. | Partially implemented in memory; policies and FMS dispatcher OPEN |
| Refused messages | Define retry/drop behavior for non-connection send failures. | AI Box drops non-connection send failures; end-to-end policy OPEN |
| Stale data | Receivers keep the timestamp. Staleness thresholds are decided by consumers. | PROPOSED |
| Schema compatibility | Strict models mean a new field needs a coordinated upgrade. Whether to allow additive changes is OPEN. | OPEN |
| Transport | MQTT, WebSocket, ROS 2 bridge or another option is OPEN. | OPEN |

## Verification coverage

`tests/integration/test_boat_fms_roundtrip.py` exercises the mock-link round trip for assignment acceptance and rejection, cancellation, safe-state, unsupported commands, target-boat routing, telemetry/progress/event/health reception, disconnect/reconnect buffering and inbound ID/direction rejection. Contract tests cover malformed payloads, invalid timestamps, and unsupported schema majors. FMS endpoint tests cover duplicate and out-of-order boat messages, registered identities, acknowledgement correlation and queue behavior. These tests do not establish network delivery, authenticated boat identity, persistence, or physical collision avoidance.
