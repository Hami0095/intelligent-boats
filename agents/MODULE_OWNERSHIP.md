# Module ownership

Ownership is by responsibility, for review. Owners are roles; assign people in the team's own tracking tool. A change to a module you do not own needs the owner's review.

| Module | Owner role | Subagent | Must coordinate with |
|---|---|---|---|
| `interfaces/` | System architect | `system-architect` | Every module (contract changes affect all) |
| `ai-box/` core, config, services, telemetry | Integration engineer | `integration-engineer` | Communications, Motion |
| `ai-box/perception/` | Perception engineer | `perception-engineer` | Motion (for obstacle use), Environment |
| `ai-box/environment/`, `ai-box/memory/` | Environment engineer | `environment-engineer` | Decision, Perception |
| `ai-box/decision/` | Environment engineer (with System architect for policy interfaces) | `environment-engineer` | Motion, Mission owners |
| `ai-box/motion/`, propulsion adapters | Motion engineer | `motion-engineer` | CAD, Hardware |
| `fms/` and FMS-side communication | Communications engineer | `communications-engineer` | Integration (bridge), FMS team |
| `adapters/` (non-simulator) | Integration engineer | `integration-engineer` | Owner of the port being implemented |
| `adapters/simulation/` | Integration engineer | `integration-engineer` | CAD (model import), demo team |
| `tests/contracts/`, `tests/integration/` | System architect | `system-architect` | Owners of the modules tested |
| `docs/`, `CLAUDE.md`, `AGENTS.md` | System architect | `system-architect` | Everyone |
