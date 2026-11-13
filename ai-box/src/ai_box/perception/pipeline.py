"""Perception service: sensor samples in, detections and obstacle summaries out."""

from __future__ import annotations

import logging
from collections.abc import Sequence

from marine_contracts import HealthStatus, MessageType

from ai_box.core.events import FMS_OUTBOUND, PERCEPTION_FRAME, SENSOR_SAMPLE, Outbound
from ai_box.core.ports import Detection, ObstacleDetector, SensorKind, SensorSample
from ai_box.core.service import Service, ServiceContext
from ai_box.perception.frames import PerceptionFrame
from ai_box.perception.summary import to_obstacle_summary

log = logging.getLogger("ai_box.perception")

COLLISION_RELEVANT_KINDS = frozenset({SensorKind.CAMERA_FRAME, SensorKind.RANGE})


class NullObstacleDetector:
    """Detects nothing. Used when no detector is configured; keeps the pipeline wired."""

    def detect(self, sample: SensorSample) -> Sequence[Detection]:
        return ()


class PerceptionService(Service):
    name = "perception"
    depends_on = ("sensor-ingest",)

    def __init__(self, detector: ObstacleDetector) -> None:
        self._detector = detector
        self._ctx: ServiceContext | None = None
        self._errors = 0

    def start(self, ctx: ServiceContext) -> None:
        self._ctx = ctx
        ctx.bus.subscribe(SENSOR_SAMPLE, self._on_sample)

    def stop(self) -> None:
        if self._ctx is not None:
            self._ctx.bus.unsubscribe(SENSOR_SAMPLE, self._on_sample)
        self._ctx = None

    def health_detail(self) -> tuple[HealthStatus, str]:
        if self._errors:
            return HealthStatus.DEGRADED, f"{self._errors} detector error(s)"
        return HealthStatus.OK, ""

    def _on_sample(self, sample: SensorSample) -> None:
        if self._ctx is None or sample.kind not in COLLISION_RELEVANT_KINDS:
            return
        try:
            detections = tuple(self._detector.detect(sample))
        except Exception:
            self._errors += 1
            log.exception("detector failed for sensor %s", sample.sensor_id)
            return
        frame = PerceptionFrame(sensor_id=sample.sensor_id, timestamp=sample.timestamp, detections=detections)
        self._ctx.bus.publish(PERCEPTION_FRAME, frame)
        if detections:
            self._ctx.bus.publish(
                FMS_OUTBOUND,
                Outbound(message_type=MessageType.OBSTACLE_SUMMARY, payload=to_obstacle_summary(frame)),
            )
