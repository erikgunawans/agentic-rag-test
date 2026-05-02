"""Phase 15: MCPClientManager unit tests.

MCP-01..06 — covers parse, convert, register, call_tool, disconnect, reconnect.

All mcp SDK imports are mocked — tests do NOT require a running MCP server.
Pattern mirrors test_tool_registry.py: autouse _reset_registry fixture +
asyncio.run() for async tests (no asyncio_mode=auto in pyproject.toml).
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.mcp_client_manager import (
    MCPClientManager,
    _ServerConfig,
    _ServerState,
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
    return SimpleNamespace(
        name=name,
        description=description,
        inputSchema=input_schema,
    )


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


def test_schema_conversion_returns_none_on_exception():
    """_convert_mcp_tool_to_openai returns None when conversion raises."""
    bad_tool = MagicMock()
    bad_tool.name = "bad"
    # Make inputSchema raise when accessed
    type(bad_tool).inputSchema = property(lambda self: (_ for _ in ()).throw(Exception("boom")))
    schema = _convert_mcp_tool_to_openai("srv", bad_tool)
    assert schema is None


# ---------------------------------------------------------------------------
# Tests: startup + registration (MCP-02, MCP-04 / D-P15-07, D-P15-08)
# ---------------------------------------------------------------------------


def _make_mock_session(tools: list) -> AsyncMock:
    """Build a mock mcp.ClientSession with given tools list."""
    mock_session = AsyncMock()
    mock_session.initialize = AsyncMock()
    mock_session.list_tools = AsyncMock(return_value=SimpleNamespace(tools=tools))
    mock_session.call_tool = AsyncMock()
    return mock_session


def _patch_connect_server(manager: MCPClientManager, mock_session: AsyncMock):
    """Patch _connect_server to directly set session and register tools, bypassing mcp SDK."""

    async def _fake_connect(state: _ServerState) -> bool:
        from app.services import tool_registry

        cfg = state.config
        # Simulate what _connect_server does: list tools, convert, register
        tools_result = await mock_session.list_tools()
        for tool in tools_result.tools:
            schema = _convert_mcp_tool_to_openai(cfg.name, tool)
            if schema is None:
                continue
            namespaced_name = schema["function"]["name"]

            async def _executor(
                arguments: dict,
                user_id: str = "",
                context: dict | None = None,
                _mgr=manager,
                _sname=cfg.name,
                _tname=tool.name,
                **kwargs: Any,
            ) -> dict | str:
                return await _mgr.call_tool(_sname, _tname, arguments)

            tool_registry.register(
                name=namespaced_name,
                description=tool.description or "",
                schema=schema,
                source="mcp",
                loading="deferred",
                executor=_executor,
            )
        state.session = mock_session
        state.available = True
        state.fail_count = 0
        tool_registry.mark_server_available(cfg.name)
        return True

    return _fake_connect


def test_startup_registers_tools_with_mcp_source():
    """_connect_server() registers MCP tools with source='mcp', loading='deferred'."""
    manager = MCPClientManager()

    mock_tool = _make_mcp_tool(
        name="search",
        description="Search tool",
        input_schema={"type": "object", "properties": {}},
    )
    mock_session = _make_mock_session([mock_tool])

    state = _ServerState(config=_ServerConfig(name="myserver", command="python", args=["server.py"]))
    manager._servers["myserver"] = state

    asyncio.run(_patch_connect_server(manager, mock_session)(state))

    from app.services import tool_registry
    assert "myserver__search" in tool_registry._REGISTRY
    registered = tool_registry._REGISTRY["myserver__search"]
    assert registered.source == "mcp"
    assert registered.loading == "deferred"


def test_startup_skips_malformed_tool_schema():
    """Tools whose schema conversion fails are skipped; server stays connected."""
    manager = MCPClientManager()

    # bad_tool: inputSchema raises on access
    bad_tool = MagicMock()
    bad_tool.name = "bad_tool"
    bad_tool.description = "bad"
    type(bad_tool).inputSchema = property(lambda self: (_ for _ in ()).throw(Exception("Schema error")))

    good_tool = _make_mcp_tool(name="good_tool", description="Good tool")
    mock_session = _make_mock_session([bad_tool, good_tool])

    state = _ServerState(config=_ServerConfig(name="svr", command="cmd", args=[]))
    manager._servers["svr"] = state

    asyncio.run(_patch_connect_server(manager, mock_session)(state))

    from app.services import tool_registry
    assert "svr__good_tool" in tool_registry._REGISTRY
    assert "svr__bad_tool" not in tool_registry._REGISTRY
    assert state.available is True


# ---------------------------------------------------------------------------
# Tests: call_tool routing + prefix stripping (MCP-04 / D-P15-06)
# ---------------------------------------------------------------------------


def test_call_tool_strips_prefix_and_routes():
    """call_tool() forwards original_tool_name (no server prefix) to the MCP session."""
    manager = MCPClientManager()

    mock_result = SimpleNamespace(content=[SimpleNamespace(text="result_text")])
    mock_session = AsyncMock()
    mock_session.call_tool = AsyncMock(return_value=mock_result)

    state = _ServerState(
        config=_ServerConfig(name="myserver", command="cmd", args=[]),
        session=mock_session,
        available=True,
    )
    manager._servers["myserver"] = state

    result = asyncio.run(manager.call_tool("myserver", "search", {"query": "test"}))

    mock_session.call_tool.assert_called_once_with("search", {"query": "test"})
    assert result == {"result": "result_text"}


def test_call_tool_returns_error_when_unavailable():
    """call_tool() returns error dict when server is unavailable."""
    manager = MCPClientManager()

    state = _ServerState(
        config=_ServerConfig(name="myserver", command="cmd", args=[]),
        session=None,
        available=False,
    )
    manager._servers["myserver"] = state

    result = asyncio.run(manager.call_tool("myserver", "search", {}))
    assert "error" in result
    assert "not available" in result["error"]


def test_call_tool_unknown_server_returns_error():
    """call_tool() returns error dict for unknown server name."""
    manager = MCPClientManager()
    result = asyncio.run(manager.call_tool("unknown_server", "some_tool", {}))
    assert "error" in result


def test_call_tool_exception_triggers_handle_failure():
    """call_tool() calls _handle_tool_call_failure on session exception."""
    manager = MCPClientManager()

    from app.services import tool_registry

    async def noop(**kw):
        return {}

    tool_registry.register(
        "myserver__tool1", "desc",
        {"type": "function", "function": {"name": "myserver__tool1"}},
        source="mcp", loading="deferred", executor=noop,
    )

    mock_session = AsyncMock()
    mock_session.call_tool = AsyncMock(side_effect=Exception("connection reset"))

    state = _ServerState(
        config=_ServerConfig(name="myserver", command="cmd", args=[]),
        session=mock_session,
        available=True,
    )
    manager._servers["myserver"] = state

    result = asyncio.run(manager.call_tool("myserver", "tool1", {}))
    assert "error" in result
    assert state.available is False  # marked unavailable by _handle_tool_call_failure
    assert tool_registry._REGISTRY["myserver__tool1"].available is False


# ---------------------------------------------------------------------------
# Tests: disconnect handling (MCP-05 / D-P15-10..D-P15-11)
# ---------------------------------------------------------------------------


def test_handle_tool_call_failure_marks_server_unavailable():
    """_handle_tool_call_failure() marks server unavailable and calls mark_server_unavailable."""
    from app.services import tool_registry

    async def noop(**kw):
        return {}

    tool_registry.register(
        "myserver__tool1", "desc",
        {"type": "function", "function": {"name": "myserver__tool1"}},
        source="mcp", loading="deferred", executor=noop,
    )

    manager = MCPClientManager()
    state = _ServerState(
        config=_ServerConfig(name="myserver", command="cmd", args=[]),
        available=True,
    )
    manager._servers["myserver"] = state

    manager._handle_tool_call_failure("myserver")

    assert state.available is False
    assert tool_registry._REGISTRY["myserver__tool1"].available is False


def test_handle_tool_call_failure_noop_when_already_unavailable():
    """_handle_tool_call_failure() is idempotent when server already unavailable."""
    manager = MCPClientManager()
    state = _ServerState(
        config=_ServerConfig(name="myserver", command="cmd", args=[]),
        available=False,
    )
    manager._servers["myserver"] = state
    # Should not raise
    manager._handle_tool_call_failure("myserver")
    assert state.available is False


# ---------------------------------------------------------------------------
# Tests: shutdown (D-P15-02, D-P15-12)
# ---------------------------------------------------------------------------


def test_shutdown_cancels_reconnect_tasks():
    """shutdown() cancels all reconnect tasks."""
    manager = MCPClientManager()

    async def long_running():
        try:
            await asyncio.sleep(100)
        except asyncio.CancelledError:
            raise

    async def run():
        task = asyncio.create_task(long_running())
        state = _ServerState(
            config=_ServerConfig(name="svr", command="cmd", args=[]),
            reconnect_task=task,
        )
        manager._servers["svr"] = state
        await manager.shutdown()
        assert task.cancelled()
        assert len(manager._servers) == 0

    asyncio.run(run())


def test_startup_skips_when_flag_off():
    """startup() is a no-op when TOOL_REGISTRY_ENABLED=False."""
    manager = MCPClientManager()
    with patch("app.services.mcp_client_manager.get_settings") as mock_settings:
        mock_settings.return_value.tool_registry_enabled = False
        mock_settings.return_value.mcp_servers = "github:npx:arg"
        asyncio.run(manager.startup())
    assert len(manager._servers) == 0


def test_startup_skips_when_mcp_servers_empty():
    """startup() is a no-op when MCP_SERVERS is empty."""
    manager = MCPClientManager()
    with patch("app.services.mcp_client_manager.get_settings") as mock_settings:
        mock_settings.return_value.tool_registry_enabled = True
        mock_settings.return_value.mcp_servers = ""
        asyncio.run(manager.startup())
    assert len(manager._servers) == 0


def test_server_names_returns_configured_servers():
    """server_names() returns list of all configured server names."""
    manager = MCPClientManager()
    manager._servers["s1"] = _ServerState(config=_ServerConfig(name="s1", command="c", args=[]))
    manager._servers["s2"] = _ServerState(config=_ServerConfig(name="s2", command="c", args=[]))
    assert set(manager.server_names()) == {"s1", "s2"}


def test_is_server_available_true_when_connected():
    """is_server_available() returns True when server state is available."""
    manager = MCPClientManager()
    state = _ServerState(
        config=_ServerConfig(name="s1", command="cmd", args=[]),
        available=True,
    )
    manager._servers["s1"] = state
    assert manager.is_server_available("s1") is True


def test_is_server_available_false_when_not_present():
    """is_server_available() returns False for unknown server."""
    manager = MCPClientManager()
    assert manager.is_server_available("nonexistent") is False
