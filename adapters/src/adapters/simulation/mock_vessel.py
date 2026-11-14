"""Explicit-step vessel mock for deterministic adapter and integration tests."""

from __future__ import annotations

import math
from datetime import timedelta

from ai_box.core.geometry import LocalPoint
from ai_box.motion.commands import PropulsionCommand, VehicleState


def _finite_number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    return float(value)


class MockVessel:
    """Implements PositionSource and PropulsionSink with synthetic local-frame kinematics.

    Each applied command is consumed by one explicit step. This adapter does not
    schedule itself or model physical vessel dynamics.
    """

    def __init__(
        self,
        initial_state: VehicleState,
        *,
        speed_mps_at_full_thrust: float,
        turn_rate_deg_s_at_full_command: float,
    ) -> None:
        self._state = initial_state
        self._speed_mps_at_full_thrust = _finite_number(speed_mps_at_full_thrust, "speed_mps_at_full_thrust")
        self._turn_rate_deg_s_at_full_command = _finite_number(
            turn_rate_deg_s_at_full_command, "turn_rate_deg_s_at_full_command"
        )
        if self._speed_mps_at_full_thrust <= 0.0:
            raise ValueError("speed_mps_at_full_thrust must be positive")
        if self._turn_rate_deg_s_at_full_command < 0.0:
            raise ValueError("turn_rate_deg_s_at_full_command must be non-negative")
        self._pending_command: PropulsionCommand | None = None

    def current_state(self) -> VehicleState:
        return self._state

    def apply(self, command: PropulsionCommand) -> None:
        self._pending_command = None
        if not isinstance(command, PropulsionCommand):
            raise TypeError("command must be a PropulsionCommand")
        thrust = _finite_number(command.thrust, "thrust")
        rudder = _finite_number(command.rudder, "rudder")
        if not -1.0 <= thrust <= 1.0 or not -1.0 <= rudder <= 1.0:
            raise ValueError("thrust and rudder must be within [-1, 1]")
        self._pending_command = command

    def step(self, duration_s: float) -> VehicleState:
        command, self._pending_command = self._pending_command, None
        step_s = _finite_number(duration_s, "duration_s")
        if step_s <= 0.0:
            raise ValueError("duration_s must be positive")

        state = self._state
        timestamp = state.timestamp + timedelta(seconds=step_s)
        if command is None or (command.thrust == 0.0 and command.rudder == 0.0):
            self._state = VehicleState(
                timestamp=timestamp,
                local_position=state.local_position,
                heading_deg=state.heading_deg,
            )
            return self._state

        position = state.local_position
        heading_deg = state.heading_deg
        if position is None or heading_deg is None:
            raise ValueError("non-zero mock commands require local position and heading")

        x_m = _finite_number(position.x_m, "state.local_position.x_m")
        y_m = _finite_number(position.y_m, "state.local_position.y_m")
        heading_deg = _finite_number(heading_deg, "state.heading_deg")
        turn_delta_deg = command.rudder * abs(command.thrust) * self._turn_rate_deg_s_at_full_command * step_s
        distance_m = command.thrust * self._speed_mps_at_full_thrust * step_s
        if not math.isfinite(turn_delta_deg) or not math.isfinite(distance_m):
            raise ValueError("mock vessel step produced non-finite motion")

        next_heading_deg = (heading_deg + turn_delta_deg) % 360.0
        heading_rad = math.radians(next_heading_deg)
        next_x_m = x_m + distance_m * math.cos(heading_rad)
        next_y_m = y_m + distance_m * math.sin(heading_rad)
        if not math.isfinite(next_x_m) or not math.isfinite(next_y_m):
            raise ValueError("mock vessel step produced a non-finite position")

        self._state = VehicleState(
            timestamp=timestamp,
            local_position=LocalPoint(next_x_m, next_y_m),
            heading_deg=next_heading_deg,
        )
        return self._state
