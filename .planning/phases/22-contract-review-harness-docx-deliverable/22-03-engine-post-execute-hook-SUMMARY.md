---
phase: 22-contract-review-harness-docx-deliverable
plan: "03"
subsystem: harness-engine
tags: [harness, post-execute, sse, workspace, docx, review-7, review-8]
dependency_graph:
  requires: []
  provides: [post_execute-invocation-site, harness_artifact-event, workspace_updated-harness-emission]
  affects: [harness_engine.py, plan-22-10-docx-callable]
tech_stack:
  added: []
  patterns:
    - "post_execute hook: try/except with non-fatal fallback (D-22-15)"
    - "harness_artifact SSE event with harness_run_id + harness_mode correlation anchors (REVIEW #8)"
    - "workspace_updated SSE emission after binary write (REVIEW #7, mirrors chat.py:1004)"
    - "phase_results accumulator: memory-bounded per-phase output dict for post_execute callbacks"
key_files:
  created:
    - backend/tests/services/test_harness_engine_post_execute.py
  modified:
    - backend/app/services/harness_engine.py
decisions:
  - "post_execute inserted after yield phase_complete_evt and before _append_progress so UI sees phase completion before artifact events (no UX racing)"
  - "workspace_updated emitted AFTER harness_artifact (artifact first so frontend can attach before re-fetching workspace)"
  - "pe_result=None is explicit noop — no yield — matching default semantics (D-16 OFF-mode invariant)"
  - "exception detail capped at 500 chars (D-19 sanitization invariant)"
metrics:
  duration: "~15 minutes"
  completed_date: "2026-05-05"
  tasks_completed: 2
  files_modified: 2
---

# Phase 22 Plan 03: Engine post_execute Hook Summary

post_execute hook wired into harness_engine.py with harness_artifact + workspace_updated SSE emission and REVIEW #7/#8 compliance verified by 7 unit tests.

## Completed Tasks

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Add failing tests for post_execute contract | cae5157 | backend/tests/services/test_harness_engine_post_execute.py |
| 2 (GREEN) | Wire post_execute invocation + workspace_updated chaining + harness_mode | 6fa16ef | backend/app/services/harness_engine.py |

## What Was Built

### harness_engine.py Changes

1. **SSE event docstring updated** — Added `harness_artifact` and `workspace_updated` to the Phase 22 section of the engine-emitted events header block.

2. **`phase_results` accumulator** — Added after WorkspaceService init in `_run_harness_engine_inner`. Populated after each successful phase with string values capped at 10,000 chars. Used by `post_execute` callbacks in plan 22-10 (DOCX callable).

3. **post_execute invocation block** — Inserted between `yield phase_complete_evt` and `await _append_progress(...)` (the exact insertion site from the plan). The block:
   - Guards `ws is None` and creates a fresh WorkspaceService if needed
   - Calls `await phase.post_execute(harness_run_id=..., thread_id=..., user_id=..., user_email=..., token=..., phase_results=..., workspace=..., harness_name=...)`
   - On exception: yields `harness_artifact` with `ok=False, code="POST_EXEC_EXC"` and continues (D-22-15)
   - On error dict return: yields `harness_artifact` with `ok=False` and all error fields
   - On success dict return: yields `harness_artifact` with `ok=True` plus all non-`wrote_binary` result keys; if `wrote_binary=True` and `docx_path` present, ALSO yields `workspace_updated` (REVIEW #7)
   - On `None` return: noop, no yield

### Test Coverage

7 tests in `backend/tests/services/test_harness_engine_post_execute.py`:

| # | Test | Behavior Verified |
|---|------|-------------------|
| 1 | `test_post_execute_none_is_noop` | post_execute=None → no harness_artifact, no workspace_updated; D-16 smoke_echo invariant |
| 2 | `test_post_execute_success_yielded_as_artifact_event` | ok=True result → harness_artifact with harness_run_id + harness_mode |
| 3 | `test_post_execute_error_dict_logged_no_status_change` | error dict → artifact ok=False; complete() called not fail() |
| 4 | `test_post_execute_exception_caught_no_status_change` | exception → artifact code=POST_EXEC_EXC; status stays completed |
| 5 | `test_post_execute_runs_after_last_phase_before_engine_complete` | ordering: phase_complete → harness_artifact → workspace_updated → harness_complete |
| 6 | `test_post_execute_emits_workspace_updated_when_wrote_binary` | REVIEW #7: wrote_binary=True → workspace_updated with file_path/source/size_bytes |
| 7 | `test_harness_artifact_event_carries_correlation_fields` | REVIEW #8: artifact has harness_run_id AND harness_mode="contract-review" |

## Deviations from Plan

None — plan executed exactly as written.

The implementation follows the action block verbatim, including:
- `phase_results` accumulator added at the ISSUE-16 pinned location
- `ws is None` guard before post_execute call
- Exception detail capped at 500 chars (D-19)
- `wrote_binary` key excluded from the artifact event payload (remains internal signal)

## Known Stubs

None — no stub patterns introduced. post_execute callsite is complete and functional.

## Threat Flags

No new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries beyond what the plan's threat model covers.

The T-22-03-02 mitigation (isinstance(dict) guard + selective key extraction) is implemented: `artifact_evt.update({k: pe_result.get(k) for k in ("error", "code", ...) if k in pe_result})` prevents injection of unexpected keys into the artifact event.

The T-22-03-03 mitigation (`str(exc)[:500]`) is implemented, matching the D-19 sanitization invariant used throughout the engine.

## Self-Check: PASSED

- FOUND: backend/tests/services/test_harness_engine_post_execute.py
- FOUND: backend/app/services/harness_engine.py
- FOUND: .planning/phases/22-contract-review-harness-docx-deliverable/22-03-engine-post-execute-hook-SUMMARY.md
- FOUND commit: cae5157 (RED test commit)
- FOUND commit: 6fa16ef (GREEN implementation commit)
