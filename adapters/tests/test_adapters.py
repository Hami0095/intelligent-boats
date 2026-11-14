import math
from datetime import datetime, timedelta, timezone

import pytest
from adapters.fms.loopback import LoopbackFmsLink
from adapters.propulsion.mock import MockPropulsionSink
from adapters.sensors.mock import MockPositionSource, MockSensorAdapter
from adapters.simulation.isaac_sim import IsaacSimAdapter
from adapters.simulation.mock_vessel import MockVessel
from ai_box.core.geometry import LocalPoint
from ai_box.core.ports import SensorKind, SensorSample
from ai_box.motion.commands import PropulsionCommand, VehicleState
from marine_contracts import BoatStatePayload, MessageType, OperatingMode, make_envelope

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_mock_sensor_replays_batches_then_goes_quiet():
    sample = SensorSample(sensor_id="cam", kind=SensorKind.CAMERA_FRAME, timestamp=T0, data={})
    sensor = MockSensorAdapter("cam", [[sample], []])
    assert sensor.sensor_id == "cam"
    assert list(sensor.poll()) == [sample]
    assert list(sensor.poll()) == []
    assert list(sensor.poll()) == []


def test_mock_position_source_reports_what_it_was_given():
    position = MockPositionSource()
    assert position.current_state() is None
    state = VehicleState(timestamp=T0, local_position=LocalPoint(1, 2))
    position.set_state(state)
    assert position.current_state() == state


def test_mock_propulsion_records_normalised_commands_in_order():
    sink = MockPropulsionSink()
    sink.apply(PropulsionCommand(timestamp=T0, thrust=0.5, rudder=0.0))
    sink.apply(PropulsionCommand.stop(T0))
    assert [c.thrust for c in sink.commands] == [0.5, 0.0]
    assert sink.last == PropulsionCommand.stop(T0)


def test_loopback_link_simulates_disconnection():
    link = LoopbackFmsLink(server=lambda env: [])
    env = make_envelope(
        boat_id="boat-01",
        message_type=MessageType.BOAT_STATE,
        payload=BoatStatePayload(operating_mode=OperatingMode.IDLE),
        sequence_number=0,
        timestamp=T0,
    )
    link.set_online(False)
    with pytest.raises(ConnectionError):
        link.send(env)
    with pytest.raises(ConnectionError):
        link.receive()


def test_loopback_link_returns_server_replies_once():
    replies = [
        make_envelope(
            boat_id="boat-01",
            message_type=MessageType.BOAT_STATE,
            payload=BoatStatePayload(operating_mode=OperatingMode.IDLE),
            sequence_number=1,
            timestamp=T0,
        )
    ]
    link = LoopbackFmsLink(server=lambda env: replies)
    link.send(replies[0])
    assert link.receive() == replies
    assert link.receive() == []


def test_isaac_sim_placeholder_fails_loudly_and_never_pretends_to_work():
    adapter = IsaacSimAdapter("front-camera")
    assert adapter.sensor_id == "front-camera"
    with pytest.raises(NotImplementedError, match="Isaac Sim"):
        adapter.poll()
    with pytest.raises(NotImplementedError):
        adapter.apply(PropulsionCommand.stop(T0))


def test_mock_vessel_updates_state_on_an_explicit_command_step():
    initial = VehicleState(timestamp=T0, local_position=LocalPoint(0.0, 0.0), heading_deg=0.0)
    vessel = MockVessel(
        initial,
        speed_mps_at_full_thrust=2.0,
        turn_rate_deg_s_at_full_command=90.0,
    )
    vessel.apply(PropulsionCommand(timestamp=T0, thrust=0.5, rudder=0.5))

    moved = vessel.step(1.0)

    assert moved.timestamp == T0 + timedelta(seconds=1)
    assert moved.heading_deg == pytest.approx(22.5)
    assert moved.local_position.x_m == pytest.approx(math.cos(math.radians(22.5)))
    assert moved.local_position.y_m == pytest.approx(math.sin(math.radians(22.5)))
    assert moved.geo_position is None
    assert moved.speed_over_ground_mps is None

    next_step = vessel.step(1.0)
    assert next_step.local_position == moved.local_position
    assert next_step.heading_deg == moved.heading_deg


@pytest.mark.parametrize("duration_s", [0.0, -1.0, float("nan"), float("inf"), True])
def test_mock_vessel_rejects_invalid_step_duration(duration_s):
    initial = VehicleState(timestamp=T0, local_position=LocalPoint(0.0, 0.0), heading_deg=0.0)
    vessel = MockVessel(initial, speed_mps_at_full_thrust=1.0, turn_rate_deg_s_at_full_command=0.0)

    with pytest.raises(ValueError, match="duration_s"):
        vessel.step(duration_s)

    assert vessel.current_state() == initial


def test_mock_vessel_rejects_nonfinite_state_without_advancing():
    initial = VehicleState(timestamp=T0, local_position=LocalPoint(float("nan"), 0.0), heading_deg=0.0)
    vessel = MockVessel(initial, speed_mps_at_full_thrust=1.0, turn_rate_deg_s_at_full_command=0.0)
    vessel.apply(PropulsionCommand(timestamp=T0, thrust=0.5, rudder=0.0))

    with pytest.raises(ValueError, match="state.local_position.x_m"):
        vessel.step(1.0)

    assert vessel.current_state() == initial


def test_mock_vessel_rejects_nonzero_command_without_position_or_heading():
    initial = VehicleState(timestamp=T0)
    vessel = MockVessel(initial, speed_mps_at_full_thrust=1.0, turn_rate_deg_s_at_full_command=0.0)
    vessel.apply(PropulsionCommand(timestamp=T0, thrust=0.5, rudder=0.0))

    with pytest.raises(ValueError, match="require local position and heading"):
        vessel.step(1.0)

    assert vessel.current_state() == initial


def test_mock_vessel_rejects_nonfinite_command_without_retaining_it():
    initial = VehicleState(timestamp=T0, local_position=LocalPoint(0.0, 0.0), heading_deg=0.0)
    vessel = MockVessel(initial, speed_mps_at_full_thrust=1.0, turn_rate_deg_s_at_full_command=0.0)

    with pytest.raises(ValueError, match="thrust"):
        vessel.apply(PropulsionCommand(timestamp=T0, thrust=float("nan"), rudder=0.0))

    assert vessel.step(1.0).local_position == initial.local_position
