"""The common message envelope wrapping every boat <-> FMS message.

The envelope is the only thing that crosses a transport boundary. It is plain
JSON text (see encode_envelope / decode_envelope); no transport library is
imported here.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator, model_validator

from marine_contracts.common import StrictModel, require_utc
from marine_contracts.registry import MESSAGE_SPECS, MessageType

SCHEMA_VERSION = "1.0.0"
SUPPORTED_MAJOR_VERSION = 1
BOAT_ID_PATTERN = r"^[a-z0-9][a-z0-9-]{1,62}$"
_SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


class Envelope(StrictModel):
    """Common header plus a payload validated against its message type."""

    schema_version: str = Field(default=SCHEMA_VERSION)
    message_id: UUID
    boat_id: str = Field(pattern=BOAT_ID_PATTERN)
    mission_id: str | None = Field(default=None, min_length=1, max_length=128)
    message_type: MessageType
    timestamp: datetime
    sequence_number: int = Field(ge=0)
    payload: dict[str, Any]

    @field_validator("schema_version")
    @classmethod
    def _supported_version(cls, value: str) -> str:
        match = _SEMVER.match(value)
        if match is None:
            raise ValueError(f"schema_version must be MAJOR.MINOR.PATCH, got {value!r}")
        if int(match.group(1)) != SUPPORTED_MAJOR_VERSION:
            raise ValueError(
                f"unsupported schema major version {match.group(1)}; this build supports {SUPPORTED_MAJOR_VERSION}.x"
            )
        return value

    @field_validator("timestamp")
    @classmethod
    def _timestamp_is_utc(cls, value: datetime) -> datetime:
        return require_utc(value)

    @model_validator(mode="after")
    def _payload_matches_type(self) -> Envelope:
        spec = MESSAGE_SPECS[self.message_type]
        if spec.requires_mission_id and self.mission_id is None:
            raise ValueError(f"{self.message_type.value} requires a mission_id")
        try:
            spec.model.model_validate(self.payload)
        except ValueError as exc:
            raise ValueError(f"payload invalid for {self.message_type.value}: {exc}") from exc
        return self

    def typed_payload(self) -> BaseModel:
        """Return the payload as its concrete contract model."""
        return MESSAGE_SPECS[self.message_type].model.model_validate(self.payload)


def make_envelope(
    *,
    boat_id: str,
    message_type: MessageType,
    payload: BaseModel,
    sequence_number: int,
    mission_id: str | None = None,
    timestamp: datetime | None = None,
    message_id: UUID | None = None,
) -> Envelope:
    """Build a valid envelope from a typed payload. The preferred way to create messages."""
    spec = MESSAGE_SPECS[message_type]
    if not isinstance(payload, spec.model):
        raise TypeError(f"{message_type.value} expects {spec.model.__name__}, got {type(payload).__name__}")
    return Envelope(
        message_id=message_id or uuid4(),
        boat_id=boat_id,
        mission_id=mission_id,
        message_type=message_type,
        timestamp=timestamp or datetime.now(timezone.utc),
        sequence_number=sequence_number,
        payload=payload.model_dump(mode="json"),
    )


def encode_envelope(envelope: Envelope) -> str:
    return envelope.model_dump_json()


def decode_envelope(raw: str | bytes) -> Envelope:
    """Parse and validate an envelope. Raises pydantic.ValidationError on bad input."""
    return Envelope.model_validate_json(raw)
