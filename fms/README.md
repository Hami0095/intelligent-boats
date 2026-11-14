# fms

The Fleet Management System foundation. It manages boat identities, receives boat telemetry and events, and builds mission commands for the per-boat outbox.

Layout (`src/fms/`):

| Package | Responsibility |
|---|---|
| `core/` | Boat identities (`fleet.py`) and the inbound endpoint (`endpoint.py`) |
| `communication/` | In-memory outbound queue with acknowledgement tracking (`outbox.py`) |
| `missions/` | Builds mission, cancellation and safe-state commands |
| `data/` | Storage of boat-originated messages (in memory for now) |
| `logging/` | Audit trail |
| `config/` | `FMS_*` environment configuration |

The outbox exposes queued commands for a caller to deliver and retains them until a matching ACK, whether accepted or rejected. Re-enqueueing an identical pending envelope is a no-op; reusing its message ID for a different envelope is rejected without replacing the original. Unknown ACKs and ACKs from another registered boat do not clear a pending command and are recorded in the audit log; unregistered boat IDs are refused. There is not yet a runtime command dispatcher, timeout, or reconnect scheduler. The loopback integration tests deliver commands manually. Data and audit records are in memory.

Scope of this phase: contracts, skeletons and tests. There is no dashboard, optimiser, or production backend. Persistence and the transport are OPEN decisions.

Run the tests from the repository root: `python -m pytest fms/tests`.
