# ADR-0006: Transport and storage are undecided

**Status:** PROPOSED

## Context

Several options exist for the transport (MQTT, WebSocket, ROS 2 bridge, others) and for FMS storage. The requirements that would decide between them (link quality, number of boats, latency, retention, hosting) are not yet confirmed.

## Decision

- Do not commit to a transport or database in code.
- Define the `FmsLink` port and the in-memory FMS store as placeholders.
- Record the evaluation criteria in `OPEN_DECISIONS.md` entries 1 to 3.

## Consequences

- The foundation runs without infrastructure.
- A decision is required before field trials. This ADR should become ACCEPTED or be replaced by specific ADRs when the requirements are known.
