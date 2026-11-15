"""Research demo: existing AI-box mock sources report to the existing Python FMS.

Run from the repository root: python -m scripts.demo_ai_box_reports --ticks 10
Only AI-box telemetry services construct reports; the FMS never generates data.
Loopback is the existing in-process transport, not a remote HTTP deployment.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for package in ("interfaces", "ai-box", "fms", "adapters"):
    sys.path.insert(0, str(ROOT / package / "src"))

from adapters.fms.loopback import LoopbackFmsLink
from adapters.propulsion.mock import MockPropulsionSink
from adapters.sensors.mock import MockPositionSource
from ai_box.bootstrap import BoatRuntime, build_boat
from ai_box.config.settings import AIBoxConfig
from ai_box.motion.commands import VehicleState
from fms.communication.outbox import Outbox
from fms.core.endpoint import FmsEndpoint
from fms.core.fleet import BoatIdentity, FleetRegistry
from fms.data.store import InMemoryFleetStore
from fms.logging.audit import AuditLog
from marine_contracts import GeoPosition, MessageType


@dataclass
class MockAIBox:
    boat_id: str
    position: MockPositionSource
    propulsion: MockPropulsionSink
    runtime: BoatRuntime


class AIBoxReportDemo:
    """Composition-only harness; no browser FleetController or second simulator."""

    def __init__(self) -> None:
        self.registry = FleetRegistry()
        self.store = InMemoryFleetStore()
        self.endpoint = FmsEndpoint(
            registry=self.registry, store=self.store, audit=AuditLog(), outbox=Outbox(limit_per_boat=100)
        )
        self.boats: dict[str, MockAIBox] = {}
        # Presentation fixtures only, not hardware specifications or a GPS transform.
        for boat_id, latitude, longitude, heading in (
            ("mock-01", 59.3300, 18.1120, 90.0),
            ("mock-02", 59.3340, 18.1200, 180.0),
        ):
            self.registry.register(BoatIdentity(boat_id=boat_id, display_name=f"Mock AI box {boat_id}"))
            position, propulsion = MockPositionSource(), MockPropulsionSink()
            position.set_state(VehicleState(
                timestamp=datetime.now(timezone.utc),
                geo_position=GeoPosition(latitude_deg=latitude, longitude_deg=longitude),
                speed_over_ground_mps=0.0, heading_deg=heading,
            ))
            runtime = build_boat(
                AIBoxConfig(boat_id=boat_id), position=position, propulsion=propulsion,
                fms_link=LoopbackFmsLink(server=self.endpoint.receive),
            )
            self.boats[boat_id] = MockAIBox(boat_id, position, propulsion, runtime)

    def start(self) -> None:
        for boat in self.boats.values():
            boat.runtime.app.start()

    def tick(self) -> None:
        for boat in self.boats.values():
            boat.runtime.app.tick()

    def close(self) -> None:
        for boat in self.boats.values():
            boat.runtime.app.shutdown()

    def received(self) -> list[dict[str, object]]:
        """Project only actual received FMS messages; never fill missing readings."""
        rows: list[dict[str, object]] = []
        for boat_id in self.boats:
            latest = self.store.latest(boat_id, MessageType.BOAT_STATE)
            if latest is None:
                continue
            rows.append({
                "boat_id": boat_id, "source": "Mock AI Box / loopback",
                "received_at": latest.received_at.isoformat(),
                "envelope": latest.envelope.model_dump(mode="json"),
            })
        return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticks", type=int, default=10)
    parser.add_argument("--interval", type=float, default=1.0)
    args = parser.parse_args()
    if args.ticks < 1 or args.interval < 0:
        parser.error("ticks must be positive and interval must be nonnegative")
    demo = AIBoxReportDemo()
    demo.start()
    try:
        for cycle in range(args.ticks):
            demo.tick()
            print(json.dumps({"cycle": cycle + 1, "fms_received": demo.received()}), flush=True)
            if cycle + 1 < args.ticks:
                time.sleep(args.interval)
    finally:
        demo.close()


if __name__ == "__main__":
    main()