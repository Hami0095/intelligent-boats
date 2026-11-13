"""Registers services, derives their start order, and tracks their health."""

from __future__ import annotations

import logging

from marine_contracts import HealthStatus, ServiceHealthEntry

from ai_box.config.settings import AIBoxConfig
from ai_box.core.events import EventBus
from ai_box.core.service import Service, ServiceContext

log = logging.getLogger("ai_box.manager")


class ServiceError(RuntimeError):
    """Misconfiguration of the service graph (duplicate names, unknown or cyclic dependencies)."""


class ServiceStartError(ServiceError):
    """A service raised while starting. Services started before it have been stopped again."""


class ServiceManager:
    def __init__(self, bus: EventBus, config: AIBoxConfig) -> None:
        self._ctx = ServiceContext(bus=bus, config=config)
        self._services: dict[str, Service] = {}
        self._status: dict[str, HealthStatus] = {}
        self._start_errors: dict[str, str] = {}
        self._tick_errors: dict[str, str] = {}
        self._started: list[Service] = []

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(self._services)

    def register(self, service: Service) -> None:
        if not service.name:
            raise ServiceError(f"{type(service).__name__} must define a non-empty name")
        if service.name in self._services:
            raise ServiceError(f"duplicate service name {service.name!r}")
        if self._started:
            raise ServiceError("services cannot be registered after startup")
        self._services[service.name] = service
        self._status[service.name] = HealthStatus.NOT_STARTED

    def start_order(self) -> list[str]:
        """Topological order of dependencies. Registration order breaks ties."""
        for svc in self._services.values():
            for dep in svc.depends_on:
                if dep not in self._services:
                    raise ServiceError(f"service {svc.name!r} depends on unknown service {dep!r}")

        order: list[str] = []
        state: dict[str, str] = {}

        def visit(name: str) -> None:
            marker = state.get(name)
            if marker == "done":
                return
            if marker == "visiting":
                raise ServiceError(f"dependency cycle involving {name!r}")
            state[name] = "visiting"
            for dep in self._services[name].depends_on:
                visit(dep)
            state[name] = "done"
            order.append(name)

        for name in self._services:
            visit(name)
        return order

    def start_all(self) -> None:
        if self._started:
            raise ServiceError("services are already started")
        started: list[Service] = []
        for name in self.start_order():
            svc = self._services[name]
            try:
                svc.start(self._ctx)
            except Exception as exc:
                self._status[name] = HealthStatus.FAILED
                self._start_errors[name] = f"{type(exc).__name__}: {exc}"
                log.exception("service %s failed to start", name)
                for prev in reversed(started):
                    self._stop_one(prev)
                self._started = []
                raise ServiceStartError(f"service {name!r} failed to start") from exc
            started.append(svc)
            self._status[name] = HealthStatus.OK
        self._started = started
        log.info("started services: %s", ", ".join(s.name for s in started))

    def tick_all(self) -> None:
        for svc in self._started:
            try:
                svc.tick()
            except Exception as exc:
                self._tick_errors[svc.name] = f"{type(exc).__name__}: {exc}"
                log.exception("service %s tick failed", svc.name)
            else:
                self._tick_errors.pop(svc.name, None)

    def stop_all(self) -> None:
        for svc in reversed(self._started):
            self._stop_one(svc)
        self._started = []

    def _stop_one(self, svc: Service) -> None:
        try:
            svc.stop()
        except Exception:
            log.exception("service %s raised while stopping", svc.name)
        self._status[svc.name] = HealthStatus.STOPPED

    def health_report(self) -> list[ServiceHealthEntry]:
        entries: list[ServiceHealthEntry] = []
        for name, svc in self._services.items():
            status = self._status[name]
            detail = self._start_errors.get(name, "")
            if status is HealthStatus.OK:
                status, detail = svc.health_detail()
            if name in self._tick_errors and status in (HealthStatus.OK, HealthStatus.DEGRADED):
                status = HealthStatus.DEGRADED
                detail = self._tick_errors[name]
            entries.append(ServiceHealthEntry(name=name, status=status, detail=detail[:512]))
        return entries
