"""Payload-level validation and registry completeness."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from marine_contracts import (
    MESSAGE_SPECS,
    AcknowledgementPayload,
    BoatStatePayload,
    ConfigurationUpdatePayload,
    EnvironmentProgressPayload,
    GeoPosition,
    HealthStatus,
    MessageType,
    MissionAssignmentPayload,
    MissionCancellationPayload,
    MissionProgressPayload,
    MissionStatus,
    NavigationGoalPayload,
    ObstacleSummaryPayload,
    ObstacleTrack,
    OperatingMode,
    OperationalEventPayload,
    Provenance,
    SafeStateAction,
    SafeStateCommandPayload,
    ServiceHealthEntry,
    ServiceHealthPayload,
    Severity,
    StrictModel,
)
from pydantic import ValidationError

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _track(**overrides):
    base = dict(track_id="t-1", relative_bearing_deg=10.0, confidence=0.8, provenance=Provenance(source="sensor:front"))
    base.update(overrides)
    return ObstacleTrack(**base)


SAMPLE_PAYLOADS = {
    MessageType.BOAT_STATE: BoatStatePayload(operating_mode=OperatingMode.IDLE),
    MessageType.MISSION_PROGRESS: MissionProgressPayload(status=MissionStatus.IN_PROGRESS, completion_fraction=0.5),
    MessageType.OBSTACLE_SUMMARY: ObstacleSummaryPayload(tracks=[_track()]),
    MessageType.ENVIRONMENT_PROGRESS: EnvironmentProgressPayload(searched_region_count=1, known_region_count=3),
    MessageType.OPERATIONAL_EVENT: OperationalEventPayload(
        severity=Severity.WARNING, code="sensor.timeout", message="no data"
    ),
    MessageType.SERVICE_HEALTH: ServiceHealthPayload(
        services=[ServiceHealthEntry(name="motion", status=HealthStatus.OK)]
    ),
    MessageType.MISSION_ASSIGNMENT: MissionAssignmentPayload(objective="search", search_area_id="area-1"),
    MessageType.NAVIGATION_GOAL: NavigationGoalPayload(
        goal_id="g-1", target=GeoPosition(latitude_deg=1, longitude_deg=2)
    ),
    MessageType.MISSION_CANCELLATION: MissionCancellationPayload(reason="operator"),
    MessageType.CONFIGURATION_UPDATE: ConfigurationUpdatePayload(
        config_version="1", parameters={"a": 1, "b": True, "c": "x", "d": 1.5}
    ),
    MessageType.SAFE_STATE_COMMAND: SafeStateCommandPayload(action=SafeStateAction.HOLD_POSITION),
    MessageType.ACKNOWLEDGEMENT: AcknowledgementPayload(acknowledged_message_id=uuid4(), accepted=True),
}


def test_every_message_type_has_a_registered_spec_and_sample():
    assert set(MESSAGE_SPECS) == set(MessageType)
    assert set(SAMPLE_PAYLOADS) == set(MessageType)
    for message_type, sample in SAMPLE_PAYLOADS.items():
        assert isinstance(sample, MESSAGE_SPECS[message_type].model)


def test_every_payload_model_is_strict_and_immutable():
    for spec in MESSAGE_SPECS.values():
        assert issubclass(spec.model, StrictModel)
        assert spec.model.model_config["extra"] == "forbid"
        assert spec.model.model_config["frozen"] is True


@pytest.mark.parametrize(
    "kwargs",
    [
        {"operating_mode": OperatingMode.IDLE, "heading_deg": 360.0},
        {"operating_mode": OperatingMode.IDLE, "battery_state_of_charge": 1.5},
        {"operating_mode": OperatingMode.IDLE, "speed_over_ground_mps": -0.1},
    ],
)
def test_boat_state_rejects_out_of_range_values(kwargs):
    with pytest.raises(ValidationError):
        BoatStatePayload(**kwargs)


def test_geo_position_rejects_impossible_latitude():
    with pytest.raises(ValidationError):
        GeoPosition(latitude_deg=91.0, longitude_deg=0.0)


def test_obstacle_track_collision_risk_may_be_unknown():
    assert _track(collision_risk=None).collision_risk is None


def test_obstacle_track_rejects_bearing_outside_range():
    with pytest.raises(ValidationError):
        _track(relative_bearing_deg=200.0)


def test_event_code_must_be_machine_readable():
    with pytest.raises(ValidationError):
        OperationalEventPayload(severity=Severity.INFO, code="Sensor Timeout")


def test_assignment_time_limit_must_be_positive():
    with pytest.raises(ValidationError):
        MissionAssignmentPayload(objective="search", search_area_id="a", time_limit_s=0)


def test_navigation_goal_acceptance_radius_must_be_positive():
    with pytest.raises(ValidationError):
        NavigationGoalPayload(goal_id="g", target=GeoPosition(latitude_deg=0, longitude_deg=0), acceptance_radius_m=0.0)


def test_configuration_parameters_reject_nested_values():
    with pytest.raises(ValidationError):
        ConfigurationUpdatePayload(config_version="1", parameters={"a": [1, 2]})
