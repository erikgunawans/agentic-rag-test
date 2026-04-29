---
id: 07-04
phase: 7
title: skills.py router — CRUD + share + export + import
wave: 3
depends_on: [07-01, 07-02, 07-03]
closes: [SKILL-01, SKILL-03, SKILL-04, SKILL-05, SKILL-06, EXPORT-01, EXPORT-02, EXPORT-03]
# Note: EXPORT-03 = "Import validates name/description and reports per-skill errors
# without blocking other skills in a bulk import" — closed by endpoint #8 (POST
# /skills/import) error aggregation, NOT by admin-moderation DELETE. Cycle-1 review
# MEDIUM correction.
estimated_atomic_commits: 1
---

# 07-04-PLAN — `skills.py` router

## Goal

Eight FastAPI endpoints under `/skills` covering create, list, read, update, delete, share/unshare, export, and import. Mirrors `clause_library.py` for RLS-scoped CRUD; adds three new patterns (share toggle, ZIP streaming, multipart import). Closes 8 of Phase 7's 9 requirements (SKILL-10 is closed by the migration in 07-01).

## Closes

- SKILL-01 (create), SKILL-03 (list with search/filter), SKILL-04 (update), SKILL-05 (delete), SKILL-06 (share/unshare), EXPORT-01 (router-side export streaming), EXPORT-02 (router-side import multipart), EXPORT-03 (per-skill error reporting in bulk import — endpoint #8's `ImportResult.results[].error` channel, not blocked by an earlier failure).

## Files to create / modify

- `backend/app/routers/skills.py` (new)
- `backend/app/middleware/skills_upload_size.py` (new — cycle-2 review H6 fix)
- `backend/app/main.py` (modified)
  - Line 6: append `, skills` to the `from app.routers import ...` block.
  - Add `app.add_middleware(SkillsUploadSizeMiddleware)` BEFORE `app.include_router(...)` calls so the size cap fires before any body parsing.
  - After current line 71 (`app.include_router(folders.router)`): add `app.include_router(skills.router)`.

### `skills_upload_size.py` (ASGI middleware — true pre-body cap)

```python
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from fastapi.responses import JSONResponse

SKILLS_IMPORT_PATH = "/skills/import"
MAX_IMPORT_BYTES = 50 * 1024 * 1024  # 50 MB

class SkillsUploadSizeMiddleware(BaseHTTPMiddleware):
    """Cycle-2 review H6 fix: cap POST /skills/import body BEFORE Starlette
    buffers the multipart upload. Rejects via Content-Length header when present;
    rejects via streaming byte counter when absent (chunked transfer-encoding).
    """
    async def dispatch(self, request: Request, call_next):
        if request.method != "POST" or request.url.path != SKILLS_IMPORT_PATH:
            return await call_next(request)

        cl = request.headers.get("content-length")
        if cl is not None:
            try:
                if int(cl) > MAX_IMPORT_BYTES:
                    return JSONResponse({"detail": "ZIP exceeds 50 MB limit"}, status_code=413)
            except ValueError:
                return JSONResponse({"detail": "Invalid Content-Length"}, status_code=400)

        # Chunked transfer-encoding: count bytes as they stream in; abort on overflow.
        # (Starlette streams the body; we wrap receive() to enforce the cap.)
        original_receive = request._receive
        total = {"n": 0}
        async def capped_receive():
            msg = await original_receive()
            if msg["type"] == "http.request":
                total["n"] += len(msg.get("body", b""))
                if total["n"] > MAX_IMPORT_BYTES:
                    # Replace body with a sentinel; downstream import handler returns 413.
                    return {"type": "http.disconnect"}
            return msg
        request._receive = capped_receive
        return await call_next(request)
```

This middleware enforces the 50 MB cap at the ASGI layer, BEFORE FastAPI's `UploadFile` parser. The Content-Length path is the fast path (fires before any byte is read); the streaming counter path covers chunked uploads.

## Pydantic request/response models (top of file)

```python
import re
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator
from postgrest.exceptions import APIError as PostgrestAPIError  # for 23505 catch
from app.dependencies import get_current_user, require_admin
from app.database import get_supabase_authed_client, get_supabase_client
from app.services.audit_service import log_action
from app.services.skill_zip_service import build_skill_zip, parse_skill_zip, ImportResult, SkillImportItem, SkippedFile

router = APIRouter(prefix="/skills", tags=["skills"])

NAME_REGEX = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")

class SkillCreate(BaseModel):
    name: str = Field(..., max_length=64)
    description: str = Field(..., min_length=20, max_length=1024)
    instructions: str = Field(..., min_length=1)
    enabled: bool = True
    metadata: dict = Field(default_factory=dict)
    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        if not NAME_REGEX.match(v):
            raise ValueError("Invalid name: must match ^[a-z][a-z0-9]*(-[a-z0-9]+)*$")
        return v

class SkillUpdate(BaseModel):
    name: str | None = Field(None, max_length=64)
    description: str | None = Field(None, min_length=20, max_length=1024)
    instructions: str | None = None
    enabled: bool | None = None
    metadata: dict | None = None
    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        if v is not None and not NAME_REGEX.match(v):
            raise ValueError("Invalid name format")
        return v

class ShareToggle(BaseModel):
    global_: bool = Field(..., alias="global")  # body: {"global": true|false}
    model_config = ConfigDict(populate_by_name=True)

class SkillResponse(BaseModel):
    id: str
    user_id: str | None
    created_by: str | None
    name: str
    description: str
    instructions: str
    enabled: bool
    metadata: dict
    created_at: datetime
    updated_at: datetime
    @computed_field
    @property
    def is_global(self) -> bool:
        return self.user_id is None
```

## Endpoints

All depend on `Depends(get_current_user)` unless noted.

| # | Method | Path | Body / Query | Behavior |
|---|---|---|---|---|
| 1 | POST   | `/skills` | `SkillCreate` | RLS-scoped client; INSERT with `created_by = user_id = auth.uid()`. 409 on `unique_violation`. `log_action("create", "skill", id)`. Returns `SkillResponse`, status 201. |
| 2 | GET    | `/skills` | `?search=` `?enabled=` `?limit=50` `?offset=0` | RLS-scoped query. Sanitize `search` via `replace(",","").replace("(","").replace(")","").replace("."," ")` before ILIKE (matches `clause_library.py:53`). **Cycle-1 review HIGH #3 fix**: order by `user_id NULLS FIRST, created_at DESC` (no `is_global` column exists in DB; that field is computed Pydantic-side only). PostgREST: `query.order("user_id", desc=False, nullsfirst=True).order("created_at", desc=True)`. Return `{"data": [SkillResponse...], "count": N}`. |
| 3 | GET    | `/skills/{id}` | — | RLS-scoped fetch; 404 if no row. |
| 4 | PATCH  | `/skills/{id}` | `SkillUpdate` | Pre-fetch (RLS-scoped). If `user_id IS NULL` → **403 "Cannot edit a global skill — unshare it first"** (D-P7-03). Else RLS-scoped UPDATE. `log_action("update", ...)`. |
| 5 | DELETE | `/skills/{id}` | — | If `user["role"] == "super_admin"` → service-role client deletes ANY (D-P7-04 admin moderation). Else RLS-scoped DELETE — RLS now requires `user_id = auth.uid() AND created_by = auth.uid()` (private-and-owned only); creator must unshare first to delete a global skill. If RLS rejects (row exists but is global) → return **403 "Cannot delete a global skill — unshare it first"** (matches the symmetry of edit-global). 404 if no row at all. `skill_files` cascade via FK. `log_action("delete", ...)`. Returns 204. |
| 6 | PATCH  | `/skills/{id}/share` | `ShareToggle` | **Cycle-1 review MEDIUM fix (existence disclosure)**: Step 1, RLS-scoped pre-fetch; if no row → 404 "Skill not found" (do not leak via service-role check). Step 2, require `row.created_by == auth.uid()` else 403 "Only the creator can change sharing". Step 3, name-conflict guard (cycle-1 review MEDIUM): if `global=true`, check no existing global row with the same `lower(name)`; if `global=false`, check no existing private row with same owner + same `lower(name)`; collision → **409 "Skill name already exists"**. Step 4, service-role UPDATE wrapped in `try / except PostgrestAPIError` — on PostgREST `23505` unique-violation (race between step-3 check and the UPDATE), translate to **409 "Skill name already exists"** (cycle-2 review MEDIUM fix: never let a unique violation surface as 500). `global=true` sets `user_id = NULL`; else sets `user_id = created_by`. `log_action("share"/"unshare", ...)`. Returns the updated `SkillResponse`. |
| 7 | GET    | `/skills/{id}/export` | — | RLS-scoped fetch of skill (404 else); RLS-scoped fetch of matching `skill_files` rows. **Cycle-1 review HIGH #2 fix**: before service-role download, re-validate that each `storage_path == auth.uid()::text + '/' + skill_id::text + '/' + filename` for private skills, OR `split_part(storage_path, '/', 2) == skill_id::text` for globals (the table-level CHECK already enforces this, but we double-check at runtime to make any future RLS regression visible). Then `bytes_loader = lambda path: get_supabase_client().storage.from_('skills-files').download(path)`. Pipe through `build_skill_zip(...)`. Return `StreamingResponse(zip_bytes, media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="{name}.zip"'})`. |
| 8 | POST   | `/skills/import` | `request: Request, file: UploadFile = File(...)` | **Cycle-2 review H6 fix (true pre-body cap)**: 50 MB cap is enforced by `SkillsUploadSizeMiddleware` (defined above) BEFORE FastAPI parses the multipart body. The middleware short-circuits via Content-Length on the fast path and via streaming byte-counter on chunked uploads, returning 413 "ZIP exceeds 50 MB limit" without buffering the upload. The endpoint signature still includes `request: Request` so any future check has access. Endpoint body: `await file.read()`, then `parse_skill_zip(content)`; on `ValueError` → 413 (defense-in-depth for ZIP-bomb compressed→uncompressed expansion). For each `ParsedSkill`: if `error` set → `SkillImportItem(status="error", error=..., skipped_files=[])`. Else INSERT skill row via the user's RLS-scoped client (catch `PostgrestAPIError` 23505 → `status="error", error="Skill name already exists"`); for each parsed file in `skill.files`, **use the user's RLS-scoped client** to upload to storage at `{user_id}/{skill_id}/{filename}` and INSERT matching skill_files row (service-role only used for the `_system` seed-time path, not for normal user import). Carry `parsed.skipped_files` through to `SkillImportItem.skipped_files` so the API caller sees per-file warnings (oversized, path_traversal, outside_layout, non_ascii_path). Aggregate into `ImportResult`. `log_action("import", "skill", null, details={"created_count": N, "error_count": M})`. **EXPORT-03 closure**: this aggregation continues past errors and reports each skill's status independently. |

## Error mapping

- **401** — handled by `get_current_user`.
- **403** — explicit `HTTPException(403, "...")` (edit-global, share-non-creator).
- **404** — `HTTPException(404, "Skill not found")`.
- **409** — `HTTPException(409, "Skill name already exists")` (PostgREST `23505` / psycopg `UniqueViolation`).
- **413** — `HTTPException(413, "ZIP exceeds 50 MB limit")` (caught from `parse_skill_zip` ValueError).
- **422** — Pydantic auto-handles invalid name regex.

## Service-role escape hatches (acceptable per `database.py` patterns)

Each MUST carry an inline `# service-role: <reason> per D-P7-NN` comment for reviewer auditability (PATTERNS.md §C). **Cycle-1 review tightening: minimize the service-role surface.**

- DELETE for super_admin only (admin moderation, **D-P7-04**)
- PATCH `/skills/{id}/share` UPDATE step — flipping `user_id` to/from NULL collides with the general UPDATE RLS. Service-role is invoked ONLY after the prior steps confirm caller is creator and there's no name conflict. The pre-fetch and conflict check use the RLS-scoped client (no existence-disclosure leak).
- GET `/skills/{id}/export` storage download — required to read files for globally-shared skills the caller doesn't own. Pre-validated by the runtime path-shape check (HIGH #2 mitigation).
- **Removed from service-role** (cycle-1 fix): POST `/skills/import` storage uploads for normal user-owned imports — these now use the RLS-scoped client; service-role is only used for the seed-time `_system` path created in migration 035 (not at runtime by users).

Every service-role usage MUST carry an inline `# service-role: <reason> per D-P7-NN` comment so reviewers can audit.

## Verification (executor must run before commit)

1. **Import smoke**: `cd backend && source venv/bin/activate && python -c "from app.routers import skills; from app.main import app; print(sorted([r.path for r in app.routes if r.path.startswith('/skills')]))"`. Expect exactly 8 paths plus `/skills/{id}` (treated as one path by FastAPI; you'll see `/skills`, `/skills/{id}`, `/skills/{id}/share`, `/skills/{id}/export`, `/skills/import`).
2. **Hot-path manual test**: `uvicorn app.main:app --reload --port 8000` then:
   - `curl -X POST http://localhost:8000/skills -H "Authorization: Bearer $TOKEN" -d '{"name":"legal-review","description":"Reviews contracts...","instructions":"..."}'` → 201
   - `curl http://localhost:8000/skills` → JSON with `count` and the new row
   - `curl -X PATCH http://localhost:8000/skills/$ID/share -d '{"global": true}'` → 200, `is_global: true`
3. **Type check**: PostToolUse hook auto-runs `python -c "from app.main import app; print('OK')"` after each edit; ensure it passes.

## Atomic commit

```
feat(skills): REST API for CRUD, share, export, import (SKILL-01/03/04/05/06, EXPORT-01/02/03)
```

## Risks / open verifications

- **`get_current_user` `role` field** is populated (cycle-1 codex review confirmed); no fallback fetch needed.
- **`storage.from_('skills-files').download`** returns `bytes` synchronously per supabase-py 2.x. Confirm this matches the pinned version (`grep "supabase" backend/requirements.txt`); if it returns a response object, adapt the bytes_loader accordingly.
- **413 pre-read defense**: FastAPI's Request supports header inspection before consuming the body. The `Content-Length` check above is best-effort — clients can omit it (chunked transfer-encoding) or lie. The post-read uncompressed-sum check in `parse_skill_zip` is the second line of defense. Reviewers may suggest a streaming MultiPartParser with a hard cap; that's a Phase 8+ enhancement.
- **Multipart import is sequential**: parse → for each skill { db_insert + N storage uploads + N db inserts }. With large bulk ZIPs this can exceed Vercel's 300 s function default. Phase 7 ships sequential; Phase 8+ may revisit with background jobs.
- **PostgREST `nullsfirst` parameter** must be supported by the supabase-py version. If the client doesn't expose `nullsfirst`, fall back to `query.order("user_id.asc.nullsfirst,created_at.desc")` literal or sort `result.data` in Python by `(user_id is None, -created_at)`. Verify before authoring.
