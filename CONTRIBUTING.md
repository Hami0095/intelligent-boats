# Contributing

## Before you start

1. Read `CLAUDE.md` and `AGENTS.md`.
2. Read the `CLAUDE.md` of the module you will change (`ai-box/`, `fms/`, `adapters/`, `interfaces/`).
3. Check `docs/OPEN_DECISIONS.md`. If your change depends on an open decision, say so in your pull request and do not decide it silently.

## Workflow

The full standard is `agents/GIT_AND_PR_STANDARD.md`. In short:

1. Branch from an up-to-date `main` using `<type>/<scope>-<summary>`, for example `feat/ai-box-record-visits`.
2. Make the change in one module where possible. Cross-module changes go through `interfaces/` contracts.
3. Add or update tests (contract, unit or integration, as appropriate).
4. Update the documentation the change affects.
5. Run `python -m pytest` from the repository root. It must pass.
6. Open a pull request titled `<scope>: <imperative summary>`, using the template. Get an approval from each module owner. Squash-merge.

## Rules that reviewers enforce

- Architecture boundaries are tested in `tests/contracts/test_boundaries.py`. A failing boundary test means the design is being violated; fix the design, not the test.
- Do not add a runtime dependency without an ADR. Do not add ROS 2, TensorRT, a database, an RL framework or a model as a mandatory dependency.
- Do not hardcode hardware specifications or mission requirements that are not confirmed.
- Message changes follow the compatibility rules in `interfaces/contracts/README.md`.

## Commit and pull request style

Commit subjects: `<scope>: <imperative summary>`, 72 characters or fewer. Full rules, including branch names, PR size, review and merge, are in `agents/GIT_AND_PR_STANDARD.md`.
