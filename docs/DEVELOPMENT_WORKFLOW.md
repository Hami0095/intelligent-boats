# Development workflow

## Setup

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -e interfaces -e ai-box -e fms -e adapters pytest
```

Requires Python 3.10 or newer. Editable installs create `*.egg-info` folders, which git ignores.

## Daily commands

| Task | Command |
|---|---|
| Run all tests | `python -m pytest` (from the repository root) |
| Run one area | `python -m pytest ai-box/tests`, `fms/tests`, `adapters/tests`, `tests/contracts`, `tests/integration` |
| Demo | `python scripts/demo_mock_boat.py` |
| Export JSON Schema | `python scripts/export_schemas.py` (writes to git-ignored `exports/`) |

Tests run without installing, because `pytest.ini` adds the source directories to the path.

## Where a change goes

| Change | Start in | Also update |
|---|---|---|
| New or changed message field | `interfaces/src/marine_contracts/payloads.py` | contract tests, `COMMUNICATION_PROTOCOL.md`, `interfaces/contracts/README.md` if the version changes |
| New AI Box service | `ai-box/src/ai_box/<module>/` and `bootstrap.py` | module `CLAUDE.md`, a unit test, an integration test if it crosses modules |
| New device or simulator | `adapters/src/adapters/<kind>/` | a test that runs the port's behaviour, `INTEGRATION_GUIDE.md` if it is a new integration |
| New FMS feature | `fms/src/fms/<module>/` | `fms/CLAUDE.md`, FMS tests |
| Architectural choice | an ADR in `docs/decisions/` | `SYSTEM_ARCHITECTURE.md` |

## Definition of done

- `python -m pytest` passes.
- Architecture-boundary tests pass.
- New behaviour has tests.
- Affected documentation is updated.
- Open questions are recorded in `OPEN_DECISIONS.md`, not decided silently.
- The pull request lists files changed, decisions, and uncertainties.

## Working with AI coding assistants

- Start the assistant in the repository root so it reads `CLAUDE.md`.
- Point it at the module `CLAUDE.md` for module work.
- Claude Code users can use the subagents in `.claude/agents/`. Other tools should follow `AGENTS.md`.
- Do not rely on a previous conversation. If something matters, write it into the repository.
