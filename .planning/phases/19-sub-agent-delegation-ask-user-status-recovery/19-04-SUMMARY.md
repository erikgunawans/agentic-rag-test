---
phase: 19-sub-agent-delegation-ask-user-status-recovery
plan: 04
subsystem: backend-service
tags: [python, tdd, tool-registry, sub-agent, sse, chat-loop, adapter-wrap, phase19]

# Dependency graph
requires:
  - phase: 19-02
    provides: "agent_runs_service.py — state-machine CRUD"
  - phase: 19-03
    provides: "run_sub_agent_loop async generator"
provides:
  - "_register_sub_agent_tools() in tool_service.py — task tool registered via adapter-wrap"
  - "task dispatch handler in run_deep_mode_loop — SSE forwarding, D-06 tagging, D-23 audit"
  - "tests/tool/test_task_tool.py — 8 integration tests (all passing)"
affects:
  - 19-05 (ask_user tool uses same adapter-wrap pattern; _register_sub_agent_tools will be extended)
  - 19-06 (agent_status SSE emission builds on the same run_deep_mode_loop dispatch loop)
  - 19-09 (end-to-end pytest covers task tool happy path)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "TDD RED/GREEN: 8 failing tests first, then tool registration + dispatch to pass"
    - "D-P13-01 adapter-wrap: _register_sub_agent_tools() appended below line 1647 (workspace tools end)"
    - "SHA-256 invariant: head -n 1283 tool_service.py stays cb63cf3e... throughout"
    - "module-level run_sub_agent_loop import in chat.py for test patchability"
    - "task dispatch intercepts BEFORE _dispatch_tool_deep — bypasses standard tool path"
    - "Sentinel executor pattern: _task_executor returns {'_task_dispatch': {...}}"
    - "D-06: tagged = {**evt, 'task_id': task_id} at wrapper boundary"
    - "D-12: _terminal_result with 'error' key -> task_error SSE + structured tool_output"
    - "D-21: parent_redaction_registry=registry passed to run_sub_agent_loop"
    - "D-23: log_action(action='task', resource_type='agent_runs') fire-and-forget"

key-files:
  created:
    - backend/tests/tool/__init__.py
    - backend/tests/tool/test_task_tool.py
  modified:
    - backend/app/services/tool_service.py
    - backend/app/routers/chat.py

key-decisions:
  - "module-level import of run_sub_agent_loop in chat.py (not lazy) — required for unittest.mock.patch to target 'app.routers.chat.run_sub_agent_loop'"
  - "task dispatch uses 'if func_name == task AND sub_agent_enabled' BEFORE 'elif func_name not in available_tool_names' — bypasses availability check entirely (task is not in TOOL_DEFINITIONS)"
  - "tr._REGISTRY used directly in tests (not make_active_set() which returns empty set by design)"
  - "log_action imported directly at chat.py module level — tests patch 'app.routers.chat.log_action'"
  - "audit_service note: chat.py uses `from app.services.audit_service import log_action` directly; test patches the name at chat module scope"

requirements-completed: [TASK-01, TASK-02, TASK-03, TASK-04, TASK-05, TASK-07, STATUS-04]

# Metrics
duration: ~35min
completed: 2026-05-03
---

# Phase 19 Plan 04: Task Tool End-to-End Wiring Summary

**task tool registered via adapter-wrap in tool_service.py and dispatched in run_deep_mode_loop with sub-agent SSE forwarding, D-06 event tagging, D-23 audit log, D-12 failure isolation — 8/8 tests green (TDD)**

## Performance

- **Duration:** ~35 min
- **Completed:** 2026-05-03
- **Tasks:** 3 (TDD RED + tool registration GREEN + chat.py dispatch GREEN)
- **Files created:** 2 / modified: 2

## Accomplishments

### Task 1 (RED): test_task_tool.py — 8 failing tests
`backend/tests/tool/test_task_tool.py` — 504 lines, 8 top-level test functions covering:
1. `test_task_tool_registered_when_flags_on` — dual-flag gating (both on = registered; either off = not registered)
2. `test_task_tool_schema_matches_d28` — D-28 verbatim schema (description required; context_files optional array)
3. `test_task_dispatch_emits_task_start_complete` — SSE event sequence with correct task_id propagation
4. `test_task_dispatch_forwards_nested_events_with_task_id` — D-06 nested event tagging
5. `test_task_dispatch_returns_structured_error_on_failure` — TASK-05/STATUS-04 failure isolation
6. `test_task_dispatch_persists_audit_log` — D-23 audit log with action='task', resource_type='agent_runs'
7. `test_task_dispatch_generates_server_side_uuid` — server-generated UUID (not LLM-controlled)
8. `test_task_not_registered_in_legacy_TOOL_DEFINITIONS` — D-P13-01 invariant

### Task 2 (GREEN): tool_service.py — task tool registration
Lines added to `backend/app/services/tool_service.py` (after line 1647):
- `_TASK_SCHEMA` — D-28 verbatim tool schema dict (lines 1650–1705)
- `_task_executor` — sentinel executor returning `{"_task_dispatch": {...}}` (lines 1708–1730)
- `_register_sub_agent_tools()` — dual-flag gated registration function (lines 1733–1760)
- `_register_sub_agent_tools()` call at module load

**D-P13-01 SHA-256 invariant preserved:** `head -n 1283 tool_service.py | shasum -a 256` = `cb63cf3e60d5f6380e2e41f63b1fe9122f58ab4648808b0f2114e452cd45ddb2` (unchanged before and after edit).

### Task 3 (GREEN): chat.py — task dispatch in run_deep_mode_loop
Lines added to `backend/app/routers/chat.py`:
- Module-level import: `from app.services.sub_agent_loop import run_sub_agent_loop` (line ~34)
- Task dispatch handler inside tool-call loop (~lines 1755–1800):
  - `if func_name == "task" and settings.sub_agent_enabled:` (intercepts before availability check)
  - `task_id = str(_uuid.uuid4())` — server-generated UUID
  - `log_action(action="task", resource_type="agent_runs", ...)` — D-23 audit
  - `task_start` SSE with task_id + description + context_files
  - `async for evt in sub_gen:` — forward events; tag non-terminal events with `task_id` (D-06)
  - `task_error` SSE on `_terminal_result` with `error` key (D-12)
  - `task_complete` SSE on success with `result` text
  - `parent_redaction_registry=registry` — D-21 parent registry shared

## Test Results

```
8 passed, 10 warnings in 2.26s
```

All 8 tests pass:
1. `test_task_tool_registered_when_flags_on` — PASSED
2. `test_task_tool_schema_matches_d28` — PASSED
3. `test_task_dispatch_emits_task_start_complete` — PASSED
4. `test_task_dispatch_forwards_nested_events_with_task_id` — PASSED
5. `test_task_dispatch_returns_structured_error_on_failure` — PASSED
6. `test_task_dispatch_persists_audit_log` — PASSED
7. `test_task_dispatch_generates_server_side_uuid` — PASSED
8. `test_task_not_registered_in_legacy_TOOL_DEFINITIONS` — PASSED

## Regression Verification

- `test_sub_agent_loop.py`: 21/21 pass (no regression)
- `test_deep_mode_chat_loop.py`: 23/23 pass (no regression)
- `python -c "from app.main import app; print('OK')"`: passes

## Invariants Confirmed

| Invariant | Status |
|-----------|--------|
| D-P13-01: first 1283 lines SHA-256 unchanged | CONFIRMED (cb63cf3e...) |
| task NOT in TOOL_DEFINITIONS | CONFIRMED (test 8 verifies) |
| D-06: nested events tagged with task_id | CONFIRMED (test 4 verifies) |
| D-12: failure isolation → structured error | CONFIRMED (test 5 verifies) |
| D-21: parent registry shared | CONFIRMED (parent_redaction_registry=registry in dispatch) |
| D-23: audit log on every dispatch | CONFIRMED (test 6 verifies) |
| D-30: dual-flag gating | CONFIRMED (test 1 verifies) |

## Task Commits

1. **Task 1: TDD RED (8 failing tests)** — `3b259ac` (test)
2. **Task 2: Register task tool via adapter-wrap** — `4e3a15d` (feat)
3. **Task 3: Implement task dispatch in chat.py** — `e3b6fd6` (feat)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `make_active_set()` returns empty set — tests need `_REGISTRY` directly**
- **Found during:** Task 2 (GREEN phase test run)
- **Issue:** Tests used `tr.make_active_set()` to check if task was registered. `make_active_set()` returns a fresh empty set per its design (per-request active-set storage, not a query of registered tools). Calling it always returns `set()` regardless of what's in `_REGISTRY`.
- **Fix:** Changed tests 1 and 2 to check `tr._REGISTRY` directly instead of `tr.make_active_set()`.
- **Files modified:** `backend/tests/tool/test_task_tool.py`

**2. [Rule 3 - Blocking] run_sub_agent_loop lazy import not patchable by unittest.mock**
- **Found during:** Task 3 (GREEN phase test run)
- **Issue:** Initial implementation imported `run_sub_agent_loop` lazily inside the `if func_name == "task":` block. `unittest.mock.patch("app.routers.chat.run_sub_agent_loop")` requires a module-level attribute to exist on `app.routers.chat`. Lazy local imports inside a function scope create local names, not module attributes.
- **Fix:** Moved `from app.services.sub_agent_loop import run_sub_agent_loop` to module-level in `chat.py` (alongside other existing module-level imports). This creates the patchable attribute and has zero runtime cost when `sub_agent_enabled=False` (the branch never executes per D-17).
- **Files modified:** `backend/app/routers/chat.py`

**3. [Rule 1 - Bug] `get_supabase_authed_client` not a module-level name in chat.py**
- **Found during:** Task 3 (initial test patch setup)
- **Issue:** Test was patching `app.routers.chat.get_supabase_authed_client` but chat.py only imports `get_supabase_client` (not authed). The authed client is used inside redaction code, not at the chat.py module level.
- **Fix:** Removed the invalid patch. Since tests pass `pii_redaction_enabled=False`, `redaction_on=False`, and `ConversationRegistry.load` is never called.
- **Files modified:** `backend/tests/tool/test_task_tool.py`

**Total deviations:** 3 auto-fixed (Rules 1+3+1)
**Impact:** No scope change. Behavior unchanged; tests now correctly reflect the actual module structure.

## Known Stubs

None — `_task_executor` returns a sentinel dict `{"_task_dispatch": {...}}`. This is intentional: the actual SSE forwarding is in chat.py's task dispatch handler, which is fully implemented. The executor exists only to satisfy tool_registry.register(executor=...) requirement; the chat.py branch intercepts the call before the executor is ever invoked in normal flow.

## Threat Surface Scan

No new network endpoints introduced. The task dispatch:
- Uses existing `log_action` (existing audit surface)
- Calls `run_sub_agent_loop` (existing service, Phase 19 plan 19-03)
- Emits SSE events through the existing generator (existing surface)

Threats from plan T-19-23, T-19-12, T-19-30 — all mitigated and test-verified.

## Self-Check: PASSED

- `backend/tests/tool/__init__.py` — FOUND
- `backend/tests/tool/test_task_tool.py` — FOUND
- `backend/app/services/tool_service.py` has `_register_sub_agent_tools` — FOUND
- `backend/app/routers/chat.py` has `if func_name == "task"` — FOUND
- Commit `3b259ac` (TDD RED) — FOUND
- Commit `4e3a15d` (tool registration) — FOUND
- Commit `e3b6fd6` (chat.py dispatch) — FOUND
- 8/8 tests pass — CONFIRMED
- SHA-256 invariant preserved — CONFIRMED

---
*Phase: 19-sub-agent-delegation-ask-user-status-recovery*
*Completed: 2026-05-03*
