---
plan: "18-05"
phase: "18-workspace-virtual-filesystem"
status: complete
wave: 4
self_check: PASSED
subsystem: sandbox-workspace-bridge
tags: [sandbox, workspace, bug-fix, wiring]
dependency_graph:
  requires: ["18-02", "18-03"]
  provides: ["workspace_files rows from sandbox execution"]
  affects: ["sandbox_service.py", "tool_service.py", "workspace_files table"]
tech_stack:
  added: []
  patterns: ["non-fatal async side-effect after upload loop", "feature-flag gated bridge"]
key_files:
  modified:
    - backend/app/services/sandbox_service.py
    - backend/app/services/tool_service.py
  created:
    - backend/tests/services/test_sandbox_workspace_integration.py
decisions:
  - "Used get_settings().workspace_enabled instead of module-level WORKSPACE_ENABLED constant (config pattern in this codebase)"
  - "Added token as keyword-only arg with default None to preserve backward compat in execute() and _collect_and_upload_files()"
  - "Token flows from tool_service.execute_tool() -> _execute_code() -> sandbox_service.execute() -> _collect_and_upload_files()"
  - "mime_type=None in SandboxFileEntry entries — workspace_service falls back to application/octet-stream (per plan spec)"
metrics:
  duration: "~3 minutes"
  completed_at: "2026-05-03T01:05Z"
  tasks_completed: 2
  files_changed: 3
---

# Phase 18 Plan 05: Sandbox-to-Workspace Bridge Summary

**One-liner:** Sandbox file uploads now persist as `workspace_files` rows via `register_sandbox_files()` gated by `workspace_enabled` flag — fixes the v1.1 disappearing-link bug.

## What Was Built

The v1.1 sandbox flow uploaded files to `sandbox-outputs` bucket and returned signed URLs, but never created `workspace_files` rows. This meant `GET /threads/{id}/files` never showed sandbox outputs. This plan wires the bridge.

### Changes

**`sandbox_service.py`** — `_collect_and_upload_files()`:
- Added `token: str | None = None` keyword arg (propagated from `execute()`)
- After the upload loop: when `workspace_enabled=True` AND `token` is set AND `uploaded` is non-empty, calls `register_sandbox_files(token, thread_id, files)` with `SandboxFileEntry` objects mapping each uploaded file
- Non-fatal: wrapped in `try/except`, logs at WARNING level on failure — sandbox tool result is never broken by workspace registration errors
- Feature-flag kill-switch: `get_settings().workspace_enabled=False` is byte-identical to v1.1

**`sandbox_service.py`** — `execute()`:
- Added `token: str | None = None` keyword arg
- Passes token to `_collect_and_upload_files()`

**`tool_service.py`** — `_execute_code()`:
- Added `token: str | None = None` keyword arg
- Passes token to `get_sandbox_service().execute()`

**`tool_service.py`** — `execute_tool()`:
- Passes `token=token` when dispatching to `_execute_code()` (token already in scope from Phase 8)

### Integration Tests (6 PASS)

| Test | Behavior |
|------|----------|
| test_collect_and_upload_calls_register_sandbox_files | register_sandbox_files called once with correct token/thread_id/2 files |
| test_uploaded_shape_preserved_after_workspace_registration | v1.1 shape (filename, size_bytes, signed_url, storage_path) unchanged |
| test_workspace_disabled_skips_register | workspace_enabled=False → register NOT called (kill-switch verified) |
| test_register_failure_is_non_fatal | RuntimeError from register → still returns uploaded (non-fatal) |
| test_empty_file_list_skips_register | empty uploaded → register NOT called |
| test_sandbox_file_entry_filenames_not_mutated | SandboxFileEntry.filename matches raw sandbox listing (T-18-19) |

## Token Propagation

The caller chain already had `token` at the `execute_tool()` level (Phase 8). It was NOT previously passed to `_execute_code()`. This plan added it all the way down. No architectural change — additive only.

## Commits

| Hash | Description |
|------|-------------|
| `ccec589` | `feat(18-05)`: wire register_sandbox_files into sandbox_service after upload loop |
| `3ecf705` | `test(18-05)`: add 6 integration tests for sandbox → workspace bridge (WS-05) |

## Deviations from Plan

### Config access pattern

**[Rule 2 - Auto-adapted]** Plan referenced `from app.config import WORKSPACE_ENABLED` (module-level constant), but the codebase uses `get_settings().workspace_enabled` (Pydantic Settings object). Used `get_settings().workspace_enabled` to match the established pattern throughout the codebase.

No other deviations — plan executed as specified.

## Must-Haves Verified

- [x] `_collect_and_upload_files` calls `register_sandbox_files` after upload loop
- [x] Returned `uploaded` shape unchanged (v1.1 backward compat)
- [x] `workspace_enabled=False` → register NOT called (byte-identical to v1.1)
- [x] `register_sandbox_files` failure → non-fatal, warning logged, uploaded returned
- [x] Empty file list → register NOT called
- [x] `SandboxFileEntry.filename` = raw sandbox filename (no mutation)
- [x] All 6 integration tests PASS
- [x] No regressions in pre-existing tests (5 pre-existing failures are NOT caused by this plan — they predate it due to Phase 14 bridge_token tuple return change)

## Known Stubs

None — all workspace entries are fully wired. `mime_type=None` in SandboxFileEntry is intentional per plan spec ("could detect via filename ext later"); workspace_service fills `application/octet-stream` as fallback for storage ops.

## Threat Flags

None — no new trust boundaries introduced. The workspace registration runs server-side using the user's own auth token (RLS enforced). T-18-19 (filename traversal) mitigated by `register_sandbox_files` which calls `validate_workspace_path("sandbox/{filename}")` — tested via existing workspace service tests.

## Self-Check: PASSED
