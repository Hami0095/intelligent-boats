# fms

The Fleet Management System foundation. It manages boat identities, receives boat telemetry and events, and dispatches missions.

Layout (`src/fms/`):

| Package | Responsibility |
|---|---|
| `core/` | Boat identities (`fleet.py`) and the inbound endpoint (`endpoint.py`) |
| `communication/` | Outbound queue with acknowledgement tracking (`outbox.py`) |
| `missions/` | Builds mission, cancellation and safe-state commands |
| `data/` | Storage of boat-originated messages (in memory for now) |
| `logging/` | Audit trail |
| `config/` | `FMS_*` environment configuration |

Scope of this phase: contracts, skeletons and tests. There is no dashboard, optimiser, or production backend. Persistence and the transport are OPEN decisions.

Run the tests from the repository root: `python -m pytest fms/tests`.
