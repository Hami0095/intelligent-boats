"""End-to-end: a boat built from mock adapters, talking to a real FMS endpoint over a loopback link."""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from adapters.fms.loopback import LoopbackFmsLink
from adapters.propulsion.mock import MockPropulsionSink
from adapters.sensors.mock import MockPositionSource, MockSensorAdapter
from adapters.simulation.isaac_sim.adapter import IsaacSimAdapter
from ai_box.bootstrap import build_boat
from ai_box.config.settings import AIBoxConfig
from ai_box.core.geometry import LocalPoint
from ai_box.core.ports import Detection, SensorKind, SensorSample
from ai_box.environment.model import SearchArea
from ai_box.motion.commands import VehicleState
from ai_box.services.command_router import NOT_IMPLEMENTED_NAV
from fms.communication.outbox import Outbox
from fms.core.endpoint import FmsEndpoint
from fms.core.fleet import BoatIdentity, FleetRegistry, UnregisteredBoatError
from fms.data.store import InMemoryFleetStore
from fms.logging.audit import AuditLog
from fms.missions.service import MissionService as FmsMissionService
from marine_contracts import (
    BoatStatePayload,
    GeoPosition,
    MessageType,
    MissionAssignmentPayload,
    MissionStatus,
    NavigationGoalPayload,
    OperatingMode,
    SafeStateAction,
    make_envelope,
)

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
    assert latest.payload.operating_mode is OperatingMode.IDLE
    assert latest.payload.position == GeoPosition(latitude_deg=59.3, longitude_deg=18.0)


def test_mission_assignment_is_accepted_and_the_boat_starts_searching(world):
    world.fms_missions.assign(BOAT, "m-1", MissionAssignmentPayload(objective="find target", search_area_id="area-1"))
    _deliver_pending_commands(world)

    for _ in range(3):
        world.runtime.app.tick()

    assert world.runtime.missions.active_mission is not None
    assert world.runtime.missions.active_mission.mission_id == "m-1"
    assert world.runtime.operating.mode is OperatingMode.AUTONOMOUS
    assert world.runtime.motion.goal is not None

    progress = world.store.latest(BOAT, MessageType.MISSION_PROGRESS)
    assert progress is not None and progress.payload.status is MissionStatus.ACCEPTED
    assert world.outbox.unacknowledged(BOAT) == ()  # the boat's acknowledgement cleared the FMS queue


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
    assert world.runtime.knowledge.region(world.runtime.missions.active_mission.regions[0]).visit_count >= 1


def test_safe_state_command_stops_propulsion_and_is_acknowledged(world):
    world.fms_missions.safe_state(BOAT, SafeStateAction.STOP_PROPULSION, reason="test")
    _deliver_pending_commands(world)
    world.runtime.app.tick()
    world.runtime.app.tick()

    assert world.runtime.operating.mode is OperatingMode.SAFE_STATE
    assert world.sink.last is not None
    assert world.sink.last.thrust == 0.0 and world.sink.last.rudder == 0.0
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
