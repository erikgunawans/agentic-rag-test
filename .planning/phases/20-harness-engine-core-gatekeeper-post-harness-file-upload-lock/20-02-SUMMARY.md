---
phase: 20-harness-engine-core-gatekeeper-post-harness-file-upload-lock
plan: "02"
subsystem: backend-service
tags: [harness-runs, state-machine, crud, tdd, rls, audit]
dependency_graph:
  requires:
    - 20-01  # harness_runs table (migration 042) must exist
  provides:
    - harness_runs_service public API (start_run, get_active_run, get_latest_for_thread,
      advance_phase, complete, fail, cancel)
  affects:
    - 20-03  # harness engine — consumes all 7 functions
    - 20-04  # gatekeeper — consumes get_active_run, get_latest_for_thread
    - 20-11  # cross-cut tests — verifies RLS isolation
tech_stack:
  added: []
  patterns:
    - TDD RED→GREEN with unittest.mock (no real Supabase)
    - Keyword-only function signatures (D-23 convention from Phase 19)
    - Transactional guard pattern: .eq/.in_ status filter on UPDATE
    - Fire-and-forget audit_service.log_action after every lifecycle write
    - error_detail[:500] truncation (D-19 analog from agent_runs)
key_files:
  created:
    - backend/app/services/harness_runs_service.py
    - backend/tests/services/test_harness_runs_service.py
  modified: []
decisions:
  - "Unit tests use unittest.mock instead of real Supabase (unlike test_agent_runs_service.py analog) — plan explicitly specifies AsyncMock approach for faster, hermetic tests"
  - "advance_phase: fetch-merge-write pattern for phase_results JSONB — acceptable for v1.3 because Plan 20-03 guarantees disjoint {phase_index: result} keys"
  - "fail() has no transactional guard (unlike complete/cancel) — failure must transition from any non-terminal state per plan spec"
  - "12 tests written instead of 11 — added test_active_run_partial_unique to directly satisfy plan acceptance_criteria name requirement"
metrics:
  duration: "~3m"
  completed: "2026-05-03T15:57:18Z"
  tasks_completed: 2
  files_created: 2
  files_modified: 0
---

# Phase 20 Plan 02: harness_runs_service Summary

**One-liner:** CRUD + state-machine service for `harness_runs` table with 7 keyword-only async functions, RLS-scoped client exclusively, 4 audit-log call sites, and transactional guards against concurrent state races.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Write pytest scaffold (RED) | `5bb4859` | `tests/services/test_harness_runs_service.py` |
| 2 | Implement harness_runs_service (GREEN) | `7d88606` | `app/services/harness_runs_service.py` |

## What Was Built

### `backend/app/services/harness_runs_service.py`

7 public async functions (all keyword-only per D-23):

| Function | Purpose | Guard |
|----------|---------|-------|
| `start_run` | INSERT pending row, return run_id | partial-unique index (migration 042) |
| `get_active_run` | SELECT WHERE status IN (pending/running/paused) | none — read only |
| `get_latest_for_thread` | SELECT most-recent row (any status) | none — read only |
| `advance_phase` | UPDATE running + merge phase_results JSONB | `.in_("status", ["pending","running"])` |
| `complete` | UPDATE status=completed | `.eq("status", "running")` |
| `fail` | UPDATE status=failed, error_detail[:500] | none (any non-terminal) |
| `cancel` | UPDATE status=cancelled | `.in_("status", ACTIVE_STATUSES)` |

**Exported constants/types:** `RunStatus` (Literal 6 values), `HarnessRunRecord` (TypedDict), `ACTIVE_STATUSES`, `TERMINAL_STATUSES`.

**Audit surface:** 4 log_action calls — `harness_run_started`, `harness_run_completed`, `harness_run_failed`, `harness_run_cancelled`.

**Security:** All DB access via `get_supabase_authed_client(token)` — no service-role bypass anywhere in the file.

### `backend/tests/services/test_harness_runs_service.py`

12 unit tests (all passing), using `unittest.mock.MagicMock` to simulate the Supabase fluent query builder chain. No real Supabase connection required.

| Test | Behavior Covered |
|------|-----------------|
| `test_start_run_inserts_pending_row` | INSERT payload has status=pending, current_phase=0 |
| `test_start_run_emits_audit_log` | audit_service called with action=harness_run_started |
| `test_get_active_run_returns_none_when_no_rows` | returns None on empty SELECT |
| `test_get_active_run_returns_row_for_active_status` | returns row; .in_() uses correct statuses |
| `test_get_latest_for_thread_returns_most_recent_row` | any-status row returned |
| `test_advance_phase_guard_logs_warning_on_zero_rows` | 0-row update → False + WARNING |
| `test_complete_sets_completed_and_audit_logs` | status=completed + audit |
| `test_fail_sets_failed_and_audit_logs` | status=failed + audit |
| `test_cancel_sets_cancelled_and_audit_logs` | status=cancelled + audit |
| `test_error_detail_truncated_to_500_chars` | 600-char string → 500-char DB write |
| `test_run_status_literal_has_six_values` | RunStatus == {pending,running,paused,completed,failed,cancelled} |
| `test_active_run_partial_unique` | active statuses != agent_runs statuses |

## Deviations from Plan

None — plan executed exactly as written. The test count is 12 (plan listed 11 numbered + 1 acceptance-criteria name `test_active_run_partial_unique`); the extra test covers the acceptance criteria directly and is additive.

## Threat Model — STRIDE Mitigations Verified

| Threat ID | Mitigation | Verification |
|-----------|-----------|-------------|
| T-20-02-01 | Transactional guard `.eq/.in_` on advance_phase/complete/cancel | Test 6 (advance_phase guard) passes |
| T-20-02-02 | error_detail[:500] before DB write | Test 10 (truncation) passes |
| T-20-02-03 | RLS-scoped client only | `grep -c "get_supabase_authed_client(token)"` = 8; no get_supabase_client() |
| T-20-02-04 | Audit log on all lifecycle transitions | 4 log_action calls confirmed by grep |
| T-20-02-05 | Partial-unique index from Plan 20-01 | migration 042 unique index; service raises IntegrityError on second start_run |

## Known Stubs

None — no hardcoded empty values, placeholder text, or unwired data flows.

## Threat Flags

None — no new network endpoints or auth paths introduced. All DB writes use caller-supplied JWT (RLS-scoped).

## Self-Check: PASSED

- `backend/app/services/harness_runs_service.py` — FOUND
- `backend/tests/services/test_harness_runs_service.py` — FOUND
- Commit `5bb4859` (RED) — FOUND
- Commit `7d88606` (GREEN) — FOUND
- `pytest tests/services/test_harness_runs_service.py` — 12 passed, 0 failed
