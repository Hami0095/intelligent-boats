"""Polls sensor adapters and publishes their samples on the bus."""

from __future__ import annotations

import logging
from collections.abc import Sequence

from marine_contracts import HealthStatus

from ai_box.core.events import SENSOR_SAMPLE
from ai_box.core.ports import SensorSource
from ai_box.core.service import Service, ServiceContext

log = logging.getLogger("ai_box.sensors")


class SensorIngestService(Service):
    name = "sensor-ingest"

    def __init__(self, sources: Sequence[SensorSource]) -> None:
        self._sources = list(sources)
        self._ctx: ServiceContext | None = None
        self._poll_errors = 0

    def start(self, ctx: ServiceContext) -> None:
        self._ctx = ctx

    def stop(self) -> None:
        self._ctx = None

    def tick(self) -> None:
        if self._ctx is None:
            return
        for source in self._sources:
            try:
                samples = source.poll()
            except Exception:
                self._poll_errors += 1
                log.exception("sensor %s poll failed", source.sensor_id)
                continue
            for sample in samples:
                self._ctx.bus.publish(SENSOR_SAMPLE, sample)

    def health_detail(self) -> tuple[HealthStatus, str]:
        if self._poll_errors:
            return HealthStatus.DEGRADED, f"{self._poll_errors} sensor poll error(s)"
        return HealthStatus.OK, ""
