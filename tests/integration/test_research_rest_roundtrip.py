"""Real local HTTP, existing AI Box reporting, and FMS dashboard retrieval."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import datetime, timezone
from threading import Thread
from typing import Any
from urllib.request import urlopen

import pytest
from adapters.fms.rest_server import make_research_server
from fms.communication.outbox import Outbox
from fms.core.endpoint import FmsEndpoint
from fms.core.fleet import BoatIdentity, FleetRegistry
from fms.data.research import ResearchFleet
from fms.data.store import InMemoryFleetStore
from fms.logging.audit import AuditLog
from marine_contracts import SCHEMA_VERSION

from scripts.demo_research_boats import GEOGRAPHIC_FIXTURES, build_mock_boats

NOW = datetime(2026, 11, 14, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def research_url() -> Iterator[str]:
    registry, store = FleetRegistry(), InMemoryFleetStore()
    for boat_id in ("mock-01", "mock-02"):
        registry.register(BoatIdentity(boat_id, f"Research {boat_id}"))
    endpoint = FmsEndpoint(registry=registry, store=store, audit=AuditLog(), outbox=Outbox(100), clock=lambda: NOW)
    application = ResearchFleet(registry=registry, store=store, endpoint=endpoint)
    server = make_research_server(("127.0.0.1", 0), application)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()
        assert not thread.is_alive()


def get_json(url: str) -> Any:
    with urlopen(url, timeout=2) as response:
        assert response.status == 200
        return json.load(response)


def test_two_ai_boxes_report_exact_values_and_health_over_real_http(research_url: str) -> None:
    assert get_json(f"{research_url}/api/v1/boats") == {"boats": []}
    boats = build_mock_boats(research_url, clock=lambda: NOW)
    try:
        for boat in boats:
            boat.start()
        for step in range(10):
            for boat in boats:
                boat.step(step)
        snapshots = get_json(f"{research_url}/api/v1/boats")["boats"]
        assert [snapshot["boat_id"] for snapshot in snapshots] == ["mock-01", "mock-02"]
        for index, snapshot in enumerate(snapshots):
            state = snapshot["messages"]["boat.state"]["envelope"]
            latitude, longitude = GEOGRAPHIC_FIXTURES[index][0]
            assert state["payload"]["position"] == {"latitude_deg": latitude, "longitude_deg": longitude}
            assert state["payload"]["heading_deg"] == float(90 + index * 90)
            assert state["payload"]["battery_state_of_charge"] is None
            assert state["boat_id"] == boats[index].boat_id
            assert state["schema_version"] == SCHEMA_VERSION
            # The existing bridge stamps envelope creation time, not the
            # PositionSource's estimation timestamp. Preserve that distinction.
            assert datetime.fromisoformat(state["timestamp"].replace("Z", "+00:00")).utcoffset() is not None
            assert snapshot["messages"]["boat.state"]["received_at"] == NOW.isoformat()
            mission = snapshot["messages"]["boat.mission_progress"]["envelope"]
            assert mission["payload"]["status"] == "accepted"
            assert mission["mission_id"] == f"research-{boats[index].boat_id}"
            environment = snapshot["messages"]["boat.environment_progress"]["envelope"]
            assert environment["mission_id"] == mission["mission_id"]
            health = snapshot["messages"]["boat.service_health"]["envelope"]["payload"]["services"]
            assert any(service["name"] == "fms-bridge" for service in health)
            assert snapshot["messages"]["boat.obstacle_summary"] is None
            assert boats[index].runtime.bridge.pending == 0
            assert all(command.thrust == 0.0 and command.rudder == 0.0 for command in boats[index].propulsion.commands)
    finally:
        for boat in boats:
            boat.stop()


def test_new_state_updates_only_the_reporting_boat(research_url: str) -> None:
    boats = build_mock_boats(research_url, clock=lambda: NOW)
    try:
        for boat in boats:
            boat.start()
            boat.step(0)
        before = get_json(f"{research_url}/api/v1/boats")["boats"]
        boats[0].step(1)
        after = get_json(f"{research_url}/api/v1/boats")["boats"]
        assert after[1] == before[1]
        old_state = before[0]["messages"]["boat.state"]["envelope"]
        new_state = after[0]["messages"]["boat.state"]["envelope"]
        assert new_state["message_id"] != old_state["message_id"]
        latitude, longitude = GEOGRAPHIC_FIXTURES[0][1]
        assert new_state["payload"]["position"] == {"latitude_deg": latitude, "longitude_deg": longitude}
        assert get_json(f"{research_url}/api/v1/boats/mock-01/state")["envelope"] == new_state
    finally:
        for boat in boats:
            boat.stop()


def test_local_only_mock_state_does_not_acquire_geographic_coordinates(research_url: str) -> None:
    assert get_json(f"{research_url}/api/v1/boats/mock-01/state") is None
    boats = build_mock_boats(research_url, clock=lambda: NOW, geographic=False)
    try:
        boats[0].start()
        state = boats[0].step(0)
        assert state.local_position is not None
        received = get_json(f"{research_url}/api/v1/boats/mock-01/state")["envelope"]["payload"]
        assert received["position"] is None
        assert received["speed_over_ground_mps"] is None
        assert received["position_uncertainty_m"] is None
        assert "x_m" not in received
    finally:
        for boat in boats:
            boat.stop()
