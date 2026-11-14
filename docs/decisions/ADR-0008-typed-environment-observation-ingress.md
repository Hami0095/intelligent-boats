# ADR-0008: Typed environment-observation ingress

**Status:** ACCEPTED

## Context

`SensorSource` produces `SensorSample` values whose `data` mapping is defined by each adapter. `sensor-ingest` publishes those samples to the event bus, and `perception` consumes collision-relevant samples to produce obstacle detections and summaries.

Generic sensor samples and perception detections do not establish environment-observation semantics. Perception detections provide relative bearing and optional range, but their category is not semantic object recognition and there is no approved transform from a detection to an environment point. The mission service records `VISITED` from the position source; this does not establish that something of interest was observed. The separate search-coverage model for `SEARCHED` remains open in decision 7.

## Decision

Add a typed in-process event-bus topic, `environment.observation`, carrying `EnvironmentObservation`. A normalizer accepts only `SensorKind.OTHER` samples with a `data["environment_observation"]` mapping containing:

- `point`, containing exactly `x_m` and `y_m` as finite numbers already in the AI Box local frame;
- `confidence`, a finite number in `[0, 1]`;
- optional `mission_id` and `provenance_detail` strings.

The normalizer uses the sample timestamp and sensor ID for the observation timestamp and provenance, and emits `ObservationKind.OBSERVED` only. Malformed samples are rejected, do not update knowledge, and degrade the ingress service's health. Samples without this mapping are ignored.

This is a mock-only, pre-normalized input contract. It does not claim that a real sensor or the collision detector can identify an object of interest or derive a local point. `VISITED` remains position-source data; `SEARCHED` remains gated by decision 7. Generic samples and collision detections must never be implicitly converted to either kind.

Alternatives considered:

- Convert collision detections into environment observations. This would conflate collision perception with environment knowledge and lacks approved semantic and local-position evidence.
- Infer a local point from raw camera or range samples. Localization, calibration and sensor fusion are unresolved; this proposal makes none of those assumptions.

## Consequences

- Mock `SensorKind.OTHER` samples can update environment knowledge through the typed event bus.
- Existing position-based `VISITED` tracking and exploration behavior continue unchanged; `OBSERVED` does not count as visited or searched.
- The FMS continues to receive supported aggregate progress reports, not individual region observations.
- Production sensor semantics, local-point derivation and evidence criteria remain open under decision 33.
