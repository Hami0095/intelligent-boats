import pytest

from ai_box.config.settings import AIBoxConfig
from ai_box.core.app import AIBoxApp
from ai_box.core.manager import ServiceError, ServiceStartError
from ai_box.core.service import Service
from marine_contracts import HealthStatus


class Recorder(Service):
    def __init__(self, name, depends_on=(), fail_start=False, fail_tick=False, log=None):
        self.name = name
        self.depends_on = tuple(depends_on)
        self._fail_start = fail_start
        self.fail_tick = fail_tick
        self.log = log if log is not None else []

    def start(self, ctx):
        if self._fail_start:
            raise RuntimeError("cannot start")
        self.log.append(("start", self.name))

    def stop(self):
        self.log.append(("stop", self.name))

    def tick(self):
        if self.fail_tick:
            raise RuntimeError("tick failed")
        self.log.append(("tick", self.name))


def _app():
    return AIBoxApp(AIBoxConfig())


def test_dependencies_start_before_their_dependents():
    app = _app()
    log = []
    app.register(Recorder("b", depends_on=("a",), log=log))
    app.register(Recorder("a", log=log))
    app.start()
    assert [entry for entry in log if entry[0] == "start"] == [("start", "a"), ("start", "b")]


def test_services_stop_in_reverse_order():
    app = _app()
    log = []
    app.register(Recorder("a", log=log))
    app.register(Recorder("b", depends_on=("a",), log=log))
    app.start()
    app.shutdown()
    assert [e for e in log if e[0] == "stop"] == [("stop", "b"), ("stop", "a")]


def test_unknown_dependency_is_a_configuration_error():
    app = _app()
    app.register(Recorder("a", depends_on=("missing",)))
    with pytest.raises(ServiceError, match="unknown service 'missing'"):
        app.start()


def test_dependency_cycle_is_a_configuration_error():
    app = _app()
    app.register(Recorder("a", depends_on=("b",)))
    app.register(Recorder("b", depends_on=("a",)))
    with pytest.raises(ServiceError, match="cycle"):
        app.start()


def test_duplicate_names_are_rejected():
    app = _app()
    app.register(Recorder("a"))
    with pytest.raises(ServiceError, match="duplicate"):
        app.register(Recorder("a"))


def test_failed_start_rolls_back_already_started_services():
    app = _app()
    log = []
    app.register(Recorder("a", log=log))
    app.register(Recorder("b", depends_on=("a",), fail_start=True, log=log))
    with pytest.raises(ServiceStartError):
        app.start()
    assert ("stop", "a") in log
    statuses = {e.name: e.status for e in app.health_report()}
    assert statuses["b"] is HealthStatus.FAILED


def test_tick_failure_degrades_then_recovers():
    app = _app()
    svc = Recorder("a", fail_tick=True)
    app.register(svc)
    app.start()
    app.tick()
    assert app.health_report()[0].status is HealthStatus.DEGRADED
    svc.fail_tick = False
    app.tick()
    assert app.health_report()[0].status is HealthStatus.OK


def test_registration_after_start_is_rejected():
    app = _app()
    app.register(Recorder("a"))
    app.start()
    with pytest.raises(ServiceError):
        app.register(Recorder("b"))
    app.shutdown()


def test_context_manager_starts_and_stops():
    log = []
    app = _app()
    app.register(Recorder("a", log=log))
    with app:
        app.tick()
    assert log == [("start", "a"), ("tick", "a"), ("stop", "a")]
