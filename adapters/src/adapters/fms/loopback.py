"""In-process link that hands envelopes straight to an FMS endpoint.

Used for integration tests. `set_online(False)` simulates a dropped connection:
send() then raises ConnectionError, which is what the AI Box bridge expects.
"""

from __future__ import annotations

from collections.abc import Callable

from marine_contracts import Envelope


class LoopbackFmsLink:
    def __init__(self, server: Callable[[Envelope], list[Envelope]]) -> None:
        self._server = server
        self._online = True
        self._inbox: list[Envelope] = []

    def set_online(self, online: bool) -> None:
        self._online = online

    def send(self, envelope: Envelope) -> None:
        if not self._online:
            raise ConnectionError("loopback link is offline")
        self._inbox.extend(self._server(envelope))

    def deliver(self, envelopes: list[Envelope]) -> None:
        """Queue FMS -> boat messages for the boat's next receive()."""
        self._inbox.extend(envelopes)

    def receive(self) -> list[Envelope]:
        if not self._online:
            raise ConnectionError("loopback link is offline")
        messages, self._inbox = self._inbox, []
        return messages
