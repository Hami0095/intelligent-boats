# CLAUDE.md - FMS

The Fleet Management System manages the boats. It talks to each boat individually; boats never talk to each other. Read the root `CLAUDE.md` first.

## Responsibilities (foundation scope)

- Boat identities (`core/fleet.py`).
- The inbound endpoint: validate, de-duplicate, store, acknowledge (`core/endpoint.py`).
- The outbound queue of commands awaiting acknowledgement (`communication/outbox.py`).
- Building mission, cancellation and safe-state commands (`missions/`).
- Storing boat-originated data as received (`data/`), and an audit trail (`logging/`).

Not in scope yet: a dashboard, a fleet optimiser, a production backend, a database, a transport.

## Rules for this module

- Import only the standard library, `pydantic`, `marine_contracts` and `fms`. The architecture tests enforce this.
- Never import `ai_box` or `adapters`. The boat is known only through envelopes.
- Only registered boats may send or receive messages.
- Boat-originated data originates on the boat. The FMS stores it and stamps receipt time. Do not reinterpret it.
- Commands are never silently dropped. A full queue raises.
- Duplicate messages are processed once. Out-of-order messages are kept and flagged.

## Open items that touch this module

Database and storage (who owns boat data, retention), transport, audit durability, configuration update semantics, and the mission-area catalogue. See `docs/OPEN_DECISIONS.md`.

## Tests

`python -m pytest fms/tests` for unit tests. End-to-end boat-to-FMS behaviour belongs in `tests/integration/`.
