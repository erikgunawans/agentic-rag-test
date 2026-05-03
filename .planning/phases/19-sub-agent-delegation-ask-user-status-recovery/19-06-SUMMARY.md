---
phase: 19-sub-agent-delegation-ask-user-status-recovery
plan: 06
subsystem: backend-service
tags: [python, tdd, sse, chat-loop, agent-status, agent-runs, lifecycle, phase19]

# Dependency graph
requires:
  - phase: 19-02
    provides: "agent_runs_service.py — start_run, complete, error CRUD"
  - phase: 19-04
    provides: "task tool dispatch in run_deep_mode_loop"
  - phase: 19-05
    provides: "ask_user dispatch handler — canonical Site B owner (waiting_for_user)"
provides:
  - "Site A agent_status{working} + agent_runs.start_run at loop entry (chat.py L1735-1751)"
  - "Site C agent_status{complete} + agent_runs.complete before final done (chat.py L2214-2217)"
  - "Site D agent_status{error, detail} + agent_runs.error on uncaught exception (chat.py L2113-2130)"
  - "All three sites gated by settings.sub_agent_enabled (D-17 byte-identical fallback)"
  - "tests/integration/test_agent_status_emission.py — 8 integration tests (all passing)"
affects:
  - 19-07 (frontend reads agent_status SSE to drive AgentStatusChip)
  - 19-09 (end-to-end pytest covers full state-machine transitions)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "TDD RED/GREEN: 7 tests fail (RED), then all 8 pass after implementation (GREEN)"
    - "Site A: if settings.sub_agent_enabled → start_run + yield working (L1735)"
    - "Site B: canonical owner 19-05 ask_user handler (L1914) — no second emission here"
    - "Site C: if settings.sub_agent_enabled → complete + yield complete before done (L2213)"
    - "Site D: except Exception → if sub_agent_enabled → error + yield error + yield done + return (L2113)"
    - "D-19: str(exc)[:500] in DB, str(exc)[:200] in SSE detail — no traceback in payloads"
    - "D-20: no catch-and-retry — LLM sees error as tool_result in next round"
    - "Rule 1 auto-fix: added agent_runs_service base mocks to test_task_tool.py + test_chat_resume_flow.py"

key-files:
  created:
    - backend/tests/integration/test_agent_status_emission.py
  modified:
    - backend/app/routers/chat.py
    - backend/tests/tool/test_task_tool.py
    - backend/tests/integration/test_chat_resume_flow.py

key-decisions:
  - "Site A block placed BEFORE resume injection (D-04) so run_id is set before the loop body runs"
  - "Site D uses return after yield done (not fall-through) so de-anonymize/persist blocks don't run on exception path"
  - "start_run count=2 is correct: one at Site A (fresh run), one inside ask_user dispatch (19-05 creates run if none exists at pause time)"
  - "test_task_tool.py uses contextlib.ExitStack replacing static with-tuple so extra_patches can be applied"

requirements-completed: [STATUS-01, STATUS-02, STATUS-03, STATUS-05]

# Metrics
duration: ~8min
completed: 2026-05-03
---

# Phase 19 Plan 06: agent_status SSE Emission + agent_runs Lifecycle Summary

**agent_status Sites A/C/D wired in run_deep_mode_loop, all gated by sub_agent_enabled — Site B delegated to 19-05 ask_user handler — agent_runs lifecycle (start_run/complete/error) integrated — append-only error contract (D-18/D-19/D-20) enforced — 28/28 cumulative tests pass (TDD)**

## Performance

- **Duration:** ~8 min
- **Completed:** 2026-05-03
- **Tasks:** 2 (TDD RED + GREEN)
- **Files created:** 1 / modified: 3

## Accomplishments

### Task 1 (RED): test_agent_status_emission.py — 8 failing tests

`backend/tests/integration/test_agent_status_emission.py` — 8 test functions:

1. `test_agent_status_transitions_working_to_complete` — Site A + Site C + lifecycle
2. `test_agent_status_transitions_to_waiting_for_user` — Site B ownership (from 19-05), exactly 1 emission
3. `test_agent_status_emits_error_on_uncaught_exception` — Site D + error lifecycle
4. `test_failed_tool_call_appended_to_messages_with_structured_error` — D-18 append-only
5. `test_no_stack_trace_in_tool_result_payload` — D-19 sanitization
6. `test_no_automatic_retry_on_tool_failure` — D-20 no-retry
7. `test_sub_agent_does_not_emit_agent_status` — D-07 no nested agent_status
8. `test_agent_runs_row_lifecycle_start_to_complete` — STATUS-05 lifecycle

RED commit: `457a759` (7/8 fail as expected; test 5 trivially passes before implementation)

### Task 2 (GREEN): chat.py — Sites A, C, D wired

**Site A — Loop entry (L1735-1751):**

```python
if settings.sub_agent_enabled:
    if resume_run_id is None:
        run_record = await agent_runs_service.start_run(...)
        run_id = run_record["id"]
    else:
        run_id = resume_run_id
    yield f"data: {json.dumps({'type': 'agent_status', 'status': 'working'})}\n\n"
else:
    run_id = None
```

Also removed the pre-existing unconditional `agent_status{working}` yield from the resume injection block (L1743 in old code) since Site A now handles it correctly for both fresh and resume paths.

**Site B — NOT emitted here.** Canonical owner is 19-05's ask_user dispatch handler at L1914. Only a documentation comment added.

**Site C — Before final done (L2213-2217):**

```python
if settings.sub_agent_enabled:
    if run_id is not None:
        await agent_runs_service.complete(run_id, token, user_id, user_email)
    yield f"data: {json.dumps({'type': 'agent_status', 'status': 'complete'})}\n\n"
yield f"data: {json.dumps({'type': 'delta', 'delta': '', 'done': True})}\n\n"  # both branches
```

**Site D — Uncaught exception (L2113-2130):**

```python
except Exception as exc:
    logger.error("run_deep_mode_loop error: %s", exc, exc_info=True)
    if settings.sub_agent_enabled:
        if run_id is not None:
            try:
                await agent_runs_service.error(run_id, token, user_id, user_email, error_detail=str(exc)[:500])
            except Exception:
                logger.exception("failed to record agent_runs error")
        yield f"data: {json.dumps({'type': 'agent_status', 'status': 'error', 'detail': str(exc)[:200]})}\n\n"
    yield f"data: {json.dumps({'type': 'delta', 'delta': '', 'done': True})}\n\n"
    return
```

**Regression fixes (Rule 1):**

- `test_task_tool.py`: Updated `_collect_sse_events` to use `contextlib.ExitStack` instead of hardcoded 6-patch `with` statement, added agent_runs_service base mocks (start_run, complete, error, get_active_run, set_pending_question)
- `test_chat_resume_flow.py`: Added same agent_runs_service base mocks to `_drive_run_deep_mode_loop` base_patches

## Test Results

```
tests/integration/test_agent_status_emission.py — 8 passed
tests/tool/test_ask_user_tool.py — 6 passed
tests/integration/test_chat_resume_flow.py — 6 passed
tests/tool/test_task_tool.py — 8 passed
======================== 28 passed, 10 warnings in 3.29s ========================
```

All 8 new tests pass. 0 regressions in prior 20 tests.

## Emission Site Line Numbers

| Site | Status | Line | Gated By |
|------|--------|------|----------|
| A | working | L1749 | `if settings.sub_agent_enabled:` |
| B | waiting_for_user | L1914 (19-05 owner) | `if func_name == "ask_user" and settings.sub_agent_enabled:` |
| C | complete | L2216 | `if settings.sub_agent_enabled:` |
| D | error | L2126 | `if settings.sub_agent_enabled:` |

## agent_runs Lifecycle Hook Line Numbers

| Method | Line | When |
|--------|------|------|
| `start_run` | L1743 | Site A — fresh loop entry |
| `start_run` | L1901 | ask_user dispatch (19-05) — creates run if none active at pause time |
| `error` | L2120 | Site D — uncaught exception |
| `complete` | L2215 | Site C — successful terminal |

## Invariants Confirmed

| Invariant | Status |
|-----------|--------|
| D-16: Sites A/C/D owned here; Site B = 19-05 | CONFIRMED |
| D-17: ALL 3 owned sites gated by sub_agent_enabled | CONFIRMED (grep confirms L1735, L2113, L2213) |
| D-19: no traceback in payloads | CONFIRMED (str(exc)[:200/500]; tests 3+5 verify) |
| D-20: no auto-retry | CONFIRMED (dispatch called exactly once; test 6 verifies) |
| D-07: sub-agent does not emit agent_status | CONFIRMED (test 7 verifies) |
| STATUS-05: agent_runs lifecycle wired | CONFIRMED (test 8 verifies both paths) |
| D-17: byte-identical fallback when flag off | CONFIRMED (no agent_status/lifecycle when sub_agent_enabled=False) |
| Site B duplication avoided | CONFIRMED (exactly 1 waiting_for_user yield in chat.py) |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Resume injection had unconditional agent_status{working} yield**
- **Found during:** Task 2 (GREEN, Site A insertion)
- **Issue:** The pre-existing resume injection code at L1742 had `yield agent_status{working}` unconditionally (not gated by sub_agent_enabled). This would violate D-17 when the flag is off, and would double-emit working when Site A's gated emission also fired.
- **Fix:** Moved the working emission entirely into the new Site A block (L1749), which handles both fresh and resume paths correctly under the sub_agent_enabled gate.
- **Files modified:** `backend/app/routers/chat.py`

**2. [Rule 1 - Bug] test_task_tool.py hardcoded 6 patches broke with new lifecycle calls**
- **Found during:** Task 2 (GREEN, running 28-test suite)
- **Issue:** `_collect_sse_events` used `with (patch0, patch1, ..., patch5)` — hardcoded 6 patches. Site A now calls `agent_runs_service.start_run` which isn't mocked, causing real Supabase client creation to fail with IndexError.
- **Fix:** Changed to `contextlib.ExitStack` pattern and added agent_runs_service base mocks.
- **Files modified:** `backend/tests/tool/test_task_tool.py`

**3. [Rule 1 - Bug] test_chat_resume_flow.py missing start_run mock**
- **Found during:** Task 2 (GREEN, running 28-test suite)
- **Issue:** Test 3 (`test_resume_branch_short_circuits_when_no_active_run`) passed `get_active_run` mock but not `start_run`. Site A now calls start_run unconditionally (when sub_agent_enabled=True and resume_run_id=None), causing real Supabase call.
- **Fix:** Added agent_runs_service base mocks to `_drive_run_deep_mode_loop`'s base_patches.
- **Files modified:** `backend/tests/integration/test_chat_resume_flow.py`

**4. [Rule 1 - Bug] Test 5 D-19 assertion used wrong "Traceback" detection**
- **Found during:** Task 2 (GREEN, running tests)
- **Issue:** Original test checked for literal "Traceback" string in exception message, but the exception message itself could contain "Traceback". D-19 prohibits `traceback.format_exc()` output (which contains `File "..."` lines), not just the word "Traceback".
- **Fix:** Updated test to raise a real exception with proper traceback capture, then assert `'File "'` (traceback line format) is absent from payloads.
- **Files modified:** `backend/tests/integration/test_agent_status_emission.py`

**Total deviations:** 4 auto-fixed (Rule 1)
**Impact:** No scope change. All behavior correct; tests now accurately verify the invariants.

## Task Commits

1. **Task 1 RED (8 failing tests):** `457a759` — test(19-06): add failing tests
2. **Task 2 GREEN (Sites A/C/D + lifecycle):** `b3cc845` — feat(19-06): wire agent_status

## Known Stubs

None — all three emission sites are wired. Site B (waiting_for_user) is fully wired by 19-05's ask_user handler. The plan's scope is complete.

## Threat Surface Scan

No new network endpoints. Changes are confined to `run_deep_mode_loop` internal flow:
- T-19-19 (stack trace exfiltration): MITIGATED — `str(exc)[:200/500]` only; tests 3+5 verify
- T-19-20 (implicit retry): MITIGATED — single dispatch; test 6 verifies
- T-19-AUDIT-LIFECYCLE (orphan working rows): MITIGATED — Sites C+D close all active runs
- T-19-D17 (byte-identical fallback leak): MITIGATED — all three sites gated

## Self-Check

Files and commits verified below.

## Self-Check: PASSED

- `backend/tests/integration/test_agent_status_emission.py` — FOUND
- `backend/app/routers/chat.py` has Site A `agent_status{working}` yield (L1749) — FOUND
- `backend/app/routers/chat.py` has Site C `agent_status{complete}` yield (L2216) — FOUND
- `backend/app/routers/chat.py` has Site D `agent_status{error}` yield (L2126) — FOUND
- `backend/app/routers/chat.py` has `agent_runs_service.start_run` (L1743) — FOUND
- `backend/app/routers/chat.py` has `agent_runs_service.complete` (L2215) — FOUND
- `backend/app/routers/chat.py` has `agent_runs_service.error` (L2120) — FOUND
- `str(exc)[:500]` in D-19 position — FOUND
- Commit `457a759` (RED) — FOUND
- Commit `b3cc845` (GREEN) — FOUND
- 28/28 tests pass — CONFIRMED

---
*Phase: 19-sub-agent-delegation-ask-user-status-recovery*
*Completed: 2026-05-03*
