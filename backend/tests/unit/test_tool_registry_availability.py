"""Phase 15: tool_registry availability field tests.

MCP-04, MCP-05 / D-P15-11 — tests for the `available` field on ToolDefinition
and the mark_server_available / mark_server_unavailable functions in tool_registry.

Mirrors test_tool_registry.py patterns: autouse _reset_registry, asyncio.run() for async.
"""
from __future__ import annotations

import asyncio

import pytest

from app.models.tools import ToolDefinition
from app.services import tool_registry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_registry():
    tool_registry._clear_for_tests()
    yield
    tool_registry._clear_for_tests()


async def _noop_executor(arguments: dict, user_id: str = "", context=None, **kw):
    return {"ok": True}


def _register_mcp_tool(server_name: str, tool_name: str, description: str = "desc"):
    namespaced = f"{server_name}__{tool_name}"
    tool_registry.register(
        name=namespaced,
        description=description,
        schema={
            "type": "function",
            "function": {
                "name": namespaced,
                "description": description,
                "parameters": {"type": "object", "properties": {}},
            },
        },
        source="mcp",
        loading="deferred",
        executor=_noop_executor,
    )
    return namespaced


# ---------------------------------------------------------------------------
# Tests: ToolDefinition.available field (D-P15-11)
# ---------------------------------------------------------------------------


def test_tool_definition_available_defaults_to_true():
    """ToolDefinition.available defaults to True (backward-compatible)."""
    tool = ToolDefinition(
        name="mytool",
        description="desc",
        schema={},
        source="native",
        loading="immediate",
        executor=_noop_executor,
    )
    assert tool.available is True


def test_tool_definition_available_can_be_set_false():
    """ToolDefinition.available can be set to False at construction."""
    tool = ToolDefinition(
        name="mytool",
        description="desc",
        schema={},
        source="mcp",
        loading="deferred",
        executor=_noop_executor,
        available=False,
    )
    assert tool.available is False


def test_tool_definition_available_can_be_mutated():
    """ToolDefinition.available can be mutated in-place (not frozen)."""
    tool = ToolDefinition(
        name="mytool",
        description="desc",
        schema={},
        source="mcp",
        loading="deferred",
        executor=_noop_executor,
    )
    assert tool.available is True
    tool.available = False
    assert tool.available is False
    tool.available = True
    assert tool.available is True


# ---------------------------------------------------------------------------
# Tests: mark_server_unavailable / mark_server_available (D-P15-11, D-P15-12)
# ---------------------------------------------------------------------------


def test_mark_server_unavailable_sets_false_for_matching_tools():
    """mark_server_unavailable(name) marks all '{name}__*' tools as available=False."""
    _register_mcp_tool("myserver", "tool1")
    _register_mcp_tool("myserver", "tool2")
    _register_mcp_tool("otherserver", "tool3")

    count = tool_registry.mark_server_unavailable("myserver")

    assert count == 2
    assert tool_registry._REGISTRY["myserver__tool1"].available is False
    assert tool_registry._REGISTRY["myserver__tool2"].available is False
    # otherserver tools unaffected
    assert tool_registry._REGISTRY["otherserver__tool3"].available is True


def test_mark_server_available_restores_to_true():
    """mark_server_available(name) re-enables all '{name}__*' tools."""
    _register_mcp_tool("myserver", "tool1")
    _register_mcp_tool("myserver", "tool2")
    tool_registry.mark_server_unavailable("myserver")

    count = tool_registry.mark_server_available("myserver")

    assert count == 2
    assert tool_registry._REGISTRY["myserver__tool1"].available is True
    assert tool_registry._REGISTRY["myserver__tool2"].available is True


def test_mark_server_unavailable_returns_zero_for_unknown_server():
    """mark_server_unavailable returns 0 when no tools match the prefix."""
    _register_mcp_tool("otherserver", "tool1")
    count = tool_registry.mark_server_unavailable("unknownserver")
    assert count == 0


def test_mark_server_unavailable_does_not_affect_native_tools():
    """Native tools never have a 'server__' prefix so they're never affected."""
    async def noop(**kw):
        return {}

    tool_registry.register(
        "search_documents", "Search", {},
        source="native", loading="immediate", executor=noop,
    )

    count = tool_registry.mark_server_unavailable("search_documents")
    assert count == 0
    assert tool_registry._REGISTRY["search_documents"].available is True


def test_mark_server_available_returns_zero_for_unknown_server():
    """mark_server_available returns 0 when no tools match the prefix."""
    _register_mcp_tool("myserver", "tool1")
    count = tool_registry.mark_server_available("unknownserver")
    assert count == 0


def test_mark_server_cycle_unavailable_then_available():
    """Full cycle: unavailable then available restores correct state."""
    _register_mcp_tool("svr", "t1")
    _register_mcp_tool("svr", "t2")

    tool_registry.mark_server_unavailable("svr")
    assert tool_registry._REGISTRY["svr__t1"].available is False
    assert tool_registry._REGISTRY["svr__t2"].available is False

    tool_registry.mark_server_available("svr")
    assert tool_registry._REGISTRY["svr__t1"].available is True
    assert tool_registry._REGISTRY["svr__t2"].available is True


# ---------------------------------------------------------------------------
# Tests: build_catalog_block with availability filter (D-P15-11)
# ---------------------------------------------------------------------------


def test_build_catalog_block_omits_unavailable_tools():
    """build_catalog_block() does not include tools where available=False."""
    _register_mcp_tool("svr", "unavailable_tool", "Unavailable tool")
    _register_mcp_tool("svr", "available_tool", "Available tool")

    # Mark all svr tools unavailable, then manually restore one
    tool_registry.mark_server_unavailable("svr")
    tool_registry._REGISTRY["svr__available_tool"].available = True

    catalog = asyncio.run(tool_registry.build_catalog_block())
    assert "svr__available_tool" in catalog
    assert "svr__unavailable_tool" not in catalog


def test_build_catalog_block_includes_available_mcp_tools():
    """build_catalog_block() includes MCP tools that are available=True."""
    _register_mcp_tool("svr", "my_tool", "My MCP tool description")
    # Tool starts with available=True (default)

    catalog = asyncio.run(tool_registry.build_catalog_block())
    assert "svr__my_tool" in catalog
    assert "mcp" in catalog


def test_build_catalog_block_empty_when_all_unavailable():
    """build_catalog_block() returns empty string (or just tool_search callout) when all tools unavailable."""
    _register_mcp_tool("svr", "tool1")
    tool_registry.mark_server_unavailable("svr")

    catalog = asyncio.run(tool_registry.build_catalog_block())
    assert "svr__tool1" not in catalog


# ---------------------------------------------------------------------------
# Tests: build_llm_tools with availability filter (D-P15-11)
# ---------------------------------------------------------------------------


def test_build_llm_tools_omits_unavailable_tools():
    """build_llm_tools() does not include tools where available=False."""
    async def noop(**kw):
        return {}

    tool_registry.register(
        "svr__tool1",
        "Tool 1",
        {"type": "function", "function": {"name": "svr__tool1"}},
        source="mcp",
        loading="immediate",  # immediate so it always appears in LLM tools array
        executor=noop,
    )
    tool_registry.mark_server_unavailable("svr")

    active_set = tool_registry.make_active_set()
    llm_tools = tool_registry.build_llm_tools(
        active_set=active_set,
        web_search_enabled=True,
        sandbox_enabled=False,
        agent_allowed_tools=None,
    )
    tool_names = [t["function"]["name"] for t in llm_tools]
    assert "svr__tool1" not in tool_names


def test_build_llm_tools_includes_available_mcp_tools():
    """build_llm_tools() includes MCP tools that are available=True and in active_set."""
    async def noop(**kw):
        return {}

    tool_registry.register(
        "svr__tool1",
        "Tool 1",
        {"type": "function", "function": {"name": "svr__tool1"}},
        source="mcp",
        loading="deferred",
        executor=noop,
    )
    # Add to active_set to include deferred tool
    active_set = {"svr__tool1"}

    llm_tools = tool_registry.build_llm_tools(
        active_set=active_set,
        web_search_enabled=True,
        sandbox_enabled=False,
        agent_allowed_tools=None,
    )
    tool_names = [t["function"]["name"] for t in llm_tools]
    assert "svr__tool1" in tool_names


def test_build_llm_tools_immediate_unavailable_excluded():
    """Immediate-loading tools are excluded when available=False."""
    async def noop(**kw):
        return {}

    tool_registry.register(
        "svr__imm",
        "Immediate tool",
        {"type": "function", "function": {"name": "svr__imm"}},
        source="mcp",
        loading="immediate",
        executor=noop,
    )

    # Available — should appear
    active_set = tool_registry.make_active_set()
    llm_tools_before = tool_registry.build_llm_tools(
        active_set=active_set,
        web_search_enabled=True,
        sandbox_enabled=False,
        agent_allowed_tools=None,
    )
    names_before = [t["function"]["name"] for t in llm_tools_before]
    assert "svr__imm" in names_before

    # Mark unavailable — should disappear
    tool_registry.mark_server_unavailable("svr")
    llm_tools_after = tool_registry.build_llm_tools(
        active_set=active_set,
        web_search_enabled=True,
        sandbox_enabled=False,
        agent_allowed_tools=None,
    )
    names_after = [t["function"]["name"] for t in llm_tools_after]
    assert "svr__imm" not in names_after
