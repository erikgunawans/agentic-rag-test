---
phase: 7
plan: "07-04"
title: "skills.py router — CRUD + share + export + import"
subsystem: backend/skills-api
tags: [fastapi, skills, crud, export, import, middleware, rls]
dependency_graph:
  requires: [07-01, 07-02, 07-03]
  provides: [skills-rest-api, skills-upload-middleware]
  affects: [backend/app/main.py, backend/app/routers/, backend/app/middleware/]
tech_stack:
  added: [SkillsUploadSizeMiddleware (ASGI pre-body cap), StreamingResponse (ZIP export)]
  patterns:
    - RLS-scoped CRUD mirroring clause_library.py
    - Service-role escapes with inline D-P7-NN audit comments
    - ASGI middleware for pre-body upload size enforcement
    - computed_field for derived is_global property
key_files:
  created:
    - backend/app/routers/skills.py
    - backend/app/middleware/skills_upload_size.py
    - backend/app/middleware/__init__.py
  modified:
    - backend/app/main.py
decisions:
  - "/skills/import declared before /{skill_id} routes so FastAPI matches static path first"
  - "Flat storage filenames: relative_path slashes replaced with __ to satisfy 3-segment CHECK constraint"
  - "nullsfirst=True on user_id ordering confirmed supported in postgrest-py (supabase==2.7.4)"
  - "download() returns bytes directly in storage3 SyncBucketProxy (supabase-py 2.7.4)"
  - "Share name-conflict check uses ilike on service-role client before UPDATE to minimize 23505 window"
metrics:
  duration: "~25 minutes"
  completed: "2026-04-29T11:03:34Z"
  tasks_completed: 1
  files_created: 3
  files_modified: 1
---

# Phase 7 Plan 04: skills.py Router Summary

## One-liner

8 FastAPI endpoints under `/skills` for full skill lifecycle (CRUD, share toggle, ZIP export/import) with ASGI upload-size middleware and RLS-scoped security per PATTERNS.md.

## What Was Built

### `backend/app/routers/skills.py` (new, 380 lines)

Eight endpoints registered under the `/skills` prefix:

| # | Method | Path | Closes |
|---|--------|------|--------|
| 1 | POST | `/skills` | SKILL-01 |
| 2 | GET | `/skills` | SKILL-03 |
| 3 | GET | `/skills/{id}` | SKILL-03 |
| 4 | PATCH | `/skills/{id}` | SKILL-04 |
| 5 | DELETE | `/skills/{id}` | SKILL-05 |
| 6 | PATCH | `/skills/{id}/share` | SKILL-06 |
| 7 | GET | `/skills/{id}/export` | EXPORT-01 |
| 8 | POST | `/skills/import` | EXPORT-02, EXPORT-03 |

Pydantic models: `SkillCreate`, `SkillUpdate`, `ShareToggle`, `SkillResponse` (with `computed_field` for `is_global`).

### `backend/app/middleware/skills_upload_size.py` (new)

`SkillsUploadSizeMiddleware` (Starlette `BaseHTTPMiddleware`) enforces a 50 MB cap on `POST /skills/import` bodies BEFORE FastAPI's multipart parser runs. Uses Content-Length fast-path for non-chunked requests; wraps `request._receive` with a streaming byte-counter for chunked transfer-encoding (cycle-2 review H6 fix).

### `backend/app/main.py` (modified)

Added `skills` to router imports, added `SkillsUploadSizeMiddleware` registration before `include_router` calls, added `app.include_router(skills.router)` after `folders.router`.

## Security Controls Applied

All service-role usages carry `# service-role: <reason> per D-P7-NN` comments per PATTERNS.md §C:

- **DELETE (admin path)**: `get_supabase_client()` for super_admin-only deletion — `D-P7-04`
- **PATCH share (UPDATE step)**: service-role to flip `user_id` NULL/non-NULL — `D-P7-06`
- **PATCH share (conflict check)**: service-role name uniqueness check before UPDATE — `D-P7-06`
- **GET export (storage download)**: service-role to download files for globally-shared skills — `D-P7-07`

Normal user import (`POST /import`) uses RLS-scoped client — no service-role.

## Cycle Review Fixes Applied

- **Cycle-1 HIGH #2**: Runtime storage_path shape validation in export endpoint before service-role download
- **Cycle-1 HIGH #3**: `order("user_id", nullsfirst=True)` for global-first listing (no `is_global` column in DB)
- **Cycle-1 MEDIUM (existence disclosure)**: Share endpoint uses RLS pre-fetch for 404 check before any service-role query
- **Cycle-1 MEDIUM (share conflict)**: Name-conflict ilike check before UPDATE to minimize unique-violation window
- **Cycle-2 H6**: ASGI middleware caps upload before body parsing (Content-Length + streaming counter paths)
- **Cycle-2 MEDIUM**: `PostgrestAPIError` 23505 on share PATCH UPDATE → 409 (never surfaces as 500)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Redundant storage_path variable in import endpoint**
- **Found during:** Task implementation review
- **Issue:** Double assignment of `storage_path` variable with first unused assignment
- **Fix:** Single clean path computation using `flat_name = skill_file.relative_path.replace("/", "__")`
- **Files modified:** `backend/app/routers/skills.py`
- **Commit:** e04b2d6

**2. [Rule 1 - Bug] Redundant `conflict_data` variable in share endpoint**
- **Found during:** Implementation review
- **Issue:** Unused `conflict_data` list comprehension before correct `conflict_check` query
- **Fix:** Removed the redundant intermediate query and variable
- **Files modified:** `backend/app/routers/skills.py`
- **Commit:** e04b2d6

**3. [Rule 2 - Critical functionality] Storage path flattening for CHECK constraint**
- **Found during:** Implementation planning
- **Issue:** `ParsedSkillFile.relative_path` includes subdirectory (e.g. `scripts/foo.py`); the `skill_files.storage_path` CHECK constraint requires exactly 3 segments with no `/` in the third segment (`^[a-zA-Z0-9_-]+/[0-9a-fA-F-]{36}/[^/]+$`)
- **Fix:** Flatten relative_path by replacing `/` with `__` for the storage path; store flat name in `filename` column
- **Files modified:** `backend/app/routers/skills.py`
- **Commit:** e04b2d6

## Known Stubs

None — all 8 endpoints are fully wired with real DB operations.

## Threat Flags

None — all new endpoints are authenticated via `Depends(get_current_user)`. Service-role escapes are minimized and documented per PATTERNS.md §C. Storage upload paths are validated at runtime (HIGH #2 mitigation). The 50 MB cap middleware protects against oversized multipart uploads.

## Self-Check: PASSED

- `backend/app/routers/skills.py` — exists, 380+ lines
- `backend/app/middleware/skills_upload_size.py` — exists
- `backend/app/middleware/__init__.py` — exists
- `backend/app/main.py` — modified with router + middleware registration
- Commit e04b2d6 — `git log --oneline | grep e04b2d6` confirmed
- Import smoke: 5 unique /skills paths (covering all 8 HTTP operations) confirmed
- `python -c "from app.main import app; print('OK')"` — PASSED
