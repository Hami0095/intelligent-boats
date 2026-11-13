"""Persistence boundary for long-lived knowledge.

The backing technology (file, database, FMS sync) is an OPEN decision. This
module defines the interface and an in-memory implementation for the foundation.
"""

from __future__ import annotations

from typing import Generic, Protocol, TypeVar

T = TypeVar("T")


class PersistentStore(Protocol[T]):
    def append(self, item: T) -> None: ...

    def items(self) -> tuple[T, ...]: ...


class InMemoryStore(Generic[T]):
    """Lost on restart. Use only for tests and the foundation build."""

    def __init__(self) -> None:
        self._items: list[T] = []

    def append(self, item: T) -> None:
        self._items.append(item)

    def items(self) -> tuple[T, ...]:
        return tuple(self._items)
