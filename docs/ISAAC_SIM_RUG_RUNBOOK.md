# Isaac Sim runbook for the RUG machine

Goal: run the Isaac Sim smoke test on a Windows machine with an RTX 5080 (16 GB VRAM)
without any AI agents on that machine. Everything needed is in this repository.

Isaac Sim is a final integration environment only. The repository tests and the mock
demo do not need it. See `CLAUDE.md`.

## 1. Check the GPU and driver

Open PowerShell and run:

```powershell
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv
```

You need at least 16 GB of VRAM. Check the driver against the NVIDIA Isaac Sim
requirements page for the exact Isaac Sim version you install. Update the driver
if the page lists a newer one.

## 2. Install Isaac Sim

Follow NVIDIA's Isaac Sim installation guide for the version you choose. Two routes
are documented:

- **Standalone package** (run scripts with `python.bat` from the Isaac Sim folder).
- **pip package `isaacsim`** (run scripts with your own Python).

Before installing, run the Isaac Sim Compatibility Checker if the guide offers it.
It reports GPU, driver and VRAM problems.

## 3. Get the code

```powershell
git clone https://github.com/Hami0095/intelligent-boats
cd intelligent-boats
git checkout feature/adapters-isaac-smoke
```

## 4. Run the Isaac Sim smoke test

Standalone package:

```powershell
<isaac-sim-folder>\python.bat adapters\src\adapters\simulation\isaac_sim\smoke_test.py
```

pip package:

```powershell
python adapters\src\adapters\simulation\isaac_sim\smoke_test.py
```

Expected output: `OK: Isaac Sim started and rendered 10 frames.` and exit code 0.

Exit code 2 means `isaacsim` cannot be imported. Check the install route and the
Python environment.

## 5. Run the repository checks (no simulator needed)

```powershell
python -m pip install -e interfaces -e ai-box -e fms -e adapters pytest
python -m pytest
python scripts\demo_mock_boat.py
```

Expected: all tests pass, and the demo prints cycle lines and FMS message counts.

## Known limits

- The smoke test only starts the simulator and renders frames. It does not load the
  CAD boat or move it.
- The live adapter backend, the CAD boat asset and the motion mapping are not
  implemented yet. Those come after the smoke test passes.
