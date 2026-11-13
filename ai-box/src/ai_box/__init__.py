"""AI Box: the onboard software environment of one autonomous boat.

The AI Box is NOT a single model. It is a set of independent Services managed by
core.manager, communicating through an in-process event bus and typed contracts.
It must never import Isaac Sim or any vendor SDK. See ai-box/CLAUDE.md.
"""

__version__ = "0.1.0"
