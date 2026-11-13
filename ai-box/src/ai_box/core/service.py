"""Lifecycle contract for every long-lived AI Box component.

A Service declares a unique `name` and the names of services that must start
before it (`depends_on`). The ServiceManager derives the start order from those.
`tick()` is the cooperative periodic hook; the (not yet built) runtime loop calls it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from marine_contracts import HealthStatus

from ai_box.config.settings import AIBoxConfig
from ai_box.core.events import EventBus


@dataclass(frozen=True)
class ServiceContext:
    bus: EventBus
    config: AIBoxConfig


class Service(ABC):
    name: str = ""
    depends_on: tuple[str, ...] = ()

    @abstractmethod
    def start(self, ctx: ServiceContext) -> None:
        """Acquire resources and subscribe to topics. Raise to signal a failed start."""

    @abstractmethod
    def stop(self) -> None:
        """Release resources. Must be safe to call even if start partly failed."""

    def tick(self) -> None:
        """Periodic work. Default: nothing to do."""

    def health_detail(self) -> tuple[HealthStatus, str]:
        """Service-specific health. Only consulted while the service is started and not failing."""
        return HealthStatus.OK, ""
