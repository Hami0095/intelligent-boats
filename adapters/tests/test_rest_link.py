"""HTTP port behaviour with a controlled transport; full local-server tests are integration tests."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from io import BytesIO
from unittest.mock import MagicMock, Mock
from urllib.error import HTTPError, URLError

import pytest
from adapters.fms.rest import RestFmsError, RestFmsLink
from marine_contracts import (
    AcknowledgementPayload,
    BoatStatePayload,
    Envelope,
    MessageType,
    OperatingMode,
    encode_envelope,
    make_envelope,
)

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
def transport(monkeypatch: pytest.MonkeyPatch) -> Mock:
    response = MagicMock()
    response.__enter__.return_value = response
    response.read.return_value = b'{"replies": []}'
    opener = Mock()
    opener.open.return_value = response
    monkeypatch.setattr("adapters.fms.rest.build_opener", Mock(return_value=opener))
    return opener


@pytest.fixture
def message() -> Envelope:
    return make_envelope(
        boat_id="mock-01",
        message_type=MessageType.BOAT_STATE,
        mission_id="mission-1",
        payload=BoatStatePayload(operating_mode=OperatingMode.IDLE),
        sequence_number=17,
        timestamp=NOW,
    )


def test_send_preserves_the_existing_envelope_and_makes_one_post(transport: Mock, message: Envelope) -> None:
    link = RestFmsLink("http://127.0.0.1:8765/", timeout_s=0.5)
    link.send(message)
    request = transport.open.call_args.args[0]
    assert request.full_url == "http://127.0.0.1:8765/api/v1/boat-messages"
    assert request.get_method() == "POST"
    assert request.get_header("Content-type") == "application/json"
    assert request.data == encode_envelope(message).encode("utf-8")
    assert transport.open.call_args.kwargs == {"timeout": 0.5}
    assert transport.open.call_count == 1
    assert link.receive() == []
    assert transport.open.call_count == 1


def test_rejected_application_ack_is_delivered_once_despite_http_success(transport: Mock, message: Envelope) -> None:
    reply = make_envelope(
        boat_id=message.boat_id,
        mission_id=message.mission_id,
        message_type=MessageType.ACKNOWLEDGEMENT,
        payload=AcknowledgementPayload(
            acknowledged_message_id=message.message_id, accepted=False, reason="unsupported command"
        ),
        sequence_number=2,
        timestamp=NOW,
    )
    transport.open.return_value.read.return_value = json.dumps({"replies": [reply.model_dump(mode="json")]}).encode()
    link = RestFmsLink("https://fms.example")
    link.send(message)
    assert link.receive() == [reply]
    assert link.receive() == []
    assert transport.open.call_count == 1


@pytest.mark.parametrize("code", [302, 400, 403, 422, 500, 503])
def test_http_refusals_do_not_retry_and_distinguish_unavailable_service(
    transport: Mock, message: Envelope, code: int
) -> None:
    transport.open.side_effect = HTTPError("http://127.0.0.1", code, "refused", None, BytesIO())
    link = RestFmsLink("http://127.0.0.1")
    expected_error = ConnectionError if code >= 500 else RestFmsError
    with pytest.raises(expected_error):
        link.send(message)
    assert transport.open.call_count == 1
    assert link.receive() == []


@pytest.mark.parametrize("error", [URLError("offline"), TimeoutError("timeout"), OSError("connection lost")])
def test_connection_failure_uses_existing_port_error_without_retry(
    transport: Mock, message: Envelope, error: Exception
) -> None:
    transport.open.side_effect = error
    link = RestFmsLink("http://127.0.0.1")
    with pytest.raises(ConnectionError):
        link.send(message)
    assert transport.open.call_count == 1


@pytest.mark.parametrize("raw", [b"not-json", b"[]", b"{}", b'{"replies": {}}', b'{"replies": [{}]}', b"\xff"])
def test_invalid_response_does_not_create_replies(transport: Mock, message: Envelope, raw: bytes) -> None:
    transport.open.return_value.read.return_value = raw
    link = RestFmsLink("http://127.0.0.1")
    with pytest.raises(RestFmsError, match="invalid envelope response"):
        link.send(message)
    assert link.receive() == []


def test_response_is_queued_atomically_and_existing_replies_survive_a_later_error(
    transport: Mock, message: Envelope
) -> None:
    valid = message.model_dump(mode="json")
    transport.open.return_value.read.side_effect = [
        json.dumps({"replies": [valid]}).encode(),
        json.dumps({"replies": [valid, {}]}).encode(),
    ]
    link = RestFmsLink("http://127.0.0.1")
    link.send(message)
    with pytest.raises(RestFmsError):
        link.send(message)
    assert link.receive() == [message]


@pytest.mark.parametrize(
    "url",
    [
        "",
        "ftp://localhost",
        "http:///missing",
        "http://localhost/api",
        "http://user:secret@localhost",
        "http://a/?b=1",
        "http://a/#fragment",
        "http://localhost:bad",
        "http://localhost:0",
        "http://localhost:65536",
        " http://localhost",
    ],
)
def test_invalid_base_url_is_rejected(url: str) -> None:
    with pytest.raises(ValueError, match="base_url"):
        RestFmsLink(url)


@pytest.mark.parametrize("timeout_s", [0.0, -1.0, float("nan"), float("inf"), True])
def test_invalid_timeout_is_rejected(timeout_s: float) -> None:
    with pytest.raises(ValueError, match="timeout_s"):
        RestFmsLink("http://localhost", timeout_s=timeout_s)
