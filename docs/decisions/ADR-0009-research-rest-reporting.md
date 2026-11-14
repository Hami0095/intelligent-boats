# ADR-0009: Research-only REST reporting through existing ports

**Status:** ACCEPTED for the software-only research milestone explicitly requested by the owner. Production transport and hosting remain OPEN.

## Context

The existing Lovable-connected React dashboard simulates its own fleet. Python AI Boxes already report typed envelopes, and Python FMS validates/stores them in memory, but these paths were not connected. The owner requested a separate `research` environment while preserving the deployed main simulation, existing contracts and package boundaries.

## Decision

- Add an opt-in standard-library HTTP implementation of `FmsLink` in `adapters`. Send established JSON envelopes once per adapter call and queue only the response's actual FMS reply envelopes for `receive()`. HTTP success is not a mission acknowledgement. Existing bridge buffering behaviour is unchanged; no new retry system is introduced.
- Add a loopback-only, single-thread HTTP server in `adapters` behind an injected application protocol. It imports no FMS implementation. A script composition root wires the existing FMS registry/endpoint/store to that server through a pure read/ingest facade in FMS.
- Reuse existing envelope decoding, registered boat identities, direction checks, in-memory storage and reply behaviour. Read endpoints return actual latest received envelopes and receipt timestamps; absent reports/fields remain absent or null. No shared message schema changes.
- Add explicit research REST data-source selection to the existing dashboard. Normal builds remain simulation by default. Research mode never constructs mock browser vessels or substitutes random telemetry when data is absent. Existing components display received values with unavailable/read-only states where backend capabilities differ.
- Demonstrate two independent AI Boxes using existing `MockPositionSource`, `MockPropulsionSink`, reporting services and the zero default controller. Geographic and local positions are independently scripted fixtures; there is no local-to-GPS transform or claim that propulsion commands cause their changes. `MockVessel` remains available for local-only tests but supplies no geographic position. Unmerged waypoint work is excluded.
- Bind ingestion to IPv4 loopback only, require JSON, and bound request bodies. The research Vite proxy forwards dashboard GET routes only; it never proxies message ingestion. No remote endpoint, production setting or deployment is changed. A remotely reachable write service requires a separately reviewed access restriction and hosting setup.

## Consequences

- No HTTP framework or new runtime dependency is needed. Accepted import boundaries remain unchanged, and architecture tests remain intact.
- `main` retains its browser-generated simulation. Research can be built independently using the same components and explicit build configuration; no duplicate frontend or invented remote URL is required.
- The first integration is reporting-only. Dashboard mission/delivery/return-home controls are unavailable in research. The producer seeds a one-time scripted assignment through the existing router to exercise supported reporting; this is not a network command dispatcher.
- Synthetic geographic fixtures, no-data handling and end-to-end values are testable over real loopback HTTP and a live React DOM integration test. Interactive browser availability and remote hosting are separate verification/deployment concerns.
- Production transport, authentication, persistence, geographic transforms, delivery guarantees, command dispatch and autonomous navigation remain OPEN. The single-thread development server is not a production hosting decision.

Alternatives considered: introducing an HTTP framework would require dependency approval; putting HTTP inside AI Box/FMS core or importing FMS from adapters would violate existing boundaries; replacing the main simulator would violate the requested environment separation.
