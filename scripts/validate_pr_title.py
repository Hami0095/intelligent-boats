#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import sys

ALLOWED_TYPES = {"feat", "fix", "docs", "test", "refactor", "perf", "build", "ci", "chore", "revert"}
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


def _candidate() -> str:
    if len(sys.argv) > 1:
        return sys.argv[1]
    return os.environ.get("PR_TITLE", "")


def _normalize_description(description: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", description.lower()).strip()


def is_valid_pr_title(title: str) -> bool:
    title = title.strip()
    if not title:
        return False

    subject = title.splitlines()[0].strip()
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
    title = _candidate()
    if not title:
        print("PR title is empty. Provide a title such as 'feat(ai-box): add service lifecycle manager'.")
        return 1

    if is_valid_pr_title(title):
        return 0

    print(
        "PR title is invalid. Use 'type(scope): description' with a required scope "
        "and a lowercase opening description. Example: "
        "'feat(ai-box): add service lifecycle manager'."
    )
    print(f"Received: {title}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
