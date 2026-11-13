"""Mock sensor and position adapters for tests and offline development."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable, Sequence

from ai_box.core.ports import SensorSample
from ai_box.motion.commands import VehicleState


class MockSensorAdapter:
    """Replays scripted batches of samples, one batch per poll()."""

    def __init__(self, sensor_id: str, batches: Iterable[Sequence[SensorSample]] = ()) -> None:
        self._sensor_id = sensor_id
        self._batches: deque[Sequence[SensorSample]] = deque(batches)

    @property
    def sensor_id(self) -> str:
        return self._sensor_id

    def poll(self) -> Sequence[SensorSample]:
        return self._batches.popleft() if self._batches else ()


class MockPositionSource:
    """Holds whatever state a test sets. Returns None until set."""

    def __init__(self) -> None:
        self._state: VehicleState | None = None

    def set_state(self, state: VehicleState | None) -> None:
        self._state = state

    def current_state(self) -> VehicleState | None:
        return self._state
