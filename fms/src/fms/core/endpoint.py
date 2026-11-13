"""Inbound endpoint: validates, de-duplicates, stores and acknowledges boat messages.

Transport-independent: callers hand over already-parsed Envelope objects. Decoding
raw bytes and moving them over a network is the adapter's job (adapters/fms).
"""

from __future__ import annotations

import logging
from collections import OrderedDict, defaultdict
from collections.abc import Callable
from datetime import datetime, timezone
from uuid import UUID

from marine_contracts import (
    MESSAGE_SPECS,
    AcknowledgementPayload,
    Direction,
    Envelope,
    MessageType,
    make_envelope,
)

from fms.communication.outbox import Outbox
from fms.core.fleet import FleetRegistry
from fms.data.store import InMemoryFleetStore
from fms.logging.audit import AuditLog

log = logging.getLogger("fms.endpoint")


class FmsEndpoint:
    def __init__(
        self,
        *,
        registry: FleetRegistry,
        store: InMemoryFleetStore,
        audit: AuditLog,
        outbox: Outbox,
        dedupe_window: int = 10_000,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._registry = registry
        self._store = store
        self._audit = audit
        self._outbox = outbox
        self._clock = clock
        self._window = dedupe_window
        self._seen: dict[str, OrderedDict[UUID, None]] = defaultdict(OrderedDict)
        self._last_sequence: dict[str, int] = {}

    def receive(self, envelope: Envelope) -> list[Envelope]:
        """Process one boat message. Returns the replies the FMS sends back to that boat."""
        boat_id = envelope.boat_id
        self._registry.require(boat_id)  # raises UnregisteredBoatError

        if envelope.message_type is MessageType.ACKNOWLEDGEMENT:
            return self._handle_ack(envelope)

        if MESSAGE_SPECS[envelope.message_type].direction is not Direction.BOAT_TO_FMS:
            self._audit.record(
                self._clock(), "rejected", boat_id, f"{envelope.message_type.value} is not a boat-originated message"
            )
            return []

        seen = self._seen[boat_id]
        if envelope.message_id in seen:
            self._audit.record(self._clock(), "duplicate", boat_id, str(envelope.message_id))
            return []
        seen[envelope.message_id] = None
        while len(seen) > self._window:
            seen.popitem(last=False)

        last = self._last_sequence.get(boat_id)
        if last is not None and envelope.sequence_number <= last:
            self._audit.record(
                self._clock(), "out_of_order", boat_id, f"sequence {envelope.sequence_number} after {last}"
            )
        self._last_sequence[boat_id] = max(envelope.sequence_number, last or 0)

        now = self._clock()
        self._store.record(envelope, received_at=now)

        if MESSAGE_SPECS[envelope.message_type].critical:
            return [self._acknowledge(envelope)]
        return []

    def _handle_ack(self, envelope: Envelope) -> list[Envelope]:
        payload = envelope.typed_payload()
        assert isinstance(payload, AcknowledgementPayload)
        removed = self._outbox.acknowledge(envelope.boat_id, payload.acknowledged_message_id)
        status = "accepted" if payload.accepted else f"rejected ({payload.reason})"
        self._audit.record(
            self._clock(),
            "ack",
            envelope.boat_id,
            f"{payload.acknowledged_message_id} {status}; queue cleared={removed}",
        )
        return []

    def _acknowledge(self, envelope: Envelope) -> Envelope:
        return make_envelope(
            boat_id=envelope.boat_id,
            message_type=MessageType.ACKNOWLEDGEMENT,
            payload=AcknowledgementPayload(acknowledged_message_id=envelope.message_id, accepted=True),
            mission_id=envelope.mission_id,
            sequence_number=self._outbox.next_sequence(envelope.boat_id),
            timestamp=self._clock(),
        )
