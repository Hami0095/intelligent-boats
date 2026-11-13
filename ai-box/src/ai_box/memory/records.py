"""The common record type for all AI Box memories."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from marine_contracts import Provenance
from marine_contracts.common import require_utc


@dataclass(frozen=True)
class MemoryRecord:
    key: str
    value: Any
    timestamp: datetime
    provenance: Provenance
    confidence: float
    mission_id: str | None = None

    def __post_init__(self) -> None:
        require_utc(self.timestamp)
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be within [0, 1]")

    def age_s(self, now: datetime) -> float:
        return (now - self.timestamp).total_seconds()

    def is_stale(self, now: datetime, max_age_s: float) -> bool:
        return self.age_s(now) > max_age_s
