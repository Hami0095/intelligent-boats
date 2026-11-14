"""Research-only HTTP transport for the existing FMS envelope port.

Each send makes one POST. Connection failures and HTTP 5xx responses raise
ConnectionError for the bridge's existing offline handling; other HTTP refusals
and malformed replies raise RestFmsError. HTTP success is not a mission ACK.
"""

from __future__ import annotations

import json
import math
from http.client import HTTPMessage
from typing import IO
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from marine_contracts import Envelope, decode_envelope, encode_envelope


class RestFmsError(RuntimeError):
    """The HTTP peer refused a message or returned an invalid envelope response."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(
        self,
        req: Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: HTTPMessage,
        newurl: str,
    ) -> None:
        # Do not silently forward boat messages to another HTTP destination.
        return None


class RestFmsLink:
    def __init__(self, base_url: str, *, timeout_s: float = 2.0) -> None:
        if not isinstance(base_url, str) or base_url != base_url.strip():
            raise ValueError("base_url must be an HTTP or HTTPS origin")
        try:
            parsed = urlsplit(base_url)
            port = parsed.port
        except ValueError as exc:
            raise ValueError("base_url must contain a valid host and port") from exc
        if (
            parsed.scheme not in ("http", "https")
            or not parsed.hostname
            or parsed.path not in ("", "/")
            or parsed.query
            or parsed.fragment
            or parsed.username is not None
            or parsed.password is not None
            or port == 0
        ):
            raise ValueError("base_url must be an HTTP or HTTPS origin without credentials, path or query")
        if isinstance(timeout_s, bool) or not math.isfinite(timeout_s) or timeout_s <= 0:
            raise ValueError("timeout_s must be finite and positive")
        self._url = base_url.rstrip("/") + "/api/v1/boat-messages"
        self._timeout_s = timeout_s
        self._opener = build_opener(_NoRedirect())
        self._inbox: list[Envelope] = []

    def send(self, envelope: Envelope) -> None:
        request = Request(
            self._url,
            data=encode_envelope(envelope).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        try:
            with self._opener.open(request, timeout=self._timeout_s) as response:
                raw = response.read()
        except HTTPError as exc:
            exc.close()
            if exc.code >= 500:
                raise ConnectionError(f"FMS HTTP service unavailable ({exc.code})") from exc
            raise RestFmsError(f"FMS refused message with HTTP {exc.code}") from exc
        except (URLError, OSError) as exc:
            raise ConnectionError("FMS HTTP connection failed") from exc
        try:
            data = json.loads(raw)
            if not isinstance(data, dict) or not isinstance(data.get("replies"), list):
                raise ValueError("expected an object containing a replies list")
            replies = [decode_envelope(json.dumps(reply)) for reply in data["replies"]]
        except (ValueError, TypeError) as exc:
            raise RestFmsError("FMS returned an invalid envelope response") from exc
        self._inbox.extend(replies)

    def receive(self) -> list[Envelope]:
        """Drain replies already returned by sends; never polls or retries HTTP."""
        replies, self._inbox = self._inbox, []
        return replies
