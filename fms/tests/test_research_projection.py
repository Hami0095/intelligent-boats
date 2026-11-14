"""The research read model returns only actual received data."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fms.communication.outbox import Outbox
from fms.core.endpoint import FmsEndpoint
from fms.core.fleet import BoatIdentity, FleetRegistry
from fms.data.research import ResearchFleet
from fms.data.store import InMemoryFleetStore
from fms.logging.audit import AuditLog
from marine_contracts import BoatStatePayload, Envelope, MessageType, OperatingMode, make_envelope

NOW = datetime(2026, 11, 15, tzinfo=timezone.utc)


@pytest.fixture
def fleet() -> ResearchFleet:
    registry, store = FleetRegistry(), InMemoryFleetStore()
    for boat_id in ("mock-01", "mock-02"):
        registry.register(BoatIdentity(boat_id, boat_id))
    endpoint = FmsEndpoint(registry=registry, store=store, audit=AuditLog(), outbox=Outbox(10), clock=lambda: NOW)
    return ResearchFleet(registry=registry, store=store, endpoint=endpoint)


def state(boat_id: str, sequence: int) -> Envelope:
    return make_envelope(
        boat_id=boat_id,
        message_type=MessageType.BOAT_STATE,
        sequence_number=sequence,
        payload=BoatStatePayload(operating_mode=OperatingMode.IDLE),
        timestamp=NOW,
    )


def test_registered_identity_alone_creates_no_telemetry(fleet: ResearchFleet) -> None:
    assert fleet.snapshots() == []
    assert fleet.snapshot("mock-01")["last_received_at"] is None
    assert all(value is None for value in fleet.snapshot("mock-01")["messages"].values())
    with pytest.raises(LookupError):
        fleet.snapshot("unknown")


def test_latest_received_envelope_and_unknown_position_are_preserved(fleet: ResearchFleet) -> None:
    original = state("mock-01", 0)
    fleet.receive(original)
    latest = state("mock-01", 1)
    fleet.receive(latest)
    report = fleet.snapshot("mock-01")["messages"]["boat.state"]
    assert report == {"envelope": latest.model_dump(mode="json"), "received_at": NOW.isoformat()}
    assert report["envelope"]["payload"]["position"] is None
    assert len(fleet.snapshots()) == 1


def test_receiving_another_boat_does_not_replace_the_first(fleet: ResearchFleet) -> None:
    fleet.receive(state("mock-01", 0))
    first = fleet.snapshot("mock-01")
    fleet.receive(state("mock-02", 0))
    assert fleet.snapshot("mock-01") == first
    assert [boat["boat_id"] for boat in fleet.snapshots()] == ["mock-01", "mock-02"]
