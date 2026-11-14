# ADR-0009: Simulator exemption in the boundary test

**Status:** PROPOSED

## Context

ADR-0003 and `CLAUDE.md` place Isaac Sim code in `adapters/src/adapters/simulation/isaac_sim/`. The boundary test in `tests/contracts/test_boundaries.py` was written to forbid any simulator import anywhere under `adapters/src`. Those two rules cannot both hold once a smoke test or live backend is added to the simulator folder.

## Decision

- The boundary test exempts only `adapters/src/adapters/simulation/isaac_sim/` from the rule that adapters may import nothing beyond `adapters`, `ai_box`, `marine_contracts` and `pydantic`.
- Simulator imports are still forbidden in `ai-box/src`, `fms/src` and `interfaces/src`.
- A test asserts that the exempt folder exists and that no simulator import appears in the rest of `adapters/src`.

## Consequences

- The Isaac Sim smoke test and the future live backend can live in their designated folder without weakening the core-package guard.
- The exemption widens what the simulator folder may import. Any new third-party dependency there still needs an ADR under `ADR-0005`.
- Status stays PROPOSED until the system architect accepts this change.
