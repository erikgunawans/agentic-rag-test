# PATTERNS.md — Phase 7: Skills Database & API Foundation

Maps every new file in Phase 7 to its closest existing analog so executors copy proven patterns and reviewers can spot deviations quickly.

## Path conventions in this repo (load-bearing)

- **Migrations**: `supabase/migrations/NNN_<slug>.sql` at the **repo root**, NOT `backend/supabase/migrations/`. Current head is `033_web_search_toggle.sql`. Phase 7 uses **034** (skills) and **035** (skill_files + bucket).
- **Routers**: `backend/app/routers/<resource>.py`, registered in `backend/app/main.py` after the existing `app.include_router(folders.router)` line (currently line 71) and imported in the top-of-file `from app.routers import ...` block (currently line 6).
- **Services**: `backend/app/services/<name>_service.py`.
- **Tests (API)**: `backend/tests/api/test_<resource>.py`, pytest fixtures from `backend/tests/api/conftest.py` (`auth_token`, `auth_token_2`, `admin_token`).
- **Auth deps**: `from app.dependencies import get_current_user, require_admin` (single file, not a package).
- **DB clients**: `from app.database import get_supabase_authed_client, get_supabase_client`.
- **Audit logging**: `from app.services.audit_service import log_action`.

## File-by-file analog mapping

| New file | Closest analog | What to copy verbatim | What is genuinely new |
|---|---|---|---|
| `supabase/migrations/034_skills_table_and_seed.sql` | `supabase/migrations/033_web_search_toggle.sql` (header style, transactional idempotency); `supabase/migrations/028_global_folders.sql` (NULL-user_id "global" pattern with partial unique index) | File header comment block, `BEGIN/COMMIT` discipline, RLS policy structure | Composite ownership (`user_id` + `created_by`), deterministic UUID seed via `ON CONFLICT (id) DO NOTHING` |
| `supabase/migrations/035_skill_files_table_and_bucket.sql` | `supabase/migrations/028_global_folders.sql` (FK + cascade); existing `documents` table storage-bucket policies (search project for `storage.buckets` to find a precedent) | RLS + storage bucket pattern | `(storage.foldername(name))[1] = auth.uid()::text` path-prefix policy — verify exact syntax against an existing storage policy in this repo before applying |
| `backend/app/services/skill_zip_service.py` | **No close analog** — pure stdlib service (`zipfile` + `io.BytesIO`) | Pydantic model placement at top of file (mirrors `document_tool_service.py` style); Field validators for size limits | First in-repo ZIP build/parse utility. **Reviewer attention required:** path traversal hardening, ZIP-bomb defense (max_total + max_per_file), Unicode filename normalization |
| `backend/app/routers/skills.py` | `backend/app/routers/clause_library.py` (1:1 — same RLS-scoped client per request, same `{data, count}` shape, same `is_global=true` global pattern, same audit log placement) | All endpoint scaffolding, `get_supabase_authed_client(user["token"])`, `log_action` call site, 404/409 error mapping, `?search=` + ILIKE sanitization | Share/unshare endpoint (`PATCH /skills/{id}/share`), export streaming (`StreamingResponse` with `Content-Disposition`), import multipart (`UploadFile = File(...)`) |
| `backend/app/main.py` (modified) | Existing `from app.routers import ...` line and `app.include_router(folders.router)` block | Append-only edit — no behavioral change to other routers | n/a |
| `backend/tests/api/test_skills.py` | `backend/tests/api/test_clause_library.py` (likely exists; if not, `test_documents.py`) | Fixture usage (`auth_token`, `auth_token_2`, `admin_token`), pytest async client setup, `API_BASE_URL` env reading | Multipart upload assertions (`POST /skills/import` with `files={"file": ("x.zip", data, "application/zip")}`), ZIP byte-equality round-trip |
| `backend/tests/api/test_skill_zip_service.py` | New — pure unit tests, no `httpx` client | Pydantic model construction patterns | First pure-stdlib service test in this repo |

## Patterns reused without modification

### A. Per-request RLS-scoped client (from `clause_library.py`)

```python
@router.get("")
async def list_skills(user: dict = Depends(get_current_user)):
    client = get_supabase_authed_client(user["token"])
    result = client.table("skills").select("*").execute()
    return {"data": result.data, "count": len(result.data)}
```

### B. Audit log on every mutation (from every Phase 1 router)

```python
log_action(
    user_id=user["id"],
    user_email=user["email"],
    action="create",         # create | update | delete | share | unshare | import
    resource_type="skill",
    resource_id=skill_id,
)
```

### C. Service-role escape hatch with inline justification (from `bjr.py` admin endpoints)

```python
# service-role: super_admin moderation per D-P7-04
admin_client = get_supabase_client()
admin_client.table("skills").delete().eq("id", skill_id).execute()
```

Every service-role usage in `skills.py` MUST carry a `# service-role: <reason> per D-P7-NN` comment so reviewers can audit privilege escalations.

### D. Search-filter sanitization (from `clause_library.py:53`)

```python
safe_search = search.replace(",", "").replace("(", "").replace(")", "").replace(".", " ")
query = query.or_(f"name.ilike.%{safe_search}%,description.ilike.%{safe_search}%")
```

PostgREST string filters require manual sanitization for `,()` — this is a project-wide gotcha noted in CLAUDE.md.

### E. Global-row pattern (from `028_global_folders.sql`)

`user_id IS NULL` ⇒ globally visible. Partial unique indexes split the namespace:
- `WHERE user_id IS NOT NULL` — uniqueness within owner
- `WHERE user_id IS NULL` — uniqueness across all global rows

This must be repeated verbatim for `skills`.

## Things to NOT copy

- **DO NOT** copy LangChain/LangGraph imports from anywhere — project rule (CLAUDE.md): raw SDK calls only.
- **DO NOT** mirror the `bjr.py` 25-endpoint scope — Phase 7 is intentionally narrow (8 endpoints). Phase 8 adds LLM tool integration.
- **DO NOT** introduce a new auth dependency — `get_current_user` and `require_admin` already cover both cases.
- **DO NOT** model `skill_files` with an UPDATE policy — files are immutable; replace = delete + insert. (D-P7-09 bias toward simplicity.)

## Open patterns to verify during execution (reviewer checklist)

1. **Storage RLS path-prefix syntax**: confirm `(storage.foldername(name))[1] = auth.uid()::text` works in this Supabase version by checking an existing storage policy in the repo (`grep -r 'storage.foldername' supabase/migrations/`). If absent, fall back to a known-good form before writing 035.
2. **`update_updated_at_column()` trigger function**: confirm it's defined in `supabase/migrations/001_*.sql`. If absent, plan 07-01 must add it inline rather than reuse.
3. **PyYAML dependency**: not currently in `backend/requirements.txt`. Plan 07-03 must add `PyYAML>=6.0` and bump pin per existing requirements.txt convention before importing `yaml`.
