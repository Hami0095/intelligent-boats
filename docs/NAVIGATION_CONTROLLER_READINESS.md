# AI Box navigation controller: design and readiness assessment

**Status:** PROPOSED; design only, no controller or runtime changes.
**Reviewed baseline:** `4c24162` (refreshed `origin/main`).

Recommendation: close the motion stop/fault-handling gaps before using nonzero output in the assembled runtime. Then add a stateless, explicitly injected local waypoint reference controller. Its initial claim is bounded command generation from declared mock inputs, not physical navigation performance or deployment safety. The zero-command controller remains the default.

## 1. Existing capabilities and limitations

| Component | Implemented | Limitation relevant to navigation |
|---|---|---|
| Composition | `build_boat(..., controller=...)` injects a `MotionController`; omission selects `HoldPositionController` | The default returns zero thrust/rudder; its name does not imply active station keeping |
| Motion | Reads vehicle state, computes a command, applies it through `PropulsionSink`; `safe_stop()` immediately attempts zero | No persistent inhibition, input-freshness policy, or motion-specific fault-stop handling |
| Mission | Accepts known local search areas, records visits, chooses/replaces local goals | No heading requirement or shared state snapshot; missing position leaves an existing goal intact |
| Exploration | Prefers never-visited unsearched regions, then nearest, excluding the current region | A reference target-selection policy, not route planning, collision avoidance, or completion logic |
| Models | Local positions in metres, optional heading/speed, goal radius, normalised commands | Frame/heading/rudder conventions are unresolved; some numeric validation is incomplete |
| Runtime | Dependency-ordered startup, cooperative ticks, reverse shutdown, health reporting | Caller supplies scheduling; tick exceptions are logged and isolated, without automatic zero output |
| Mocks | A position source holds assigned states; a propulsion sink records commands | Neither mock models movement, steering, inertia, braking, or command expiry |

Source entry points: [bootstrap](../ai-box/src/ai_box/bootstrap.py), [controller](../ai-box/src/ai_box/motion/controller.py), [motion service](../ai-box/src/ai_box/motion/service.py), [mission](../ai-box/src/ai_box/decision/mission.py), [policy](../ai-box/src/ai_box/decision/policy.py), [manager](../ai-box/src/ai_box/core/manager.py).

Existing motion tests cover command bounds, a positive radius, the zero controller and goal clearing on `safe_stop`. Mission and integration tests cover goal selection/replacement using manually supplied positions. They do not establish closed-loop navigation with nonzero output. The demo also assigns positions manually; it does not derive them from commands.

## 2. Exact goal-to-command flow and timing

```text
FMS assignment envelope -> FmsLink.receive()
  -> FmsBridgeService -> synchronous fms.inbound event
  -> CommandRouter -> SearchMissionService.assign(mission_id, search_area_id)
  -> locally supplied SearchArea -> candidate region IDs

PositionSource.current_state() -> SearchMissionService.tick()
  -> VISITED observation + mission memory
  -> ExplorationPolicy.next_intent(...) -> NavigationIntent(target=region centre)
  -> NavigationGoal -> MotionService.set_goal(goal)

MotionService.tick(): clock() + PositionSource.current_state() + stored goal
  -> MotionController.compute(goal, state, now)
  -> PropulsionCommand(timestamp, thrust, rudder)
  -> PropulsionSink.apply(command)
```

Goal transfer is a direct method call. The controller does not read FMS envelopes or select mission targets. Geographic FMS navigation goals remain rejected; this proposal uses local goals only.

The current assembled tick order is `sensor-ingest -> perception -> motion -> search-mission -> telemetry -> fms-bridge -> command-router`. Dependencies determine startup order; the manager ticks that same ordered list. The router handles commands synchronously during the bridge's receive phase; its own tick does nothing.

For an assignment received in bridge tick N: assignment occurs at N, search creates the first goal at N+1, and motion first consumes it at N+2. An already active mission's new goal likewise takes effect on the next motion tick. Mission acknowledgements produced during receive normally leave on the next bridge send phase. No fixed elapsed duration follows from these tick counts.

Motion must check arrival itself: it executes before mission code clears/replaces a reached goal. Mission, motion and telemetry independently read position; no per-tick coherent snapshot is guaranteed.

### Stop/fault findings that the zero controller masks

1. A supported safe-state command cancels a mission only if its optional mission ID matches. With no ID or a different ID, the mission stays active. `safe_stop()` clears the goal and emits zero once; search can then generate another goal while operating mode remains `SAFE_STATE`. Motion never checks that mode. An executed mock diagnostic reproduced nonzero resumption at N+2 after a stop received at N for both unmatched cases; the matching-ID control remained zero. See the assessment validation results below.
2. Cancellation clears the goal without immediately applying zero. A command sent earlier in that tick remains the latest sink command until the next successful motion tick. The adapter contract does not specify how long that command remains effective.
3. Exceptions in the clock, position source, controller or sink can leave the previous command unaddressed. Manager health degradation alone does not revoke a command. Sink failure also means a stop attempt cannot establish delivery.
4. Shutdown attempts zero through `MotionService.stop()`, but has no independent guarantee if its clock or sink fails. The mission's `safety_clear` callback defaults to true in composition and is not a collision-avoidance connection.

See [command routing](../ai-box/src/ai_box/services/command_router.py), [operating state](../ai-box/src/ai_box/core/state.py), and the motion/mission/manager sources above.

## 3. Minimum controller inputs, outputs and proposed algorithm

Keep the existing protocol unchanged:

```text
compute(goal: NavigationGoal | None,
        state: VehicleState | None,
        now: datetime) -> PropulsionCommand
```

Nonzero reference output requires finite current local coordinates, a finite local target in the same frame, finite heading with a declared relationship to that frame, a finite positive radius, an aware state timestamp, usable aware `now`, and explicit validated controller settings. Output remains a timestamped command with thrust/rudder in `[-1, 1]`.

Proposed class: `LocalWaypointController`, configured through its constructor with a pure heading-to-local-angle conversion, signed rudder convention, forward normalised thrust, proportional steering gain, rudder cap and maximum state age. Require explicit settings; do not choose hardware-derived defaults. In tests only, the conversion can declare heading zero along local +x and increasing counterclockwise. This is a synthetic fixture convention, not a new global interpretation of `VehicleState.heading_deg` or a real-boat coordinate choice.

After validating inputs and derived geometry:

```text
dx, dy = target - current_position
distance = hypot(dx, dy)
if distance <= acceptance_radius: zero thrust and rudder
otherwise:
    bearing = atan2(dy, dx)
    error = wrap(bearing - converted_heading) into [-pi, pi)
    rudder = clamp(rudder_sign * steering_gain * error, -rudder_cap, rudder_cap)
    thrust = explicitly configured positive normalised reference thrust
```

The exact opposite-bearing tie is -pi under this proposed interval and must be tested. Validate the result of heading conversion and intermediate subtraction/distance as well as original inputs: finite coordinates can still overflow during subtraction.

No integral/derivative terms, speed regulator, reverse manoeuvre, turn-in-place rule, route planner or dynamics model is proposed. Constant normalised thrust has no established speed meaning and does not guarantee decreasing distance, convergence, braking or successful turns. A zero-thrust alignment gate would not establish turning ability either.

## 4. Missing information and readiness boundaries

| Missing information | Consequence and proposed treatment |
|---|---|
| Local axes, heading zero/rotation and signed rudder meaning | Required declaration for meaningful command direction. Use explicit mock conversion/sign only; keep real-frame decisions OPEN (#4, #11) |
| Frame identity | Models carry no frame IDs. Caller/fixture must ensure common frame; controller cannot detect a frame mismatch |
| Localisation capability and coherent heading/position age | One aggregate timestamp cannot establish independent heading freshness. No fusion or heading inference is proposed (#5) |
| State-age limit, future-time tolerance, uncertainty policy | Use explicit fixture age limit and reject future timestamps for initial tests; production limits and quality requirements remain OPEN |
| Physical propulsion/dynamics, cadence and command expiry | Cannot derive speed from thrust, select physical gains or promise convergence/stop distance. Scheduler and device watchdog remain OPEN (#11, #14, #18) |
| Speed-cap semantics | First reference controller should output zero for any supplied `max_speed_mps`; a physical speed limit cannot be honoured by an uncalibrated thrust command |
| Persistent motion permission and resumption authority | Must be reviewed before nonzero assembled-runtime use; ordinary goal generation must never release a stop |
| Arrival semantics | Propose zero at distance <= radius, using goal-supplied radius. Existing 5 m default is not a newly confirmed navigation requirement |

Geographic position, measured speed and uncertainty are not required to evaluate the limited mock command mapping. Missing values remain unknown. Known invalid optional numeric values should inhibit output; whether unknown uncertainty prohibits real movement is still OPEN. Heading must not be inferred from successive positions or speed-over-ground.

## 5. Testing with existing mocks

Use `MockPositionSource.set_state(...)`, `MockPropulsionSink.commands`, fixed aware timestamps and `MotionService(..., clock=...)`. Supply a goal, tick motion, and inspect the recorded command. Change the state and verify recomputation rather than reuse of an earlier command. No hardware, simulator or new dependency is needed.

Use a scripted sequence of states outside, approaching, at and inside the radius to test feedback mapping and arrival. Explicitly state that the test supplied this trajectory: commands did not cause the motion. Do not add a toy boat dynamics model or claim this demonstrates autonomous travel.

Controller tests belong in `ai-box/tests/unit/`; stop/mission/FMS interactions belong in `tests/integration/`. Reuse the existing mocks without modifying their responsibilities. A deliberately nonzero test double should expose motion-inhibition failures independently of any navigation algorithm.

## 6. Missing and invalid information policy (PROPOSED)

| Condition | Proposed behaviour |
|---|---|
| No goal, state, local position or heading | Zero command using valid `now`; do not retain previous nonzero output |
| Geographic position present but local position absent | Zero; do not invent a geographic-to-local transform |
| Nonfinite coordinates, heading, radius, converted angle or computed geometry; radius <= 0 | Zero when a valid command timestamp is available |
| Heading outside [0, 360) | Already rejected by `VehicleState` construction; controller/service boundary must also inhibit malformed input |
| Stale state: age > explicit maximum; future timestamp: age < 0 | Zero; age equal to the configured maximum remains valid in the proposed fixture policy |
| At target, inside radius or exactly on radius | Zero thrust and rudder |
| Any `max_speed_mps` supplied | Zero and document unsupported speed control; never silently ignore a speed cap |
| Optional speed/uncertainty is absent | Leave unknown; not required for mock mapping |
| Optional speed/uncertainty is supplied but negative or nonfinite | Zero; do not use invalid optional information as valid state |
| Invalid controller settings | Reject construction with `ValueError`, before output |
| Source/conversion/controller exception | Inhibit motion and attempt zero through a functioning sink; preserve fault reporting |
| Sink exception | Inhibit, report failure and make a bounded stop attempt; never claim that zero reached a failed sink |
| Unusable/naive/raising clock | No valid `stop(now)` can be formed from that value. Inhibit and report; an emergency timestamp policy is a prerequisite, not something the controller can solve |

Current validation gaps: `LocalPoint` has no finiteness validation; local `NavigationGoal` accepts NaN/positive-infinite radius and does not validate `max_speed_mps`. Dataclass annotations do not enforce runtime types. Guard the controller boundary; avoid broad unrelated model changes. The shared `require_utc` helper checks timezone awareness, not zero UTC offset. Compare aware instants correctly without silently changing shared contracts.

For the first hardening PR, a proposal to review is retaining the last validated clock value solely to timestamp an emergency zero after a later clock failure, with a persistent fault. It must not be represented as fresh time. Before any valid clock value exists, no nonzero command may be allowed. Hardware timestamp acceptance, expiry and an independent watchdog remain unresolved; this fallback provides no physical guarantee.

## 7. Preserve default behaviour and boundaries

Leave `HoldPositionController`, the bootstrap fallback and existing demo selection unchanged. An alternative is selected only by passing a constructed instance through the existing `controller=` parameter. No environment switch, automatic selection, physical adapter, new runtime dependency, or shared message/port change is needed.

The new controller belongs in `ai_box.motion`, imports only permitted packages and standard-library math, and receives data rather than reading ports itself. Motion alone applies commands. Unit/integration fixtures inject mocks. Perception, environment, FMS, adapters and simulator dependencies remain separated. Collision avoidance is outside this proposal.

## 8. ADR assessment

Using the existing controller protocol does not require an architectural redesign. However, controller conventions, speed-limit refusal, explicit selection and persistent stop/fault semantics are significant choices under root `CLAUDE.md`. Record them in [ADR-0007](decisions/ADR-0007-opt-in-local-navigation-controller.md), status PROPOSED. Owner review is required before treating them as accepted. No architecture boundary is changed by this assessment, and implementation stops at design as requested.

## 9. Assumptions and unresolved questions

New OPEN_DECISIONS entries #23-26 record proposed controller semantics, persistent stop/resumption, state validity/time policy, and unsupported speed caps/arrival. Existing items #4, #5, #11, #12, #14 and #18 remain unresolved.

The only working assumptions are for explicit mock fixtures: one consistent local frame, declared heading conversion and rudder sign, coherent state samples and test-supplied parameter values. No gain, thrust level, age threshold, radius, sensor capability or dynamics value is promoted to a production requirement.

## 10. Proposed implementation tasks, acceptance criteria and test plan

### First implementation PR: prevent command resumption after a stop

Suggested branch: `fix/ai-box-preserve-motion-stop`.
Suggested title: `ai-box: inhibit motion after stop and controller faults`.

After review of the proposed stop/time policy, harden motion and its existing command integration. Preserve the zero controller and all port/message signatures. Proposed minimal behaviour: `safe_stop()` latches inhibition before attempting zero; assigning a goal cannot release it; `set_goal(None)` immediately attempts zero without independently rearming or latching; source/controller/clock/sink faults inhibit output and remain visible in health. Define the emergency timestamp fallback before implementation. For this first PR, do not add automatic or remote rearming; reject mission assignments while a stop/fault inhibits motion. Recovery/resumption policy remains OPEN rather than adding a new FMS command.

Goal clearing, cancellation, shutdown and safe-state handling must share the validated stop/fault path. Establish inhibition on a fault before any further fallible clock/sink work. Complete mission cancellation cleanup even if zero cannot be delivered; the new immediate-stop path must not leave the mission active because `set_goal(None)` raised. Report the delivery failure explicitly and do not emit an unconditional successful cancellation acknowledgement that implies stopping succeeded.

Acceptance criteria, exercised with a nonzero test double and mock sink:

1. Safe state with absent, matching or mismatching mission ID emits zero and cannot be followed by nonzero output, including after new goals, rejected assignments and multiple ticks.
2. Matching cancellation replaces the prior nonzero command with zero during handling, without waiting for another tick. Ordinary successful cancellation need not latch the safety inhibit. Failed delivery still clears the mission, latches a fault and reports failure rather than an unconditional accepted acknowledgement.
3. Source/controller failures and invalid/raising clocks after nonzero output inhibit subsequent output, make the specified zero attempt, and report failure. A rejected zero at the sink is reported as failed delivery.
4. Invalid initial clock never permits nonzero output. Last-good timestamp fallback, if approved, is explicitly tested without labelling it current time.
5. Shutdown delivers final zero to a functioning mock sink. New goals cannot bypass an inhibition; unrelated successful ticks cannot silently clear the fault.
6. Default `build_boat` still sends only zero with an active mission and fully valid position/heading. Existing contracts and boundary tests remain intact.

Likely files are motion service/tests, command router/bootstrap only as necessary for permission checks, integration regressions, and affected docs. No manager scheduling rewrite is proposed. Motion, integration and architecture owners should review these related responsibilities. Split the work if it exceeds the repository's approximate 400-line PR target.

### Following implementation PR: opt-in local waypoint reference controller

Suggested branch: `feat/ai-box-local-waypoint-controller`.
Suggested title: `ai-box: add an opt-in local waypoint reference controller`.

Prerequisites: first PR's stop regressions pass, explicit mock convention/settings are reviewed, and the test environment is usable. Add the controller and focused tests without changing default selection, demo behaviour or shared contracts. Keep initial examples restricted to recording sinks.

Acceptance/test matrix:

| Case | Required assertion |
|---|---|
| Ahead/left/right/behind under declared fixture convention | Correct signed rudder, explicit thrust and deterministic opposite-bearing tie |
| Heading crossing 0/360; reversed declared convention | Shortest-angle result and correct conversion/sign, without an implicit compass assumption |
| Large error and gain; valid finite input ranges | Finite bounded rudder, nonnegative bounded thrust, timestamp equals usable `now` |
| Distance below/equal/just above radius | Exact zero at/below boundary; reference command outside |
| Missing/invalid/stale/future required input | Zero, including transition from a previously nonzero command |
| NaN/infinity/overflow; invalid optional numeric values | No nonfinite/nonzero command escapes; invalid settings rejected |
| Supplied speed cap; absent optional speed/geo/uncertainty | Speed cap inhibits; unknown optional fields remain unknown |
| Goal cleared/replaced; state/heading updated | Immediate specified stop for clearing and deterministic recomputation on tick |
| Scripted approach with fixed mock clock | Zero at arrival, without claiming a command-driven trajectory |
| Explicit injection versus omitted controller | Alternative works through existing ports with recording sink; omitted controller stays zero |
| Active mission plus stop/fault/cancellation/shutdown | First PR's persistent-inhibition and delivery/reporting regressions continue to pass |

Run focused motion/mission tests, relevant integration tests, then `python3 -m pytest` from the root on this MacBook. Required CI additionally includes boundary checks, Ruff, mypy and the 90% coverage gate described in `CONTRIBUTING.md`; do not claim them passed until executed. No new runtime dependencies or simulator tests are proposed.

## Assessment validation results

Commands attempted from the repository root on the reviewed baseline:

Use `python3` on this MacBook. The initial attempts below are retained as an execution record; the subsequent virtual-environment run succeeded.

```text
$ python -m pytest
zsh:1: command not found: python
exit status: 127

$ python3 -m pytest
/Library/Frameworks/Python.framework/Versions/3.13/bin/python3: No module named pytest
exit status: 1
```

Those initial attempts collected no tests because the interpreter/environment was not ready. After the user authorised installing pytest, a git-ignored `.venv` was created with Python 3.13.6. It contains pytest 9.2.0 and the existing declared Pydantic dependency (2.14.3), with their transitive dependencies. No new dependency was added to a repository manifest. Tests import the source checkout through `pytest.ini`; editable package installation is unnecessary for this run.

```text
$ .venv/bin/python3 -m pytest
collected 111 items
111 passed in 0.77s
exit status: 0

$ .venv/bin/python3 -m pip check
No broken requirements found.
exit status: 0
```

The full suite, including architecture-boundary and integration tests, passed. Coverage, Ruff, mypy and the remaining CI gates were not run as part of this assessment. To use the environment interactively, run `source .venv/bin/activate`, then `python3 -m pytest` from the root.

### Subsequent foundation and stop-state checks

After the user requested testing, the full suite was rerun with `.venv/bin/python3 -m pytest`: **111 passed in 0.18s**, exit status 0. The mock demo, `.venv/bin/python3 scripts/demo_mock_boat.py`, also completed with exit status 0: five boat-state messages, one mission-progress message, four environment-progress messages and zero unacknowledged commands. Thrust stayed zero throughout. The demo manually supplies positions; it does not demonstrate command-driven movement.

A separate ephemeral diagnostic used the existing composition root, `MockPositionSource`, `MockPropulsionSink` and `LoopbackFmsLink`. The injected fixed-output test double returned test-only thrust 0.2 when a goal existed, otherwise zero; it implemented no navigation mathematics or vehicle dynamics. Each case delivered a mission assignment, ticked three times, delivered a stop envelope and inspected the last command immediately and over the following two ticks.

| Safe-state envelope mission ID | Thrust immediately after stop | Next tick | Following tick | Final mode |
|---|---|---|---|---|
| Absent | 0.0 | 0.0 | 0.2 | SAFE_STATE |
| Matches active mission | 0.0 | 0.0 | 0.0 | SAFE_STATE |
| Different mission | 0.0 | 0.0 | 0.2 | SAFE_STATE |

All three runtime shutdowns appended zero to the functioning recording sink. The diagnostic exited 0 because its assertions reproduced the expected gap; that is not a passing stop-inhibition invariant. The existing 111 tests pass without covering this case. Motion can also emit nonzero earlier in the stop-receiving tick, before the bridge processes the command and the router appends zero.

The diagnostic changed no source/test files or default selection and invoked no physical adapters. This is evidence about runtime command handling, not evidence of autonomous navigation, movement or deployment safety.

No controller, source code, test, default, propulsion adapter, simulator integration or package boundary was changed. No PR was opened or merged.
