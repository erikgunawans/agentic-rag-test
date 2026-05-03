---
phase: 19-sub-agent-delegation-ask-user-status-recovery
plan: 01
subsystem: database
tags: [supabase, postgres, rls, migration, tdd, agent_runs, phase19]

# Dependency graph
requires:
  - phase: 18-workspace-virtual-filesystem
    provides: "migration 039 (workspace_files), handle_updated_at trigger, threads/messages FK base"
provides:
  - "agent_runs table with 9 columns, CHECK constraints, partial unique index, RLS + super_admin override"
  - "messages.parent_task_id UUID column for sub-agent message tree reconstruction"
  - "7-test integration suite covering schema, constraints, trigger, RLS isolation"
affects:
  - 19-02 (agent_runs DB methods + service skeleton)
  - 19-03 (ask_user tool implementation)
  - 19-04 (status + recovery loop)
  - all downstream Phase 19 plans requiring agent_runs in production

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "TDD RED/GREEN migration gate: write 7 failing tests first, apply migration, confirm 7 passing"
    - "RLS via thread_id IN subquery form (NOT user_id = auth.uid() direct) — mirrors Phase 18 D-03 pattern"
    - "DROP POLICY IF EXISTS guards before every CREATE POLICY (CLAUDE.md Gotchas pattern)"
    - "Partial unique index on (thread_id) WHERE status IN ('working','waiting_for_user') for at-most-one active run"
    - "Bidirectional CHECK invariant: (status='waiting_for_user') = (pending_question IS NOT NULL)"
    - "Non-admin as User A in RLS isolation test — super_admin bypass invalidates the test if admin used"

key-files:
  created:
    - supabase/migrations/040_agent_runs.sql
    - backend/tests/integration/test_migration_040_agent_runs.py
  modified: []

key-decisions:
  - "RLS uses thread_id IN subquery form, not user_id = auth.uid() — required because agent_runs has both user_id and thread_id columns and the thread ownership chain is the correct trust boundary (D-03)"
  - "RLS isolation test must use non-admin as User A — super_admin SELECT policy bypass means test@test.com (super_admin) legitimately sees all rows; test-2@test.com (non-admin) used as User A to properly verify isolation"
  - "Migration not wrapped in BEGIN/COMMIT — mirrors 038 pattern; no storage-bucket coupling in this migration"
  - "handle_updated_at trigger reused from 001_initial_schema.sql — not redefined"

patterns-established:
  - "RLS isolation test pattern: User A = non-admin, User B = admin; A inserts → A can read own → B as admin can read all (expected) → A cannot read B's rows"
  - "agent_runs as the canonical status backbone for Phase 19 paused/resumable runs (TASK-04, ASK-04, STATUS-05)"

requirements-completed: [TASK-04, ASK-04, STATUS-05]

# Metrics
duration: 12min
completed: 2026-05-03
---

# Phase 19 Plan 01: Migration 040 agent_runs Summary

**`agent_runs` table live in production with partial unique index, bidirectional CHECK invariant, thread-ownership RLS, and messages.parent_task_id column — 7/7 integration tests green (TDD)**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-05-03T06:55:00Z
- **Completed:** 2026-05-03T07:07:00Z
- **Tasks:** 3 (TDD RED → migration DDL → db push + GREEN verification)
- **Files modified:** 2

## Accomplishments

- `agent_runs` table with 9 columns, `agent_runs_pending_question_invariant` CHECK, partial unique index `idx_agent_runs_thread_active` (WHERE status IN ('working','waiting_for_user')), 4 RLS policies with DROP IF EXISTS guards, and `handle_agent_runs_updated_at` trigger applied to production Supabase (`qedhulpfezucnfadlfiz`)
- `messages.parent_task_id UUID NULL` column + sparse index `idx_messages_parent_task` applied — enables sub-agent message tree reconstruction on thread reload (D-10)
- 7-test integration suite: columns/INSERT/SELECT, partial unique constraint, pending_question invariant, status CHECK, updated_at trigger, RLS User A vs User B isolation (T-19-03 mitigation verified), messages.parent_task_id acceptance

## Task Commits

Each task was committed atomically:

1. **Task 1: Write failing migration tests (TDD RED)** - `a8ab228` (test)
2. **Task 2: Create migration 040_agent_runs.sql** - `8c207b7` (feat)
3. **Task 3: Apply migration + fix RLS isolation test + verify GREEN** - `42c28fe` (test)

## Files Created/Modified

- `supabase/migrations/040_agent_runs.sql` - Full DDL: agent_runs table, partial unique index, pending_question invariant CHECK, 4 RLS policies (thread_id subquery form + super_admin override), handle_updated_at trigger reuse, messages.parent_task_id ALTER
- `backend/tests/integration/test_migration_040_agent_runs.py` - 7 integration tests covering schema correctness, all constraints, trigger, RLS isolation (T-19-03), and parent_task_id column; 518 lines including verbatim helpers from test_migration_038

## Decisions Made

- RLS uses `thread_id IN (SELECT id FROM public.threads WHERE user_id = auth.uid())` — the thread ownership chain is the correct trust boundary because agent_runs spans both user_id and thread_id columns (D-03). Using `user_id = auth.uid()` directly would bypass the cascade integrity.
- Migration not wrapped in `BEGIN/COMMIT` — mirrors 038 pattern; no storage-bucket DDL (Supabase DDL transactionality not required here).
- `handle_updated_at` trigger reused from `001_initial_schema.sql` — no redefinition, per CLAUDE.md invariant.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] RLS isolation test swapped User A from super_admin to non-admin**
- **Found during:** Task 3 (Apply migration + verify GREEN)
- **Issue:** `test_agent_runs_rls_user_isolation` used `test@test.com` (super_admin) as User A. The RLS SELECT policy includes `OR (auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin'`, so User A (super_admin) legitimately sees all rows — including User B's. The test was asserting that User A sees 0 rows for User B's data, which is the wrong expectation for a super_admin. This caused a false failure: the security model was correct, the test was wrong.
- **Fix:** Swapped roles: `test-2@test.com` (non-admin) as User A, `test@test.com` (super_admin) as User B. User A inserts a row, then attempts to SELECT User B's row — correctly gets 0 results. User B (super_admin) can read all rows as expected.
- **Files modified:** `backend/tests/integration/test_migration_040_agent_runs.py`
- **Verification:** `pytest tests/integration/test_migration_040_agent_runs.py -v` → 7 passed
- **Committed in:** `42c28fe` (test(19-01): fix RLS isolation test — use non-admin as User A)

---

**Total deviations:** 1 auto-fixed (Rule 1 — bug in test logic)
**Impact on plan:** Fix was necessary for correct test semantics. No change to migration DDL or RLS policy. No scope creep.

## Issues Encountered

- `supabase db push --include-all` was needed (vs plain `supabase db push`) to ensure migration 040 was included given the `--include-all` flag requirement for the project's migration tracking state. Resolved immediately.

## User Setup Required

None - migration applied to production automatically as part of Task 3. No environment variables or external service configuration required beyond what was already in place.

## Next Phase Readiness

- `agent_runs` table live in production — all downstream Phase 19 plans (19-02 onward) can now run integration tests against the real schema
- Threat T-19-03 (RLS cross-tenant enumeration) mitigated and verified by `test_agent_runs_rls_user_isolation`
- Threat T-19-RACE accepted with documented mitigation: partial unique index enforces at-most-one active run per thread; advisory lock for multi-worker hardening deferred to D-31
- Threat T-19-INV mitigated: `agent_runs_pending_question_invariant` CHECK + `status IN (...)` CHECK both active in production
- PreToolUse hook now blocks further edits to `040_agent_runs.sql` (applied migration protection)

## Self-Check: PASSED

- `supabase/migrations/040_agent_runs.sql` — FOUND
- `backend/tests/integration/test_migration_040_agent_runs.py` — FOUND
- Commit `a8ab228` (TDD RED) — FOUND
- Commit `8c207b7` (migration DDL) — FOUND
- Commit `42c28fe` (RLS fix + GREEN) — FOUND

---
*Phase: 19-sub-agent-delegation-ask-user-status-recovery*
*Completed: 2026-05-03*
