"""Phase 13 Plan 02 — native tool adapter-wrap tests (TOOL-04, TOOL-05).

Verifies:
  - Test 1: TOOL_REGISTRY_ENABLED=false → tool_registry module is NOT imported
            after `import app.services.tool_service`. Subprocess test, runs in
            a clean Python process to avoid cross-test pollution.
  - Test 2: TOOL_REGISTRY_ENABLED=true → every TOOL_DEFINITIONS entry's name is
            in `_REGISTRY` (subset, resilient to 13-04 self-registering tool_search
            after this plan's wave runs in parallel; plan-checker warning C).
  - Test 3: All registered natives have source='native', loading='immediate'.
  - Test 4: Each registered native's schema == the full TOOL_DEFINITIONS entry,
            description == fn.description.
  - Test 5: Executor closure delegates to ToolService.execute_tool with the
            captured tool name (no late-binding leak).
  - Test 6: Re-running _register_natives_with_registry() on a clean registry
            registers all natives again (idempotent on clean state).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest


# Backend project root for cwd / PYTHONPATH in subprocess tests
_BACKEND_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _reset_registry():
    """Each test starts with an empty _REGISTRY."""
    from app.services import tool_registry

    tool_registry._clear_for_tests()
    yield
    tool_registry._clear_for_tests()


@pytest.fixture
def _flag_on(monkeypatch):
    """Force settings.tool_registry_enabled True for this test only."""
    from app.services import tool_service as ts_mod

    monkeypatch.setattr(ts_mod.settings, "tool_registry_enabled", True, raising=True)
    yield


def test_no_import_when_flag_off():
    """Test 1: importing tool_service with TOOL_REGISTRY_ENABLED=false does NOT
    import app.services.tool_registry (TOOL-05 byte-identical fallback)."""
    code = (
        "import os, sys, json;"
        "os.environ['TOOL_REGISTRY_ENABLED']='false';"
        "import app.services.tool_service;"
        "print(json.dumps('app.services.tool_registry' in sys.modules))"
    )
    env = {**os.environ, "TOOL_REGISTRY_ENABLED": "false"}
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=str(_BACKEND_ROOT),
        env=env,
        timeout=60,
    )
    assert result.returncode == 0, f"subprocess failed: {result.stderr}"
    # JSON-serialized False is "false"
    assert result.stdout.strip() == "false", (
        f"tool_registry was unexpectedly imported on flag-off path:\n{result.stdout}\n{result.stderr}"
    )


def test_subset_registration(_flag_on):
    """Test 2 (plan-checker warning C): every TOOL_DEFINITIONS name is in _REGISTRY,
    and no native is registered twice."""
    from app.services import tool_registry
    from app.services.tool_service import (
        TOOL_DEFINITIONS,
        _register_natives_with_registry,
    )

    _register_natives_with_registry()

    expected = {entry["function"]["name"] for entry in TOOL_DEFINITIONS}
    assert expected, "TOOL_DEFINITIONS unexpectedly empty"
    assert expected <= set(tool_registry._REGISTRY.keys()), (
        f"missing natives: {expected - set(tool_registry._REGISTRY.keys())}"
    )
    # No duplicates: dict-keys uniqueness already enforces it, but re-running
    # the bootstrap should not raise either (first-write-wins logs WARNING).
    _register_natives_with_registry()
    # Each name still maps to ONE entry (first-write-wins kept the original).
    for name in expected:
        assert name in tool_registry._REGISTRY


def test_all_natives_have_correct_source_and_loading(_flag_on):
    """Test 3: every native registered has source='native', loading='immediate'."""
    from app.services import tool_registry
    from app.services.tool_service import (
        TOOL_DEFINITIONS,
        _register_natives_with_registry,
    )

    _register_natives_with_registry()

    expected_names = {entry["function"]["name"] for entry in TOOL_DEFINITIONS}
    for name in expected_names:
        td = tool_registry._REGISTRY[name]
        assert td.source == "native", f"{name}: source={td.source}"
        assert td.loading == "immediate", f"{name}: loading={td.loading}"


def test_schema_and_description_match_tool_definitions(_flag_on):
    """Test 4: registered schema == full TOOL_DEFINITIONS entry; description == fn.description."""
    from app.services import tool_registry
    from app.services.tool_service import (
        TOOL_DEFINITIONS,
        _register_natives_with_registry,
    )

    _register_natives_with_registry()

    for entry in TOOL_DEFINITIONS:
        name = entry["function"]["name"]
        td = tool_registry._REGISTRY[name]
        assert td.schema == entry, f"{name}: schema mismatch"
        assert td.description == entry["function"].get("description", ""), (
            f"{name}: description mismatch"
        )


@pytest.mark.asyncio
async def test_executor_delegates_to_execute_tool_with_captured_name(_flag_on):
    """Test 5: closure invokes ToolService.execute_tool with the captured tool name.
    Verifies the late-binding fix (each closure has its own _name)."""
    from app.services import tool_registry
    from app.services.tool_service import (
        TOOL_DEFINITIONS,
        ToolService,
        _register_natives_with_registry,
    )

    # Patch ToolService.execute_tool BEFORE registering so the closure captures
    # the patched method via the bound _svc instance.
    with patch.object(
        ToolService, "execute_tool", new=AsyncMock(return_value={"ok": True})
    ) as mock_execute:
        _register_natives_with_registry()

        # Pick the first 3 native names to verify name-capture for multiple closures.
        sample_names = [entry["function"]["name"] for entry in TOOL_DEFINITIONS[:3]]
        for name in sample_names:
            td = tool_registry._REGISTRY[name]
            await td.executor(arguments={"q": "test"}, user_id="u1", context={})

        # Each call must have used the closure's own captured name as the
        # first positional argument (no late-binding leak).
        called_names = [call.args[0] for call in mock_execute.await_args_list]
        assert called_names == sample_names, (
            f"late-binding leak: expected {sample_names}, got {called_names}"
        )


def test_register_idempotent_on_clean_registry(_flag_on):
    """Test 6: clearing the registry then re-running the bootstrap registers
    every native again (no stale closure state, no missing entries)."""
    from app.services import tool_registry
    from app.services.tool_service import (
        TOOL_DEFINITIONS,
        _register_natives_with_registry,
    )

    _register_natives_with_registry()
    first_names = set(tool_registry._REGISTRY.keys())
    expected = {entry["function"]["name"] for entry in TOOL_DEFINITIONS}
    assert expected <= first_names

    # Clear and re-run
    tool_registry._clear_for_tests()
    assert tool_registry._REGISTRY == {}
    _register_natives_with_registry()
    second_names = set(tool_registry._REGISTRY.keys())
    assert expected <= second_names
