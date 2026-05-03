---
phase: 20-harness-engine-core-gatekeeper-post-harness-file-upload-lock
plan: "06"
subsystem: file-upload
tags: [workspace, upload, file-validation, magic-bytes, tdd, security]
dependency_graph:
  requires:
    - 20-03  # config.py harness_enabled flag (informational only — NOT used as upload gate)
    - "18"   # workspace_service.py write_binary_file + validate_workspace_path + WorkspaceService base
  provides:
    - POST /threads/{thread_id}/files/upload endpoint
    - WorkspaceService.register_uploaded_file helper
  affects:
    - backend/app/routers/workspace.py
    - backend/app/services/workspace_service.py
    - 20-10  # frontend FileUploadButton.tsx POSTs to this endpoint
    - 20-07  # smoke harness Phase 1 reads uploaded binary via WorkspaceService.read_file
tech_stack:
  added:
    - fastapi.UploadFile (multipart file parsing)
  patterns:
    - Magic-byte validation (PDF: %PDF-; DOCX: PK\x03\x04 + [Content_Types].xml scan)
    - WorkspaceService instance method following register_sandbox_files template
    - Server-controlled path sanitisation (uploads/<safe_name>)
    - Feature-flag gate on settings.workspace_enabled (W6 — NOT harness_enabled per D-13)
    - Audit logging via audit_service.log_action on every successful upload
key_files:
  created:
    - backend/tests/services/test_workspace_upload.py
    - backend/tests/routers/test_workspace_upload_endpoint.py
  modified:
    - backend/app/services/workspace_service.py  # added register_uploaded_file + audit_service import
    - backend/app/routers/workspace.py            # added upload endpoint + constants + _emit_workspace_updated
decisions:
  - "W6: Upload endpoint gated on settings.workspace_enabled (Phase 18 flag) per D-13 authority — NOT settings.harness_enabled. CONTEXT.md D-13 is the authoritative locked decision. Standalone workspace upload (workspace_enabled=True, harness_enabled=False) succeeds and files land as source='upload'."
  - "register_uploaded_file calls write_binary_file then performs a second upsert with source='upload' discriminator (idempotent on conflict). write_binary_file is mocked in tests — the second upsert is the testable source='upload' gate."
  - "_emit_workspace_updated extracted as module-level function in workspace.py for testability (allows patch() without ImportError fallback dance)."
  - "D-14 honored: endpoint stores raw bytes only; text extraction is lazy at harness-phase runtime."
metrics:
  duration: "~35 minutes"
  completed: "2026-05-03"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 2
  tests_added: 15
---

# Phase 20 Plan 06: File Upload Endpoint — DOCX/PDF to Workspace Summary

Build the `POST /threads/{thread_id}/files/upload` endpoint and `WorkspaceService.register_uploaded_file` helper. Binary stored in `workspace-files` bucket with `source='upload'` discriminator; text extraction deferred to harness Phase 1 (D-14).

## One-Liner

DOCX/PDF upload endpoint with magic-byte validation, 25 MB cap, `workspace_enabled` gating (W6 per D-13), audit logging, and 15 TDD tests (6 service + 9 endpoint).

## Endpoint Contract

```
POST /threads/{thread_id}/files/upload
Content-Type: multipart/form-data
Field: file (UploadFile)

Gate: settings.workspace_enabled == True (W6 — NOT harness_enabled per D-13)
Accept: application/pdf, application/vnd.openxmlformats-officedocument.wordprocessingml.document
Max size: 25 MB
```

### Validation Pipeline (in order)

| Step | Check | Error |
|------|-------|-------|
| 1 | `settings.workspace_enabled` | 404 `workspace_disabled` |
| 2 | MIME in accepted set | 400 `wrong_mime` |
| 3 | Body size ≤ 25 MB | 413 `upload_too_large` |
| 4 | Magic bytes match MIME | 400 `magic_byte_mismatch` |
| 5 | Server path sanitisation | 400 `path_invalid` (via WorkspaceValidationError) |
| 6 | Storage write | 500 `storage_write_failed` |
| 7 | DB upsert | 500 `db_error` |

### Magic-Byte Rules

- **PDF**: first 5 bytes = `%PDF-`
- **DOCX**: first 4 bytes = `PK\x03\x04` AND `[Content_Types].xml` in first 2 KB

### Success Response (200)

```json
{
  "ok": true,
  "id": "<uuid>",
  "file_path": "uploads/<safe_name>",
  "size_bytes": 12345,
  "storage_path": "<user_id>/<thread_id>/<row_id>/<filename>",
  "mime_type": "application/pdf",
  "source": "upload"
}
```

## W6 Gating Correction — Tri-State Behavior Matrix

| `workspace_enabled` | `harness_enabled` | Upload Result |
|---------------------|-------------------|---------------|
| `False` | any | 404 `workspace_disabled` |
| `True` | `False` | 200 — file lands as `source='upload'`; no gatekeeper trigger (D-13 standalone case) |
| `True` | `True` | 200 — file visible to gatekeeper; gatekeeper may trigger harness |

**Authority:** CONTEXT.md D-13 (lines 81-83) is the locked decision. Prior plan revision had incorrectly gated on `harness_enabled`; W6 corrects this.

## register_uploaded_file Helper

Instance method on `WorkspaceService` (sibling of `register_sandbox_files`):

1. `validate_workspace_path(file_path)` — raises `WorkspaceValidationError` on invalid path
2. `write_binary_file(...)` — delegates storage; returns `{error: storage_write_failed}` on failure
3. `client.table("workspace_files").upsert({source: "upload", ...})` — sets discriminator
4. `audit_service.log_action(action="workspace_file_uploaded", resource_type="workspace_files")`

Returns `{ok: True, id, file_path, size_bytes, storage_path, mime_type, source: "upload"}` on success.

## New Tests (15 total)

### Service tests (6) — `tests/services/test_workspace_upload.py`

| # | Test | Behavior |
|---|------|----------|
| 1 | `test_register_uploaded_file_calls_write_binary_file` | Delegates to write_binary_file with correct bytes |
| 2 | `test_register_uploaded_file_upserts_with_source_upload` | DB upsert includes source='upload' |
| 3 | `test_register_uploaded_file_audit_logs` | audit_service.log_action with action='workspace_file_uploaded' |
| 4 | `test_register_uploaded_file_invalid_path_no_storage_write` | WorkspaceValidationError raised, no storage write |
| 5 | `test_register_uploaded_file_storage_write_failure` | Returns {error: storage_write_failed}, no DB insert |
| 6 | `test_register_uploaded_file_db_error` | Returns {error: db_error}, storage stays (GC deferred) |

### Endpoint tests (9) — `tests/routers/test_workspace_upload_endpoint.py`

| # | Test | Behavior |
|---|------|----------|
| 1 | `test_upload_valid_pdf_returns_200` | PDF magic bytes → 200 ok=True |
| 2 | `test_upload_valid_docx_returns_200` | DOCX magic bytes → 200 ok=True |
| 3 | `test_upload_too_large_returns_413` | >25 MB → 413 upload_too_large |
| 4 | `test_upload_pdf_mime_wrong_magic_bytes_returns_400` | PDF MIME but wrong bytes → 400 magic_byte_mismatch |
| 5 | `test_upload_wrong_mime_returns_400` | application/zip → 400 wrong_mime |
| 6 | `test_upload_workspace_disabled_returns_404` | (W6) workspace_enabled=False → 404 workspace_disabled |
| 7 | `test_upload_traversal_filename_returns_400` | Service raises WorkspaceValidationError → 400 path_invalid |
| 8 | `test_upload_success_emits_workspace_updated` | Successful upload calls _emit_workspace_updated |
| 9 | `test_upload_succeeds_when_workspace_enabled_harness_disabled` | (W6) harness_enabled=False → still 200 |

## Deviations from Plan

### Implementation difference: _emit_workspace_updated as module-level function

**Found during:** Task 2 implementation

**Plan said:** Import `emit_workspace_updated` from workspace_service with try/ImportError fallback.

**Issue:** The try/ImportError pattern makes the SSE emission untestable (Test 8 requires mocking the emit call).

**Fix:** Extracted `_emit_workspace_updated` as a module-level function in `workspace.py` that Test 8 can patch directly. In production it logs at DEBUG level; future plans can wire it to the SSE queue (Phase 18 D-10 Supabase Realtime handles the panel re-render).

**Rule:** Rule 2 (missing testability = correctness requirement for TDD plan).

**Files modified:** `backend/app/routers/workspace.py`

## Threat Surface Scan

The new endpoint and service method are entirely within the threat model defined in the plan's `<threat_model>` section. No new surface detected beyond:

| Flag | File | Description |
|------|------|-------------|
| threat_flag: multipart-upload | backend/app/routers/workspace.py | New `POST /threads/{id}/files/upload` endpoint — covered by T-20-06-01 through T-20-06-07 in plan's threat register |

All 7 threats (T-20-06-01 through T-20-06-07) are mitigated by the implementation:
- T-20-06-01 (MIME spoofing): magic-byte check on first 5 bytes (PDF) / 4 bytes + 2 KB scan (DOCX)
- T-20-06-02 (path traversal): server strips separators from filename, `validate_workspace_path` rejects `..`
- T-20-06-03 (DoS via oversized upload): 25 MB cap → 413
- T-20-06-04 (cross-tenant write): RLS via authed client + thread_id URL param
- T-20-06-05 (repudiation): `audit_service.log_action(action='workspace_file_uploaded')` on every success
- T-20-06-06 (filename injection): `rsplit("/")[-1]` + `rsplit("\\")[-1]` strip separators
- T-20-06-07 (filename PII): accepted as out-of-scope per CONTEXT.md

## Known Stubs

None — endpoint is fully functional. Text extraction is intentionally deferred to harness Phase 1 (D-14, not a stub).

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| `backend/app/services/workspace_service.py` | FOUND |
| `backend/app/routers/workspace.py` | FOUND |
| `backend/tests/services/test_workspace_upload.py` | FOUND |
| `backend/tests/routers/test_workspace_upload_endpoint.py` | FOUND |
| Commit `20643ea` (Task 1) | FOUND |
| Commit `72741ac` (Task 2) | FOUND |
| 15 tests GREEN | PASSED |
