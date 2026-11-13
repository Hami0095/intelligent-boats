# ADR-0002: Separate perception from environment knowledge

**Status:** ACCEPTED

## Context

Obstacle detection for collision prevention and the knowledge of which areas have been searched look similar (both involve position and sensing) but differ in purpose, data, rate and failure modes.

## Decision

- `ai_box.perception` produces collision-relevant detections and summaries.
- `ai_box.environment` records visits, search coverage and observations at region level.
- They communicate only through the event bus and typed messages. Neither imports the other.

## Consequences

- A failing detector degrades perception without corrupting search progress.
- Search-progress models can change without affecting collision handling.
- Some data (for example, an observed object's position) must pass between them explicitly. Those pathways are defined in `DATA_FLOW.md`.
