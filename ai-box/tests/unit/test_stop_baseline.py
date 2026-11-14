"""Baseline stop/default guarantees independent of persistent inhibition."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from adapters.fms.loopback import LoopbackFmsLink
from adapters.propulsion.mock import MockPropulsionSink
from adapters.sensors.mock import MockPositionSource
from ai_box.bootstrap import build_boat
from ai_box.config.settings import AIBoxConfig
from ai_box.core.geometry import LocalPoint
from ai_box.environment.model import SearchArea
from ai_box.motion.commands import NavigationGoal, PropulsionCommand, VehicleState
from ai_box.motion.service import MotionService

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


class NonzeroTestController:
    """Synthetic output only; this does not implement navigation."""

    def __init__(self) -> None:
        self.calls = 0

    def compute(self, goal: NavigationGoal | None, state: VehicleState | None, now: datetime) -> PropulsionCommand:
        self.calls += 1
        return PropulsionCommand(timestamp=now, thrust=0.25, rudder=-0.5)


def _position() -> MockPositionSource:
    position = MockPositionSource()
    position.set_state(VehicleState(timestamp=NOW, local_position=LocalPoint(5.0, 5.0), heading_deg=0.0))
    return position


@pytest.mark.parametrize("stop_method", ["safe_stop", "stop"])
def test_stop_immediately_overrides_nonzero_output_without_controller(stop_method: str) -> None:
    sink, controller = MockPropulsionSink(), NonzeroTestController()
    motion = MotionService(_position(), sink, controller, clock=lambda: NOW)
    motion.set_goal(NavigationGoal(goal_id="goal", target=LocalPoint(20.0, 20.0)))
    motion.tick()
    nonzero = PropulsionCommand(timestamp=NOW, thrust=0.25, rudder=-0.5)
    assert sink.commands == (nonzero,)
    assert controller.calls == 1

    getattr(motion, stop_method)()

    assert sink.commands == (nonzero, PropulsionCommand.stop(NOW))
    assert motion.last_command == PropulsionCommand.stop(NOW)
    assert motion.goal is None
    assert controller.calls == 1


def test_default_composition_stays_zero_across_mission_goal_regeneration() -> None:
    position, sink = _position(), MockPropulsionSink()
    boat = build_boat(
        AIBoxConfig(),
        position=position,
        propulsion=sink,
        fms_link=LoopbackFmsLink(server=lambda envelope: []),
        search_areas={"area": SearchArea(0.0, 0.0, 20.0, 20.0)},
    )
    assert boat.missions.assign("mission", "area") is None
    targets: set[LocalPoint] = set()
    with boat.app:
        for _ in range(5):
            boat.app.tick()
            goal = boat.motion.goal
            assert goal is not None
            targets.add(goal.target)
            # Scripted arrival exercises retargeting, without modelling motion.
            position.set_state(VehicleState(timestamp=NOW, local_position=goal.target, heading_deg=0.0))
        assert len(targets) > 1
        assert len(sink.commands) >= 5
    assert all(command.thrust == 0.0 and command.rudder == 0.0 for command in sink.commands)
