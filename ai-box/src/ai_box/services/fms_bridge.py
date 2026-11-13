"""The only component that talks to the FMS.

Boat-side services publish `Outbound` messages on FMS_OUTBOUND. This bridge wraps
them in envelopes with monotonic sequence numbers, buffers them while the link is
down (bounded, drop-oldest), and publishes inbound envelopes on FMS_INBOUND.
"""

from __future__ import annotations

import logging
from collections import deque

from marine_contracts import Envelope, HealthStatus, make_envelope

from ai_box.core.events import FMS_INBOUND, FMS_OUTBOUND, Outbound
from ai_box.core.ports import FmsLink
from ai_box.core.service import Service, ServiceContext

log = logging.getLogger("ai_box.fms_bridge")


class FmsBridgeService(Service):
    name = "fms-bridge"

    def __init__(self, link: FmsLink) -> None:
        self._link = link
        self._ctx: ServiceContext | None = None
        self._outbox: deque[Envelope] = deque()
        self._limit = 1
        self._sequence = 0
        self._dropped = 0
        self._send_failures = 0

    @property
    def pending(self) -> int:
        return len(self._outbox)

    def start(self, ctx: ServiceContext) -> None:
        self._ctx = ctx
        self._limit = ctx.config.outbound_buffer_limit
        ctx.bus.subscribe(FMS_OUTBOUND, self._on_outbound)

    def stop(self) -> None:
        if self._ctx is not None:
            self._ctx.bus.unsubscribe(FMS_OUTBOUND, self._on_outbound)
        self._ctx = None

    def _on_outbound(self, message: Outbound) -> None:
        if self._ctx is None:
            return
        try:
            envelope = make_envelope(
                boat_id=self._ctx.config.boat_id,
                message_type=message.message_type,
                payload=message.payload,
                mission_id=message.mission_id,
                sequence_number=self._sequence,
            )
        except (TypeError, ValueError):
            self._dropped += 1
            log.exception("refusing to send invalid %s message", message.message_type.value)
            return
        self._sequence += 1
        if len(self._outbox) >= self._limit:
            self._outbox.popleft()
            self._dropped += 1
            log.warning("outbound buffer full; dropped oldest message")
        self._outbox.append(envelope)

    def tick(self) -> None:
        if self._ctx is None:
            return
        while self._outbox:
            head = self._outbox[0]
            try:
                self._link.send(head)
            except ConnectionError:
                # Link is down: keep the message and retry on the next tick.
                self._send_failures += 1
                break
            except Exception:
                # The peer refused this message. Retrying would block everything behind it.
                self._dropped += 1
                log.exception("link refused message %s; dropping it", head.message_id)
            self._outbox.popleft()
        try:
            inbound = self._link.receive()
        except ConnectionError:
            self._send_failures += 1
            return
        for envelope in inbound:
            self._ctx.bus.publish(FMS_INBOUND, envelope)

    def health_detail(self) -> tuple[HealthStatus, str]:
        if self._dropped:
            return HealthStatus.DEGRADED, f"{self._dropped} outbound message(s) dropped"
        if self._outbox:
            return HealthStatus.DEGRADED, f"{len(self._outbox)} message(s) buffered while link unavailable"
        return HealthStatus.OK, ""
