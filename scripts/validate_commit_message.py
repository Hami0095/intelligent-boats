#!/usr/bin/env python3
from __future__ import annotations

import re
import sys

GENERIC_TITLES = {
    "updates",
    "changes",
    "fixes",
    "final code",
    "work",
    "wip",
    "code cleanup",
    "misc updates",
}
CONVENTIONAL_RE = re.compile(
    r"(?P<type>feat|fix|docs|test|refactor|perf|build|ci|chore|revert)"
    r"\(\s*(?P<scope>[a-z0-9][a-z0-9-]*)\s*\):\s*"
    r"(?P<description>[a-z][a-z0-9][a-z0-9 ,;:/\"'\-]*[a-z0-9])"
)
REPO_STYLE_RE = re.compile(
    r"(?P<scope>[a-z0-9][a-z0-9-]*):\s*"
    r"(?P<description>[a-z][a-z0-9][a-z0-9 ,;:/\"'\-]*[a-z0-9])"
)


def _normalize_description(description: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", description.lower()).strip()


def is_valid_commit_message(message: str) -> bool:
    text = message.strip()
    if not text:
        return False
    if text.startswith("Merge "):
        return True
    subject = text.splitlines()[0].strip()
    conventional = CONVENTIONAL_RE.fullmatch(subject)
    if conventional:
        description = conventional.group("description")
        normalized = _normalize_description(description)
        return normalized not in GENERIC_TITLES and not any(generic in normalized for generic in GENERIC_TITLES)
    repo_style = REPO_STYLE_RE.fullmatch(subject)
    if repo_style:
        description = repo_style.group("description")
        normalized = _normalize_description(description)
        return normalized not in GENERIC_TITLES and not any(generic in normalized for generic in GENERIC_TITLES)
    return False


def main() -> int:
    incoming = sys.stdin.read().strip()
    if not incoming:
        print("No commit message was provided.")
        return 1
    if is_valid_commit_message(incoming):
        return 0
    print(
        "Commit message is invalid. Use 'type(scope): description', for example "
        "'feat(ai-box): add service lifecycle manager'."
    )
    print(f"Received:\n{incoming}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
