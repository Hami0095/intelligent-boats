# Data flow

This document traces how data moves through the system. It complements `SYSTEM_ARCHITECTURE.md`.

## 1. Telemetry (boat -> FMS)

1. `telemetry` reads the vehicle state and operating mode, builds a `BoatStatePayload`, and publishes it as an `Outbound` on `fms.outbound`.
2. Every tenth tick, `telemetry` also publishes a `ServiceHealthPayload` built from the service manager.
3. `fms-bridge` wraps each `Outbound` in an `Envelope`, assigns the next sequence number, and appends it to its outbox (bounded, drop-oldest).
4. On each tick, the bridge sends queued envelopes in order. `ConnectionError` leaves the message queued for a later tick; other send errors are logged and dropped. A full buffer drops the oldest message.
5. The FMS endpoint requires a registered boat ID, checks message direction, de-duplicates boat-originated non-ACK messages, stores valid messages by boat and type, and returns an acknowledgement if the spec is critical. Out-of-order messages are stored and audited.

The bridge removes an outbound envelope when `send()` returns; it does not retain critical boat messages until their FMS acknowledgement arrives. FMS storage and audit are in-memory. The loopback link is in-process; no network transport is implemented.

## 2. Commands (FMS -> boat)

1. The FMS `MissionService` creates an envelope, assigns a per-boat sequence number, and queues it in the FMS outbox until acknowledged.
2. The caller obtains unacknowledged commands from that queue and delivers them to the intended boat. The current loopback tests do this manually; there is no FMS command dispatcher or reconnect scheduler. The AI Box bridge drops inbound envelopes with a different configured boat ID or a boat-to-FMS-only message type, and otherwise publishes them on `fms.inbound`.
3. `command-router` validates the message and acts:
   - mission assignment: `search-mission` rejects assignments while motion is inhibited; otherwise records the mission and its candidate regions;
   - cancellation: clears the matching mission before immediately attempting zero; successful ordinary cancellation does not latch inhibition;
   - supported safe-state command: sets SAFE_STATE and latches motion inhibition before fallible cancellation/stop I/O; mission cancellation still requires a matching supplied ID;
   - unsupported command: rejected, with the reason.
4. The router publishes an acknowledgement (accepted or rejected, with reason) and, for missions, a progress message.
5. The FMS matches the acknowledgement's message ID and boat ID and clears the queued command for either accepted or rejected acknowledgements.

Failed zero application produces a rejected acknowledgement with a reason; cancellation can have completed locally even when stop delivery failed. Motion inhibition remains latched despite goal regeneration, callback recovery or new assignments. Motion source/controller/clock/sink faults also latch inhibition and persistent degraded service health. Each stop event/inhibited motion tick makes at most one zero attempt; a rejected nonzero application can additionally trigger one emergency zero. If the clock fails, the last validated timestamp may stamp that zero with an explicit not-fresh fault detail. Without a valid timestamp, no command is fabricated. See accepted ADR-0007 H1-H3; no software result proves physical stopping.

## 3. Sensing to obstacle summary

1. A sensor adapter returns `SensorSample` objects on each poll.
2. `sensor-ingest` publishes each sample on `sensor.sample`.
3. `perception` runs the detector on collision-relevant samples (camera frames and range data) and publishes a `PerceptionFrame`.
4. If there are detections, `perception` also sends an `ObstacleSummaryPayload` to the FMS, with `collision_risk` unset.

Separately, `environment-observation-ingest` accepts only `SensorKind.OTHER` samples with a `data["environment_observation"]` mapping containing a local `point` (`x_m`, `y_m`) and `confidence`, plus optional `mission_id` and `provenance_detail`. It validates the fields, uses the sample timestamp and sensor ID as provenance, and publishes a typed `EnvironmentObservation` on `environment.observation`. `environment-knowledge` records that event. This mock-only payload is already normalized: it creates `OBSERVED` only, and does not infer a local point or meaning from camera/range data. Invalid payloads are rejected and degrade ingress health; unrelated samples are ignored. Production sensor evidence and localization remain open in decision 33; `SEARCHED` remains governed by decision 7. See [ADR-0008](decisions/ADR-0008-typed-environment-observation-ingress.md).

## 4. Search progress

1. On each active-mission tick, `search-mission` takes the current local position and records a VISITED observation in environment knowledge and mission memory. An observation-only region is reported as OBSERVED and remains unsearched; the baseline policy treats it like UNKNOWN when preferring never-visited regions. Visiting a cell never marks it searched. The mock ingress can create OBSERVED records only from its explicit normalized payload; production sensor evidence remains open (decision 33), as does search coverage for SEARCHED (decision 7).
2. The exploration policy reads knowledge and chooses the next target: never-visited regions first, then the nearest, never the current region.
3. The target becomes a `NavigationGoal` for `motion`. The goal is replaced after the boat enters its acceptance radius.
4. While a mission is active, `telemetry` obtains the environment summary together with that mission ID and publishes it as an `EnvironmentProgressPayload` in an envelope carrying the same ID. The FMS stores the received envelope and payload by boat and message type; the summary contains counts and coverage, not per-region identifiers. It reports no verified searched coverage until a SEARCHED observation is explicitly recorded, and it does not signal mission completion.

Health reports use the service manager's lifecycle and service-level health details. The bridge reports a link unavailable only after a `ConnectionError` is observed; an outbound message waiting for the next bridge tick does not by itself make health degraded. Sensor measurements not available from the injected sources remain `None` in boat-state telemetry.

## 5. Explicit-step mock vessel

`adapters.simulation.mock_vessel.MockVessel` can be injected as both `PositionSource` and `PropulsionSink` in tests. It consumes each supplied normalized command on one explicit `step(duration_s)` call and returns its updated local state through `current_state()`. A test or caller must place that step between `app.tick()` calls; no scheduler or default bootstrap wiring is added. The existing `HoldPositionController` remains the default and emits zero, so the mock adapter does not create autonomous movement. Its synthetic equations and limitations are documented in [adapters/README.md](../adapters/README.md); they do not establish controller behavior, physical dynamics or vessel safety.

## Timestamps and time zones

Current producers use timezone-aware UTC timestamps. Naive datetimes are rejected, but envelope validation currently accepts other timezone-aware offsets without normalization.
