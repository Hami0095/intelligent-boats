"""Region indexing: how continuous positions map to the discrete regions the knowledge base tracks.

GridIndexer is a placeholder implementation. The real partitioning scheme is an
OPEN decision and must be swappable without touching knowledge or decision code.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol

from ai_box.core.geometry import LocalPoint

RegionId = str


@dataclass(frozen=True)
class SearchArea:
    min_x_m: float
    min_y_m: float
    max_x_m: float
    max_y_m: float

    def __post_init__(self) -> None:
        if self.min_x_m > self.max_x_m or self.min_y_m > self.max_y_m:
            raise ValueError("search area minimum must not exceed maximum")

    def contains(self, point: LocalPoint) -> bool:
        return self.min_x_m <= point.x_m <= self.max_x_m and self.min_y_m <= point.y_m <= self.max_y_m


class RegionIndexer(Protocol):
    def region_of(self, point: LocalPoint) -> RegionId: ...

    def center_of(self, region: RegionId) -> LocalPoint: ...

    def regions_in(self, area: SearchArea) -> list[RegionId]: ...


_PREFIX = "grid:"


class GridIndexer:
    """Square cells of a fixed size. Placeholder scheme; cell size is not a confirmed requirement."""

    def __init__(self, cell_size_m: float = 10.0) -> None:
        if cell_size_m <= 0.0:
            raise ValueError("cell_size_m must be positive")
        self._size = cell_size_m

    def region_of(self, point: LocalPoint) -> RegionId:
        return _format(math.floor(point.x_m / self._size), math.floor(point.y_m / self._size))

    def center_of(self, region: RegionId) -> LocalPoint:
        ix, iy = _parse(region)
        return LocalPoint((ix + 0.5) * self._size, (iy + 0.5) * self._size)

    def regions_in(self, area: SearchArea) -> list[RegionId]:
        ix0 = math.floor(area.min_x_m / self._size)
        ix1 = math.floor(area.max_x_m / self._size)
        iy0 = math.floor(area.min_y_m / self._size)
        iy1 = math.floor(area.max_y_m / self._size)
        return [_format(ix, iy) for ix in range(ix0, ix1 + 1) for iy in range(iy0, iy1 + 1)]


def _format(ix: int, iy: int) -> RegionId:
    return f"{_PREFIX}{ix}:{iy}"


def _parse(region: RegionId) -> tuple[int, int]:
    if not region.startswith(_PREFIX):
        raise ValueError(f"not a grid region id: {region!r}")
    ix, iy = region[len(_PREFIX):].split(":")
    return int(ix), int(iy)
