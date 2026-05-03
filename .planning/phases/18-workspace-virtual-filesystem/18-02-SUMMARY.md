---
plan: "18-02"
phase: "18-workspace-virtual-filesystem"
status: complete
wave: 2
self_check: PASSED
---

## Summary: WorkspaceService — CRUD Service + TDD Tests

**What was built:** `workspace_service.py` (514 lines) — the single canonical service for all workspace CRUD operations. Includes 7-rule path validator, dual-storage (text inline / binary via Supabase Storage), structured errors for LLM recovery, and `register_sandbox_files()` for the sandbox bridge.

## Key Files Created

- `backend/app/services/workspace_service.py` — WorkspaceService class + WorkspaceValidationError + SandboxFileEntry
- `backend/tests/services/test_workspace_service.py` — 25 TDD unit tests (all passing)

## TDD Gate

- **RED:** `test(18-02)` — 25 failing tests committed (ModuleNotFoundError, service did not exist)
- **GREEN:** `feat(18-02)` — implementation committed, all 25 tests pass (0.97s)
- **REFACTOR:** Not needed

## What WorkspaceService Delivers

| Method | Behavior |
|--------|----------|
| `validate_workspace_path` | 7 rules: empty, >500 chars, leading-slash, backslash, control chars, trailing-slash, traversal (..) |
| `write_text_file` | Upsert with create/update detection, 1 MB cap, mime-type autodetect |
| `read_file` | Text inline / binary signed-URL (1h TTL), structured `file_not_found` error |
| `edit_file` | Exact-string replace with `not_found` + `ambiguous` guards |
| `list_files` | Ordered by `updated_at DESC` |
| `write_binary_file` | 4-segment storage path, `workspace-files` bucket |
| `register_sandbox_files()` | Idempotent upsert for plan 18-05 sandbox handover |

## Commits

| Hash | Description |
|------|-------------|
| `af01e8c` | `test(18-02)`: add failing tests — path validator + text CRUD (RED) |
| `d61accf` | `feat(18-02)`: implement workspace_service.py — path validator, text CRUD, dual-storage, structured errors (GREEN) |

## Must-Haves Verified

- [x] `validate_workspace_path` accepts good paths and rejects bad ones with structured `WorkspaceValidationError`
- [x] Writes text to `workspace_files.content`, binary to Supabase Storage with `storage_path/storage_bucket`
- [x] Returns structured-error dicts (never raises) so the LLM can recover
- [x] Uses `get_supabase_authed_client(token)` exclusively — RLS enforced

## Self-Check: PASSED
