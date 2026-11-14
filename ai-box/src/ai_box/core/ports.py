"""Abstract boundaries between the AI Box and everything outside it.

Concrete devices, simulators and networks implement these Protocols inside
adapters/. Nothing in the AI Box may import a vendor SDK or simulator.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Protocol

from marine_contracts import Envelope
from marine_contracts.common import require_utc

from ai_box.motion.commands import PropulsionCommand, VehicleState


class SensorKind(str, Enum):
    CAMERA_FRAME = "camera_frame"
    RANGE = "range"
    POSITION_FIX = "position_fix"
    MOTION = "motion"
    OTHER = "other"


@dataclass(frozen=True)
class SensorSample:
    """A normalized reading. `SensorKind.OTHER` may carry the mock observation schema documented in DATA_FLOW.md."""

    sensor_id: str
    kind: SensorKind
    timestamp: datetime
    data: Mapping[str, Any]

    def __post_init__(self) -> None:
        require_utc(self.timestamp)


@dataclass(frozen=True)
class Detection:
    """Something the detector believes lies in a sensor's field of view. Not a semantic label."""

    bearing_deg: float
    range_m: float | None
    category: str
    confidence: float

    def __post_init__(self) -> None:
        if not -180.0 <= self.bearing_deg <= 180.0:
            raise ValueError("bearing_deg must be within [-180, 180]")
        if self.range_m is not None and self.range_m < 0.0:
            raise ValueError("range_m must be non-negative")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be within [0, 1]")


class SensorSource(Protocol):
    @property
    def sensor_id(self) -> str: ...

    def poll(self) -> Sequence[SensorSample]:
        """Return samples produced since the last call. Must not block for long."""
        ...


class ObstacleDetector(Protocol):
    def detect(self, sample: SensorSample) -> Sequence[Detection]: ...


class PositionSource(Protocol):
    def current_state(self) -> VehicleState | None:
        """Latest estimate, or None when no estimate exists yet."""
        ...


class PropulsionSink(Protocol):
    def apply(self, command: PropulsionCommand) -> None: ...


class FmsLink(Protocol):
    """Transport-independent link to the FMS. `send` raises ConnectionError while offline."""

    def send(self, envelope: Envelope) -> None: ...

    def receive(self) -> list[Envelope]: ...
