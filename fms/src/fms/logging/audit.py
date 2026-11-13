"""Audit trail of operational events and rejected messages.

Entries are kept in memory and also emitted through the standard logger
"fms.audit". Durable storage of the audit trail is an OPEN decision.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

log = logging.getLogger("fms.audit")


@dataclass(frozen=True)
class AuditEntry:
    recorded_at: datetime
    category: str
    boat_id: str | None
    message: str


class AuditLog:
    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []

    def record(self, recorded_at: datetime, category: str, boat_id: str | None, message: str) -> None:
        entry = AuditEntry(recorded_at=recorded_at, category=category, boat_id=boat_id, message=message)
        self._entries.append(entry)
        log.info("%s boat=%s %s", category, boat_id, message)

    def entries(self) -> tuple[AuditEntry, ...]:
        return tuple(self._entries)
