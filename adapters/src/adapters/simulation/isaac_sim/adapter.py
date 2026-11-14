"""Isaac Sim adapter for the AI Box sensor, position and propulsion ports.

The adapter forwards to a `SimulatorBackend`. With no backend connected, every call
raises `SimulatorUnavailableError`. The AI Box then reports the sensor as degraded and
keeps running. The adapter imports no simulator code itself.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime, timezone

from ai_box.core.geometry import LocalPoint
from ai_box.core.ports import SensorKind, SensorSample
from ai_box.motion.commands import PropulsionCommand, VehicleState

from adapters.simulation.isaac_sim.backend import SimulatorBackend, SimulatorUnavailableError


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class IsaacSimAdapter:
    def __init__(
        self,
        sensor_id: str,
        backend: SimulatorBackend | None = None,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._sensor_id = sensor_id
        self._backend = backend
        self._clock = clock
        self._state: VehicleState | None = None

    @property
    def sensor_id(self) -> str:
        return self._sensor_id

    @property
    def is_available(self) -> bool:
        return self._backend is not None

    def poll(self) -> Sequence[SensorSample]:
        """Read the boat pose from the simulator as one POSITION_FIX sample."""
        pose = self._require_backend().read_pose()
        now = self._clock()
        heading = pose.heading_deg % 360.0
        self._state = VehicleState(
            timestamp=now,
            local_position=LocalPoint(x_m=pose.x_m, y_m=pose.y_m),
            heading_deg=heading,
            speed_over_ground_mps=pose.speed_mps,
        )
        sample = SensorSample(
            sensor_id=self._sensor_id,
            kind=SensorKind.POSITION_FIX,
            timestamp=now,
            data={
                "x_m": pose.x_m,
                "y_m": pose.y_m,
                "heading_deg": heading,
                "speed_mps": pose.speed_mps,
            },
        )
        return (sample,)

    def current_state(self) -> VehicleState | None:
        """Latest pose read by poll(). None until the first successful poll."""
        return self._state

    def apply(self, command: PropulsionCommand) -> None:
        self._require_backend().write_command(command.thrust, command.rudder)

    def _require_backend(self) -> SimulatorBackend:
        if self._backend is None:
            raise SimulatorUnavailableError("Isaac Sim backend is not connected")
        return self._backend
