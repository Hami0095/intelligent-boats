# Contract versioning

- `schema_version` is a semantic version carried on every envelope.
- **MAJOR**: an incompatible change, such as a removed or renamed field or a changed meaning. Requires an ADR and a coordinated upgrade of boat and FMS.
- **MINOR**: an additive change. Today the models use `extra="forbid"`, so a receiver rejects unknown fields. Until decision 13 in `docs/OPEN_DECISIONS.md` is settled, a MINOR change must still be deployed to receivers first.
- **PATCH**: documentation or validation-only fixes.
- The supported major version is defined in `marine_contracts/envelope.py` (`SUPPORTED_MAJOR_VERSION`).
