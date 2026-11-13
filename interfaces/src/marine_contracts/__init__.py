"""Shared, versioned message contracts for the autonomous marine system.

This package is the ONLY code that the AI Box, the FMS and the adapters may
share. It contains data definitions and validation, never behaviour.
See interfaces/README.md and docs/COMMUNICATION_PROTOCOL.md.
"""

from marine_contracts.common import (
    GeoPosition,
    HealthStatus,
    OperatingMode,
    Provenance,
    Severity,
    StrictModel,
)
from marine_contracts.envelope import (
    SCHEMA_VERSION,
    Envelope,
    decode_envelope,
    encode_envelope,
    make_envelope,
)
from marine_contracts.payloads import (
    AcknowledgementPayload,
    BoatStatePayload,
    ConfigurationUpdatePayload,
    EnvironmentProgressPayload,
    MissionAssignmentPayload,
    MissionCancellationPayload,
    MissionProgressPayload,
    MissionStatus,
    NavigationGoalPayload,
    ObstacleSummaryPayload,
    ObstacleTrack,
    OperationalEventPayload,
    SafeStateAction,
    SafeStateCommandPayload,
    ServiceHealthEntry,
    ServiceHealthPayload,
)
from marine_contracts.registry import MESSAGE_SPECS, Direction, MessageSpec, MessageType

__all__ = [
    "AcknowledgementPayload",
    "BoatStatePayload",
    "ConfigurationUpdatePayload",
    "Direction",
    "EnvironmentProgressPayload",
    "Envelope",
    "GeoPosition",
    "HealthStatus",
    "MESSAGE_SPECS",
    "MessageSpec",
    "MessageType",
    "MissionAssignmentPayload",
    "MissionCancellationPayload",
    "MissionProgressPayload",
    "MissionStatus",
    "NavigationGoalPayload",
    "ObstacleSummaryPayload",
    "ObstacleTrack",
    "OperatingMode",
    "OperationalEventPayload",
    "Provenance",
    "SCHEMA_VERSION",
    "SafeStateAction",
    "SafeStateCommandPayload",
    "ServiceHealthEntry",
    "ServiceHealthPayload",
    "Severity",
    "StrictModel",
    "decode_envelope",
    "encode_envelope",
    "make_envelope",
]
