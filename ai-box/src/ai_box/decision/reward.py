"""Reward interface. The reward definition is not yet provided (OPEN decision).

NoReward is a placeholder: it reports that no reward information exists. It must
never be read as "zero reward".
"""

from __future__ import annotations

from typing import Protocol

from ai_box.environment.observations import EnvironmentObservation


class RewardSignal(Protocol):
    def evaluate(self, observation: EnvironmentObservation) -> float | None: ...


class NoReward:
    def evaluate(self, observation: EnvironmentObservation) -> float | None:
        return None
