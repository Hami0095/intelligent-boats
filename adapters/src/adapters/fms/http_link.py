"""HTTP link that connects an AI Box to the Lovable fleet-management dashboard.

The dashboard hosts the FMS in the browser; this adapter exchanges envelopes
with it through the dashboard's `/api/public/fms-link` relay endpoint:

- ``send`` POSTs one boat-originated envelope (boat -> FMS).
- ``receive`` GETs and drains the FMS commands waiting for this boat.

Every request carries ``Authorization: Bearer <token>``; the token must match
the dashboard's ``FMS_LINK_TOKEN`` secret. Only the Python standard library is
used, so no new dependencies are introduced.

Like the loopback adapter, ``send``/``receive`` raise ``ConnectionError`` while
the link is unreachable, which is what ``FmsBridgeService`` expects. A remote
refusal (non-2xx response) raises ``RuntimeError`` instead, so the bridge drops
that single message rather than blocking everything behind it.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from marine_contracts import Envelope
from marine_contracts.envelope import SCHEMA_VERSION, decode_envelope, encode_envelope


class HttpFmsLink:
    """FmsLink implementation over plain HTTPS JSON."""

    def __init__(self, base_url: str, boat_id: str, token: str, timeout: float = 5.0) -> None:
        self._url = base_url.rstrip("/") + "/api/public/fms-link"
        self._boat_id = boat_id
        self._token = token
        self._timeout = timeout

    def _request(self, method: str, url: str, body: dict | None = None) -> dict:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", f"Bearer {self._token}")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"FMS link refused {method} {url}: HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ConnectionError(f"FMS link unreachable: {exc}") from exc

    def send(self, envelope: Envelope) -> None:
        self._request("POST", self._url, {"envelopes": [json.loads(encode_envelope(envelope))]})

    def receive(self) -> list[Envelope]:
        query = urllib.parse.urlencode({"boat_id": self._boat_id})
        data = self._request("GET", f"{self._url}?{query}")
        envelopes: list[Envelope] = []
        for raw in data.get("envelopes", []):
            envelopes.append(decode_envelope(json.dumps(self._normalise(raw))))
        return envelopes

    @staticmethod
    def _normalise(raw: dict) -> dict:
        """Tolerate dashboard-native envelopes (epoch-ms timestamp, no schema version)."""
        raw = dict(raw)
        raw.setdefault("schema_version", SCHEMA_VERSION)
        ts = raw.get("timestamp")
        if isinstance(ts, (int, float)):
            raw["timestamp"] = datetime.fromtimestamp(ts / 1000.0, tz=timezone.utc).isoformat()
        return raw
