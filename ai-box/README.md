# ai-box

The onboard software environment of one autonomous boat. See `CLAUDE.md` for responsibilities and rules, and `../docs/SYSTEM_ARCHITECTURE.md` for how it fits the whole system.

## Quick start

```python
from adapters.fms.loopback import LoopbackFmsLink
from adapters.propulsion.mock import MockPropulsionSink
from adapters.sensors.mock import MockPositionSource
from ai_box.bootstrap import build_boat
from ai_box.config.settings import load_config

boat = build_boat(
    load_config(),
    position=MockPositionSource(),
    propulsion=MockPropulsionSink(),
    fms_link=LoopbackFmsLink(server=lambda envelope: []),
)
with boat.app:          # starts services in dependency order, stops them in reverse on exit
    boat.app.tick()     # run one control cycle
    print(boat.app.health_report())
```

Run the tests with `python -m pytest ai-box/tests` from the repository root.
