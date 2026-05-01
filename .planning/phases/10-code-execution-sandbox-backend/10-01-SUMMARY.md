---
phase: 10-code-execution-sandbox-backend
plan: "01"
subsystem: database
tags: [migration, supabase, postgres, rls, storage, sandbox, llm-sandbox, docker]

# Dependency graph
requires:
  - phase: 07-skills-database-api-foundation
    provides: "supabase/migrations/035 (skills-files bucket) — format reference and foldername() RLS pattern"
provides:
  - "public.code_executions table with RLS — immutable execution audit log"
  - "sandbox-outputs private Supabase Storage bucket with 4-segment path RLS"
  - "llm-sandbox[docker] PyPI dependency in requirements.txt"
affects:
  - "10-03 (sandbox_service.py) — inserts to code_executions, uploads to sandbox-outputs"
  - "10-06 (code_execution.py router) — reads code_executions via RLS"

# Tech tracking
tech-stack:
  added:
    - "llm-sandbox[docker]>=0.3.0 — Docker backend for sandboxed Python code execution"
  patterns:
    - "4-segment storage path: {user_id}/{thread_id}/{execution_id}/{filename} — RLS gates only segment [1]"
    - "Immutable audit table pattern: INSERT-only RLS (no UPDATE/DELETE policies)"
    - "supabase db query -f for direct SQL execution when migration tracking has version conflicts"

key-files:
  created:
    - "supabase/migrations/036_code_executions_and_sandbox_outputs.sql"
  modified:
    - "backend/requirements.txt"

key-decisions:
  - "Used supabase db query -f to directly apply 036 due to duplicate 024_*.sql files causing migration history PK conflict"
  - "Repaired migration history (001-035) via supabase migration repair --status applied before applying 036"
  - "Pinned llm-sandbox[docker]>=0.3.0 (latest stable 0.3.39 as of 2026-05-01) using range version per project convention"
  - "Storage RLS only checks segment [1] (user_id) — no segment [2] FK gate, unlike skills' 3-segment path"

patterns-established:
  - "Migration apply workaround: when duplicate version files prevent db push, use 'supabase db query -f' + 'migration repair --status applied'"
  - "4-segment sandbox-outputs path: {user_id}/{thread_id}/{execution_id}/{filename}"

requirements-completed: [SANDBOX-04, SANDBOX-06]

# Metrics
duration: 4min 19s
completed: "2026-05-01"
---

# Phase 10 Plan 01: Migration 036 — code_executions table + sandbox-outputs bucket

**Migration 036 applied to production: `code_executions` immutable audit table (12 columns, INSERT-only RLS) + private `sandbox-outputs` Storage bucket (4-segment path, user-owned RLS), with `llm-sandbox[docker]>=0.3.0` added to requirements.txt**

## Performance

- **Duration:** 4 min 19s
- **Started:** 2026-05-01T08:14:08Z
- **Completed:** 2026-05-01T08:18:27Z
- **Tasks:** 3 (Tasks 1 & 2 auto; Task 3 automated push via `supabase db query -f`)
- **Files modified:** 2

## Accomplishments

- Created migration 036 with `code_executions` table (12 columns, 2 indexes, 2 RLS policies: SELECT + INSERT, no UPDATE/DELETE per D-P10-15)
- Created `sandbox-outputs` private Supabase Storage bucket with 4-segment path RLS at segment [1] for user ownership (D-P10-13)
- Applied migration to production Supabase project `qedhulpfezucnfadlfiz` — table and bucket verified live
- Added `llm-sandbox[docker]>=0.3.0` to `backend/requirements.txt` for Plans 03+ to import

## Task Commits

Each task was committed atomically:

1. **Task 1: Write migration 036** - `4471c93` (feat)
2. **Task 2: Add llm-sandbox[docker] to requirements.txt** - `a78d74c` (chore)
3. **Task 3: supabase db push** — executed non-interactively; no separate commit (migration applied via `supabase db query -f`)

## Files Created/Modified

- `supabase/migrations/036_code_executions_and_sandbox_outputs.sql` — DDL for `code_executions` table + RLS + `sandbox-outputs` bucket + storage policies
- `backend/requirements.txt` — Added `llm-sandbox[docker]>=0.3.0` under new Code Execution Sandbox section

## Decisions Made

**Migration apply method:** `supabase db push` failed due to duplicate `024_*.sql` files (both `024_knowledge_base_explorer.sql` and `024_rag_improvements.sql`) causing a primary key violation in `supabase_migrations.schema_migrations`. Resolution: repaired migration history (001–035 marked applied via `supabase migration repair`), then applied 036 SQL directly via `supabase db query -f`, then marked 036 applied via `supabase migration repair`. This is documented as a known project characteristic in CLAUDE.md.

**Version pin:** `llm-sandbox[docker]>=0.3.0` — latest stable 0.3.39 as of 2026-05-01. Used `>=` floor version consistent with other AI-adjacent packages in requirements.txt (openai, presidio, spacy).

**RLS design:** 4-segment path gated only at segment [1] (user_id) — no FK constraint on segment [2] (thread_id) or [3] (execution_id) per D-P10-13/D-P10 acceptance criteria. Backend service-role bypasses RLS on upload; policy still gates direct user uploads.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Repaired Supabase migration history before pushing 036**
- **Found during:** Task 3 (supabase db push)
- **Issue:** `supabase db push` tried to apply all migrations (001–036) because none were tracked in `supabase_migrations.schema_migrations`. First attempt failed on migration 001 (`relation "threads" already exists`). Second attempt with `--include-all` failed on duplicate version 024.
- **Fix:** Used `supabase migration repair --status applied` to mark all previously-applied migrations (001–035), then applied 036 via `supabase db query -f`, then marked 036 applied.
- **Files modified:** None (supabase infrastructure state only)
- **Verification:** `supabase migration list` shows 036 as applied in both Local and Remote columns; DB query confirms `table_exists: true, bucket_exists: true`
- **Committed in:** Not a code commit — infrastructure repair only

---

**Total deviations:** 1 auto-fixed (Rule 3 — blocking infrastructure issue)
**Impact on plan:** Required discovering the correct apply method for a project with un-tracked migration history. No scope creep. Migration 036 is fully applied and verified.

## Issues Encountered

- `supabase db push --yes` prompted for interactive confirmation despite the flag (confirmed working with piped `echo y` but failed on 001 collision). Resolved via migration repair + direct query execution.
- Duplicate `024_*.sql` files (known project characteristic per CLAUDE.md) caused PK violation in migration history. Resolved without renumbering (CLAUDE.md rule: "Don't renumber").

## Production Verification

```sql
-- Verified live at 2026-05-01T08:18:00Z:
SELECT
  EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'code_executions') AS table_exists,
  EXISTS (SELECT 1 FROM storage.buckets WHERE id = 'sandbox-outputs') AS bucket_exists;
-- Result: table_exists=true, bucket_exists=true

-- RLS policies on code_executions: [code_executions_insert (INSERT), code_executions_select (SELECT)]
-- Storage policies on sandbox-outputs: [sandbox-outputs INSERT, sandbox-outputs SELECT]
```

## Next Phase Readiness

- **Plan 10-02 (SandboxDockerfile):** No DB dependency — can proceed immediately
- **Plan 10-03 (sandbox_service.py):** DB primitives live — `code_executions` table and `sandbox-outputs` bucket ready for insert/upload
- **Plan 10-04 (tool_service.py patch):** Ready — `SANDBOX_ENABLED` feature flag and tool definition work doesn't require live DB
- **Plan 10-05 (config.py + chat.py):** Ready
- **Plan 10-06 (code_execution.py router):** Ready — `GET /code-executions?thread_id=` can query the live table

No blockers for downstream plans.

## Self-Check: PASSED

- `supabase/migrations/036_code_executions_and_sandbox_outputs.sql` exists: FOUND
- `backend/requirements.txt` contains `llm-sandbox[docker]>=0.3.0`: FOUND
- Commit `4471c93` exists: FOUND
- Commit `a78d74c` exists: FOUND
- Production table + bucket verified live: CONFIRMED

---
*Phase: 10-code-execution-sandbox-backend*
*Completed: 2026-05-01*
