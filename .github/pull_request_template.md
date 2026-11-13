## Title format
`<scope>: <imperative summary>` (see agents/GIT_AND_PR_STANDARD.md)

## Summary
<!-- What changes, in two or three sentences. -->

## Why
<!-- The problem or requirement this addresses. Link the OPEN_DECISIONS item or ADR if relevant. -->

## Modules touched
<!-- Tick every module changed. -->
- [ ] interfaces (contracts)
- [ ] ai-box
- [ ] fms
- [ ] adapters
- [ ] tests (cross-module)
- [ ] docs / agent instructions
- [ ] repo / CI / scripts

## Design decisions
<!-- Decisions made in this change and why. Write "None" if none. -->

## Open decisions and ADRs
<!-- New or changed entries in docs/OPEN_DECISIONS.md, or ADRs added. Write "None" if none. -->

## Tests run
<!-- Command and result, e.g. `python -m pytest` -> 111 passed. -->

## Checklist
- [ ] Branch name follows `<type>/<scope>-<summary>`
- [ ] Commits follow `<scope>: <imperative summary>`
- [ ] Branch is up to date with `main`
- [ ] `python -m pytest` passes from the repository root
- [ ] Architecture-boundary tests pass and were not weakened
- [ ] Affected documentation updated
- [ ] No secrets, caches or generated files committed
- [ ] Contract changes follow `interfaces/contracts/README.md`

## Remaining uncertainties
<!-- Required, even if it is "None". List anything a reviewer should question. -->

---
<!-- If an AI assistant wrote this change, keep the attribution line its tooling adds. -->
