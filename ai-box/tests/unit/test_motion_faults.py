"""Approved stop/fault invariants, using recording adapters and fixed-output doubles."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from adapters.propulsion.mock import MockPropulsionSink
from adapters.sensors.mock import MockPositionSource
from ai_box.core.geometry import LocalPoint
from ai_box.motion.commands import NavigationGoal, PropulsionCommand, VehicleState
from ai_box.motion.service import MotionFault, MotionService
from marine_contracts import HealthStatus

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
GOAL = NavigationGoal(goal_id="test", target=LocalPoint(20.0, 0.0))


def _output(goal, state, now) -> PropulsionCommand:
    return PropulsionCommand(timestamp=now, thrust=0.2 if goal else 0.0, rudder=0.0)


@pytest.fixture
def rig() -> SimpleNamespace:
    position, sink = MockPositionSource(), MockPropulsionSink()
    position.set_state(VehicleState(timestamp=T0, local_position=LocalPoint(0.0, 0.0), heading_deg=0.0))
    position.current_state = Mock(wraps=position.current_state)
    sink.apply = Mock(wraps=sink.apply)
    controller, clock = Mock(), Mock(return_value=T0)
    controller.compute.side_effect = _output
    motion = MotionService(position, sink, controller, clock=clock)
    motion.set_goal(GOAL)
    return SimpleNamespace(motion=motion, position=position, sink=sink, controller=controller, clock=clock)


def test_safe_stop_latches_before_clock_and_goals_cannot_rearm(rig: SimpleNamespace) -> None:
    rig.motion.tick()
    assert rig.sink.last.thrust == 0.2

    def observing_clock() -> datetime:
        assert rig.motion.inhibited
        return T0

    rig.clock.side_effect = observing_clock
    rig.motion.safe_stop()
    assert rig.motion.goal is None
    calls = (rig.position.current_state.call_count, rig.controller.compute.call_count)
    for _ in range(3):
        rig.motion.set_goal(GOAL)
        rig.motion.tick()
        assert rig.sink.last == PropulsionCommand.stop(T0)
    assert calls == (rig.position.current_state.call_count, rig.controller.compute.call_count)
    assert rig.sink.apply.call_count == 5


def test_ordinary_goal_clear_stops_immediately_without_latching(rig: SimpleNamespace) -> None:
    rig.motion.tick()
    rig.motion.set_goal(None)
    assert rig.sink.last == PropulsionCommand.stop(T0)
    assert rig.sink.apply.call_count == 2
    assert not rig.motion.inhibited
    rig.motion.set_goal(GOAL)
    rig.motion.tick()
    assert rig.sink.last.thrust == 0.2


@pytest.mark.parametrize("fault", ["source", "controller", "sink", "invalid_result"])
def test_tick_fault_inhibits_and_attempts_one_zero(rig: SimpleNamespace, fault: str) -> None:
    rig.motion.tick()
    previous = rig.motion.last_command
    if fault == "invalid_result":
        rig.controller.compute.side_effect = None
        rig.controller.compute.return_value = object()
    else:
        callback = {
            "source": rig.position.current_state,
            "controller": rig.controller.compute,
            "sink": rig.sink.apply,
        }[fault]
        callback.side_effect = RuntimeError("injected fault")
    attempts = rig.sink.apply.call_count
    with pytest.raises(MotionFault):
        rig.motion.tick()
    assert rig.motion.inhibited
    assert rig.sink.apply.call_count - attempts == (2 if fault == "sink" else 1)
    assert rig.sink.apply.call_args.args[0] == PropulsionCommand.stop(T0)
    assert rig.motion.last_command == (previous if fault == "sink" else PropulsionCommand.stop(T0))
    rig.position.current_state.side_effect = None
    rig.controller.compute.side_effect = _output
    rig.sink.apply.side_effect = None
    for _ in range(2):
        rig.motion.tick()
        assert rig.sink.last == PropulsionCommand.stop(T0)
    assert rig.motion.inhibited
    assert rig.motion.health_detail()[0] is HealthStatus.DEGRADED


@pytest.mark.parametrize("bad_clock", [RuntimeError("clock unavailable"), datetime(2026, 1, 1), None])
@pytest.mark.parametrize("operation", ["tick", "safe_stop", "clear_goal", "stop"])
def test_later_clock_failure_uses_cached_time_and_never_rearms(
    rig: SimpleNamespace, bad_clock: object, operation: str
) -> None:
    rig.motion.tick()
    rig.clock.side_effect = bad_clock if isinstance(bad_clock, Exception) else None
    rig.clock.return_value = bad_clock
    with pytest.raises(MotionFault):
        if operation == "clear_goal":
            rig.motion.set_goal(None)
        else:
            getattr(rig.motion, operation)()
    assert rig.sink.last == PropulsionCommand.stop(T0)
    assert rig.sink.apply.call_count == 2
    assert "not fresh" in rig.motion.health_detail()[1]
    rig.clock.side_effect = None
    rig.clock.return_value = T0 + timedelta(seconds=1)
    rig.motion.tick()
    assert rig.sink.last == PropulsionCommand.stop(T0 + timedelta(seconds=1))
    assert rig.motion.inhibited
    assert rig.motion.health_detail()[0] is HealthStatus.DEGRADED


@pytest.mark.parametrize("bad_clock", [RuntimeError("clock unavailable"), datetime(2026, 1, 1), None])
@pytest.mark.parametrize("operation", ["tick", "safe_stop", "clear_goal", "stop"])
def test_initial_clock_failure_emits_no_command(rig: SimpleNamespace, bad_clock: object, operation: str) -> None:
    rig.clock.side_effect = bad_clock if isinstance(bad_clock, Exception) else None
    rig.clock.return_value = bad_clock
    with pytest.raises(MotionFault):
        if operation == "clear_goal":
            rig.motion.set_goal(None)
        else:
            getattr(rig.motion, operation)()
    assert rig.motion.inhibited
    assert rig.motion.last_command is None
    rig.sink.apply.assert_not_called()
    rig.position.current_state.assert_not_called()
    rig.controller.compute.assert_not_called()


@pytest.mark.parametrize("action", ["safe_stop", "clear_goal", "stop", "zero_tick", "reentrant_tick"])
def test_failed_stop_is_bounded_and_last_command_remains_truthful(rig: SimpleNamespace, action: str) -> None:
    rig.motion.tick()
    previous = rig.motion.last_command
    if action in ("zero_tick", "reentrant_tick"):

        def zero(goal, state, now):
            if action == "reentrant_tick":
                rig.motion.inhibit()
            return PropulsionCommand.stop(now)

        rig.controller.compute.side_effect = zero
        operation = rig.motion.tick
    else:
        operation = (lambda: rig.motion.set_goal(None)) if action == "clear_goal" else getattr(rig.motion, action)
    rig.sink.apply.side_effect = ConnectionError("sink unavailable")
    attempts = rig.sink.apply.call_count
    with pytest.raises(MotionFault):
        operation()
    assert rig.motion.inhibited and rig.motion.goal is None
    assert rig.sink.apply.call_count == attempts + 1
    assert rig.motion.last_command == previous
    for count in range(1, 4):
        with pytest.raises(MotionFault):
            rig.motion.tick()
        assert rig.sink.apply.call_count == attempts + 1 + count
        assert rig.sink.apply.call_args.args[0] == PropulsionCommand.stop(T0)
        assert rig.motion.last_command == previous
    assert rig.motion.health_detail()[0] is HealthStatus.DEGRADED


@pytest.mark.parametrize("callback", ["clock", "source", "controller"])
def test_callback_cannot_bypass_inhibition(rig: SimpleNamespace, callback: str) -> None:
    if callback == "clock":

        def clock() -> datetime:
            rig.motion.inhibit()
            return T0

        rig.clock.side_effect = clock
    elif callback == "source":
        state = rig.position.current_state()

        def read():
            rig.motion.inhibit()
            return state

        rig.position.current_state.side_effect = read
    else:

        def compute(goal, state, now):
            rig.motion.inhibit()
            return _output(goal, state, now)

        rig.controller.compute.side_effect = compute
    rig.motion.tick()
    assert rig.motion.inhibited
    assert rig.sink.last == PropulsionCommand.stop(T0)
