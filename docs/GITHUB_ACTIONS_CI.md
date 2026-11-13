# GitHub Actions PR validation and merge policy

This document defines the repository-side CI behavior and the manual GitHub ruleset settings required to enforce the intended merge policy for `main`.

## Repository-side implementation (in this repository)

### Workflow and required check name

- File: `/home/runner/work/intelligent-boats/intelligent-boats/.github/workflows/ci.yml`
- Workflow name: `PR validation`
- Required status check name to select in rulesets/branch protection: **`PR validation`** (the single job/check run name)
- Triggers:
  - `pull_request` to `main` for `opened`, `synchronize`, `reopened`, `ready_for_review`
  - `workflow_dispatch` for manual runs
- Security model:
  - Uses `pull_request` (not `pull_request_target`) to execute contributor code safely
  - Minimal permission scope: `contents: read`
  - No deployment or privileged repository mutation steps

### Checks executed by `PR validation`

1. Repository standards
   - `python scripts/validate_branch_name.py` (pull request events)
   - `python scripts/validate_pr_title.py` (pull request events)
   - `python scripts/validate_repo_structure.py`
2. Python quality and type safety
   - `python -m ruff check .`
   - `python -m ruff format --check .`
   - `python -m mypy ai-box/src fms/src interfaces/src adapters/src`
3. Architecture boundaries
   - `python -m pytest tests/contracts/test_boundaries.py`
4. Contracts and service behavior tests with coverage gate
   - `python -m pytest --cov=interfaces/src --cov=ai-box/src --cov=fms/src --cov=adapters/src --cov-report=term-missing --cov-fail-under=90`
5. Security dependency audit
   - `python -m pip_audit --desc --progress-spinner off`

### Detailed violations reporting

Every run publishes a **Pull Request Validation Report** in the job summary and uploads per-check logs as the `ci-validation-logs` artifact.

The report includes:
- PR number and commit SHA
- Overall status
- Category table (PASS / FAIL / NOT CHECKED)
- Executed checks with exact command/rule and log references
- Violation entries (file/line/rule/problem/suggested fix) when determinable
- Test summary line when available
- Checks not executed and why

The workflow is fail-closed: if any validation fails, the `PR validation` check fails. Failed/cancelled runs are never reported as success.

## CODEOWNERS policy

- File: `/home/runner/work/intelligent-boats/intelligent-boats/.github/CODEOWNERS`
- Configured owner policy:
  - `* @Hami0095`
  - `/.github/CODEOWNERS @Hami0095`

No existing ownership conflict was found in the repository file set; placeholder owners were replaced with the explicit owner policy above.

## Intended merge policy and manual GitHub ruleset setup

Repository files cannot set remote rulesets directly. Configure rulesets manually in GitHub.

### Ruleset A (CI gate, no admin bypass)

Purpose: ensure required CI checks for **everyone**, including administrators.

Recommended settings:
1. Target: default branch (`main`)
2. Enforcement: Active
3. Require status checks to pass:
   - `PR validation`
4. Require branch to be up to date before merging (recommended)
5. **Administrator/bypass disabled** for this ruleset

Result: CI cannot be bypassed by `@Hami0095` or other administrators.

### Ruleset B (review gate, admin bypass allowed)

Purpose: enforce contributor review policy while allowing owner self-merges when needed.

Recommended settings:
1. Target: default branch (`main`)
2. Require pull request before merging
3. Require at least 1 approval
4. Require Code Owner review
5. Dismiss stale approvals on new commits
6. Require conversation resolution before merging
7. Keep force-push and branch-deletion blocked
8. **Administrator/bypass enabled** for this ruleset

Result:
- Contributor PRs require `@Hami0095` approval (as sole code owner).
- `@Hami0095` can merge his own PRs by using administrator bypass for review requirements.
- CI still remains mandatory because Ruleset A does not allow bypass.

## Important limitation: bypass scope is not exclusive to one user

Administrator/bypass capability is tied to GitHub permissions and ruleset bypass lists, not to repository text files alone.

If other accounts are granted equivalent administrator or explicit bypass rights, they may also bypass Ruleset B review requirements. Do **not** claim bypass is exclusive to `@Hami0095` unless repository permissions/ruleset bypass actors are explicitly restricted in GitHub settings.

## Self-authored PR behavior

GitHub does not allow users to approve their own pull requests. Therefore:
- Do not require `@Hami0095` to self-approve his own PRs.
- Use the Ruleset B administrator bypass path for self-authored PR review requirements when necessary.
- `PR validation` remains required and cannot be bypassed under the Ruleset A design above.

## Plan/permission limitations to verify in GitHub UI

Feature availability (rulesets, bypass options, enforcement controls) can vary by GitHub plan and repository ownership model.

Administrators should verify:
- rulesets are available,
- bypass controls are exposed,
- and status checks can be selected exactly as `PR validation`.

If specific controls are unavailable, record that limitation in repository governance notes and use the closest equivalent branch-protection settings.

## What is intentionally not implemented here

- No automatic merge behavior
- No weakening of CI requirements
- No remote ruleset/branch protection mutations from repository code
- No privileged `pull_request_target` execution path for untrusted PR code

