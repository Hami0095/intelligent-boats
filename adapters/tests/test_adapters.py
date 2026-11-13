from datetime import datetime, timezone

import pytest
from adapters.fms.loopback import LoopbackFmsLink
from adapters.propulsion.mock import MockPropulsionSink
from adapters.sensors.mock import MockPositionSource, MockSensorAdapter
from adapters.simulation.isaac_sim import IsaacSimAdapter
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
