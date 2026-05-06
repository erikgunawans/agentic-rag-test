---
phase: 22-contract-review-harness-docx-deliverable
plan: 14
subsystem: backend/harness-engine
tags: [bug-fix, tdd, write-todos, harness-engine, gap-closure]
dependency_graph:
  requires: []
  provides: [correct-write-todos-call-signature]
  affects: [harness-engine-phase-transitions, plan-panel-todos]
tech_stack:
  added: []
  patterns: [TDD-red-green, side-effect-capturing-mock]
key_files:
  created:
    - backend/tests/services/test_harness_engine_todos.py
  modified:
    - backend/app/services/harness_engine.py
    - backend/tests/services/test_harness_engine.py
decisions:
  - "Fixed call sites rather than changing write_todos signature (per plan constraint)"
  - "Updated test_harness_engine.py assertion index from [1] to [4] after call signature correction"
metrics:
  duration: "~15 minutes"
  completed: "2026-05-06"
  tasks: 2
  files_changed: 3
---

# Phase 22 Plan 14: write_todos Signature Fix Summary

**One-liner:** Fixed all 4 `write_todos` call sites in `harness_engine.py` from broken 3-arg `(thread_id, todos, token)` to correct 5-arg `(thread_id, user_id, user_email, token, todos)` using TDD red-green cycle.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Write regression test (RED) | b9353ce | backend/tests/services/test_harness_engine_todos.py |
| 2 | Fix call sites + update existing test (GREEN) | 02d1860 | backend/app/services/harness_engine.py, backend/tests/services/test_harness_engine.py |

## RED Step — Captured Failure Output

Running `pytest tests/services/test_harness_engine_todos.py::test_write_todos_signature_propagation` BEFORE the fix produced:

```
WARNING  harness_engine:harness_engine.py:204 harness_engine: write_todos (init) failed harness_run_id=run-1:
    capturing_write_todos() missing 2 required positional arguments: 'token' and 'todos'
WARNING  harness_engine:harness_engine.py:291 harness_engine: write_todos (in_progress) failed:
    capturing_write_todos() missing 2 required positional arguments: 'token' and 'todos'
WARNING  harness_engine:harness_engine.py:430 harness_engine: write_todos (completed) failed:
    capturing_write_todos() missing 2 required positional arguments: 'token' and 'todos'

AssertionError: Expected >=3 write_todos calls (init/in_progress/completed); got 0

FAILED tests/services/test_harness_engine_todos.py::test_write_todos_signature_propagation
```

This confirms the error handler's `except` blocks swallowed all 3 TypeErrors silently — matching the UAT diagnosis that harness failure was silent (Plan Panel rendered empty phases, no progression).

## Fix — Diff of harness_engine.py (4 lines changed)

```python
# Line 201 (init)
- await agent_todos_service.write_todos(thread_id, todos, token)
+ await agent_todos_service.write_todos(thread_id, user_id, user_email, token, todos)

# Line 289 (in_progress)
- await agent_todos_service.write_todos(thread_id, todos, token)
+ await agent_todos_service.write_todos(thread_id, user_id, user_email, token, todos)

# Line 361 (error)
- await agent_todos_service.write_todos(thread_id, todos, token)
+ await agent_todos_service.write_todos(thread_id, user_id, user_email, token, todos)

# Line 428 (completed)
- await agent_todos_service.write_todos(thread_id, todos, token)
+ await agent_todos_service.write_todos(thread_id, user_id, user_email, token, todos)
```

`user_id` and `user_email` were already in scope at all 4 sites (keyword args of `_run_harness_engine_inner`).

## GREEN Step — Pytest Summary

```
tests/services/test_harness_engine_todos.py::test_write_todos_signature_propagation PASSED
tests/services/test_harness_engine_todos.py::test_write_todos_signature_propagation_error_path PASSED
2 passed in 0.50s
```

Full harness engine suite (34 tests):
```
tests/services/test_harness_engine.py ............. (13 passed)
tests/services/test_harness_engine_todos.py .. (2 passed)
tests/services/test_harness_engine_post_execute.py ...... (6 passed)
tests/services/test_harness_engine_smoke_phase21.py ............. (13 passed)
34 passed in 1.92s — 0 failures
```

Full backend suite: 65 pre-existing failures (confirmed identical count before and after this plan — no regressions introduced). Pre-existing failures are in `test_redact_text_batch`, `test_redaction_service_d84_gate`, and `test_tool_registry_natives`.

## tool_service.py SHA Verification

```
cb63cf3e60d5f6380e2e41f63b1fe9122f58ab4648808b0f2114e452cd45ddb2  -
```

Matches pinned hash. Frozen range untouched.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated pre-existing test assertion for corrected signature**
- **Found during:** Task 2 GREEN verification
- **Issue:** `test_run_harness_engine_writes_agent_todos` in `test_harness_engine.py` accessed `call_args_list[0][0][1]` to extract `todos`. This index was correct for the old broken 3-arg signature but now returns `user_id` (a string) after the fix, causing `TypeError: string indices must be integers, not 'str'`.
- **Root cause:** The pre-existing test was written to the broken call signature — it only "passed" before because `AsyncMock` accepted any args and the index accidentally matched.
- **Fix:** Changed assertion index from `[0][1]` to `[0][4]` to match the corrected 5-arg signature, and added a comment explaining the positional layout.
- **Files modified:** `backend/tests/services/test_harness_engine.py`
- **Commit:** 02d1860

## Known Stubs

None — all test data is real (no hardcoded empty values flowing to UI).

## Threat Flags

None — no new network endpoints, auth paths, or trust boundary changes. This fix only corrects positional argument order in an internal async service call.

## Self-Check: PASSED

- [x] `backend/tests/services/test_harness_engine_todos.py` exists
- [x] Contains `test_write_todos_signature_propagation`
- [x] Contains `test_write_todos_signature_propagation_error_path`
- [x] `grep -c "write_todos(thread_id, user_id, user_email, token, todos)" harness_engine.py` = 4
- [x] `grep -c "write_todos(thread_id, todos, token)" harness_engine.py` = 0
- [x] Import check: IMPORT_OK
- [x] Regression tests: 2/2 PASSED
- [x] Existing harness tests: 34/34 PASSED
- [x] tool_service.py SHA: cb63cf3e... matches
- [x] Commit b9353ce (RED) verified in git log
- [x] Commit 02d1860 (GREEN) verified in git log
