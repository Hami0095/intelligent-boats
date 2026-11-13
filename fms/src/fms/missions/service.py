"""Creates FMS -> boat commands and queues them until the boat acknowledges them."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from marine_contracts import (
    Envelope,
    MessageType,
    MissionAssignmentPayload,
    MissionCancellationPayload,
    SafeStateAction,
    SafeStateCommandPayload,
    make_envelope,
)

from fms.communication.outbox import Outbox
from fms.core.fleet import FleetRegistry


class MissionService:
    def __init__(self, registry: FleetRegistry, outbox: Outbox) -> None:
        self._registry = registry
        self._outbox = outbox

    def assign(self, boat_id: str, mission_id: str, payload: MissionAssignmentPayload) -> Envelope:
        return self._queue(
            boat_id,
            MessageType.MISSION_ASSIGNMENT,
            payload,
            mission_id=mission_id,
        )

    def cancel(self, boat_id: str, mission_id: str, reason: str) -> Envelope:
        return self._queue(
            boat_id,
            MessageType.MISSION_CANCELLATION,
            MissionCancellationPayload(reason=reason),
            mission_id=mission_id,
        )

    def safe_state(self, boat_id: str, action: SafeStateAction, reason: str = "") -> Envelope:
        return self._queue(
            boat_id,
            MessageType.SAFE_STATE_COMMAND,
            SafeStateCommandPayload(action=action, reason=reason),
            mission_id=None,
        )

    def _queue(self, boat_id, message_type, payload, *, mission_id) -> Envelope:
        self._registry.require(boat_id)
        envelope = make_envelope(
            boat_id=boat_id,
            message_type=message_type,
            payload=payload,
            mission_id=mission_id,
            sequence_number=self._outbox.next_sequence(boat_id),
            timestamp=datetime.now(timezone.utc),
            message_id=uuid4(),
        )
        self._outbox.enqueue(envelope)
        return envelope
