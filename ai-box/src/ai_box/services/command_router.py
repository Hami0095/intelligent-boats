"""Handles commands from the FMS and answers each critical one with an acknowledgement.

Commands the foundation does not implement are REJECTED explicitly, with a reason,
rather than silently accepted. Acceptance of a command means it has taken effect.
"""

from __future__ import annotations

import logging

from marine_contracts import (
    AcknowledgementPayload,
    Envelope,
    MessageType,
    MissionAssignmentPayload,
    MissionCancellationPayload,
    MissionProgressPayload,
    MissionStatus,
    OperatingMode,
    OperationalEventPayload,
    SafeStateAction,
    SafeStateCommandPayload,
    Severity,
)

from ai_box.core.events import FMS_INBOUND, FMS_OUTBOUND, Outbound
from ai_box.core.service import Service, ServiceContext
from ai_box.core.state import OperatingState
from ai_box.decision.mission import SearchMissionService
from ai_box.motion.service import MotionFault, MotionService

log = logging.getLogger("ai_box.commands")

NOT_IMPLEMENTED_NAV = "geo-to-local localisation is not implemented (OPEN)"
NOT_IMPLEMENTED_CONFIG = "configuration updates are not implemented in the foundation build"
NOT_IMPLEMENTED_RETURN = "return-home behaviour is not implemented"


class CommandRouter(Service):
    name = "command-router"
    depends_on = ("motion", "search-mission", "fms-bridge")

    def __init__(
        self,
        *,
        missions: SearchMissionService,
        motion: MotionService,
        operating: OperatingState,
    ) -> None:
        self._missions = missions
        self._motion = motion
        self._operating = operating
        self._ctx: ServiceContext | None = None

    def start(self, ctx: ServiceContext) -> None:
        self._ctx = ctx
        ctx.bus.subscribe(FMS_INBOUND, self._on_inbound)

    def stop(self) -> None:
        if self._ctx is not None:
            self._ctx.bus.unsubscribe(FMS_INBOUND, self._on_inbound)
        self._ctx = None

    def _on_inbound(self, envelope: Envelope) -> None:
        if self._ctx is None or envelope.message_type is MessageType.ACKNOWLEDGEMENT:
            return
        payload = envelope.typed_payload()
        if envelope.message_type is MessageType.MISSION_ASSIGNMENT:
            if not isinstance(payload, MissionAssignmentPayload):
                raise TypeError(f"expected MissionAssignmentPayload, got {type(payload).__name__}")
            assert envelope.mission_id is not None
            reason = self._missions.assign(envelope.mission_id, payload.search_area_id)
            if reason is None:
                self._operating.set_mode(OperatingMode.AUTONOMOUS)
                self._ack(envelope, accepted=True)
                self._progress(envelope.mission_id, MissionStatus.ACCEPTED, "")
            else:
                self._ack(envelope, accepted=False, reason=reason)
                self._progress(envelope.mission_id, MissionStatus.REJECTED, reason)
        elif envelope.message_type is MessageType.MISSION_CANCELLATION:
            if not isinstance(payload, MissionCancellationPayload):
                raise TypeError(f"expected MissionCancellationPayload, got {type(payload).__name__}")
            assert envelope.mission_id is not None
            try:
                cancelled = self._missions.cancel(envelope.mission_id)
            except MotionFault as exc:
                reason = f"mission cancelled locally; zero command failed: {exc}"[:512]
                self._ack(envelope, accepted=False, reason=reason)
                self._progress(envelope.mission_id, MissionStatus.ABORTED, reason)
                return
            if cancelled:
                self._operating.set_mode(OperatingMode.IDLE)
                self._ack(envelope, accepted=True)
                self._progress(envelope.mission_id, MissionStatus.ABORTED, payload.reason)
            else:
                self._ack(envelope, accepted=False, reason="no matching active mission")
        elif envelope.message_type is MessageType.NAVIGATION_GOAL:
            self._ack(envelope, accepted=False, reason=NOT_IMPLEMENTED_NAV)
        elif envelope.message_type is MessageType.SAFE_STATE_COMMAND:
            if not isinstance(payload, SafeStateCommandPayload):
                raise TypeError(f"expected SafeStateCommandPayload, got {type(payload).__name__}")
            if payload.action is SafeStateAction.RETURN_HOME:
                self._ack(envelope, accepted=False, reason=NOT_IMPLEMENTED_RETURN)
                return
            self._operating.set_mode(OperatingMode.SAFE_STATE)
            self._motion.inhibit()
            active = self._missions.active_mission
            matches_active = active is not None and active.mission_id == envelope.mission_id
            try:
                cancelled = envelope.mission_id is not None and self._missions.cancel(envelope.mission_id)
                if not cancelled:
                    self._motion.safe_stop()
            except MotionFault as exc:
                detail = "mission cancelled locally; " if matches_active else ""
                self._ack(envelope, accepted=False, reason=f"{detail}zero command failed: {exc}"[:512])
            else:
                self._ack(envelope, accepted=True)
        elif envelope.message_type is MessageType.CONFIGURATION_UPDATE:
            self._ack(envelope, accepted=False, reason=NOT_IMPLEMENTED_CONFIG)
        else:  # pragma: no cover - the registry guarantees exhaustive handling
            log.error("unhandled inbound message type %s", envelope.message_type.value)

    def _ack(self, envelope: Envelope, *, accepted: bool, reason: str | None = None) -> None:
        assert self._ctx is not None
        self._ctx.bus.publish(
            FMS_OUTBOUND,
            Outbound(
                message_type=MessageType.ACKNOWLEDGEMENT,
                payload=AcknowledgementPayload(
                    acknowledged_message_id=envelope.message_id,
                    accepted=accepted,
                    reason=reason,
                ),
                mission_id=envelope.mission_id,
            ),
        )

    def _progress(self, mission_id: str, status: MissionStatus, detail: str) -> None:
        assert self._ctx is not None
        self._ctx.bus.publish(
            FMS_OUTBOUND,
            Outbound(
                message_type=MessageType.MISSION_PROGRESS,
                payload=MissionProgressPayload(status=status, detail=detail[:1024]),
                mission_id=mission_id,
            ),
        )

    def publish_event(self, severity: Severity, code: str, message: str) -> None:
        if self._ctx is None:
            return
        self._ctx.bus.publish(
            FMS_OUTBOUND,
            Outbound(
                message_type=MessageType.OPERATIONAL_EVENT,
                payload=OperationalEventPayload(severity=severity, code=code, message=message),
            ),
        )
