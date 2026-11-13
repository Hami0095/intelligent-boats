"""Exports JSON Schema for every contract payload to exports/schemas/ (git-ignored).

Usage (from the repository root): python scripts/export_schemas.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "interfaces" / "src"))

from marine_contracts import MESSAGE_SPECS, Envelope  # noqa: E402


def main() -> None:
    out = ROOT / "exports" / "schemas"
    out.mkdir(parents=True, exist_ok=True)
    (out / "envelope.json").write_text(json.dumps(Envelope.model_json_schema(), indent=2), encoding="utf-8")
    for message_type, spec in MESSAGE_SPECS.items():
        path = out / f"{message_type.value}.json"
        path.write_text(json.dumps(spec.model.model_json_schema(), indent=2), encoding="utf-8")
    print(f"wrote {len(MESSAGE_SPECS) + 1} schema files to {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
