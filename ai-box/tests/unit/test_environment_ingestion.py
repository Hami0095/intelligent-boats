from datetime import datetime, timezone

from ai_box.config.settings import AIBoxConfig
from ai_box.core.events import ENVIRONMENT_OBSERVATION, SENSOR_SAMPLE, EventBus
from ai_box.core.geometry import LocalPoint
from ai_box.core.ports import SensorKind, SensorSample
from ai_box.core.service import ServiceContext
from ai_box.environment.ingestion import EnvironmentKnowledgeService, EnvironmentObservationIngestService
from ai_box.environment.knowledge import InMemoryEnvironmentKnowledge, RegionStatus
from ai_box.environment.model import GridIndexer
from ai_box.environment.observations import EnvironmentObservation, ObservationKind

T0 = datetime(2026, 11, 14, tzinfo=timezone.utc)


def _sample(data, *, kind=SensorKind.OTHER):
    return SensorSample(sensor_id="mock-observation", kind=kind, timestamp=T0, data=data)


def _services():
    bus = EventBus()
    ctx = ServiceContext(bus=bus, config=AIBoxConfig())
    grid = GridIndexer()
    knowledge = InMemoryEnvironmentKnowledge(grid)
    ingest = EnvironmentObservationIngestService()
    recorder = EnvironmentKnowledgeService(knowledge)
    ingest.start(ctx)
    recorder.start(ctx)
    return bus, grid, knowledge, ingest, recorder


def test_mock_sample_publishes_and_records_a_typed_observed_event():
    bus, grid, knowledge, ingest, recorder = _services()
    published: list[EnvironmentObservation] = []
    bus.subscribe(ENVIRONMENT_OBSERVATION, published.append)
    sample = _sample(
        {
            "environment_observation": {
                "point": {"x_m": 15.0, "y_m": 5.0},
                "confidence": 0.8,
                "mission_id": "mission-1",
                "provenance_detail": "explicit mock fixture",
            }
        }
    )

    try:
        bus.publish(SENSOR_SAMPLE, sample)
    finally:
        ingest.stop()
        recorder.stop()

    assert len(published) == 1
    observation = published[0]
    assert observation.kind is ObservationKind.OBSERVED
    assert observation.point == LocalPoint(15.0, 5.0)
    assert observation.timestamp == T0
    assert observation.provenance.source == "sensor:mock-observation"
    assert observation.provenance.detail == "explicit mock fixture"
    assert observation.mission_id == "mission-1"
    region = grid.region_of(observation.point)
    assert knowledge.region(region).status is RegionStatus.OBSERVED
    assert knowledge.region(region).search_count == 0


def test_malformed_mock_observation_is_rejected_without_changing_knowledge():
    bus, grid, knowledge, ingest, recorder = _services()
    published: list[EnvironmentObservation] = []
    bus.subscribe(ENVIRONMENT_OBSERVATION, published.append)
    sample = _sample(
        {
            "environment_observation": {
                "point": {"x_m": 15.0},
                "confidence": 0.8,
            }
        }
    )

    try:
        bus.publish(SENSOR_SAMPLE, sample)
        status, detail = ingest.health_detail()
    finally:
        ingest.stop()
        recorder.stop()

    region = grid.region_of(LocalPoint(15.0, 5.0))
    assert published == []
    assert knowledge.region(region).status is RegionStatus.UNKNOWN
    assert status.value == "degraded"
    assert "invalid environment observation" in detail


def test_unrelated_other_sensor_sample_is_ignored():
    bus, grid, knowledge, ingest, recorder = _services()
    published: list[EnvironmentObservation] = []
    bus.subscribe(ENVIRONMENT_OBSERVATION, published.append)

    try:
        bus.publish(SENSOR_SAMPLE, _sample({"raw_value": 1.0}))
        status, detail = ingest.health_detail()
    finally:
        ingest.stop()
        recorder.stop()

    region = grid.region_of(LocalPoint(15.0, 5.0))
    assert published == []
    assert knowledge.region(region).status is RegionStatus.UNKNOWN
    assert status.value == "ok"
    assert detail == ""


def test_collision_sensor_sample_cannot_create_an_environment_observation():
    bus, grid, knowledge, ingest, recorder = _services()
    published: list[EnvironmentObservation] = []
    bus.subscribe(ENVIRONMENT_OBSERVATION, published.append)
    sample = _sample(
        {
            "environment_observation": {
                "point": {"x_m": 15.0, "y_m": 5.0},
                "confidence": 0.8,
            }
        },
        kind=SensorKind.RANGE,
    )

    try:
        bus.publish(SENSOR_SAMPLE, sample)
        status, detail = ingest.health_detail()
    finally:
        ingest.stop()
        recorder.stop()

    region = grid.region_of(LocalPoint(15.0, 5.0))
    assert published == []
    assert knowledge.region(region).status is RegionStatus.UNKNOWN
    assert status.value == "degraded"
    assert "invalid environment observation sample" in detail
