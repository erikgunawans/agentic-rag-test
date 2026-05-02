"""Phase 13 Plan 05 Task 1 — should_filter_tool predicate unit tests.

Locks D-P13-06:
  - Skills bypass agent.tool_names (Test 1)
  - tool_search always-on regardless of agent (Test 2)
  - Native gated by agent.tool_names (Tests 3, 4)
  - MCP gated by agent.tool_names (Tests 5, 6)
  - Empty tool_names → only skills + tool_search pass (Test 7)
"""

from __future__ import annotations

import pytest

from app.models.agents import AgentDefinition
from app.models.tools import ToolDefinition
from app.services.agent_service import should_filter_tool


async def _noop_executor(*args, **kwargs):
    return {}


def _make_tool(name: str, source: str = "native") -> ToolDefinition:
    return ToolDefinition(
        name=name,
        description=f"{name} desc",
        schema={"type": "function", "function": {"name": name}},
        source=source,  # type: ignore[arg-type]
        loading="immediate",
        executor=_noop_executor,
    )


def _make_agent(tool_names: list[str]) -> AgentDefinition:
    return AgentDefinition(
        name="test_agent",
        display_name="Test",
        system_prompt="...",
        tool_names=tool_names,
        max_iterations=5,
    )


def test_skill_bypasses_empty_agent_tool_names():
    """Test 1: skill always passes filter (skill bypass)."""
    skill = _make_tool("legal_review", source="skill")
    agent = _make_agent(tool_names=[])
    assert should_filter_tool(skill, agent) is True


def test_tool_search_always_on():
    """Test 2: tool_search always retained even with empty allow list."""
    tool_search = _make_tool("tool_search", source="native")
    agent = _make_agent(tool_names=[])
    assert should_filter_tool(tool_search, agent) is True


def test_native_in_agent_allow_list_passes():
    """Test 3: native tool in tool_names → True."""
    tool = _make_tool("search_documents", source="native")
    agent = _make_agent(tool_names=["search_documents"])
    assert should_filter_tool(tool, agent) is True


def test_native_not_in_agent_allow_list_filtered():
    """Test 4: native tool NOT in tool_names → False."""
    tool = _make_tool("query_database", source="native")
    agent = _make_agent(tool_names=["search_documents"])
    assert should_filter_tool(tool, agent) is False


def test_mcp_in_agent_allow_list_passes():
    """Test 5: mcp tool in tool_names → True."""
    tool = _make_tool("github_search", source="mcp")
    agent = _make_agent(tool_names=["github_search"])
    assert should_filter_tool(tool, agent) is True


def test_mcp_not_in_agent_allow_list_filtered():
    """Test 6: mcp tool NOT in tool_names → False."""
    tool = _make_tool("github_search", source="mcp")
    agent = _make_agent(tool_names=["search_documents"])
    assert should_filter_tool(tool, agent) is False


def test_empty_tool_names_only_skills_and_tool_search_pass():
    """Test 7: with no allow list, only skills + tool_search are kept."""
    agent = _make_agent(tool_names=[])

    skill = _make_tool("legal_review", source="skill")
    tool_search = _make_tool("tool_search", source="native")
    native = _make_tool("query_database", source="native")
    mcp_tool = _make_tool("github_search", source="mcp")

    assert should_filter_tool(skill, agent) is True
    assert should_filter_tool(tool_search, agent) is True
    assert should_filter_tool(native, agent) is False
    assert should_filter_tool(mcp_tool, agent) is False
