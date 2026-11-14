"""Periodic telemetry: boat state each tick, service health every few ticks."""

from __future__ import annotations

from collections.abc import Callable

from marine_contracts import (
    BoatStatePayload,
    EnvironmentProgressPayload,
    MessageType,
    OperatingMode,
    ServiceHealthEntry,
    ServiceHealthPayload,
)
from pydantic import BaseModel

from ai_box.core.events import FMS_OUTBOUND, Outbound
from ai_box.core.ports import PositionSource
from ai_box.core.service import Service, ServiceContext
from ai_box.core.state import OperatingState
from ai_box.motion.commands import VehicleState

HEALTH_EVERY_N_TICKS = 10


def build_boat_state(
    state: VehicleState | None,
    mode: OperatingMode,
    battery_state_of_charge: float | None,
) -> BoatStatePayload:
    if state is None:
        return BoatStatePayload(operating_mode=mode, battery_state_of_charge=battery_state_of_charge)
    return BoatStatePayload(
        operating_mode=mode,
        position=state.geo_position,
        position_uncertainty_m=state.position_uncertainty_m,
        speed_over_ground_mps=state.speed_over_ground_mps,
        heading_deg=state.heading_deg,
        battery_state_of_charge=battery_state_of_charge,
    )


class TelemetryService(Service):
    name = "telemetry"

    def __init__(
        self,
        *,
        position: PositionSource,
        operating: OperatingState,
        health_provider: Callable[[], list[ServiceHealthEntry]],
        progress_provider: Callable[[], tuple[str, EnvironmentProgressPayload] | None] | None = None,
        battery_provider: Callable[[], float | None] | None = None,
    ) -> None:
        self._position = position
        self._operating = operating
        self._health_provider = health_provider
        self._progress_provider = progress_provider
        self._battery_provider = battery_provider
        self._ctx: ServiceContext | None = None
        self._ticks = 0

    def start(self, ctx: ServiceContext) -> None:
        self._ctx = ctx

    def stop(self) -> None:
        self._ctx = None

    def tick(self) -> None:
        if self._ctx is None:
            return
        self._ticks += 1
        battery = self._battery_provider() if self._battery_provider else None
        state_payload = build_boat_state(self._position.current_state(), self._operating.mode, battery)
        self._publish(MessageType.BOAT_STATE, state_payload)

        if self._progress_provider is not None:
            report = self._progress_provider()
            if report is not None:
                mission_id, progress = report
                self._publish(MessageType.ENVIRONMENT_PROGRESS, progress, mission_id=mission_id)

        if self._ticks % HEALTH_EVERY_N_TICKS == 0:
            self._publish(MessageType.SERVICE_HEALTH, ServiceHealthPayload(services=self._health_provider()))

    def _publish(self, message_type: MessageType, payload: BaseModel, mission_id: str | None = None) -> None:
        assert self._ctx is not None
        self._ctx.bus.publish(FMS_OUTBOUND, Outbound(message_type=message_type, payload=payload, mission_id=mission_id))
