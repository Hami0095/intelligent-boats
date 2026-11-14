"""End-to-end: a boat built from mock adapters, talking to a real FMS endpoint over a loopback link."""

from collections.abc import Iterator
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from adapters.fms.loopback import LoopbackFmsLink
from adapters.propulsion.mock import MockPropulsionSink
from adapters.sensors.mock import MockPositionSource, MockSensorAdapter
from adapters.simulation.isaac_sim.adapter import IsaacSimAdapter
from adapters.simulation.mock_vessel import MockVessel
from ai_box.bootstrap import build_boat
from ai_box.config.settings import AIBoxConfig
from ai_box.core.events import FMS_OUTBOUND, Outbound
from ai_box.core.geometry import LocalPoint
from ai_box.core.ports import Detection, SensorKind, SensorSample
from ai_box.environment.knowledge import RegionStatus
from ai_box.environment.model import GridIndexer, SearchArea
from ai_box.motion.commands import NavigationGoal, PropulsionCommand, VehicleState
from ai_box.services.command_router import NOT_IMPLEMENTED_NAV
from fms.communication.outbox import Outbox
from fms.core.endpoint import FmsEndpoint
from fms.core.fleet import BoatIdentity, FleetRegistry, UnregisteredBoatError
from fms.data.store import InMemoryFleetStore
from fms.logging.audit import AuditLog
from fms.missions.service import MissionService as FmsMissionService
from marine_contracts import (
    SCHEMA_VERSION,
    BoatStatePayload,
    ConfigurationUpdatePayload,
    Envelope,
    GeoPosition,
    HealthStatus,
    MessageType,
    MissionAssignmentPayload,
    MissionCancellationPayload,
    MissionStatus,
    NavigationGoalPayload,
    OperatingMode,
    OperationalEventPayload,
    SafeStateAction,
    SafeStateCommandPayload,
    Severity,
    make_envelope,
)
from pydantic import BaseModel

NOW = datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)
BOAT = "boat-01"


@pytest.fixture
def world():
    registry = FleetRegistry()
    registry.register(BoatIdentity(boat_id=BOAT, display_name="Alpha"))
    store = InMemoryFleetStore()
    audit = AuditLog()
    outbox = Outbox(limit_per_boat=100)
    endpoint = FmsEndpoint(registry=registry, store=store, audit=audit, outbox=outbox, clock=lambda: NOW)
    fms_missions = FmsMissionService(registry, outbox)

    link = LoopbackFmsLink(server=endpoint.receive)
    position = MockPositionSource()
    position.set_state(
        VehicleState(
            timestamp=NOW,
            local_position=LocalPoint(5.0, 5.0),
            geo_position=GeoPosition(latitude_deg=59.3, longitude_deg=18.0),
        )
    )
    sink = MockPropulsionSink()
    runtime = build_boat(
        AIBoxConfig(boat_id=BOAT, outbound_buffer_limit=50),
        position=position,
        propulsion=sink,
        fms_link=link,
        search_areas={"area-1": SearchArea(0.0, 0.0, 20.0, 20.0)},
    )
    runtime.app.start()
    yield SimpleNamespace(
        runtime=runtime,
        store=store,
        audit=audit,
        outbox=outbox,
        endpoint=endpoint,
        link=link,
        position=position,
        sink=sink,
        fms_missions=fms_missions,
        registry=registry,
    )
    runtime.app.shutdown()


def _deliver_pending_commands(world, boat_id=BOAT):
    for envelope in world.outbox.unacknowledged(boat_id):
        world.link.deliver([envelope])


def test_boat_state_telemetry_reaches_the_fms(world):
    world.runtime.app.tick()
    latest = world.store.latest(BOAT, MessageType.BOAT_STATE)
    assert latest is not None
    assert latest.envelope.boat_id == BOAT
    assert latest.envelope.mission_id is None
    assert latest.payload.operating_mode is OperatingMode.IDLE
    assert latest.payload.position == GeoPosition(latitude_deg=59.3, longitude_deg=18.0)


def test_missing_boat_state_measurements_remain_unknown_in_fms_storage(world):
    world.position.set_state(None)
    world.runtime.app.tick()

    latest = world.store.latest(BOAT, MessageType.BOAT_STATE)
    assert latest is not None
    assert latest.payload.position is None
    assert latest.payload.position_uncertainty_m is None
    assert latest.payload.speed_over_ground_mps is None
    assert latest.payload.heading_deg is None
    assert latest.payload.battery_state_of_charge is None

    world.position.set_state(
        VehicleState(
            timestamp=NOW,
            position_uncertainty_m=0.0,
            speed_over_ground_mps=0.0,
            heading_deg=0.0,
        )
    )
    world.runtime.app.tick()

    latest = world.store.latest(BOAT, MessageType.BOAT_STATE)
    assert latest is not None
    assert latest.payload.position_uncertainty_m == 0.0
    assert latest.payload.speed_over_ground_mps == 0.0
    assert latest.payload.heading_deg == 0.0
    assert latest.payload.battery_state_of_charge is None


def test_mission_assignment_is_accepted_and_the_boat_starts_searching(world):
    command = world.fms_missions.assign(
        BOAT, "m-1", MissionAssignmentPayload(objective="find target", search_area_id="area-1")
    )
    assert command.message_type is MessageType.MISSION_ASSIGNMENT
    assert command.boat_id == BOAT
    assert command.mission_id == "m-1"
    assert command.schema_version == SCHEMA_VERSION
    assert command.timestamp.utcoffset() is not None
    assert command.timestamp.utcoffset().total_seconds() == 0
    assert command.sequence_number == 0
    assert world.outbox.unacknowledged(BOAT) == (command,)
    _deliver_pending_commands(world)

    for _ in range(3):
        world.runtime.app.tick()

    assert world.runtime.missions.active_mission is not None
    assert world.runtime.missions.active_mission.mission_id == "m-1"
    assert world.runtime.operating.mode is OperatingMode.AUTONOMOUS
    assert world.runtime.motion.goal is not None

    progress = world.store.latest(BOAT, MessageType.MISSION_PROGRESS)
    assert progress is not None and progress.payload.status is MissionStatus.ACCEPTED
    assert progress.envelope.boat_id == BOAT
    assert progress.envelope.mission_id == "m-1"
    assert progress.envelope.schema_version == SCHEMA_VERSION
    assert progress.envelope.timestamp.utcoffset() is not None
    assert progress.envelope.timestamp.utcoffset() == timezone.utc.utcoffset(progress.envelope.timestamp)
    assert progress.envelope.sequence_number >= 0
    assert any(
        str(command.message_id) in entry.message
        and "accepted" in entry.message
        and "queue cleared=True" in entry.message
        for entry in world.audit.entries()
        if entry.category == "ack"
    )
    environment_progress = world.store.latest(BOAT, MessageType.ENVIRONMENT_PROGRESS)
    assert environment_progress is not None
    assert environment_progress.envelope.boat_id == BOAT
    assert environment_progress.envelope.mission_id == "m-1"
    assert environment_progress.payload.searched_region_count == 0
    assert environment_progress.payload.coverage_fraction == 0.0
    mission = world.runtime.missions.active_mission
    assert mission is not None
    visited = world.runtime.knowledge.region(mission.regions[0])
    assert visited.status is RegionStatus.VISITED
    assert visited.visit_count > 0 and visited.search_count == 0
    assert world.runtime.knowledge.region(mission.regions[1]).status is RegionStatus.UNKNOWN
    assert world.outbox.unacknowledged(BOAT) == ()  # the boat's acknowledgement cleared the FMS queue


def test_duplicate_assignment_delivery_does_not_replace_the_active_mission(world: SimpleNamespace) -> None:
    command = world.fms_missions.assign(
        BOAT, "m-duplicate", MissionAssignmentPayload(objective="find target", search_area_id="area-1")
    )
    world.link.deliver([command, command])

    for _ in range(3):
        world.runtime.app.tick()

    progress = world.store.history(BOAT, MessageType.MISSION_PROGRESS)
    assert [message.payload.status for message in progress] == [MissionStatus.ACCEPTED, MissionStatus.REJECTED]
    assert world.runtime.missions.active_mission is not None
    assert world.runtime.missions.active_mission.mission_id == "m-duplicate"
    acknowledgements = [
        entry.message
        for entry in world.audit.entries()
        if entry.category == "ack" and str(command.message_id) in entry.message
    ]
    assert len(acknowledgements) == 2
    assert "accepted" in acknowledgements[0] and "queue cleared=True" in acknowledgements[0]
    assert "rejected" in acknowledgements[1] and "queue cleared=False" in acknowledgements[1]
    assert world.outbox.unacknowledged(BOAT) == ()


def test_rejected_mission_assignment_is_acknowledged_and_clears_the_fms_queue(world: SimpleNamespace) -> None:
    command = world.fms_missions.assign(
        BOAT,
        "m-unknown-area",
        MissionAssignmentPayload(objective="find target", search_area_id="missing-area"),
    )
    _deliver_pending_commands(world)

    for _ in range(3):
        world.runtime.app.tick()

    progress = world.store.latest(BOAT, MessageType.MISSION_PROGRESS)
    assert progress is not None and progress.payload.status is MissionStatus.REJECTED
    assert progress.envelope.mission_id == "m-unknown-area"
    assert any(
        str(command.message_id) in entry.message
        and "rejected" in entry.message
        and "queue cleared=True" in entry.message
        for entry in world.audit.entries()
        if entry.category == "ack"
    )
    assert world.runtime.missions.active_mission is None
    assert world.outbox.unacknowledged(BOAT) == ()


def test_fms_routes_a_mission_only_to_its_target_boat(world: SimpleNamespace) -> None:
    other_boat_id = "boat-02"
    world.registry.register(BoatIdentity(boat_id=other_boat_id, display_name="Bravo"))
    position = MockPositionSource()
    position.set_state(
        VehicleState(
            timestamp=NOW,
            local_position=LocalPoint(1.0, 1.0),
            geo_position=GeoPosition(latitude_deg=59.4, longitude_deg=18.1),
        )
    )
    other_link = LoopbackFmsLink(server=world.endpoint.receive)
    other_runtime = build_boat(
        AIBoxConfig(boat_id=other_boat_id),
        position=position,
        propulsion=MockPropulsionSink(),
        fms_link=other_link,
        search_areas={"area-1": SearchArea(0.0, 0.0, 20.0, 20.0)},
    )
    other_runtime.app.start()
    try:
        command = world.fms_missions.assign(
            other_boat_id, "m-2", MissionAssignmentPayload(objective="find target", search_area_id="area-1")
        )
        other_link.deliver([command])
        for _ in range(3):
            other_runtime.app.tick()

        assert world.runtime.missions.active_mission is None
        assert other_runtime.missions.active_mission is not None
        assert other_runtime.missions.active_mission.mission_id == "m-2"
        assert world.store.latest(other_boat_id, MessageType.MISSION_PROGRESS) is not None
        assert world.store.history(BOAT, MessageType.MISSION_PROGRESS) == ()
        assert world.outbox.unacknowledged(other_boat_id) == ()
    finally:
        other_runtime.app.shutdown()


def test_one_boat_can_disconnect_while_the_other_keeps_reporting_and_commands_ack(
    world: SimpleNamespace,
) -> None:
    other_boat_id = "boat-02"
    world.registry.register(BoatIdentity(boat_id=other_boat_id, display_name="Bravo"))
    other_position = MockPositionSource()
    other_position.set_state(
        VehicleState(
            timestamp=NOW,
            local_position=LocalPoint(1.0, 1.0),
            geo_position=GeoPosition(latitude_deg=59.4, longitude_deg=18.1),
        )
    )
    other_link = LoopbackFmsLink(server=world.endpoint.receive)
    other_runtime = build_boat(
        AIBoxConfig(boat_id=other_boat_id),
        position=other_position,
        propulsion=MockPropulsionSink(),
        fms_link=other_link,
        search_areas={"area-1": SearchArea(0.0, 0.0, 20.0, 20.0)},
    )
    other_runtime.app.start()
    try:
        command_a = world.fms_missions.assign(
            BOAT, "mission-a", MissionAssignmentPayload(objective="search A", search_area_id="area-1")
        )
        command_b = world.fms_missions.assign(
            other_boat_id, "mission-b", MissionAssignmentPayload(objective="search B", search_area_id="area-1")
        )
        assert command_a.sequence_number == command_b.sequence_number == 0

        world.link.deliver([command_a])
        world.runtime.app.tick()
        other_link.deliver([command_b])
        other_runtime.app.tick()
        other_runtime.app.tick()

        assert world.runtime.missions.active_mission is not None
        assert other_runtime.missions.active_mission is not None
        assert world.outbox.unacknowledged(BOAT) == (command_a,)
        assert world.outbox.unacknowledged(other_boat_id) == ()
        assert any(
            entry.category == "ack"
            and entry.boat_id == other_boat_id
            and str(command_b.message_id) in entry.message
            and "queue cleared=True" in entry.message
            for entry in world.audit.entries()
        )

        world.link.set_online(False)
        event = OperationalEventPayload(
            severity=Severity.WARNING,
            code="test.offline",
            message="buffered while boat A is disconnected",
        )
        world.runtime.app.bus.publish(FMS_OUTBOUND, Outbound(message_type=MessageType.OPERATIONAL_EVENT, payload=event))
        for _ in range(10):
            world.runtime.app.tick()
            other_runtime.app.tick()

        assert len(world.store.history(BOAT, MessageType.BOAT_STATE)) == 1
        assert world.store.history(BOAT, MessageType.MISSION_PROGRESS) == ()
        assert world.runtime.bridge.pending >= 10
        assert world.outbox.unacknowledged(BOAT) == (command_a,)
        assert world.outbox.unacknowledged(other_boat_id) == ()
        assert len(world.store.history(other_boat_id, MessageType.BOAT_STATE)) > 1
        assert world.store.latest(other_boat_id, MessageType.MISSION_PROGRESS) is not None

        world.link.set_online(True)
        for _ in range(3):
            world.runtime.app.tick()
            other_runtime.app.tick()

        assert world.outbox.unacknowledged(BOAT) == ()
        assert world.outbox.unacknowledged(other_boat_id) == ()
        assert world.store.latest(BOAT, MessageType.MISSION_PROGRESS).payload.status is MissionStatus.ACCEPTED
        assert world.store.latest(BOAT, MessageType.OPERATIONAL_EVENT).payload == event
        offline_health = world.store.latest(BOAT, MessageType.SERVICE_HEALTH)
        assert offline_health is not None
        bridge_health = next(item for item in offline_health.payload.services if item.name == "fms-bridge")
        assert bridge_health.status.value == "degraded"
        assert world.store.latest(other_boat_id, MessageType.MISSION_PROGRESS).payload.status is MissionStatus.ACCEPTED
        assert world.store.latest(BOAT, MessageType.BOAT_STATE).payload.position == GeoPosition(
            latitude_deg=59.3, longitude_deg=18.0
        )
        assert world.store.latest(other_boat_id, MessageType.BOAT_STATE).payload.position == GeoPosition(
            latitude_deg=59.4, longitude_deg=18.1
        )
        assert not any(
            entry.category == "out_of_order" and entry.boat_id == other_boat_id for entry in world.audit.entries()
        )
        assert world.runtime.missions.active_mission.mission_id == "mission-a"
        assert other_runtime.missions.active_mission.mission_id == "mission-b"
        assert world.runtime.bridge.pending == 0
        assert other_runtime.bridge.pending == 0
    finally:
        other_runtime.app.shutdown()


def test_boat_rejects_a_mission_addressed_to_another_registered_boat(world: SimpleNamespace) -> None:
    other_boat_id = "boat-02"
    world.registry.register(BoatIdentity(boat_id=other_boat_id, display_name="Bravo"))
    command = world.fms_missions.assign(
        other_boat_id, "m-2", MissionAssignmentPayload(objective="find target", search_area_id="area-1")
    )
    world.link.deliver([command])
    world.runtime.app.tick()

    assert world.runtime.missions.active_mission is None
    assert world.runtime.operating.mode is OperatingMode.IDLE
    assert world.outbox.unacknowledged(other_boat_id) == (command,)
    status, detail = world.runtime.bridge.health_detail()
    assert status.value == "degraded"
    assert "inbound message(s) rejected" in detail
    assert world.runtime.bridge.pending == 0


def test_boat_rejects_boat_originated_message_on_fms_inbound_link(world: SimpleNamespace) -> None:
    message = make_envelope(
        boat_id=BOAT,
        message_type=MessageType.BOAT_STATE,
        payload=BoatStatePayload(operating_mode=OperatingMode.IDLE),
        sequence_number=0,
        timestamp=NOW,
    )
    world.link.deliver([message])
    world.runtime.app.tick()

    status, detail = world.runtime.bridge.health_detail()
    assert status.value == "degraded"
    assert "inbound message(s) rejected" in detail
    assert world.runtime.missions.active_mission is None


@pytest.mark.parametrize(
    ("message_type", "payload"),
    [
        (
            MessageType.CONFIGURATION_UPDATE,
            ConfigurationUpdatePayload(config_version="v1", parameters={"mode": "test"}),
        ),
        (
            MessageType.SAFE_STATE_COMMAND,
            SafeStateCommandPayload(action=SafeStateAction.RETURN_HOME, reason="test"),
        ),
    ],
)
def test_unsupported_commands_are_rejected_with_a_reason(
    world: SimpleNamespace, message_type: MessageType, payload: BaseModel
) -> None:
    command = make_envelope(
        boat_id=BOAT,
        message_type=message_type,
        payload=payload,
        sequence_number=0,
        timestamp=NOW,
    )
    world.link.deliver([command])
    world.runtime.app.tick()
    world.runtime.app.tick()

    acknowledgement = next(
        entry.message
        for entry in world.audit.entries()
        if entry.category == "ack" and str(command.message_id) in entry.message
    )
    assert "rejected" in acknowledgement
    assert "queue cleared=False" in acknowledgement
    assert "not implemented" in acknowledgement
    assert world.runtime.operating.mode is OperatingMode.IDLE
    assert world.runtime.motion.goal is None


def test_operational_events_and_service_health_reach_the_fms(world: SimpleNamespace) -> None:
    event = OperationalEventPayload(
        severity=Severity.WARNING,
        code="test.integration",
        message="deterministic event",
    )
    world.runtime.app.bus.publish(FMS_OUTBOUND, Outbound(message_type=MessageType.OPERATIONAL_EVENT, payload=event))

    for _ in range(10):
        world.runtime.app.tick()

    stored_event = world.store.latest(BOAT, MessageType.OPERATIONAL_EVENT)
    health = world.store.latest(BOAT, MessageType.SERVICE_HEALTH)
    assert stored_event is not None and stored_event.payload == event
    assert health is not None
    assert stored_event.envelope.boat_id == BOAT
    assert stored_event.envelope.mission_id is None
    assert health.envelope.boat_id == BOAT
    assert health.envelope.mission_id is None
    services = {service.name: service for service in health.payload.services}
    assert services["fms-bridge"].status is HealthStatus.OK
    assert services["telemetry"].status is HealthStatus.OK


def test_outbound_buffer_drops_oldest_message_and_flushes_remaining_in_order(world: SimpleNamespace) -> None:
    world.link.set_online(False)
    runtime = build_boat(
        AIBoxConfig(boat_id=BOAT, outbound_buffer_limit=2),
        position=world.position,
        propulsion=MockPropulsionSink(),
        fms_link=world.link,
    )
    runtime.app.start()
    try:
        for _ in range(3):
            runtime.app.tick()
        assert runtime.bridge.pending == 2
        status, detail = runtime.bridge.health_detail()
        assert status.value == "degraded"
        assert "1 outbound message(s) dropped" in detail

        world.link.set_online(True)
        runtime.bridge.tick()

        history = world.store.history(BOAT, MessageType.BOAT_STATE)
        assert [message.envelope.sequence_number for message in history] == [1, 2]
        assert runtime.bridge.pending == 0
    finally:
        runtime.app.shutdown()


def test_boat_retargets_once_it_reaches_its_goal(world):
    world.fms_missions.assign(BOAT, "m-1", MissionAssignmentPayload(objective="find target", search_area_id="area-1"))
    _deliver_pending_commands(world)
    for _ in range(3):
        world.runtime.app.tick()
    first_target = world.runtime.motion.goal.target

    world.position.set_state(VehicleState(timestamp=NOW, local_position=first_target))
    world.runtime.app.tick()

    second_target = world.runtime.motion.goal.target
    assert second_target != first_target
    mission = world.runtime.missions.active_mission
    assert mission is not None
    records = [world.runtime.knowledge.region(region) for region in mission.regions]
    assert sum(record.visit_count for record in records) >= 2
    assert any(record.status is RegionStatus.VISITED for record in records)
    assert all(record.search_count == 0 for record in records)
    environment_progress = world.store.latest(BOAT, MessageType.ENVIRONMENT_PROGRESS)
    assert environment_progress is not None
    assert environment_progress.envelope.mission_id == "m-1"
    assert environment_progress.payload.known_region_count >= 2
    assert environment_progress.payload.searched_region_count == 0


def test_safe_state_command_stops_propulsion_and_is_acknowledged(world):
    command = world.fms_missions.safe_state(BOAT, SafeStateAction.STOP_PROPULSION, reason="test")
    _deliver_pending_commands(world)
    world.runtime.app.tick()
    world.runtime.app.tick()

    assert world.runtime.operating.mode is OperatingMode.SAFE_STATE
    assert world.sink.last is not None
    assert world.sink.last.thrust == 0.0 and world.sink.last.rudder == 0.0
    assert any(
        str(command.message_id) in entry.message and "accepted" in entry.message
        for entry in world.audit.entries()
        if entry.category == "ack"
    )
    assert world.outbox.unacknowledged(BOAT) == ()


def test_fms_mission_cancellation_round_trip_is_recorded_and_acknowledged(world: SimpleNamespace) -> None:
    world.fms_missions.assign(BOAT, "m-1", MissionAssignmentPayload(objective="find target", search_area_id="area-1"))
    _deliver_pending_commands(world)
    for _ in range(3):
        world.runtime.app.tick()
    assert world.runtime.missions.active_mission is not None

    command = world.fms_missions.cancel(BOAT, "m-1", reason="operator request")
    _deliver_pending_commands(world)
    for _ in range(3):
        world.runtime.app.tick()

    progress = world.store.latest(BOAT, MessageType.MISSION_PROGRESS)
    assert progress is not None and progress.payload.status is MissionStatus.ABORTED
    assert progress.envelope.mission_id == "m-1"
    assert world.runtime.missions.active_mission is None
    assert any(
        str(command.message_id) in entry.message
        and "accepted" in entry.message
        and "queue cleared=True" in entry.message
        for entry in world.audit.entries()
        if entry.category == "ack"
    )
    assert world.outbox.unacknowledged(BOAT) == ()


def test_unsupported_navigation_goal_is_rejected_explicitly(world):
    goal = make_envelope(
        boat_id=BOAT,
        message_type=MessageType.NAVIGATION_GOAL,
        payload=NavigationGoalPayload(goal_id="g-1", target=GeoPosition(latitude_deg=59.0, longitude_deg=18.0)),
        mission_id="m-1",
        sequence_number=0,
        timestamp=NOW,
    )
    world.link.deliver([goal])
    world.runtime.app.tick()
    world.runtime.app.tick()

    rejections = [e for e in world.audit.entries() if e.category == "ack" and "rejected" in e.message]
    assert any(NOT_IMPLEMENTED_NAV in e.message for e in rejections), (
        "boat must reject the command visibly, with the reason, not accept it silently"
    )
    assert world.runtime.motion.goal is None


def test_telemetry_is_buffered_during_disconnection_and_delivered_in_order(world):
    world.link.set_online(False)
    for _ in range(3):
        world.runtime.app.tick()
    assert world.store.history(BOAT, MessageType.BOAT_STATE) == ()
    assert world.runtime.bridge.pending >= 3

    world.link.set_online(True)
    world.runtime.app.tick()

    history = world.store.history(BOAT, MessageType.BOAT_STATE)
    sequences = [m.envelope.sequence_number for m in history]
    assert len(history) >= 4
    assert sequences == sorted(sequences)
    assert world.runtime.bridge.pending == 0


def test_unregistered_boat_is_refused_and_the_boat_reports_degraded(world):
    rogue = build_boat(
        AIBoxConfig(boat_id="boat-99"),
        position=world.position,
        propulsion=MockPropulsionSink(),
        fms_link=LoopbackFmsLink(server=world.endpoint.receive),
    )
    rogue.app.start()
    try:
        rogue.app.tick()
        assert world.store.history("boat-99", MessageType.BOAT_STATE) == ()
        bridge_health = next(e for e in rogue.app.health_report() if e.name == "fms-bridge")
        assert bridge_health.status.value == "degraded"
    finally:
        rogue.app.shutdown()


def test_endpoint_raises_for_unknown_boats_directly(world):
    stranger = make_envelope(
        boat_id="boat-42",
        message_type=MessageType.BOAT_STATE,
        payload=BoatStatePayload(operating_mode=OperatingMode.IDLE),
        sequence_number=0,
        timestamp=NOW,
    )
    with pytest.raises(UnregisteredBoatError):
        world.endpoint.receive(stranger)


def test_mock_sensor_observation_updates_knowledge_and_reports_aggregate_progress(world: SimpleNamespace) -> None:
    observation_point = LocalPoint(15.0, 5.0)
    sample = SensorSample(
        sensor_id="mock-observation",
        kind=SensorKind.OTHER,
        timestamp=NOW,
        data={
            "environment_observation": {
                "point": {"x_m": observation_point.x_m, "y_m": observation_point.y_m},
                "confidence": 0.8,
                "mission_id": "m-observed",
                "provenance_detail": "explicit mock fixture",
            }
        },
    )
    position = MockPositionSource()
    position.set_state(VehicleState(timestamp=NOW, local_position=LocalPoint(5.0, 5.0)))
    link = LoopbackFmsLink(server=world.endpoint.receive)
    grid = GridIndexer()
    runtime = build_boat(
        AIBoxConfig(boat_id=BOAT, outbound_buffer_limit=50),
        position=position,
        propulsion=MockPropulsionSink(),
        fms_link=link,
        sensors=[MockSensorAdapter("mock-observation", [[], [sample]])],
        search_areas={"area-1": SearchArea(0.0, 0.0, 20.0, 20.0)},
        indexer=grid,
    )
    runtime.app.start()
    try:
        command = world.fms_missions.assign(
            BOAT, "m-observed", MissionAssignmentPayload(objective="find target", search_area_id="area-1")
        )
        link.deliver([command])
        for _ in range(10):
            runtime.app.tick()

        assert runtime.missions.active_mission is not None
        assert runtime.missions.active_mission.mission_id == "m-observed"
        assert world.outbox.unacknowledged(BOAT) == ()

        observed = runtime.knowledge.region(grid.region_of(observation_point))
        visited = runtime.knowledge.region(grid.region_of(LocalPoint(5.0, 5.0)))
        assert observed.status is RegionStatus.OBSERVED
        assert observed.visit_count == 0 and observed.search_count == 0
        assert visited.status is RegionStatus.VISITED

        progress = world.store.latest(BOAT, MessageType.ENVIRONMENT_PROGRESS)
        assert progress is not None
        assert progress.envelope.mission_id == "m-observed"
        assert progress.payload.known_region_count == 2
        assert progress.payload.searched_region_count == 0
        assert progress.payload.coverage_fraction == 0.0

        health = world.store.latest(BOAT, MessageType.SERVICE_HEALTH)
        assert health is not None
        services = {service.name: service for service in health.payload.services}
        assert services["environment-observation-ingest"].status is HealthStatus.OK
        assert services["environment-knowledge"].status is HealthStatus.OK
    finally:
        runtime.app.shutdown()


def test_explicit_step_mock_vessel_reports_state_and_stays_inhibited_after_safe_state(
    world: SimpleNamespace,
) -> None:
    boat_id = "boat-sim"
    world.registry.register(BoatIdentity(boat_id=boat_id, display_name="Mock simulation boat"))
    initial_position = LocalPoint(5.0, 5.0)
    vessel = MockVessel(
        VehicleState(timestamp=NOW, local_position=initial_position, heading_deg=0.0),
        speed_mps_at_full_thrust=2.0,
        turn_rate_deg_s_at_full_command=90.0,
    )
    link = LoopbackFmsLink(server=world.endpoint.receive)
    grid = GridIndexer()
    runtime = build_boat(
        AIBoxConfig(boat_id=boat_id),
        position=vessel,
        propulsion=vessel,
        fms_link=link,
        search_areas={"area-sim": SearchArea(0.0, 0.0, 20.0, 20.0)},
        indexer=grid,
    )
    runtime.app.start()
    try:
        assignment = world.fms_missions.assign(
            boat_id, "mission-sim", MissionAssignmentPayload(objective="test", search_area_id="area-sim")
        )
        link.deliver([assignment])
        for _ in range(3):
            runtime.app.tick()
            vessel.step(1.0)

        assert runtime.missions.active_mission is not None
        assert runtime.missions.active_mission.mission_id == "mission-sim"
        assert runtime.motion.goal is not None
        assert vessel.current_state().local_position == initial_position
        visited = runtime.knowledge.region(grid.region_of(initial_position))
        assert visited.status is RegionStatus.VISITED
        assert visited.search_count == 0

        safe_state = world.fms_missions.safe_state(
            boat_id, SafeStateAction.STOP_PROPULSION, reason="mock simulation stop"
        )
        link.deliver([safe_state])
        for _ in range(3):
            runtime.app.tick()
            vessel.step(1.0)

        assert runtime.motion.inhibited
        assert runtime.operating.mode is OperatingMode.SAFE_STATE
        assert runtime.missions.active_mission is not None
        assert runtime.motion.goal is not None
        assert vessel.current_state().local_position == initial_position
        assert vessel.current_state().heading_deg == 0.0
        assert world.outbox.unacknowledged(boat_id) == ()

        boat_state = world.store.latest(boat_id, MessageType.BOAT_STATE)
        assert boat_state is not None
        assert boat_state.payload.operating_mode is OperatingMode.SAFE_STATE
        assert boat_state.payload.position is None
        assert boat_state.payload.heading_deg == 0.0
        progress = world.store.latest(boat_id, MessageType.ENVIRONMENT_PROGRESS)
        assert progress is not None
        assert progress.envelope.mission_id == "mission-sim"
        assert progress.payload.searched_region_count == 0
        assert progress.payload.coverage_fraction == 0.0
    finally:
        runtime.app.shutdown()


def test_obstacle_detection_is_forwarded_as_summary_without_fabricated_risk(world):
    class OneRock:
        def detect(self, sample):
            return [Detection(bearing_deg=20.0, range_m=12.0, category="rock", confidence=0.9)]

    sample = SensorSample(sensor_id="front", kind=SensorKind.RANGE, timestamp=NOW, data={})
    runtime = build_boat(
        AIBoxConfig(boat_id=BOAT),
        position=world.position,
        propulsion=MockPropulsionSink(),
        fms_link=LoopbackFmsLink(server=world.endpoint.receive),
        sensors=[MockSensorAdapter("front", [[sample]])],
        detector=OneRock(),
    )
    runtime.app.start()
    try:
        runtime.app.tick()
        obstacles = world.store.history(BOAT, MessageType.OBSTACLE_SUMMARY)
    finally:
        runtime.app.shutdown()
    assert len(obstacles) == 1
    track = obstacles[0].payload.tracks[0]
    assert track.range_m == 12.0
    assert track.collision_risk is None


def test_simulator_adapter_failure_degrades_the_boat_without_crashing_it(world):
    runtime = build_boat(
        AIBoxConfig(boat_id=BOAT),
        position=world.position,
        propulsion=MockPropulsionSink(),
        fms_link=LoopbackFmsLink(server=world.endpoint.receive),
        sensors=[IsaacSimAdapter("front-camera")],
    )
    runtime.app.start()
    try:
        runtime.app.tick()
        runtime.app.tick()
        ingest = next(e for e in runtime.app.health_report() if e.name == "sensor-ingest")
    finally:
        runtime.app.shutdown()
    assert ingest.status.value == "degraded"
    assert "poll error" in ingest.detail


class _FixedOutputController:
    def compute(self, goal: NavigationGoal | None, state: VehicleState | None, now: datetime) -> PropulsionCommand:
        if goal is None:
            return PropulsionCommand.stop(now)
        return PropulsionCommand(timestamp=now, thrust=0.25, rudder=0.1)


class _SwitchableStopSink(MockPropulsionSink):
    fail_zero = False
    zero_attempts = 0

    def apply(self, command: PropulsionCommand) -> None:
        if command.thrust == 0.0 and command.rudder == 0.0:
            self.zero_attempts += 1
            if self.fail_zero:
                raise ConnectionError("recording sink rejected zero")
        super().apply(command)


@pytest.fixture
def moving(world: SimpleNamespace) -> Iterator[SimpleNamespace]:
    sink = _SwitchableStopSink()
    boat = build_boat(
        AIBoxConfig(boat_id=BOAT),
        position=world.position,
        propulsion=sink,
        fms_link=world.link,
        search_areas={"area-1": SearchArea(0.0, 0.0, 20.0, 20.0)},
        controller=_FixedOutputController(),
    )
    with boat.app:
        world.fms_missions.assign(BOAT, "m-1", MissionAssignmentPayload(objective="test", search_area_id="area-1"))
        _deliver_pending_commands(world)
        for _ in range(3):
            boat.app.tick()
        assert sink.last.thrust == 0.25
        try:
            yield SimpleNamespace(boat=boat, sink=sink, world=world)
        finally:
            sink.fail_zero = False


def _command(moving: SimpleNamespace, kind: MessageType, payload: BaseModel, mission_id: str | None = None) -> Envelope:
    command = make_envelope(
        boat_id=BOAT, message_type=kind, payload=payload, mission_id=mission_id, sequence_number=0, timestamp=NOW
    )
    moving.world.link.deliver([command])
    moving.boat.bridge.tick()
    return command


def _ack_message(moving: SimpleNamespace, command: Envelope) -> str:
    return next(
        e.message for e in moving.world.audit.entries() if e.category == "ack" and str(command.message_id) in e.message
    )


@pytest.mark.parametrize("mission_id", [None, "m-1", "other"])
@pytest.mark.parametrize("action", [SafeStateAction.STOP_PROPULSION, SafeStateAction.HOLD_POSITION])
@pytest.mark.parametrize("fail_zero", [False, True])
def test_safe_state_inhibits_regenerated_and_forced_goals(
    moving: SimpleNamespace, mission_id: str | None, action: SafeStateAction, fail_zero: bool
) -> None:
    moving.sink.fail_zero = fail_zero
    attempts = moving.sink.zero_attempts
    command = _command(moving, MessageType.SAFE_STATE_COMMAND, SafeStateCommandPayload(action=action), mission_id)
    assert moving.sink.zero_attempts == attempts + 1
    assert moving.boat.motion.inhibited
    assert moving.boat.operating.mode is OperatingMode.SAFE_STATE
    assert (moving.boat.missions.active_mission is None) == (mission_id == "m-1")
    moving.sink.fail_zero = False
    start = len(moving.sink.commands)
    for _ in range(3):
        moving.boat.app.tick()
    if mission_id == "m-1":
        assert moving.boat.motion.goal is None
    else:
        assert moving.boat.motion.goal is not None
        assert moving.boat.motion.goal.goal_id.startswith("m-1:")
    moving.boat.motion.set_goal(NavigationGoal(goal_id="forced", target=LocalPoint(50.0, 50.0)))
    for _ in range(3):
        moving.boat.app.tick()
    assert all(c.thrust == 0.0 and c.rudder == 0.0 for c in moving.sink.commands[start:])
    assert moving.boat.operating.mode is OperatingMode.SAFE_STATE
    assert ("rejected" if fail_zero else "accepted") in _ack_message(moving, command)
    if fail_zero and mission_id == "m-1":
        assert "cancelled locally" in _ack_message(moving, command)


def test_duplicate_safe_state_and_reconnect_cannot_rearm_motion(moving: SimpleNamespace) -> None:
    world = moving.world
    command = world.fms_missions.safe_state(BOAT, SafeStateAction.STOP_PROPULSION, reason="duplicate test")
    world.link.deliver([command, command])
    moving.boat.bridge.tick()
    moving.boat.bridge.tick()

    assert moving.boat.motion.inhibited
    assert moving.boat.operating.mode is OperatingMode.SAFE_STATE
    assert moving.sink.zero_attempts >= 2
    acknowledgements = [
        entry.message
        for entry in world.audit.entries()
        if entry.category == "ack" and str(command.message_id) in entry.message
    ]
    assert len(acknowledgements) == 2
    assert "queue cleared=True" in acknowledgements[0]
    assert "queue cleared=False" in acknowledgements[1]

    start = len(moving.sink.commands)
    world.link.set_online(False)
    assignment = world.fms_missions.assign(
        BOAT, "m-after-reconnect", MissionAssignmentPayload(objective="test", search_area_id="area-1")
    )
    _deliver_pending_commands(world)
    for _ in range(2):
        moving.boat.app.tick()
    assert world.outbox.unacknowledged(BOAT) == (assignment,)

    world.link.set_online(True)
    for _ in range(3):
        moving.boat.app.tick()

    assert moving.boat.motion.inhibited
    assert moving.boat.operating.mode is OperatingMode.SAFE_STATE
    assert moving.boat.missions.active_mission is not None
    assert moving.boat.missions.active_mission.mission_id == "m-1"
    assert all(command.thrust == 0.0 and command.rudder == 0.0 for command in moving.sink.commands[start:])
    assert world.outbox.unacknowledged(BOAT) == ()


def test_inhibited_assignment_is_rejected_directly_and_through_fms(moving: SimpleNamespace) -> None:
    _command(
        moving, MessageType.SAFE_STATE_COMMAND, SafeStateCommandPayload(action=SafeStateAction.STOP_PROPULSION), "m-1"
    )
    assert "inhibited" in moving.boat.missions.assign("m-2", "area-1")
    command = _command(
        moving,
        MessageType.MISSION_ASSIGNMENT,
        MissionAssignmentPayload(objective="test", search_area_id="area-1"),
        "m-2",
    )
    moving.boat.app.tick()
    assert "rejected" in _ack_message(moving, command)
    assert "inhibited" in _ack_message(moving, command)
    assert moving.boat.missions.active_mission is None
    assert moving.boat.operating.mode is OperatingMode.SAFE_STATE
    assert moving.sink.last.thrust == 0.0


@pytest.mark.parametrize("fail_zero", [False, True])
def test_cancellation_cleans_up_and_reports_stop_delivery(moving: SimpleNamespace, fail_zero: bool) -> None:
    moving.sink.fail_zero = fail_zero
    attempts = moving.sink.zero_attempts
    command = _command(moving, MessageType.MISSION_CANCELLATION, MissionCancellationPayload(reason="test"), "m-1")
    assert moving.sink.zero_attempts == attempts + 1
    assert moving.boat.missions.active_mission is None
    assert moving.boat.motion.goal is None
    assert moving.boat.motion.inhibited is fail_zero
    assert moving.boat.operating.mode is (OperatingMode.AUTONOMOUS if fail_zero else OperatingMode.IDLE)
    if not fail_zero:
        assert moving.sink.last.thrust == 0.0 and moving.sink.last.rudder == 0.0
    moving.sink.fail_zero = False
    moving.boat.app.tick()
    ack = _ack_message(moving, command)
    assert ("rejected" if fail_zero else "accepted") in ack
    if fail_zero:
        assert "cancelled locally" in ack and "zero command failed" in ack
    assert moving.world.store.latest(BOAT, MessageType.MISSION_PROGRESS).payload.status is MissionStatus.ABORTED


def test_duplicate_cancellation_cannot_cancel_a_later_mission(moving: SimpleNamespace) -> None:
    world = moving.world
    old_cancel = world.fms_missions.cancel(BOAT, "m-1", reason="operator request")
    world.link.deliver([old_cancel])
    moving.boat.bridge.tick()
    moving.boat.bridge.tick()
    assert moving.boat.missions.active_mission is None

    world.fms_missions.assign(BOAT, "m-2", MissionAssignmentPayload(objective="new mission", search_area_id="area-1"))
    _deliver_pending_commands(world)
    moving.boat.bridge.tick()
    moving.boat.bridge.tick()
    assert moving.boat.missions.active_mission is not None
    assert moving.boat.missions.active_mission.mission_id == "m-2"

    zero_attempts = moving.sink.zero_attempts
    world.link.deliver([old_cancel])
    moving.boat.bridge.tick()

    assert moving.sink.zero_attempts == zero_attempts
    assert moving.boat.missions.active_mission.mission_id == "m-2"
    assert not moving.boat.motion.inhibited
    moving.boat.bridge.tick()
    assert any(
        entry.category == "ack" and str(old_cancel.message_id) in entry.message and "rejected" in entry.message
        for entry in world.audit.entries()
    )


def test_mismatching_cancellation_does_not_stop_or_clear_the_active_mission(moving: SimpleNamespace) -> None:
    attempts = moving.sink.zero_attempts
    command = _command(moving, MessageType.MISSION_CANCELLATION, MissionCancellationPayload(reason="test"), "other")
    assert moving.sink.zero_attempts == attempts
    assert moving.boat.missions.active_mission.mission_id == "m-1"
    assert not moving.boat.motion.inhibited
    moving.boat.bridge.tick()
    assert "rejected" in _ack_message(moving, command)


def test_shutdown_completes_mission_cleanup_when_zero_delivery_fails(moving: SimpleNamespace) -> None:
    moving.sink.fail_zero = True
    moving.boat.app.shutdown()
    assert moving.boat.missions.active_mission is None
    assert moving.boat.motion.inhibited
    assert moving.boat.motion.health_detail()[0].value == "degraded"


def test_restarting_services_cannot_rearm_motion(moving: SimpleNamespace) -> None:
    moving.boat.app.shutdown()
    moving.boat.app.start()
    assert "inhibited" in moving.boat.missions.assign("m-2", "area-1")
    start = len(moving.sink.commands)
    moving.boat.motion.set_goal(NavigationGoal(goal_id="restart", target=LocalPoint(50.0, 50.0)))
    for _ in range(3):
        moving.boat.app.tick()
    assert moving.boat.motion.inhibited
    assert all(c.thrust == 0.0 and c.rudder == 0.0 for c in moving.sink.commands[start:])
