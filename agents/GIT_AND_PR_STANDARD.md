# Git, branch and pull request standard

**Applies to every human and every AI agent** that changes this repository. Agents must follow it exactly. If a rule here conflicts with a tool default, this file wins.

## 1. Branches

`main` is protected. Nobody commits to it directly. Every change starts on a short-lived branch created from an up-to-date `main`.

### Name format

```
<type>/<scope>-<summary>
```

- **type**: one of the values below.
- **scope**: the module the change is mainly in.
- **summary**: 2 to 5 words, lowercase, hyphen-separated, describing the outcome.
- Total length 60 characters or fewer. Lowercase ASCII only: letters, digits and hyphens. No spaces, no uppercase, no underscores, no personal names, no dates, no ticket-free words like "stuff" or "fix2".

| type | Use for |
|---|---|
| `feat` | New behaviour or capability |
| `fix` | Correcting wrong behaviour |
| `refactor` | Restructuring with no behaviour change |
| `test` | Tests only |
| `docs` | Documentation only |
| `chore` | Tooling, CI, dependencies, housekeeping |
| `spike` | Time-boxed experiment. Never merged to `main`; deleted or turned into an ADR |

| scope | Covers |
|---|---|
| `interfaces` | `interfaces/`, the message contracts |
| `ai-box` | `ai-box/` |
| `fms` | `fms/` |
| `adapters` | `adapters/` |
| `tests` | cross-module `tests/` |
| `docs` | `docs/`, ADRs, agent instructions |
| `repo` | root files, CI, `scripts/` |

Examples:

- `feat/ai-box-record-visits-from-position`
- `fix/fms-reject-duplicate-acks`
- `feat/interfaces-add-obstacle-track-id`
- `docs/repo-git-standard`
- `spike/ai-box-kalman-position-fusion` (must not be merged)

### Rules

- One branch, one purpose. If you find a second problem, make a second branch.
- Keep branches short-lived. Rebase or merge `main` in regularly; do not let a branch drift for weeks.
- Do not push to another person's branch unless they ask you to.
- Delete the branch after its pull request is merged.

## 2. Commits

Subject line:

```
<scope>: <imperative summary>
```

- Imperative mood ("add", "fix", "remove"), not "added" or "fixes".
- 72 characters or fewer. No full stop at the end.
- Scope uses the same names as branches.

Body (required when the change is not obvious from the subject):

- What changed and **why**.
- Any decision taken, and the ADR or `OPEN_DECISIONS.md` entry it relates to.
- Anything a reviewer must know.

Example:

```
ai-box: record visits from the position source

Visits feed environment knowledge but are not search coverage (see
ADR-0002 and OPEN_DECISIONS item 7). Visit confidence is a fixed
placeholder until a position-quality model exists.
```

Rules:

- Commit in logical steps. Each commit should pass `python -m pytest` where practical.
- Never commit secrets, `.env` files, `__pycache__`, `*.egg-info`, `exports/`, editor folders or OS junk. The `.gitignore` covers these; do not override it.
- If an AI assistant wrote the commit, keep the trailers its tooling requires (for example `Co-Authored-By:`). Do not remove them.

## 3. Pull requests

### Title

Same format as a commit subject: `<scope>: <imperative summary>`. A reviewer should understand the change from the title alone.

### Size

- Target 400 changed lines or fewer, excluding generated files and lock files.
- Larger changes are split. An ADR or contract change can go first in its own PR, followed by the code that uses it.

### Body

Use the template in `.github/pull_request_template.md`. Every section must be filled in. Write `None` if a section does not apply. Do not delete sections.

### Before opening

1. Branch is up to date with `main`.
2. `python -m pytest` passes from the repository root.
3. Documentation affected by the change is updated (see root `CLAUDE.md`, "How agents should update documentation").
4. New open questions are recorded in `docs/OPEN_DECISIONS.md`.
5. No architecture-boundary test was weakened.

### Review

- At least **one approval** from the owner of each module touched (`.github/CODEOWNERS` and `agents/MODULE_OWNERSHIP.md`).
- Changes to `interfaces/` or `tests/contracts/` also need the system architect's approval.
- Changes that alter architecture need an ADR, with status `PROPOSED` in the PR and `ACCEPTED` only after the team agrees.
- Reviewers check the code, the tests, the documentation and the boundary rules. Authors respond to every comment: fix it, or explain why not.
- Authors do not merge their own PRs without an approval.

### Merge

- **Squash merge** into `main`. The squashed commit uses the PR title as its subject.
- Merge only when CI is green and all required reviews are present.
- Delete the source branch.

## 4. Agents

AI agents follow the same rules as people, with these additions:

- Create the branch yourself using the format above. Do not work on `main`.
- Commit only files relevant to the task. Report anything unrelated you noticed; do not include it.
- Open the PR with the full template. The "Remaining uncertainties" section is mandatory.
- Do not merge PRs. A human approves and merges.
- If you cannot push or open a PR, say so in your report and give the exact branch name and commit list so a human can finish it.

## 5. Things nobody does

- Force-push to `main`, or any shared branch.
- Rewrite history on a branch someone else has pulled.
- Disable a failing test, or mark one skipped, to get a green build.
- Weaken `tests/contracts/test_boundaries.py`.
- Commit a simulator or vendor import into `ai-box/`, `fms/` or `interfaces/`.
- Merge with failing CI.

## 6. Repository setup (for maintainers)

Configure `main` with branch protection:

- Require a pull request before merging, with at least one approval and code-owner review.
- Require the `CI` status check to pass, and the branch to be up to date.
- Require linear history (squash merges only).
- Block force-pushes and deletions.
- Automatically delete head branches after merge.
