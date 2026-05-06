---
phase: 22-contract-review-harness-docx-deliverable
plan: 13
type: execute
wave: 1
depends_on: []
files_modified:
  - supabase/migrations/043_workspace_files_source_harness.sql
autonomous: false
gap_closure: true
requirements: [CR-01]
must_haves:
  truths:
    - "DB CHECK constraint workspace_files_source_check accepts source='harness'"
    - "Live harness CR-01 phase can write contract-text.md without 42P10/check-constraint failure"
    - "Migration is idempotent (re-runnable; uses DROP CONSTRAINT IF EXISTS guard)"
  artifacts:
    - path: "supabase/migrations/043_workspace_files_source_harness.sql"
      provides: "ALTER TABLE workspace_files: widen source CHECK to include 'harness'"
      contains: "CHECK (source IN ('agent','sandbox','upload','harness'))"
  key_links:
    - from: "backend/app/services/workspace_service.py write_text_file(..., source='harness')"
      to: "public.workspace_files row insert"
      via: "Supabase PostgREST insert"
      pattern: "INSERT.*workspace_files.*source.*harness"
---

<objective>
Close UAT Gap 1 (BLOCKER): the DB CHECK constraint `workspace_files_source_check` rejects `source='harness'` because migration 039 hard-codes the allowed set as `('agent','sandbox','upload')`. Plan 22-11 widened the frontend `WorkspaceFile.source` type to include `'harness'` but the schema was never updated. Live harness CR-01 phase fails with `new row for relation "workspace_files" violates check constraint "workspace_files_source_check"` and the entire contract-review pipeline silently dies.

Purpose: A 1-statement schema migration that drops and re-adds the CHECK constraint with the widened tuple. Idempotent so it can be re-run without error.
Output: `supabase/migrations/043_workspace_files_source_harness.sql` applied on Supabase.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/22-contract-review-harness-docx-deliverable/22-HUMAN-UAT.md
@CLAUDE.md
@supabase/migrations/039_workspace_files.sql

<interfaces>
<!-- Authoritative facts from supabase/migrations/039_workspace_files.sql:18 -->
Current CHECK constraint definition (line 18 of 039_workspace_files.sql):
```sql
source          TEXT NOT NULL CHECK (source IN ('agent','sandbox','upload')),
```

PostgreSQL auto-generates the constraint name as `workspace_files_source_check` (table name + column name + `_check` suffix).

Latest applied migration on disk: `042_harness_runs.sql`. Next available slot: `043_`.

Frontend type already widened (frontend/src/lib/database.types.ts:333):
```ts
source: 'agent' | 'sandbox' | 'upload' | 'harness'
```

Code that breaks today (from harness_engine.py:214-219 and contract_review.py phase 1):
```python
await ws.write_text_file(thread_id, PROGRESS_PATH, ..., source="harness")
# also: source="harness" passed by CR-01 intake when writing contract-text.md
```
</interfaces>

<invariants>
- CLAUDE.md: "Never edit applied migrations 001-042" — this plan only ADDS migration 043.
- CLAUDE.md: "CREATE POLICY needs DROP IF EXISTS guards" — same applies to ALTER CONSTRAINT. Use `DROP CONSTRAINT IF EXISTS` then `ADD CONSTRAINT`.
- CLAUDE.md: "Never reuse a numeric prefix" — confirm 043 is unused before writing.
- CLAUDE.md: schema migration is NOT a row-level mutation, so audit_action is N/A here.
- D-22-15 (off-mode invariance): when `contract_review_enabled=False` no harness writes happen, so the constraint widening is a no-op for OFF-mode. Safe.
</invariants>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Write migration 043 — widen workspace_files.source CHECK</name>
  <read_first>
    - supabase/migrations/039_workspace_files.sql (line 18: original CHECK constraint)
    - supabase/migrations/042_harness_runs.sql (header style — pattern for new migration files)
    - CLAUDE.md (search for "CREATE POLICY needs DROP IF EXISTS" — same pattern applies to constraints)
  </read_first>
  <files>supabase/migrations/043_workspace_files_source_harness.sql</files>
  <action>
Create `supabase/migrations/043_workspace_files_source_harness.sql` with EXACTLY this content (header comments may be edited for clarity but the SQL statements MUST match exactly):

```sql
-- Migration 043: Widen workspace_files.source CHECK constraint to include 'harness'
-- Phase 22 / UAT Gap 1 (BLOCKER) / 2026-05-06
-- Depends on: 039_workspace_files.sql (original CHECK), 042_harness_runs.sql (latest)
--
-- Background: Plan 22-11 widened frontend WorkspaceFile.source to include 'harness'
-- but the DB CHECK constraint was never updated. Live harness CR-01 phase fails with
-- 'new row for relation "workspace_files" violates check constraint
-- "workspace_files_source_check"' when contract_review_enabled=True.
--
-- Idempotent: uses DROP CONSTRAINT IF EXISTS so re-running this migration is safe
-- (matches the pattern documented in CLAUDE.md for RLS policies).

BEGIN;

ALTER TABLE public.workspace_files
  DROP CONSTRAINT IF EXISTS workspace_files_source_check;

ALTER TABLE public.workspace_files
  ADD CONSTRAINT workspace_files_source_check
  CHECK (source IN ('agent','sandbox','upload','harness'));

COMMIT;
```

Do NOT add an audit_log INSERT — this is a schema migration, not a row mutation (per CLAUDE.md guidance). Do NOT include any other ALTER TABLE statements; the constraint widening is the entire scope of this migration.

Write only this file. Do not modify any other migration. Do not edit `039_workspace_files.sql` (immutable per CLAUDE.md — applied migrations are frozen).
  </action>
  <verify>
    <automated>test -f supabase/migrations/043_workspace_files_source_harness.sql && grep -q "DROP CONSTRAINT IF EXISTS workspace_files_source_check" supabase/migrations/043_workspace_files_source_harness.sql && grep -qE "CHECK \(source IN \('agent','sandbox','upload','harness'\)\)" supabase/migrations/043_workspace_files_source_harness.sql && ! ls supabase/migrations/043_*.sql | grep -v "043_workspace_files_source_harness.sql"</automated>
  </verify>
  <acceptance_criteria>
    - File `supabase/migrations/043_workspace_files_source_harness.sql` exists
    - File contains the exact string `DROP CONSTRAINT IF EXISTS workspace_files_source_check`
    - File contains the exact string `CHECK (source IN ('agent','sandbox','upload','harness'))`
    - File contains `ADD CONSTRAINT workspace_files_source_check`
    - File is wrapped in `BEGIN;` ... `COMMIT;`
    - No other migration is modified (`git diff supabase/migrations/` shows ONLY the new 043 file as added; nothing changed in 001..042)
    - No other 043_*.sql file exists in supabase/migrations/ (numeric collision check per CLAUDE.md "never reuse a numeric prefix")
  </acceptance_criteria>
  <done>The 043 migration file exists, contains the idempotent DROP+ADD pattern with the widened tuple, and is the only file modified by this task.</done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 2: Apply migration 043 to Supabase remote</name>
  <what-built>Migration 043 SQL file written to supabase/migrations/. The constraint widening must be APPLIED on the live Supabase project (qedhulpfezucnfadlfiz) before live harness UAT can resume.</what-built>
  <how-to-verify>
This is a deploy step that touches production schema. The executor cannot apply migrations to remote Supabase unattended.

Steps for the human:
1. Review the migration: `cat supabase/migrations/043_workspace_files_source_harness.sql`
2. Apply it via Supabase CLI (project: qedhulpfezucnfadlfiz):
   ```
   supabase db push
   ```
   OR run the SQL directly in the Supabase Dashboard SQL editor.
3. Verify the constraint is widened:
   ```sql
   SELECT pg_get_constraintdef(oid)
   FROM pg_constraint
   WHERE conname = 'workspace_files_source_check';
   ```
   Expected output contains: `CHECK (source = ANY (ARRAY['agent'::text, 'sandbox'::text, 'upload'::text, 'harness'::text]))`
4. Smoke test: insert a test row with `source='harness'` (clean up after):
   ```sql
   -- on a thread row that exists; clean up after with DELETE
   INSERT INTO workspace_files (thread_id, file_path, content, source, size_bytes)
   VALUES ('<some-thread-uuid>', '__migration_043_smoke.md', 'ok', 'harness', 2)
   RETURNING id;
   -- Then: DELETE FROM workspace_files WHERE file_path='__migration_043_smoke.md';
   ```

Expected: INSERT succeeds (no 23514 check_violation).
  </how-to-verify>
  <resume-signal>Type "applied" when migration 043 is live on Supabase remote and the smoke INSERT succeeded. Type "blocked: <detail>" otherwise.</resume-signal>
</task>

</tasks>

<verification>
- Migration file 043 exists with correct SQL.
- DROP CONSTRAINT IF EXISTS guard present (idempotent).
- ADD CONSTRAINT statement contains all 4 values: 'agent','sandbox','upload','harness'.
- After remote apply: live harness CR-01 phase can write contract-text.md with source='harness' (rerun the harness end-to-end after this lands; covered by plan 22-12 e2e test, but live remote run is what proves the fix).
- No edits to migrations 001-042.
</verification>

<success_criteria>
- [ ] `supabase/migrations/043_workspace_files_source_harness.sql` exists
- [ ] File uses DROP CONSTRAINT IF EXISTS (idempotent guard)
- [ ] File widens CHECK to `('agent','sandbox','upload','harness')`
- [ ] No other migration touched
- [ ] Migration applied on Supabase remote (human checkpoint)
- [ ] Smoke insert with `source='harness'` returns row id (no check_violation)
</success_criteria>

<output>
After completion, write `.planning/phases/22-contract-review-harness-docx-deliverable/22-13-SUMMARY.md` documenting:
- The exact constraint definition before and after (from `pg_get_constraintdef`)
- Whether the migration ran cleanly or required manual remediation
- Confirmation that 22-14, 22-15 fixes can now be live-tested end-to-end
</output>
</output>
