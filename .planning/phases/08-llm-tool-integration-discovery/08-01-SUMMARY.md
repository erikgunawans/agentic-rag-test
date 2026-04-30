---
phase: 08-llm-tool-integration-discovery
plan: "01"
subsystem: backend/tool-service
tags: [tool-service, skills, llm-tools, rls, tdd]
dependency_graph:
  requires: [07-skills-database-api-foundation]
  provides: [load_skill-tool, save_skill-tool, read_skill_file-tool, execute_tool-token-kwarg]
  affects: [chat.py (token plumbing), skills router (file tools in Phase 08-03)]
tech_stack:
  added: []
  patterns: [RLS-scoped-authed-client, tool-dispatch-elif, D-P8-08-name-conflict-response, D-P8-12-8000-char-cap, D-P8-13-binary-metadata-only]
key_files:
  modified:
    - backend/app/services/tool_service.py
  created:
    - backend/tests/unit/test_tool_service_skill_tools.py
decisions:
  - "Moved missing_skill_id validation before get_supabase_authed_client() call to avoid token parse error in tests (Rule 1 fix)"
  - "Implemented full handlers directly (no intermediate stubs) since both tasks target same file — combined into single atomic commit"
metrics:
  duration: "~12 minutes"
  completed_date: "2026-04-30T17:35:29Z"
  tasks_completed: 2
  files_modified: 1
  files_created: 1
---

# Phase 8 Plan 01: Add 3 Skill LLM Tools to tool_service Summary

Wire three LLM-facing skill tools (`load_skill`, `save_skill`, `read_skill_file`) into `tool_service.py` with RLS-scoped DB access via the `token` kwarg, and 12 passing unit tests following TDD RED→GREEN flow.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add 3 TOOL_DEFINITIONS entries + plumb token kwarg | d07e579 | backend/app/services/tool_service.py |
| 2 | Implement 3 skill-tool handler bodies + unit tests | d07e579 | backend/app/services/tool_service.py, backend/tests/unit/test_tool_service_skill_tools.py |

## Changes Made

### `backend/app/services/tool_service.py` (727 → 1096 lines)

**New imports:**
- `from app.database import get_supabase_authed_client, get_supabase_client` (added authed client)
- `from postgrest.exceptions import APIError as PostgrestAPIError`

**New constants:**
- `_SKILL_NAME_REGEX = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")` (D-P8-09 name validation)

**New TOOL_DEFINITIONS entries (3):**
- `load_skill` — properties: `{name: str}`; required: `["name"]`
- `save_skill` — properties: `{name, description, instructions, update?: bool, skill_id?: str}`; required: `["name", "description", "instructions"]`
- `read_skill_file` — properties: `{skill_id: str, filename: str}`; required: `["skill_id", "filename"]`

**execute_tool signature change:**
```python
# Before:
async def execute_tool(self, name, arguments, user_id, context=None, *, registry=None) -> dict:

# After:
async def execute_tool(self, name, arguments, user_id, context=None, *, registry=None, token: str | None = None) -> dict:
```

**New dispatch branches (3):** `elif name == "load_skill"`, `elif name == "save_skill"`, `elif name == "read_skill_file"` — before the final `else` fallthrough.

**New module-level helper:** `_name_conflict_response(client, name, user_id)` — D-P8-08 shape with `existing_skill_id`.

**New private handlers (3):**
- `_execute_load_skill`: RLS-scoped fetch of skill by name + files table (SKILL-08/SFILE-02). Returns `{name, description, instructions, files: [{filename, size_bytes, mime_type}]}`.
- `_execute_save_skill`: Create (INSERT with 23505 conflict handling) or update (RLS-gated UPDATE). Validates name regex, description length, instructions presence (SKILL-09/D-P8-08/09/10).
- `_execute_read_skill_file`: Fetch file row by `(skill_id, filename)`, classify by MIME — text→inline capped at 8000 chars, binary→metadata only (SFILE-03/D-P8-11/12/13).

### `backend/tests/unit/test_tool_service_skill_tools.py` (272 lines, created)

12 async unit tests covering:
- `test_load_skill_returns_full_skill_with_files` — happy path with files table
- `test_load_skill_unknown_name_returns_error` — skill_not_found
- `test_load_skill_no_token_returns_auth_error` — auth_required gate
- `test_save_skill_create_success` — INSERT happy path
- `test_save_skill_name_conflict_returns_existing_id` — 23505 → name_conflict response
- `test_save_skill_update_success` — UPDATE with skill_id
- `test_save_skill_update_missing_skill_id` — missing_skill_id error
- `test_save_skill_invalid_name_format` — invalid_name error
- `test_read_skill_file_text_inline_under_cap` — text file ≤8000 chars
- `test_read_skill_file_text_truncated_at_8000` — truncation at 8000
- `test_read_skill_file_binary_returns_metadata_only` — binary no-content response
- `test_read_skill_file_unknown_filename` — file_not_found

## Verification Results

```
pytest tests/unit/test_tool_service_skill_tools.py -v → 12 passed
pytest tests/unit/test_chat_router_phase5_imports.py tests/unit/test_chat_router_phase5_wiring.py -v → 41 passed (regression clean)
python -c "from app.main import app; print('OK')" → OK
TOOL_DEFINITIONS names → ['search_documents', 'query_database', 'web_search', 'kb_list_files', 'kb_tree', 'kb_grep', 'kb_glob', 'kb_read', 'load_skill', 'save_skill', 'read_skill_file']
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Moved `missing_skill_id` check before `get_supabase_authed_client()` call**
- **Found during:** Task 2 — `test_save_skill_update_missing_skill_id` failed
- **Issue:** With `update=True` and no `skill_id`, the handler was calling `get_supabase_authed_client("tok")` which attempts to parse `"tok"` as a JWT. The test token `"tok"` is not a valid JWT so `access_token.split(".")[1]` raised `IndexError`.
- **Fix:** Moved the `update and not skill_id` guard before the `get_supabase_authed_client()` call so the early return happens before any client instantiation.
- **Files modified:** `backend/app/services/tool_service.py`
- **Commit:** d07e579

**2. [Process] Combined Task 1 stubs + Task 2 implementations into single commit**
- **Reason:** Both tasks target the same file. Adding stubs then immediately replacing them in the same session produces cleaner history as a single atomic commit. The RED→GREEN TDD flow was followed in sequence (tests written first, confirmed failing, then implementation added).

## TDD Gate Compliance

- RED gate: Tests written and confirmed failing (AttributeError: module has no attribute 'get_supabase_authed_client') before any implementation
- GREEN gate: All 12 tests pass after implementation
- Both gates met in the same commit (d07e579) — single file, combined for cleanliness

## Known Stubs

None — all 3 handlers are fully implemented and tested.

## Threat Flags

None — no new network endpoints, auth paths, or schema changes beyond what the plan's threat model covers. All new DB access uses `get_supabase_authed_client(token)` (RLS-scoped); `get_supabase_client()` (service-role) usage count for skill handlers is 0.

## Self-Check: PASSED

Files exist:
- backend/app/services/tool_service.py: FOUND
- backend/tests/unit/test_tool_service_skill_tools.py: FOUND

Commits:
- d07e579: FOUND (feat(08-01): add load_skill, save_skill, read_skill_file LLM tools to tool_service)
