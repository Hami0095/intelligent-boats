"""Motion service: turns the current goal and vehicle state into propulsion commands."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timezone

from marine_contracts import HealthStatus
from marine_contracts.common import require_utc

from ai_box.core.ports import PositionSource, PropulsionSink
from ai_box.core.service import Service, ServiceContext
from ai_box.motion.commands import NavigationGoal, PropulsionCommand
from ai_box.motion.controller import MotionController

log = logging.getLogger("ai_box.motion")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MotionFault(RuntimeError):
    """Motion is inhibited; a command or its required input could not be trusted."""


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
        self._inhibited = False
        self._fault_detail = ""
        self._last_valid_time: datetime | None = None
        self.last_command: PropulsionCommand | None = None

    @property
    def goal(self) -> NavigationGoal | None:
        return self._goal

    @property
    def inhibited(self) -> bool:
        return self._inhibited

    def inhibit(self) -> None:
        """Latch inhibition without I/O. Only a new instance starts uninhibited."""
        self._inhibited = True

    def set_goal(self, goal: NavigationGoal | None) -> None:
        self._goal = goal
        if goal is None:
            self._stop_now()

    def start(self, ctx: ServiceContext) -> None:
        return None

    def tick(self) -> None:
        if self._inhibited:
            self._stop_now()
            return
        now: datetime | None = None
        zero_attempted = False
        try:
            now = self._read_time()
            if self._inhibited:
                zero_attempted = True
                self._apply(PropulsionCommand.stop(now))
                return
            state = self._position.current_state()
            if self._inhibited:
                zero_attempted = True
                self._apply(PropulsionCommand.stop(now))
                return
            command = self._controller.compute(self._goal, state, now)
            if not isinstance(command, PropulsionCommand):
                raise TypeError("controller must return a PropulsionCommand")
            if self._inhibited:
                command = PropulsionCommand.stop(now)
            zero_attempted = command.thrust == 0.0 and command.rudder == 0.0
            self._apply(command)
        except Exception as exc:
            raise self._fail_and_stop(exc, now, attempt_zero=not zero_attempted) from exc

    def safe_stop(self) -> None:
        """Inhibit before fallible work, drop the goal and attempt zero once."""
        self.inhibit()
        self._goal = None
        self._stop_now()
        log.info("safe stop commanded")

    def stop(self) -> None:
        self.safe_stop()

    def health_detail(self) -> tuple[HealthStatus, str]:
        if self._fault_detail:
            return HealthStatus.DEGRADED, self._fault_detail[:512]
        return HealthStatus.OK, "motion inhibited; fresh runtime required" if self._inhibited else ""

    def _read_time(self) -> datetime:
        now = self._clock()
        if not isinstance(now, datetime):
            raise ValueError("motion clock must return a timezone-aware datetime")
        require_utc(now)
        self._last_valid_time = now
        return now

    def _apply(self, command: PropulsionCommand) -> None:
        self._sink.apply(command)
        # A raised apply() does not establish delivery or replace this record.
        self.last_command = command

    def _stop_now(self) -> None:
        try:
            now = self._read_time()
        except Exception as exc:
            raise self._fail_and_stop(exc, None) from exc
        try:
            self._apply(PropulsionCommand.stop(now))
        except Exception as exc:
            # This event has already attempted zero. Do not retry internally.
            self.inhibit()
            self._goal = None
            self._fault_detail = f"zero command delivery failed: {type(exc).__name__}: {exc}"
            log.error("%s", self._fault_detail)
            raise MotionFault(self._fault_detail) from exc

    def _fail_and_stop(self, exc: Exception, now: datetime | None, *, attempt_zero: bool = True) -> MotionFault:
        self.inhibit()
        self._goal = None
        self._fault_detail = f"{type(exc).__name__}: {exc}"
        if not attempt_zero:
            self._fault_detail = f"zero command delivery failed: {self._fault_detail}"
        if now is None:
            now = self._last_valid_time
            if now is None:
                self._fault_detail += "; no validated timestamp available for zero command"
            else:
                self._fault_detail += "; emergency zero uses last validated timestamp (not fresh)"
        if now is not None and attempt_zero:
            try:
                self._apply(PropulsionCommand.stop(now))
            except Exception as stop_exc:
                self._fault_detail += f"; zero command delivery failed: {type(stop_exc).__name__}: {stop_exc}"
        log.error("%s", self._fault_detail)
        return MotionFault(self._fault_detail)
