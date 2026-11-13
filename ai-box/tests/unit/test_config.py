import pytest
from ai_box.config.settings import AIBoxConfig, load_config
from pydantic import ValidationError


def test_defaults_are_usable_without_any_environment():
    config = load_config({})
    assert config.boat_id == "boat-dev-01"
    assert config.outbound_buffer_limit > 0


def test_aibox_variables_are_read_and_coerced():
    config = load_config(
        {"AIBOX_BOAT_ID": "boat-07", "AIBOX_TELEMETRY_INTERVAL_S": "2.5", "AIBOX_OUTBOUND_BUFFER_LIMIT": "10"}
    )
    assert config.boat_id == "boat-07"
    assert config.telemetry_interval_s == 2.5
    assert config.outbound_buffer_limit == 10


def test_unrelated_environment_variables_are_ignored():
    assert load_config({"PATH": "/usr/bin", "HOME": "/root"}).boat_id == "boat-dev-01"


def test_misspelled_aibox_variable_is_an_error():
    with pytest.raises(ValidationError):
        load_config({"AIBOX_BOAT_IDD": "boat-07"})


def test_invalid_boat_id_is_rejected():
    with pytest.raises(ValidationError):
        AIBoxConfig(boat_id="Boat One")


def test_log_level_is_restricted():
    with pytest.raises(ValidationError):
        AIBoxConfig(log_level="TRACE")
