"""Boat identities. Only registered boats may exchange messages with the FMS."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BoatIdentity:
    boat_id: str
    display_name: str


class UnregisteredBoatError(LookupError):
    """A message arrived from, or a command targeted, a boat the FMS does not know."""


class FleetRegistry:
    def __init__(self) -> None:
        self._boats: dict[str, BoatIdentity] = {}

    def register(self, identity: BoatIdentity) -> None:
        if identity.boat_id in self._boats:
            raise ValueError(f"boat {identity.boat_id!r} is already registered")
        self._boats[identity.boat_id] = identity

    def is_registered(self, boat_id: str) -> bool:
        return boat_id in self._boats

    def require(self, boat_id: str) -> BoatIdentity:
        identity = self._boats.get(boat_id)
        if identity is None:
            raise UnregisteredBoatError(f"unknown boat {boat_id!r}")
        return identity

    def all(self) -> tuple[BoatIdentity, ...]:
        return tuple(self._boats.values())
