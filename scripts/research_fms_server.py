"""Run the research-only, loopback FMS REST server without changing the main demo."""

from __future__ import annotations

import argparse
import logging
import re
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for package in ("interfaces", "ai-box", "fms", "adapters"):
    sys.path.insert(0, str(ROOT / package / "src"))

from adapters.fms.rest_server import make_research_server
from fms.communication.outbox import Outbox
from fms.core.endpoint import FmsEndpoint
from fms.core.fleet import BoatIdentity, FleetRegistry
from fms.data.research import ResearchFleet
from fms.data.store import InMemoryFleetStore
from fms.logging.audit import AuditLog
from marine_contracts.envelope import BOAT_ID_PATTERN


def build_application(identities: Sequence[BoatIdentity]) -> ResearchFleet:
    registry = FleetRegistry()
    for identity in identities:
        registry.register(identity)
    store = InMemoryFleetStore()
    endpoint = FmsEndpoint(registry=registry, store=store, audit=AuditLog(), outbox=Outbox(limit_per_boat=1000))
    return ResearchFleet(registry=registry, store=store, endpoint=endpoint)


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765, help="local development port (default: 8765)")
    parser.add_argument("--boat", action="append", metavar="ID[:NAME]", help="registered mock identity; repeatable")
    args = parser.parse_args(argv)
    identities = []
    for item in args.boat or ["mock-01", "mock-02"]:
        boat_id, _, name = item.partition(":")
        if re.fullmatch(BOAT_ID_PATTERN, boat_id) is None:
            parser.error(f"invalid boat ID: {boat_id!r}")
        identities.append(BoatIdentity(boat_id=boat_id, display_name=name or boat_id))
    logging.basicConfig(level=logging.INFO)
    with make_research_server(("127.0.0.1", args.port), build_application(identities)) as server:
        print(f"Research FMS: http://127.0.0.1:{server.server_address[1]} (loopback only)", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
