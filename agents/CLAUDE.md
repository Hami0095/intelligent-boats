# Agent engineering context

Persistent instructions for every AI agent working in this repository. The root `CLAUDE.md` is the project-wide authority; this file adds working rules.

## Before you change anything

1. Read the root `CLAUDE.md`.
2. Read the module documentation you will touch: the module's `CLAUDE.md`, and the relevant pages in `docs/`.
3. Read `MODULE_OWNERSHIP.md` to know who owns the code and which interfaces it must respect.
4. Read `OPEN_DECISIONS.md`. If your task depends on an open item, say so and do not decide it silently.

## Rules

- **Never invent hardware capabilities or mission requirements.** If a value is not confirmed, label it as an assumption, in code and in documentation.
- **Never silently change established architecture.** Propose a change as an ADR draft in `docs/decisions/` and stop for review.
- **Document assumptions and unresolved decisions** in `docs/OPEN_DECISIONS.md`.
- **Update documentation** when interfaces or responsibilities change.
- **Add or update tests** for every behaviour you add or change. Run `python -m pytest` from the repository root.
- **Avoid unrelated modules.** If you find a problem elsewhere, report it instead of fixing it.
- **Respect boundaries.** The AI Box does not import the FMS or adapters. The FMS does not import the AI Box. No package outside `adapters` imports a simulator.

## Git and pull requests

Every agent follows `GIT_AND_PR_STANDARD.md` in this folder: branch names, commit subjects, PR template, review and merge rules. Never work on `main`. Never merge.

## Reporting

End every task with:

1. Files changed (paths).
2. Design decisions made, and why.
3. Assumptions and open questions added to `OPEN_DECISIONS.md`.
4. Test results.
5. What you did not do, and why.

## Style

- Prefer small, explicit interfaces over clever abstractions.
- Name things after the domain: region, observation, goal, obstacle, mission.
- Do not add a dependency without an ADR.
