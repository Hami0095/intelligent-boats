"""Environment observations: the raw facts the knowledge base is built from."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from marine_contracts import Provenance
from marine_contracts.common import require_utc

from ai_box.core.geometry import LocalPoint


class ObservationKind(str, Enum):
    VISITED = "visited"  # the boat was at this point
    SEARCHED = "searched"  # a search sensor covered this point (sensor coverage model is OPEN)
    OBSERVED = "observed"  # something of interest was seen here; does not change search status


@dataclass(frozen=True)
class EnvironmentObservation:
    kind: ObservationKind
    point: LocalPoint
    timestamp: datetime
    provenance: Provenance
    confidence: float
    mission_id: str | None = None

    def __post_init__(self) -> None:
        require_utc(self.timestamp)
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be within [0, 1]")
