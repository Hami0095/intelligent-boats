"""Mission memory: which regions this mission has already covered. Cleared when the mission ends."""

from __future__ import annotations


class MissionMemory:
    def __init__(self) -> None:
        self._visited: dict[str, set[str]] = {}

    def record_visit(self, mission_id: str, region_id: str) -> None:
        self._visited.setdefault(mission_id, set()).add(region_id)

    def visited_regions(self, mission_id: str) -> frozenset[str]:
        return frozenset(self._visited.get(mission_id, set()))

    def forget(self, mission_id: str) -> None:
        self._visited.pop(mission_id, None)
