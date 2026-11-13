"""Runs one mock boat against the FMS for a few control cycles and prints what the FMS received.

Usage (from the repository root):  python scripts/demo_mock_boat.py
Works from a source checkout without installing the packages.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for package_src in ("interfaces", "ai-box", "fms", "adapters"):
    sys.path.insert(0, str(ROOT / package_src / "src"))

from adapters.fms.loopback import LoopbackFmsLink  # noqa: E402
from adapters.propulsion.mock import MockPropulsionSink  # noqa: E402
from adapters.sensors.mock import MockPositionSource  # noqa: E402
from ai_box.bootstrap import build_boat  # noqa: E402
from ai_box.config.settings import AIBoxConfig  # noqa: E402
from ai_box.core.geometry import LocalPoint  # noqa: E402
from ai_box.environment.model import SearchArea  # noqa: E402
from ai_box.motion.commands import VehicleState  # noqa: E402
from fms.communication.outbox import Outbox  # noqa: E402
from fms.core.endpoint import FmsEndpoint  # noqa: E402
from fms.core.fleet import BoatIdentity, FleetRegistry  # noqa: E402
from fms.data.store import InMemoryFleetStore  # noqa: E402
from fms.logging.audit import AuditLog  # noqa: E402
from fms.missions.service import MissionService  # noqa: E402
from marine_contracts import MessageType, MissionAssignmentPayload  # noqa: E402


def main() -> None:
    boat_id = "boat-dev-01"
    registry = FleetRegistry()
    registry.register(BoatIdentity(boat_id=boat_id, display_name="Development boat"))
    store, outbox = InMemoryFleetStore(), Outbox(limit_per_boat=100)
    endpoint = FmsEndpoint(registry=registry, store=store, audit=AuditLog(), outbox=outbox)
    fms_missions = MissionService(registry, outbox)

    link = LoopbackFmsLink(server=endpoint.receive)
    position = MockPositionSource()
    position.set_state(VehicleState(timestamp=datetime.now(timezone.utc), local_position=LocalPoint(5.0, 5.0)))
    sink = MockPropulsionSink()

    boat = build_boat(
        AIBoxConfig(boat_id=boat_id),
        position=position,
        propulsion=sink,
        fms_link=link,
        search_areas={"demo-area": SearchArea(0.0, 0.0, 30.0, 30.0)},
    )
    boat.app.start()
    try:
        fms_missions.assign(boat_id, "demo-mission",
                            MissionAssignmentPayload(objective="demo search", search_area_id="demo-area"))
        for envelope in outbox.unacknowledged(boat_id):
            link.deliver([envelope])

        for cycle in range(1, 6):
            boat.app.tick()
            if boat.motion.goal is not None:
                position.set_state(VehicleState(timestamp=datetime.now(timezone.utc),
                                                local_position=boat.motion.goal.target))
            print(f"cycle {cycle}: mode={boat.operating.mode.value} goal={boat.motion.goal and boat.motion.goal.goal_id} "
                  f"thrust={sink.last.thrust if sink.last else None}")
    finally:
        boat.app.shutdown()

    print()
    print("FMS received:")
    for message_type in (MessageType.BOAT_STATE, MessageType.MISSION_PROGRESS, MessageType.ENVIRONMENT_PROGRESS):
        print(f"  {message_type.value:<24} {len(store.history(boat_id, message_type))} message(s)")
    print(f"  unacknowledged commands to boat: {len(outbox.unacknowledged(boat_id))}")


if __name__ == "__main__":
    main()
