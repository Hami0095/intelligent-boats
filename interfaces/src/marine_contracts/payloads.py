"""Typed payload models for every message family.

Boat -> FMS payloads describe what the boat observed or did.
FMS -> Boat payloads describe what the boat is asked to do.
Acknowledgements flow in both directions.

Payloads never contain transport details. Adding a field is a MINOR schema
change; removing or renaming one is a MAJOR change (see interfaces/contracts/README.md).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import Field

from marine_contracts.common import (
    GeoPosition,
    HealthStatus,
    OperatingMode,
    Provenance,
    Severity,
    StrictModel,
)

_CODE_PATTERN = r"^[a-z0-9_.-]+$"


# --------------------------------------------------------------------------- #
# Boat -> FMS
# --------------------------------------------------------------------------- #


class BoatStatePayload(StrictModel):
    """Periodic state telemetry. Every field except operating_mode may be unknown."""

    operating_mode: OperatingMode
    position: GeoPosition | None = None
    position_uncertainty_m: float | None = Field(default=None, ge=0.0)
    speed_over_ground_mps: float | None = Field(default=None, ge=0.0)
    heading_deg: float | None = Field(default=None, ge=0.0, lt=360.0)
    battery_state_of_charge: float | None = Field(default=None, ge=0.0, le=1.0)


class MissionStatus(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABORTED = "aborted"


class MissionProgressPayload(StrictModel):
    status: MissionStatus
    completion_fraction: float | None = Field(default=None, ge=0.0, le=1.0)
    detail: str = Field(default="", max_length=1024)


class ObstacleTrack(StrictModel):
    """One collision-relevant object in the boat's path.

    This is NOT a semantic classification record. `category` is free text for
    logging only; the navigation system must rely on range, bearing and risk.
    `collision_risk` is None until a risk estimator has produced a value.
    """

    track_id: str = Field(min_length=1, max_length=64)
    category: str = Field(default="unspecified", max_length=64)
    relative_bearing_deg: float = Field(ge=-180.0, le=180.0)
    range_m: float | None = Field(default=None, ge=0.0)
    collision_risk: float | None = Field(default=None, ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    provenance: Provenance


class ObstacleSummaryPayload(StrictModel):
    tracks: list[ObstacleTrack] = Field(default_factory=list)


class EnvironmentProgressPayload(StrictModel):
    """Search-progress summary. Region identifiers are opaque to the FMS."""

    searched_region_count: int = Field(ge=0)
    known_region_count: int = Field(ge=0)
    coverage_fraction: float | None = Field(default=None, ge=0.0, le=1.0)
    last_observation_at: datetime | None = None


class OperationalEventPayload(StrictModel):
    severity: Severity
    code: str = Field(min_length=1, max_length=64, pattern=_CODE_PATTERN)
    message: str = Field(max_length=1024)
    context: dict[str, str] = Field(default_factory=dict)


class ServiceHealthEntry(StrictModel):
    name: str = Field(min_length=1, max_length=64)
    status: HealthStatus
    detail: str = Field(default="", max_length=512)


class ServiceHealthPayload(StrictModel):
    services: list[ServiceHealthEntry]


# --------------------------------------------------------------------------- #
# FMS -> Boat
# --------------------------------------------------------------------------- #


class MissionAssignmentPayload(StrictModel):
    """A mission the boat should accept or reject.

    `search_area_id` and `reward_reference` are OPAQUE references. The FMS owns
    the definitions behind them; the reward definition is an OPEN decision.
    """

    objective: str = Field(min_length=1, max_length=1024)
    search_area_id: str = Field(min_length=1, max_length=128)
    time_limit_s: int | None = Field(default=None, gt=0)
    reward_reference: str | None = Field(default=None, max_length=128)


class NavigationGoalPayload(StrictModel):
    goal_id: str = Field(min_length=1, max_length=64)
    target: GeoPosition
    max_speed_mps: float | None = Field(default=None, gt=0.0)
    acceptance_radius_m: float = Field(default=5.0, gt=0.0)


class MissionCancellationPayload(StrictModel):
    reason: str = Field(max_length=512)


class ConfigurationUpdatePayload(StrictModel):
    config_version: str = Field(min_length=1, max_length=64)
    parameters: dict[str, str | int | float | bool] = Field(default_factory=dict)


class SafeStateAction(str, Enum):
    HOLD_POSITION = "hold_position"
    STOP_PROPULSION = "stop_propulsion"
    RETURN_HOME = "return_home"


class SafeStateCommandPayload(StrictModel):
    action: SafeStateAction
    reason: str = Field(default="", max_length=512)


# --------------------------------------------------------------------------- #
# Both directions
# --------------------------------------------------------------------------- #


class AcknowledgementPayload(StrictModel):
    """Confirms receipt (and acceptance) of a critical message."""

    acknowledged_message_id: UUID
    accepted: bool
    reason: str | None = Field(default=None, max_length=512)
