"""NVIDIA Isaac Sim integration boundary.

Isaac Sim is the FINAL demonstration environment only. It is not the runtime
architecture and must never be imported by ai_box/, fms/ or interfaces/.
Only this folder may import the simulator. See docs/INTEGRATION_GUIDE.md and ADR-0009.
"""

from adapters.simulation.isaac_sim.adapter import IsaacSimAdapter
from adapters.simulation.isaac_sim.backend import BoatPose, SimulatorBackend, SimulatorUnavailableError

__all__ = ["BoatPose", "IsaacSimAdapter", "SimulatorBackend", "SimulatorUnavailableError"]
