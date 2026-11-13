"""NVIDIA Isaac Sim integration boundary.

Isaac Sim is the FINAL demonstration environment only. It is not the runtime
architecture and must never be imported by ai_box/, fms/ or interfaces/.
See docs/INTEGRATION_GUIDE.md.
"""

from adapters.simulation.isaac_sim.adapter import IsaacSimAdapter

__all__ = ["IsaacSimAdapter"]
