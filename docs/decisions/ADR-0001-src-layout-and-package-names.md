# ADR-0001: src layout and package names

**Status:** ACCEPTED

## Context

The brief uses folder names such as `ai-box/` and `fms/`, which contain `core/`, `config/` and `tests/` folders. Two packages with a `core` subpackage would collide on import. Folder names containing hyphens cannot be imported.

## Decision

- Each Python project uses a `src/` layout: `ai-box/src/ai_box/`, `fms/src/fms/`, `interfaces/src/marine_contracts/`, `adapters/src/adapters/`.
- Import names are underscored, and each project is named after its import name.
- The folder structure from the brief is otherwise kept (`core`, `services`, `perception` and so on live inside the package).

## Consequences

- Packages cannot import each other's `core` by accident, because the top-level names differ.
- Tests run from the root without installing, via `pytest.ini`.
- Editable installs create `*.egg-info` folders, which are git-ignored.
