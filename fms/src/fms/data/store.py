"""In-memory store of boat-originated messages, indexed by boat and message type."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from marine_contracts import Envelope, MessageType


@dataclass(frozen=True)
class ReceivedMessage:
    envelope: Envelope
    received_at: datetime

    @property
    def payload(self) -> Any:
        return self.envelope.typed_payload()


class InMemoryFleetStore:
    def __init__(self) -> None:
        self._history: dict[tuple[str, MessageType], list[ReceivedMessage]] = {}

    def record(self, envelope: Envelope, received_at: datetime) -> None:
        key = (envelope.boat_id, envelope.message_type)
        self._history.setdefault(key, []).append(ReceivedMessage(envelope, received_at))

    def history(self, boat_id: str, message_type: MessageType) -> tuple[ReceivedMessage, ...]:
        return tuple(self._history.get((boat_id, message_type), ()))

    def latest(self, boat_id: str, message_type: MessageType) -> ReceivedMessage | None:
        items = self._history.get((boat_id, message_type))
        return items[-1] if items else None
