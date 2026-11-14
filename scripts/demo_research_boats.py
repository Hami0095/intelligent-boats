"""Report two explicitly stepped mock AI Boxes through the research REST link.

Geographic fixtures are synthetic inputs, independent of the local search frame.
Commands do not cause the scripted movement; the default controller stays zero.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for package in ("interfaces", "ai-box", "adapters"):
    sys.path.insert(0, str(ROOT / package / "src"))

from adapters.fms.rest import RestFmsLink
from adapters.propulsion.mock import MockPropulsionSink
from adapters.sensors.mock import MockPositionSource
from ai_box.bootstrap import BoatRuntime, build_boat
from ai_box.config.settings import AIBoxConfig
from ai_box.core.events import FMS_INBOUND
from ai_box.core.geometry import LocalPoint
from ai_box.environment.model import SearchArea
from ai_box.motion.commands import VehicleState
from marine_contracts import GeoPosition, MessageType, MissionAssignmentPayload, make_envelope

# Explicit geographic samples within the dashboard's existing Stockholm view.
# There is intentionally no conversion between these and the local coordinates.
GEOGRAPHIC_FIXTURES = (
    ((59.3300, 18.1120), (59.3302, 18.1125), (59.3304, 18.1130)),
    ((59.3340, 18.1200), (59.3338, 18.1205), (59.3336, 18.1210)),
)
LOCAL_FIXTURES = (LocalPoint(5.0, 5.0), LocalPoint(15.0, 5.0), LocalPoint(15.0, 15.0))


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class ResearchMockBoat:
    boat_id: str
    runtime: BoatRuntime
    position: MockPositionSource
    propulsion: MockPropulsionSink
    fixture_index: int
    clock: Callable[[], datetime]
    geographic: bool = True

    def start(self) -> None:
        self.runtime.app.start()
        # This is a one-time scripted input to the existing command router, not
        # a REST command dispatcher or a dashboard-issued mission.
        assignment = make_envelope(
            boat_id=self.boat_id,
            mission_id=f"research-{self.boat_id}",
            message_type=MessageType.MISSION_ASSIGNMENT,
            payload=MissionAssignmentPayload(objective="scripted reporting demonstration", search_area_id="demo-area"),
            sequence_number=0,
            timestamp=self.clock(),
        )
        self.runtime.app.bus.publish(FMS_INBOUND, assignment)

    def step(self, index: int) -> VehicleState:
        latitude, longitude = GEOGRAPHIC_FIXTURES[self.fixture_index][index % 3]
        state = VehicleState(
            timestamp=self.clock(),
            local_position=LOCAL_FIXTURES[(index + self.fixture_index) % len(LOCAL_FIXTURES)],
            geo_position=GeoPosition(latitude_deg=latitude, longitude_deg=longitude) if self.geographic else None,
            heading_deg=float(90 + self.fixture_index * 90),
        )
        self.position.set_state(state)
        self.runtime.app.tick()
        return state

    def stop(self) -> None:
        self.runtime.app.shutdown()


def build_mock_boats(
    base_url: str, *, clock: Callable[[], datetime] = utc_now, geographic: bool = True
) -> list[ResearchMockBoat]:
    boats = []
    for index, boat_id in enumerate(("mock-01", "mock-02")):
        position, propulsion = MockPositionSource(), MockPropulsionSink()
        runtime = build_boat(
            AIBoxConfig(boat_id=boat_id),
            position=position,
            propulsion=propulsion,
            fms_link=RestFmsLink(base_url),
            search_areas={"demo-area": SearchArea(0.0, 0.0, 30.0, 30.0)},
        )
        boats.append(ResearchMockBoat(boat_id, runtime, position, propulsion, index, clock, geographic))
    return boats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default="http://127.0.0.1:8765")
    parser.add_argument("--ticks", type=int, default=0, help="Number of explicit steps; 0 continues until interrupted")
    parser.add_argument("--interval", type=float, default=1.0, help="Seconds between scripted steps")
    parser.add_argument(
        "--no-geographic-position", action="store_true", help="Exercise truthful map-unavailable display"
    )
    args = parser.parse_args()
    if args.ticks < 0 or not math.isfinite(args.interval) or args.interval < 0:
        parser.error("ticks and finite interval must be non-negative")
    boats = build_mock_boats(args.api_url, geographic=not args.no_geographic_position)
    try:
        for boat in boats:
            boat.start()
        index = 0
        while not args.ticks or index < args.ticks:
            for boat in boats:
                state = boat.step(index)
                health, detail = boat.runtime.bridge.health_detail()
                print(
                    json.dumps(
                        {
                            "boat_id": boat.boat_id,
                            "scripted_step": index,
                            "position": state.geo_position.model_dump() if state.geo_position else None,
                            "bridge_health": health.value,
                            "detail": detail,
                            "pending": boat.runtime.bridge.pending,
                        }
                    ),
                    flush=True,
                )
            index += 1
            if not args.ticks or index < args.ticks:
                time.sleep(args.interval)
    except KeyboardInterrupt:
        pass
    finally:
        for boat in boats:
            boat.stop()


if __name__ == "__main__":
    main()
