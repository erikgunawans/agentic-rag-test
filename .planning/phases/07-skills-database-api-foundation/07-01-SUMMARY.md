---
phase: 07-skills-database-api-foundation
plan: "01"
subsystem: database
tags: [postgres, supabase, rls, migrations, skills, sql]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: "public.handle_updated_at() trigger function (migration 001)"
  - phase: 01-foundation
    provides: "RLS admin pattern — (auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin'"
provides:
  - "public.skills table with composite ownership model (user_id + created_by)"
  - "4 RLS policies gating SELECT/INSERT/UPDATE/DELETE on skills"
  - "3 indexes: per-user unique name (CI), global unique name (CI), created_by provenance"
  - "skills_handle_updated_at trigger (auto-maintained updated_at)"
  - "System seed: skill-creator skill (UUID 00000000-0000-0000-0000-000000000007, global)"
affects:
  - "07-02 (skills API router — depends on this table)"
  - "07-03 (skills service layer — depends on this schema)"
  - "07-04 (skill sharing / global promotion — service-role escape hatch, depends on RLS here)"
  - "07-05 (frontend skills tab — depends on API built on this schema)"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Composite ownership: user_id (current owner, nullable for global) + created_by (immutable provenance, nullable for system seeds)"
    - "Deterministic system seed UUIDs: 00000000-0000-0000-0000-XXXXXXXXXXXX (phase N sentinel)"
    - "Dollar-quoted heredoc for multi-line string seeds: $tag$...$tag$ avoids escaping"
    - "ON CONFLICT (id) DO NOTHING for idempotent seeding"

key-files:
  created:
    - "supabase/migrations/034_skills_table_and_seed.sql"
  modified: []

key-decisions:
  - "Composite ownership (user_id + created_by) separates transfer/sharing ownership from immutable creation provenance — enables share/unshare flows without losing audit trail"
  - "Global skills (user_id IS NULL) can only be seeded via migration or service-role; the INSERT RLS policy (created_by=uid AND user_id=uid) blocks API-level global creation"
  - "DELETE RLS: must be private+owned OR super_admin; globally-shared skills require unshare first (prevents creators from nuking shared globals)"
  - "Deterministic UUID 00000000-0000-0000-0000-000000000007 for skill-creator seed — collision-checked, phase-7 sentinel"
  - "skill-creator instructions include three concrete Indonesian legal domain examples (NDA review, board minutes, payment terms) and explicit save_skill call-to-action"

patterns-established:
  - "Migration idempotency: CREATE TABLE IF NOT EXISTS + CREATE INDEX IF NOT EXISTS + ON CONFLICT DO NOTHING"
  - "RLS DELETE combined predicate: (private ownership check) OR (super_admin role check)"
  - "Reuse public.handle_updated_at() for all new tables — do not redefine"

requirements-completed: [SKILL-10]

# Metrics
duration: 8min
completed: "2026-04-29"
---

# Phase 7 Plan 01: Migration 034 — skills table + RLS + seed skill-creator Summary

**Postgres `public.skills` table with composite ownership model, 4 RLS policies (SELECT/INSERT/UPDATE/DELETE), 3 indexes, and system-seeded `skill-creator` global skill in a single idempotent migration**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-04-29T10:35:00Z
- **Completed:** 2026-04-29T10:43:46Z
- **Tasks:** 1 (single atomic migration)
- **Files modified:** 1

## Accomplishments

- Created `public.skills` table with `user_id` (ownership, nullable for globals) and `created_by` (provenance, nullable for system seeds), supporting the private/global/shared ownership model required by v1.1
- Implemented all 4 RLS policies with precise semantics: global skills visible to all, API INSERT restricted to private self-owned, UPDATE restricted to private rows, DELETE requires private+self-owned or super_admin role
- Seeded `skill-creator` as a global system skill (UUID `00000000-0000-0000-0000-000000000007`) with full authoring guide instructions including 3 Indonesian legal domain examples

## Task Commits

1. **Task 1: Migration 034 — skills table, RLS, seed** - `662654f` (feat)

**Plan metadata:** (committed with SUMMARY — see final commit)

## Files Created/Modified

- `supabase/migrations/034_skills_table_and_seed.sql` — 174-line idempotent migration: table, 3 indexes, updated_at trigger, RLS enable + 4 policies, system seed with dollar-quoted heredoc

## Decisions Made

- **Composite ownership (user_id + created_by):** Separates who currently owns a skill from who originally created it. Enables the share/unshare flow in 07-04 without losing provenance. `user_id` changes on promotion (NULL = global); `created_by` never changes.
- **DELETE semantics:** Aligned with REQUIREMENTS SKILL-05 ("User can delete their own private skills"). DELETE policy requires `user_id = uid AND created_by = uid` — so a creator who has already globally shared a skill cannot DELETE it directly; they must unshare first. This prevents accidental deletion of shared globals. super_admin can delete any skill for moderation (D-P7-04). Addresses cycle-1 review MEDIUM.
- **INSERT RLS blocks global creation via API:** `created_by = uid AND user_id = uid` WITH CHECK means API callers can never insert `user_id = NULL` rows. Global skills come only from migrations or service-role calls (the share promotion flow in 07-04).
- **Idempotency strategy:** `CREATE TABLE IF NOT EXISTS` + `CREATE UNIQUE INDEX IF NOT EXISTS` + `ON CONFLICT (id) DO NOTHING` — safe to re-apply without errors or duplicates.

## Deviations from Plan

None — plan executed exactly as written. All schema, index, trigger, RLS, and seed specifications from the plan were implemented verbatim.

## Issues Encountered

- Supabase CLI not available in the worktree environment, so local `supabase migration up` verification was not possible. Migration SQL was verified by:
  1. Reviewing against all established patterns (handle_updated_at, super_admin RLS, idempotent indexes)
  2. Confirming `public.handle_updated_at()` exists (migration 001, grep-verified across 13 usages)
  3. Confirming no UUID collision for `0000...0007` (grep across .sql, .ts, .py — no hits)
  4. Confirming admin RLS pattern matches migration 016 exactly
  Live verification against `qedhulpfezucnfadlfiz` will run when the migration is applied via Supabase MCP or `railway up`.

## User Setup Required

None — no external service configuration required. Migration applies on next `supabase migration up` or Railway deploy.

## Known Stubs

None — the migration contains concrete schema only. No stub values or placeholder data.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: rls-new-table | supabase/migrations/034_skills_table_and_seed.sql | New `public.skills` table at auth trust boundary — mitigated within this migration via 4 RLS policies covering all CRUD operations |

(Threat mitigated within this plan — flagged for completeness per threat surface scan protocol.)

## Next Phase Readiness

- `public.skills` table is ready for the API layer (07-02 skills router)
- RLS policies gate all user-facing CRUD; service-role clients in 07-04 share flow will bypass RLS as intended
- Seed `skill-creator` available for integration tests from day 1
- No blockers for 07-02 or 07-03

## Self-Check: PASSED

- `supabase/migrations/034_skills_table_and_seed.sql` — EXISTS (174 lines, 8180 bytes)
- Commit `662654f` — EXISTS (`git log --oneline | head -1`)
- No unexpected file deletions in commit

---
*Phase: 07-skills-database-api-foundation*
*Completed: 2026-04-29*
