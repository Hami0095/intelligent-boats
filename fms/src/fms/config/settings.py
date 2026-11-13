"""FMS configuration from FMS_* environment variables."""

from __future__ import annotations

import os
from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, Field

ENV_PREFIX = "FMS_"


class FmsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    outbox_limit_per_boat: int = Field(default=1000, gt=0)
    dedupe_window: int = Field(default=10_000, gt=0)


def load_config(environ: Mapping[str, str] | None = None) -> FmsConfig:
    source = os.environ if environ is None else environ
    raw = {k[len(ENV_PREFIX) :].lower(): v for k, v in source.items() if k.startswith(ENV_PREFIX)}
    return FmsConfig.model_validate(raw)
