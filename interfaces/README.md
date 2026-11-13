# interfaces

Versioned data contracts shared by the AI Box, the FMS and the adapters.

- `src/marine_contracts/` - the importable Python package (pydantic models).
- `schemas/` - human-readable schema notes; generated JSON Schema can be produced with `scripts/export_schemas.py`.
- `protocols/` - transport-independent protocol behaviour (disconnects, ordering, acks). Status: PROPOSED.
- `contracts/` - versioning and compatibility rules.

Rules:
1. This package contains data definitions and validation only. No I/O, no transport libraries, no device code.
2. Every change to a payload needs a contract test in `tests/contracts/`.
3. Breaking changes bump the MAJOR schema version and must be recorded in `docs/decisions/`.
