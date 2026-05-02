---
plan: 15-02
phase: 15-mcp-client-integration
status: complete
wave: 1
completed: 2026-05-03
commit: 243244f
---

## Summary

Created `backend/app/services/mcp_client_manager.py` — the new MCP integration service. Implements `parse_mcp_servers()` (name:command:args format, shlex.split, comma-separated), `MCPClientManager` class with `startup()`, `_connect_server()`, `_reconnect_loop()`, `_handle_tool_call_failure()`, `call_tool()`, and `shutdown()`. Tools are namespaced `{server_name}__{tool_name}` and registered via `tool_registry.register()` with `source="mcp"`, `loading="deferred"`. Exponential backoff `[1,2,4,8,16,32]s` stops after 5 consecutive failures. `get_mcp_client_manager()` is an `@lru_cache` singleton.

## Key Files

- `backend/app/services/mcp_client_manager.py` (NEW, 474 lines)

## Self-Check: PASSED

- `parse_mcp_servers` handles all edge cases ✓
- `MCPClientManager` class exists with all required methods ✓
- `get_mcp_client_manager()` singleton via `@lru_cache` ✓
- `startup()` no-op when `TOOL_REGISTRY_ENABLED=False` or `MCP_SERVERS=""` ✓
- `_reconnect_loop` with `CancelledError` re-raise, `_BACKOFF_DELAYS`, `_MAX_FAILURES` ✓
- App import smoke test: `OK` ✓
