---
phase: 17-deep-mode-foundation-planning-todos-plan-panel
plan: "05"
subsystem: backend-api
tags: [rest-endpoint, rls, tdd, threads, agent-todos, todo-07]
dependency_graph:
  requires:
    - supabase/migrations/038_agent_todos_and_deep_mode.sql
    - backend/app/routers/threads.py
  provides:
    - GET /threads/{thread_id}/todos read-only endpoint (TODO-07 hydration)
  affects:
    - frontend/src/components/chat/PlanPanel.tsx (consumes this endpoint on thread reload)
tech_stack:
  added: []
  patterns:
    - "RLS-scoped nested resource read via get_supabase_authed_client(token)"
    - "Position-ordered list endpoint returning minimal projection"
    - "TDD RED/GREEN gate: test file authored before endpoint implementation"
key_files:
  created:
    - backend/tests/integration/test_threads_todos_endpoint.py
  modified:
    - backend/app/routers/threads.py
decisions:
  - "D-27 honored: GET-only surface; no POST/PATCH/DELETE — LLM writes via write_todos tool"
  - "D-28 honored: endpoint added to existing threads.py, not a new router file"
  - "Rule 1 auto-fix: test expected 401 but project convention is 403 (get_current_user returns 403 Not authenticated — matches test_admin_settings_auth.py pattern)"
metrics:
  duration: "~8 minutes"
  completed: "2026-05-03T00:00:00Z"
  tasks_completed: 2
  tasks_total: 2
---

# Phase 17 Plan 05: Todos REST Endpoint Summary

**One-liner:** GET /threads/{id}/todos endpoint added to threads.py router — RLS-scoped, position-ordered, returns {todos:[{id,content,status,position}]} for Plan Panel hydration on thread reload.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Write failing integration tests for GET /threads/{id}/todos | 81e18f8 | backend/tests/integration/test_threads_todos_endpoint.py |
| 2 | Implement GET /threads/{id}/todos in threads.py | 80ff0c3 | backend/app/routers/threads.py, backend/tests/integration/test_threads_todos_endpoint.py |

## Verification

- GET /threads/{id}/todos returns ordered list (position ASC) — verified by `test_get_todos_returns_ordered_list`
- Empty thread returns `{"todos": []}` — verified by `test_get_todos_empty_thread`
- Unauthenticated request returns 403 — verified by `test_get_todos_unauthorized_no_token`
- RLS isolation: User B sees `[]` for User A's thread — verified by `test_get_todos_rls_isolation_returns_empty`
- Unknown thread_id returns `{"todos": []}` — verified by `test_get_todos_unknown_thread`
- Response shape is exactly `{id, content, status, position}` — verified by `test_get_todos_response_shape`
- All 6 integration tests pass (GREEN gate)
- Import check passes: `python -c "from app.main import app; print('OK')"`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Auth test expected 401 but project returns 403**
- **Found during:** Task 2 (GREEN gate run)
- **Issue:** Plan spec said "GET without Authorization header → 401". The existing `get_current_user` dependency returns 403 "Not authenticated" (not 401). This is the established project convention, confirmed by `tests/unit/test_admin_settings_auth.py` which asserts `r.status_code == 403`.
- **Fix:** Updated `test_get_todos_unauthorized_no_token` to assert 403 and updated the docstring to explain the project convention.
- **Files modified:** `backend/tests/integration/test_threads_todos_endpoint.py`
- **Commit:** 80ff0c3

## TDD Gate Compliance

- RED gate: `81e18f8` — 6 tests defined, all fail (404 — endpoint not implemented)
- GREEN gate: `80ff0c3` — all 6 tests pass after endpoint added

## Known Stubs

None — endpoint is fully wired to the `agent_todos` table via RLS-scoped Supabase client.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: read_endpoint | backend/app/routers/threads.py | GET /threads/{id}/todos exposes agent_todos data — mitigated by RLS (T-17-12): get_supabase_authed_client enforces user_id = auth.uid() policy, integration test confirms User B sees [] for User A's thread |

T-17-12 (cross-tenant todo read) and T-17-13 (client mutation via this surface) are both mitigated: RLS prevents cross-user reads, GET-only prevents mutations.

## Self-Check

### Created Files Exist

- [x] `backend/tests/integration/test_threads_todos_endpoint.py` — present

### Modified Files

- [x] `backend/app/routers/threads.py` — GET /{thread_id}/todos added at line 116

### Commits Exist

- [x] 81e18f8 — test(17-05): add failing integration tests for GET /threads/{id}/todos
- [x] 80ff0c3 — feat(17-05): add GET /threads/{thread_id}/todos read-only endpoint

## Self-Check: PASSED
