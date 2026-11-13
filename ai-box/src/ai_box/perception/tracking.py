"""Obstacle tracking interface across frames. STATUS: OPEN (no tracker chosen yet).

The foundation build assigns frame-local identifiers only. Stable cross-frame
identity is required before collision-risk estimation is meaningful.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from marine_contracts import ObstacleTrack

from ai_box.perception.frames import PerceptionFrame


class ObstacleTracker(Protocol):
    def update(self, frame: PerceptionFrame) -> Sequence[ObstacleTrack]: ...
