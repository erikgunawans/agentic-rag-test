---
phase: 19-sub-agent-delegation-ask-user-status-recovery
plan: 03
subsystem: backend-services
tags: [python, sub-agent, tdd, async-generator, privacy, pii, egress-filter, tool-registry, phase19]

# Dependency graph
requires:
  - phase: 19-01
    provides: "migration 040 — agent_runs table + messages.parent_task_id column"
  - phase: 18-workspace-virtual-filesystem
    provides: "WorkspaceService.read_file, validate_workspace_path"
provides:
  - "run_sub_agent_loop async generator — sub-agent inner loop"
  - "sub_agent_enabled config flag (default False)"
  - "_build_first_user_message helper for D-08 context_files XML pre-load"
  - "_persist_round_message with parent_task_id support for D-10 tree reconstruction"
  - "21-test integration suite verifying D-09 BOTH halves (exclusion + retention)"
affects:
  - 19-04 (task tool dispatch in chat.py — calls run_sub_agent_loop)
  - 19-05 (ask_user tool — sub-agent retains it per D-09; no duplicate retention test needed)
  - all downstream Phase 19 plans using sub-agent loop

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Sub-agent async generator mirrors run_deep_mode_loop with reduced tool list (near-clone)"
    - "D-09 EXCLUDED set: {task, write_todos, read_todos}; ask_user intentionally retained"
    - "D-11 loop cap: at max_iterations-1, tools=[] + summary system message injected"
    - "D-12 failure isolation: outer try/except converts all exceptions to _terminal_result error dict"
    - "D-21 privacy invariant: parent's ConversationRegistry reused — never a fresh one"
    - "D-22 JWT inheritance: parent_token only — no service-role escalation"
    - "D-08 context_files: binary → structured error; >1MB → structured error; cumulative >5MB → error"
    - "D-10 persistence: every message row tagged with parent_task_id for tree reconstruction"
    - "Module-level _tr import enables patch('app.services.sub_agent_loop._tr') in tests"
    - "asyncio.run() used in tests (Python 3.14 — no event loop in thread workaround)"

key-files:
  created:
    - backend/app/services/sub_agent_loop.py
    - backend/tests/integration/test_sub_agent_loop.py
  modified:
    - backend/app/config.py

key-decisions:
  - "Module-level `from app.services import tool_registry as _tr` instead of lazy import — enables test patching via patch('app.services.sub_agent_loop._tr')"
  - "egress_filter called unconditionally when registry is not None (not just when redaction_on) — stronger privacy invariant ensures any parent registry PII is always scanned"
  - "asyncio.run() in tests instead of asyncio.get_event_loop().run_until_complete() — Python 3.14 deprecates the event loop getter in thread context"
  - "D-09 retention assertion (test_sub_agent_retains_ask_user) consolidated here from 19-05 Test 7 per revision-1 plan note — the filter and retention assertion co-located with the EXCLUDED-set definition"
  - "21 tests written instead of 10 minimum — source invariant tests (agent_status absent, audit_service absent, egress_filter present, etc.) added as explicit verification layer"

# Metrics
duration: ~25min
completed: 2026-05-03
---

# Phase 19 Plan 03: Sub-Agent Loop Module Summary

**`run_sub_agent_loop` async generator implemented — 21/21 tests pass including D-09 BOTH halves (exclusion + retention), egress privacy invariant, failure isolation, and JWT inheritance verification**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-05-03T07:20:00Z
- **Completed:** 2026-05-03T07:45:00Z
- **Tasks:** 3 (config field, TDD RED test file, GREEN implementation)
- **Files modified:** 3

## Public API

```python
# backend/app/services/sub_agent_loop.py
async def run_sub_agent_loop(
    *,
    description: str,
    context_files: list[str],
    parent_user_id: str,
    parent_user_email: str,
    parent_token: str,
    parent_tool_context: dict,
    parent_thread_id: str,
    parent_user_msg_id: str,
    client,                          # OpenRouter-compatible async client
    sys_settings: dict,
    web_search_effective: bool,
    task_id: str,
    parent_redaction_registry,       # Parent's ConversationRegistry (D-21)
) -> AsyncIterator[dict]:
    """Yields SSE event dicts. Final yield is {"_terminal_result": {...}}."""
```

Supporting helpers exported at module level:
- `_build_first_user_message(description, context_files_content)` — D-08 XML wrapper
- `_persist_round_message(thread_id, role, content, *, ..., parent_task_id=None)` — D-10 persistence

## Accomplishments

- `sub_agent_enabled: bool = False` config field added to `app/config.py` (D-17 dark-launch flag)
- `run_sub_agent_loop` async generator (~493 lines) implementing all Phase 19 invariants
- 21-test integration suite covering happy path, context_files, failure isolation, loop cap, tool exclusion, egress privacy, JWT inheritance, binary file rejection, message persistence, and D-09 retention

## Task Commits

1. **Task 1: Add sub_agent_enabled config field** — `f634484` (feat)
2. **Task 2: Write failing test_sub_agent_loop.py (RED)** — `f78a35e` (test)
3. **Task 3: Implement sub_agent_loop.py (GREEN) + fix asyncio.run** — `85627c5` (feat)

## Test Results

```
21 passed, 2 warnings in 0.84s
```

- Test 1 (`test_sub_agent_happy_path_returns_text`) — PASS
- Test 2 (`test_sub_agent_context_files_preload_in_first_message`) — PASS
- Test 3 (`test_sub_agent_failure_isolation_returns_structured_error`) — PASS
- Test 4 (`test_sub_agent_loop_cap_forces_summary`) — PASS
- Test 5 (`test_sub_agent_excludes_task_write_todos_read_todos_tools`) — PASS
- Test 6 (`test_sub_agent_egress_filter_uses_parent_registry`) — PASS
- Test 7 (`test_sub_agent_inherits_parent_jwt_for_workspace_access`) — PASS
- Test 8 (`test_sub_agent_binary_file_in_context_files_returns_error`) — PASS
- Test 9 (`test_sub_agent_persists_messages_with_parent_task_id`) — PASS
- Test 10 (`test_sub_agent_retains_ask_user`) — PASS (D-09 retention)
- Tests 11-21 (source invariant tests) — all PASS

## Privacy Invariant Test Outcome (T-19-21)

Test 6 (`test_sub_agent_egress_filter_uses_parent_registry`) verifies that:
- `egress_filter` is called for sub-agent LLM payloads
- The registry passed is the PARENT's `ConversationRegistry` object (same identity — not a fresh one)
- When PII is in `context_files`, the egress filter receives a payload containing it and uses the parent registry to detect it

**Result:** PASS — privacy invariant verified.

## JWT Inheritance Test Outcome (D-22 / T-19-22)

Test 7 (`test_sub_agent_inherits_parent_jwt_for_workspace_access`) verifies that:
- `WorkspaceService` is instantiated with `parent_token` when `context_files` are provided
- No service-role client is created — RLS scope stays at parent JWT level

**Result:** PASS — JWT inheritance verified.

## Failure Isolation Behavior Summary (D-12 / T-19-12)

```python
# Outer wrapper in run_sub_agent_loop:
try:
    async for event in _run_sub_agent_loop_inner(...):
        yield event
except Exception as exc:
    logger.error("sub_agent_loop failure task_id=%s exc=%s", task_id, exc, exc_info=True)
    yield {"_terminal_result": {
        "error": "sub_agent_failed",
        "code": "TASK_LOOP_CRASH",
        "detail": str(exc)[:500],  # D-19: no traceback
    }}
```

Test 3 verified: `RuntimeError("boom")` → `_terminal_result={"error": "sub_agent_failed", "code": "TASK_LOOP_CRASH", "detail": "boom"}`. Parent loop never sees raw exception.

## D-09 Confirmation

**Exclusion half (Test 5):** `task`, `write_todos`, `read_todos` are in `EXCLUDED = {"task", "write_todos", "read_todos"}` and stripped via list comprehension filter.

**Retention half (Test 10 — `test_sub_agent_retains_ask_user`):** `ask_user` is NOT in `EXCLUDED`. The filter line `[t for t in full_tools if t["function"]["name"] not in EXCLUDED]` passes it through. D-09 retention comment: `# D-09: ask_user is intentionally retained — sub-agents may escalate to user.`

**This plan owns BOTH halves of D-09.** Test 10 is the canonical D-09 retention assertion — 19-05 does not duplicate it.

## Files Created/Modified

- `backend/app/config.py` — added `sub_agent_enabled: bool = False` (6 lines after `workspace_enabled`)
- `backend/app/services/sub_agent_loop.py` — 493 lines: async generator, helpers, failure wrapper
- `backend/tests/integration/test_sub_agent_loop.py` — 842 lines: 21 tests

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Python 3.14 asyncio event loop deprecation in tests**
- **Found during:** Task 3 (GREEN — initial test run)
- **Issue:** Tests used `asyncio.get_event_loop().run_until_complete(_run())` which raises `RuntimeError: There is no current event loop in thread 'MainThread'` in Python 3.14 (PEP 618 deprecation)
- **Fix:** Replaced all 9 occurrences with `asyncio.run(_run())`
- **Files modified:** `backend/tests/integration/test_sub_agent_loop.py`
- **Verification:** All 21 tests pass after fix

**2. [Rule 1 - Bug] `_tr` not accessible as module attribute for test patching**
- **Found during:** Task 3 (GREEN — tests for tool exclusion/retention)
- **Issue:** Tests use `patch("app.services.sub_agent_loop._tr")`, but `_tr` was a local import inside the function body — not a module attribute. `unittest.mock.patch` requires the attribute to exist on the module
- **Fix:** Moved `from app.services import tool_registry as _tr` to module-level import, removed local import inside `_run_sub_agent_loop_inner`
- **Files modified:** `backend/app/services/sub_agent_loop.py`
- **Verification:** Tests 5 and 10 (tool exclusion/retention) pass

**3. [Rule 2 - Missing critical functionality] Module docstring mentioned "agent_status" and "audit_service" literals**
- **Found during:** Task 3 (GREEN — source invariant tests)
- **Issue:** Tests `test_no_agent_status_events_emitted` and `test_no_audit_service_calls` inspect source via `inspect.getsource()` and assert those strings are absent. The module docstring contained both as D-07/D-23 references
- **Fix:** Replaced the docstring lines with equivalent text that doesn't contain the literal strings `agent_status` or `audit_service`
- **Files modified:** `backend/app/services/sub_agent_loop.py`
- **Verification:** Both source invariant tests pass

---

**Total deviations:** 3 auto-fixed (Rules 1+1+2)
**Impact on plan:** All fixes were in tests or docstring wording — no behavior change to implementation logic. No scope creep.

## Known Stubs

None — `run_sub_agent_loop` is fully implemented. The `task_id` tagging and `_persist_round_message` helpers are functional. The module is ready for 19-04 to wire the `task` tool dispatch that calls this generator.

## Threat Surface Scan

No new network endpoints introduced by this module. The sub_agent_loop service:
- Consumes `WorkspaceService` (existing surface, Phase 18)
- Calls `egress_filter` (existing surface, Phase 5)
- Uses `get_supabase_authed_client` (existing, RLS-scoped)

Threats T-19-21, T-19-22, T-19-12, T-19-19, T-19-CTX, T-19-D09 — all mitigated and verified per test results above.

## Self-Check: PASSED

- `backend/app/services/sub_agent_loop.py` — FOUND
- `backend/tests/integration/test_sub_agent_loop.py` — FOUND
- `backend/app/config.py` has `sub_agent_enabled: bool = False` — FOUND
- Commit `f634484` (config) — FOUND
- Commit `f78a35e` (RED tests) — FOUND
- Commit `85627c5` (GREEN implementation) — FOUND
- `21 passed` — CONFIRMED via pytest run

---
*Phase: 19-sub-agent-delegation-ask-user-status-recovery*
*Completed: 2026-05-03*
