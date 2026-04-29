---
phase: 07
plan: "05"
subsystem: skills-api-tests
tags: [test, integration, skills, api, rls, storage, zip, export, import]
dependency_graph:
  requires: [07-04]
  provides: [phase-7-verification-gate]
  affects: [supabase/migrations/035_skill_files_table_and_bucket.sql]
tech_stack:
  added: [httpx-integration-tests, raw-socket-testing]
  patterns: [httpx-live-backend-testing, supabase-auth-in-tests, raw-socket-content-length]
key_files:
  created:
    - backend/tests/api/test_skills.py
  modified:
    - supabase/migrations/035_skill_files_table_and_bucket.sql
decisions:
  - "Use httpx against live local backend (not TestClient) — tests exercise full middleware stack including SkillsUploadSizeMiddleware"
  - "Use raw socket for test 13 (pre-read 413) — h11 enforces Content-Length match so httpx cannot fake it"
  - "Apply migrations 034+035 to live Supabase via supabase db query --linked (tables were not yet applied)"
metrics:
  duration_seconds: 1191
  completed_date: "2026-04-29"
  tasks_completed: 1
  files_created: 1
  files_modified: 1
---

# Phase 7 Plan 05: API integration tests for Phase 7 Summary

## One-liner

29 integration tests (23 logical cases) covering all 9 Phase 7 requirements via live httpx calls with fixed storage RLS policy ambiguous column reference.

## What Was Built

- `backend/tests/api/test_skills.py` — 23 integration test classes (29 pytest cases including parametrize variants) testing every Phase 7 endpoint against a live local backend
- Fixed storage INSERT/DELETE policy in `035_skill_files_table_and_bucket.sql` — bare `name` reference inside EXISTS subquery was resolved by PostgreSQL as `skills.name` (wrong), not `storage.objects.name` (intended), causing all skill file uploads to fail with RLS denial

## Requirements Closed

| Requirement | Test | Description |
|-------------|------|-------------|
| SKILL-10 | TestSeedSkillCreatorExists | seed `skill-creator` row visible to any user |
| SKILL-01 | TestCreateReadUpdateDeleteCycle, TestCreateInvalidName422, TestCreateDuplicateName409 | full CRUD + name validation |
| SKILL-03 | TestCreateReadUpdateDeleteCycle | GET single skill |
| SKILL-04 | TestCreateReadUpdateDeleteCycle | PATCH update |
| SKILL-05 | TestCreateReadUpdateDeleteCycle | DELETE |
| SKILL-06 | TestGlobalSkillVisibleToOtherUser, TestShareUnshareRoundtrip, TestShareOnlyCreator403, TestShareNameConflict409, TestUnshareNameConflict409 | sharing/unsharing semantics with conflict guards |
| EXPORT-01 | TestExportReturnsValidZipWithFrontmatterDelimiter | ZIP export with `---\n` frontmatter delimiter |
| EXPORT-02 | TestImportSingleSkillZip, TestImportBulkZipWithMixedResults | single and bulk ZIP import |
| EXPORT-03 | TestImportBulkZipWithMixedResults, TestImportOversizedFileSkipped, TestUnshareNameConflict409 | per-skill error aggregation, soft-skip semantics |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed storage RLS policy ambiguous `name` column reference**
- **Found during:** Task 1 (test execution — TestImportOversizedFileSkipped)
- **Issue:** Storage INSERT/DELETE policies in migration 035 used `storage.foldername(name)` inside an EXISTS subquery referencing `FROM public.skills s`. PostgreSQL resolved bare `name` as `s.name` (the `skills.name` column), not the `storage.objects.name` column. This caused the EXISTS clause to never match (comparing `skills.id::text` to `storage.foldername(skills.name)[2]` — always false), making all authenticated skill file uploads fail with "new row violates row-level security policy".
- **Fix:** Changed `storage.foldername(name)` to `storage.foldername(objects.name)` in both INSERT (WITH CHECK) and DELETE (USING) policies, then applied fix to live Supabase via `supabase db query --linked`
- **Files modified:** `supabase/migrations/035_skill_files_table_and_bucket.sql`
- **Commit:** d1d0d52

**2. [Rule 1 - Bug] Fixed TestImportOversizedZip413PreRead: use raw socket for fake Content-Length**
- **Found during:** Task 1 (test 13 execution failure)
- **Issue:** httpx/h11 enforces that the actual body matches the declared Content-Length. Sending `Content-Length: 60_000_000` with a 16-byte body caused h11 to raise `LocalProtocolError: Too little data for declared Content-Length` before the request was sent.
- **Fix:** Replaced httpx.post() with a raw socket connection that sends the HTTP/1.1 request bytes directly, bypassing h11's enforcement. The server's middleware correctly rejects based on the Content-Length header.
- **Files modified:** `backend/tests/api/test_skills.py`
- **Commit:** d1d0d52

**3. [Rule 2 - Missing] Applied Supabase migrations 034+035 to live database**
- **Found during:** Task 1 (first test run — all tests returned 404 "table not found")
- **Issue:** Migrations 034 (skills table) and 035 (skill_files + storage bucket + RLS policies) existed in `supabase/migrations/` but had not been applied to the live Supabase project `qedhulpfezucnfadlfiz`.
- **Fix:** Applied both migrations via `npx supabase db query --linked -f supabase/migrations/034_skills_table_and_seed.sql` and the same for 035. Confirmed tables exist with correct seed data.
- **Impact:** All 29 tests passed after migration application + RLS fix.

### Deferred Items

None — all identified issues resolved within the 3-attempt limit.

## Test Coverage Summary

| Test Class | Plan # | Status | Notes |
|------------|--------|--------|-------|
| TestSeedSkillCreatorExists | 1 | PASS | skill-creator seed visible globally |
| TestCreateReadUpdateDeleteCycle | 2 | PASS | Full CRUD round-trip |
| TestCreateInvalidName422 | 3 | PASS (×7) | 7 parametrized invalid names |
| TestCreateDuplicateName409 | 4 | PASS | Same-user duplicate → 409 |
| TestGlobalSkillVisibleToOtherUser | 5 | PASS | SKILL-06 positive |
| TestShareUnshareRoundtrip | 6 | PASS | Share + unshare + RLS |
| TestShareOnlyCreator403 | 7 | PASS | Non-creator share attempt |
| TestEditGlobalSkill403 | 8 | PASS | D-P7-03 guard |
| TestAdminCanDeleteAnySkill | 9 | PASS | D-P7-04 admin moderation |
| TestExportReturnsValidZipWithFrontmatterDelimiter | 10 | PASS | HIGH #4 regression |
| TestListSkillsOrdersGlobalsFirst | 11 | PASS | HIGH #3 regression |
| TestImportOversizedFileSkipped | 12 | PASS | HIGH #5, soft-skip semantics |
| TestImportOversizedZip413PreRead | 13 | PASS | HIGH #6, raw socket approach |
| TestImportOversizedZip413PostRead | 14 | PASS | ZIP parse defense |
| TestStoragePathSpoofingRejected | 15 | PASS | HIGH #2 + storage RLS HIGH #1 |
| TestShareNameConflict409 | 16 | PASS | cycle-1 MEDIUM conflict guard |
| TestUnshareNameConflict409 | 17 | PASS | Symmetric conflict guard |
| TestOtherUserCannotSeePrivateSkill | 18 | PASS | RLS positive smoke |
| TestImportSingleSkillZip | 19 | PASS | EXPORT-02 single |
| TestImportBulkZipWithMixedResults | 20 | PASS | EXPORT-02/03 bulk |
| TestGlobalSkillCreatorCannotMutateStorage | 21 | PASS | NEW-H1 closure |
| TestParserReturnsErrorOnlySkillForBadYaml | 22 | PASS | NEW-H2 closure |
| TestShareUniqueViolationRaceReturns409 | 23 | PASS | cycle-2 MEDIUM race → 409 |

## Self-Check

- [x] `backend/tests/api/test_skills.py` exists
- [x] `supabase/migrations/035_skill_files_table_and_bucket.sql` modified
- [x] Commit d1d0d52 exists
- [x] All 29 tests pass against `http://localhost:8000`
- [x] `python -c "from app.main import app; print('OK')"` passes

## Self-Check: PASSED

All claims verified: test file created, migration bug fixed, 29/29 tests pass, backend import check clean.
