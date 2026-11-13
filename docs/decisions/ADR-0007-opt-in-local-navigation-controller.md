# ADR-0007: Opt-in local navigation reference controller

**Status:** PROPOSED

**Accepted subset:** Motion hardening H1-H3 below was explicitly approved by the human owner on 2026-11-13. Waypoint navigation and the remaining proposals retain PROPOSED status.

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

## Motion-hardening decisions and approval

**Approval status:** H1, H2 and H3 ACCEPTED by explicit human responses: "Approve H1 as proposed", "Approve H2 as proposed", and "Approve H3 as proposed". Refreshing `origin/main` to `3e07d1b` confirmed the CI baseline; the assessment was carried from local commit `d6c5860`. These approvals accept only the stop/fault policies below, not the waypoint-controller proposal.

Established behaviour to preserve: zero default, constructor injection and boundaries; supported hold/stop commands clear the current goal and attempt immediate zero; matching cancellation clears the mission; unsupported return-home is rejected. The reviewed foundation had no persistent inhibition state. H1-H3 now define its software scope and lifetime.

Accepted human decisions for OPEN_DECISIONS #24-25:

| ID | Accepted first-PR policy | Alternatives not selected |
|---|---|---|
| H1: inhibition and resumption | Latch motion inhibition before supported safe-stop or motion clock/source/controller/sink fault handling. Goals and ticks never release it; controller/position callbacks cannot bypass it. No rearming API or automatic/remote rearming in this PR: a new runtime instance is required for a fresh mission. Reject assignments while inhibited. Set SAFE_STATE before fallible supported safe-stop delivery; other motion faults remain visible in persistent service health without inventing new operating-mode transitions. Existing matching-only cancellation scope is preserved. | Gate by operating mode and define who may change it to re-enable motion; or keep the implementation pending. A mission-only safety callback does not enforce inhibition at the command sink. |
| H2: ordinary goal clearing and cancellation | Clearing a goal or cancelling a matching mission immediately attempts zero without latching on success. Complete mission cleanup even when stop delivery fails; such failure latches inhibition and is reported. Accepted cancellation/safe-state ACK requires its specified effects, including successful zero application to the sink; otherwise return a rejected ACK with a reason that distinguishes local cleanup from delivery failure. | Preserve deferred zero on ordinary goal clearing until the next motion tick; or defer cancellation/ACK changes to a separately reviewed PR. |
| H3: clock failure and stop attempts | Validate an aware datetime before any nonzero command. Use current valid time for zero; if the clock later fails, use the last validated time solely to timestamp an emergency zero, explicitly reporting that it is not fresh. With no validated time, inhibit/report without inventing a timestamp or emitting nonzero. Attempt zero once per triggering event and at most once on each subsequent explicit inhibited tick when a valid timestamp is available; no internal retry loop. Failed sink application remains a fault, never proof of delivery. Clock/sink recovery does not release inhibition. | Require a separately injected emergency clock with a reviewed failure policy; or exclude clock-fallback implementation from the first PR and state that limitation. |

H2's failure latch and H3's persistent inhibition depend on H1; H1's emergency stop after clock failure depends on H3. All three approvals were received, so this subset is dependency-complete. SAFE_STATE and inhibition must be established before cancellation/goal clearing because H2 makes those calls perform fallible stop I/O. No waypoint, heading/frame, physical propulsion, stale-state threshold, collision-avoidance, device watchdog or production-safety policy was approved. Faults that prevent timestamp creation or sink delivery remain limits on what software can establish.

Regressions cover absent/matching/mismatching stop mission IDs, forced and mission-regenerated goals over repeated ticks, assignments during inhibition, cancellation timing/cleanup/ACK cases, invalid initial/later clock values, source/controller/sink exceptions, bounded stop attempts and persistent fault reporting. Baseline zero-default and immediate-stop tests remain distinct from these new inhibition checks. A zero delivery failure during cancellation is acknowledged as rejected while reporting completed local mission cleanup; no ACK asserts physical stopping.
