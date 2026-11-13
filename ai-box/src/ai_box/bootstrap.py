"""Composition root: wires concrete adapters into the AI Box.

This is the ONLY place where the AI Box is assembled. Adapters are passed in; the
AI Box never constructs device or simulator objects itself.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from ai_box.config.settings import AIBoxConfig
from ai_box.core.app import AIBoxApp
from ai_box.core.events import EventBus
from ai_box.core.ports import FmsLink, ObstacleDetector, PositionSource, PropulsionSink, SensorSource
from ai_box.core.state import OperatingState
from ai_box.decision.mission import SearchMissionService
from ai_box.decision.policy import ExplorationPolicy, UnsearchedRegionPolicy
from ai_box.decision.reward import NoReward
from ai_box.environment.knowledge import InMemoryEnvironmentKnowledge
from ai_box.environment.model import GridIndexer, RegionIndexer, SearchArea
from ai_box.memory.mission import MissionMemory
from ai_box.memory.persistent import InMemoryStore
from ai_box.motion.controller import HoldPositionController, MotionController
from ai_box.motion.service import MotionService
from ai_box.perception.pipeline import NullObstacleDetector, PerceptionService
from ai_box.services.command_router import CommandRouter
from ai_box.services.fms_bridge import FmsBridgeService
from ai_box.services.sensor_ingest import SensorIngestService
from ai_box.telemetry.service import TelemetryService


@dataclass
class BoatRuntime:
    """The wired AI Box. Exposed so tests and the future runtime loop can reach its parts."""

    app: AIBoxApp
    operating: OperatingState
    motion: MotionService
    missions: SearchMissionService
    knowledge: InMemoryEnvironmentKnowledge
    bridge: FmsBridgeService


def build_boat(
    config: AIBoxConfig,
    *,
    position: PositionSource,
    propulsion: PropulsionSink,
    fms_link: FmsLink,
    sensors: Sequence[SensorSource] = (),
    detector: ObstacleDetector | None = None,
    search_areas: Mapping[str, SearchArea] | None = None,
    indexer: RegionIndexer | None = None,
    policy: ExplorationPolicy | None = None,
    controller: MotionController | None = None,
    battery_provider: Callable[[], float | None] | None = None,
    bus: EventBus | None = None,
) -> BoatRuntime:
    indexer = indexer or GridIndexer()
    app = AIBoxApp(config, bus=bus)
    operating = OperatingState()
    knowledge = InMemoryEnvironmentKnowledge(indexer, store=InMemoryStore())
    motion = MotionService(position, propulsion, controller or HoldPositionController())
    missions = SearchMissionService(
        position=position,
        motion=motion,
        knowledge=knowledge,
        indexer=indexer,
        search_areas=search_areas or {},
        policy=policy or UnsearchedRegionPolicy(),
        mission_memory=MissionMemory(),
        reward=NoReward(),
    )
    telemetry = TelemetryService(
        position=position,
        operating=operating,
        health_provider=app.health_report,
        progress_provider=missions.progress,
        battery_provider=battery_provider,
    )
    bridge = FmsBridgeService(fms_link)
    router = CommandRouter(missions=missions, motion=motion, operating=operating)

    for service in (
        SensorIngestService(sensors),
        PerceptionService(detector or NullObstacleDetector()),
        motion,
        missions,
        telemetry,
        bridge,
        router,
    ):
        app.register(service)

    return BoatRuntime(
        app=app,
        operating=operating,
        motion=motion,
        missions=missions,
        knowledge=knowledge,
        bridge=bridge,
    )
