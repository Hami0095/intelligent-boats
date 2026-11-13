from datetime import datetime, timedelta, timezone

import pytest
from adapters.propulsion.mock import MockPropulsionSink
from adapters.sensors.mock import MockPositionSource
from ai_box.core.geometry import LocalPoint
from ai_box.memory.mission import MissionMemory
from ai_box.memory.records import MemoryRecord
from ai_box.memory.short_term import ShortTermMemory
from ai_box.motion.commands import NavigationGoal, PropulsionCommand
from ai_box.motion.controller import HoldPositionController
from ai_box.motion.service import MotionService
from marine_contracts import Provenance

T0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def _record(key, seconds_ago):
    return MemoryRecord(
        key=key,
        value=1,
        timestamp=T0 - timedelta(seconds=seconds_ago),
        provenance=Provenance(source="test"),
        confidence=0.5,
    )


def test_short_term_memory_hides_stale_records():
    memory = ShortTermMemory(capacity=10, max_age_s=60)
    memory.put(_record("old", 120))
    memory.put(_record("fresh", 5))
    assert [r.key for r in memory.recent(T0)] == ["fresh"]


def test_short_term_memory_is_bounded_and_drops_oldest():
    memory = ShortTermMemory(capacity=2, max_age_s=600)
    for key in ("a", "b", "c"):
        memory.put(_record(key, 1))
    assert len(memory) == 2
    assert [r.key for r in memory.recent(T0)] == ["c", "b"]


def test_memory_records_must_be_timestamped_in_utc():
    with pytest.raises(ValueError):
        MemoryRecord(
            key="k", value=0, timestamp=datetime(2026, 1, 1), provenance=Provenance(source="t"), confidence=0.5
        )


def test_mission_memory_is_scoped_to_one_mission():
    memory = MissionMemory()
    memory.record_visit("m-1", "grid:0:0")
    memory.record_visit("m-2", "grid:9:9")
    assert memory.visited_regions("m-1") == {"grid:0:0"}
    memory.forget("m-1")
    assert memory.visited_regions("m-1") == frozenset()
    assert memory.visited_regions("m-2") == {"grid:9:9"}


def test_propulsion_commands_are_normalised():
    with pytest.raises(ValueError):
        PropulsionCommand(timestamp=T0, thrust=1.2, rudder=0.0)
    with pytest.raises(ValueError):
        PropulsionCommand(timestamp=T0, thrust=0.0, rudder=-2.0)
    assert PropulsionCommand.stop(T0) == PropulsionCommand(timestamp=T0, thrust=0.0, rudder=0.0)


def test_navigation_goal_requires_a_positive_radius():
    with pytest.raises(ValueError):
        NavigationGoal(goal_id="g", target=LocalPoint(0, 0), acceptance_radius_m=0)


def test_hold_position_controller_ignores_the_goal():
    goal = NavigationGoal(goal_id="g", target=LocalPoint(100, 100))
    command = HoldPositionController().compute(goal, None, T0)
    assert command.thrust == 0.0 and command.rudder == 0.0


def test_motion_service_commands_zero_propulsion_and_safe_stop_clears_goal():
    position, sink = MockPositionSource(), MockPropulsionSink()
    motion = MotionService(position, sink, HoldPositionController(), clock=lambda: T0)
    motion.set_goal(NavigationGoal(goal_id="g", target=LocalPoint(1, 1)))
    motion.tick()
    assert sink.last == PropulsionCommand.stop(T0)
    assert motion.goal is not None

    motion.safe_stop()
    assert motion.goal is None
    assert len(sink.commands) == 2
