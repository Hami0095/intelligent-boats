"""Loopback-only research HTTP transport with an injected FMS application.

The adapter does not import FMS internals. This is a single-thread software demo
server, not a public or production endpoint.
"""

from __future__ import annotations

import ipaddress
import json
import logging
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Protocol
from urllib.parse import unquote, urlsplit

from marine_contracts import MESSAGE_SPECS, Direction, Envelope, MessageType, decode_envelope
from pydantic import ValidationError

log = logging.getLogger("fms.research_http")


class ResearchApplication(Protocol):
    def receive(self, envelope: Envelope) -> list[Envelope]: ...

    def snapshots(self) -> list[dict[str, Any]]: ...

    def snapshot(self, boat_id: str) -> dict[str, Any]: ...


def make_research_server(
    address: tuple[str, int], app: ResearchApplication, *, max_body_bytes: int = 1_048_576
) -> HTTPServer:
    """Create an unstarted HTTP server bound only to an IPv4 loopback address."""
    host, port = address
    if host == "localhost":
        host = "127.0.0.1"
    try:
        parsed_host = ipaddress.ip_address(host)
    except ValueError as exc:
        raise ValueError("research HTTP server requires an IPv4 loopback bind address") from exc
    if parsed_host.version != 4 or not parsed_host.is_loopback:
        raise ValueError("research HTTP server requires an IPv4 loopback bind address")
    if isinstance(max_body_bytes, bool) or not isinstance(max_body_bytes, int) or max_body_bytes <= 0:
        raise ValueError("max_body_bytes must be a positive integer")

    class Handler(BaseHTTPRequestHandler):
        def _respond(self, status: HTTPStatus, value: Any) -> None:
            body = json.dumps(value, allow_nan=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            path = urlsplit(self.path).path.rstrip("/")
            if path == "/api/v1/boats":
                self._respond(HTTPStatus.OK, {"boats": app.snapshots()})
                return
            parts = path.split("/")
            if len(parts) != 6 or parts[1:4] != ["api", "v1", "boats"]:
                self._respond(HTTPStatus.NOT_FOUND, {"error": "route not found"})
                return
            resource = parts[5]
            if resource not in ("state", "progress", "health"):
                self._respond(HTTPStatus.NOT_FOUND, {"error": "route not found"})
                return
            try:
                snapshot = app.snapshot(unquote(parts[4]))
            except LookupError:
                self._respond(HTTPStatus.NOT_FOUND, {"error": "unknown boat_id"})
                return
            messages = snapshot["messages"]
            if resource == "state":
                value = messages[MessageType.BOAT_STATE.value]
            elif resource == "health":
                value = messages[MessageType.SERVICE_HEALTH.value]
            else:
                value = {
                    "mission": messages[MessageType.MISSION_PROGRESS.value],
                    "environment": messages[MessageType.ENVIRONMENT_PROGRESS.value],
                }
            self._respond(HTTPStatus.OK, value)

        def do_POST(self) -> None:
            if urlsplit(self.path).path != "/api/v1/boat-messages":
                self._respond(HTTPStatus.NOT_FOUND, {"error": "route not found"})
                return
            if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
                self._respond(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"error": "application/json required"})
                return
            length_header = self.headers.get("Content-Length")
            if length_header is None:
                self._respond(HTTPStatus.LENGTH_REQUIRED, {"error": "Content-Length required"})
                return
            try:
                length = int(length_header)
            except ValueError:
                self._respond(HTTPStatus.BAD_REQUEST, {"error": "invalid Content-Length"})
                return
            if length <= 0:
                self._respond(HTTPStatus.BAD_REQUEST, {"error": "JSON body required"})
                return
            if length > max_body_bytes:
                self._respond(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "request body too large"})
                return
            raw = self.rfile.read(length)
            try:
                value = json.loads(raw)
            except (ValueError, UnicodeDecodeError, RecursionError):
                self._respond(HTTPStatus.BAD_REQUEST, {"error": "malformed JSON"})
                return
            try:
                # Python accepts NaN/Infinity and overflows numbers such as
                # 1e999 to inf. Reject them before Pydantic can normalize a
                # received nonfinite payload value into null in API output.
                json.dumps(value, allow_nan=False)
            except (ValueError, RecursionError):
                self._respond(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "JSON values must be finite"})
                return
            try:
                envelope = decode_envelope(raw)
            except ValidationError:
                self._respond(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "invalid marine_contracts envelope"})
                return
            if MESSAGE_SPECS[envelope.message_type].direction not in (Direction.BOAT_TO_FMS, Direction.EITHER):
                self._respond(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "message is not boat-originated"})
                return
            try:
                replies = app.receive(envelope)
            except LookupError:
                self._respond(HTTPStatus.FORBIDDEN, {"error": "unknown boat_id"})
                return
            self._respond(HTTPStatus.OK, {"replies": [reply.model_dump(mode="json") for reply in replies]})

        def log_message(self, format: str, *args: object) -> None:
            log.info(format, *args)

    return HTTPServer((host, port), Handler)
