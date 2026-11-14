"""Research API application over the existing in-memory FMS components.

This module contains no HTTP or AI Box implementation. The composition root
passes this application to the transport adapter.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from marine_contracts import MESSAGE_SPECS, Direction, Envelope

from fms.core.endpoint import FmsEndpoint
from fms.core.fleet import FleetRegistry
from fms.data.store import InMemoryFleetStore

BOAT_MESSAGE_TYPES = tuple(
    message_type for message_type, spec in MESSAGE_SPECS.items() if spec.direction is Direction.BOAT_TO_FMS
)


class ResearchFleet:
    """Expose received FMS data without inventing absent vessel information."""

    def __init__(self, *, registry: FleetRegistry, store: InMemoryFleetStore, endpoint: FmsEndpoint) -> None:
        self._registry = registry
        self._store = store
        self._endpoint = endpoint

    def receive(self, envelope: Envelope) -> list[Envelope]:
        return self._endpoint.receive(envelope)

    def snapshots(self) -> list[dict[str, Any]]:
        snapshots = [self.snapshot(identity.boat_id) for identity in self._registry.all()]
        return [snapshot for snapshot in snapshots if snapshot["last_received_at"] is not None]

    def snapshot(self, boat_id: str) -> dict[str, Any]:
        identity = self._registry.require(boat_id)
        messages: dict[str, Any] = {}
        latest: datetime | None = None
        for message_type in BOAT_MESSAGE_TYPES:
            received = self._store.latest(boat_id, message_type)
            messages[message_type.value] = (
                {
                    "envelope": received.envelope.model_dump(mode="json"),
                    "received_at": received.received_at.isoformat(),
                }
                if received is not None
                else None
            )
            if received is not None and (latest is None or received.received_at > latest):
                latest = received.received_at
        return {
            "boat_id": identity.boat_id,
            "display_name": identity.display_name,
            "last_received_at": latest.isoformat() if latest is not None else None,
            "messages": messages,
        }
