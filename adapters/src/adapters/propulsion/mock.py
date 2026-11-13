"""Records every normalised propulsion command it receives."""

from __future__ import annotations

from ai_box.motion.commands import PropulsionCommand


class MockPropulsionSink:
    def __init__(self) -> None:
        self._commands: list[PropulsionCommand] = []

    def apply(self, command: PropulsionCommand) -> None:
        self._commands.append(command)

    @property
    def commands(self) -> tuple[PropulsionCommand, ...]:
        return tuple(self._commands)

    @property
    def last(self) -> PropulsionCommand | None:
        return self._commands[-1] if self._commands else None
