# scripts

| Script | Purpose |
|---|---|
| `demo_mock_boat.py` | Runs one mock boat against the FMS end to end and prints the result. |
| `demo_ai_box_reports.py` | Research-only: two existing AI-box mock position sources report through their telemetry services to the Python FMS; prints actual received envelopes. |
| `export_schemas.py` | Writes JSON Schema for the contracts to `exports/` (git-ignored). |

Run `python -m scripts.demo_ai_box_reports --ticks 10 --interval 0` from the repository root with pydantic installed.
Flow: existing `MockPositionSource` → `build_boat` telemetry/bridge → existing `LoopbackFmsLink` → `FmsEndpoint` → `InMemoryFleetStore`.
The FMS has no reports before the AI boxes tick. Each boat has its own source and runtime; missing fields remain null.
The geographic values are explicitly scripted presentation fixtures, not measured GPS. No browser boat simulator generates this data.
This demo uses the existing in-process transport only; it does not connect the browser dashboard or deploy HTTP services.
