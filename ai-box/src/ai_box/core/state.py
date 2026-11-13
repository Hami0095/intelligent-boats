"""Small shared state: the boat's current operating mode."""

from __future__ import annotations

from marine_contracts import OperatingMode


class OperatingState:
    def __init__(self, mode: OperatingMode = OperatingMode.IDLE) -> None:
        self._mode = mode

    @property
    def mode(self) -> OperatingMode:
        return self._mode

    def set_mode(self, mode: OperatingMode) -> None:
        self._mode = mode
