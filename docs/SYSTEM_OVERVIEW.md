# System overview

**Status:** foundation. Describes the intended system and what the repository establishes. Items marked OPEN are not decided.

## Purpose

A fleet of autonomous unmanned surface vessels (USVs). Each boat is assigned a search area by the Fleet Management System (FMS), searches it for a target or reward, avoids physical obstacles, and reports what it is doing.

## What each boat must do

- Receive missions and instructions from the FMS.
- Understand its local environment through sensors.
- Search its assigned area without repeatedly covering the same ground.
- Avoid collisions with rocks, large fish, other autonomous boats, other boats and ships, and similar objects.
- Control its movement and propulsion through defined interfaces.
- Keep memory of its environment and search progress.
- Report telemetry, mission progress, observations, events and logs to the FMS.

There is **no boat-to-boat communication** and no swarm requirement. Each boat talks to the FMS only.

## Two separate concerns

| Concern | Question it answers | Module |
|---|---|---|
| Obstacle detection and collision avoidance | Is something in my path, how far is it, and is it a collision risk? | `ai_box.perception` |
| Environment knowledge and reward-seeking | Where have I been, what have I searched, where should I search next? | `ai_box.environment`, `ai_box.decision` |

They are separate because they change at different rates, need different data, and fail differently. Keeping them apart stops a search-progress bug from affecting collision avoidance, and the reverse.

## Reward

The reward definition and reward signal are not yet provided. The boat is **not** given the location of the reward. The decision layer exposes a reward interface (`RewardSignal`) so approaches can be evaluated later. The foundation returns "no reward information", which is never treated as zero.

## Development and final demonstration

- Two deliverables are developed in parallel: the physical boat design (CAD) and the onboard software.
- The software is developed and tested independently of any simulator.
- For the final demonstration, the boat design and software are integrated into NVIDIA Isaac Sim through an adapter. See `INTEGRATION_GUIDE.md`.
- The same architecture is intended to run on real hardware through hardware adapters.

## What this repository is not

Not a finished autonomous boat, not an FMS dashboard, not a production backend, not a trained model. See `OPEN_DECISIONS.md` for what remains open.
