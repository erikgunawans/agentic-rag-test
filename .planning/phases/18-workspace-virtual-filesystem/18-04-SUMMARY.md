---
plan: "18-04"
phase: "18-workspace-virtual-filesystem"
status: complete
wave: 3
self_check: PASSED

subsystem: workspace-virtual-filesystem
tags: [fastapi, router, rls, workspace, api-tests]

dependency_graph:
  requires: ["18-02"]
  provides: ["workspace-rest-api"]
  affects: ["18-07-workspace-panel-ui"]

tech_stack:
  added: []
  patterns:
    - "Lazy-import feature-flag gate (WORKSPACE_ENABLED) — same pattern as sandbox_enabled + tool_registry_enabled"
    - "asyncio.run() wrapper for async WorkspaceService calls inside sync pytest tests"
    - "follow_redirects=False in httpx.Client for explicit 307 redirect assertions"

key_files:
  created:
    - backend/app/routers/workspace.py
    - backend/tests/api/test_workspace_endpoints.py
  modified:
    - backend/app/config.py
    - backend/app/main.py

decisions:
  - "get_current_user import path: app.dependencies (confirmed via threads.py analog)"
  - "Cross-thread RLS isolation test returns 403/404 (not 200-empty) — RLS denies at read level too"
  - "asyncio.run() used as async wrapper (not anyio/pytest-asyncio) — consistent with sync test style of existing API tests"
  - "Test backend started on port 8001 with WORKSPACE_ENABLED=true to avoid interference with running production-like backend on 8000"

metrics:
  duration: "~15 minutes"
  completed: "2026-05-03T00:53:31Z"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 2
---

# Phase 18 Plan 04: Workspace REST Endpoints + API Tests Summary

**One-liner:** FastAPI workspace router with RLS-scoped list/read endpoints, WORKSPACE_ENABLED feature flag gate, and 8-test live-API suite verifying auth, isolation, and content type handling.

## What Was Built

Two REST endpoints added to `backend/app/routers/workspace.py`:

| Endpoint | Behavior |
|----------|----------|
| `GET /threads/{thread_id}/files` | Returns JSON array of `{file_path, size_bytes, source, mime_type, updated_at}` ordered by `updated_at DESC` |
| `GET /threads/{thread_id}/files/{file_path:path}` | Text files: inline body with detected MIME type. Binary files: 307 redirect to 1-hour signed URL. Missing/denied: 404. Invalid path: 400. |

## Implementation Details

**`get_current_user` import path:** `app.dependencies` (confirmed by reading `backend/app/routers/threads.py` — the closest analog with the same RLS-scoped pattern).

**Feature flag gate:** `workspace_enabled: bool = False` added to `Settings` in `backend/app/config.py`. The router is imported lazily inside `if settings.workspace_enabled:` in `main.py` — when `False`, the routes do not exist and FastAPI returns 404 (T-18-18 mitigation).

**Asyncio wrapper in tests:** `asyncio.run()` used as a thin wrapper for `WorkspaceService` coroutines inside sync pytest functions. This is consistent with the sync-first style of existing API test files (`test_code_executions.py`, etc.) which do not use `pytest-asyncio` markers.

**Cross-thread RLS result:** User B attempting to read User A's file gets **403** (FastAPI's auth middleware rejects before the RLS predicate fires — the token is valid but Supabase denies the row). Test accepts `403` or `404`.

## Commits

| Hash | Description |
|------|-------------|
| `df943a5` | `feat(18-04)`: workspace router + config workspace_enabled + main.py mount |
| `795e572` | `test(18-04)`: API tests — auth gate, list, read, 404, traversal, RLS isolation |

## Must-Haves Verified

- [x] `GET /threads/{thread_id}/files` returns RLS-scoped list as JSON array
- [x] `GET /threads/{thread_id}/files/{path:path}` returns text inline or 307-redirects to signed URL for binary
- [x] Non-owner / cross-thread access is rejected (403 — RLS-driven)
- [x] When `WORKSPACE_ENABLED=False` both endpoints return 404 (not registered)

## Test Results

```
8 passed, 1 skipped, 6 warnings in 10.20s
```

| Test | Result |
|------|--------|
| `TestAuthGate::test_list_no_auth_returns_403` | PASSED |
| `TestAuthGate::test_read_no_auth_returns_403` | PASSED |
| `TestEmptyList::test_list_empty_thread` | PASSED |
| `TestWriteListRead::test_write_then_list_then_read_text` | PASSED |
| `TestMissingFile::test_read_missing_file_404` | PASSED |
| `TestInvalidPath::test_dotdot_traversal_rejected` | PASSED |
| `TestRLSIsolation::test_cross_thread_list_isolation` | PASSED |
| `TestRLSIsolation::test_cross_thread_read_isolation` | PASSED |
| `TestWorkspaceDisabledGate::test_disabled_gate_smoke` | SKIPPED (process-isolated; covered by Task 1 assertion) |

## Deviations from Plan

### Auto-added: workspace_enabled config field

The plan referenced `WORKSPACE_ENABLED` env var / config flag but the `Settings` class did not have `workspace_enabled` field yet. Added as part of Task 1 (Rule 3 — blocking issue: `settings.workspace_enabled` would raise `AttributeError` without it).

**Files modified:** `backend/app/config.py`
**Commit:** `df943a5`

## Threat Surface Scan

No new network endpoints beyond the two documented in the plan (`GET /threads/{thread_id}/files*`). Both are RLS-scoped and auth-gated. No schema changes in this plan.

## Self-Check: PASSED

- `backend/app/routers/workspace.py` — EXISTS
- `backend/tests/api/test_workspace_endpoints.py` — EXISTS
- `backend/app/config.py` contains `workspace_enabled` — EXISTS
- `backend/app/main.py` contains `if settings.workspace_enabled:` — EXISTS
- Commit `df943a5` — EXISTS
- Commit `795e572` — EXISTS
- Import check `python -c "from app.main import app; print('OK')"` — PASSED
- Route registration check with `WORKSPACE_ENABLED=true` — PASSED (both routes confirmed)
- Route absence check with `WORKSPACE_ENABLED=False` — PASSED (no routes registered)
- Test suite: 8 passed, 1 skipped — PASSED
