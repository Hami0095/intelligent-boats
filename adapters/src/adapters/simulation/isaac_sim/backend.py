"""The seam between the Isaac Sim adapter and the simulator.

The adapter depends only on the `SimulatorBackend` protocol and the value types here.
Tests use a fake backend. The real backend lives in `isaac_backend.py`, the only
module that imports `isaacsim`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol


class SimulatorUnavailableError(RuntimeError):
    """The simulator is not installed, not connected, or cannot serve this request.

    The AI Box treats this like any other poll or apply failure: the sensor is
    reported as degraded and the boat keeps running.
    """


@dataclass(frozen=True)
class BoatPose:
    """Ground-truth boat pose from the simulator.

    Assumption: the simulator's local metric frame, in metres. The frame origin and
    axis convention are not decided yet (docs/OPEN_DECISIONS.md), and the pose is not
    a modelled sensor reading. Do not treat it as a sensor specification.
    """

    x_m: float
    y_m: float
    heading_deg: float
    speed_mps: float

    def __post_init__(self) -> None:
        for name in ("x_m", "y_m", "heading_deg", "speed_mps"):
            if not math.isfinite(getattr(self, name)):
                raise ValueError(f"{name} must be finite")


class SimulatorBackend(Protocol):
    def read_pose(self) -> BoatPose:
        """Return the current boat pose. Raise SimulatorUnavailableError if unavailable."""
        ...

    def write_command(self, thrust: float, rudder: float) -> None:
        """Apply a normalised command in [-1, 1]. Raise SimulatorUnavailableError if unavailable."""
        ...

    def close(self) -> None:
        """Release the simulator. Safe to call more than once."""
        ...
