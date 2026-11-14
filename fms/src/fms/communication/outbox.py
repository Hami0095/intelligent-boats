"""Per-boat queue of FMS -> boat messages awaiting acknowledgement.

Commands are never silently dropped. When a boat's queue is full, enqueueing
fails loudly so the caller can react. Unacknowledged messages are re-offered on
reconnection (see unacknowledged()).
"""

from __future__ import annotations

from collections import defaultdict
from uuid import UUID

from marine_contracts import Envelope


class OutboxFullError(RuntimeError):
    pass


class Outbox:
    def __init__(self, limit_per_boat: int) -> None:
        if limit_per_boat <= 0:
            raise ValueError("limit_per_boat must be positive")
        self._limit = limit_per_boat
        self._pending: dict[str, dict[UUID, Envelope]] = defaultdict(dict)
        self._sequence: dict[str, int] = defaultdict(int)

    def next_sequence(self, boat_id: str) -> int:
        value = self._sequence[boat_id]
        self._sequence[boat_id] += 1
        return value

    def enqueue(self, envelope: Envelope) -> None:
        queue = self._pending[envelope.boat_id]
        existing = queue.get(envelope.message_id)
        if existing is not None:
            if existing != envelope:
                raise ValueError(
                    f"message_id {envelope.message_id} is already queued for {envelope.boat_id!r} "
                    "with a different envelope"
                )
            return
        if len(queue) >= self._limit:
            raise OutboxFullError(f"outbox for {envelope.boat_id!r} is full ({self._limit})")
        queue[envelope.message_id] = envelope

    def unacknowledged(self, boat_id: str) -> tuple[Envelope, ...]:
        return tuple(self._pending.get(boat_id, {}).values())

    def acknowledge(self, boat_id: str, message_id: UUID) -> bool:
        return self._pending.get(boat_id, {}).pop(message_id, None) is not None
