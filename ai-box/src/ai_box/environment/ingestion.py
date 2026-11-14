"""Normalize explicitly supplied mock observations and record typed bus events."""

from __future__ import annotations

import logging
import math
from collections.abc import Mapping

from marine_contracts import HealthStatus, Provenance

from ai_box.core.events import ENVIRONMENT_OBSERVATION, SENSOR_SAMPLE
from ai_box.core.geometry import LocalPoint
from ai_box.core.ports import SensorKind, SensorSample
from ai_box.core.service import Service, ServiceContext
from ai_box.environment.knowledge import EnvironmentKnowledge
from ai_box.environment.observations import EnvironmentObservation, ObservationKind

log = logging.getLogger("ai_box.environment.ingestion")

_OBSERVATION_KEY = "environment_observation"
_OBSERVATION_FIELDS = frozenset({"point", "confidence", "mission_id", "provenance_detail"})
_POINT_FIELDS = frozenset({"x_m", "y_m"})


def _number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{field} must be a finite number")
    return float(value)


def _from_sensor_sample(sample: SensorSample) -> EnvironmentObservation | None:
    if _OBSERVATION_KEY not in sample.data:
        return None
    if sample.kind is not SensorKind.OTHER:
        raise ValueError(f"{_OBSERVATION_KEY} is only supported on OTHER samples")
    if not sample.sensor_id:
        raise ValueError("sensor_id must not be empty")

    raw = sample.data[_OBSERVATION_KEY]
    if not isinstance(raw, Mapping):
        raise ValueError(f"{_OBSERVATION_KEY} must be a mapping")
    if set(raw) - _OBSERVATION_FIELDS:
        raise ValueError(f"{_OBSERVATION_KEY} has unexpected fields")

    point = raw.get("point")
    if not isinstance(point, Mapping) or set(point) != _POINT_FIELDS:
        raise ValueError("point must contain exactly x_m and y_m")

    confidence = _number(raw.get("confidence"), "confidence")
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be within [0, 1]")

    mission_id = raw.get("mission_id")
    if mission_id is not None and not isinstance(mission_id, str):
        raise ValueError("mission_id must be a string when provided")

    detail = raw.get("provenance_detail")
    if detail is not None and not isinstance(detail, str):
        raise ValueError("provenance_detail must be a string when provided")

    return EnvironmentObservation(
        kind=ObservationKind.OBSERVED,
        point=LocalPoint(x_m=_number(point["x_m"], "point.x_m"), y_m=_number(point["y_m"], "point.y_m")),
        timestamp=sample.timestamp,
        provenance=Provenance(source=f"sensor:{sample.sensor_id}", detail=detail),
        confidence=confidence,
        mission_id=mission_id,
    )


class EnvironmentObservationIngestService(Service):
    """Publishes typed OBSERVED events only from the accepted mock sample schema."""

    name = "environment-observation-ingest"
    depends_on = ("sensor-ingest",)

    def __init__(self) -> None:
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
            return HealthStatus.DEGRADED, f"{self._errors} invalid environment observation sample(s)"
        return HealthStatus.OK, ""

    def _on_sample(self, value: object) -> None:
        if self._ctx is None:
            return
        if not isinstance(value, SensorSample):
            self._errors += 1
            log.error("environment observation ingress received a non-SensorSample value")
            return
        try:
            observation = _from_sensor_sample(value)
        except (OverflowError, TypeError, ValueError) as exc:
            self._errors += 1
            log.warning("invalid environment observation from sensor %s: %s", value.sensor_id, exc)
            return
        if observation is not None:
            self._ctx.bus.publish(ENVIRONMENT_OBSERVATION, observation)


class EnvironmentKnowledgeService(Service):
    """Records typed environment observations delivered over the event bus."""

    name = "environment-knowledge"
    depends_on = ("environment-observation-ingest",)

    def __init__(self, knowledge: EnvironmentKnowledge) -> None:
        self._knowledge = knowledge
        self._ctx: ServiceContext | None = None
        self._errors = 0

    def start(self, ctx: ServiceContext) -> None:
        self._ctx = ctx
        ctx.bus.subscribe(ENVIRONMENT_OBSERVATION, self._on_observation)

    def stop(self) -> None:
        if self._ctx is not None:
            self._ctx.bus.unsubscribe(ENVIRONMENT_OBSERVATION, self._on_observation)
        self._ctx = None

    def health_detail(self) -> tuple[HealthStatus, str]:
        if self._errors:
            return HealthStatus.DEGRADED, f"{self._errors} environment observation record error(s)"
        return HealthStatus.OK, ""

    def _on_observation(self, value: object) -> None:
        if not isinstance(value, EnvironmentObservation):
            self._errors += 1
            log.error("environment knowledge received a non-EnvironmentObservation value")
            return
        self._knowledge.record(value)
