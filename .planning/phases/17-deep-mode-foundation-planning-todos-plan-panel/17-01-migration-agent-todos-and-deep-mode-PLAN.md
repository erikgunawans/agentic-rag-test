---
phase: 17-deep-mode-foundation-planning-todos-plan-panel
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - supabase/migrations/038_agent_todos_and_deep_mode.sql
  - backend/tests/integration/test_migration_038_agent_todos.py
autonomous: true
requirements: [TODO-01, MIG-01, MIG-04, SEC-01]
must_haves:
  truths:
    - "Migration 038_agent_todos_and_deep_mode.sql exists at supabase/migrations/ and is the next sequential migration after 037 (no gaps)."
    - "agent_todos table is created with columns id, thread_id, user_id, content, status, position, created_at, updated_at."
    - "agent_todos has CHECK constraint enforcing status IN ('pending','in_progress','completed')."
    - "agent_todos has FK on thread_id REFERENCES threads(id) ON DELETE CASCADE and user_id REFERENCES auth.users(id) ON DELETE CASCADE."
    - "agent_todos has indexes idx_agent_todos_thread (thread_id, position) and idx_agent_todos_user (user_id, created_at DESC)."
    - "agent_todos enables RLS with policies enforcing auth.uid() = user_id for SELECT, INSERT, UPDATE, DELETE (per D-03)."
    - "messages table has new BOOLEAN NOT NULL DEFAULT false column named deep_mode after migration 038 applies."
    - "Existing pre-migration messages rows have deep_mode = false (default applied by ALTER TABLE)."
    - "RLS regression test asserts User A cannot SELECT/INSERT/UPDATE/DELETE rows in agent_todos belonging to User B's thread (SEC-01)."
    - "handle_updated_at trigger from migration 001 fires on agent_todos UPDATE (updated_at advances on row change)."
  artifacts:
    - path: "supabase/migrations/038_agent_todos_and_deep_mode.sql"
      provides: "agent_todos table + RLS + indexes + handle_updated_at trigger + messages.deep_mode column"
      contains: "create table if not exists public.agent_todos"
    - path: "backend/tests/integration/test_migration_038_agent_todos.py"
      provides: "Schema and RLS regression tests for migration 038"
      contains: "def test_rls_user_a_cannot_access_user_b_todos"
  key_links:
    - from: "supabase/migrations/038_agent_todos_and_deep_mode.sql"
      to: "public.threads"
      via: "FK thread_id"
      pattern: "references public.threads"
    - from: "supabase/migrations/038_agent_todos_and_deep_mode.sql"
      to: "public.messages"
      via: "ALTER TABLE messages ADD COLUMN deep_mode"
      pattern: "alter table public.messages add column .*deep_mode"
---

<objective>
Land the database foundation for Phase 17:
1. New `agent_todos` table (TODO-01) with thread-ownership RLS (SEC-01).
2. New `messages.deep_mode` BOOLEAN column (MIG-04) for UI history reconstruction (DEEP-04).

Per D-01 (CONTEXT.md), MIG-01 and MIG-04 are bundled into a single migration for reviewer simplicity. RLS pattern follows D-03 (defense-in-depth: mirrored `user_id` column + JOIN-aware policy). Migration is the absolute first plan because every other Phase 17 plan depends on the schema existing.

Purpose: Without this migration, `write_todos` / `read_todos` tools, the Plan Panel hydration endpoint, and the Deep Mode badge cannot be implemented. RLS enforcement here is also the SEC-01 deliverable for the entire phase.

Output:
- `supabase/migrations/038_agent_todos_and_deep_mode.sql` — schema + indexes + RLS + trigger + column-add.
- `backend/tests/integration/test_migration_038_agent_todos.py` — schema regression test + RLS regression test (User A vs User B, the canonical SEC-01 assertion).
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/17-deep-mode-foundation-planning-todos-plan-panel/17-CONTEXT.md
@supabase/migrations/001_initial_schema.sql
@supabase/migrations/036_code_executions_and_sandbox_outputs.sql
@supabase/migrations/032_pii_redaction_enabled_setting.sql

<interfaces>
**Existing `threads` table (migration 001):** primary key `id UUID`, `user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE`. RLS enabled with `auth.uid() = user_id` on all four CRUD policies. This is the FK target for `agent_todos.thread_id` and the source-of-truth for the mirrored `agent_todos.user_id`.

**Existing `messages` table (migration 001):** `id, thread_id, user_id, role, content, created_at`. RLS enabled with `auth.uid() = user_id` on SELECT/INSERT/DELETE. We add `deep_mode BOOLEAN NOT NULL DEFAULT false`. Default applies to existing rows via ALTER TABLE — no backfill needed.

**Existing `handle_updated_at` trigger function (migration 001 lines 32-38):** `RETURNS trigger; SET new.updated_at = now()`. Reused for `agent_todos`, no redefinition.

**RLS pattern reference — `code_executions` (migration 036):** Direct `user_id = auth.uid()` policy on a mirrored user_id column; insert WITH CHECK gates user_id self-assignment. Phase 17 follows this pattern; UPDATE/DELETE policies are added (unlike code_executions which is immutable audit) since todos are full-replacement-mutable.
</interfaces>

</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Write failing schema + RLS regression test</name>
  <files>backend/tests/integration/test_migration_038_agent_todos.py</files>
  <behavior>
    - Test schema_columns_present: queries Supabase information_schema for `agent_todos` columns; asserts exactly: id (uuid), thread_id (uuid), user_id (uuid), content (text), status (text), position (integer), created_at (timestamptz), updated_at (timestamptz).
    - Test schema_check_constraint: asserts `status` CHECK constraint accepts 'pending', 'in_progress', 'completed' and rejects 'foo' (psql expected_failure path).
    - Test schema_indexes_present: asserts `idx_agent_todos_thread` and `idx_agent_todos_user` exist on `agent_todos`.
    - Test schema_messages_deep_mode_column: asserts `messages.deep_mode` exists, type boolean, NOT NULL, default false.
    - Test rls_user_a_cannot_access_user_b_todos: signs in two users, User A creates thread + todo via authed Supabase client, User B with their JWT runs SELECT on the same row id and receives 0 rows; INSERT into User A's thread_id with User B's JWT raises permission/PostgrestError; UPDATE and DELETE same. Mirrors v1.0 entity_registry RLS test pattern.
    - Test handle_updated_at_trigger_fires: insert a row, capture updated_at, sleep 50ms, UPDATE the content, assert updated_at advanced.
  </behavior>
  <action>
    Create `backend/tests/integration/test_migration_038_agent_todos.py` using the existing pytest + Supabase test fixture pattern from `backend/tests/integration/` (look at any existing migration / RLS test for boilerplate; e.g. tests that exercise `code_executions` RLS).

    Use existing test fixtures `TEST_EMAIL`/`TEST_PASSWORD` (User A) and `TEST_EMAIL_2`/`TEST_PASSWORD_2` (User B) from CLAUDE.md `## Testing` block.

    All tests should fail at this stage (table does not exist yet — TDD RED).

    Run pytest to confirm RED:
    ```
    cd backend && source venv/bin/activate && pytest tests/integration/test_migration_038_agent_todos.py -v
    ```
    Expected: 6 tests, all errors with "relation public.agent_todos does not exist" or "column messages.deep_mode does not exist".
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pytest tests/integration/test_migration_038_agent_todos.py -v 2>&1 | grep -E "FAILED|ERROR" | wc -l | grep -q "[1-9]"</automated>
  </verify>
  <done>Test file exists, 6 tests defined, all 6 currently fail (table/column not yet created). RED gate satisfied.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Author migration 038 — agent_todos table + RLS + messages.deep_mode</name>
  <files>supabase/migrations/038_agent_todos_and_deep_mode.sql</files>
  <action>
    Create `supabase/migrations/038_agent_todos_and_deep_mode.sql` with the following EXACT structure (per D-01..D-07 in CONTEXT.md). Implement as `CREATE TABLE IF NOT EXISTS` and use idempotent guards on policies.

    File contents (verbatim, modulo whitespace):

    ```sql
    -- Migration 038: agent_todos table + messages.deep_mode column
    -- Phase 17 / Plan 17-01 — foundation for TODO-01 (planning todos), MIG-04 (deep_mode persistence), SEC-01 (RLS).
    -- Bundles MIG-01 + MIG-04 per CONTEXT.md D-01.
    -- Depends on: 037_pii_domain_deny_list_extra.sql

    -- ============================================================
    -- 1. TABLE: public.agent_todos (TODO-01)
    -- ============================================================
    CREATE TABLE IF NOT EXISTS public.agent_todos (
      id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      thread_id   UUID NOT NULL REFERENCES public.threads(id) ON DELETE CASCADE,
      user_id     UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
      content     TEXT NOT NULL,
      status      TEXT NOT NULL CHECK (status IN ('pending','in_progress','completed')),
      position    INTEGER NOT NULL,
      created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
      updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    -- ============================================================
    -- 2. INDEXES
    -- ============================================================
    CREATE INDEX IF NOT EXISTS idx_agent_todos_thread
      ON public.agent_todos(thread_id, position);
    CREATE INDEX IF NOT EXISTS idx_agent_todos_user
      ON public.agent_todos(user_id, created_at DESC);

    -- ============================================================
    -- 3. updated_at trigger (reuses handle_updated_at from migration 001)
    -- ============================================================
    DROP TRIGGER IF EXISTS handle_agent_todos_updated_at ON public.agent_todos;
    CREATE TRIGGER handle_agent_todos_updated_at
      BEFORE UPDATE ON public.agent_todos
      FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

    -- ============================================================
    -- 4. ROW-LEVEL SECURITY (SEC-01) — thread-ownership scope
    -- ============================================================
    ALTER TABLE public.agent_todos ENABLE ROW LEVEL SECURITY;

    DROP POLICY IF EXISTS "agent_todos_select" ON public.agent_todos;
    CREATE POLICY "agent_todos_select"
      ON public.agent_todos
      FOR SELECT
      USING (user_id = auth.uid());

    DROP POLICY IF EXISTS "agent_todos_insert" ON public.agent_todos;
    CREATE POLICY "agent_todos_insert"
      ON public.agent_todos
      FOR INSERT
      WITH CHECK (
        user_id = auth.uid()
        AND EXISTS (
          SELECT 1 FROM public.threads t
          WHERE t.id = agent_todos.thread_id
            AND t.user_id = auth.uid()
        )
      );

    DROP POLICY IF EXISTS "agent_todos_update" ON public.agent_todos;
    CREATE POLICY "agent_todos_update"
      ON public.agent_todos
      FOR UPDATE
      USING (user_id = auth.uid())
      WITH CHECK (user_id = auth.uid());

    DROP POLICY IF EXISTS "agent_todos_delete" ON public.agent_todos;
    CREATE POLICY "agent_todos_delete"
      ON public.agent_todos
      FOR DELETE
      USING (user_id = auth.uid());

    -- ============================================================
    -- 5. ALTER TABLE: messages.deep_mode (MIG-04 / DEEP-04)
    -- ============================================================
    -- Default false applies to existing rows automatically.
    ALTER TABLE public.messages
      ADD COLUMN IF NOT EXISTS deep_mode BOOLEAN NOT NULL DEFAULT false;
    ```

    Save the file. Do NOT push to Supabase yet — Task 3 does that as a deliberate manual step (per D-38).
  </action>
  <verify>
    <automated>test -f supabase/migrations/038_agent_todos_and_deep_mode.sql && grep -q "create table if not exists public.agent_todos" supabase/migrations/038_agent_todos_and_deep_mode.sql -i && grep -qi "alter table public.messages" supabase/migrations/038_agent_todos_and_deep_mode.sql && grep -qi "enable row level security" supabase/migrations/038_agent_todos_and_deep_mode.sql</automated>
  </verify>
  <done>Migration file exists at the correct path, contains all 5 sections (table, indexes, trigger, RLS, ALTER messages), idempotent guards applied (IF NOT EXISTS / DROP POLICY IF EXISTS).</done>
</task>

<task type="checkpoint:human-action" gate="blocking">
  <name>Task 3: HUMAN — apply migration 038 to Supabase project qedhulpfezucnfadlfiz</name>
  <what-built>Migration 038 SQL file authored, ready to apply.</what-built>
  <how-to-verify>
    From repo root, run the Supabase push command (manual per D-38 — never auto-applied by execute-phase):

    ```
    supabase db push
    ```

    OR via the Supabase SQL editor, copy/paste the contents of `supabase/migrations/038_agent_todos_and_deep_mode.sql` and execute against the `qedhulpfezucnfadlfiz` project.

    Verify by running the test suite from Task 1 — all 6 tests should now PASS (TDD GREEN):
    ```
    cd backend && source venv/bin/activate && \
      TEST_EMAIL="test@test.com" TEST_PASSWORD='!*-3-3?3uZ?b$v&' \
      TEST_EMAIL_2="test-2@test.com" TEST_PASSWORD_2='fK4$Wd?HGKmb#A2' \
      pytest tests/integration/test_migration_038_agent_todos.py -v
    ```

    Expected: 6 passed.

    NOTE: After applying, the PreToolUse hook will block any further edits to migration 038. Get the schema right BEFORE pushing.
  </how-to-verify>
  <resume-signal>Type "applied" once `pytest tests/integration/test_migration_038_agent_todos.py -v` reports `6 passed`. Otherwise describe failure.</resume-signal>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| client→Supabase (direct SDK) | Authenticated Supabase JS client could attempt cross-tenant reads/writes against agent_todos via direct SQL or PostgREST |
| LLM tool→DB (server-side via service-role token) | Server-side write_todos calls must use the user's JWT-scoped client, not the service-role bypass — RLS only protects when the right client is used |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-17-01 | I (Information Disclosure) | agent_todos cross-user read | mitigate | RLS policy `agent_todos_select USING (user_id = auth.uid())` enforced; SEC-01 regression test in Task 1 asserts User A cannot read User B's todos |
| T-17-02 | T (Tampering) | agent_todos cross-user write | mitigate | RLS INSERT policy includes `EXISTS (... threads.user_id = auth.uid())` — defense-in-depth blocks insertion against another user's thread even if user_id is correctly forged |
| T-17-03 | E (Elevation of Privilege) | service-role bypass for write_todos | accept | Plan 17-04 will mandate `get_supabase_authed_client(token)` for the tool implementation; service-role client is forbidden in user-facing tool calls per project convention; documented in tool service plan |

</threat_model>

<verification>
- File `supabase/migrations/038_agent_todos_and_deep_mode.sql` is the next sequential migration after 037; numbering is monotonic.
- `pytest tests/integration/test_migration_038_agent_todos.py -v` returns 6 passed after Task 3 applies the migration.
- Schema columns, types, defaults, indexes, RLS policies all match the spec.
- `messages.deep_mode` column exists, is BOOLEAN NOT NULL DEFAULT false, and existing pre-migration rows now carry `false`.
- RLS regression test (User A vs User B) PASSES — the SEC-01 invariant is verified by automated assertion, not by inspection.
- `handle_updated_at` trigger (from migration 001) fires on agent_todos UPDATE.
</verification>

<success_criteria>
- Migration file authored, applied to Supabase, and frozen (PreToolUse hook will block further edits).
- All 6 integration tests pass.
- TODO-01, MIG-01, MIG-04, SEC-01 are all observably satisfied.
- Phase 17 unblocked: every downstream plan (config + tool + chat-loop + UI + REST endpoint) can now read/write `agent_todos` and `messages.deep_mode`.
</success_criteria>

<output>
After completion, create `.planning/phases/17-deep-mode-foundation-planning-todos-plan-panel/17-01-SUMMARY.md`
</output>
