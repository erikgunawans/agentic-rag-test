---
phase: 03-entity-resolution-llm-provider-configuration
plan: 02
type: execute
wave: 2
depends_on: [01]
files_modified: []
autonomous: true
requirements_addressed: [PROVIDER-06, RESOLVE-01]
must_haves:
  truths:
    - "Migration 030 is applied to the live Supabase database (project qedhulpfezucnfadlfiz)"
    - "system_settings has all 9 new columns queryable from the live DB"
    - "DB CHECK constraints reject bad enum values at the DB layer (23514) — defense-in-depth per D-60"
    - "Existing system_settings row (id=1) keeps its prior column values; new columns get their declared defaults"
  artifacts:
    - path: "supabase/migrations/030_pii_provider_settings.sql"
      provides: "Applied DDL on live Supabase project qedhulpfezucnfadlfiz"
      contains: "entity_resolution_mode"
  key_links:
    - from: "local migration file 030_pii_provider_settings.sql"
      to: "live Supabase database (qedhulpfezucnfadlfiz)"
      via: "Supabase MCP apply_migration"
      pattern: "apply_migration"
---

<objective>
[BLOCKING] Apply migration 030 to the live Supabase database (project `qedhulpfezucnfadlfiz`) so every downstream Phase 3 plan that reads the new `system_settings` columns runs against a real schema.

Purpose: Without this push, `get_system_settings()` raises at runtime when any code path touches the new columns — false-positive build/type checks pass while runtime fails. Plans 03-04 (`llm_provider.py` reads `system_settings.llm_provider`), 03-05 (redaction-service wiring reads mode), 03-06 (admin PATCH writes new columns), and 03-07 (tests query against the live shape) all depend on this.

Output: Live `system_settings` table on project `qedhulpfezucnfadlfiz` carrying all 9 new columns. The single existing row (`id=1`) gets the declared defaults for every new column on the ALTER TABLE pass.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/03-entity-resolution-llm-provider-configuration/03-CONTEXT.md
@CLAUDE.md
@supabase/migrations/030_pii_provider_settings.sql
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: [BLOCKING] Apply migration 030 to live Supabase via MCP apply_migration</name>
  <files></files>
  <read_first>
    - supabase/migrations/030_pii_provider_settings.sql (Plan 03-01 output — confirm present and well-formed before applying)
    - .planning/phases/02-conversation-scoped-registry-and-round-trip/02-03-supabase-db-push-PLAN.md (Phase 2 precedent — same shape; that plan used Supabase MCP apply_migration on project qedhulpfezucnfadlfiz)
    - .planning/phases/03-entity-resolution-llm-provider-configuration/03-CONTEXT.md decisions D-57 (column shape), D-60 (CHECK enums)
    - CLAUDE.md "Supabase project: qedhulpfezucnfadlfiz" reference
  </read_first>
  <action>
This task is BLOCKING — every Plan 03-04..03-07 task that reads new system_settings columns fails at runtime without it. The push command is non-destructive (additive ALTER TABLE; no schema changes to existing columns).

Pre-check (fail fast if Plan 03-01 Task 2 did not run):
```bash
test -f supabase/migrations/030_pii_provider_settings.sql || { echo "MIGRATION FILE MISSING — Plan 03-01 Task 2 did not run"; exit 1; }
```

**Apply path (PROJECT PRECEDENT — Phase 2 plan 02-03):** Use the Supabase MCP `apply_migration` tool directly against project `qedhulpfezucnfadlfiz`. Read the file content from `supabase/migrations/030_pii_provider_settings.sql` and pass it as the `query` arg with `name: "pii_provider_settings"` (Supabase auto-prefixes the timestamp; the version row in `supabase_migrations.schema_migrations` will be the timestamp + name).

If the Supabase MCP is unavailable in the executor's environment, the CLI fallback is:
```bash
supabase db push --include-all
```
Pipe `yes` if prompted:
```bash
yes | supabase db push --include-all
```
Set `SUPABASE_ACCESS_TOKEN` from environment if non-TTY:
```bash
SUPABASE_ACCESS_TOKEN="$SUPABASE_ACCESS_TOKEN" supabase db push --include-all
```

Either path is acceptable. The acceptance criterion is that the migration appears in `list_migrations` afterwards AND the new columns are queryable.

**Post-apply verification (MANDATORY — do not move to Wave 3 without ALL of these passing):**

1. List migrations via Supabase MCP `list_migrations` and confirm a row matches `030` / `pii_provider_settings`:
   - Expected: a row with `version` matching the just-applied timestamp AND `name = "pii_provider_settings"` (Supabase MCP form) OR a `name` containing `030_pii_provider_settings` (CLI form).

2. Confirm the new columns exist via Python + supabase-py service-role client (the project's standard verification path; psql credentials are not always available):
```bash
cd backend && source venv/bin/activate && python -c "
from app.database import get_supabase_client
client = get_supabase_client()
res = client.table('system_settings').select('id,entity_resolution_mode,llm_provider,llm_provider_fallback_enabled,entity_resolution_llm_provider,missed_scan_llm_provider,title_gen_llm_provider,metadata_llm_provider,fuzzy_deanon_llm_provider,pii_missed_scan_enabled').eq('id', 1).single().execute()
row = res.data
assert row['entity_resolution_mode'] == 'algorithmic', f'expected algorithmic, got {row[\"entity_resolution_mode\"]}'
assert row['llm_provider'] == 'local', f'expected local, got {row[\"llm_provider\"]}'
assert row['llm_provider_fallback_enabled'] is False
assert row['pii_missed_scan_enabled'] is True
assert row['entity_resolution_llm_provider'] is None
assert row['missed_scan_llm_provider'] is None
assert row['title_gen_llm_provider'] is None
assert row['metadata_llm_provider'] is None
assert row['fuzzy_deanon_llm_provider'] is None
print('NEW_COLUMNS_PRESENT_WITH_DEFAULTS')
"
```
If this raises `column \"entity_resolution_mode\" does not exist` (PGRST or similar), the apply did NOT land. Re-run apply_migration / supabase db push and re-verify. Do NOT proceed.

3. Confirm CHECK constraints reject bad values (defense-in-depth proof for D-60). This is a DESTRUCTIVE-LOOKING but actually safe probe — we attempt an UPDATE with a bogus enum value and confirm Postgres raises 23514:
```bash
cd backend && source venv/bin/activate && python -c "
from app.database import get_supabase_client
client = get_supabase_client()
try:
    client.table('system_settings').update({'entity_resolution_mode': 'invalid_mode_xyz'}).eq('id', 1).execute()
    print('CHECK_CONSTRAINT_BROKEN — DB accepted bad enum value')
    raise SystemExit(1)
except Exception as e:
    msg = str(e).lower()
    if 'check' in msg or '23514' in msg or 'violates' in msg:
        print('CHECK_CONSTRAINT_OK')
    else:
        print(f'UNEXPECTED_ERROR: {e}')
        raise SystemExit(1)
"
```
Expected output: `CHECK_CONSTRAINT_OK`.

4. Smoke-test `get_system_settings()` reads the new columns (the 60s TTL cache wraps the read; this is what every consumer in Phase 3 uses):
```bash
cd backend && source venv/bin/activate && python -c "
from app.services.system_settings_service import get_system_settings
s = get_system_settings()
assert 'entity_resolution_mode' in s, f'cache shape missing key; got: {sorted(s.keys())}'
assert s['entity_resolution_mode'] == 'algorithmic'
assert s['llm_provider'] == 'local'
print('SETTINGS_SERVICE_READS_NEW_COLUMNS')
"
```

If ANY of steps 1-4 fail, mark the task incomplete and re-apply. Wave 3 + Wave 4 + Wave 5 are gated on this task's success.

DO NOT commit any new files — this task only produces a DB-side change. The local migration file from Plan 03-01 is the artifact; this task makes it live.
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && python -c "
from app.database import get_supabase_client
client = get_supabase_client()
res = client.table('system_settings').select('id,entity_resolution_mode,llm_provider,llm_provider_fallback_enabled,entity_resolution_llm_provider,missed_scan_llm_provider,title_gen_llm_provider,metadata_llm_provider,fuzzy_deanon_llm_provider,pii_missed_scan_enabled').eq('id', 1).single().execute()
row = res.data
assert row['entity_resolution_mode'] == 'algorithmic'
assert row['llm_provider'] == 'local'
assert row['llm_provider_fallback_enabled'] is False
assert row['pii_missed_scan_enabled'] is True
print('MIGRATION_030_APPLIED_OK')
" 2>&1 | grep -q "MIGRATION_030_APPLIED_OK"</automated>
  </verify>
  <acceptance_criteria>
    - Supabase MCP `list_migrations` (or CLI `supabase migration list`) returns a row whose name matches `pii_provider_settings` (timestamp prefix may vary).
    - The verification Python script returns exit 0 with output `NEW_COLUMNS_PRESENT_WITH_DEFAULTS` — all 9 new columns are present on `system_settings.id=1`, with values: `entity_resolution_mode='algorithmic'`, `llm_provider='local'`, `llm_provider_fallback_enabled=False`, 5 per-feature overrides = None, `pii_missed_scan_enabled=True`.
    - The CHECK-constraint probe returns `CHECK_CONSTRAINT_OK` (Postgres rejects `entity_resolution_mode = 'invalid_mode_xyz'` with a 23514-class error).
    - The `get_system_settings()` smoke-test prints `SETTINGS_SERVICE_READS_NEW_COLUMNS` (the cache returns a dict containing the new keys).
    - Backend imports cleanly: `python -c "from app.main import app; print('OK')"` returns `OK`.
    - Phase 1 + Phase 2 regression still passes (`pytest tests/`) — additive ALTER TABLE does not change existing column values.
  </acceptance_criteria>
  <done>Migration 030 applied to live DB; new columns queryable; CHECK constraints active; existing 39/39 tests still pass; Plan 03-04..03-07 unblocked.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| local migration file → live DB | This task crosses this boundary; once applied, the migration is irreversible without an explicit rollback migration |
| operator → Supabase project | The MCP / CLI uses service-role credentials; only the deployer's machine should hold these |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-DDL-01 | Tampering | Migration applied with bad column types / constraints | mitigate | Plan 03-01 Task 2 acceptance criteria already validated the SQL; this task only APPLIES the validated file. Post-apply step 2 confirms columns + defaults match. |
| T-CONFIG-01 | Tampering | DB row updated with bad enum value via SQL or PostgREST | mitigate | Post-apply step 3 actively probes CHECK constraints (23514 on bogus value) — defense-in-depth proof for D-60 |
| T-AUDIT-01 | Repudiation | DDL change unaudited | accept | Migration applies are version-controlled in `supabase_migrations.schema_migrations`; the project's standard audit posture for DDL relies on the git-committed migration file + the schema_migrations row. No new audit code needed. |
</threat_model>

<verification>
After this plan completes:
- Supabase MCP `list_migrations` shows the `pii_provider_settings` migration applied.
- All 9 new columns queryable on `system_settings` (id=1) with declared defaults.
- CHECK constraints actively reject bad enum values (probe returns 23514).
- `get_system_settings()` returns a dict containing the new keys.
- Backend imports cleanly; 39/39 prior tests still pass.
- Plans 03-04 (`llm_provider.py`), 03-05 (redaction-service wiring), 03-06 (admin router + UI), 03-07 (tests) are all unblocked.
</verification>

<success_criteria>
- Migration 030 applied to project `qedhulpfezucnfadlfiz`.
- All 9 new columns present on `system_settings.id=1` with the declared defaults from D-57.
- CHECK constraints active (mirror Pydantic Literal sets — D-60).
- No regression on prior columns or RLS posture.
- Phase 1 + Phase 2 tests still pass.
</success_criteria>

<output>
Create `.planning/phases/03-entity-resolution-llm-provider-configuration/03-02-SUMMARY.md` with:
- Apply path used (Supabase MCP apply_migration vs CLI supabase db push)
- list_migrations output snippet showing the new row
- All 9 new columns confirmed queryable with defaults
- CHECK-constraint probe result
- Phase 1+2 regression: 39/39 still pass
- Plans 03-04..03-07 are now unblocked.
</output>
