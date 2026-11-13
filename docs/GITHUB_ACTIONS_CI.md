# GitHub Actions PR validation and merge controls

This document explains what is implemented in-repository and what must be configured in the GitHub web UI.

## What this repository now enforces in code

### Workflow

- File: `.github/workflows/ci.yml`
- Workflow name: `CI`
- Stable required job/check name: `PR validation`
- Triggers:
  - `pull_request` on `main` for: `opened`, `synchronize`, `reopened`, `ready_for_review`
  - `workflow_dispatch` for manual runs
- Security model:
  - Uses `pull_request` (not `pull_request_target`) for untrusted PR code
  - Uses minimum workflow permission: `contents: read`
  - No deployment steps, no hardware access, no Isaac Sim usage

### Automated checks run by `PR validation`

1. Install and tooling setup:
   - `python -m pip install --upgrade pip`
   - `python -m pip install -e interfaces -e ai-box -e fms -e adapters`
   - `python -m pip install pytest pytest-cov ruff mypy pip-audit`
2. Repository standards:
   - `python scripts/validate_branch_name.py` (PR events)
   - `python scripts/validate_pr_title.py` (PR events)
   - `python scripts/validate_repo_structure.py`
3. Python quality:
   - `python -m ruff check .`
   - `python -m ruff format --check .`
   - `python -m mypy ai-box/src fms/src interfaces/src adapters/src`
4. Architecture regression:
   - `python -m pytest tests/contracts/test_boundaries.py`
5. Tests and coverage:
   - `python -m pytest --cov=interfaces/src --cov=ai-box/src --cov=fms/src --cov=adapters/src --cov-report=term-missing --cov-fail-under=90`
6. Security:
   - `python -m pip_audit --desc --progress-spinner off`
   - `gitleaks/gitleaks-action@v2`

### Validation report

Every run writes a **Pull Request Validation Report** into the job summary, including:

- PR number and commit SHA
- Overall status (PASSED/FAILED)
- Category status table (PASS/FAIL/NOT CHECKED)
- Executed check table with command and log references
- Violations with file/line/rule/problem/suggested fix when determinable
- Test count summary (from pytest output when available)
- Checks not executed and reasons
- Artifact reference for detailed logs

Raw logs are uploaded as artifact: `ci-validation-logs`.

## CODEOWNERS configuration

- File: `.github/CODEOWNERS`
- Owner policy implemented: `@Hami0095` is the sole owner for `*` (all files), including `.github/CODEOWNERS` itself.

Important: CODEOWNERS requests review but **does not block merges by itself**. Branch protection/rulesets must enforce blocking rules.

## Required manual GitHub web UI configuration

Repository administrators must configure branch protection (or a ruleset) for `main`:

1. **Require a pull request before merging**
2. **Require approvals** (at least 1)
3. **Require review from Code Owners**
4. **Require status checks to pass** and select:
   - `PR validation`
5. **Dismiss stale approvals when new commits are pushed**
6. **Require conversation resolution before merging**
7. **Do not allow force pushes**
8. **Do not allow branch deletion**
9. If available in your plan/settings: disable admin bypass (`Include administrators` / equivalent)

## Verify `@Hami0095` approval enforcement

1. Open a PR from a non-main branch.
2. Confirm `@Hami0095` is requested by CODEOWNERS.
3. Confirm `PR validation` appears and must pass.
4. Confirm merge button remains blocked until required code-owner approval and checks are satisfied.

## Self-authored PR approval deadlock

A user cannot approve their own PR. If `@Hami0095` is the PR author, strict code-owner approval can deadlock.

Recommended policy options:

- Add at least one additional trusted code owner/reviewer for emergency/unblocking.
- Or define a separate authorized reviewer path in branch protection/rulesets.

Do **not** bypass protections ad hoc.

## Deliberate violation testing

To test enforcement safely:

1. Create a branch with an invalid branch name pattern and confirm branch-name validation fails.
2. Or open a PR with an invalid title format and confirm PR-title validation fails.
3. Or introduce a temporary lint violation and confirm `PR validation` fails and summary includes the violation.
4. Push a fix commit and confirm the workflow reruns on `synchronize` and updates status.

## Reruns and new commits

- Manual rerun: use the Actions "Re-run jobs" button.
- New commits to an open PR automatically trigger a new run (`synchronize`).
- With stale-approval dismissal enabled, new commits also invalidate previous approvals.

## Permissions and plan limitations

- Rulesets/branch-protection feature availability can depend on repository plan and org policy.
- If "Include administrators" or equivalent is unavailable, document this as a governance limitation.
- Ensure `@Hami0095` has admin/maintainer permissions required to configure protections.

## What is intentionally not changed here

- Remote branch protection/rulesets are **not** modified by repository files.
- No workflow uses privileged events (`pull_request_target`) for untrusted PR code.
- No deployment or environment-secret workflow is included for PR validation.
