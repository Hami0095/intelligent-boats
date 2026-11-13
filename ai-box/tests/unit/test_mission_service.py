from datetime import datetime, timezone

from adapters.propulsion.mock import MockPropulsionSink
from adapters.sensors.mock import MockPositionSource
from ai_box.core.geometry import LocalPoint
from ai_box.decision.mission import SearchMissionService
from ai_box.decision.policy import UnsearchedRegionPolicy
from ai_box.environment.knowledge import InMemoryEnvironmentKnowledge
from ai_box.environment.model import GridIndexer, SearchArea
from ai_box.memory.mission import MissionMemory
from ai_box.motion.commands import VehicleState
from ai_box.motion.controller import HoldPositionController
from ai_box.motion.service import MotionService

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


class Harness:
    def __init__(self, safe=True):
        self.position = MockPositionSource()
        self.sink = MockPropulsionSink()
        self.grid = GridIndexer(cell_size_m=10.0)
        self.motion = MotionService(self.position, self.sink, HoldPositionController(), clock=lambda: T0)
        self.safe = safe
        self.missions = SearchMissionService(
            position=self.position, motion=self.motion,
            knowledge=InMemoryEnvironmentKnowledge(self.grid), indexer=self.grid,
            search_areas={"area-1": SearchArea(0.0, 0.0, 20.0, 20.0)},
            policy=UnsearchedRegionPolicy(), mission_memory=MissionMemory(),
            safety_clear=lambda: self.safe,
        )

    def locate(self, x, y):
        self.position.set_state(VehicleState(timestamp=T0, local_position=LocalPoint(x, y)))


def test_assignment_rejects_unknown_area_and_a_second_mission():
    h = Harness()
    assert "unknown search_area_id" in h.missions.assign("m-1", "nowhere")
    assert h.missions.assign("m-1", "area-1") is None
    assert "already active" in h.missions.assign("m-2", "area-1")


def test_cancel_only_matches_the_active_mission():
    h = Harness()
    h.missions.assign("m-1", "area-1")
    assert h.missions.cancel("other") is False
    assert h.missions.cancel("m-1") is True
    assert h.missions.active_mission is None


def test_progress_is_unavailable_without_a_mission():
    assert Harness().missions.progress() is None


def test_ticking_records_the_visit_and_sets_the_first_goal():
    h = Harness()
    h.missions.assign("m-1", "area-1")
    h.locate(5, 5)
    h.missions.tick()
    assert h.missions.progress().known_region_count == 1
    assert h.motion.goal is not None
    assert h.motion.goal.target == LocalPoint(5.0, 15.0)


def test_goal_is_replaced_only_after_the_boat_arrives():
    h = Harness()
    h.missions.assign("m-1", "area-1")
    h.locate(5, 5)
    h.missions.tick()
    first = h.motion.goal

    h.locate(5, 9)  # still outside the acceptance radius of the goal
    h.missions.tick()
    assert h.motion.goal is first

    h.locate(5, 14)  # inside it
    h.missions.tick()
    assert h.motion.goal is not None and h.motion.goal != first


def test_unsafe_conditions_clear_the_goal_and_stop_new_targets():
    h = Harness()
    h.missions.assign("m-1", "area-1")
    h.locate(5, 5)
    h.missions.tick()
    h.safe = False
    h.missions.tick()
    assert h.motion.goal is None


def test_position_without_local_estimate_is_ignored():
    h = Harness()
    h.missions.assign("m-1", "area-1")
    h.position.set_state(VehicleState(timestamp=T0))
    h.missions.tick()
    assert h.motion.goal is None
    assert h.missions.progress().known_region_count == 0
