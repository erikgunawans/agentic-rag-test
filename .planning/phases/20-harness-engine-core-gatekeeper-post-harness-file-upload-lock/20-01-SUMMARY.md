---
phase: 20-harness-engine-core-gatekeeper-post-harness-file-upload-lock
plan: "01"
subsystem: database
tags: [migration, supabase, rls, harness-engine, schema]
dependency_graph:
  requires: [040_agent_runs.sql, 041_rag_improvements_legacy.sql]
  provides: [harness_runs table, messages.harness_mode column]
  affects: [backend/app/routers/chat.py (Plans 20-04, 20-05), backend/app/services/harness/ (Plans 20-02 through 20-11)]
tech_stack:
  added: []
  patterns: [thread-ownership RLS, partial-unique-active-row, handle_updated_at trigger reuse, DROP POLICY IF EXISTS guard]
key_files:
  created: [supabase/migrations/042_harness_runs.sql]
  modified: []
decisions:
  - "Partial unique index WHERE status IN ('pending','running','paused') mirrors agent_runs 040 pattern exactly — 3-value active set reserves 'paused' for Phase 21 HIL."
  - "messages.harness_mode TEXT NULL (not BOOLEAN) to carry registered harness key string per D-04 spec."
  - "UPDATE RLS policy carries both USING and WITH CHECK clauses per T-20-01-02 tampering mitigation."
metrics:
  duration: "1m 19s"
  completed: "2026-05-03T15:53:32Z"
  tasks_completed: 2
  files_created: 1
---

# Phase 20 Plan 01: Migration 042 — harness_runs Table + messages.harness_mode Summary

Migration 042 adds the `harness_runs` state-machine table (HARN-01, MIG-03) and the `messages.harness_mode TEXT NULL` column (D-04/D-08), both pushed to the live Supabase project (`qedhulpfezucnfadlfiz`).

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Write migration 042 (harness_runs table + RLS + messages.harness_mode ALTER) | ba5ae52 | supabase/migrations/042_harness_runs.sql |
| 2 | Apply migration 042 via supabase db push | (no file commit — schema push only) | Live Supabase project |

## What Was Built

**Migration 042 (`supabase/migrations/042_harness_runs.sql`)** — 105 lines, 7 sections:

1. `CREATE TABLE IF NOT EXISTS public.harness_runs` — UUID PK, thread_id FK → threads(id) ON DELETE CASCADE, user_id FK → auth.users(id) ON DELETE CASCADE, harness_type TEXT, status TEXT CHECK with 6 values (pending/running/paused/completed/failed/cancelled), current_phase INTEGER, phase_results JSONB, input_file_ids UUID[], error_detail TEXT, created_at/updated_at TIMESTAMPTZ.

2. Partial unique index `idx_harness_runs_thread_active` on (thread_id) WHERE status IN ('pending','running','paused') — enforces at-most-one active run per thread (D-01 constraint, T-20-01-04 race mitigation).

3. Auditing index `idx_harness_runs_user_created` on (user_id, created_at DESC).

4. `handle_harness_runs_updated_at` trigger reusing `public.handle_updated_at()` from migration 001.

5. RLS enabled. 4 policies (SELECT/INSERT/UPDATE/DELETE) each guarded by `DROP POLICY IF EXISTS` per CLAUDE.md SQLSTATE 42710 gotcha. Thread-ownership predicate: `thread_id IN (SELECT id FROM public.threads WHERE user_id = auth.uid())`. Super-admin escape hatch on all 4 policies.

6. `ALTER TABLE public.messages ADD COLUMN IF NOT EXISTS harness_mode TEXT NULL` — tags assistant messages produced by harness flow (gatekeeper D-08, post-harness D-09).

7. `idx_messages_harness_mode_thread` partial index on (thread_id, created_at) WHERE harness_mode IS NOT NULL — for gatekeeper conversation reconstruction.

**Schema push:** `supabase db push` applied migration 042 to `qedhulpfezucnfadlfiz`. Push log confirmed "Applying migration 042_harness_runs.sql... Finished supabase db push." NOTICE messages (trigger/policy objects not existing prior) are expected first-apply output.

## Deviations from Plan

None — plan executed exactly as written.

## Push Log Excerpt

```
Connecting to remote database...
 • 042_harness_runs.sql
Applying migration 042_harness_runs.sql...
NOTICE (00000): trigger "handle_harness_runs_updated_at" does not exist, skipping
NOTICE (00000): policy "harness_runs_select" does not exist, skipping
NOTICE (00000): policy "harness_runs_insert" does not exist, skipping
NOTICE (00000): policy "harness_runs_update" does not exist, skipping
NOTICE (00000): policy "harness_runs_delete" does not exist, skipping
Finished supabase db push.
```

## Known Stubs

None.

## Threat Flags

None — migration introduces only the surfaces already covered in the plan's threat model (harness_runs SELECT/UPDATE RLS, messages.harness_mode server-side-only writes). No new surfaces beyond the threat register.

## Self-Check: PASSED

- [x] `supabase/migrations/042_harness_runs.sql` exists — confirmed
- [x] Commit ba5ae52 exists — confirmed
- [x] Migration 042 applied to live Supabase — confirmed ("Finished supabase db push")
- [x] No migration file numbered > 042 auto-generated — confirmed (042 is latest)
- [x] 4 DROP POLICY IF EXISTS guards present — confirmed (grep count = 4)
- [x] Status CHECK has all 6 enum values — confirmed
- [x] UPDATE policy has both USING and WITH CHECK — confirmed
- [x] handle_updated_at reused, not redefined — confirmed (0 CREATE OR REPLACE FUNCTION matches)
