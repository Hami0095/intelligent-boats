"""Search-mission service: owns the active mission and feeds goals to motion.

Responsibilities: record where the boat has travelled, ask the exploration policy
for the next target, and hand that target to motion. It does NOT decide how the
boat steers, and it does NOT know about the FMS wire format.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from marine_contracts import EnvironmentProgressPayload, Provenance

from ai_box.core.ports import PositionSource
from ai_box.core.service import Service, ServiceContext
from ai_box.decision.policy import DecisionState, ExplorationPolicy
from ai_box.decision.reward import NoReward, RewardSignal
from ai_box.environment.knowledge import EnvironmentKnowledge, RegionStatus
from ai_box.environment.model import RegionId, RegionIndexer, SearchArea
from ai_box.environment.observations import EnvironmentObservation, ObservationKind
from ai_box.memory.mission import MissionMemory
from ai_box.motion.commands import NavigationGoal
from ai_box.motion.service import MotionService

# Placeholder until a position-quality model exists (OPEN: calibration and estimation).
PLACEHOLDER_VISIT_CONFIDENCE = 0.5


@dataclass(frozen=True)
class ActiveMission:
    mission_id: str
    search_area_id: str
    regions: tuple[RegionId, ...]


class SearchMissionService(Service):
    name = "search-mission"

    def __init__(
        self,
        *,
        position: PositionSource,
        motion: MotionService,
        knowledge: EnvironmentKnowledge,
        indexer: RegionIndexer,
        search_areas: Mapping[str, SearchArea],
        policy: ExplorationPolicy,
        mission_memory: MissionMemory,
        reward: RewardSignal | None = None,
        safety_clear: Callable[[], bool] = lambda: True,
    ) -> None:
        self._position = position
        self._motion = motion
        self._knowledge = knowledge
        self._indexer = indexer
        self._areas = dict(search_areas)
        self._policy = policy
        self._mission_memory = mission_memory
        self._reward = reward or NoReward()
        self._safety_clear = safety_clear
        self._active: ActiveMission | None = None
        self.last_reward: float | None = None

    @property
    def active_mission(self) -> ActiveMission | None:
        return self._active

    def start(self, ctx: ServiceContext) -> None:
        return None

    def stop(self) -> None:
        self._motion.set_goal(None)
        self._active = None

    def assign(self, mission_id: str, search_area_id: str) -> str | None:
        """Activate a mission. Returns None on success, or the reason it was refused."""
        if self._active is not None:
            return f"another mission ({self._active.mission_id}) is already active"
        area = self._areas.get(search_area_id)
        if area is None:
            return f"unknown search_area_id {search_area_id!r}"
        self._active = ActiveMission(
            mission_id=mission_id,
            search_area_id=search_area_id,
            regions=tuple(self._indexer.regions_in(area)),
        )
        return None

    def cancel(self, mission_id: str) -> bool:
        if self._active is None or self._active.mission_id != mission_id:
            return False
        self._motion.set_goal(None)
        self._mission_memory.forget(mission_id)
        self._active = None
        return True

    def progress(self) -> EnvironmentProgressPayload | None:
        mission = self._active
        if mission is None:
            return None
        searched = sum(
            1 for r in mission.regions if self._knowledge.region(r).status is RegionStatus.SEARCHED
        )
        total = len(mission.regions)
        return EnvironmentProgressPayload(
            searched_region_count=searched,
            known_region_count=self._knowledge.known_region_count(),
            coverage_fraction=(searched / total) if total else None,
            last_observation_at=self._knowledge.last_observation_at(),
        )

    def tick(self) -> None:
        mission = self._active
        if mission is None:
            return
        state = self._position.current_state()
        if state is None or state.local_position is None:
            return
        observation = EnvironmentObservation(
            kind=ObservationKind.VISITED,
            point=state.local_position,
            timestamp=state.timestamp,
            provenance=Provenance(source="position-source"),
            confidence=PLACEHOLDER_VISIT_CONFIDENCE,
            mission_id=mission.mission_id,
        )
        self._knowledge.record(observation)
        self._mission_memory.record_visit(mission.mission_id, self._indexer.region_of(state.local_position))
        self.last_reward = self._reward.evaluate(observation)

        if not self._safety_clear():
            self._motion.set_goal(None)
            return

        goal = self._motion.goal
        if goal is not None:
            if state.local_position.distance_to(goal.target) > goal.acceptance_radius_m:
                return  # still en route
            self._motion.set_goal(None)

        intent = self._policy.next_intent(
            DecisionState(
                position=state.local_position,
                safety_clear=True,
                candidate_regions=mission.regions,
                mission_id=mission.mission_id,
            ),
            self._knowledge,
            self._indexer,
        )
        if intent is not None:
            self._motion.set_goal(
                NavigationGoal(
                    goal_id=f"{mission.mission_id}:{self._indexer.region_of(intent.target)}",
                    target=intent.target,
                )
            )
