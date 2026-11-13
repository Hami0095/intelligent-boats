"""Value types shared by every payload. Frozen and strict by design."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    """Base class for every contract model: immutable, no unknown fields."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class GeoPosition(StrictModel):
    """WGS-84 position. Only present when a position source provides one.

    Whether the boat has a GPS fix, and how it is fused with IMU/odometry, is
    an OPEN decision (see docs/OPEN_DECISIONS.md). Do not assume it is set.
    """

    latitude_deg: float = Field(ge=-90.0, le=90.0)
    longitude_deg: float = Field(ge=-180.0, le=180.0)


class Provenance(StrictModel):
    """Where a piece of data came from, e.g. 'sensor:front-camera' or 'fms'."""

    source: str = Field(min_length=1, max_length=128)
    detail: str | None = Field(default=None, max_length=512)


class OperatingMode(str, Enum):
    IDLE = "idle"
    AUTONOMOUS = "autonomous"
    SAFE_STATE = "safe_state"
    RETURNING_HOME = "returning_home"
    FAULT = "fault"


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class HealthStatus(str, Enum):
    NOT_STARTED = "not_started"
    OK = "ok"
    DEGRADED = "degraded"
    FAILED = "failed"
    STOPPED = "stopped"


def require_utc(value: datetime) -> datetime:
    """Reject naive datetimes. All contract timestamps must carry a timezone."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamps must be timezone-aware (use UTC)")
    return value
