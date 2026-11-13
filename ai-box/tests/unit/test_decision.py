from datetime import datetime, timezone

from ai_box.core.geometry import LocalPoint
from ai_box.decision.policy import DecisionState, UnsearchedRegionPolicy
from ai_box.environment.knowledge import InMemoryEnvironmentKnowledge
from ai_box.environment.model import GridIndexer, SearchArea
from ai_box.environment.observations import EnvironmentObservation, ObservationKind
from marine_contracts import Provenance

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
GRID = GridIndexer(cell_size_m=10.0)
AREA = GRID.regions_in(SearchArea(0.0, 0.0, 20.0, 20.0))


def _knowledge(*observations):
    knowledge = InMemoryEnvironmentKnowledge(GRID)
    for kind, point in observations:
        knowledge.record(
            EnvironmentObservation(
                kind=kind, point=point, timestamp=T0, provenance=Provenance(source="test"), confidence=1.0
            )
        )
    return knowledge


def _state(position, safe=True):
    return DecisionState(position=position, safety_clear=safe, candidate_regions=AREA, mission_id="m")


def test_policy_declines_when_safety_is_not_clear():
    intent = UnsearchedRegionPolicy().next_intent(_state(LocalPoint(5, 5), safe=False), _knowledge(), GRID)
    assert intent is None


def test_policy_declines_without_a_position_estimate():
    assert UnsearchedRegionPolicy().next_intent(_state(None), _knowledge(), GRID) is None


def test_policy_never_targets_the_region_the_boat_is_already_in():
    intent = UnsearchedRegionPolicy().next_intent(_state(LocalPoint(5, 5)), _knowledge(), GRID)
    assert intent is not None
    assert GRID.region_of(intent.target) != GRID.region_of(LocalPoint(5, 5))


def test_policy_prefers_never_visited_regions_over_visited_ones():
    near_visited = LocalPoint(15, 5)  # adjacent region, visited but not searched
    knowledge = _knowledge((ObservationKind.VISITED, near_visited))
    intent = UnsearchedRegionPolicy().next_intent(_state(LocalPoint(5, 5)), knowledge, GRID)
    assert GRID.region_of(intent.target) != GRID.region_of(near_visited)


def test_policy_returns_nothing_once_everything_is_searched():
    everything = [(ObservationKind.SEARCHED, GRID.center_of(r)) for r in AREA]
    intent = UnsearchedRegionPolicy().next_intent(_state(LocalPoint(5, 5)), _knowledge(*everything), GRID)
    assert intent is None
