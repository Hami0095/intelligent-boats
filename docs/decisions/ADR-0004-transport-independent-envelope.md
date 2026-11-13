# ADR-0004: Transport-independent typed envelope

**Status:** ACCEPTED

## Context

The transport between boat and FMS is undecided. Choosing one early would spread its concepts through the code.

## Decision

- All boat <-> FMS messages are typed pydantic models wrapped in one envelope, serialised as JSON.
- `marine_contracts` contains no transport code.
- The `FmsLink` port hides the transport from the AI Box and the FMS.

## Consequences

- The transport can be chosen later with changes limited to adapters.
- Schema validation happens at the boundary, independent of the wire technology.
- JSON is verbose compared with binary formats. This is acceptable for the foundation; a binary encoding would be a new ADR.
