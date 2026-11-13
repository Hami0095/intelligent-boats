"""Collapse per-service health into one boat-level status."""

from __future__ import annotations

from collections.abc import Iterable

from marine_contracts import HealthStatus

_PRECEDENCE = (
    HealthStatus.FAILED,
    HealthStatus.DEGRADED,
    HealthStatus.NOT_STARTED,
    HealthStatus.STOPPED,
    HealthStatus.OK,
)


def overall_status(statuses: Iterable[HealthStatus]) -> HealthStatus:
    """Worst status wins. An empty set is reported as STOPPED."""
    present = set(statuses)
    if not present:
        return HealthStatus.STOPPED
    for candidate in _PRECEDENCE:
        if candidate in present:
            return candidate
    return HealthStatus.OK  # pragma: no cover - every enum member is in _PRECEDENCE
