"""Placeholder Isaac Sim adapter.

Implements the AI Box sensor and propulsion ports by shape, but every method raises
NotImplementedError. It exists so the integration boundary is visible and tested
before the simulator is connected. It imports NO simulator code.
"""

from __future__ import annotations

from collections.abc import Sequence

from ai_box.core.ports import SensorSample
from ai_box.motion.commands import PropulsionCommand

_MESSAGE = "Isaac Sim integration is not implemented yet (see docs/INTEGRATION_GUIDE.md)"


class IsaacSimAdapter:
    def __init__(self, sensor_id: str) -> None:
        self._sensor_id = sensor_id

    @property
    def sensor_id(self) -> str:
        return self._sensor_id

    def poll(self) -> Sequence[SensorSample]:
        raise NotImplementedError(_MESSAGE)

    def apply(self, command: PropulsionCommand) -> None:
        raise NotImplementedError(_MESSAGE)
