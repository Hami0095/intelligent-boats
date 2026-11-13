# ADR-0005: Python-first with minimal dependencies

**Status:** ACCEPTED

## Context

The team needs an approachable, testable foundation. Heavy frameworks (ROS 2, TensorRT, a database, an RL framework) are not yet justified by a confirmed requirement.

## Decision

- Python 3.10+ with type hints.
- pydantic v2 for contract validation. The only runtime dependency.
- pytest for tests.
- Standard `logging`, environment variables for configuration.
- Any new dependency needs an ADR and must be justified by a confirmed need.

## Consequences

- Installation is simple and the architecture tests can enforce the allowed dependencies.
- Performance-critical or hardware-facing code may later need another language or framework. That would be a new ADR.
