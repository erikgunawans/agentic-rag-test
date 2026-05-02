---
phase: 17-deep-mode-foundation-planning-todos-plan-panel
plan: "01"
subsystem: database
tags: [migration, rls, agent-todos, deep-mode, tdd, sec-01]
dependency_graph:
  requires: [supabase/migrations/037_pii_domain_deny_list_extra.sql]
  provides:
    - public.agent_todos table with RLS + indexes + handle_updated_at trigger
    - public.messages.deep_mode BOOLEAN NOT NULL DEFAULT false column
  affects:
    - backend/tests/integration/test_migration_038_agent_todos.py
tech_stack:
  added: []
  patterns:
    - "CREATE TABLE IF NOT EXISTS + DROP POLICY IF EXISTS idempotent migration pattern"
    - "RLS defense-in-depth: direct user_id = auth.uid() + EXISTS thread ownership check"
    - "TDD RED/GREEN gate: test file authored before migration applied"
key_files:
  created:
    - supabase/migrations/038_agent_todos_and_deep_mode.sql
    - backend/tests/integration/test_migration_038_agent_todos.py
  modified: []
decisions:
  - "D-01: MIG-01 + MIG-04 bundled into single migration 038 (reviewer simplicity + atomic ship)"
  - "D-03: RLS uses direct user_id = auth.uid() + EXISTS(threads.user_id) defense-in-depth"
  - "D-04: 8 columns — id, thread_id, user_id, content, status, position, created_at, updated_at"
  - "D-38: supabase db push is a deliberate manual step — not auto-applied by executor"
metrics:
  duration: "~10 minutes"
  completed: "2026-05-02T21:51:44Z"
  tasks_completed: 2
  tasks_total: 3
  tasks_pending: 1
---

# Phase 17 Plan 01: Migration agent_todos and deep_mode Summary

**One-liner:** Migration 038 creates agent_todos table with thread-ownership RLS (4 policies) + messages.deep_mode BOOLEAN column for Phase 17 Deep Mode foundation.

## Status: PARTIAL — Task 3 Requires Human Action

Task 3 is a `checkpoint:human-action`. The migration SQL is authored and committed. The human operator must run `supabase db push` to apply migration 038 to Supabase project `qedhulpfezucnfadlfiz`.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Write failing schema + RLS regression test | c0d5b9b | backend/tests/integration/test_migration_038_agent_todos.py |
| 2 | Author migration 038 — agent_todos + RLS + messages.deep_mode | 965e2e4 | supabase/migrations/038_agent_todos_and_deep_mode.sql |

## Task 3: Human Action Required

**Task:** Apply migration 038 to Supabase project `qedhulpfezucnfadlfiz`

**How to apply:**

From repo root:
```
supabase db push
```

OR paste the contents of `supabase/migrations/038_agent_todos_and_deep_mode.sql` into the Supabase SQL editor and execute against the `qedhulpfezucnfadlfiz` project.

**Verification (TDD GREEN gate):**
```
cd backend && source venv/bin/activate && \
  TEST_EMAIL="test@test.com" TEST_PASSWORD='!*-3-3?3uZ?b$v&' \
  TEST_EMAIL_2="test-2@test.com" TEST_PASSWORD_2='fK4$Wd?HGKmb#A2' \
  pytest tests/integration/test_migration_038_agent_todos.py -v
```

Expected after applying: **6 passed**

**Resume signal:** Type "applied" once `pytest tests/integration/test_migration_038_agent_todos.py -v` reports `6 passed`. Otherwise describe failure.

## Migration 038 Contents

`supabase/migrations/038_agent_todos_and_deep_mode.sql` contains all 5 required sections:

1. **TABLE public.agent_todos** — 8 columns with UUID PK, thread_id FK (CASCADE), user_id FK (CASCADE), content TEXT, status TEXT + CHECK, position INTEGER, created_at/updated_at TIMESTAMPTZ
2. **INDEXES** — `idx_agent_todos_thread (thread_id, position)` + `idx_agent_todos_user (user_id, created_at DESC)`
3. **TRIGGER** — `handle_agent_todos_updated_at` reuses `handle_updated_at()` from migration 001
4. **RLS (SEC-01)** — 4 policies (SELECT/INSERT/UPDATE/DELETE). INSERT defense-in-depth: `EXISTS (SELECT 1 FROM threads WHERE threads.id = agent_todos.thread_id AND threads.user_id = auth.uid())`
5. **ALTER TABLE messages** — `ADD COLUMN IF NOT EXISTS deep_mode BOOLEAN NOT NULL DEFAULT false`

All guards are idempotent: `CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`, `DROP POLICY IF EXISTS + CREATE POLICY`, `ADD COLUMN IF NOT EXISTS`.

## TDD Gate Compliance

- RED gate: `c0d5b9b` — 6 tests defined, all fail (agent_todos table does not exist)
- GREEN gate: pending Task 3 migration apply + pytest rerun

## Deviations from Plan

None — plan executed exactly as written. Task 3 is a deliberate `checkpoint:human-action` per D-38 (migration apply is always a manual step).

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: new_table_rls | supabase/migrations/038_agent_todos_and_deep_mode.sql | New agent_todos table introduces direct Supabase JS client access surface — covered by SEC-01 RLS policies in the same migration |
| threat_flag: schema_column_add | supabase/migrations/038_agent_todos_and_deep_mode.sql | messages.deep_mode is a new column on the messages table — no new trust boundary, default false, no RLS change required |

## Self-Check

### Created Files Exist

- [x] `supabase/migrations/038_agent_todos_and_deep_mode.sql` — present
- [x] `backend/tests/integration/test_migration_038_agent_todos.py` — present

### Commits Exist

- [x] c0d5b9b — test(17-01): add failing schema + RLS regression tests for migration 038
- [x] 965e2e4 — feat(17-01): author migration 038 — agent_todos table + RLS + messages.deep_mode

## Self-Check: PASSED
