"""In-process event bus and the topic names used between AI Box services.

Handler exceptions are logged and isolated so one faulty subscriber cannot stop
the others. Escalation policy for safety-relevant handlers is an OPEN decision.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from marine_contracts import MessageType
from pydantic import BaseModel

log = logging.getLogger("ai_box.events")

SENSOR_SAMPLE = "sensor.sample"
PERCEPTION_FRAME = "perception.frame"
TELEMETRY_BOAT_STATE = "telemetry.boat_state"
FMS_OUTBOUND = "fms.outbound"
FMS_INBOUND = "fms.inbound"

Handler = Callable[[Any], None]


@dataclass(frozen=True)
class Outbound:
    """A boat -> FMS message awaiting envelope creation. Only the FMS bridge sends these."""

    message_type: MessageType
    payload: BaseModel
    mission_id: str | None = None


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = defaultdict(list)

    def subscribe(self, topic: str, handler: Handler) -> None:
        self._handlers[topic].append(handler)

    def unsubscribe(self, topic: str, handler: Handler) -> None:
        handlers = self._handlers.get(topic, [])
        if handler in handlers:
            handlers.remove(handler)

    def publish(self, topic: str, event: Any) -> int:
        """Deliver to every subscriber. Returns the number of handlers that completed without error."""
        delivered = 0
        for handler in list(self._handlers.get(topic, [])):
            try:
                handler(event)
            except Exception:
                log.exception("handler failed on topic %s", topic)
            else:
                delivered += 1
        return delivered
