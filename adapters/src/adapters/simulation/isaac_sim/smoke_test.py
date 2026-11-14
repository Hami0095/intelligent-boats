"""Isaac Sim smoke test: start the simulator headless, render a few frames, exit.

Run this only on a machine that has Isaac Sim installed. It is the only place in
the repository that imports the simulator, and it does not depend on any AI Box
or FMS code.

Usage (standalone Isaac Sim install on Windows):
    <isaac-sim-folder>\\python.bat adapters\\src\\adapters\\simulation\\isaac_sim\\smoke_test.py

Usage (pip-installed isaacsim):
    python adapters\\src\\adapters\\simulation\\isaac_sim\\smoke_test.py

Exit codes: 0 = simulator started and rendered; 2 = isaacsim is not importable.
"""

from __future__ import annotations

import sys

FRAMES = 10


def main() -> int:
    try:
        from isaacsim import SimulationApp  # type: ignore[import-not-found]
    except ImportError as exc:
        print(f"FAIL: cannot import isaacsim: {exc}", file=sys.stderr)
        print(
            "Install Isaac Sim first. See docs/ISAAC_SIM_RUG_RUNBOOK.md.",
            file=sys.stderr,
        )
        return 2

    app = SimulationApp({"headless": True})
    try:
        for _ in range(FRAMES):
            app.update()
        print(f"OK: Isaac Sim started and rendered {FRAMES} frames.")
        return 0
    finally:
        app.close()


if __name__ == "__main__":
    raise SystemExit(main())
