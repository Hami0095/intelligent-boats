"""Envelope contract: every boat <-> FMS message is wrapped and validated this way."""

import json
from datetime import datetime, timezone

import pytest
from marine_contracts import (
    SCHEMA_VERSION,
    AcknowledgementPayload,
    BoatStatePayload,
    Envelope,
    GeoPosition,
    MessageType,
    MissionProgressPayload,
    MissionStatus,
    OperatingMode,
    decode_envelope,
    encode_envelope,
    make_envelope,
)
from pydantic import ValidationError

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def _state_envelope(**overrides):
    payload = BoatStatePayload(
        operating_mode=OperatingMode.IDLE,
        position=GeoPosition(latitude_deg=59.3, longitude_deg=18.0),
    )
    kwargs = dict(
        boat_id="boat-01", message_type=MessageType.BOAT_STATE, payload=payload, sequence_number=7, timestamp=NOW
    )
    kwargs.update(overrides)
    return make_envelope(**kwargs)


def test_round_trip_preserves_header_and_typed_payload():
    env = _state_envelope()
    decoded = decode_envelope(encode_envelope(env))
    assert decoded == env
    assert decoded.typed_payload() == env.typed_payload()
    assert decoded.schema_version == SCHEMA_VERSION


def test_wire_format_contains_every_required_header_field():
    data = json.loads(encode_envelope(_state_envelope()))
    required = {
        "schema_version",
        "message_id",
        "boat_id",
        "mission_id",
        "message_type",
        "timestamp",
        "sequence_number",
        "payload",
    }
    assert required <= data.keys()


def test_unsupported_major_schema_version_is_rejected():
    data = json.loads(encode_envelope(_state_envelope()))
    data["schema_version"] = "2.0.0"
    with pytest.raises(ValidationError, match="unsupported schema major version"):
        decode_envelope(json.dumps(data))


@pytest.mark.parametrize("bad_version", ["1.0", "one", "1.0.0-beta"])
def test_malformed_schema_version_is_rejected(bad_version):
    data = json.loads(encode_envelope(_state_envelope()))
    data["schema_version"] = bad_version
    with pytest.raises(ValidationError):
        decode_envelope(json.dumps(data))


def test_naive_timestamp_is_rejected():
    data = json.loads(encode_envelope(_state_envelope()))
    data["timestamp"] = "2026-01-01T12:00:00"
    with pytest.raises(ValidationError, match="timezone-aware"):
        decode_envelope(json.dumps(data))


def test_boat_id_must_match_the_pattern():
    with pytest.raises(ValidationError):
        _state_envelope(boat_id="Boat 01")


def test_negative_sequence_number_is_rejected():
    with pytest.raises(ValidationError):
        _state_envelope(sequence_number=-1)


def test_mission_message_without_mission_id_is_rejected():
    payload = MissionProgressPayload(status=MissionStatus.ACCEPTED)
    with pytest.raises(ValidationError, match="requires a mission_id"):
        make_envelope(
            boat_id="boat-01",
            message_type=MessageType.MISSION_PROGRESS,
            payload=payload,
            sequence_number=0,
            timestamp=NOW,
        )


def test_make_envelope_refuses_payload_of_the_wrong_type():
    with pytest.raises(TypeError, match="expects BoatStatePayload"):
        make_envelope(
            boat_id="boat-01",
            message_type=MessageType.BOAT_STATE,
            payload=AcknowledgementPayload(
                acknowledged_message_id="3f1f2f4e-0000-4000-8000-000000000000", accepted=True
            ),
            sequence_number=0,
            timestamp=NOW,
        )


def test_raw_payload_that_does_not_match_its_type_is_rejected():
    with pytest.raises(ValidationError, match="payload invalid"):
        Envelope(
            message_id="3f1f2f4e-0000-4000-8000-000000000000",
            boat_id="boat-01",
            message_type=MessageType.BOAT_STATE,
            timestamp=NOW,
            sequence_number=0,
            payload={"not_a_field": 1},
        )


def test_unknown_message_type_is_rejected():
    data = json.loads(encode_envelope(_state_envelope()))
    data["message_type"] = "boat.unknown"
    with pytest.raises(ValidationError):
        decode_envelope(json.dumps(data))


def test_acknowledgement_is_a_valid_message_in_either_direction():
    ack = make_envelope(
        boat_id="boat-01",
        message_type=MessageType.ACKNOWLEDGEMENT,
        payload=AcknowledgementPayload(
            acknowledged_message_id="3f1f2f4e-0000-4000-8000-000000000000", accepted=False, reason="not supported"
        ),
        sequence_number=1,
        timestamp=NOW,
    )
    assert decode_envelope(encode_envelope(ack)).typed_payload().accepted is False
