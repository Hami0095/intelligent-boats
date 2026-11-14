# Module responsibilities

| Module | Owns | Must not | Depends on |
|---|---|---|---|
| `interfaces` (`marine_contracts`) | Message models, envelope, versioning, message registry | Perform I/O, hold state, import transports | pydantic |
| `ai-box` core | Service lifecycle, event bus, port definitions, operating state | Import adapters or simulators | interfaces |
| `ai-box` config, health | Settings from `AIBOX_*` variables; health aggregation | Read files or networks | interfaces |
| `ai-box` services | Sensor ingest, FMS bridge (sole FMS I/O), command router | Build envelopes for FMS-facing messages outside the bridge; touch devices | core, interfaces |
| `ai-box` perception | Detections, summaries, tracking interface | Estimate risk without a validated estimator; use semantic labels for decisions | core, interfaces |
| `ai-box` environment | Region indexing, typed observations, accepted mock observation ingress, search status | Depend on a particular mapping algorithm; infer semantic observations from collision detections | core, memory (persistence interface) |
| `ai-box` memory | Records with timestamp, provenance, confidence; mission memory; persistence interface | Treat old data as current | interfaces |
| `ai-box` decision | Mission lifecycle, exploration policy, reward interface | Hardcode an RL algorithm or reward function; steer the boat directly | environment, motion |
| `ai-box` motion | Goals, vehicle state, normalised commands, control interface, latched stop/fault inhibition and truthful command-delivery records | Know about hardware specifications; rearm an inhibited instance | core |
| `ai-box` telemetry | Boat state and health messages | Choose the transport | core, interfaces |
| `fms` | Boat identities, inbound endpoint, outbox, mission dispatch, stored boat data, audit, pure research latest-message projection | Import AI Box internals or adapters; perform HTTP I/O; invent missing data | interfaces |
| `adapters` | Device, network and simulator implementations of ports; research REST link and loopback HTTP server behind an injected application protocol | Be imported by the AI Box or the FMS; import FMS implementation | ai-box ports, interfaces |
| `fleet-dashboard` | Existing main simulation and explicit research REST read/view mode | Generate fallback telemetry in research; infer geographic positions or unsupported features | existing frontend tooling; research read API |
| `tests` | Contract, boundary and integration tests | Test against real hardware or simulators | all |

Ownership of each module, for review purposes, is in `agents/MODULE_OWNERSHIP.md`.
