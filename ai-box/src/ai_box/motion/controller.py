"""Motion control interface.

Only the safe default controller exists in the foundation. It never moves.
A real navigation controller is intentionally not implemented here.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from ai_box.motion.commands import NavigationGoal, PropulsionCommand, VehicleState


class MotionController(Protocol):
    def compute(
        self,
        goal: NavigationGoal | None,
        state: VehicleState | None,
        now: datetime,
    ) -> PropulsionCommand: ...


class HoldPositionController:
    """Safe default: zero thrust and zero rudder regardless of goal."""

    def compute(
        self,
        goal: NavigationGoal | None,
        state: VehicleState | None,
        now: datetime,
    ) -> PropulsionCommand:
        return PropulsionCommand.stop(now)
