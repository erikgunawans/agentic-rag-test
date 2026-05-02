---
phase: 15-mcp-client-integration
plan: 04
type: execute
wave: 2
depends_on:
  - 15-02
files_modified:
  - backend/app/services/mcp_client_manager.py
autonomous: true
requirements:
  - MCP-05
must_haves:
  truths:
    - "MCPClientManager has a _reconnect_loop(server_name) async method that implements exponential backoff with delays [1, 2, 4, 8, 16, 32] seconds (max 32s cap)"
    - "After 5 consecutive failures, _reconnect_loop logs at ERROR level and stops retrying"
    - "After a successful reconnect, fail_count is reset to 0 and mark_server_available(server_name) is called"
    - "After a disconnect/failure, mark_server_unavailable(server_name) is called before starting the reconnect wait"
    - "startup() spawns an asyncio.Task per server for _reconnect_loop after the initial _connect_server call (regardless of success/failure)"
    - "shutdown() cancels all reconnect tasks and awaits their cancellation"
    - "The reconnect loop uses asyncio.sleep for backoff delays (cancellable via Task.cancel)"
    - "_ServerState.reconnect_task holds the asyncio.Task reference for each server's reconnect loop"
  artifacts:
    - path: "backend/app/services/mcp_client_manager.py"
      provides: "_reconnect_loop(), updated startup() with task spawning, updated shutdown() with task cancellation"
      contains: "_reconnect_loop"
  key_links:
    - from: "_reconnect_loop"
      to: "tool_registry.mark_server_unavailable"
      via: "called when server disconnect is detected"
      pattern: "mark_server_unavailable"
    - from: "_reconnect_loop"
      to: "tool_registry.mark_server_available"
      via: "called after successful reconnect"
      pattern: "mark_server_available"
---

<objective>
Add reconnect-with-exponential-backoff to `MCPClientManager` (D-P15-10..D-P15-12).

The reconnect architecture:
- `startup()` spawns one `asyncio.Task` per server that runs `_reconnect_loop(server_name)` as a background task.
- `_reconnect_loop()` monitors server state and:
  1. If server is `available=True` — check periodically (every 30s) whether the session is still alive (or rely on call_tool() exceptions to signal disconnection).
  2. If server is `available=False` — apply exponential backoff delays, call `_connect_server()`, update `fail_count`.
  3. After `_MAX_FAILURES` consecutive failures — log at ERROR, stop looping.
  4. On successful reconnect — reset `fail_count`, call `mark_server_available()`.
  5. `asyncio.CancelledError` is re-raised (enables clean shutdown).
- `shutdown()` cancels all tasks and awaits them.

This is a targeted additive patch to `mcp_client_manager.py` created in Plan 15-02. The reconnect loop only runs inside the lifespan context (started by `startup()`, cancelled by `shutdown()`).

Note on disconnect detection: MCP SDK's `call_tool()` raises an exception when the server process terminates. The executor closure in `_connect_server()` will surface this as an error return from `call_tool()`. For the reconnect loop, we use a simpler probe: `_reconnect_loop` starts the backoff cycle whenever `state.available` is False (set by the executor on connection failure).
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
</context>

<tasks>

<task id="1">
<name>Add _reconnect_loop async method to MCPClientManager</name>
<read_first>
- backend/app/services/mcp_client_manager.py (full file — understand existing _ServerState, _connect_server, _BACKOFF_DELAYS, _MAX_FAILURES)
- backend/app/services/tool_registry.py (mark_server_unavailable, mark_server_available signatures)
</read_first>
<action>
In `backend/app/services/mcp_client_manager.py`, add the `_reconnect_loop` async method to the `MCPClientManager` class.

Add this method after the `_connect_server` method but before `call_tool`:

```python
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
```

Also add a `_handle_tool_call_failure` method that can be called from `call_tool()` to mark server unavailable when a call fails due to connection error:

```python
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
```

Update `call_tool()` to call `_handle_tool_call_failure` on exception:

In the `call_tool()` method, update the `except Exception` block:
```python
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
```
</action>
<acceptance_criteria>
- `grep -n "def _reconnect_loop" backend/app/services/mcp_client_manager.py` returns a match
- `grep -n "_handle_tool_call_failure" backend/app/services/mcp_client_manager.py` returns at least 2 matches (definition + call in call_tool)
- `grep -n "asyncio.CancelledError" backend/app/services/mcp_client_manager.py` returns a match inside `_reconnect_loop`
- `grep -n "_BACKOFF_DELAYS\[" backend/app/services/mcp_client_manager.py` returns a match inside `_reconnect_loop`
- `grep -n "_MAX_FAILURES" backend/app/services/mcp_client_manager.py` returns at least 2 matches (definition + use in _reconnect_loop)
- `cd backend && source venv/bin/activate && python -c "from app.services.mcp_client_manager import MCPClientManager; import inspect; src = inspect.getsource(MCPClientManager._reconnect_loop); assert 'CancelledError' in src; assert '_BACKOFF_DELAYS' in src; print('PASS')"` prints `PASS`
- `cd backend && source venv/bin/activate && python -c "from app.main import app; print('OK')"` prints `OK`
</acceptance_criteria>
</task>

<task id="2">
<name>Update startup() to spawn _reconnect_loop task per server</name>
<read_first>
- backend/app/services/mcp_client_manager.py (startup() method — current implementation from 15-02)
</read_first>
<action>
In `backend/app/services/mcp_client_manager.py`, update the `startup()` method to spawn a `_reconnect_loop` task for each server after the initial `_connect_server()` call.

Replace the loop inside `startup()` where servers are connected:

After `await self._connect_server(state)`, add task spawning:

```python
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
```

Also update `shutdown()` to cancel and await all reconnect tasks. Find the shutdown method and update the server cleanup loop:

```python
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
        self._servers.clear()
        logger.info("mcp_client_manager: shutdown complete")
```
</action>
<acceptance_criteria>
- `grep -n "asyncio.create_task" backend/app/services/mcp_client_manager.py` returns a match inside `startup()` that calls `self._reconnect_loop`
- `grep -n "state.reconnect_task = asyncio.create_task" backend/app/services/mcp_client_manager.py` returns a match
- `grep -n "reconnect_task.cancel" backend/app/services/mcp_client_manager.py` returns a match inside `shutdown()`
- `grep -n "asyncio.wait_for" backend/app/services/mcp_client_manager.py` returns a match inside `shutdown()` (bounded cancellation wait)
- `cd backend && source venv/bin/activate && python -c "from app.main import app; print('OK')"` prints `OK`
</acceptance_criteria>
</task>

</tasks>

<verification>
Plan 15-04 is complete when:
1. `_reconnect_loop(server_name)` exists in `MCPClientManager` with backoff delays `[1,2,4,8,16,32]`
2. After `_MAX_FAILURES=5` failures, the loop logs ERROR and returns (stops retrying)
3. `asyncio.CancelledError` is re-raised in `_reconnect_loop` (clean cancellation)
4. `startup()` spawns one `asyncio.Task` per server after `_connect_server()` call
5. `shutdown()` cancels all tasks with a 5s timeout
6. `_handle_tool_call_failure()` marks server unavailable when `call_tool()` raises an exception
7. App import smoke test: `python -c "from app.main import app; print('OK')"` → `OK`
</verification>
