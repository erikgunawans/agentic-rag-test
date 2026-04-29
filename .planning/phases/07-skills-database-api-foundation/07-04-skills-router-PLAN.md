---
id: 07-04
phase: 7
title: skills.py router — CRUD + share + export + import
wave: 3
depends_on: [07-01, 07-02, 07-03]
closes: [SKILL-01, SKILL-03, SKILL-04, SKILL-05, SKILL-06, EXPORT-01, EXPORT-02, EXPORT-03]
estimated_atomic_commits: 1
---

# 07-04-PLAN — `skills.py` router

## Goal

Eight FastAPI endpoints under `/skills` covering create, list, read, update, delete, share/unshare, export, and import. Mirrors `clause_library.py` for RLS-scoped CRUD; adds three new patterns (share toggle, ZIP streaming, multipart import). Closes 8 of Phase 7's 9 requirements (SKILL-10 is closed by the migration in 07-01).

## Closes

- SKILL-01 (create), SKILL-03 (list with search/filter), SKILL-04 (update), SKILL-05 (delete), SKILL-06 (share/unshare), EXPORT-01 (router-side export), EXPORT-02 (router-side import multipart), EXPORT-03 (admin-moderation delete).

## Files to create / modify

- `backend/app/routers/skills.py` (new)
- `backend/app/main.py` (modified)
  - Line 6: append `, skills` to the `from app.routers import ...` block.
  - After current line 71 (`app.include_router(folders.router)`): add `app.include_router(skills.router)`.

## Pydantic request/response models (top of file)

```python
import re
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator
from app.dependencies import get_current_user, require_admin
from app.database import get_supabase_authed_client, get_supabase_client
from app.services.audit_service import log_action
from app.services.skill_zip_service import build_skill_zip, parse_skill_zip, ImportResult, SkillImportItem

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
| 2 | GET    | `/skills` | `?search=` `?enabled=` `?limit=50` `?offset=0` | RLS-scoped query. Sanitize `search` via `replace(",","").replace("(","").replace(")","").replace("."," ")` before ILIKE (matches `clause_library.py:53`). Order by `is_global DESC, created_at DESC`. Return `{"data": [SkillResponse...], "count": N}`. |
| 3 | GET    | `/skills/{id}` | — | RLS-scoped fetch; 404 if no row. |
| 4 | PATCH  | `/skills/{id}` | `SkillUpdate` | Pre-fetch (RLS-scoped). If `user_id IS NULL` → **403 "Cannot edit a global skill — unshare it first"** (D-P7-03). Else RLS-scoped UPDATE. `log_action("update", ...)`. |
| 5 | DELETE | `/skills/{id}` | — | If `user["role"] == "super_admin"` → service-role client deletes ANY (D-P7-04, EXPORT-03 for admin moderation). Else RLS-scoped DELETE (created_by enforced by RLS). 404 if not found. `skill_files` cascade via FK. `log_action("delete", ...)`. Returns 204. |
| 6 | PATCH  | `/skills/{id}/share` | `ShareToggle` | Pre-fetch (RLS-scoped or service-role for share-already-global case); require `created_by = auth.uid()` else 403. If `global=true` → service-role UPDATE setting `user_id = NULL`. Else → service-role UPDATE setting `user_id = created_by`. `log_action("share"/"unshare", ...)`. Returns the updated `SkillResponse`. |
| 7 | GET    | `/skills/{id}/export` | — | RLS-scoped fetch of skill; RLS-scoped fetch of `skill_files` rows. For each file, `bytes_loader = lambda path: get_supabase_client().storage.from_('skills-files').download(path)`. Pipe through `build_skill_zip(skill_dict, files_list, bytes_loader)`. Return `StreamingResponse(zip_bytes, media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="{name}.zip"'})`. |
| 8 | POST   | `/skills/import` | `file: UploadFile = File(...)` | Read body. Call `parse_skill_zip(content)`; on `ValueError` ("exceeds 50 MB") → 413. For each `ParsedSkill`: if `error` set → `SkillImportItem(status="error", error=...)`. Else INSERT skill row (catch unique_violation → `error: "Skill name already exists"`); for each parsed file, upload to storage at `{user_id}/{skill_id}/{filename}` via service-role and INSERT skill_files row. Aggregate into `ImportResult`. `log_action("import", "skill", null, details={"created_count": N})`. |

## Error mapping

- **401** — handled by `get_current_user`.
- **403** — explicit `HTTPException(403, "...")` (edit-global, share-non-creator).
- **404** — `HTTPException(404, "Skill not found")`.
- **409** — `HTTPException(409, "Skill name already exists")` (PostgREST `23505` / psycopg `UniqueViolation`).
- **413** — `HTTPException(413, "ZIP exceeds 50 MB limit")` (caught from `parse_skill_zip` ValueError).
- **422** — Pydantic auto-handles invalid name regex.

## Service-role escape hatches (acceptable per `database.py` patterns)

Each MUST carry an inline `# service-role: <reason> per D-P7-NN` comment for reviewer auditability (PATTERNS.md §C):

- DELETE for super_admin (admin moderation, **D-P7-04**, **EXPORT-03**)
- PATCH `/skills/{id}/share` toggling — flipping `user_id` to/from NULL collides with the general UPDATE RLS, so we go service-role after a manual `created_by = auth.uid()` check
- POST `/skills/import` storage uploads when the storage path uses `_system` or a global-skill creator folder
- GET `/skills/{id}/export` storage downloads (the export endpoint must be able to download files for skills the user can SELECT but doesn't own — globals)

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

- **`get_current_user` `role` field**: `clause_library.py` uses `user["id"]`/`user["email"]`/`user["token"]`. Confirm `user["role"]` is also populated by `get_current_user` (CLAUDE.md says it returns `{id, email, token, role}`); if absent, fetch role inline from `user_profiles`.
- **`storage.from_('skills-files').download`**: returns `bytes` synchronously per supabase-py 2.x. Confirm this is the actual signature in the repo's pinned version (`grep "supabase" backend/requirements.txt`); if it returns a response object, adapt the bytes_loader accordingly.
- **413 handling for upload body itself**: FastAPI/Uvicorn defaults may accept >50 MB before the parser sees it. Confirm Railway/Uvicorn config has no looser body size limit, or add an explicit `Content-Length` check before reading.
- **Multipart import is sequential**: parse → for each skill { db_insert + N storage uploads + N db inserts }. With large bulk ZIPs this can exceed Vercel's 300 s function default. Phase 7 ships sequential; Phase 8+ may revisit with background jobs.
