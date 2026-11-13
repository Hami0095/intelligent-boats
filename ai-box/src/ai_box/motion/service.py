"""Motion service: turns the current goal and vehicle state into propulsion commands."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timezone

from ai_box.core.ports import PositionSource, PropulsionSink
from ai_box.core.service import Service, ServiceContext
from ai_box.motion.commands import NavigationGoal, PropulsionCommand
from ai_box.motion.controller import MotionController

log = logging.getLogger("ai_box.motion")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MotionService(Service):
    name = "motion"

    def __init__(
        self,
        position: PositionSource,
        sink: PropulsionSink,
        controller: MotionController,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._position = position
        self._sink = sink
        self._controller = controller
        self._clock = clock
        self._goal: NavigationGoal | None = None
        self.last_command: PropulsionCommand | None = None

    @property
    def goal(self) -> NavigationGoal | None:
        return self._goal

    def set_goal(self, goal: NavigationGoal | None) -> None:
        self._goal = goal

    def start(self, ctx: ServiceContext) -> None:
        return None

    def tick(self) -> None:
        now = self._clock()
        state = self._position.current_state()
        command = self._controller.compute(self._goal, state, now)
        self._sink.apply(command)
        self.last_command = command

    def safe_stop(self) -> None:
        """Drop the goal and command zero propulsion immediately."""
        self._goal = None
        command = PropulsionCommand.stop(self._clock())
        self._sink.apply(command)
        self.last_command = command
        log.info("safe stop commanded")

    def stop(self) -> None:
        self.safe_stop()
