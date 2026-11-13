"""Top-level handle on a running AI Box: owns the bus and the service manager."""

from __future__ import annotations

from marine_contracts import ServiceHealthEntry

from ai_box.config.settings import AIBoxConfig
from ai_box.core.events import EventBus
from ai_box.core.manager import ServiceManager
from ai_box.core.service import Service


class AIBoxApp:
    def __init__(self, config: AIBoxConfig, *, bus: EventBus | None = None) -> None:
        self.config = config
        self.bus = bus or EventBus()
        self.manager = ServiceManager(self.bus, config)

    def register(self, service: Service) -> None:
        self.manager.register(service)

    def start(self) -> None:
        self.manager.start_all()

    def tick(self) -> None:
        self.manager.tick_all()

    def shutdown(self) -> None:
        self.manager.stop_all()

    def health_report(self) -> list[ServiceHealthEntry]:
        return self.manager.health_report()

    def __enter__(self) -> AIBoxApp:
        self.start()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.shutdown()
