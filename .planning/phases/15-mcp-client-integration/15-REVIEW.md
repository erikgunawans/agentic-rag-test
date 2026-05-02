---
phase: 15
status: clean
depth: standard
files_reviewed: 7
findings:
  critical: 0
  warning: 2
  info: 3
  total: 5
reviewed: 2026-05-03
---

# Code Review — Phase 15: MCP Client Integration

## Files Reviewed

1. `backend/app/models/tools.py`
2. `backend/app/services/mcp_client_manager.py`
3. `backend/app/services/tool_registry.py`
4. `backend/app/config.py`
5. `backend/app/main.py`
6. `backend/tests/unit/test_mcp_client_manager.py`
7. `backend/tests/unit/test_tool_registry_availability.py`

---

## Findings

### WR-01 — `_open_stdio` uses `__aenter__` directly without paired `__aexit__` on error path

**File:** `backend/app/services/mcp_client_manager.py` — `_open_stdio()` / `_connect_server()`
**Severity:** Warning

`_open_stdio()` calls `ctx.__aenter__()` to open an `stdio_client` async context manager and stores the context in `self._open_contexts[server_name]`. However, if `_connect_server()` fails after `_open_stdio()` succeeds (e.g., `session.initialize()` raises), the context manager is stored but the error path in `_connect_server`'s `except Exception` block returns `False` without calling `__aexit__` on the stored context. This can leak subprocess handles for the duration of the app lifecycle.

`shutdown()` does iterate `_open_contexts` and call `__aexit__`, so the leak only persists until app shutdown — not indefinitely. Still, repeated failed reconnects would accumulate dead stdio contexts.

**Recommendation:** In `_connect_server`'s `except Exception` block, check if a context was stored for this server and call `__aexit__` on it before returning `False`:

```python
except Exception as e:
    # Clean up stdio context if opened but connect failed
    if cfg.name in self._open_contexts:
        try:
            await self._open_contexts.pop(cfg.name).__aexit__(None, None, None)
        except Exception:
            pass
    logger.warning(...)
    return False
```

---

### WR-02 — `dataclass` imports `field` but never uses it

**File:** `backend/app/services/mcp_client_manager.py` — line 31
**Severity:** Warning

```python
from dataclasses import dataclass, field
```

`field` is imported but not used anywhere in the file. All `@dataclass` fields use plain defaults. This is a minor lint issue (would fail `flake8 F401`).

**Fix:** Remove `field` from the import:
```python
from dataclasses import dataclass
```

---

### IN-01 — `lru_cache` singleton `get_mcp_client_manager` is not reset between tests

**File:** `backend/tests/unit/test_mcp_client_manager.py`
**Severity:** Info

`get_mcp_client_manager()` uses `@lru_cache` for singleton behavior. The test file creates `MCPClientManager()` instances directly (correct — avoids the singleton), but if any test accidentally calls `get_mcp_client_manager()`, the singleton instance would persist across tests. The `_reset_registry` fixture only resets the tool registry, not the manager singleton.

This is not a current bug (tests don't call `get_mcp_client_manager()`), but worth noting for future tests that may test startup integration paths.

**Recommendation:** Consider adding a note in the test file's docstring or a `_reset_manager` fixture that calls `get_mcp_client_manager.cache_clear()` if needed.

---

### IN-02 — `MCP_SERVERS` env var is not documented with a format validator

**File:** `backend/app/config.py`
**Severity:** Info

`mcp_servers: str = ""` accepts any string and defers format validation to `parse_mcp_servers()` at runtime (startup). A malformed value like `"github"` (no colon) silently produces an empty server list with only a log warning — no startup error. This matches the project's non-critical MCP design intent (D-P15-01), but operators may not notice the warning if they don't check logs.

This is acceptable per the design decision, but worth noting for observability. The `_handle_tool_call_failure` path would later mark it unavailable with an ERROR log if a partially-valid entry somehow connected.

No action required — documents the accepted design trade-off.

---

### IN-03 — `_reconnect_loop` marks tools unavailable AFTER the backoff sleep, not immediately on disconnect

**File:** `backend/app/services/mcp_client_manager.py` — `_reconnect_loop()`
**Severity:** Info

The reconnect loop calls `mark_server_unavailable(server_name)` at the start of each reconnect attempt (after the backoff sleep). This means there's a window after `state.available` is set to `False` (by `_handle_tool_call_failure`) but before `mark_server_unavailable` is called in the reconnect loop where `state.available=False` but the registry tools still show `available=True`.

In practice this window is at most 30 seconds (the heartbeat sleep interval in `_reconnect_loop`). The `call_tool()` guard checks `state.available` directly and rejects calls immediately on disconnect, so the only "incorrect" state is the catalog showing the tool as available when it cannot be called.

This is an acceptable race condition for v1.2 (catalog is advisory, call_tool is the enforcement point). Documents the known behavior.

---

## Summary

Phase 15 code is well-structured, follows established patterns (singleton, feature-flagged lifespan hooks, try/except non-critical warmup), and the test coverage is comprehensive (68 tests, 0 failures). The two warnings (subprocess handle leak on failed connect, unused import) are low-risk and should be fixed before production deployment. The three informational findings are design trade-offs consistent with the CONTEXT.md decisions.

**Verdict:** Advisory fixes recommended for WR-01 and WR-02 before Railway deploy. No blocking issues.
