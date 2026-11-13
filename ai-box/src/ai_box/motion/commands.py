"""Motion value types. Commands are normalised; no motor specifications live here."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from marine_contracts import GeoPosition
from marine_contracts.common import require_utc

from ai_box.core.geometry import LocalPoint


@dataclass(frozen=True)
class VehicleState:
    """Best current estimate of the boat. Every field may be unknown."""

    timestamp: datetime
    local_position: LocalPoint | None = None
    geo_position: GeoPosition | None = None
    position_uncertainty_m: float | None = None
    speed_over_ground_mps: float | None = None
    heading_deg: float | None = None

    def __post_init__(self) -> None:
        require_utc(self.timestamp)
        if self.heading_deg is not None and not 0.0 <= self.heading_deg < 360.0:
            raise ValueError("heading_deg must be within [0, 360)")


@dataclass(frozen=True)
class PropulsionCommand:
    """Normalised command: thrust and rudder both in [-1, 1]."""

    timestamp: datetime
    thrust: float
    rudder: float

    def __post_init__(self) -> None:
        require_utc(self.timestamp)
        if not -1.0 <= self.thrust <= 1.0:
            raise ValueError("thrust must be within [-1, 1]")
        if not -1.0 <= self.rudder <= 1.0:
            raise ValueError("rudder must be within [-1, 1]")

    @classmethod
    def stop(cls, timestamp: datetime) -> PropulsionCommand:
        return cls(timestamp=timestamp, thrust=0.0, rudder=0.0)


@dataclass(frozen=True)
class NavigationGoal:
    goal_id: str
    target: LocalPoint
    acceptance_radius_m: float = 5.0
    max_speed_mps: float | None = None

    def __post_init__(self) -> None:
        if not self.goal_id:
            raise ValueError("goal_id must be non-empty")
        if self.acceptance_radius_m <= 0.0:
            raise ValueError("acceptance_radius_m must be positive")
