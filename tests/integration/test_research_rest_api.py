"""Research HTTP boundary exercised against the real in-memory FMS application."""

from __future__ import annotations

import http.client
import json
import sys
from collections.abc import Iterator
from datetime import datetime, timezone
from threading import Thread
from types import SimpleNamespace
from typing import Any

import pytest
from adapters.fms.rest_server import make_research_server
from fms.communication.outbox import Outbox
from fms.core.endpoint import FmsEndpoint
from fms.core.fleet import BoatIdentity, FleetRegistry
from fms.data.research import ResearchFleet
from fms.data.store import InMemoryFleetStore
from fms.logging.audit import AuditLog
from marine_contracts import (
    BoatStatePayload,
    GeoPosition,
    MessageType,
    MissionProgressPayload,
    MissionStatus,
    OperatingMode,
    SafeStateAction,
    SafeStateCommandPayload,
    make_envelope,
)

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
def running_fms() -> Iterator[SimpleNamespace]:
    registry = FleetRegistry()
    registry.register(BoatIdentity(boat_id="mock-01", display_name="Alpha"))
    registry.register(BoatIdentity(boat_id="mock-02", display_name="Beta"))
    store = InMemoryFleetStore()
    endpoint = FmsEndpoint(
        registry=registry, store=store, audit=AuditLog(), outbox=Outbox(limit_per_boat=10), clock=lambda: NOW
    )
    app = ResearchFleet(registry=registry, store=store, endpoint=endpoint)
    server = make_research_server(("127.0.0.1", 0), app)
    thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    try:
        yield SimpleNamespace(port=server.server_address[1], app=app, store=store)
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()
        assert not thread.is_alive()


def _request(
    rig: SimpleNamespace,
    method: str,
    path: str,
    raw: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, Any]:
    connection = http.client.HTTPConnection("127.0.0.1", rig.port, timeout=2)
    try:
        connection.request(method, path, raw, headers or {"Content-Type": "application/json"})
        response = connection.getresponse()
        return response.status, json.loads(response.read())
    finally:
        connection.close()


def _state(boat_id: str = "mock-01", *, latitude: float | None = None, sequence: int = 0) -> bytes:
    envelope = make_envelope(
        boat_id=boat_id,
        message_type=MessageType.BOAT_STATE,
        payload=BoatStatePayload(
            operating_mode=OperatingMode.IDLE,
            position=GeoPosition(latitude_deg=latitude, longitude_deg=18.0) if latitude is not None else None,
        ),
        sequence_number=sequence,
        timestamp=NOW,
    )
    return envelope.model_dump_json().encode()


def test_initial_data_is_empty_and_registered_missing_messages_are_null(running_fms: SimpleNamespace) -> None:
    assert _request(running_fms, "GET", "/api/v1/boats") == (200, {"boats": []})
    assert _request(running_fms, "GET", "/api/v1/boats/mock-01/state") == (200, None)
    assert _request(running_fms, "GET", "/api/v1/boats/mock-01/health") == (200, None)
    assert _request(running_fms, "GET", "/api/v1/boats/mock-01/progress") == (
        200,
        {"mission": None, "environment": None},
    )


def test_ingestion_preserves_envelope_and_unknown_values(running_fms: SimpleNamespace) -> None:
    raw = _state()
    assert _request(running_fms, "POST", "/api/v1/boat-messages", raw) == (200, {"replies": []})
    status, body = _request(running_fms, "GET", "/api/v1/boats")
    assert status == 200
    assert len(body["boats"]) == 1
    boat = body["boats"][0]
    assert boat["boat_id"] == "mock-01" and boat["display_name"] == "Alpha"
    assert boat["last_received_at"] == NOW.isoformat()
    assert len(boat["messages"]) == 6
    stored = boat["messages"]["boat.state"]
    assert stored == {"envelope": json.loads(raw), "received_at": NOW.isoformat()}
    assert stored["envelope"]["payload"]["position"] is None
    assert stored["envelope"]["payload"]["battery_state_of_charge"] is None
    assert boat["messages"]["boat.service_health"] is None
    assert _request(running_fms, "GET", "/api/v1/boats/mock-01/state") == (200, stored)


def test_latest_received_states_are_isolated_between_boats(running_fms: SimpleNamespace) -> None:
    first = _state(latitude=59.1)
    second = _state("mock-02")
    updated = _state(latitude=59.2, sequence=1)
    for raw in (first, second, updated):
        assert _request(running_fms, "POST", "/api/v1/boat-messages", raw)[0] == 200
    _, body = _request(running_fms, "GET", "/api/v1/boats")
    boats = {boat["boat_id"]: boat for boat in body["boats"]}
    assert set(boats) == {"mock-01", "mock-02"}
    assert boats["mock-01"]["messages"]["boat.state"]["envelope"] == json.loads(updated)
    assert boats["mock-02"]["messages"]["boat.state"]["envelope"] == json.loads(second)
    assert len(running_fms.store.history("mock-01", MessageType.BOAT_STATE)) == 2
    assert len(running_fms.store.history("mock-02", MessageType.BOAT_STATE)) == 1


def test_report_status_and_transport_success_remain_distinct(running_fms: SimpleNamespace) -> None:
    envelope = make_envelope(
        boat_id="mock-01",
        mission_id="reported-mission",
        message_type=MessageType.MISSION_PROGRESS,
        payload=MissionProgressPayload(status=MissionStatus.REJECTED, detail="unknown area"),
        sequence_number=0,
        timestamp=NOW,
    )
    status, body = _request(running_fms, "POST", "/api/v1/boat-messages", envelope.model_dump_json().encode())
    assert status == 200
    assert body["replies"][0]["message_type"] == "ack"
    assert body["replies"][0]["payload"]["acknowledged_message_id"] == str(envelope.message_id)
    _, progress = _request(running_fms, "GET", "/api/v1/boats/mock-01/progress")
    assert progress["mission"]["envelope"] == envelope.model_dump(mode="json")
    assert progress["mission"]["envelope"]["payload"]["status"] == "rejected"
    assert progress["environment"] is None


@pytest.mark.parametrize("raw", [b"{", b"\xff"])
def test_malformed_json_is_rejected(running_fms: SimpleNamespace, raw: bytes) -> None:
    assert _request(running_fms, "POST", "/api/v1/boat-messages", raw)[0] == 400
    assert running_fms.app.snapshots() == []


@pytest.mark.parametrize("number", ["NaN", "Infinity", "-Infinity", "1e999", "-1e999"])
def test_nonfinite_wire_values_cannot_poison_stored_data(running_fms: SimpleNamespace, number: str) -> None:
    data = json.loads(_state())
    data["payload"]["position_uncertainty_m"] = "WIRE_NUMBER"
    raw = json.dumps(data).replace('"WIRE_NUMBER"', number).encode()
    assert _request(running_fms, "POST", "/api/v1/boat-messages", raw)[0] == 422
    assert running_fms.store.history("mock-01", MessageType.BOAT_STATE) == ()
    assert _request(running_fms, "GET", "/api/v1/boats") == (200, {"boats": []})
    assert _request(running_fms, "POST", "/api/v1/boat-messages", _state())[0] == 200
    assert _request(running_fms, "GET", "/api/v1/boats")[0] == 200


def test_parser_depth_failure_returns_a_request_error(running_fms: SimpleNamespace) -> None:
    depth = sys.getrecursionlimit() + 100
    raw = b"[" * depth + b"]" * depth
    # Interpreter versions may reject at parse time or during the finite JSON
    # representation check; both must produce a request error, not disconnect.
    status, body = _request(running_fms, "POST", "/api/v1/boat-messages", raw)
    assert status in (400, 422)
    assert "error" in body
    assert running_fms.app.snapshots() == []


@pytest.mark.parametrize("change", ["missing_header", "unsupported_version", "invalid_payload"])
def test_invalid_contracts_are_rejected(running_fms: SimpleNamespace, change: str) -> None:
    data = json.loads(_state())
    if change == "missing_header":
        del data["boat_id"]
    elif change == "unsupported_version":
        data["schema_version"] = "2.0.0"
    else:
        data["payload"]["invented_field"] = 1
    assert _request(running_fms, "POST", "/api/v1/boat-messages", json.dumps(data).encode())[0] == 422
    assert running_fms.app.snapshots() == []


def test_unknown_boat_cannot_ingest_data(running_fms: SimpleNamespace) -> None:
    assert _request(running_fms, "POST", "/api/v1/boat-messages", _state("unknown-boat"))[0] == 403
    assert running_fms.app.snapshots() == []


def test_fms_commands_cannot_be_ingested_as_boat_reports(running_fms: SimpleNamespace) -> None:
    command = make_envelope(
        boat_id="mock-01",
        message_type=MessageType.SAFE_STATE_COMMAND,
        payload=SafeStateCommandPayload(action=SafeStateAction.STOP_PROPULSION),
        sequence_number=0,
        timestamp=NOW,
    )
    assert _request(running_fms, "POST", "/api/v1/boat-messages", command.model_dump_json().encode())[0] == 422
    assert running_fms.app.snapshots() == []


@pytest.mark.parametrize("path", ["/not-an-api", "/api/v1/boats/mock-01/unsupported", "/api/v1/boats/unknown/state"])
def test_unknown_read_routes_and_boats_are_not_found(running_fms: SimpleNamespace, path: str) -> None:
    assert _request(running_fms, "GET", path)[0] == 404


@pytest.mark.parametrize(
    ("headers", "status"),
    [
        ({"Content-Type": "text/plain"}, 415),
        ({"Content-Type": "application/json", "Content-Length": "bad"}, 400),
        ({"Content-Type": "application/json", "Content-Length": "0"}, 400),
        ({"Content-Type": "application/json", "Content-Length": "-1"}, 400),
        ({"Content-Type": "application/json", "Content-Length": "1048577"}, 413),
    ],
)
def test_request_boundary_rejects_unsupported_or_invalid_bodies(
    running_fms: SimpleNamespace, headers: dict[str, str], status: int
) -> None:
    assert _request(running_fms, "POST", "/api/v1/boat-messages", b"{}", headers)[0] == status


def test_missing_content_length_and_wrong_post_route_are_rejected(running_fms: SimpleNamespace) -> None:
    connection = http.client.HTTPConnection("127.0.0.1", running_fms.port, timeout=2)
    try:
        connection.putrequest("POST", "/api/v1/boat-messages")
        connection.putheader("Content-Type", "application/json")
        connection.endheaders()
        assert connection.getresponse().status == 411
    finally:
        connection.close()
    assert _request(running_fms, "POST", "/api/v1/unknown", b"{}")[0] == 404


@pytest.mark.parametrize("host", ["0.0.0.0", "192.0.2.1", "::1", "example.com"])
def test_server_refuses_non_ipv4_loopback_bind(host: str) -> None:
    with pytest.raises(ValueError, match="IPv4 loopback"):
        make_research_server((host, 0), None)  # type: ignore[arg-type]


@pytest.mark.parametrize("limit", [0, -1, True])
def test_server_requires_a_positive_body_limit(limit: int) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        make_research_server(("127.0.0.1", 0), None, max_body_bytes=limit)  # type: ignore[arg-type]
