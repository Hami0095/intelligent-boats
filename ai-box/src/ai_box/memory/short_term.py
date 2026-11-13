"""Short-term operational memory: bounded, newest-first, age-limited."""

from __future__ import annotations

from collections import deque
from datetime import datetime

from ai_box.memory.records import MemoryRecord


class ShortTermMemory:
    def __init__(self, capacity: int, max_age_s: float) -> None:
        if capacity <= 0 or max_age_s <= 0:
            raise ValueError("capacity and max_age_s must be positive")
        self._items: deque[MemoryRecord] = deque(maxlen=capacity)
        self._max_age_s = max_age_s

    def __len__(self) -> int:
        return len(self._items)

    def put(self, record: MemoryRecord) -> None:
        self._items.append(record)

    def recent(self, now: datetime) -> list[MemoryRecord]:
        """Non-stale records, newest first."""
        return [r for r in reversed(self._items) if not r.is_stale(now, self._max_age_s)]
