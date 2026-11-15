"""The FMS must receive existing AI-box mock values, never its own mock dataset."""

from marine_contracts import GeoPosition, MessageType

from scripts.demo_ai_box_reports import AIBoxReportDemo


def test_fms_has_no_boat_reports_before_ai_boxes_tick() -> None:
    demo = AIBoxReportDemo()
    assert demo.received() == []
    demo.start()
    try:
        assert demo.received() == []
        demo.tick()
        assert {row["boat_id"] for row in demo.received()} == {"mock-01", "mock-02"}
    finally:
        demo.close()


def test_fms_receives_exact_independent_ai_box_source_values() -> None:
    demo = AIBoxReportDemo()
    demo.start()
    try:
        for _ in range(10):
            demo.tick()
        for boat_id in ("mock-01", "mock-02"):
            source = demo.boats[boat_id].position.current_state()
            latest = demo.store.latest(boat_id, MessageType.BOAT_STATE)
            assert source is not None and latest is not None
            assert latest.payload.position == source.geo_position
            assert latest.payload.heading_deg == source.heading_deg
            assert latest.payload.speed_over_ground_mps == source.speed_over_ground_mps
            assert latest.payload.battery_state_of_charge is None
            assert len(demo.store.history(boat_id, MessageType.BOAT_STATE)) == 10
            assert demo.store.latest(boat_id, MessageType.SERVICE_HEALTH) is not None
        assert demo.store.latest("mock-01", MessageType.BOAT_STATE).payload.position == GeoPosition(
            latitude_deg=59.3300, longitude_deg=18.1120
        )
        assert demo.store.latest("mock-02", MessageType.BOAT_STATE).payload.position == GeoPosition(
            latitude_deg=59.3340, longitude_deg=18.1200
        )
    finally:
        demo.close()


def test_missing_ai_box_position_stays_unknown_in_fms() -> None:
    demo = AIBoxReportDemo()
    demo.start()
    try:
        demo.boats["mock-01"].position.set_state(None)
        demo.tick()
        latest = demo.store.latest("mock-01", MessageType.BOAT_STATE)
        assert latest is not None
        assert latest.payload.position is None
        assert latest.payload.speed_over_ground_mps is None
        other = demo.store.latest("mock-02", MessageType.BOAT_STATE)
        assert other is not None and other.payload.position is not None
    finally:
        demo.close()