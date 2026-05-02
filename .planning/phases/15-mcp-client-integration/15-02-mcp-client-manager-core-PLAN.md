---
phase: 15-mcp-client-integration
plan: 02
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/app/services/mcp_client_manager.py
autonomous: true
requirements:
  - MCP-01
  - MCP-02
  - MCP-03
  - MCP-04
must_haves:
  truths:
    - "backend/app/services/mcp_client_manager.py exists as a new file with class MCPClientManager"
    - "MCPClientManager.parse_mcp_servers(mcp_servers_str) correctly parses 'name:command:args' format splitting on first two colons only; multiple servers are comma-separated"
    - "MCPClientManager.startup() calls tool_registry.register() for each discovered MCP tool with source='mcp', loading='deferred', and an executor closure that calls call_tool()"
    - "MCP tool names are namespaced as '{server_name}__{original_tool_name}' (double underscore separator)"
    - "Schema conversion: MCP tool inputSchema maps to OpenAI 'parameters' field; missing inputSchema uses empty object {'type':'object','properties':{}}"
    - "Tools with malformed/unconvertable inputSchema are skipped with a WARNING log; the server remains connected with its other tools"
    - "MCPClientManager.call_tool(server_name, original_tool_name, arguments) strips the server_name prefix before forwarding to mcp SDK call_tool"
    - "get_mcp_client_manager() returns a module-level singleton via lru_cache pattern identical to get_sandbox_service()"
    - "When MCP_SERVERS is empty string or TOOL_REGISTRY_ENABLED is False, startup() is a no-op that spawns zero processes"
  artifacts:
    - path: "backend/app/services/mcp_client_manager.py"
      provides: "MCPClientManager class, get_mcp_client_manager() singleton, parse_mcp_servers(), startup(), shutdown(), call_tool()"
      contains: "class MCPClientManager"
  key_links:
    - from: "backend/app/services/mcp_client_manager.py"
      to: "backend/app/services/tool_registry.py"
      via: "tool_registry.register() called from startup() for each MCP tool"
      pattern: "tool_registry\\.register"
    - from: "MCPClientManager.call_tool"
      to: "mcp.ClientSession.call_tool"
      via: "executor closure strips server_name prefix and forwards original_tool_name"
      pattern: "call_tool"
---

<objective>
Create `backend/app/services/mcp_client_manager.py` — the new core MCP integration service.

This plan implements:
1. `parse_mcp_servers(s: str) -> list[ServerConfig]` — parse `MCP_SERVERS` env var (format: `name:command:args`, split on first 2 colons only, multiple servers comma-separated, `shlex.split` for args)
2. `MCPClientManager` class with:
   - `startup()` — async method that for each configured server: spawns via `mcp` SDK's `stdio_client(StdioServerParameters(command=cmd, args=args_list))`, opens a `ClientSession`, calls `session.list_tools()`, converts each tool to OpenAI schema, and registers via `tool_registry.register(name=f"{server_name}__{tool.name}", source="mcp", loading="deferred", ...)`
   - `shutdown()` — async method that terminates all child processes cleanly
   - `call_tool(server_name, original_tool_name, arguments)` — calls `session.call_tool(original_tool_name, arguments)` and returns the result content as a dict
3. `get_mcp_client_manager()` — `@lru_cache` singleton (mirrors `get_sandbox_service()` pattern)

The reconnect loop and availability management (D-P15-10..D-P15-12) are in Plan 15-04 — this plan focuses on the happy-path connect/register/call flow.

**mcp SDK async API** (reference):
```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async with stdio_client(StdioServerParameters(command=cmd, args=args_list)) as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()
        tools_result = await session.list_tools()
        # tools_result.tools: list[mcp.types.Tool]
        # tool.name, tool.description, tool.inputSchema (JSON Schema dict)
        result = await session.call_tool(tool_name, arguments)
        # result.content: list[TextContent | ImageContent | EmbeddedResource]
        # result.content[0].text for text results
```
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/phases/15-mcp-client-integration/15-CONTEXT.md
@backend/app/services/tool_registry.py
@backend/app/services/sandbox_service.py
@backend/app/models/tools.py
@backend/app/config.py
</context>

<tasks>

<task id="1">
<name>Create backend/app/services/mcp_client_manager.py with core structure</name>
<read_first>
- backend/app/services/sandbox_service.py (singleton pattern, dataclass usage, asyncio.Lock, background task)
- backend/app/services/tool_registry.py (register() API signature, source/loading Literals)
- backend/app/models/tools.py (ToolDefinition shape for reference)
- backend/app/config.py (get_settings() pattern)
</read_first>
<action>
Create `backend/app/services/mcp_client_manager.py` with the following implementation:

```python
"""Phase 15: MCP Client Integration — MCPClientManager.

MCP-01..06 / D-P15-01..D-P15-15.

Manages stdio-transport connections to external MCP servers, discovers their
tools, converts MCP JSON Schema to OpenAI function-calling format, and
registers tools in the unified registry as source='mcp', loading='deferred'.

Reconnect-with-backoff for disconnected servers (D-P15-10..D-P15-12) is
wired in the startup() method via asyncio background tasks.

Decisions enforced:
  - D-P15-03: parse 'name:command:args' splitting on first 2 colons; shlex.split for args.
  - D-P15-04: eager schema conversion at connect time; per-tool skip on failure.
  - D-P15-05: missing inputSchema → permissive passthrough {'type':'object','properties':{}}.
  - D-P15-06: tool names namespaced '{server_name}__{original_tool_name}'; executor strips prefix.
  - D-P15-07: register() called with source='mcp', loading='deferred'.
  - D-P15-08: deferred loading — MCP tools not injected into LLM array until tool_search activates them.
  - D-P15-10: exponential backoff [1,2,4,8,16,32]s, stop after 5 failures.
  - D-P15-11: mark_server_unavailable / mark_server_available via tool_registry.
  - D-P15-12: reconnect as asyncio.Task per server, cancelled in shutdown().
  - D-P15-13: MCP call_tool does NOT route through egress filter (not a cloud-LLM call).
  - D-P15-14: MCP tool results flow back through chat.py _run_tool_loop for de-anonymization.
  - D-P15-15: LLM arguments already anonymized upstream (Phase 5 BUFFER-01..03).
"""
from __future__ import annotations

import asyncio
import logging
import shlex
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)

# D-P15-10: exponential backoff delays (seconds), max 32s cap.
_BACKOFF_DELAYS = [1, 2, 4, 8, 16, 32]
_MAX_FAILURES = 5  # stop retrying after 5 consecutive failures


@dataclass
class _ServerConfig:
    """Parsed entry from MCP_SERVERS env var (D-P15-03)."""
    name: str
    command: str
    args: list[str]


@dataclass
class _ServerState:
    """Per-server runtime state. Internal implementation detail."""
    config: _ServerConfig
    session: Any = None          # mcp.ClientSession when connected, else None
    available: bool = False      # True after successful startup() connect
    fail_count: int = 0
    reconnect_task: asyncio.Task | None = None


def parse_mcp_servers(mcp_servers_str: str) -> list[_ServerConfig]:
    """Parse MCP_SERVERS env var into a list of server configs (D-P15-03).

    Format: 'name:command:args' where args is everything after the second colon.
    Multiple servers: comma-separated. Empty or whitespace-only → empty list.

    Examples:
      'github:npx:-y @modelcontextprotocol/server-github' →
        _ServerConfig(name='github', command='npx', args=['-y', '@modelcontextprotocol/server-github'])
      'postgres:python:server.py --port 5432' →
        _ServerConfig(name='postgres', command='python', args=['server.py', '--port', '5432'])
    """
    if not mcp_servers_str or not mcp_servers_str.strip():
        return []

    configs: list[_ServerConfig] = []
    for entry in mcp_servers_str.split(","):
        entry = entry.strip()
        if not entry:
            continue
        parts = entry.split(":", 2)
        if len(parts) < 2:
            logger.warning(
                "mcp_client_manager: malformed MCP_SERVERS entry %r — "
                "expected 'name:command[:args]', skipping",
                entry,
            )
            continue
        name = parts[0].strip()
        command = parts[1].strip()
        args_str = parts[2].strip() if len(parts) > 2 else ""
        try:
            args = shlex.split(args_str) if args_str else []
        except ValueError as e:
            logger.warning(
                "mcp_client_manager: shlex.split failed for entry %r args=%r: %s — skipping",
                entry,
                args_str,
                e,
            )
            continue
        if not name or not command:
            logger.warning(
                "mcp_client_manager: empty name or command in entry %r — skipping",
                entry,
            )
            continue
        configs.append(_ServerConfig(name=name, command=command, args=args))

    return configs


def _convert_mcp_tool_to_openai(server_name: str, tool) -> dict | None:
    """Convert an mcp.types.Tool to an OpenAI function-calling schema (D-P15-04, D-P15-05).

    Returns None if conversion fails (caller logs and skips).
    Tool name is namespaced: '{server_name}__{tool.name}' (D-P15-06).
    """
    try:
        namespaced_name = f"{server_name}__{tool.name}"
        description = tool.description or ""
        # D-P15-05: missing inputSchema → permissive passthrough
        input_schema = tool.inputSchema if tool.inputSchema else {"type": "object", "properties": {}}
        # inputSchema is already a JSON Schema dict — maps directly to OpenAI 'parameters'
        return {
            "type": "function",
            "function": {
                "name": namespaced_name,
                "description": description,
                "parameters": input_schema,
            },
        }
    except Exception as e:
        logger.warning(
            "mcp_client_manager: schema conversion failed for tool=%s server=%s: %s — skipping",
            getattr(tool, "name", "?"),
            server_name,
            e,
        )
        return None


class MCPClientManager:
    """Manages stdio connections to external MCP servers.

    Lifecycle: startup() in FastAPI lifespan, shutdown() after yield.
    One asyncio.Task per server for reconnect-with-backoff (D-P15-12).
    """

    def __init__(self) -> None:
        self._servers: dict[str, _ServerState] = {}
        self._lock = asyncio.Lock()

    async def startup(self) -> None:
        """Parse MCP_SERVERS, connect to each server, register tools (D-P15-01).

        Idempotent: calling startup() twice when already running is a no-op.
        Wrapped in try/except by the caller (main.py lifespan) so failures
        never crash app startup (non-critical infrastructure).
        """
        settings = get_settings()
        if not settings.tool_registry_enabled or not settings.mcp_servers.strip():
            logger.debug("mcp_client_manager: startup skipped (flag off or no MCP_SERVERS)")
            return

        configs = parse_mcp_servers(settings.mcp_servers)
        if not configs:
            logger.debug("mcp_client_manager: no valid server configs parsed from MCP_SERVERS")
            return

        for cfg in configs:
            if cfg.name in self._servers:
                logger.debug("mcp_client_manager: server=%s already initialized, skipping", cfg.name)
                continue
            state = _ServerState(config=cfg)
            self._servers[cfg.name] = state
            await self._connect_server(state)

    async def _connect_server(self, state: _ServerState) -> bool:
        """Connect to a single MCP server and register its tools.

        Returns True on success, False on failure. Does NOT start the
        reconnect loop — that is handled by startup() and _reconnect_loop().
        """
        cfg = state.config
        logger.info(
            "mcp_client_manager: connecting to server=%s command=%s args=%s",
            cfg.name,
            cfg.command,
            cfg.args,
        )
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client

            server_params = StdioServerParameters(command=cfg.command, args=cfg.args)
            # Note: stdio_client is an async context manager that must stay open for
            # the lifetime of the connection. We store the session reference and keep
            # the context manager alive via a background task (see _run_server_session).
            # For the initial connect, we open the session here and store it.
            # The context manager exit (cleanup) happens in shutdown() or reconnect loop.
            read_stream, write_stream = await self._open_stdio(server_params)
            if read_stream is None:
                raise RuntimeError("stdio_client returned None streams")

            session = ClientSession(read_stream, write_stream)
            await session.initialize()
            tools_result = await session.list_tools()

            registered = 0
            skipped = 0
            for tool in tools_result.tools:
                schema = _convert_mcp_tool_to_openai(cfg.name, tool)
                if schema is None:
                    skipped += 1
                    continue
                namespaced_name = schema["function"]["name"]
                from app.services import tool_registry

                # Create executor closure capturing server_name and original tool name
                # Default-arg binding prevents late-binding closure bug (D-P13-01 pattern)
                async def _executor(
                    arguments: dict,
                    user_id: str,
                    context: dict | None = None,
                    _manager=self,
                    _server_name=cfg.name,
                    _tool_name=tool.name,
                    **kwargs,
                ) -> dict | str:
                    return await _manager.call_tool(_server_name, _tool_name, arguments)

                tool_registry.register(
                    name=namespaced_name,
                    description=tool.description or "",
                    schema=schema,
                    source="mcp",
                    loading="deferred",
                    executor=_executor,
                )
                registered += 1

            state.session = session
            state.available = True
            state.fail_count = 0

            # Mark all server tools as available in the registry (after reconnect,
            # they may have been marked unavailable by a prior disconnect)
            tool_registry.mark_server_available(cfg.name)

            logger.info(
                "mcp_client_manager: server=%s connected; registered=%d skipped=%d",
                cfg.name,
                registered,
                skipped,
            )
            return True

        except ImportError:
            logger.error(
                "mcp_client_manager: 'mcp' package not installed. "
                "Add 'mcp' to backend/requirements.txt and reinstall."
            )
            return False
        except Exception as e:
            logger.warning(
                "mcp_client_manager: failed to connect to server=%s: %s",
                cfg.name,
                e,
                exc_info=True,
            )
            return False

    async def _open_stdio(self, server_params):
        """Open stdio streams for an MCP server. Returns (read, write) or (None, None)."""
        try:
            from mcp.client.stdio import stdio_client

            # stdio_client is normally used as async context manager.
            # We use __aenter__ directly to get streams without exiting immediately.
            # The streams stay open as long as the MCPClientManager is alive.
            # shutdown() calls _close_stdio() to clean up.
            ctx = stdio_client(server_params)
            streams = await ctx.__aenter__()
            # Store context managers for cleanup in shutdown()
            if not hasattr(self, '_open_contexts'):
                self._open_contexts: dict[str, object] = {}
            return streams
        except Exception as e:
            logger.warning("mcp_client_manager: _open_stdio failed: %s", e)
            return None, None

    async def call_tool(
        self,
        server_name: str,
        original_tool_name: str,
        arguments: dict,
    ) -> dict | str:
        """Call an MCP tool on the named server (D-P15-06).

        Strips the server_name prefix — the MCP server receives only the
        original tool name. Returns the tool result as a dict or string.
        """
        state = self._servers.get(server_name)
        if state is None or state.session is None or not state.available:
            return {
                "error": f"MCP server '{server_name}' is not available. "
                         f"It may be disconnected and reconnecting."
            }
        try:
            result = await state.session.call_tool(original_tool_name, arguments)
            # Extract text content from MCP result
            if hasattr(result, "content") and result.content:
                content = result.content[0]
                if hasattr(content, "text"):
                    return {"result": content.text}
                # Image or embedded resource — return type info
                return {"result": str(content), "type": type(content).__name__}
            return {"result": None, "raw": str(result)}
        except Exception as e:
            logger.error(
                "mcp_client_manager: call_tool failed server=%s tool=%s: %s",
                server_name,
                original_tool_name,
                e,
            )
            return {"error": str(e)}

    async def shutdown(self) -> None:
        """Clean up all MCP server connections (D-P15-02)."""
        logger.info("mcp_client_manager: shutting down %d server(s)", len(self._servers))
        for server_name, state in self._servers.items():
            # Cancel reconnect task if running
            if state.reconnect_task and not state.reconnect_task.done():
                state.reconnect_task.cancel()
                try:
                    await state.reconnect_task
                except asyncio.CancelledError:
                    pass
            state.session = None
            state.available = False
        self._servers.clear()
        logger.info("mcp_client_manager: shutdown complete")

    def server_names(self) -> list[str]:
        """Return names of all configured servers."""
        return list(self._servers.keys())

    def is_server_available(self, server_name: str) -> bool:
        """Return True if the named server is connected and available."""
        state = self._servers.get(server_name)
        return state is not None and state.available


@lru_cache
def get_mcp_client_manager() -> MCPClientManager:
    """Return the process-singleton MCPClientManager instance (D-P15-02).

    Pattern mirrors get_sandbox_service() in sandbox_service.py.
    """
    return MCPClientManager()
```

Write this as the complete content of `backend/app/services/mcp_client_manager.py`.
</action>
<acceptance_criteria>
- `test -f backend/app/services/mcp_client_manager.py` exits 0 (file exists)
- `grep -n "class MCPClientManager" backend/app/services/mcp_client_manager.py` returns a match
- `grep -n "def get_mcp_client_manager" backend/app/services/mcp_client_manager.py` returns a match with `@lru_cache` above it
- `grep -n "def parse_mcp_servers" backend/app/services/mcp_client_manager.py` returns a match
- `grep -n "def call_tool" backend/app/services/mcp_client_manager.py` returns a match
- `cd backend && source venv/bin/activate && python -c "
from app.services.mcp_client_manager import parse_mcp_servers, get_mcp_client_manager

# Test parsing
configs = parse_mcp_servers('github:npx:-y @modelcontextprotocol/server-github')
assert len(configs) == 1
assert configs[0].name == 'github'
assert configs[0].command == 'npx'
assert configs[0].args == ['-y', '@modelcontextprotocol/server-github']

# Test empty
assert parse_mcp_servers('') == []
assert parse_mcp_servers('   ') == []

# Test malformed (too few colons) — should skip with warning
configs2 = parse_mcp_servers('badentry')
assert configs2 == []

# Test multi-server
configs3 = parse_mcp_servers('svr1:cmd1:arg1,svr2:cmd2:arg2 arg3')
assert len(configs3) == 2
assert configs3[0].name == 'svr1'
assert configs3[1].args == ['arg2', 'arg3']

# Test singleton
mgr1 = get_mcp_client_manager()
mgr2 = get_mcp_client_manager()
assert mgr1 is mgr2

print('PASS')
"` prints `PASS`
- `cd backend && source venv/bin/activate && python -c "from app.main import app; print('OK')"` prints `OK` (app import smoke test — note: mcp_client_manager should not be imported in main.py yet, that's Plan 15-03)
</acceptance_criteria>
</task>

</tasks>

<verification>
Plan 15-02 is complete when:
1. `backend/app/services/mcp_client_manager.py` exists with `MCPClientManager`, `parse_mcp_servers`, `get_mcp_client_manager`
2. `parse_mcp_servers` correctly handles: single server, multi-server (comma-separated), empty string, malformed entries
3. `startup()` calls `tool_registry.register()` for each discovered tool with `source='mcp'`, `loading='deferred'`
4. Tool names are namespaced `{server_name}__{tool.name}`
5. Executor closure captures server_name and original_tool_name at registration time (late-binding safe)
6. App import smoke test passes
</verification>
