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


def _convert_mcp_tool_to_openai(server_name: str, tool: Any) -> dict | None:
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
        self._open_contexts: dict[str, Any] = {}

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
            # Initial connect (happy path)
            await self._connect_server(state)
            # Spawn reconnect loop task regardless of initial connect success.
            # The loop monitors state.available and retries on failure (D-P15-12).
            state.reconnect_task = asyncio.create_task(
                self._reconnect_loop(cfg.name),
                name=f"mcp-reconnect-{cfg.name}",
            )
            logger.debug(
                "mcp_client_manager: spawned reconnect task for server=%s", cfg.name
            )

    async def _connect_server(self, state: _ServerState) -> bool:
        """Connect to a single MCP server and register its tools.

        Returns True on success, False on failure. Does NOT start the
        reconnect loop — that is handled by startup().
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
            from app.services import tool_registry

            server_params = StdioServerParameters(command=cfg.command, args=cfg.args)
            read_stream, write_stream = await self._open_stdio(cfg.name, server_params)
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

                # Create executor closure capturing server_name and original tool name.
                # Default-arg binding prevents late-binding closure bug (D-P13-01 pattern).
                async def _executor(
                    arguments: dict,
                    user_id: str,
                    context: dict | None = None,
                    _manager: MCPClientManager = self,
                    _server_name: str = cfg.name,
                    _tool_name: str = tool.name,
                    **kwargs: Any,
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
            # they may have been marked unavailable by a prior disconnect).
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

    async def _open_stdio(self, server_name: str, server_params: Any) -> tuple[Any, Any]:
        """Open stdio streams for an MCP server. Returns (read, write) or (None, None)."""
        try:
            from mcp.client.stdio import stdio_client

            # stdio_client is normally used as async context manager.
            # We use __aenter__ directly to get streams without exiting immediately.
            # The streams stay open as long as the MCPClientManager is alive.
            # shutdown() calls __aexit__ on stored context managers to clean up.
            ctx = stdio_client(server_params)
            streams = await ctx.__aenter__()
            self._open_contexts[server_name] = ctx
            return streams
        except Exception as e:
            logger.warning("mcp_client_manager: _open_stdio failed for server=%s: %s", server_name, e)
            return None, None

    async def _reconnect_loop(self, server_name: str) -> None:
        """Background reconnect loop with exponential backoff (D-P15-10..D-P15-12).

        Runs as an asyncio.Task for each server. Terminates when:
        - _MAX_FAILURES consecutive failures → logs ERROR and returns.
        - asyncio.CancelledError → re-raised (enables clean shutdown()).

        Backoff: _BACKOFF_DELAYS = [1, 2, 4, 8, 16, 32]s.
        After max failures stop retrying — operator must restart the app to retry.
        """
        from app.services import tool_registry

        state = self._servers.get(server_name)
        if state is None:
            return

        logger.debug("mcp_client_manager: _reconnect_loop started for server=%s", server_name)

        while True:
            try:
                if state.available:
                    # Server is up — wait a bit, then re-check (heartbeat interval).
                    # In practice, disconnection surfaces when call_tool() raises.
                    # The call_tool() error path sets state.available=False so we
                    # loop back into the reconnect path on the next iteration.
                    await asyncio.sleep(30)
                    continue

                # Server is unavailable — apply backoff and try to reconnect.
                if state.fail_count >= _MAX_FAILURES:
                    logger.error(
                        "mcp_client_manager: server=%s has failed %d times — "
                        "stopping reconnect loop. Restart the app to retry.",
                        server_name,
                        state.fail_count,
                    )
                    return

                delay_idx = min(state.fail_count, len(_BACKOFF_DELAYS) - 1)
                delay = _BACKOFF_DELAYS[delay_idx]
                logger.info(
                    "mcp_client_manager: server=%s unavailable (fail_count=%d) — "
                    "retrying in %ds",
                    server_name,
                    state.fail_count,
                    delay,
                )
                await asyncio.sleep(delay)

                # Mark tools unavailable before attempting reconnect (D-P15-11).
                tool_registry.mark_server_unavailable(server_name)

                success = await self._connect_server(state)
                if success:
                    # _connect_server() already calls mark_server_available() on success.
                    logger.info(
                        "mcp_client_manager: server=%s reconnected successfully (was down %d attempt(s))",
                        server_name,
                        state.fail_count,
                    )
                    state.fail_count = 0
                else:
                    state.fail_count += 1
                    logger.warning(
                        "mcp_client_manager: server=%s reconnect attempt %d/%d failed",
                        server_name,
                        state.fail_count,
                        _MAX_FAILURES,
                    )

            except asyncio.CancelledError:
                logger.debug(
                    "mcp_client_manager: _reconnect_loop cancelled for server=%s", server_name
                )
                raise  # Re-raise to allow clean cancellation (D-P15-12)
            except Exception as e:
                logger.error(
                    "mcp_client_manager: unexpected error in _reconnect_loop for server=%s: %s",
                    server_name,
                    e,
                    exc_info=True,
                )
                state.fail_count += 1
                # Continue loop — unexpected errors don't stop the reconnect loop

    def _handle_tool_call_failure(self, server_name: str) -> None:
        """Called when call_tool() encounters a connection error.

        Marks the server unavailable so the reconnect loop triggers.
        """
        state = self._servers.get(server_name)
        if state and state.available:
            state.available = False
            from app.services import tool_registry
            tool_registry.mark_server_unavailable(server_name)
            logger.warning(
                "mcp_client_manager: server=%s marked unavailable due to call_tool failure",
                server_name,
            )

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
            # D-P15-10: signal disconnect to the reconnect loop
            self._handle_tool_call_failure(server_name)
            return {"error": str(e)}

    async def shutdown(self) -> None:
        """Clean up all MCP server connections (D-P15-02)."""
        logger.info("mcp_client_manager: shutting down %d server(s)", len(self._servers))
        for server_name, state in list(self._servers.items()):
            # Cancel reconnect task (D-P15-12)
            if state.reconnect_task and not state.reconnect_task.done():
                state.reconnect_task.cancel()
                try:
                    await asyncio.wait_for(state.reconnect_task, timeout=5.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass
            state.session = None
            state.available = False
        # Close open stdio contexts
        for server_name, ctx in list(self._open_contexts.items()):
            try:
                await ctx.__aexit__(None, None, None)
            except Exception as e:
                logger.debug("mcp_client_manager: error closing stdio context for %s: %s", server_name, e)
        self._open_contexts.clear()
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
