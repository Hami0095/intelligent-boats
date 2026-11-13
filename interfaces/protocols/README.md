# Protocol behaviour (STATUS: PROPOSED)

This document is the target behaviour for the boat <-> FMS link. None of it is
implemented against a real transport yet. See docs/COMMUNICATION_PROTOCOL.md for the full discussion.

| Concern | Proposed behaviour | Status |
|---|---|---|
| Duplication | Receivers drop a `message_id` they have already processed (bounded cache). | PROPOSED |
| Ordering | `sequence_number` is monotonic per sender per boat. Out-of-order messages are processed, flagged, not rejected. | PROPOSED |
| Acknowledgement | Messages whose spec has `critical=True` are acknowledged with an `ack` envelope. | PROPOSED |
| Stale data | Receivers keep the timestamp; consumers decide what "stale" means for their use. | PROPOSED |
| Disconnection | The boat buffers outbound telemetry and critical events while offline (bounded). | OPEN (size and policy) |
| Schema compatibility | Receivers accept any MINOR version of their supported MAJOR version. | PROPOSED |
| Transport | Not chosen. MQTT, WebSocket, ROS 2 bridge, or other are OPEN. | OPEN |
