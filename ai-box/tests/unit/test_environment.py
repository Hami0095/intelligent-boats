from datetime import datetime, timezone

import pytest

from ai_box.core.geometry import LocalPoint
from ai_box.environment.knowledge import InMemoryEnvironmentKnowledge, RegionStatus
from ai_box.environment.model import GridIndexer, SearchArea
from ai_box.environment.observations import EnvironmentObservation, ObservationKind
from ai_box.memory.persistent import InMemoryStore
from marine_contracts import Provenance

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def obs(kind, x, y, minute=0, confidence=0.6):
    return EnvironmentObservation(
        kind=kind,
        point=LocalPoint(x, y),
        timestamp=datetime(2026, 1, 1, 0, minute, tzinfo=timezone.utc),
        provenance=Provenance(source="test"),
        confidence=confidence,
    )


def test_grid_round_trip_returns_the_same_region():
    grid = GridIndexer(cell_size_m=10.0)
    region = grid.region_of(LocalPoint(23.0, -4.0))
    assert grid.region_of(grid.center_of(region)) == region


def test_grid_regions_cover_the_whole_area_inclusively():
    grid = GridIndexer(cell_size_m=10.0)
    regions = grid.regions_in(SearchArea(0.0, 0.0, 20.0, 20.0))
    assert len(regions) == 9
    assert len(set(regions)) == 9


def test_invalid_cell_size_and_region_ids_are_rejected():
    with pytest.raises(ValueError):
        GridIndexer(cell_size_m=0)
    with pytest.raises(ValueError):
        GridIndexer().center_of("not-a-grid-id")


def test_search_area_must_be_ordered():
    with pytest.raises(ValueError):
        SearchArea(10.0, 0.0, 0.0, 5.0)


def test_visiting_a_region_is_not_the_same_as_searching_it():
    grid = GridIndexer()
    knowledge = InMemoryEnvironmentKnowledge(grid)
    knowledge.record(obs(ObservationKind.VISITED, 5, 5))
    region = grid.region_of(LocalPoint(5, 5))
    assert knowledge.region(region).status is RegionStatus.VISITED
    assert knowledge.unsearched([region]) == [region]


def test_search_coverage_marks_region_searched():
    grid = GridIndexer()
    knowledge = InMemoryEnvironmentKnowledge(grid)
    knowledge.record(obs(ObservationKind.SEARCHED, 5, 5))
    region = grid.region_of(LocalPoint(5, 5))
    assert knowledge.region(region).status is RegionStatus.SEARCHED
    assert knowledge.unsearched([region]) == []


def test_observations_of_objects_do_not_change_search_status():
    grid = GridIndexer()
    knowledge = InMemoryEnvironmentKnowledge(grid)
    knowledge.record(obs(ObservationKind.OBSERVED, 5, 5))
    region = grid.region_of(LocalPoint(5, 5))
    assert knowledge.region(region).status is RegionStatus.UNKNOWN
    assert knowledge.region(region).observation_count == 1


def test_coverage_is_the_searched_fraction_of_candidates():
    grid = GridIndexer(cell_size_m=10.0)
    knowledge = InMemoryEnvironmentKnowledge(grid)
    knowledge.record(obs(ObservationKind.SEARCHED, 5, 5))
    candidates = grid.regions_in(SearchArea(0.0, 0.0, 19.0, 9.0))  # two cells
    assert knowledge.coverage(candidates) == 0.5
    assert knowledge.coverage([]) is None


def test_unsearched_removes_duplicates_and_keeps_order():
    grid = GridIndexer()
    knowledge = InMemoryEnvironmentKnowledge(grid)
    assert knowledge.unsearched(["grid:0:0", "grid:1:0", "grid:0:0"]) == ["grid:0:0", "grid:1:0"]


def test_knowledge_keeps_every_observation_in_its_store():
    store = InMemoryStore()
    knowledge = InMemoryEnvironmentKnowledge(GridIndexer(), store=store)
    knowledge.record(obs(ObservationKind.VISITED, 1, 1))
    knowledge.record(obs(ObservationKind.VISITED, 2, 2, minute=5))
    assert len(store.items()) == 2
    assert knowledge.last_observation_at() == datetime(2026, 1, 1, 0, 5, tzinfo=timezone.utc)
    assert knowledge.known_region_count() == 1


def test_observation_confidence_must_be_a_probability():
    with pytest.raises(ValueError):
        obs(ObservationKind.VISITED, 0, 0, confidence=1.5)
