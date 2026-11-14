"""Exploration policy interface and a deliberately simple reference implementation."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from ai_box.core.geometry import LocalPoint
from ai_box.decision.intent import NavigationIntent
from ai_box.environment.knowledge import EnvironmentKnowledge, RegionStatus
from ai_box.environment.model import RegionId, RegionIndexer


@dataclass(frozen=True)
class DecisionState:
    position: LocalPoint | None
    safety_clear: bool
    candidate_regions: Sequence[RegionId]
    mission_id: str | None = None


class ExplorationPolicy(Protocol):
    def next_intent(
        self,
        state: DecisionState,
        knowledge: EnvironmentKnowledge,
        indexer: RegionIndexer,
    ) -> NavigationIntent | None: ...


class UnsearchedRegionPolicy:
    """Reference policy: prefer never-visited regions, then nearest, avoiding the region the boat is in.

    This is a baseline for evaluating smarter approaches, not a tuned search strategy.
    """

    def next_intent(
        self,
        state: DecisionState,
        knowledge: EnvironmentKnowledge,
        indexer: RegionIndexer,
    ) -> NavigationIntent | None:
        if not state.safety_clear or state.position is None:
            return None
        here = indexer.region_of(state.position)
        best: tuple[tuple[int, float, str], RegionId, LocalPoint] | None = None
        for region_id in knowledge.unsearched(state.candidate_regions):
            if region_id == here:
                continue
            center = indexer.center_of(region_id)
            status = knowledge.region(region_id).status
            key = (
                0 if status in (RegionStatus.UNKNOWN, RegionStatus.OBSERVED) else 1,
                state.position.distance_to(center),
                region_id,
            )
            if best is None or key < best[0]:
                best = (key, region_id, center)
        if best is None:
            return None
        _, _, center = best
        return NavigationIntent(target=center, reason="nearest unsearched region", mission_id=state.mission_id)
