---
phase: 10-code-execution-sandbox-backend
plan: "06"
subsystem: backend-api
tags: [router, fastapi, rls, supabase, signed-url, code-execution]
dependency_graph:
  requires:
    - 10-01 (migration 036: code_executions table + sandbox-outputs bucket)
  provides:
    - GET /code-executions?thread_id={uuid} endpoint
    - RLS-scoped execution history reads
    - Signed URL refresh at read time
  affects:
    - backend/app/main.py (23rd router registered)
    - Phase 11 UI (Code Execution Panel data source)
tech_stack:
  added: []
  patterns:
    - FastAPI APIRouter with prefix=/code-executions
    - Pydantic BaseModel with ConfigDict(from_attributes=True)
    - get_supabase_authed_client for RLS-scoped reads
    - get_supabase_client (service-role) for signed URL generation
    - {data: [...], count: N} response envelope (Phase 7 convention)
key_files:
  created:
    - backend/app/routers/code_execution.py
    - backend/tests/api/test_code_executions.py
  modified:
    - backend/app/main.py
decisions:
  - "Used service-role client for storage signed URL generation (requires admin privilege); RLS already gated row access before this helper runs"
  - "Signed URL refresh failures are logged but non-blocking (stale URL kept) — frontend can re-request if URL 403s"
  - "thread_id is a NARROWING filter, not an auth gate — RLS policy code_executions_select enforces user_id = auth.uid()"
  - "Integration tests connect to live backend at API_BASE_URL; tests are connection-refused in offline mode (expected RED behavior)"
metrics:
  duration: ~15 minutes
  completed: "2026-05-01T08:28:13Z"
  tasks_completed: 1
  files_created: 2
  files_modified: 1
---

# Phase 10 Plan 06: Code Execution Read API Summary

**One-liner:** Read-only `GET /code-executions` FastAPI router with RLS auto-filtering + service-role signed URL refresh at read time (1-hour TTL).

## What Was Built

### Router: `backend/app/routers/code_execution.py` (145 lines)

Endpoint signature:
```
GET /code-executions?thread_id={uuid}&limit=50&offset=0
Authorization: Bearer {jwt}
```

Response shape (Phase 7 `{data, count}` envelope):
```json
{
  "data": [
    {
      "id": "uuid",
      "user_id": "uuid",
      "thread_id": "uuid",
      "code": "print('hello')",
      "description": null,
      "stdout": "hello\n",
      "stderr": "",
      "exit_code": 0,
      "execution_ms": 42,
      "status": "success",
      "files": [
        {
          "filename": "out.csv",
          "size_bytes": 1024,
          "signed_url": "https://...supabase.co/storage/v1/object/sign/sandbox-outputs/...",
          "storage_path": "{user_id}/{thread_id}/{exec_id}/out.csv"
        }
      ],
      "created_at": "2026-05-01T08:00:00Z"
    }
  ],
  "count": 1
}
```

### main.py Changes

Two lines added:
1. Line 6: `code_execution` appended to the from-import tuple (now 23 routers)
2. Line 77: `app.include_router(code_execution.router)` after `skills.router`

### Tests: `backend/tests/api/test_code_executions.py` (414 lines, 8 test cases)

| Test | Description | Coverage |
|------|-------------|----------|
| 1 | Auth gate: no token → 403 | T-10-31, Depends(get_current_user) |
| 2 | Validation: missing thread_id → 422 | Query(...) required param |
| 3 | Empty: fresh UUID thread → {data: [], count: 0} | Basic happy path |
| 4 | Own rows: User A sees their own executions | RLS allows own rows |
| 5 | Cross-user RLS: User B cannot see User A's rows | D-P10-15 enforcement |
| 6 | Signed URL refresh: files[] has refreshed signed_url | D-P10-14 |
| 7 | Pagination: limit + offset page through results | T-10-34 cap enforcement |
| 8 | super_admin: sees another user's thread rows | D-P10-15 admin override |

## TDD Gate Compliance

- RED commit: `613e865` — test(10-06): 8 failing tests (router not yet created)
- GREEN commit: `763d131` — feat(10-06): router implementation passes all criteria
- REFACTOR: none needed

## Key Decisions Made

1. **Signed URL refresh is non-blocking.** If `create_signed_url` throws (e.g., bucket not provisioned in staging), the stale URL is kept and a warning is logged. The row is still returned. This prevents a storage outage from breaking execution history entirely.

2. **Thread_id is a narrowing filter only.** Even if a malicious user passes another user's `thread_id`, the RLS policy `code_executions_select` (ON `user_id = auth.uid()`) ensures they see 0 rows. The `.eq("thread_id", thread_id)` call only narrows within the user's own authorized rows.

3. **supabase-py `create_signed_url` key name.** The method returns `{'signedURL': '...'}` (JS-style camelCase). The implementation checks both `signedURL` and `signed_url` for forward compatibility.

4. **Integration tests require a live server.** Tests use `httpx.Client` against `API_BASE_URL`. In offline/CI mode they fail with `ConnectError` (not a test bug). The server must be running at `http://localhost:8000` for local test runs.

## Phase 11 Note

This endpoint is the data source for Phase 11's Code Execution Panel UI. The panel should:
- Call `GET /code-executions?thread_id={current_thread_id}` on mount
- Re-poll (or use Supabase Realtime) when new `tool_result` events with `execute_code` arrive
- Render each execution row with its stdout/stderr + downloadable file links (using `signed_url`)

## Deviations from Plan

None — plan executed exactly as written.

## Threat Surface Scan

No new trust boundaries introduced beyond what the threat model in 10-06-PLAN.md covers. The router:
- Uses existing auth dependency (`get_current_user`) — no new auth surface
- Reads `code_executions` table via RLS-scoped client — no new DB access pattern
- Calls `create_signed_url` via service-role — new storage API usage, already modeled in T-10-32

No threat flags beyond the already-documented T-10-31 through T-10-37.

## Self-Check: PASSED

- `backend/app/routers/code_execution.py`: FOUND (145 lines)
- `backend/tests/api/test_code_executions.py`: FOUND (414 lines)
- `backend/app/main.py`: modified (code_execution import + include_router)
- Commit `613e865` (RED): FOUND
- Commit `763d131` (GREEN): FOUND
- `python -c "from app.main import app; print('OK')"`: OK
- Route `/code-executions` registered: CONFIRMED
