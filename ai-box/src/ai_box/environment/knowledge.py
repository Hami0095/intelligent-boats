"""Environment knowledge: aggregates observations per region and answers search-progress questions."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Protocol

from ai_box.environment.model import RegionId, RegionIndexer
from ai_box.environment.observations import EnvironmentObservation, ObservationKind
from ai_box.memory.persistent import InMemoryStore, PersistentStore


class RegionStatus(str, Enum):
    UNKNOWN = "unknown"
    OBSERVED = "observed"  # something of interest was seen, but the region was not necessarily visited or searched
    VISITED = "visited"  # travelled through, but no search coverage recorded
    SEARCHED = "searched"


@dataclass(frozen=True)
class RegionRecord:
    region_id: RegionId
    status: RegionStatus
    visit_count: int
    search_count: int
    observation_count: int
    last_observed_at: datetime | None
    best_confidence: float


@dataclass
class _Aggregate:
    visit_count: int = 0
    search_count: int = 0
    observation_count: int = 0
    last_observed_at: datetime | None = None
    best_confidence: float = 0.0


class EnvironmentKnowledge(Protocol):
    def record(self, observation: EnvironmentObservation) -> None: ...

    def region(self, region_id: RegionId) -> RegionRecord: ...

    def unsearched(self, candidates: Iterable[RegionId]) -> list[RegionId]: ...

    def coverage(self, candidates: Iterable[RegionId]) -> float | None: ...

    def known_region_count(self) -> int: ...

    def last_observation_at(self) -> datetime | None: ...


class InMemoryEnvironmentKnowledge:
    def __init__(
        self,
        indexer: RegionIndexer,
        store: PersistentStore[EnvironmentObservation] | None = None,
    ) -> None:
        self._indexer = indexer
        self._store: PersistentStore[EnvironmentObservation] = store or InMemoryStore()
        self._regions: dict[RegionId, _Aggregate] = {}

    def record(self, observation: EnvironmentObservation) -> None:
        self._store.append(observation)
        agg = self._regions.setdefault(self._indexer.region_of(observation.point), _Aggregate())
        agg.observation_count += 1
        if observation.kind is ObservationKind.VISITED:
            agg.visit_count += 1
        elif observation.kind is ObservationKind.SEARCHED:
            agg.search_count += 1
        if agg.last_observed_at is None or observation.timestamp > agg.last_observed_at:
            agg.last_observed_at = observation.timestamp
        agg.best_confidence = max(agg.best_confidence, observation.confidence)

    def region(self, region_id: RegionId) -> RegionRecord:
        agg = self._regions.get(region_id, _Aggregate())
        if agg.search_count:
            status = RegionStatus.SEARCHED
        elif agg.visit_count:
            status = RegionStatus.VISITED
        elif agg.observation_count:
            status = RegionStatus.OBSERVED
        else:
            status = RegionStatus.UNKNOWN
        return RegionRecord(
            region_id=region_id,
            status=status,
            visit_count=agg.visit_count,
            search_count=agg.search_count,
            observation_count=agg.observation_count,
            last_observed_at=agg.last_observed_at,
            best_confidence=agg.best_confidence,
        )

    def unsearched(self, candidates: Iterable[RegionId]) -> list[RegionId]:
        seen: set[RegionId] = set()
        result: list[RegionId] = []
        for region_id in candidates:
            if region_id in seen:
                continue
            seen.add(region_id)
            if self.region(region_id).status is not RegionStatus.SEARCHED:
                result.append(region_id)
        return result

    def coverage(self, candidates: Iterable[RegionId]) -> float | None:
        unique = set(candidates)
        if not unique:
            return None
        searched = sum(1 for r in unique if self.region(r).status is RegionStatus.SEARCHED)
        return searched / len(unique)

    def known_region_count(self) -> int:
        return len(self._regions)

    def last_observation_at(self) -> datetime | None:
        stamps = [a.last_observed_at for a in self._regions.values() if a.last_observed_at]
        return max(stamps) if stamps else None
