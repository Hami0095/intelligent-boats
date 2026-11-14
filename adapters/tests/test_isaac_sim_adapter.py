"""Isaac Sim adapter tests. They use a fake backend, never a real simulator.

The `isaacsim` import is blocked explicitly where it matters, so these tests give the
same result on a machine that has Isaac Sim installed.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from typing import Any

import pytest
from adapters.simulation.isaac_sim.adapter import IsaacSimAdapter
from adapters.simulation.isaac_sim.backend import BoatPose, SimulatorUnavailableError
from adapters.simulation.isaac_sim.isaac_backend import IsaacSimBackend, open_isaac_backend
from ai_box.core.ports import SensorKind
from ai_box.motion.commands import PropulsionCommand

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


class FakeBackend:
    def __init__(self, pose: BoatPose | None = None, fail_read: bool = False) -> None:
        self.pose = pose or BoatPose(x_m=10.0, y_m=-4.0, heading_deg=370.0, speed_mps=1.5)
        self.fail_read = fail_read
        self.commands: list[tuple[float, float]] = []
        self.closed = 0

    def read_pose(self) -> BoatPose:
        if self.fail_read:
            raise RuntimeError("simulator hiccup")
        return self.pose

    def write_command(self, thrust: float, rudder: float) -> None:
        self.commands.append((thrust, rudder))

    def close(self) -> None:
        self.closed += 1


def _clock() -> datetime:
    return T0


def test_without_backend_poll_and_apply_raise_and_state_stays_empty():
    adapter = IsaacSimAdapter("front", clock=_clock)
    with pytest.raises(SimulatorUnavailableError):
        adapter.poll()
    with pytest.raises(SimulatorUnavailableError):
        adapter.apply(PropulsionCommand.stop(T0))
    assert adapter.current_state() is None


def test_poll_returns_one_position_sample_and_updates_current_state():
    adapter = IsaacSimAdapter("front", backend=FakeBackend(), clock=_clock)
    samples = adapter.poll()
    assert len(samples) == 1
    sample = samples[0]
    assert sample.sensor_id == "front"
    assert sample.kind is SensorKind.POSITION_FIX
    assert sample.timestamp == T0
    assert sample.data == {"x_m": 10.0, "y_m": -4.0, "heading_deg": 10.0, "speed_mps": 1.5}

    state = adapter.current_state()
    assert state is not None
    assert state.local_position is not None
    assert (state.local_position.x_m, state.local_position.y_m) == (10.0, -4.0)
    assert state.heading_deg == pytest.approx(10.0)
    assert state.speed_over_ground_mps == 1.5
    assert state.geo_position is None


def test_apply_forwards_the_normalised_command_to_the_backend():
    backend = FakeBackend()
    adapter = IsaacSimAdapter("front", backend=backend, clock=_clock)
    adapter.apply(PropulsionCommand(timestamp=T0, thrust=0.5, rudder=-0.25))
    assert backend.commands == [(0.5, -0.25)]


def test_backend_read_failure_propagates_so_the_ai_box_can_report_degraded():
    adapter = IsaacSimAdapter("front", backend=FakeBackend(fail_read=True), clock=_clock)
    with pytest.raises(RuntimeError, match="simulator hiccup"):
        adapter.poll()
    assert adapter.current_state() is None


def test_non_finite_pose_is_rejected_at_the_value_type():
    with pytest.raises(ValueError, match="x_m must be finite"):
        BoatPose(x_m=float("nan"), y_m=0.0, heading_deg=0.0, speed_mps=0.0)


def test_open_isaac_backend_requires_a_usd_path():
    with pytest.raises(ValueError, match="AIBOX_SIM_USD_PATH"):
        open_isaac_backend(None)
    with pytest.raises(ValueError):
        open_isaac_backend("")


def test_open_isaac_backend_reports_unavailable_when_isaacsim_is_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "isaacsim", None)
    with pytest.raises(SimulatorUnavailableError, match="not installed"):
        open_isaac_backend("boat.usd")


class _FakeApp:
    def __init__(self) -> None:
        self.closed = 0

    def close(self) -> None:
        self.closed += 1


def test_real_backend_pose_and_command_steps_are_not_bound_yet_and_say_so():
    backend = IsaacSimBackend(app=_FakeApp(), usd_path="boat.usd")
    with pytest.raises(SimulatorUnavailableError, match="not implemented yet"):
        backend.read_pose()
    with pytest.raises(SimulatorUnavailableError, match="not implemented yet"):
        backend.write_command(0.0, 0.0)


def test_real_backend_close_is_idempotent():
    app: Any = _FakeApp()
    backend = IsaacSimBackend(app=app, usd_path="boat.usd")
    backend.close()
    backend.close()
    assert app.closed == 1
