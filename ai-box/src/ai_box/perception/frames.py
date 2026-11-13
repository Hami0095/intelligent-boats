"""Perception output for one sensor sample."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ai_box.core.ports import Detection


@dataclass(frozen=True)
class PerceptionFrame:
    sensor_id: str
    timestamp: datetime
    detections: tuple[Detection, ...]
