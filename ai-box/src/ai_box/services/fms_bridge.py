"""The only component that talks to the FMS.

Boat-side services publish `Outbound` messages on FMS_OUTBOUND. This bridge wraps
them in envelopes with monotonic sequence numbers, buffers them while the link is
down (bounded, drop-oldest), and publishes inbound envelopes on FMS_INBOUND.
"""

from __future__ import annotations

import logging
from collections import deque

from marine_contracts import MESSAGE_SPECS, Direction, Envelope, HealthStatus, make_envelope

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
        self._inbound_rejected = 0
        self._link_unavailable = False

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
        send_failed = False
        while self._outbox:
            head = self._outbox[0]
            try:
                self._link.send(head)
            except ConnectionError:
                # Link is down: keep the message and retry on the next tick.
                self._link_unavailable = True
                send_failed = True
                break
            except Exception:
                # The peer refused this message. Retrying would block everything behind it.
                self._dropped += 1
                log.exception("link refused message %s; dropping it", head.message_id)
            self._outbox.popleft()
        try:
            inbound = self._link.receive()
        except ConnectionError:
            self._link_unavailable = True
            return
        if not send_failed:
            self._link_unavailable = False
        for envelope in inbound:
            if envelope.boat_id != self._ctx.config.boat_id:
                self._inbound_rejected += 1
                log.error(
                    "discarding inbound message %s addressed to boat %s on boat %s",
                    envelope.message_id,
                    envelope.boat_id,
                    self._ctx.config.boat_id,
                )
                continue
            if MESSAGE_SPECS[envelope.message_type].direction not in (Direction.FMS_TO_BOAT, Direction.EITHER):
                self._inbound_rejected += 1
                log.error("discarding inbound message %s with boat-to-FMS direction", envelope.message_id)
                continue
            self._ctx.bus.publish(FMS_INBOUND, envelope)

    def health_detail(self) -> tuple[HealthStatus, str]:
        details = []
        if self._dropped:
            details.append(f"{self._dropped} outbound message(s) dropped")
        if self._inbound_rejected:
            details.append(f"{self._inbound_rejected} inbound message(s) rejected")
        if self._link_unavailable:
            if self._outbox:
                details.append(f"{len(self._outbox)} message(s) buffered while link unavailable")
            else:
                details.append("FMS link unavailable")
        if details:
            return HealthStatus.DEGRADED, "; ".join(details)
        return HealthStatus.OK, ""
