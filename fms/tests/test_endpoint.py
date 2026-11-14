from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fms.communication.outbox import Outbox
from fms.core.endpoint import FmsEndpoint
from fms.core.fleet import BoatIdentity, FleetRegistry, UnregisteredBoatError
from fms.data.store import InMemoryFleetStore
from fms.logging.audit import AuditLog
from marine_contracts import (
    AcknowledgementPayload,
    BoatStatePayload,
    MessageType,
    MissionAssignmentPayload,
    MissionProgressPayload,
    MissionStatus,
    OperatingMode,
    make_envelope,
)

NOW = datetime(2026, 2, 1, tzinfo=timezone.utc)


@pytest.fixture
def fms():
    registry = FleetRegistry()
    registry.register(BoatIdentity(boat_id="boat-01", display_name="Alpha"))
    store, audit, outbox = InMemoryFleetStore(), AuditLog(), Outbox(limit_per_boat=10)
    endpoint = FmsEndpoint(
        registry=registry, store=store, audit=audit, outbox=outbox, clock=lambda: NOW, dedupe_window=2
    )
    return registry, store, audit, outbox, endpoint


def _state(seq=0, message_id=None):
    return make_envelope(
        boat_id="boat-01",
        message_type=MessageType.BOAT_STATE,
        payload=BoatStatePayload(operating_mode=OperatingMode.IDLE),
        sequence_number=seq,
        timestamp=NOW,
        message_id=message_id or uuid4(),
    )


def _progress(seq=0):
    return make_envelope(
        boat_id="boat-01",
        message_type=MessageType.MISSION_PROGRESS,
        payload=MissionProgressPayload(status=MissionStatus.ACCEPTED),
        mission_id="m-1",
        sequence_number=seq,
        timestamp=NOW,
    )


def test_identities_must_be_unique_and_required_for_traffic():
    registry = FleetRegistry()
    registry.register(BoatIdentity(boat_id="boat-01", display_name="Alpha"))
    with pytest.raises(ValueError):
        registry.register(BoatIdentity(boat_id="boat-01", display_name="Again"))
    with pytest.raises(UnregisteredBoatError):
        registry.require("boat-02")


@pytest.mark.parametrize("window", [0, -1])
def test_endpoint_rejects_non_positive_dedupe_window(fms, window):
    registry, store, audit, outbox, _ = fms
    with pytest.raises(ValueError, match="dedupe_window must be positive"):
        FmsEndpoint(registry=registry, store=store, audit=audit, outbox=outbox, dedupe_window=window)


def test_unknown_boat_is_refused(fms):
    _, store, _, _, endpoint = fms
    stranger = make_envelope(
        boat_id="boat-09",
        message_type=MessageType.BOAT_STATE,
        payload=BoatStatePayload(operating_mode=OperatingMode.IDLE),
        sequence_number=0,
        timestamp=NOW,
    )
    with pytest.raises(UnregisteredBoatError):
        endpoint.receive(stranger)
    assert store.history("boat-09", MessageType.BOAT_STATE) == ()


def test_telemetry_is_stored_and_not_acknowledged(fms):
    _, store, _, _, endpoint = fms
    replies = endpoint.receive(_state())
    assert replies == []
    assert store.latest("boat-01", MessageType.BOAT_STATE) is not None


def test_critical_boat_messages_are_acknowledged(fms):
    _, _, _, _, endpoint = fms
    progress = _progress()
    replies = endpoint.receive(progress)
    assert len(replies) == 1
    ack = replies[0].typed_payload()
    assert isinstance(ack, AcknowledgementPayload)
    assert ack.acknowledged_message_id == progress.message_id and ack.accepted is True
    assert replies[0].mission_id == "m-1"


def test_duplicate_messages_are_processed_once(fms):
    _, store, audit, _, endpoint = fms
    state = _state()
    endpoint.receive(state)
    assert endpoint.receive(state) == []
    assert len(store.history("boat-01", MessageType.BOAT_STATE)) == 1
    assert any(e.category == "duplicate" for e in audit.entries())


def test_reused_boat_message_id_with_changed_payload_cannot_replace_stored_state(fms):
    _, store, audit, _, endpoint = fms
    original = _state()
    conflicting = make_envelope(
        boat_id="boat-01",
        message_type=MessageType.BOAT_STATE,
        payload=BoatStatePayload(operating_mode=OperatingMode.SAFE_STATE),
        sequence_number=original.sequence_number + 1,
        timestamp=NOW,
        message_id=original.message_id,
    )

    endpoint.receive(original)
    endpoint.receive(conflicting)

    history = store.history("boat-01", MessageType.BOAT_STATE)
    assert len(history) == 1
    assert history[0].payload.operating_mode is OperatingMode.IDLE
    assert any(entry.category == "duplicate" for entry in audit.entries())


def test_duplicate_critical_boat_message_is_not_stored_or_acknowledged_again(fms):
    _, store, audit, _, endpoint = fms
    progress = _progress()

    first_replies = endpoint.receive(progress)
    duplicate_replies = endpoint.receive(progress)

    assert len(first_replies) == 1
    reply_payload = first_replies[0].typed_payload()
    assert isinstance(reply_payload, AcknowledgementPayload)
    assert reply_payload.acknowledged_message_id == progress.message_id
    assert duplicate_replies == []
    history = store.history("boat-01", MessageType.MISSION_PROGRESS)
    assert len(history) == 1 and history[0].envelope == progress
    assert any(entry.category == "duplicate" for entry in audit.entries())


def test_out_of_order_messages_are_kept_and_flagged(fms):
    _, store, audit, _, endpoint = fms
    endpoint.receive(_state(seq=5))
    endpoint.receive(_state(seq=3))
    assert len(store.history("boat-01", MessageType.BOAT_STATE)) == 2
    assert any(e.category == "out_of_order" for e in audit.entries())


def test_boat_cannot_send_fms_originated_commands(fms):
    _, store, audit, _, endpoint = fms
    spoofed = make_envelope(
        boat_id="boat-01",
        message_type=MessageType.MISSION_ASSIGNMENT,
        payload=MissionAssignmentPayload(objective="x", search_area_id="a"),
        mission_id="m-1",
        sequence_number=0,
        timestamp=NOW,
    )
    assert endpoint.receive(spoofed) == []
    assert store.history("boat-01", MessageType.MISSION_ASSIGNMENT) == ()
    assert any(e.category == "rejected" for e in audit.entries())


@pytest.mark.parametrize(("accepted", "reason"), [(True, None), (False, "not supported")])
def test_boat_acknowledgement_clears_the_outbox(fms, accepted, reason):
    _, _, audit, outbox, endpoint = fms
    command = make_envelope(
        boat_id="boat-01",
        message_type=MessageType.MISSION_ASSIGNMENT,
        payload=MissionAssignmentPayload(objective="x", search_area_id="a"),
        mission_id="m-1",
        sequence_number=outbox.next_sequence("boat-01"),
        timestamp=NOW,
    )
    outbox.enqueue(command)
    ack = make_envelope(
        boat_id="boat-01",
        message_type=MessageType.ACKNOWLEDGEMENT,
        payload=AcknowledgementPayload(acknowledged_message_id=command.message_id, accepted=accepted, reason=reason),
        sequence_number=0,
        timestamp=NOW,
    )
    endpoint.receive(ack)
    assert outbox.unacknowledged("boat-01") == ()
    result = next(entry.message for entry in audit.entries() if entry.category == "ack")
    assert str(command.message_id) in result
    assert ("accepted" if accepted else f"rejected ({reason})") in result
    assert "queue cleared=True" in result


def test_command_remains_pending_until_a_matching_ack_arrives(fms):
    _, _, _, outbox, endpoint = fms
    command = make_envelope(
        boat_id="boat-01",
        message_type=MessageType.MISSION_ASSIGNMENT,
        payload=MissionAssignmentPayload(objective="x", search_area_id="a"),
        mission_id="m-1",
        sequence_number=outbox.next_sequence("boat-01"),
        timestamp=NOW,
    )
    outbox.enqueue(command)

    endpoint.receive(_state())
    assert outbox.unacknowledged("boat-01") == (command,)

    ack = make_envelope(
        boat_id="boat-01",
        message_type=MessageType.ACKNOWLEDGEMENT,
        payload=AcknowledgementPayload(acknowledged_message_id=command.message_id, accepted=True),
        sequence_number=1,
        timestamp=NOW,
    )
    endpoint.receive(ack)

    assert outbox.unacknowledged("boat-01") == ()


def test_acknowledgement_for_unknown_command_is_audited_without_clearing_pending_command(fms):
    _, _, audit, outbox, endpoint = fms
    command = make_envelope(
        boat_id="boat-01",
        message_type=MessageType.MISSION_ASSIGNMENT,
        payload=MissionAssignmentPayload(objective="x", search_area_id="a"),
        mission_id="m-1",
        sequence_number=outbox.next_sequence("boat-01"),
        timestamp=NOW,
    )
    outbox.enqueue(command)
    unknown_id = uuid4()
    ack = make_envelope(
        boat_id="boat-01",
        message_type=MessageType.ACKNOWLEDGEMENT,
        payload=AcknowledgementPayload(acknowledged_message_id=unknown_id, accepted=True),
        sequence_number=0,
        timestamp=NOW,
    )

    endpoint.receive(ack)

    assert outbox.unacknowledged("boat-01") == (command,)
    assert any(
        entry.category == "ack" and str(unknown_id) in entry.message and "queue cleared=False" in entry.message
        for entry in audit.entries()
    )


def test_duplicate_acknowledgement_is_harmless_and_does_not_clear_another_command(fms):
    _, _, audit, outbox, endpoint = fms
    first = make_envelope(
        boat_id="boat-01",
        message_type=MessageType.MISSION_ASSIGNMENT,
        payload=MissionAssignmentPayload(objective="first", search_area_id="a"),
        mission_id="m-1",
        sequence_number=outbox.next_sequence("boat-01"),
        timestamp=NOW,
    )
    second = make_envelope(
        boat_id="boat-01",
        message_type=MessageType.MISSION_ASSIGNMENT,
        payload=MissionAssignmentPayload(objective="second", search_area_id="b"),
        mission_id="m-2",
        sequence_number=outbox.next_sequence("boat-01"),
        timestamp=NOW,
    )
    outbox.enqueue(first)
    outbox.enqueue(second)
    ack = make_envelope(
        boat_id="boat-01",
        message_type=MessageType.ACKNOWLEDGEMENT,
        payload=AcknowledgementPayload(acknowledged_message_id=first.message_id, accepted=True),
        sequence_number=0,
        timestamp=NOW,
    )

    endpoint.receive(ack)
    endpoint.receive(ack)

    assert outbox.unacknowledged("boat-01") == (second,)
    results = [entry.message for entry in audit.entries() if entry.category == "ack"]
    assert len(results) == 2
    assert "queue cleared=True" in results[0]
    assert "queue cleared=False" in results[1]


def test_acknowledgement_from_another_registered_boat_cannot_clear_command(fms):
    registry, _, audit, outbox, endpoint = fms
    registry.register(BoatIdentity(boat_id="boat-02", display_name="Bravo"))
    command = make_envelope(
        boat_id="boat-01",
        message_type=MessageType.MISSION_ASSIGNMENT,
        payload=MissionAssignmentPayload(objective="x", search_area_id="a"),
        mission_id="m-1",
        sequence_number=outbox.next_sequence("boat-01"),
        timestamp=NOW,
    )
    outbox.enqueue(command)
    ack = make_envelope(
        boat_id="boat-02",
        message_type=MessageType.ACKNOWLEDGEMENT,
        payload=AcknowledgementPayload(acknowledged_message_id=command.message_id, accepted=True),
        sequence_number=0,
        timestamp=NOW,
    )

    endpoint.receive(ack)

    assert outbox.unacknowledged("boat-01") == (command,)
    assert outbox.unacknowledged("boat-02") == ()
    assert any(
        entry.category == "ack"
        and entry.boat_id == "boat-02"
        and str(command.message_id) in entry.message
        and "queue cleared=False" in entry.message
        for entry in audit.entries()
    )


def test_dedupe_window_is_bounded(fms):
    _, store, _, _, endpoint = fms
    first = _state(seq=0)
    endpoint.receive(first)
    endpoint.receive(_state(seq=1))
    endpoint.receive(_state(seq=2))  # pushes `first` out of the window of 2
    endpoint.receive(first)
    assert len(store.history("boat-01", MessageType.BOAT_STATE)) == 4
