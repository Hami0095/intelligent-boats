#!/usr/bin/env python3
from __future__ import annotations

import os
import re

DEFAULT_BRANCHES = {"main", "master", "develop"}
ALLOWED_PREFIXES = {
    "feature",
    "fix",
    "bugfix",
    "hotfix",
    "refactor",
    "docs",
    "test",
    "ci",
    "chore",
    "feat",
}
PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _branch_name() -> str:
    for key in ("BRANCH_NAME", "GITHUB_HEAD_REF", "GITHUB_REF_NAME"):
        value = os.environ.get(key, "").strip()
        if value:
            return value
    return ""


def is_valid_branch_name(branch_name: str) -> bool:
    if not branch_name:
        return False
    if branch_name.startswith("refs/"):
        if branch_name.startswith("refs/tags/") or branch_name.startswith("refs/pull/"):
            return True
        branch_name = branch_name.removeprefix("refs/heads/")
    if branch_name in DEFAULT_BRANCHES:
        return True
    if branch_name.startswith("HEAD"):
        return True
    if "/" not in branch_name:
        return False
    prefix, suffix = branch_name.split("/", 1)
    if prefix not in ALLOWED_PREFIXES:
        return False
    if not suffix:
        return False
    if not PATTERN.fullmatch(suffix):
        return False
    return True


def main() -> int:
    branch_name = _branch_name()
    if not branch_name:
        print("No branch was provided for validation.")
        return 1
    if is_valid_branch_name(branch_name):
        return 0
    print(
        "Branch name is invalid. Use one of: "
        "feature/<short-description>, fix/<short-description>, bugfix/<short-description>, "
        "hotfix/<short-description>, refactor/<short-description>, docs/<short-description>, "
        "test/<short-description>, ci/<short-description>, chore/<short-description>, "
        "feat/<scope>-<summary>, or a protected default branch such as main."
    )
    print(f"Received: {branch_name}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
