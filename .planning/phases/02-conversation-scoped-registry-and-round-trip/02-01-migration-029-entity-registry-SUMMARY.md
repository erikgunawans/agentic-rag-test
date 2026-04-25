---
phase: 02-conversation-scoped-registry-and-round-trip
plan: 01
subsystem: database
tags: [supabase, postgres, migration, rls, pii, entity-registry]

# Dependency graph
requires:
  - phase: 01-detection-anonymization-foundation
    provides: "RedactionService + entity_map shape (real → surrogate) that this table durably stores"
provides:
  - "supabase/migrations/029_pii_entity_registry.sql — DDL for the per-thread real↔surrogate map"
  - "Composite UNIQUE(thread_id, real_value_lower) — DB-layer enforcement of REG-04 (same real → same surrogate)"
  - "Service-role-only RLS posture for the entity_registry table (D-25, no user-facing policies)"
  - "handle_entity_registry_updated_at trigger wired to existing handle_updated_at() function"
affects:
  - "02-02 ConversationRegistry skeleton (consumes EntityMapping shape)"
  - "02-03 supabase db push (Wave 2 BLOCKING — this file is its input)"
  - "02-04 Registry DB methods (load / upsert_delta query this table)"
  - "02-05 redaction_service wiring (ON CONFLICT path relies on the composite UNIQUE)"
  - "02-06 pytest SC#5 race test (exercises the UNIQUE constraint as the cross-process serialisation safety net)"

# Tech tracking
tech-stack:
  added:
    - "Postgres table: public.entity_registry (system-level)"
  patterns:
    - "System-level table + service-role-only RLS (stricter than audit_logs — NO super_admin SELECT policy because no PostgREST consumer per D-26)"
    - "Composite UNIQUE constraint as cross-process serialisation safety net (forward-compat with D-31 advisory-lock upgrade)"
    - "FUTURE-WORK SQL header comment for documenting deferred hardening (D-31 → Phase 6)"

key-files:
  created:
    - "supabase/migrations/029_pii_entity_registry.sql"
  modified: []

key-decisions:
  - "D-22 honored: 8 columns exact (id, thread_id, real_value, real_value_lower, surrogate_value, entity_type, source_message_id, created_at, updated_at)"
  - "D-23 honored: composite UNIQUE(thread_id, real_value_lower) inline in table body"
  - "D-25 honored: RLS enabled with ZERO user-facing policies — stricter than audit_logs; no super_admin SELECT because D-26 has no /admin/registry route"
  - "source_message_id is nullable + ON DELETE SET NULL (NOT cascade) — Phase 5 chat router backfills AFTER message commit; deleting a message must not delete its surrogate mappings"
  - "entity_type is text NOT NULL with NO check constraint — Presidio types are application-side; a SQL CHECK would couple the schema to the type set"
  - "D-31 FUTURE-WORK note for pg_advisory_xact_lock upgrade path captured in SQL header comment (Phase 6 hardening)"

patterns-established:
  - "Service-role-only system-level table: RLS enabled, NO policies, comment annotation describing posture, service-role-only access via get_supabase_client()"
  - "FUTURE-WORK header comment: SQL files document deferred hardening + the upgrade path inline so future executors don't need to cross-reference STATE.md"
  - "Composite UNIQUE on (parent_id, normalized_lookup_key) doubles as the index path for the case-insensitive lookup — no redundant single-column index required"

requirements-completed: [REG-01, REG-02, REG-03, REG-04, REG-05]

# Metrics
duration: 1min
completed: 2026-04-26
---

# Phase 2 Plan 01: Migration 029 entity_registry Summary

**Postgres `public.entity_registry` table — service-role-only system-level storage for the per-thread real↔surrogate map, with composite UNIQUE(thread_id, real_value_lower) enforcing "same real → same surrogate" at the DB layer.**

## Performance

- **Duration:** ~1 min
- **Started:** 2026-04-25T23:00:48Z
- **Completed:** 2026-04-25T23:01:52Z
- **Tasks:** 1
- **Files modified:** 1 (created)

## Accomplishments

- Wrote `supabase/migrations/029_pii_entity_registry.sql` (44 lines, well under the 80-line sanity bound) with all four required sections: table, indexes, trigger, RLS.
- All 8 D-22 columns present with exact types and NOT-NULL constraints.
- Composite `unique (thread_id, real_value_lower)` constraint inline in the table body (D-23) — the cross-process serialisation safety net for the D-31 advisory-lock future.
- `thread_id` FK with `ON DELETE CASCADE` and `source_message_id` FK nullable with `ON DELETE SET NULL` (Phase 5 chat router backfills after message commit).
- RLS enabled with zero user-facing policies (D-25, D-26) — stricter than `audit_logs` because no PostgREST consumer exists.
- `handle_entity_registry_updated_at` trigger wired to the existing `handle_updated_at()` function from migration 001.
- `idx_entity_registry_thread_id` index for thread-scoped scans.
- D-31 FUTURE-WORK pg_advisory_xact_lock upgrade path documented in the SQL header comment.
- `comment on table` annotation describes the RLS posture and links to PRD §4.FR-3.

## Task Commits

Each task was committed atomically:

1. **Task 1: Create migration 029_pii_entity_registry.sql with table, indexes, RLS, trigger** — `f7a3ff5` (feat)

**Plan metadata:** (final commit will include this SUMMARY.md, STATE.md, ROADMAP.md)

## Files Created/Modified

- `supabase/migrations/029_pii_entity_registry.sql` (NEW, 44 lines) — full DDL: 1 table, 1 explicit index, 1 trigger, RLS enable, 1 table comment

## Schema Confirmed

All 8 columns present with exact types per D-22:

| Column              | Type                | Null     | Default              | Notes                                                   |
|---------------------|---------------------|----------|----------------------|---------------------------------------------------------|
| id                  | uuid                | NOT NULL | gen_random_uuid()    | Primary key                                             |
| thread_id           | uuid                | NOT NULL | —                    | FK → public.threads(id) ON DELETE CASCADE               |
| real_value          | text                | NOT NULL | —                    | Original casing preserved for de-anon output            |
| real_value_lower    | text                | NOT NULL | —                    | str.casefold() at write time; case-insensitive lookup   |
| surrogate_value     | text                | NOT NULL | —                    | Faker-generated surrogate                               |
| entity_type         | text                | NOT NULL | —                    | Presidio type (no CHECK — app-side enum)                |
| source_message_id   | uuid                | NULL     | —                    | FK → public.messages(id) ON DELETE SET NULL (nullable)  |
| created_at          | timestamptz         | NOT NULL | now()                |                                                         |
| updated_at          | timestamptz         | NOT NULL | now()                | Updated by handle_entity_registry_updated_at trigger    |

Composite constraint: `unique (thread_id, real_value_lower)` (D-23).

## RLS Posture (D-25)

- `alter table public.entity_registry enable row level security;` — RLS ENABLED.
- ZERO `create policy` statements (verified by negative grep in the verification step).
- Backend uses `get_supabase_client()` (service role) for all reads and writes (D-25).
- No HTTP route in Phase 2 (D-26 — admin UI is PRD §10 future work).

## Decisions Made

- Followed D-21..D-26, D-31, D-36 from `02-CONTEXT.md` exactly as planned. No deviations.
- Honored CLAUDE.md gotcha: did not edit applied migrations 001-028; this is migration 029, the next sequential.
- Did not use `/create-migration` skill — D-21 locks the file number and the plan called for direct write.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None. Pre-commit hook (PostToolUse) ran cleanly on the migration commit (no Python or TS files in the diff, so no lint passes were triggered).

## User Setup Required

None — schema is on disk only. The actual `supabase db push` happens in Wave 2 (plan 02-03), which is the BLOCKING task that requires explicit user confirmation per the orchestrator's wave-2 protocol.

## Next Phase Readiness

- Wave 1 sibling plan **02-02** (ConversationRegistry skeleton) is unblocked — it depends on the EntityMapping shape, which mirrors the column set defined in this migration.
- Wave 2 plan **02-03** (`supabase db push`) is unblocked — its only input is this file existing on disk.
- Wave 3+ plans depend on the table being live in the database; they wait for Wave 2.

## Self-Check: PASSED

- File exists: `supabase/migrations/029_pii_entity_registry.sql` — FOUND
- Commit exists: `f7a3ff5` — FOUND
- All plan automated verification grep patterns return `ALL_CHECKS_PASS`
- File length 44 lines (under 80-line sanity bound)
- No deletions in commit (verified via `git diff --diff-filter=D HEAD~1 HEAD`)

---
*Phase: 02-conversation-scoped-registry-and-round-trip*
*Completed: 2026-04-26*
