# Data flow

This document traces how data moves through the system. It complements `SYSTEM_ARCHITECTURE.md`.

## 1. Telemetry (boat -> FMS)

1. `telemetry` reads the vehicle state and operating mode, builds a `BoatStatePayload`, and publishes it as an `Outbound` on `fms.outbound`.
2. Every tenth tick, `telemetry` also publishes a `ServiceHealthPayload` built from the service manager.
3. `fms-bridge` wraps each `Outbound` in an `Envelope`, assigns the next sequence number, and appends it to its outbox (bounded, drop-oldest).
4. On each tick, the bridge sends queued envelopes in order. If the link is down, it keeps them and retries.
5. The FMS endpoint validates the envelope, drops duplicates, stores the message by boat and type, and returns an acknowledgement if the spec is critical.

## 2. Commands (FMS -> boat)

1. The FMS `MissionService` creates an envelope, assigns a sequence number, and queues it in the FMS outbox until acknowledged.
2. The transport delivers it to the boat. The bridge receives it and publishes it on `fms.inbound`.
3. `command-router` validates the message and acts:
   - mission assignment: `search-mission` rejects assignments while motion is inhibited; otherwise records the mission and its candidate regions;
   - cancellation: clears the matching mission before immediately attempting zero; successful ordinary cancellation does not latch inhibition;
   - supported safe-state command: sets SAFE_STATE and latches motion inhibition before fallible cancellation/stop I/O; mission cancellation still requires a matching supplied ID;
   - unsupported command: rejected, with the reason.
4. The router publishes an acknowledgement (accepted or rejected, with reason) and, for missions, a progress message.
5. The FMS receives the acknowledgement and clears the queued command.

Failed zero application produces a rejected acknowledgement with a reason; cancellation can have completed locally even when stop delivery failed. Motion inhibition remains latched despite goal regeneration, callback recovery or new assignments. Motion source/controller/clock/sink faults also latch inhibition and persistent degraded service health. Each stop event/inhibited motion tick makes at most one zero attempt; a rejected nonzero application can additionally trigger one emergency zero. If the clock fails, the last validated timestamp may stamp that zero with an explicit not-fresh fault detail. Without a valid timestamp, no command is fabricated. See accepted ADR-0007 H1-H3; no software result proves physical stopping.

## 3. Sensing to obstacle summary

1. A sensor adapter returns `SensorSample` objects on each poll.
2. `sensor-ingest` publishes each sample on `sensor.sample`.
3. `perception` runs the detector on collision-relevant samples (camera frames and range data) and publishes a `PerceptionFrame`.
4. If there are detections, `perception` also sends an `ObstacleSummaryPayload` to the FMS, with `collision_risk` unset.

## 4. Search progress

1. On each tick, `search-mission` takes the current position and records a VISITED observation in environment knowledge and in mission memory.
2. The exploration policy reads knowledge and chooses the next target: never-visited regions first, then the nearest, never the current region.
3. The target becomes a `NavigationGoal` for `motion`. The goal is replaced after the boat enters its acceptance radius.
4. `telemetry` sends an `EnvironmentProgressPayload` built from the mission's coverage.

## Timestamps and time zones

All timestamps are timezone-aware UTC. Naive datetimes are rejected at the contract boundary and in domain types.
