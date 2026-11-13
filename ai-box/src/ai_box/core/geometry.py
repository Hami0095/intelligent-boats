"""Local Cartesian geometry used inside the AI Box.

The frame origin, axis orientation and the conversion from WGS-84 are an OPEN
decision (docs/OPEN_DECISIONS.md). Until that is settled, the AI Box works in a
local metric frame and never invents a geo<->local transform.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class LocalPoint:
    """A position in the local frame, in metres."""

    x_m: float
    y_m: float

    def distance_to(self, other: LocalPoint) -> float:
        return math.hypot(self.x_m - other.x_m, self.y_m - other.y_m)
