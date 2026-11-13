# AGENTS.md - guide for any AI coding assistant

This repository is shared by several engineers and their AI tools. Conversation memory is not shared between them. **The repository documents are the source of truth.** Read this file, then `CLAUDE.md` at the root, then the `CLAUDE.md` of the module you are changing.

## Rules

1. Read `CLAUDE.md` (root) and the module's `CLAUDE.md` before editing.
2. Respect the module boundaries: `interfaces` (contracts) <- `ai-box`, `fms` and `adapters`. `ai-box` and `fms` never import each other. Nothing outside `adapters` imports adapters. `ai-box` never imports Isaac Sim.
3. Do not invent hardware specifications, sensor capabilities or mission requirements.
4. Do not silently change the architecture. If you think it should change, write an ADR proposal in `docs/decisions/` and stop.
5. Document assumptions and open questions in `docs/OPEN_DECISIONS.md`.
6. Update documentation when interfaces or responsibilities change.
7. Add or update tests. Run `python -m pytest` from the repository root.
8. Do not edit modules unrelated to your task.
9. Follow `agents/GIT_AND_PR_STANDARD.md` for branch names, commits and pull requests. Never work on `main`.
10. When you finish, report: files changed, design decisions made, and remaining uncertainties.

## Quick map

| Question | Read |
|---|---|
| What is the system? | `docs/SYSTEM_OVERVIEW.md` |
| How are the parts connected? | `docs/SYSTEM_ARCHITECTURE.md`, `docs/DATA_FLOW.md` |
| What do messages look like? | `docs/COMMUNICATION_PROTOCOL.md`, `interfaces/src/marine_contracts/` |
| Who owns what? | `docs/MODULE_RESPONSIBILITIES.md`, `agents/MODULE_OWNERSHIP.md` |
| What is still undecided? | `docs/OPEN_DECISIONS.md` |
| How do I run and test? | `docs/DEVELOPMENT_WORKFLOW.md` |
| How do I branch, commit and open a PR? | `agents/GIT_AND_PR_STANDARD.md` |
