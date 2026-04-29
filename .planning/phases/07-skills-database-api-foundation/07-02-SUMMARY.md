---
phase: 07-skills-database-api-foundation
plan: "02"
subsystem: database
tags: [supabase, postgres, rls, storage, skill-files, migration]

# Dependency graph
requires:
  - phase: 07-01
    provides: public.skills table (FK target for skill_files.skill_id)

provides:
  - public.skill_files table with path-shape and path-skill-match CHECK constraints
  - idx_skill_files_skill_id index
  - RLS policies: SELECT (parent-skill visibility), INSERT (private-skill ownership + path-prefix), DELETE (private-skill owner). No UPDATE (immutable).
  - skills-files storage bucket (private, public=false)
  - Storage SELECT policy: exact storage_path JOIN to skill_files (cycle-1 HIGH #1 fix)
  - Storage INSERT policy: private-parent-skill gate (cycle-2 NEW-H1 fix)
  - Storage DELETE policy: mirrors INSERT predicate

affects:
  - 07-04 (skills router will compute storage paths and use the bucket)
  - 07-05 (API tests will validate RLS smoke tests against this schema)
  - Phase 8+ SFILE-* requirements (file attachment CRUD)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Three-segment storage path {owner_id}/{skill_id}/{filename} enforced by DB CHECK + Storage RLS simultaneously (defense-in-depth)"
    - "Storage RLS delegates to table RLS via EXISTS JOIN on exact path (not first-segment heuristic) to prevent leakage to global-skill users"
    - "No UPDATE RLS policy = immutable file rows; replace = delete + insert pattern"
    - "Private-skill gate on Storage INSERT blocks creator from mutating globally-shared skill blobs without unsharing first"

key-files:
  created:
    - supabase/migrations/035_skill_files_table_and_bucket.sql
  modified: []

key-decisions:
  - "Storage SELECT policy uses exact storage_path JOIN (not first-segment match) to fix cycle-1 HIGH #1: prevents leaking private files of users who also have global skills"
  - "Storage INSERT/DELETE policies require parent skill to be PRIVATE (user_id = auth.uid()), fixing cycle-2 NEW-H1: creators cannot mutate global-skill blobs directly via Storage"
  - "No UPDATE RLS policy on skill_files — files are immutable; replacement is delete-then-insert to maintain audit trail"
  - "10MB per-file cap is enforced at the DB CHECK level and must remain in sync with skill_zip_service.parse_skill_zip(max_per_file=...)"

patterns-established:
  - "skill_files_storage_path_shape CHECK: 3-segment regex with UUID in segment 2 — all future file tables for skill-related content should follow this pattern"
  - "skill_files_storage_path_skill_match CHECK: split_part(storage_path,'/',2) = skill_id::text — row cannot point at a different skill's blob"

requirements-completed: []

# Metrics
duration: 2min
completed: "2026-04-29"
---

# Phase 7 Plan 02: skill_files Table and skills-files Storage Bucket Summary

**Postgres `skill_files` table with dual-CHECK path-binding security and private-only Supabase Storage bucket `skills-files` with exact-path-join SELECT and private-skill-gate INSERT policies**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-04-29T10:51:51Z
- **Completed:** 2026-04-29T10:53:32Z
- **Tasks:** 1 (single atomic migration commit)
- **Files modified:** 1

## Accomplishments

- Created `public.skill_files` table with FK cascade from `skills`, two structural CHECK constraints blocking storage-path spoofing (cycle-1 HIGH #2 mitigation), and a `size_bytes` cap of 10MB
- Established RLS policies enforcing private-skill ownership for INSERT/DELETE; SELECT delegates to parent-skill visibility; no UPDATE (immutable files)
- Created private `skills-files` storage bucket and three Storage RLS policies with exact-path-JOIN SELECT (cycle-1 HIGH #1 fix) and private-parent-skill gate on INSERT/DELETE (cycle-2 NEW-H1 fix)

## Task Commits

1. **Task 1: Migration 035 — skill_files table + skills-files storage bucket** - `210c5d1` (feat)

**Plan metadata:** (SUMMARY commit — see below)

## Files Created/Modified

- `supabase/migrations/035_skill_files_table_and_bucket.sql` — Full schema: skill_files table, index, RLS, storage bucket, storage RLS policies

## Decisions Made

- Exact-path JOIN in Storage SELECT policy (not first-segment heuristic): prevents cycle-1 HIGH #1 leakage where a user with a global skill could read another user's private file objects that happen to be in the same owner folder
- Storage INSERT/DELETE require `s.user_id = auth.uid()` (private skill only): fixes cycle-2 NEW-H1 — a creator who has shared their skill globally must unshare it before they can modify its file blobs via Storage
- No UPDATE policy: files are immutable at the table level; the replace workflow is delete + insert, which preserves audit trail and cascade integrity

## Deviations from Plan

None — plan executed exactly as written. All security properties from cycle-1 and cycle-2 codex reviews are implemented as specified in the plan's schema and policy sections.

## Issues Encountered

- Migration 034 was not present in this worktree (worktree was branched before Wave 1 landed). Fetched it from the Wave 1 commit (`662654f`) for reference to confirm the `public.skills` table schema and FK target. Migration 034 itself is NOT committed in this worktree — it will be merged in by the orchestrator from the 07-01 agent's worktree branch.

## User Setup Required

None — no external service configuration required beyond running `supabase migration up` in the target environment.

## Next Phase Readiness

- `skill_files` table and `skills-files` bucket are fully operational as prerequisites for:
  - 07-04 skills router (file upload, download signed URLs, delete endpoints)
  - 07-05 API tests (RLS smoke tests for all 8 verification scenarios from the plan)
  - Phase 8+ SFILE-* requirements (file attachment CRUD UI, `read_skill_file` LLM tool)
- 10MB cap in `size_bytes CHECK` must stay in sync with `skill_zip_service.parse_skill_zip(max_per_file=...)` from 07-03

---
*Phase: 07-skills-database-api-foundation*
*Completed: 2026-04-29*

## Self-Check: PASSED

- `supabase/migrations/035_skill_files_table_and_bucket.sql` — FOUND (created in this execution)
- Commit `210c5d1` — FOUND in git log
- No unexpected file deletions confirmed
