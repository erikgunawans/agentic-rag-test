# Phase 8: LLM Tool Integration & Discovery - Context

**Gathered:** 2026-04-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire the Phase 7 skills database into the live chat pipeline. This is a **backend-only** phase. No frontend changes.

**Deliverables:**
1. `build_skill_catalog_block(user_id, token)` — async helper that fetches enabled skills and returns a formatted system-prompt block
2. `chat.py` patch — inject `skill_catalog_block` into both single-agent and multi-agent system prompt assembly
3. Three new LLM tools in `tool_service.py`: `load_skill`, `save_skill`, `read_skill_file`
4. New file endpoints in `skills.py`: `POST /skills/{id}/files`, `DELETE /skills/{id}/files/{file_id}`, `GET /skills/{id}/files/{file_id}/content`

**Out of scope (explicitly deferred):**
- Skills tab in navigation — Phase 9
- Skill editor UI — Phase 9
- File preview panel — Phase 9
- Code execution sandbox — Phase 10
- Re-ordering or ranking skills in the catalog beyond alphabetical

</domain>

<decisions>
## Implementation Decisions

### Catalog Injection (SKILL-07)

- **D-P8-01:** Append block pattern — `SYSTEM_PROMPT + pii_guidance + skill_catalog_block`. Consistent with how `pii_guidance` is already appended in `chat.py:491`. A new `build_skill_catalog_block(user_id, token)` async function fetches enabled skills via the RLS-scoped client and returns a formatted string (or `""` when there are no enabled skills).
- **D-P8-02:** When a user has **0 enabled skills**, return `""` from `build_skill_catalog_block` — nothing is appended to the system prompt. No empty section or placeholder shown.
- **D-P8-03:** Inject on **both** chat paths: single-agent (`SYSTEM_PROMPT + pii_guidance + skill_catalog`) and multi-agent (`agent_def.system_prompt + skill_catalog`). Skills work regardless of which agent path is active.
- **D-P8-04:** Skill tools (`load_skill`, `save_skill`, `read_skill_file`) are **always registered unconditionally** in `get_available_tools()`. No conditional gate based on whether the user has skills. Mirrors how `web_search` is always registered unless the API key is missing.

### Skill Catalog Format (SKILL-07)

- **D-P8-05:** Markdown table format. Block starts with `## Your Skills`, followed by the anti-speculation guardrail instruction, then a `| Skill | Description |` table. Example:
  ```
  ## Your Skills
  Call `load_skill` with the skill name when the user's request clearly
  matches a skill. Only load a skill when there's a strong match.

  | Skill | Description |
  |-------|-------------|
  | legal-review | Reviews NDA and contract clauses for compliance risks. Use when the user asks to check a contract. |
  ```
- **D-P8-06:** Cap at **20 enabled skills**, ordered alphabetically by name. At ~50 tokens per row, 20 skills ≈ 1,000 tokens maximum catalog overhead.
- **D-P8-07:** When the cap is hit, append a footer: `Showing 20 of N skills. Call load_skill with any skill name to load it directly.` — so the LLM knows additional skills exist.

### `save_skill` Tool (SKILL-09)

- **D-P8-08:** On name conflict (same `name` for this user already exists) → return an error object to the LLM with `existing_skill_id` and a hint:
  ```json
  {"error": "name_conflict",
   "message": "Skill 'legal-review' already exists.",
   "existing_skill_id": "uuid-...",
   "hint": "Use a different name, or resend with update=true and skill_id=<existing_id> to update."}
  ```
  The LLM must either suggest a different name to the user or resend with `update=true + skill_id`.
- **D-P8-09:** `save_skill` with `update=true + skill_id` can update **any skill owned by the user** (standard `user_id = auth.uid()` ownership check — same as `PATCH /skills/{id}`). The LLM receives the `existing_skill_id` from the conflict error and can use it.
- **D-P8-10:** On success → return the full skill object:
  ```json
  {"skill_id": "uuid-...", "name": "legal-review", "description": "...",
   "instructions": "...", "enabled": true, "message": "Skill saved successfully."}
  ```

### `read_skill_file` Tool (SFILE-03)

- **D-P8-11:** Text vs binary classification uses `mime_type` from the `skill_files` DB row — `mime_type.startswith("text/")` → readable inline; anything else → binary/metadata only. No content sniffing.
- **D-P8-12:** Text files are returned **inline capped at 8,000 characters**. When truncated:
  ```json
  {"filename": "legal-clauses.md", "content": "...first 8000 chars...",
   "truncated": true, "total_bytes": 45230, "message": "Content truncated at 8000 chars."}
  ```
- **D-P8-13:** Binary files return metadata only — no content, no download URL:
  ```json
  {"filename": "contract-template.pdf", "mime_type": "application/pdf",
   "size_bytes": 142000, "readable": false,
   "message": "Binary file — cannot display inline. Available as a skill resource."}
  ```

### Claude's Discretion

- `build_skill_catalog_block` lives in a new `backend/app/services/skill_catalog_service.py`.
- Skills fetched with the RLS-scoped client: `SELECT name, description FROM skills WHERE enabled = true AND (user_id = auth.uid() OR user_id IS NULL) ORDER BY name LIMIT 20`.
- `load_skill` response schema: `{name, description, instructions, files: [{filename, size_bytes, mime_type}]}`. The files table fulfills SFILE-02.
- `save_skill` input schema: `{name: str, description: str, instructions: str, update: bool = False, skill_id: str | None = None}`.
- `read_skill_file` input schema: `{skill_id: str, filename: str}` — use filename (the flat name stored in `skill_files.filename`) rather than file UUID, so the LLM can reference files from the `load_skill` response naturally.
- New file endpoints follow the existing `multipart/form-data` pattern from `POST /documents/upload`. 10 MB per-file limit (D-P7-08).
- File list is needed by both `load_skill` (to return the files table) and `GET /skills/{id}/files` — share the same service query.
- `GET /skills/{id}/files/{file_id}/content` → backend endpoint backing `read_skill_file` tool (returns file content or metadata depending on MIME type).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Primary Specification
- `docs/PRD-skill.md` — Full feature spec. Phase 8 covers §Feature 1 (LLM Tools: `load_skill`, `save_skill`) and §Feature 2 (Building-Block Files: `read_skill_file`). Progressive disclosure pattern described in §Feature 1 §How Discovery Works.
- `docs/PRD-skill.md` §Feature 2 — File tool schema and behavior. Confirms: `load_skill` includes files table (SFILE-02), `read_skill_file` reads inline (SFILE-03).

### Requirements
- `.planning/REQUIREMENTS.md` §SKILL-02 — AI-guided skill creation via `skill-creator` skill + `save_skill` tool
- `.planning/REQUIREMENTS.md` §SKILL-07 — Catalog injection into system prompt
- `.planning/REQUIREMENTS.md` §SKILL-08 — `load_skill` tool behavior
- `.planning/REQUIREMENTS.md` §SKILL-09 — `save_skill` tool behavior
- `.planning/REQUIREMENTS.md` §SFILE-01 — File upload endpoint (standalone, not ZIP import)
- `.planning/REQUIREMENTS.md` §SFILE-02 — `load_skill` includes file table
- `.planning/REQUIREMENTS.md` §SFILE-03 — `read_skill_file` tool
- `.planning/REQUIREMENTS.md` §SFILE-05 — File delete endpoint

### Roadmap
- `.planning/ROADMAP.md` §Phase 8 — Success criteria (5 criteria)

### Prior Phase Decisions (binding)
- `.planning/phases/07-skills-database-api-foundation/07-CONTEXT.md` — D-P7-01..14: ownership model, RLS policies, storage path convention `{owner_id}/{skill_id}/{flat_name}`, file size limits (D-P7-08), skill_files schema (D-P7-09), skill-creator seed (D-P7-10/11)

### Codebase Conventions
- `.planning/codebase/CONVENTIONS.md` — Router skeleton, response format, Pydantic validator usage, audit pattern
- `backend/app/routers/chat.py` — Single-agent path (~line 491) and multi-agent path (~line 437) where skill catalog must be injected
- `backend/app/services/tool_service.py` — `TOOL_DEFINITIONS` list and `execute_tool()` dispatch switch: new tools follow exact same pattern
- `backend/app/routers/skills.py` — Existing Phase 7 endpoints; new file endpoints add to this router

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `chat.py:491` — System prompt assembly block: `SYSTEM_PROMPT + pii_guidance` is the current pattern; skill catalog appended here with same concatenation.
- `chat.py:408` — `tool_service.get_available_tools(web_search_enabled=...)` call; skill tools added to `TOOL_DEFINITIONS` list alongside existing tools.
- `skills.py:218-237` (ZIP import handler) — File upload-to-Supabase-Storage pattern: `storage.from_("skills-files").upload(path, content)` + `skill_files` insert. New `POST /skills/{id}/files` endpoint reuses this exact pattern.
- `tool_service.py:247` — `get_available_tools()` conditional filtering pattern (web_search gate); skill tools are unconditional so no gate needed — just add to `TOOL_DEFINITIONS`.
- `tool_service.py:266` — `execute_tool()` name dispatch switch — add `load_skill`, `save_skill`, `read_skill_file` cases here.
- `skills.py:573-576` — `storage.from_("skills-files").download(path)` — same call used by `read_skill_file` to fetch text file bytes.

### Established Patterns
- PII guidance append pattern (`SYSTEM_PROMPT + pii_guidance`) mirrors how skill catalog will be appended — avoid touching the constant itself.
- `get_supabase_authed_client(token)` for all skill reads (RLS enforcement) vs `get_supabase_client()` for service-role operations.
- Tool error responses are plain dicts returned from `execute_tool()` — the LLM sees them as tool result content.

### Integration Points
- `chat.py` single-agent path and multi-agent path both need `build_skill_catalog_block` injected.
- `execute_tool()` in `tool_service.py` needs a `db_client` or `token` parameter passed through for skill tools that need DB access (check how `search_documents` gets `user_id`).
- `skills.py` router gets 3 new endpoints: `POST /{id}/files`, `DELETE /{id}/files/{file_id}`, `GET /{id}/files/{file_id}/content`.

</code_context>

<specifics>
## Specific Ideas

- **Catalog format confirmed:** The markdown table format with `## Your Skills` header and anti-speculation guardrail instruction (as shown in the preview) is the exact target format.
- **save_skill conflict hint:** Return `existing_skill_id` in the error response so the LLM can immediately use it in a follow-up `save_skill` with `update=true` without any extra tool calls.
- **read_skill_file input:** Use `filename` (the flat name from `skill_files.filename`) rather than a UUID so the LLM can reference files naturally from what `load_skill` returns.

</specifics>

<deferred>
## Deferred Ideas

- Skills tab in navigation — Phase 9 (SKILL-11)
- Skill editor UI with file upload button — Phase 9
- File preview panel (text file slide-in panel) — Phase 9 (SFILE-04)
- Code execution sandbox — Phase 10
- Skill ranking / ordering beyond alphabetical in catalog — future phase if needed
- Admin cap for max skills in catalog (currently hardcoded 20) — deferred until users hit the limit in practice

</deferred>

---

*Phase: 8-LLM Tool Integration & Discovery*
*Context gathered: 2026-04-30*
