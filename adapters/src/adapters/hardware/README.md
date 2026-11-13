# hardware adapters (not yet implemented)

Real sensor, GPS/IMU and motor-controller adapters go here, one sub-package per device.
Each must implement a port from `ai_box.core.ports` and pass the shared contract tests in `tests/integration/`.
Device selection depends on the CAD and hardware decisions, which are OPEN.
