---
phase: 18-workspace-virtual-filesystem
plan: "01"
subsystem: database/storage
tags: [migration, supabase, rls, storage, workspace]
dependency_graph:
  requires: [migration-038-agent-todos]
  provides: [workspace_files-table, workspace-files-bucket, workspace-rls]
  affects: [phase-18-02, phase-18-03, phase-18-04, phase-18-05, phase-18-08]
tech_stack:
  added: []
  patterns: [supabase-migration, rls-thread-ownership, 4-segment-storage-path, updated_at-trigger]
key_files:
  created:
    - supabase/migrations/039_workspace_files.sql
  modified: []
decisions:
  - "Migration 039 confirmed free (038 = agent_todos, 039 was unallocated) — no renumber needed"
  - "storage_bucket discriminator column added per D-04 to enable bucket-aware signed-URL dispatch without path-prefix sniffing"
  - "sandbox-outputs bucket intentionally untouched — backward-compat invariant preserved"
metrics:
  duration_seconds: 63
  completed_date: "2026-05-03"
  tasks_completed: 1
  tasks_total: 2
  files_created: 1
  files_modified: 0
---

# Phase 18 Plan 01: Migration 039 workspace_files + workspace-files Bucket Summary

**One-liner:** SQL migration creating `public.workspace_files` table with thread-ownership RLS, path-defence CHECK constraints, `updated_at` trigger, and private `workspace-files` Supabase Storage bucket with 4-segment-path RLS — the data-layer foundation for Phase 18 virtual filesystem.

## Tasks Executed

| Task | Name | Status | Commit |
|------|------|--------|--------|
| 1 | Create migration 039_workspace_files.sql | COMPLETE | f3703c5 |
| 2 | Apply migration 039 to Supabase production | AWAITING HUMAN ACTION | — |

## Task 1: Migration File

**Final filename:** `supabase/migrations/039_workspace_files.sql` (no renumber — 039 was free)

### Schema Summary

**Table `public.workspace_files`:**
- `id uuid PRIMARY KEY DEFAULT gen_random_uuid()`
- `thread_id uuid NOT NULL REFERENCES public.threads(id) ON DELETE CASCADE`
- `file_path text NOT NULL` — path-defence CHECKs applied at DB level
- `content text` — NULL for binary files
- `storage_path text` — NULL for text files
- `storage_bucket text` — discriminator for bucket-aware signed-URL dispatch
- `source text NOT NULL CHECK (source IN ('agent','sandbox','upload'))`
- `size_bytes integer NOT NULL DEFAULT 0`
- `mime_type text`
- `created_at, updated_at timestamptz NOT NULL DEFAULT now()`

**Constraints:**
- `workspace_files_path_length` — length 1..500
- `workspace_files_path_no_leading_slash`
- `workspace_files_path_no_backslash`
- `workspace_files_path_no_traversal`
- `workspace_files_storage_xor` — content XOR storage_path (exactly one populated)
- `workspace_files_bucket_check` — storage_bucket must be in ('sandbox-outputs','workspace-files')
- `workspace_files_bucket_set` — storage_bucket set iff storage_path set
- `workspace_files_thread_path_unique UNIQUE (thread_id, file_path)`

**Indexes:**
- `idx_workspace_files_thread_updated (thread_id, updated_at DESC)`
- `idx_workspace_files_thread_created (thread_id, created_at DESC)`

**Trigger:** `workspace_files_updated_at` — BEFORE UPDATE fires `workspace_files_set_updated_at()` to refresh `updated_at`

**RLS:** Enabled with 4 policies — `workspace_files_select`, `workspace_files_insert`, `workspace_files_update`, `workspace_files_delete`. All use thread-ownership predicate:
```sql
thread_id IN (SELECT id FROM public.threads WHERE user_id = auth.uid())
OR (auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin'
```

**Storage bucket `workspace-files`:** Private (`public=false`), inserted with `ON CONFLICT DO NOTHING`. 4 RLS policies (SELECT/INSERT/UPDATE/DELETE) gate on `(storage.foldername(objects.name))[1] = auth.uid()::text` — mirroring `sandbox-outputs` pattern from migration 036.

## Task 2: Apply Migration (CHECKPOINT — human-action required)

This task is a `checkpoint:human-action`. The operator must apply migration 039 to the Supabase project `qedhulpfezucnfadlfiz`:

```bash
# From repo root, with SUPABASE_ACCESS_TOKEN set
supabase db push --linked
```

**Fallback:** Paste the contents of `supabase/migrations/039_workspace_files.sql` into the Supabase dashboard SQL editor and run.

**Verification after apply:**
```sql
SELECT to_regclass('public.workspace_files')::text;  -- should return 'public.workspace_files'
SELECT relrowsecurity FROM pg_class WHERE oid = 'public.workspace_files'::regclass;  -- should return 't'
SELECT id FROM storage.buckets WHERE id = 'workspace-files';  -- should return row
SELECT policyname FROM pg_policies WHERE tablename = 'workspace_files';  -- 4 rows
```

## Deviations from Plan

None — plan executed exactly as written. Migration number 039 confirmed free (no collision with Phase 17 which owns 038). The file was hand-written (equivalent to `/create-migration` skill output) per the plan's fallback instruction.

## Threat Surface Scan

No new network endpoints, auth paths, or file access patterns introduced in this plan — schema-only migration. All threats in the plan's STRIDE register (T-18-01 through T-18-05) are addressed by the RLS policies and CHECK constraints in the SQL.

## Known Stubs

None — this plan is schema-only. No service layer, no UI stubs.

## Self-Check: PASSED

- `supabase/migrations/039_workspace_files.sql` exists: FOUND
- Commit f3703c5 exists: FOUND
- All 21 acceptance criteria checks: PASS (verified at commit time)
