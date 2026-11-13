"""Architecture tests: the modules may only import what their responsibilities allow.

These are static checks over source code. They fail the build if, for example,
the AI Box grows a dependency on Isaac Sim or the FMS reaches into AI Box internals.
"""

import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
STDLIB = set(sys.stdlib_module_names)
SIMULATOR_MODULES = {"isaacsim", "omni", "isaaclab", "isaac_sim"}


def _top_level_imports(package_dir: Path) -> set[str]:
    names: set[str] = set()
    for path in package_dir.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names.add(node.module.split(".")[0])
    return names


def _assert_only_allowed(package: str, allowed: set[str]) -> None:
    imported = _top_level_imports(ROOT / package)
    disallowed = imported - allowed - STDLIB
    assert not disallowed, f"{package} imports disallowed modules: {sorted(disallowed)}"


def test_ai_box_has_no_simulator_or_vendor_dependency():
    _assert_only_allowed("ai-box/src", {"ai_box", "marine_contracts", "pydantic"})


def test_fms_has_no_ai_box_or_adapter_dependency():
    _assert_only_allowed("fms/src", {"fms", "marine_contracts", "pydantic"})


def test_shared_contracts_are_pure_data_definitions():
    _assert_only_allowed("interfaces/src", {"marine_contracts", "pydantic"})


def test_only_the_adapters_package_may_depend_on_ai_box_ports():
    # Adapters may use the AI Box port definitions. Nothing else outside the AI Box may.
    assert "ai_box" not in _top_level_imports(ROOT / "fms" / "src")
    assert "adapters" not in _top_level_imports(ROOT / "ai-box" / "src")


def test_adapters_stay_inside_their_allowed_dependencies():
    _assert_only_allowed("adapters/src", {"adapters", "ai_box", "marine_contracts", "pydantic"})


@pytest.mark.parametrize("package", ["ai-box/src", "fms/src", "interfaces/src", "adapters/src"])
def test_no_package_imports_isaac_sim(package):
    assert not (_top_level_imports(ROOT / package) & SIMULATOR_MODULES)
