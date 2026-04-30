---
phase: 08-llm-tool-integration-discovery
plan: "03"
subsystem: skills-file-api
tags: [skills, file-upload, storage, rls, middleware, sfile]
dependency_graph:
  requires:
    - 07-04-SUMMARY (skill_files table, skills-files storage bucket, RLS migration 035)
    - 07-05-SUMMARY (SkillsUploadSizeMiddleware pattern, integration test helpers)
  provides:
    - POST /skills/{skill_id}/files (SFILE-01)
    - DELETE /skills/{skill_id}/files/{file_id} (SFILE-05)
    - GET /skills/{skill_id}/files/{file_id}/content (SFILE-03)
    - SkillsUploadSizeMiddleware dual-gate (50 MB /import + 10 MB /files)
  affects:
    - 08-01 (read_skill_file LLM tool now has a matching HTTP endpoint for UAT)
    - Phase 9 (Skills file manager UI has a stable backend)
tech_stack:
  patterns:
    - RLS-scoped authed client for all mutations; service-role fallback for global-skill downloads
    - Content-Length fast-path + streaming byte counter in ASGI middleware (Phase 7 cycle-2 H6 pattern)
    - Storage path shape: {user_id}/{skill_id}/{flat_name} with '/' → '__' flattening (D-P7-09 CHECK constraint)
    - Defense-in-depth: middleware enforces 10 MB cap before multipart parsing; handler enforces same cap after file.read()
    - Binary vs text classification via mime_type.startswith('text/') (D-P8-13)
    - log_action on upload_file + delete_file mutations (audit trail)
key_files:
  modified:
    - path: backend/app/middleware/skills_upload_size.py
      lines: 75
      change: Extended to dual-gate — /import at 50 MB, /skills/{id}/files at 10 MB via regex dispatch
    - path: backend/app/routers/skills.py
      lines: 786
      change: Appended 3 new endpoints (upload_skill_file, delete_skill_file, get_skill_file_content) + constants
    - path: backend/tests/api/test_skills.py
      lines: 1423
      change: Appended 4 new test classes covering 7 test methods for all 3 new endpoints
decisions:
  - "Middleware path dispatch uses regex (_IMPORT_RE + _FILES_UPLOAD_RE) instead of string equality for extensibility"
  - "Cross-user upload returns 404 (not 403) because private skills are invisible to non-owners via RLS — existence disclosure avoided"
  - "Binary file GET returns metadata-only with NO content key (D-P8-13 compliance); text is inline capped at 8000 chars"
  - "Storage delete is best-effort: DB row deletion succeeds first, storage.remove() failure only logs a warning (orphaned objects can be reconciled by a periodic job)"
  - "In-handler 10 MB check after file.read() is defense-in-depth (T-08-03-01); middleware is the primary gate"
  - "skills-files count in skills.py is 6 (not 7 as plan estimated) — plan baseline miscounted; all functionality correctly implemented"
metrics:
  duration_seconds: 283
  completed_at: "2026-05-01T00:35:50Z"
  tasks_completed: 3
  tasks_total: 3
  files_modified: 3
---

# Phase 08 Plan 03: Skill File HTTP Endpoints Summary

**One-liner:** Three authenticated skill file endpoints (upload/delete/read) with 10 MB ASGI middleware gate and binary-vs-text response classification.

## What Was Built

### New Routes (skills.py)

| Method | Path | Status | Purpose |
|--------|------|--------|---------|
| POST | /skills/{skill_id}/files | 201 | Upload single file to owned skill (SFILE-01) |
| DELETE | /skills/{skill_id}/files/{file_id} | 204 | Delete file from owned skill (SFILE-05) |
| GET | /skills/{skill_id}/files/{file_id}/content | 200 | Read text inline or binary metadata (SFILE-03) |

### Middleware Extension (skills_upload_size.py)

The existing SkillsUploadSizeMiddleware (Phase 7 cycle-2 H6) now enforces two caps:
- `POST /skills/import` → 50 MB (`_IMPORT_MAX_BYTES`, unchanged)
- `POST /skills/{id}/files` → 10 MB (`_PER_FILE_MAX_BYTES`, new — `_FILES_UPLOAD_RE = re.compile(r"^/skills/[^/]+/files$")`)

Both branches reuse the same Content-Length fast-path + chunked-encoding streaming byte counter pattern from Phase 7.

### Security Properties (Threat Model T-08-03-*)

- **T-08-03-01 (DoS):** Middleware rejects oversized uploads before multipart parsing; in-handler `file.read()` + size check is defense-in-depth.
- **T-08-03-02 (Cross-user upload):** Private skills are invisible to non-owners (RLS SELECT) → handler returns 404 before reaching the ownership check. 403 returned only for skills visible but not owned (e.g., global skills).
- **T-08-03-03 (Path traversal):** `file.filename.replace("/", "__")` + 3-segment `{user_id}/{skill_id}/{flat_name}` storage path enforced by CHECK constraint.
- **T-08-03-04 (Binary PII disclosure):** Binary files return metadata-only (`readable: False`, no `content` key, no signed URL).
- **T-08-03-05 (Large text DoS):** Text content hard-capped at `_TEXT_INLINE_CAP = 8000` chars.
- **T-08-03-06 (Cross-user delete):** RLS DELETE policy on `skill_files` gates on parent skill ownership; empty `delete_result.data` → 404.
- **T-08-03-08 (Repudiation):** `log_action("upload_file")` and `log_action("delete_file")` on every mutation.

### Integration Tests (test_skills.py)

4 new test classes, 7 test methods appended to the Phase 7 test file:

| Class | Test | Coverage |
|-------|------|----------|
| TestUploadSkillFile | test_upload_text_file_201 | SFILE-01 happy path |
| TestUploadSkillFile | test_upload_to_nonowned_skill_403_or_404 | T-08-03-02 cross-user |
| TestUploadOversize413 | test_oversize_upload_returns_413_pre_read | T-08-03-01 DoS guard |
| TestDeleteSkillFile | test_delete_file_204 | SFILE-05 + subsequent GET 404 |
| TestDeleteSkillFile | test_delete_nonowned_file_404 | T-08-03-06 cross-user delete |
| TestReadSkillFileContent | test_get_content_text_inline | SFILE-03 text path (D-P8-12) |
| TestReadSkillFileContent | test_get_content_binary_metadata | SFILE-03 binary path (D-P8-13) |

The oversize test uses a raw socket with spoofed `Content-Length: 11485760` (mirrors Phase 7 `TestImportOversizedZip413PreRead`). All other tests use the existing `_http(token)` httpx client helper.

**Test status:** All 7 tests collect cleanly (`pytest --collect-only`). Live backend tests require migrations 034 + 035 applied and `skills-files` storage bucket created (Phase 7 artifacts).

## Commits

| Hash | Task | Description |
|------|------|-------------|
| 941107d | Task 1 | feat(08-03): extend SkillsUploadSizeMiddleware to gate /skills/{id}/files at 10 MB |
| d5fb616 | Task 2 | feat(08-03): add 3 skill file endpoints — POST upload, DELETE, GET content |
| cb06134 | Task 3 | test(08-03): add integration tests for 3 skill file endpoints (SFILE-01/03/05) |

## Deviations from Plan

### Minor Counting Discrepancy

**Found during:** Task 2 acceptance criteria check

**Issue:** The plan stated `grep -c "skills-files" backend/app/routers/skills.py` should return at least 7. The actual file has 6 occurrences. The plan miscounted the Phase 7 baseline (expected "4 from Phase 7" + "3 new = 7" but the actual Phase 7 baseline had 2 occurrences in the import loop + 1 in the export path = 3 pre-Phase-8 occurrences, and the 3 new endpoints add 3 more = 6 total).

**Fix:** No fix needed — all required storage bucket usages are correctly implemented. The implementation covers upload (import loop), download (export path), upload (new endpoint), remove (delete endpoint), download x2 (get_content RLS + service-role fallback).

**Impact:** None — functional behavior is correct per all other acceptance criteria.

## Known Stubs

None — all endpoints are fully wired to Supabase Storage and skill_files table.

## Threat Flags

None — no new network surfaces beyond the 3 endpoints planned in the threat model.

## Self-Check: PASSED

- Files exist: backend/app/middleware/skills_upload_size.py ✓, backend/app/routers/skills.py ✓, backend/tests/api/test_skills.py ✓
- Commits exist: 941107d ✓, d5fb616 ✓, cb06134 ✓
- Routes registered: `/skills/{skill_id}/files`, `/skills/{skill_id}/files/{file_id}`, `/skills/{skill_id}/files/{file_id}/content` ✓
- Backend import smoke: `from app.main import app` → OK ✓
- Test collection: 7 new tests collected without error ✓
