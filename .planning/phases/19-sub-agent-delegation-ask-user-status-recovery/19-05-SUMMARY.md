---
phase: 19-sub-agent-delegation-ask-user-status-recovery
plan: 05
subsystem: backend-service
tags: [python, tdd, tool-registry, ask_user, pause-resume, sse, chat-loop, adapter-wrap, phase19]

# Dependency graph
requires:
  - phase: 19-02
    provides: "agent_runs_service.py — state-machine CRUD (start_run, set_pending_question, get_active_run, transition_status)"
  - phase: 19-04
    provides: "_register_sub_agent_tools() foundation + task dispatch handler pattern"
provides:
  - "_ASK_USER_SCHEMA + _ask_user_executor appended to tool_service.py; _register_sub_agent_tools updated to also register ask_user"
  - "Resume-detection branch in stream_chat — detects waiting_for_user run, transitions to working, re-enters run_deep_mode_loop with resume kwargs"
  - "ask_user dispatch handler in run_deep_mode_loop — canonical Site B owner of agent_status='waiting_for_user' (D-16); calls set_pending_question, emits SSE, closes loop (D-01)"
  - "run_deep_mode_loop resume injection — injects ask_user tool_result verbatim into loop_messages (D-15)"
  - "tests/tool/test_ask_user_tool.py — 6 integration tests (all passing)"
  - "tests/integration/test_chat_resume_flow.py — 6 integration tests (all passing)"
affects:
  - 19-06 (agent_status SSE Site B ownership documented here; 19-06 must NOT add a second emission)
  - 19-09 (end-to-end pytest covers the ask_user pause/resume flow)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "TDD GREEN: all 12 tests (6 tool + 6 integration) pass on first run after implementation"
    - "D-P13-01 adapter-wrap: ask_user registered in _register_sub_agent_tools() below line 1283 boundary"
    - "SHA-256 invariant: head -n 1283 tool_service.py stays cb63cf3e... unchanged"
    - "Sentinel executor: _ask_user_executor returns {'_ask_user_pause': True, 'question': ...}"
    - "Site B canonical owner: exactly 1 yield of agent_status='waiting_for_user' in chat.py (line ~1898)"
    - "Resume injection: synthetic ask_user tool_call + tool_result appended to loop_messages (D-04/D-15)"
    - "Module-level agent_runs_service import in chat.py for test patchability"

key-files:
  created: []
  modified:
    - backend/app/services/tool_service.py
    - backend/app/routers/chat.py

key-decisions:
  - "ask_user dispatch handler uses 'if func_name == ask_user' BEFORE 'elif func_name == task' — ask_user intercepts first, returns immediately (D-01)"
  - "Resume injection appends a synthetic assistant+tool message pair to loop_messages with a sentinel tool_call_id — LLM sees the full context as if the ask_user round had completed normally"
  - "agent_status{working} emitted at resume injection point (before loop starts) so frontend shows active state immediately"
  - "stream_chat resume branch rebuilds full context (history, sys_settings, web_search) to avoid stale data from the paused session"
  - "audit_service.log_action uses 'details=' kwarg (not 'metadata=') to match the existing log_action signature in chat.py"

requirements-completed: [ASK-01, ASK-02, ASK-03, ASK-04]

# Metrics
duration: ~25min
completed: 2026-05-03
---

# Phase 19 Plan 05: ask_user Tool End-to-End Wiring (Pause + Resume) Summary

**ask_user registered via adapter-wrap, pause path emits canonical Site B agent_status + ask_user SSE then closes generator, resume branch in stream_chat detects waiting_for_user run and re-enters run_deep_mode_loop with verbatim tool_result injection — 12/12 tests green (TDD)**

## Performance

- **Duration:** ~25 min
- **Completed:** 2026-05-03
- **Tasks:** 2 (Task 2 RED was already done in prior session; Task 3 GREEN + Task 4 SUMMARY)
- **Files created:** 0 / modified: 2

## Accomplishments

### Task 2 (continuation from prior session)
Tests were already committed at `6ef047f` (RED gate):
- `test_ask_user_tool.py` — 6 tests (RED)
- `test_chat_resume_flow.py` — 6 tests (RED)

### Task 3 (GREEN): tool_service.py — ask_user registration

Lines appended to `backend/app/services/tool_service.py` (after line 1760):
- `_ASK_USER_SCHEMA` — D-29 verbatim tool schema dict
- `_ask_user_executor` — sentinel executor returning `{"_ask_user_pause": True, "question": ...}`
- `_register_sub_agent_tools()` updated to also call `tool_registry.register(name="ask_user", ...)`

**D-P13-01 SHA-256 invariant preserved:** `head -n 1283 tool_service.py | shasum -a 256` = `cb63cf3e60d5f6380e2e41f63b1fe9122f58ab4648808b0f2114e452cd45ddb2` (unchanged).

### Task 3 (GREEN): chat.py — resume branch + ask_user dispatch

Lines added to `backend/app/routers/chat.py`:

**Module-level import:**
- `from app.services import agent_runs_service` — enables `unittest.mock.patch("app.routers.chat.agent_runs_service")`

**Resume-detection branch in `stream_chat`** (~lines 267-338):
- Gated by `settings.sub_agent_enabled AND settings.deep_mode_enabled` (D-17)
- Calls `agent_runs_service.get_active_run(thread_id, user["token"])`
- If `status == "waiting_for_user"`: calls `transition_status(new_status="working")`, rebuilds full context, returns `StreamingResponse(run_deep_mode_loop(..., resume_run_id=..., resume_tool_result=body.message, resume_round_index=last_round_index+1))`

**Extended `run_deep_mode_loop` signature** (3 new optional kwargs):
- `resume_run_id: str | None = None`
- `resume_tool_result: str | None = None`
- `resume_round_index: int = 0`

**Resume injection** (after loop_messages built):
- Emits `agent_status{working}` SSE immediately
- Appends synthetic `assistant` (tool_call) + `tool` (tool_result=body.message verbatim) to `loop_messages` (D-15)

**ask_user dispatch handler** (~lines 1863-1902):
- Intercepts `if func_name == "ask_user"` BEFORE `elif func_name == "task"`
- Calls `log_action(action="ask_user", resource_type="agent_runs")` (D-23)
- Calls `agent_runs_service.get_active_run` → `start_run` if None → `set_pending_question`
- Yields `agent_status{waiting_for_user, detail:question}` + `ask_user{question}` + `delta{done:True}`
- Returns immediately (closes generator — D-01)

## Test Results

```
tests/tool/test_ask_user_tool.py — 6 passed
tests/integration/test_chat_resume_flow.py — 6 passed
======================== 12 passed, 5 warnings in 1.72s ========================
```

**Regression:** `test_task_tool.py` (8) + `test_deep_mode_chat_loop.py` (23) = 31 passed.

All tests pass:
1. `test_ask_user_registered_when_flags_on` — PASSED (dual-flag gating)
2. `test_ask_user_schema_matches_d29` — PASSED (schema verbatim D-29)
3. `test_ask_user_pause_emits_sse` — PASSED (pause flow SSE sequence)
4. `test_ask_user_dispatch_persists_audit_log` — PASSED (D-23 audit log)
5. `test_ask_user_pause_does_not_persist_messages_row` — PASSED (D-15)
6. `test_ask_user_not_in_legacy_TOOL_DEFINITIONS` — PASSED (D-P13-01)
7. `test_chat_resume_after_pause_routes_message_as_tool_result` — PASSED (two-request flow)
8. `test_resume_branch_short_circuits_when_sub_agent_disabled` — PASSED (D-17)
9. `test_resume_branch_short_circuits_when_no_active_run` — PASSED (D-04)
10. `test_resume_ignores_deep_mode_flag_in_body` — PASSED (D-04)
11. `test_offtopic_reply_passed_through_verbatim` — PASSED (D-15)
12. `test_resume_increments_last_round_index` — PASSED (D-04)

## Invariants Confirmed

| Invariant | Status |
|-----------|--------|
| D-P13-01: first 1283 lines SHA-256 unchanged | CONFIRMED (`cb63cf3e...`) |
| ask_user NOT in TOOL_DEFINITIONS | CONFIRMED (test 6 verifies) |
| D-01: ask_user dispatch closes generator (return after yield) | CONFIRMED (test 3 verifies) |
| D-15: tool_result passed verbatim, no filter | CONFIRMED (test 11 verifies) |
| D-16: exactly 1 Site B agent_status emission in chat.py | CONFIRMED (grep shows 1 yield) |
| D-17: resume branch gated by sub_agent_enabled AND deep_mode_enabled | CONFIRMED (tests 2, 8 verify) |
| D-23: audit log on every ask_user dispatch | CONFIRMED (test 4 verifies) |
| D-04: resume detects waiting_for_user run at stream_chat entry | CONFIRMED (test 7 verifies) |

## Task Commits

1. **Task 1+2 RED (from prior session):** `6ef047f` — 12 failing tests
2. **Task 3 GREEN (ask_user + resume):** `4aed788` — feat(19-05): wire ask_user tool

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `details=` kwarg instead of `metadata=`**
- **Found during:** Task 3 (GREEN, writing ask_user dispatch handler)
- **Issue:** The plan's pseudocode used `metadata={"question": ...}` for `log_action`, but the existing `log_action` signature in chat.py (and how it was called in the task dispatch handler added in 19-04) uses `details=`. Using `metadata=` would silently fail or raise a TypeError.
- **Fix:** Used `details={"question": question[:200]}` consistent with the 19-04 pattern.
- **Files modified:** `backend/app/routers/chat.py`

**Total deviations:** 1 auto-fixed (Rule 1)
**Impact:** No scope change. Behavior correct; log_action called with the right kwarg name.

## Known Stubs

None — ask_user is fully wired end-to-end. The sentinel `_ask_user_executor` is intentional (same pattern as `_task_executor` from 19-04): the actual SSE dispatch happens in chat.py before the executor is ever invoked.

## Threat Surface Scan

No new network endpoints. The ask_user flow:
- Writes to `agent_runs` via existing RLS-scoped service (T-19-RESUME — two-layer auth guard: RLS + thread ownership validation before resume branch)
- Emits SSE through existing generator surface
- Audit via existing `log_action` (T-19-23 — mitigated)
- Race condition T-19-RACE: `transition_status` delegates to service-layer UPDATE; only one of two racing requests will see the row in `waiting_for_user` state — accepted per D-31 carryover

## Self-Check: PASSED

- `backend/app/services/tool_service.py` has `_ASK_USER_SCHEMA` — FOUND
- `backend/app/services/tool_service.py` has `_ask_user_executor` — FOUND
- `backend/app/routers/chat.py` has `agent_runs_service` module-level import — FOUND
- `backend/app/routers/chat.py` has `if func_name == "ask_user"` — FOUND
- `backend/app/routers/chat.py` has `agent_runs_service.set_pending_question` — FOUND
- `backend/app/routers/chat.py` has `agent_runs_service.get_active_run` (2 locations) — FOUND
- `backend/app/routers/chat.py` has `resume_run_id` in run_deep_mode_loop signature — FOUND
- `backend/app/routers/chat.py` has `last_round_index` in stream_chat — FOUND
- SHA-256 invariant check: `INVARIANT OK`
- Site B: exactly 1 yield of `agent_status='waiting_for_user'` in chat.py — CONFIRMED
- Commit `6ef047f` (RED) — FOUND (prior session)
- Commit `4aed788` (GREEN) — FOUND
- 12/12 tests pass — CONFIRMED

---
*Phase: 19-sub-agent-delegation-ask-user-status-recovery*
*Completed: 2026-05-03*
