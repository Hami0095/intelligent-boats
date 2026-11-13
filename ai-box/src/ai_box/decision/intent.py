"""A high-level movement intention produced by decision-making."""

from __future__ import annotations

from dataclasses import dataclass

from ai_box.core.geometry import LocalPoint


@dataclass(frozen=True)
class NavigationIntent:
    target: LocalPoint
    reason: str
    mission_id: str | None = None
