# ADR-0008: Typed environment-observation ingress

**Status:** PROPOSED

## Context

`SensorSource` produces `SensorSample` values whose `data` mapping is defined by each adapter. `sensor-ingest` publishes those samples to the event bus, and `perception` consumes collision-relevant samples to produce obstacle detections and summaries.

That data is not currently sufficient to create an `EnvironmentObservation` safely. The environment model requires a local point, timestamp, provenance and confidence. Perception detections provide relative bearing and optional range, but their category is not semantic object recognition and there is no approved transform from a detection to an environment point. The mission service records `VISITED` from the position source; this does not establish that something of interest was observed. The separate search-coverage model for `SEARCHED` remains open in decision 7.

## Decision

This proposal recommends an explicit, typed in-process ingress for `EnvironmentObservation`, separate from collision perception. A producer may publish an observation only when it can supply the existing model's required evidence, including a valid local point and provenance. Generic sensor samples and obstacle detections must not be implicitly converted to `OBSERVED` or `SEARCHED`.

The ingress mechanism and the evidence criteria for an `OBSERVED` record require agreement before implementation. `SEARCHED` remains gated by the separate search-coverage decision; receiving an `OBSERVED` record must not change search status.

Alternatives considered:

- Define implicit mappings from adapter-specific `SensorSample.data` fields. This leaves core behavior dependent on undocumented payload shapes and does not resolve evidence or localization requirements.
- Convert collision detections into environment observations. This would conflate collision perception with environment knowledge and lacks approved semantic and local-position evidence.

## Consequences

- No sensor-to-environment observation path is implemented until the ingress and evidence criteria are accepted.
- Existing position-based `VISITED` tracking and exploration behavior continue unchanged.
- The FMS continues to receive supported aggregate progress reports, not individual region observations.
- If accepted, implementation must add deterministic tests for valid and invalid observations while preserving the distinction between `VISITED`, `OBSERVED` and `SEARCHED`.
