"""AI Box configuration, loaded from AIBOX_* environment variables.

Unknown AIBOX_* variables are an error (extra="forbid") so typos are caught early.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from marine_contracts.envelope import BOAT_ID_PATTERN

ENV_PREFIX = "AIBOX_"


class AIBoxConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    boat_id: str = Field(default="boat-dev-01", pattern=BOAT_ID_PATTERN)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    telemetry_interval_s: float = Field(default=5.0, gt=0.0)
    outbound_buffer_limit: int = Field(default=1000, gt=0)
    short_term_capacity: int = Field(default=500, gt=0)
    short_term_max_age_s: float = Field(default=60.0, gt=0.0)


def load_config(environ: Mapping[str, str] | None = None) -> AIBoxConfig:
    source = os.environ if environ is None else environ
    raw = {
        key[len(ENV_PREFIX):].lower(): value
        for key, value in source.items()
        if key.startswith(ENV_PREFIX)
    }
    return AIBoxConfig.model_validate(raw)
