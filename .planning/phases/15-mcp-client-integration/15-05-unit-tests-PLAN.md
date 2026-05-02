---
phase: 15-mcp-client-integration
plan: 05
type: execute
wave: 2
depends_on:
  - 15-01
  - 15-02
  - 15-04
files_modified:
  - backend/tests/unit/test_mcp_client_manager.py
  - backend/tests/unit/test_tool_registry_availability.py
autonomous: true
requirements:
  - MCP-01
  - MCP-02
  - MCP-03
  - MCP-04
  - MCP-05
  - MCP-06
must_haves:
  truths:
    - "backend/tests/unit/test_mcp_client_manager.py exists and contains at least 15 test functions"
    - "Tests cover: parse_mcp_servers (valid, empty, multi-server, malformed), schema conversion, registration with source=mcp loading=deferred, call_tool routing with prefix stripping, disconnect handling via _handle_tool_call_failure"
    - "MCP SDK (mcp.ClientSession, mcp.client.stdio.stdio_client) is mocked — tests do NOT require a running MCP server or npx"
    - "backend/tests/unit/test_tool_registry_availability.py tests mark_server_available, mark_server_unavailable, and available field filtering in build_catalog_block and build_llm_tools"
    - "All tests in both new files pass: pytest tests/unit/test_mcp_client_manager.py tests/unit/test_tool_registry_availability.py -v exits 0"
    - "All pre-existing Phase 13 registry tests continue passing: pytest tests/unit/test_tool_registry.py -x -q exits 0"
  artifacts:
    - path: "backend/tests/unit/test_mcp_client_manager.py"
      provides: "MCPClientManager unit tests (parse, convert, register, call, disconnect)"
      contains: "test_parse_mcp_servers"
    - path: "backend/tests/unit/test_tool_registry_availability.py"
      provides: "ToolDefinition.available field and registry availability filter tests"
      contains: "test_mark_server_unavailable"
  key_links:
    - from: "backend/tests/unit/test_mcp_client_manager.py"
      to: "backend/app/services/mcp_client_manager.py"
      via: "imports parse_mcp_servers, MCPClientManager, get_mcp_client_manager"
      pattern: "from app.services.mcp_client_manager import"
    - from: "backend/tests/unit/test_tool_registry_availability.py"
      to: "backend/app/services/tool_registry.py"
      via: "imports mark_server_available, mark_server_unavailable, build_catalog_block, build_llm_tools"
      pattern: "from app.services import tool_registry"
---

<objective>
Create comprehensive unit tests for the Phase 15 MCP integration. Two test files:

1. `backend/tests/unit/test_mcp_client_manager.py` — tests for `MCPClientManager`:
   - `parse_mcp_servers()` — all parsing edge cases
   - `_connect_server()` — with mocked `mcp` SDK
   - `call_tool()` — routing, prefix stripping, error handling
   - `_handle_tool_call_failure()` — disconnect signaling
   - `shutdown()` — task cancellation
   - Schema conversion (`_convert_mcp_tool_to_openai`) — edge cases

2. `backend/tests/unit/test_tool_registry_availability.py` — tests for the Phase 15 availability extensions:
   - `ToolDefinition.available` field default and mutation
   - `mark_server_unavailable()` / `mark_server_available()` — correct tool filtering by prefix
   - `build_catalog_block()` — omits `available=False` tools
   - `build_llm_tools()` — omits `available=False` tools

All mcp SDK imports are mocked via `unittest.mock.AsyncMock` / `MagicMock`. Tests do NOT spawn real child processes or require `npx`.

Mirrors the existing unit test patterns in `test_tool_registry.py` (autouse `_reset_registry` fixture, `asyncio.run()` for async tests).
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/phases/15-mcp-client-integration/15-CONTEXT.md
@backend/app/services/mcp_client_manager.py
@backend/app/services/tool_registry.py
@backend/app/models/tools.py
@backend/tests/unit/test_tool_registry.py
@backend/tests/unit/test_agent_service_should_filter_tool.py
</context>

<tasks>

<task id="1">
<name>Create backend/tests/unit/test_mcp_client_manager.py</name>
<read_first>
- backend/app/services/mcp_client_manager.py (full file — all functions, class methods, _ServerConfig, _ServerState dataclasses)
- backend/tests/unit/test_tool_registry.py (fixture patterns, _reset_registry, asyncio.run usage)
- backend/tests/unit/test_agent_service_should_filter_tool.py (mock patterns)
</read_first>
<action>
Create `backend/tests/unit/test_mcp_client_manager.py` with the following test suite:

```python
"""Phase 15: MCPClientManager unit tests.

MCP-01..06 — covers parse, convert, register, call_tool, disconnect, reconnect.

All mcp SDK imports are mocked — tests do NOT require a running MCP server.
Pattern mirrors test_tool_registry.py autouse fixture + asyncio.run() for async tests.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.mcp_client_manager import (
    MCPClientManager,
    _convert_mcp_tool_to_openai,
    parse_mcp_servers,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_registry():
    """Reset tool registry before each test to prevent cross-test pollution."""
    from app.services import tool_registry
    tool_registry._clear_for_tests()
    yield
    tool_registry._clear_for_tests()


def _make_mcp_tool(name="my_tool", description="A tool", input_schema=None):
    """Create a minimal MCP tool object (mock mcp.types.Tool)."""
    tool = SimpleNamespace(
        name=name,
        description=description,
        inputSchema=input_schema,
    )
    return tool


# ---------------------------------------------------------------------------
# Tests: parse_mcp_servers (MCP-01 / D-P15-03)
# ---------------------------------------------------------------------------


def test_parse_empty_string():
    """Empty string returns empty list."""
    assert parse_mcp_servers("") == []


def test_parse_whitespace_only():
    """Whitespace-only string returns empty list."""
    assert parse_mcp_servers("   ") == []


def test_parse_single_server():
    """Single 'name:command:args' entry parses correctly."""
    configs = parse_mcp_servers("github:npx:-y @modelcontextprotocol/server-github")
    assert len(configs) == 1
    assert configs[0].name == "github"
    assert configs[0].command == "npx"
    assert configs[0].args == ["-y", "@modelcontextprotocol/server-github"]


def test_parse_multiple_servers():
    """Comma-separated servers produce multiple configs."""
    configs = parse_mcp_servers("svr1:cmd1:arg1 arg2,svr2:cmd2:arg3")
    assert len(configs) == 2
    assert configs[0].name == "svr1"
    assert configs[0].args == ["arg1", "arg2"]
    assert configs[1].name == "svr2"
    assert configs[1].args == ["arg3"]


def test_parse_no_args_section():
    """Entry with name:command (no third colon) parses with empty args."""
    configs = parse_mcp_servers("myserver:python")
    assert len(configs) == 1
    assert configs[0].name == "myserver"
    assert configs[0].command == "python"
    assert configs[0].args == []


def test_parse_args_with_multiple_colons():
    """Args section can contain colons (split only on first 2)."""
    configs = parse_mcp_servers("db:python:server.py --uri postgres://host:5432/db")
    assert len(configs) == 1
    assert configs[0].args == ["server.py", "--uri", "postgres://host:5432/db"]


def test_parse_malformed_entry_no_colon_skipped():
    """Entry without a colon is logged as WARNING and skipped."""
    configs = parse_mcp_servers("badentry,github:npx:arg1")
    assert len(configs) == 1
    assert configs[0].name == "github"


def test_parse_strips_whitespace():
    """Whitespace around commas and entries is stripped."""
    configs = parse_mcp_servers("  svr1:cmd1:arg1  ,  svr2:cmd2:arg2  ")
    assert len(configs) == 2
    assert configs[0].name == "svr1"
    assert configs[1].name == "svr2"


# ---------------------------------------------------------------------------
# Tests: schema conversion (MCP-03 / D-P15-04, D-P15-05)
# ---------------------------------------------------------------------------


def test_schema_conversion_basic():
    """Standard tool with inputSchema converts to OpenAI format."""
    tool = _make_mcp_tool(
        name="search",
        description="Search for something",
        input_schema={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    )
    schema = _convert_mcp_tool_to_openai("myserver", tool)
    assert schema is not None
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "myserver__search"
    assert schema["function"]["description"] == "Search for something"
    assert schema["function"]["parameters"]["properties"]["query"]["type"] == "string"


def test_schema_conversion_no_input_schema():
    """Tool without inputSchema uses permissive passthrough (D-P15-05)."""
    tool = _make_mcp_tool(name="noop", description="Noop tool", input_schema=None)
    schema = _convert_mcp_tool_to_openai("myserver", tool)
    assert schema is not None
    assert schema["function"]["parameters"] == {"type": "object", "properties": {}}


def test_schema_conversion_no_description():
    """Tool without description uses empty string."""
    tool = _make_mcp_tool(name="mytool", description=None, input_schema=None)
    schema = _convert_mcp_tool_to_openai("myserver", tool)
    assert schema is not None
    assert schema["function"]["description"] == ""


def test_schema_conversion_name_namespacing():
    """Tool name is prefixed with server_name and double underscore (D-P15-06)."""
    tool = _make_mcp_tool(name="read_file")
    schema = _convert_mcp_tool_to_openai("filesystem", tool)
    assert schema["function"]["name"] == "filesystem__read_file"


# ---------------------------------------------------------------------------
# Tests: startup + registration (MCP-02, MCP-04 / D-P15-07, D-P15-08)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_startup_registers_tools_with_mcp_source():
    """startup() registers MCP tools in the registry with source='mcp', loading='deferred'."""
    manager = MCPClientManager()

    mock_tool = _make_mcp_tool(
        name="search",
        description="Search tool",
        input_schema={"type": "object", "properties": {}},
    )
    mock_tools_result = SimpleNamespace(tools=[mock_tool])
    mock_session = AsyncMock()
    mock_session.list_tools = AsyncMock(return_value=mock_tools_result)
    mock_session.initialize = AsyncMock()

    with (
        patch("app.config.get_settings") as mock_settings,
        patch("app.services.mcp_client_manager.asyncio.create_task"),  # suppress background task
        patch("app.services.mcp_client_manager.MCPClientManager._open_stdio") as mock_open_stdio,
        patch("mcp.ClientSession", return_value=mock_session),
    ):
        mock_settings.return_value.tool_registry_enabled = True
        mock_settings.return_value.mcp_servers = "myserver:python:server.py"
        mock_open_stdio.return_value = (AsyncMock(), AsyncMock())

        await manager._connect_server(
            manager._servers.setdefault(
                "myserver",
                __import__("app.services.mcp_client_manager", fromlist=["_ServerState"])._ServerState(
                    config=__import__("app.services.mcp_client_manager", fromlist=["_ServerConfig"])._ServerConfig(
                        name="myserver", command="python", args=["server.py"]
                    )
                ),
            )
        )

    from app.services import tool_registry
    assert "myserver__search" in tool_registry._REGISTRY
    registered = tool_registry._REGISTRY["myserver__search"]
    assert registered.source == "mcp"
    assert registered.loading == "deferred"


@pytest.mark.asyncio
async def test_startup_skips_malformed_tool_schema():
    """Tools whose schema conversion fails are skipped; server stays connected."""
    manager = MCPClientManager()

    # Tool that raises on attribute access to simulate malformed schema
    bad_tool = MagicMock()
    bad_tool.name = "bad_tool"
    bad_tool.description = "bad"
    bad_tool.inputSchema = MagicMock(side_effect=Exception("Schema error"))

    good_tool = _make_mcp_tool(name="good_tool", description="Good tool")

    mock_tools_result = SimpleNamespace(tools=[bad_tool, good_tool])
    mock_session = AsyncMock()
    mock_session.list_tools = AsyncMock(return_value=mock_tools_result)
    mock_session.initialize = AsyncMock()

    from app.services.mcp_client_manager import _ServerConfig, _ServerState

    state = _ServerState(config=_ServerConfig(name="svr", command="cmd", args=[]))
    manager._servers["svr"] = state

    with (
        patch("app.services.mcp_client_manager.MCPClientManager._open_stdio") as mock_open_stdio,
        patch("mcp.ClientSession", return_value=mock_session),
    ):
        mock_open_stdio.return_value = (AsyncMock(), AsyncMock())
        await manager._connect_server(state)

    from app.services import tool_registry
    # good_tool is registered; bad_tool is skipped
    assert "svr__good_tool" in tool_registry._REGISTRY
    assert "svr__bad_tool" not in tool_registry._REGISTRY
    assert state.available is True


# ---------------------------------------------------------------------------
# Tests: call_tool routing + prefix stripping (MCP-04 / D-P15-06)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_tool_strips_prefix_and_routes():
    """call_tool() forwards original_tool_name (no server prefix) to the MCP session."""
    manager = MCPClientManager()

    mock_result = SimpleNamespace(content=[SimpleNamespace(text="result_text")])
    mock_session = AsyncMock()
    mock_session.call_tool = AsyncMock(return_value=mock_result)

    from app.services.mcp_client_manager import _ServerConfig, _ServerState

    state = _ServerState(
        config=_ServerConfig(name="myserver", command="cmd", args=[]),
        session=mock_session,
        available=True,
    )
    manager._servers["myserver"] = state

    result = await manager.call_tool("myserver", "search", {"query": "test"})

    mock_session.call_tool.assert_called_once_with("search", {"query": "test"})
    assert result == {"result": "result_text"}


@pytest.mark.asyncio
async def test_call_tool_returns_error_when_unavailable():
    """call_tool() returns error dict when server is unavailable."""
    manager = MCPClientManager()

    from app.services.mcp_client_manager import _ServerConfig, _ServerState

    state = _ServerState(
        config=_ServerConfig(name="myserver", command="cmd", args=[]),
        session=None,
        available=False,
    )
    manager._servers["myserver"] = state

    result = await manager.call_tool("myserver", "search", {})
    assert "error" in result
    assert "not available" in result["error"]


@pytest.mark.asyncio
async def test_call_tool_unknown_server_returns_error():
    """call_tool() returns error dict for unknown server name."""
    manager = MCPClientManager()
    result = await manager.call_tool("unknown_server", "some_tool", {})
    assert "error" in result


# ---------------------------------------------------------------------------
# Tests: disconnect handling (MCP-05 / D-P15-10..D-P15-11)
# ---------------------------------------------------------------------------


def test_handle_tool_call_failure_marks_server_unavailable():
    """_handle_tool_call_failure() marks server unavailable and calls mark_server_unavailable."""
    from app.services import tool_registry

    async def noop(**kw):
        return {}

    tool_registry.register(
        "myserver__tool1", "desc", {"type": "function", "function": {"name": "myserver__tool1"}},
        source="mcp", loading="deferred", executor=noop,
    )

    manager = MCPClientManager()
    from app.services.mcp_client_manager import _ServerConfig, _ServerState

    state = _ServerState(
        config=_ServerConfig(name="myserver", command="cmd", args=[]),
        available=True,
    )
    manager._servers["myserver"] = state

    manager._handle_tool_call_failure("myserver")

    assert state.available is False
    assert tool_registry._REGISTRY["myserver__tool1"].available is False


# ---------------------------------------------------------------------------
# Tests: shutdown (D-P15-02, D-P15-12)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_shutdown_cancels_reconnect_tasks():
    """shutdown() cancels all reconnect tasks."""
    manager = MCPClientManager()

    from app.services.mcp_client_manager import _ServerConfig, _ServerState

    async def long_running():
        try:
            await asyncio.sleep(100)
        except asyncio.CancelledError:
            raise

    task = asyncio.create_task(long_running())
    state = _ServerState(
        config=_ServerConfig(name="svr", command="cmd", args=[]),
        reconnect_task=task,
    )
    manager._servers["svr"] = state

    await manager.shutdown()

    assert task.cancelled()
    assert len(manager._servers) == 0


@pytest.mark.asyncio
async def test_startup_skips_when_flag_off():
    """startup() is a no-op when TOOL_REGISTRY_ENABLED=False."""
    manager = MCPClientManager()
    with patch("app.config.get_settings") as mock_settings:
        mock_settings.return_value.tool_registry_enabled = False
        mock_settings.return_value.mcp_servers = "github:npx:arg"
        await manager.startup()
    assert len(manager._servers) == 0


@pytest.mark.asyncio
async def test_startup_skips_when_mcp_servers_empty():
    """startup() is a no-op when MCP_SERVERS is empty."""
    manager = MCPClientManager()
    with patch("app.config.get_settings") as mock_settings:
        mock_settings.return_value.tool_registry_enabled = True
        mock_settings.return_value.mcp_servers = ""
        await manager.startup()
    assert len(manager._servers) == 0
```

Note: This test file uses `pytest-asyncio`. Check that `pytest.ini` or `pyproject.toml` has `asyncio_mode = "auto"` or add `@pytest.mark.asyncio` decorators as shown. Look at existing async tests to match the pattern used in this codebase.

After writing the file, run: `cd backend && source venv/bin/activate && python -m pytest tests/unit/test_mcp_client_manager.py -v --tb=short 2>&1 | tail -30`

Fix any import errors or assertion failures before marking this task complete. Common issues:
- `asyncio_mode` not set → add `@pytest.mark.asyncio` to async tests
- `_ServerState` / `_ServerConfig` private classes → import from `mcp_client_manager` directly
- Mock patching paths → use `app.services.mcp_client_manager.ClientSession` not `mcp.ClientSession` if the import is inside the method
</action>
<acceptance_criteria>
- `test -f backend/tests/unit/test_mcp_client_manager.py` exits 0
- `grep -c "^def test_\|^async def test_" backend/tests/unit/test_mcp_client_manager.py` returns a number >= 15
- `cd backend && source venv/bin/activate && python -m pytest tests/unit/test_mcp_client_manager.py -v --tb=short 2>&1 | grep -E "PASSED|FAILED|ERROR" | head -30` shows all tests PASSED (no FAILED or ERROR)
- `cd backend && source venv/bin/activate && python -m pytest tests/unit/test_mcp_client_manager.py -v --tb=short 2>&1 | tail -3` shows `passed` with 0 failures
</acceptance_criteria>
</task>

<task id="2">
<name>Create backend/tests/unit/test_tool_registry_availability.py</name>
<read_first>
- backend/app/services/tool_registry.py (mark_server_available, mark_server_unavailable, build_catalog_block, build_llm_tools)
- backend/app/models/tools.py (ToolDefinition with available field from Plan 15-01)
- backend/tests/unit/test_tool_registry.py (_reset_registry fixture pattern)
</read_first>
<action>
Create `backend/tests/unit/test_tool_registry_availability.py`:

```python
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
        schema={"type": "function", "function": {"name": namespaced, "description": description, "parameters": {"type": "object", "properties": {}}}},
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
    """ToolDefinition.available can be set to False."""
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
    async def noop(**kw): return {}
    tool_registry.register("search_documents", "Search", {}, source="native", loading="immediate", executor=noop)

    count = tool_registry.mark_server_unavailable("search_documents")
    assert count == 0
    assert tool_registry._REGISTRY["search_documents"].available is True


# ---------------------------------------------------------------------------
# Tests: build_catalog_block with availability filter (D-P15-11)
# ---------------------------------------------------------------------------


def test_build_catalog_block_omits_unavailable_tools():
    """build_catalog_block() does not include tools where available=False."""
    _register_mcp_tool("svr", "available_tool", "Available tool")
    _register_mcp_tool("svr", "unavailable_tool", "Unavailable tool")
    tool_registry.mark_server_unavailable("svr")
    # Re-register available tool (same registry, now all svr tools are unavailable)
    # Manually restore one tool:
    tool_registry._REGISTRY["svr__available_tool"].available = True

    catalog = asyncio.run(tool_registry.build_catalog_block())
    assert "available_tool" in catalog
    assert "unavailable_tool" not in catalog


def test_build_catalog_block_includes_available_mcp_tools():
    """build_catalog_block() includes MCP tools that are available=True."""
    _register_mcp_tool("svr", "my_tool", "My MCP tool description")
    # Tool starts with available=True (default)

    catalog = asyncio.run(tool_registry.build_catalog_block())
    assert "svr__my_tool" in catalog
    assert "mcp" in catalog


# ---------------------------------------------------------------------------
# Tests: build_llm_tools with availability filter (D-P15-11)
# ---------------------------------------------------------------------------


def test_build_llm_tools_omits_unavailable_tools():
    """build_llm_tools() does not include tools where available=False."""
    async def noop(**kw): return {}
    tool_registry.register(
        "svr__tool1",
        "Tool 1",
        {"type": "function", "function": {"name": "svr__tool1"}},
        source="mcp",
        loading="immediate",  # Use immediate so it appears in LLM tools array
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
    async def noop(**kw): return {}
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
```

After writing, run:
`cd backend && source venv/bin/activate && python -m pytest tests/unit/test_tool_registry_availability.py -v --tb=short 2>&1 | tail -30`

Fix any failures. Common issue: Pydantic v2 models may be immutable — if `tool.available = False` raises, use `tool_registry._REGISTRY[name] = tool.model_copy(update={"available": False})` in the `mark_server_unavailable` implementation.
</action>
<acceptance_criteria>
- `test -f backend/tests/unit/test_tool_registry_availability.py` exits 0
- `grep -c "^def test_" backend/tests/unit/test_tool_registry_availability.py` returns a number >= 10
- `cd backend && source venv/bin/activate && python -m pytest tests/unit/test_tool_registry_availability.py -v --tb=short 2>&1 | tail -5` shows all tests PASSED with 0 failures
- `cd backend && source venv/bin/activate && python -m pytest tests/unit/test_tool_registry.py tests/unit/test_tool_registry_availability.py tests/unit/test_mcp_client_manager.py -v --tb=short 2>&1 | tail -5` exits 0 (all pass)
</acceptance_criteria>
</task>

</tasks>

<verification>
Plan 15-05 is complete when:
1. `backend/tests/unit/test_mcp_client_manager.py` has ≥15 test functions, all passing
2. `backend/tests/unit/test_tool_registry_availability.py` has ≥10 test functions, all passing
3. All pre-existing Phase 13 registry tests still pass (`test_tool_registry.py`)
4. Combined test run exits 0: `pytest tests/unit/test_tool_registry.py tests/unit/test_tool_registry_availability.py tests/unit/test_mcp_client_manager.py -v`
5. No FAILED or ERROR in the combined output

MCP-06 coverage: MCP tools are registered in the unified registry and appear in the catalog (same table as native/skill tools) — verified by `test_build_catalog_block_includes_available_mcp_tools` and `test_build_llm_tools_includes_available_mcp_tools`.
</verification>
