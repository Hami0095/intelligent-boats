#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

REQUIRED_ITEMS = [
    "AGENTS.md",
    "CLAUDE.md",
    "README.md",
    "docs",
    "agents",
    "interfaces",
    "ai-box",
    "fms",
    "adapters",
    ".github",
    ".github/workflows/ci.yml",
]


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    missing = [item for item in REQUIRED_ITEMS if not (root / item).exists()]
    if missing:
        print("Repository structure validation failed. Missing:")
        for item in missing:
            print(f"  - {item}")
        return 1
    print("Repository structure validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
