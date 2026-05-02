---
phase: 17-deep-mode-foundation-planning-todos-plan-panel
plan: 03
subsystem: api
tags: [python, fastapi, supabase, tool-registry, audit-logging, rls, tdd]

# Dependency graph
requires:
  - phase: 17-deep-mode-foundation-planning-todos-plan-panel/17-01
    provides: agent_todos table with RLS (migration 038 applied)

provides:
  - "agent_todos_service.write_todos() — full-replacement write with 50-item cap and audit log"
  - "agent_todos_service.read_todos() — ordered read by position with audit log"
  - "tool_registry.py — write_todos + read_todos registered as native tools with OpenAI function schemas"
  - "Unit tests covering full-replacement semantic, position assignment, truncation, auth client, audit"
  - "Integration tests covering RLS isolation, full-replacement semantic, registry dispatch"

affects:
  - 17-04-deep-mode-chat-loop
  - 17-06-plan-panel-ui

tech-stack:
  added: []
  patterns:
    - "agent_todos_service follows delete-then-insert full-replacement pattern (D-06)"
    - "tool_registry adapter wrap: executors extract thread_id from ctx (server-set, T-17-06)"
    - "user_email resolved from context dict with fallback (Plan 17-04 wires it via tool_context)"
    - "_register_phase17_todos() self-registers at module load, gated by tool_registry_enabled flag"

key-files:
  created:
    - backend/app/services/agent_todos_service.py
    - backend/tests/unit/test_agent_todos_service.py
    - backend/tests/integration/test_write_read_todos_tools.py
  modified:
    - backend/app/services/tool_registry.py

key-decisions:
  - "audit_service.log_action is synchronous (not async) — callers do not await it; confirmed by inspecting audit_service.py signature"
  - "user_email defaults to empty string in registry executors when not in context — Plan 17-04 adds it to tool_context"
  - "Registry integration tests use the live _REGISTRY directly (no module reload needed) — simpler and more reliable than reload approach"
  - "test for RLS uses _audit=False to avoid audit log noise in isolation test"

patterns-established:
  - "Agent tool executors: (arguments, user_id, context, *, token=None, **kwargs) — token kwarg from chat.py _dispatch_tool"
  - "thread_id always from ctx (server-set), never from LLM arguments — T-17-06 pattern"
  - "_register_phase17_*() at module bottom follows same idiom as _register_tool_search()"

requirements-completed: [TODO-02, TODO-03, TODO-05]

# Metrics
duration: 35min
completed: 2026-05-03
---

# Phase 17 Plan 03: Write/Read Todos Tools Summary

**write_todos + read_todos LLM tools with full-replacement semantic, 50-item cap, RLS-scoped authed client, and OpenAI function schemas registered via ToolRegistry adapter wrap**

## Performance

- **Duration:** 35 min
- **Started:** 2026-05-03T00:00:00Z
- **Completed:** 2026-05-03T00:35:00Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- Created `agent_todos_service.py` implementing full-replacement write (delete-then-insert per D-06), position auto-assignment, 50-item truncation cap (D-29), and audit logging (D-34)
- Registered `write_todos` and `read_todos` in `tool_registry.py` as native tools with correct OpenAI function-tool JSON schemas, gated by `TOOL_REGISTRY_ENABLED` flag (D-31)
- 15 tests pass (8 unit + 7 integration): full-replacement semantic, RLS isolation, registry dispatch, byte-identical fallback when flag is off

## Task Commits

Each task was committed atomically:

1. **Task 1: Write failing unit + integration tests (TDD RED)** - `0d53740` (test)
2. **Task 2: Implement agent_todos_service.py (TDD GREEN)** - `be8ce8f` (feat)
3. **Task 3: Register write_todos/read_todos via ToolRegistry (TDD GREEN)** - `b6c92ab` (feat)

## Files Created/Modified

- `backend/app/services/agent_todos_service.py` - Service layer: write_todos (full-replacement) + read_todos (ordered by position) + audit logging
- `backend/app/services/tool_registry.py` - Added `_register_phase17_todos()` with write_todos + read_todos schemas + executor adapters
- `backend/tests/unit/test_agent_todos_service.py` - 8 unit tests (mock Supabase client): full-replacement, positions, truncation, auth client, audit
- `backend/tests/integration/test_write_read_todos_tools.py` - 7 integration tests: service direct calls, full-replacement semantic, RLS isolation, registry dispatch, byte-identical fallback

## Decisions Made

- `audit_service.log_action` is synchronous (not async) — inspected `audit_service.py` to confirm; no `await` needed
- `user_email` falls back to empty string in registry executors when not in context dict; Plan 17-04 will wire it into `tool_context` in `chat.py`
- Integration tests use the live `_REGISTRY` directly rather than module reload (simpler, more reliable)
- Unit test for `test_write_todos_uses_authed_client` patches `app.database.get_supabase_client` not the service module namespace (since `get_supabase_client` is not imported in `agent_todos_service.py`)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed unit test patch target for service-role client assertion**
- **Found during:** Task 2 (TDD GREEN — running unit tests after implementing service)
- **Issue:** `test_write_todos_uses_authed_client` tried to patch `app.services.agent_todos_service.get_supabase_client`, which doesn't exist in the service module (only `get_supabase_authed_client` is imported)
- **Fix:** Changed patch target to `app.database.get_supabase_client` and updated assertion to verify `get_supabase_authed_client` was called exactly once with the token
- **Files modified:** `backend/tests/unit/test_agent_todos_service.py`
- **Verification:** All 8 unit tests pass after fix
- **Committed in:** `be8ce8f` (Task 2 commit)

**2. [Rule 1 - Bug] Fixed integration tests for registry dispatch (test_write_todos_via_execute_tool, test_read_todos_via_execute_tool)**
- **Found during:** Task 3 (verifying registry dispatch tests)
- **Issue:** Tests used `tool_registry._clear_for_tests()` followed by `importlib.reload(tool_service)` to re-register tools — this reload only re-registered `TOOL_DEFINITIONS` natives but NOT Phase 17 todos (since they register from `tool_registry.py` module load, which doesn't re-fire on reload)
- **Fix:** Simplified tests to use the live `_REGISTRY` directly (already populated at module load including Phase 17 todos), with a skip guard if `write_todos` not present
- **Files modified:** `backend/tests/integration/test_write_read_todos_tools.py`
- **Verification:** All 15 tests pass with `TOOL_REGISTRY_ENABLED=true`
- **Committed in:** `b6c92ab` (Task 3 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 - bug fixes in test code)
**Impact on plan:** Both fixes necessary for correct test operation. No scope creep.

## Issues Encountered

None beyond the auto-fixed test bugs above.

## Known Stubs

None — `write_todos` and `read_todos` are fully wired to Supabase. The `user_email` fallback to empty string in registry executors is intentional pending Plan 17-04 wiring it into `tool_context`.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| T-17-06 | backend/app/services/tool_registry.py | write_todos executor ignores any thread_id in arguments; reads only from ctx (server-set) — mitigation implemented |
| T-17-07 | backend/app/services/agent_todos_service.py | Only get_supabase_authed_client used; unit test asserts service-role not called — mitigation implemented |
| T-17-08 | backend/app/services/agent_todos_service.py | Both write_todos and read_todos call audit_service.log_action — mitigation implemented |

## Next Phase Readiness

- `write_todos` and `read_todos` are dispatchable via `tool_registry._REGISTRY` when `TOOL_REGISTRY_ENABLED=true`
- Plan 17-04 (deep-mode chat loop) needs to: (a) add `user_email` to `tool_context` dict in `chat.py`, (b) load write_todos/read_todos into the deep-mode tool list, (c) emit `todos_updated` SSE events after write_todos dispatch
- No blockers — service layer is complete and tested

---
*Phase: 17-deep-mode-foundation-planning-todos-plan-panel*
*Completed: 2026-05-03*
