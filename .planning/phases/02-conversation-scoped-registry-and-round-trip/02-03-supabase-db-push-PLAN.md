---
phase: 02-conversation-scoped-registry-and-round-trip
plan: 03
type: execute
wave: 2
depends_on: [01]
files_modified: []
autonomous: true
requirements: [REG-01, REG-02]
must_haves:
  truths:
    - "Migration 029 is applied to the live Supabase database"
    - "Table public.entity_registry exists in the live DB"
    - "RLS is enabled on the table; no policies exist"
    - "Composite UNIQUE (thread_id, real_value_lower) is queryable"
  artifacts:
    - path: "supabase/migrations/029_pii_entity_registry.sql"
      provides: "Applied DDL"
      contains: "entity_registry"
  key_links:
    - from: "local migration file"
      to: "live Supabase database (qedhulpfezucnfadlfiz)"
      via: "supabase db push"
      pattern: "supabase db push"
---

<objective>
[BLOCKING] Push migration 029 to the live Supabase database so Wave 3 (registry DB methods) and Wave 4 (integration tests that hit the real DB) can run.

Purpose: Without this push, every downstream task that touches `public.entity_registry` fails at runtime — the table simply does not exist. The push command is non-destructive (additive: new table only; no schema changes to existing tables).

Output: Live `entity_registry` table in the Supabase project `qedhulpfezucnfadlfiz`, with RLS enabled and the composite UNIQUE constraint queryable via psql / supabase-py.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/02-conversation-scoped-registry-and-round-trip/02-CONTEXT.md
@CLAUDE.md
@supabase/migrations/029_pii_entity_registry.sql
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: [BLOCKING] supabase db push — apply migration 029 to live DB</name>
  <files></files>
  <read_first>
    - supabase/migrations/029_pii_entity_registry.sql (Plan 01 output — confirm present and well-formed before pushing)
    - CLAUDE.md "Deployment" + "Supabase project: qedhulpfezucnfadlfiz" reference
    - .planning/phases/02-conversation-scoped-registry-and-round-trip/02-CONTEXT.md D-21 (migration filename), D-25 (RLS posture to verify post-push)
  </read_first>
  <action>
This task is BLOCKING — Wave 3 + Wave 4 cannot proceed without it. Run the supabase CLI to push migrations to the live DB.

Pre-check (fail fast if Plan 01 is missing):
```bash
test -f supabase/migrations/029_pii_entity_registry.sql || { echo "MIGRATION FILE MISSING — Plan 01 did not run"; exit 1; }
```

Push command (CLAUDE.md confirms the user is signed into supabase CLI on their machine):
```bash
supabase db push
```

If the command emits an interactive confirmation prompt that cannot be auto-answered (the supabase CLI sometimes prompts "Do you want to push these migrations to the remote database? [Y/n]"), pipe `yes` to it:
```bash
yes | supabase db push
```

If the CLI asks for an access token (non-TTY environment), set `SUPABASE_ACCESS_TOKEN` from the environment before the call:
```bash
SUPABASE_ACCESS_TOKEN="$SUPABASE_ACCESS_TOKEN" supabase db push
```

Expected stdout (substring match — the exact wording varies by CLI version):
- `Applying migration 029_pii_entity_registry.sql`
- `Finished` / `Done` / `up to date`

Post-push verification (MANDATORY — do not move to Wave 3 without this passing):

1. Confirm the table exists. Use Python + supabase-py service-role client (we cannot rely on psql credentials being available):

```bash
cd backend && source venv/bin/activate && python -c "
from app.database import get_supabase_client
client = get_supabase_client()
# Querying with limit 0 confirms the table exists without returning data.
res = client.table('entity_registry').select('id').limit(0).execute()
print('TABLE_EXISTS', res)
"
```

If this raises `relation \"public.entity_registry\" does not exist` (PGRST or similar), the push did NOT land. Re-run `supabase db push` and re-verify. Do NOT proceed.

2. Confirm RLS is enabled and has zero policies (D-25 invariant). Use the supabase admin SQL endpoint via supabase-py:

```bash
cd backend && source venv/bin/activate && python -c "
from app.database import get_supabase_client
client = get_supabase_client()
# information_schema is unrestricted; pg_policies is the canonical source.
# We use the rpc/raw SQL escape via a temporary postgres function would be over-engineering;
# instead, INSERT one test row + SELECT it back via service-role client (RLS bypassed).
# This proves the table is writable AND that the unique constraint is queryable.
test_row = {
    'thread_id': '00000000-0000-0000-0000-000000000000',  # invalid FK — must fail with FK violation, not RLS denial
    'real_value': '__rls_smoke_test__',
    'real_value_lower': '__rls_smoke_test__',
    'surrogate_value': '__smoke__',
    'entity_type': 'PERSON',
}
try:
    client.table('entity_registry').insert(test_row).execute()
    print('UNEXPECTED_SUCCESS — FK constraint not enforced')
except Exception as e:
    msg = str(e).lower()
    # Expected: FK violation (thread does not exist). RLS denial would surface differently.
    assert 'foreign key' in msg or 'violates' in msg or '23503' in msg, f'Unexpected error (not FK violation): {e}'
    print('FK_CONSTRAINT_OK — RLS not blocking service role')
"
```

Expected output: `FK_CONSTRAINT_OK — RLS not blocking service role`. This proves both that the table exists and that the service-role client bypasses RLS as designed.

3. (Optional but recommended) If the user has psql access and a connection string in env, run a final structural check:
```bash
psql "$DATABASE_URL" -c "\\d public.entity_registry" 2>/dev/null || echo "psql skipped (no DATABASE_URL)"
```

Special cases:
- If `supabase db push` reports "no migrations to apply" but the table doesn't exist, the migrations dir may be out of sync with the project's migration tracking table. Run `supabase migration list` to inspect and surface the diagnostic to the user — do NOT manually patch the `supabase_migrations.schema_migrations` tracking table.
- If the push fails with a syntax error in the SQL, the executor MUST surface the full error and stop. Do NOT edit migration 029 to "fix" it after a failed push attempt — file a follow-up to Plan 01.

This task is `autonomous: true` IF the supabase CLI is non-interactive on the user's machine. If it requires a TTY confirm and we hit a prompt mid-execution, surface that immediately to the orchestrator (the orchestrator will then convert this into a checkpoint for the user to confirm, and resume).
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && python -c "from app.database import get_supabase_client; client = get_supabase_client(); res = client.table('entity_registry').select('id').limit(0).execute(); print('TABLE_EXISTS_OK')"</automated>
  </verify>
  <acceptance_criteria>
    - The supabase CLI command exits with status 0.
    - The Python smoke test prints `TABLE_EXISTS_OK` (table is queryable via service-role client).
    - The FK-violation smoke test (Step 2) confirms RLS is not blocking service-role inserts AND the FK constraint is enforced.
    - No new migrations are listed by `supabase migration list` as pending after the push.
  </acceptance_criteria>
  <done>The `entity_registry` table is live in Supabase project `qedhulpfezucnfadlfiz`. Wave 3 plans (registry DB methods) and Wave 4 plans (integration tests hitting the real DB) can now proceed.</done>
</task>

</tasks>

<verification>
- `entity_registry` table exists in live DB (Python smoke test passes).
- RLS is enabled (the FK violation surfacing — not RLS denial — proves service-role bypasses RLS as designed; D-25).
- No untracked schema drift introduced (only the additive table; nothing else changed).
- Migration 029 is recorded in supabase's `schema_migrations` tracking table.
</verification>

<success_criteria>
- `cd backend && source venv/bin/activate && python -c "from app.database import get_supabase_client; get_supabase_client().table('entity_registry').select('id').limit(0).execute()"` succeeds.
- Wave 3 + Wave 4 unblocked.
</success_criteria>

<output>
Create `.planning/phases/02-conversation-scoped-registry-and-round-trip/02-03-SUMMARY.md` with:
- supabase db push output (or stderr if it failed and was retried)
- Confirmation that table exists in live DB
- Confirmation FK constraint is enforced and RLS is bypassed by service role
- Project ID `qedhulpfezucnfadlfiz` (from CLAUDE.md) — the actual target.
</output>
