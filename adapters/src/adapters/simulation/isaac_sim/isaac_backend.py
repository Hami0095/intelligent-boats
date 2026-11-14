"""Real Isaac Sim backend. The only module in the repository that imports `isaacsim`.

Implemented: starting the simulator headless and closing it.

Not yet implemented: reading the boat pose and writing commands. Both need the CAD
boat asset and the articulation API of the Isaac Sim version installed on the RUG
machine. Until then they raise SimulatorUnavailableError, so the AI Box reports the
sensor as degraded and keeps running. The usd_path is stored for that step.
"""

from __future__ import annotations

from typing import Any

from adapters.simulation.isaac_sim.backend import BoatPose, SimulatorUnavailableError

_NOT_BOUND = (
    "Isaac Sim boat binding is not implemented yet: it needs the CAD boat asset and "
    "the articulation API of the installed Isaac Sim version"
)


def open_isaac_backend(usd_path: str | None) -> IsaacSimBackend:
    """Start Isaac Sim headless. Raises SimulatorUnavailableError if isaacsim cannot be imported.

    `usd_path` should come from AIBOX_SIM_USD_PATH. It is required even though
    loading the stage is not implemented yet, so a missing setting fails early.
    """
    if not usd_path:
        raise ValueError("usd_path is required (set AIBOX_SIM_USD_PATH)")
    try:
        from isaacsim import SimulationApp  # type: ignore[import-not-found]
    except ImportError as exc:
        raise SimulatorUnavailableError("isaacsim is not installed") from exc
    app = SimulationApp({"headless": True})
    return IsaacSimBackend(app=app, usd_path=usd_path)


class IsaacSimBackend:
    def __init__(self, app: Any, usd_path: str) -> None:
        self._app = app
        self._usd_path = usd_path
        self._closed = False

    @property
    def usd_path(self) -> str:
        return self._usd_path

    def read_pose(self) -> BoatPose:
        raise SimulatorUnavailableError(_NOT_BOUND)

    def write_command(self, thrust: float, rudder: float) -> None:
        raise SimulatorUnavailableError(_NOT_BOUND)

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._app.close()
