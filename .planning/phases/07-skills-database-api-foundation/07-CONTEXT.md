# Phase 7: Skills Database & API Foundation - Context

**Gathered:** 2026-04-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Establish the skills data model, Supabase RLS policies, Supabase Storage bucket for skill files, and complete REST API for skills CRUD, sharing, and ZIP export/import. All subsequent phases (8–11) build on this foundation.

**Deliverables:**
1. Migration 034: `skills` table with RLS, seed `skill-creator` global skill
2. Migration 035: `skill_files` table with RLS, `skills-files` storage bucket policy
3. `backend/app/routers/skills.py`: POST/GET/PATCH/DELETE, share toggle, export, import
4. `backend/app/services/skill_zip_service.py`: ZIP export/import utility (SKILL.md format)

**Out of scope (explicitly deferred):**
- LLM tool wiring (`load_skill`, `save_skill`, `read_skill_file`) — Phase 8
- Skill file upload/delete UI — Phase 8
- Skills tab in navigation — Phase 9
- Skill catalog injection into system prompt — Phase 8
- Code execution sandbox — Phase 10

</domain>

<decisions>
## Implementation Decisions

### Ownership & Sharing Model

- **D-P7-01:** `skills` table schema: `user_id UUID REFERENCES auth.users NULL` (current owner — NULL means global/shared) + `created_by UUID REFERENCES auth.users NULL` (immutable creator — NULL means system-seeded). For user-created skills, both are set on creation. Sharing sets `user_id = NULL`; unsharing sets `user_id = created_by`. This enables "toggle back" while keeping global skills distinguishable.
- **D-P7-02:** Any authenticated user can share their own private skill to global via `PATCH /skills/{id}/share`. Only `created_by = auth.uid()` can unshare (set `user_id` back to `created_by`). No admin-only gate on sharing — community-contributed model.
- **D-P7-03:** Editing a global skill (user_id IS NULL) is blocked for everyone including the creator. `PATCH /skills/{id}` returns `403 "Cannot edit a global skill — unshare it first"`. Creator must call `PATCH /skills/{id}/share` to unshare before editing.
- **D-P7-04:** `super_admin` can `DELETE /skills/{id}` for any skill regardless of `created_by` — moderation escape hatch. Matches the admin-bypass pattern in `require_admin` dependency.
- **D-P7-05:** RLS policies:
  - SELECT: `user_id = auth.uid() OR user_id IS NULL` (own skills + all global skills)
  - INSERT: `created_by = auth.uid() AND user_id = auth.uid()` (user-created skills always start owned)
  - UPDATE (general): `user_id = auth.uid()` (own skills only; global blocked at row level)
  - UPDATE (share/unshare endpoint): `created_by = auth.uid()` (creator can toggle even when user_id differs)
  - DELETE: `created_by = auth.uid() OR (auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin'`

### ZIP Import File Scope

- **D-P7-06:** Phase 7 includes the `skill_files` table + `skills-files` Supabase Storage bucket. ZIP import stores files from `scripts/`, `references/`, `assets/` subdirs. Phase 8 adds the UI to view, upload, and delete skill files — the data layer must exist in Phase 7 so imported files aren't silently dropped.
- **D-P7-07:** Supabase Storage bucket: `skills-files` (private, no public access). Storage path: `{owner_id}/{skill_id}/{filename}` where `owner_id = user_id` if private, or `owner_id = created_by` if global (user_id is NULL). This keeps path non-NULL in all cases.
- **D-P7-08:** File size limits: 10 MB per individual file (files exceeding this are skipped and reported in results), 50 MB total ZIP cap (EXPORT-03). Files dropped due to size limit are included as `{status: "skipped", error: "File exceeds 10 MB limit"}` in import results.
- **D-P7-09:** `skill_files` table columns: `id UUID PK DEFAULT gen_random_uuid()`, `skill_id UUID NOT NULL REFERENCES skills(id) ON DELETE CASCADE`, `filename TEXT NOT NULL`, `size_bytes BIGINT NOT NULL`, `mime_type TEXT`, `storage_path TEXT NOT NULL`, `created_at TIMESTAMPTZ DEFAULT now()`, `created_by UUID REFERENCES auth.users`. RLS: SELECT inherits from parent skill visibility; INSERT/DELETE gated on skill's `user_id = auth.uid()` (own skills only — global skill files can't be modified by other users).

### Seed Skill-Creator

- **D-P7-10:** `skill-creator` global skill is seeded via SQL INSERT in migration 034. `user_id = NULL` (global), `created_by = NULL` (system-seeded, no human owner). It is enabled by default (`enabled = true`).
- **D-P7-11:** Instructions are LexCore-tailored: covers naming conventions (lowercase-hyphenated identifier, max 64 chars, no consecutive hyphens), description authoring (third-person, what-it-does + when-to-use, 20–1024 chars), instruction conciseness (only context the LLM doesn't already know), legal-domain skill examples (e.g., `reviewing-nda-clauses`, `summarizing-board-decisions`). Instructions end with explicit `save_skill` tool-call guidance: after collaborating with the user on name/description/instructions, summarize the proposed skill and call `save_skill` to persist it.

### Bulk Import Response Schema

- **D-P7-12:** `POST /skills/import` response:
  ```json
  {
    "created_count": 2,
    "error_count": 1,
    "results": [
      {"name": "legal-review", "status": "created", "skill_id": "uuid-..."},
      {"name": "analyze-sales", "status": "created", "skill_id": "uuid-..."},
      {"name": "bad-skill!!", "status": "error", "error": "Invalid name format"}
    ]
  }
  ```
  Pydantic response model: `ImportResult(created_count, error_count, results: list[SkillImportItem])` where `SkillImportItem(name, status: Literal['created', 'error', 'skipped'], skill_id: str | None, error: str | None)`.
- **D-P7-13:** Naming conflict = same `name` for that `user_id` (case-insensitive match). Action: error + skip. Error: `"Skill name already exists"`. No auto-rename. Consistent with EXPORT-03: "naming conflicts reported as errors without blocking other skills in a bulk import."
- **D-P7-14:** `POST /skills/import` accepts `multipart/form-data` with a `file` field containing the ZIP. Consistent with `POST /documents/upload` FormData pattern; `apiFetch` already skips `Content-Type` for FormData.

### Claude's Discretion

- Migration numbering: 034 for `skills` table + seed skill-creator; 035 for `skill_files` table + storage bucket policy. Keep them separate to make rollback cleaner.
- Name validation: `^[a-z][a-z0-9]*(-[a-z0-9]+)*$` (lowercase start, alphanumeric segments, single hyphens, max 64 chars). Enforced via Pydantic `@field_validator`.
- `skill_zip_service.py` uses Python stdlib `zipfile` — no new dependencies.
- Index on `skills(user_id, name)` for name-conflict check on import; partial index on `skills(name) WHERE user_id IS NULL` for global skill lookups.
- For `GET /skills/{id}/export`, response: `StreamingResponse` with `Content-Type: application/zip` and `Content-Disposition: attachment; filename="{name}.zip"`. Same pattern as no existing router, but follows FastAPI's `StreamingResponse` pattern used in chat SSE.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Primary Specification
- `docs/PRD-skill.md` — Full feature spec for all 5 features (Skills, Files, Sandbox, Export/Import, Memory). SKILL.md frontmatter format defined in §Feature 4. Backend API table in §Feature 1. Phase 7 covers Features 1 (backend), 2 (data layer), 4.
- `docs/PRD-skill.md` §Feature 4 — SKILL.md format: `name`, `description`, `license`, `compatibility`, `metadata` (key-value) in YAML frontmatter, plus `# Instructions` markdown body. ZIP structure: `skill-name/SKILL.md + scripts/ + references/ + assets/`.

### Requirements
- `.planning/REQUIREMENTS.md` §SKILL-01, 03–06, 10 — Skills CRUD + share + seed requirements
- `.planning/REQUIREMENTS.md` §EXPORT-01–03 — ZIP export/import requirements

### Roadmap
- `.planning/ROADMAP.md` §Phase 7 — Success criteria (5 criteria, Phase 7 section)

### Codebase Conventions
- `.planning/codebase/CONVENTIONS.md` — Router skeleton, migration pattern, audit pattern, response format (`{"data": [...], "count": N}`), Pydantic validator usage

### Closest Analog Routers (read before writing new router)
- `backend/app/routers/clause_library.py` — Most similar existing pattern: list+CRUD with `is_global` visibility, RLS-scoped client, `log_action`, `{"data": [...], "count": N}` response
- `backend/app/routers/documents.py` — multipart FormData upload pattern to reference for `POST /skills/import`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/app/dependencies.py`: `get_current_user` (auth, used on every endpoint), `require_admin` (for admin-delete bypass)
- `backend/app/database.py`: `get_supabase_authed_client(token)` for all RLS-scoped ops; `get_supabase_client()` only for service-role operations (e.g., admin delete, seed skill read)
- `backend/app/services/audit_service.py`: `log_action(user_id, user_email, action, resource_type, resource_id)` — call on every mutation
- `backend/app/routers/clause_library.py`: `{"data": result.data, "count": len(result.data)}` list response; RLS-scoped client pattern; `is_global` visibility combining owned + shared rows

### Established Patterns
- Router skeleton: `router = APIRouter(prefix="/skills", tags=["skills"])` + Pydantic request/response models at top of file
- Response format: `{"data": [...], "count": N}` for list endpoints
- File upload: `UploadFile` + `FormData` pattern from `documents.py` — `apiFetch` skips `Content-Type` for FormData
- Error handling: `HTTPException(403, "detail")` for auth failures; `HTTPException(404, "Skill not found")` for missing resources; `HTTPException(409, "Skill name already exists")` for uniqueness violations on single-create
- Migration template: `backend/supabase/migrations/033_web_search_toggle.sql` as most recent reference for format; always include `CREATE POLICY` blocks and `ALTER TABLE ... ENABLE ROW LEVEL SECURITY`

### Integration Points
- `backend/app/main.py` — register `from app.routers import skills; app.include_router(skills.router)` (lines 36-56)
- `backend/app/config.py` — no new env vars needed for Phase 7 (Supabase bucket creation is a Supabase-side operation; bucket name can be a constant in the router or config)
- Supabase Storage: new `skills-files` bucket must be created (include in migration via Supabase Storage API or document as setup step)
- Next migration numbers: 034 (skills table), 035 (skill_files table + bucket policy)

</code_context>

<specifics>
## Specific Ideas

- SKILL.md frontmatter exact format (from PRD §Feature 4):
  ```yaml
  ---
  name: analyzing-sales-data
  description: Analyzes sales data and generates reports...
  license: MIT
  compatibility: agentskills-v1
  metadata:
    author: jane
    version: "1.0"
  ---
  ```
- Import supports both single-skill ZIPs (`SKILL.md` at root or in a named directory) and bulk ZIPs (multiple directories each with their own `SKILL.md`). The `skill_zip_service` parser must handle both layouts.
- Storage path for global skills uses `created_by` as owner prefix (not user_id which is NULL). For system-seeded global skills (`created_by = NULL`), use a fixed path prefix like `_system/{skill_id}/{filename}`.
- Import result schema uses `status: 'created'|'error'|'skipped'` — `skipped` covers per-file size violations inside an otherwise valid skill import.
- `PATCH /skills/{id}/share` body: `{"global": true}` to share, `{"global": false}` to unshare. Returns the updated skill object.

</specifics>

<deferred>
## Deferred Ideas

- **Skill catalog injection into system prompt** — Phase 8 (SKILL-07). Phase 7 only builds the DB and API; the LLM doesn't know about skills yet.
- **`load_skill`, `save_skill`, `read_skill_file` tools** — Phase 8 (SKILL-08, SKILL-09, SFILE-03).
- **Skill file upload/delete UI** — Phase 9 (SFILE-01, SFILE-04, SFILE-05). Phase 7 provides the data layer; the upload/manage UI comes in Phase 9.
- **`GET /skills/{id}/files/{file_id}/content` endpoint** — Phase 8 (SFILE-02 file table in `load_skill` response, SFILE-03 read tool). Infrastructure exists in Phase 7 but the endpoint for reading file content belongs with the LLM wiring phase.
- **Skill analytics / versioning** — Explicitly deferred in REQUIREMENTS.md §Future Requirements.

</deferred>

---

*Phase: 7-Skills Database & API Foundation*
*Context gathered: 2026-04-29*
