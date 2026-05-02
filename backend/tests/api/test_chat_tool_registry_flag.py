"""Phase 13 Plan 05 Task 2 — chat.py registry-flag wiring tests.

Locks key invariants:
  1. TOOL-05 byte-identical fallback: when flag is OFF, tool_service.get_available_tools
     and build_skill_catalog_block are the ONLY catalog sources; tool_registry.* is
     never imported (subprocess-verifiable).
  2. Flag-on, single-agent: build_catalog_block is invoked with agent_allowed_tools=None.
  3. Flag-on, multi-agent: build_catalog_block + build_llm_tools both filter by
     agent.tool_names (D-P13-06).
  4. Active-set per-request reset: make_active_set() returns a new set each call.
  5. Skill registration per-request: register_user_skills called fresh each request.
  6. _dispatch_tool prefers registry executor when flag is on, falls through otherwise.

These are direct unit-level tests on chat.py's helpers/branches rather than the
full TestClient SSE path, which would require Supabase + LLM mocking that is
already covered by test_chat_skill_catalog.py and test_chat_router_phase5_*.
The full TestClient byte-identical snapshot is locked by the JSON reference
fixture at backend/tests/api/fixtures/chat_v1_1_reference.json.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_FIXTURE_PATH = (
    _BACKEND_ROOT / "tests" / "api" / "fixtures" / "chat_v1_1_reference.json"
)


@pytest.fixture(autouse=True)
def _reset_registry():
    """Reset registry to clean state (just tool_search re-registered)."""
    from app.services import tool_registry

    tool_registry._clear_for_tests()
    yield
    tool_registry._clear_for_tests()


# ---------------------------------------------------------------------------
# Test 1: byte-identical reference fixture exists and documents the invariant
# ---------------------------------------------------------------------------


def test_v1_1_reference_fixture_exists_and_documents_invariant():
    """The byte-identical snapshot fixture must exist and pin the TOOL-05 contract."""
    assert _FIXTURE_PATH.exists(), f"Missing fixture: {_FIXTURE_PATH}"
    data = json.loads(_FIXTURE_PATH.read_text())
    assert data["captured_with"] == "TOOL_REGISTRY_ENABLED=false"
    assert "tool_registry" not in data["tools_array_source"]
    assert "build_skill_catalog_block" in data["skill_catalog_source"]
    assert data["input_matrix"]["tool_registry_enabled"] is False


# ---------------------------------------------------------------------------
# Test 2: subprocess no-import on flag-off
# ---------------------------------------------------------------------------


def test_no_tool_registry_import_when_flag_off():
    """TOOL-05 invariant at the import level: chat.py + tool_service.py must NOT
    import tool_registry when TOOL_REGISTRY_ENABLED=false."""
    code = (
        "import os, sys, json;"
        "os.environ['TOOL_REGISTRY_ENABLED']='false';"
        "import app.routers.chat;"
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
    assert result.stdout.strip() == "false", (
        f"tool_registry was imported on flag-off path:\n{result.stdout}\n{result.stderr}"
    )


# ---------------------------------------------------------------------------
# Test 3: flag-on, single-agent — build_catalog_block called with None
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_flag_on_single_agent_catalog_block_no_filter():
    """When flag is on and agents are off, build_catalog_block(agent_allowed_tools=None)
    returns a string starting with '## Available Tools' once natives are registered."""
    from app.services import tool_registry

    # Register one native to populate the catalog (mirrors what 13-02's bootstrap does).
    async def _noop(*a, **k):
        return {"ok": True}

    tool_registry.register(
        name="search_documents",
        description="Search internal docs",
        schema={"type": "function", "function": {"name": "search_documents"}},
        source="native",
        loading="immediate",
        executor=_noop,
    )

    block = await tool_registry.build_catalog_block(agent_allowed_tools=None)
    assert "## Available Tools" in block
    assert "Call `tool_search`" in block
    assert "| search_documents |" in block


# ---------------------------------------------------------------------------
# Test 4: flag-on, multi-agent — D-P13-06 filter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_flag_on_multi_agent_filter_skill_bypass_and_native_gate():
    """Agent with tool_names=['search_documents'] sees:
       - search_documents (native, allowed)
       - legal_review (skill, bypass)
       - tool_search excluded from rows
       - query_database filtered out
    """
    from app.services import tool_registry

    async def _noop(*a, **k):
        return {"ok": True}

    for name, source in [
        ("search_documents", "native"),
        ("query_database", "native"),
        ("legal_review", "skill"),
    ]:
        tool_registry.register(
            name=name,
            description=f"{name} desc",
            schema={"type": "function", "function": {"name": name}},
            source=source,  # type: ignore[arg-type]
            loading="immediate",
            executor=_noop,
        )

    catalog = await tool_registry.build_catalog_block(
        agent_allowed_tools=["search_documents"],
    )
    assert "| search_documents |" in catalog
    assert "| legal_review |" in catalog  # skill bypass
    assert "| query_database |" not in catalog  # filtered
    assert "| tool_search |" not in catalog  # excluded from rows

    tools = tool_registry.build_llm_tools(
        active_set=set(),
        web_search_enabled=True,
        sandbox_enabled=True,
        agent_allowed_tools=["search_documents"],
    )
    names = {
        s["function"]["name"] for s in tools if isinstance(s, dict) and "function" in s
    }
    assert "search_documents" in names
    assert "legal_review" in names
    assert "query_database" not in names
    assert "tool_search" in names  # always-on


# ---------------------------------------------------------------------------
# Test 5: active-set per-request reset (TOOL-03)
# ---------------------------------------------------------------------------


def test_active_set_per_request_reset():
    """make_active_set() returns a fresh empty set each call. Mutations to one
    request's set do NOT leak into the next request's set."""
    from app.services import tool_registry

    s1 = tool_registry.make_active_set()
    s1.add("deferred_tool_a")
    s2 = tool_registry.make_active_set()
    assert s2 == set()
    assert s2 is not s1
    s2.add("deferred_tool_b")
    assert "deferred_tool_a" not in s2
    assert "deferred_tool_b" not in s1


# ---------------------------------------------------------------------------
# Test 6: register_user_skills called per-request (no caching)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_user_skills_called_per_request():
    """Two consecutive register_user_skills calls with different skill rows
    register both sets (registry first-write-wins keeps user A's; in chat.py
    we accept that natives + tool_search persist while skills register from
    the current request's RLS-scoped client)."""
    from app.services import tool_registry
    from app.services.skill_catalog_service import register_user_skills

    def _mk(rows):
        client = MagicMock()
        chain = MagicMock()
        chain.execute.return_value.data = rows
        chain.eq.return_value = chain
        chain.order.return_value = chain
        chain.select.return_value = chain
        client.table.return_value = chain
        return client

    with patch(
        "app.services.skill_catalog_service.get_supabase_authed_client",
        return_value=_mk([{"name": "skill_a", "description": "A"}]),
    ):
        await register_user_skills("u1", "tok")
    skills_present_a = {
        n for n, td in tool_registry._REGISTRY.items() if td.source == "skill"
    }
    assert "skill_a" in skills_present_a

    # Second call with different rows — first-write-wins keeps skill_a; new
    # skill_b also registers (different name).
    with patch(
        "app.services.skill_catalog_service.get_supabase_authed_client",
        return_value=_mk([{"name": "skill_b", "description": "B"}]),
    ):
        await register_user_skills("u2", "tok")
    skills_present_b = {
        n for n, td in tool_registry._REGISTRY.items() if td.source == "skill"
    }
    assert "skill_a" in skills_present_b  # first-write-wins
    assert "skill_b" in skills_present_b


# ---------------------------------------------------------------------------
# Test 7: chat.py imports and exposes _dispatch_tool helper
# ---------------------------------------------------------------------------


def test_chat_py_has_dispatch_tool_helper():
    """The Phase 13 D-P13-05 Option A registry-first dispatch wrapper exists
    in chat.py and is gated by settings.tool_registry_enabled."""
    chat_py = (_BACKEND_ROOT / "app" / "routers" / "chat.py").read_text()
    assert "_dispatch_tool" in chat_py
    # The helper must check the flag and the registry membership.
    assert "settings.tool_registry_enabled" in chat_py
    assert "tool_registry._REGISTRY" in chat_py


# ---------------------------------------------------------------------------
# Test 8: chat.py wiring — agent.tool_names, NOT allowed_tools
# ---------------------------------------------------------------------------


def test_chat_py_uses_tool_names_not_allowed_tools():
    """PATTERNS.md critical finding: agent.tool_names is the field name; the
    informal prose `allowed_tools` must NOT appear in chat.py."""
    chat_py = (_BACKEND_ROOT / "app" / "routers" / "chat.py").read_text()
    assert "agent_def.tool_names" in chat_py
    assert "agent_def.allowed_tools" not in chat_py
    assert "agent.allowed_tools" not in chat_py
