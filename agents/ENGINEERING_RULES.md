# Engineering rules

1. **Contracts first.** A message change starts in `interfaces/` with a test. Dependent code follows.
2. **Ports, not vendors.** Core code depends on Protocols in `ai_box/core/ports.py`. Vendor code lives in `adapters/`.
3. **Timestamps are UTC and timezone-aware.** Naive datetimes are errors.
4. **Units are in the name or the type.** Metres in `_m`, seconds in `_s`, speeds in `_mps`, degrees in `_deg`. Normalised commands are in [-1, 1].
5. **Explicit refusal beats silent acceptance.** A command the boat cannot perform is rejected with a reason.
6. **Failures are visible.** Services report health; errors are logged with context. Do not swallow exceptions without logging.
7. **Bounded everything.** Queues, histories and caches have size limits.
8. **Unknown is not zero.** Use `None` for unknown values. Never fabricate a risk, a position or a reward.
9. **Tests are required.** Unit tests for behaviour, contract tests for messages, integration tests for cross-module flows.
10. **Boundaries are enforced by tests.** Do not weaken `tests/contracts/test_boundaries.py` to make a change pass. Redesign the change instead.
11. **Small commits, clear subjects.** Name the module in the subject.
