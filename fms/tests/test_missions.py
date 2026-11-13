from datetime import datetime, timezone

import pytest

from fms.communication.outbox import Outbox, OutboxFullError
from fms.core.fleet import BoatIdentity, FleetRegistry, UnregisteredBoatError
from fms.missions.service import MissionService
from marine_contracts import MessageType, MissionAssignmentPayload, SafeStateAction


def _service(limit=10):
    registry = FleetRegistry()
    registry.register(BoatIdentity(boat_id="boat-01", display_name="Alpha"))
    outbox = Outbox(limit_per_boat=limit)
    return MissionService(registry, outbox), outbox


def test_assignment_is_queued_with_increasing_sequence_numbers():
    missions, outbox = _service()
    payload = MissionAssignmentPayload(objective="search", search_area_id="area-1")
    first = missions.assign("boat-01", "m-1", payload)
    second = missions.safe_state("boat-01", SafeStateAction.HOLD_POSITION)
    assert first.message_type is MessageType.MISSION_ASSIGNMENT
    assert first.mission_id == "m-1"
    assert (first.sequence_number, second.sequence_number) == (0, 1)
    assert outbox.unacknowledged("boat-01") == (first, second)


def test_commands_cannot_target_unregistered_boats():
    missions, outbox = _service()
    with pytest.raises(UnregisteredBoatError):
        missions.cancel("boat-99", "m-1", "test")
    assert outbox.unacknowledged("boat-99") == ()


def test_full_outbox_refuses_rather_than_dropping_commands():
    missions, _ = _service(limit=1)
    missions.safe_state("boat-01", SafeStateAction.STOP_PROPULSION)
    with pytest.raises(OutboxFullError):
        missions.safe_state("boat-01", SafeStateAction.STOP_PROPULSION)


def test_unacknowledged_commands_are_offered_again_after_reconnection():
    missions, outbox = _service()
    command = missions.cancel("boat-01", "m-1", "operator request")
    assert command in outbox.unacknowledged("boat-01")  # still there after a dropped link
    assert outbox.acknowledge("boat-01", command.message_id) is True
    assert outbox.unacknowledged("boat-01") == ()


def test_outbox_rejects_non_positive_limits():
    with pytest.raises(ValueError):
        Outbox(limit_per_boat=0)
