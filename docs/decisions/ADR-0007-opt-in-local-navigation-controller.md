# ADR-0007: Opt-in local navigation reference controller

**Status:** PROPOSED

## Context

Motion already accepts an injected controller, optional local goal/state and explicit time. The default emits zero. Frame/heading conventions, physical propulsion mapping, freshness, speed control and persistent stop/resumption remain unresolved. The current one-shot stop and exception handling are insufficient foundations for nonzero output in the assembled runtime.

See [navigation readiness assessment](../NAVIGATION_CONTROLLER_READINESS.md) and OPEN_DECISIONS #4, #5, #11, #12, #14, #18 and #23-26. This record proposes choices for review; it accepts no hardware or mission requirements.

## Decision (proposed)

- Preserve the zero-command default and existing constructor injection, ports and message contracts.
- Before assembled-runtime nonzero use, implement and test persistent stop/fault inhibition, immediate zero on ordinary goal clearing/cancellation, and explicit fault reporting. New goals cannot release inhibition. The first hardening PR provides no automatic/remote rearming; inhibited mission assignments are rejected. Operational recovery remains OPEN.
- Use one validated stop/fault path for cancellation, shutdown and safe state. A delivery failure must inhibit motion before further fallible work, allow internal mission cleanup to complete, and be reported without a successful cancellation acknowledgement implying that zero was delivered.
- Review emergency timestamp handling before implementation: a possible mock fallback uses the last validated time solely for an emergency zero, without calling it current time. No valid initial time means no permission for nonzero output. Failed sink delivery cannot be represented as a successful stop.
- Subsequently add a stateless local waypoint reference controller with explicit heading-to-local conversion, rudder sign, bounded normalised parameters and state-age limit. Validate inputs/derived geometry and return zero for missing or invalid required state and arrival at/below the supplied radius.
- Use wrapped bearing error and bounded proportional rudder with explicit forward normalised thrust. This establishes a reference command mapping, not physical convergence or speed regulation.
- Return zero for any supplied speed cap until its enforcement is supported; do not infer a speed/thrust relationship.
- Use only explicit synthetic frame/sign/time conventions in mocks. Keep global localisation and hardware conventions OPEN. No simulator, collision avoidance, real propulsion activation or runtime dependency is introduced.

## Consequences

- No package-boundary or responsibility redesign is needed; implementation uses the existing extension point.
- Stop/fault regressions precede controller integration. Review by motion, integration and architecture owners is needed before these proposals become accepted behaviour.
- Deterministic mock tests can establish command direction, bounds, inhibition and arrival handling. They cannot establish real motion, station keeping, obstacle safety, braking distance or deployment suitability.
- Heading freshness, clock fallback acceptance, uncertainty requirements, rearming, physical calibration and device watchdog semantics remain unresolved and explicitly recorded.
