---
phase: 04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/app/config.py
  - supabase/migrations/031_pii_fuzzy_settings.sql
autonomous: true
requirements_addressed: [DEANON-03]
tags: [pii, fuzzy-deanon, config, migration, supabase, schema-push]
must_haves:
  truths:
    - "Settings class exposes fuzzy_deanon_mode (Literal['algorithmic','llm','none'], default 'none') and fuzzy_deanon_threshold (float, default 0.85, range [0.50, 1.00]) — both env-var-backed (D-67/D-69)"
    - "Migration file 031_pii_fuzzy_settings.sql exists, well-formed SQL, mirrors migration 030 shape — adds 2 columns to system_settings"
    - "DB CHECK constraints reject bad enum values (23514) and out-of-range threshold values at the DB layer — defense-in-depth per D-60 / D-69"
    - "Migration 031 is APPLIED to live Supabase project qedhulpfezucnfadlfiz; the new columns are queryable from the live DB ([BLOCKING] schema push completes within this plan)"
    - "No edits to applied migrations 001-030 (CLAUDE.md gotcha — PreToolUse hook blocks edits to applied migrations)"
  artifacts:
    - path: "backend/app/config.py"
      provides: "Phase 4 env-var-backed Settings fields fuzzy_deanon_mode + fuzzy_deanon_threshold"
      contains: "fuzzy_deanon_mode"
    - path: "supabase/migrations/031_pii_fuzzy_settings.sql"
      provides: "ALTER TABLE system_settings DDL — 2 new columns with CHECK constraints"
      contains: "alter table system_settings"
  key_links:
    - from: "backend/app/config.py"
      to: "system_settings columns (live Supabase qedhulpfezucnfadlfiz)"
      via: "Pydantic Literal type matches DB CHECK enum exactly (D-60 defense-in-depth)"
      pattern: "Literal\\[['\\\"]algorithmic['\\\"], ['\\\"]llm['\\\"], ['\\\"]none['\\\"]\\]"
    - from: "supabase/migrations/031_pii_fuzzy_settings.sql"
      to: "live Supabase qedhulpfezucnfadlfiz"
      via: "Supabase MCP apply_migration (precedent: Phase 2 plan 02-03 + Phase 3 plan 03-02)"
      pattern: "apply_migration"
threat_model:
  trust_boundaries:
    - "config.py env-var read → application memory (deploy-time secret surface; no runtime input)"
    - "supabase migration → live DB (one-time admin DDL; service-role context)"
  threats:
    - id: "T-04-01-1"
      category: "Tampering"
      component: "fuzzy_deanon_threshold env var / DB column"
      severity: "low"
      disposition: "mitigate"
      mitigation: "Pydantic Field(ge=0.50, le=1.00) at API layer + DB CHECK (>= 0.50 AND <= 1.00) at data layer (defense-in-depth per D-60). Out-of-range values cannot be inserted via either surface."
    - id: "T-04-01-2"
      category: "Tampering"
      component: "fuzzy_deanon_mode env var / DB column"
      severity: "low"
      disposition: "mitigate"
      mitigation: "Pydantic Literal['algorithmic','llm','none'] at API layer + DB CHECK at data layer. Invalid mode strings rejected at both layers."
    - id: "T-04-01-3"
      category: "Information Disclosure"
      component: "Migration 031 SQL file in repo"
      severity: "low"
      disposition: "accept"
      mitigation: "DDL only; no data; no secrets. system_settings table already has service-role-only RLS from earlier migrations — no new policy surface."
---

<objective>
Ship the two parallel-independent foundation artifacts plus the [BLOCKING] schema push: the env-var-backed `Settings` field block extension on `app/config.py` (D-67/D-69) and the SQL migration `031_pii_fuzzy_settings.sql` (D-69 / D-70), then APPLY migration 031 to the live Supabase project so every downstream Phase 4 plan that reads the new columns runs against a real schema.

Purpose: These are the schema + config primitives every downstream Phase 4 plan reads from. Plan 04-04 (`missed_scan.py` reads `pii_missed_scan_enabled` — already shipped in 030 — and operates on the Phase 4-extended settings surface), Plan 04-03 (`de_anonymize_text` reads `fuzzy_deanon_mode` + `fuzzy_deanon_threshold`), Plan 04-06 (admin PATCH writes the new columns), and Plan 04-07 (integration tests query the live shape) ALL depend on this plan's outputs being live.

Output: Three changes:
1. `backend/app/config.py` extended with 2 new fields (`fuzzy_deanon_mode`, `fuzzy_deanon_threshold`).
2. `supabase/migrations/031_pii_fuzzy_settings.sql` written to disk.
3. Migration applied to live Supabase project `qedhulpfezucnfadlfiz` — verified via `information_schema.columns` query.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance/04-CONTEXT.md
@.planning/phases/04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance/04-PATTERNS.md
@CLAUDE.md
@backend/app/config.py
@supabase/migrations/030_pii_provider_settings.sql

<interfaces>
<!-- Existing primitives this plan extends. Read once; no codebase exploration needed. -->

From backend/app/config.py (Phase 1+2+3 baseline — Pydantic BaseSettings field block ends with):
```python
class Settings(BaseSettings):
    # ... earlier fields (Phase 1+2+3 PII fields) ...
    pii_missed_scan_enabled: bool = True   # ← Phase 3 D-57 forward-compat (Phase 4 consumes)
    # Phase 4 fields go HERE.
```

From supabase/migrations/030_pii_provider_settings.sql (Phase 3 — exact mirror template):
```sql
-- 030: PII Provider Settings — entity_resolution_mode + llm_provider + ... (Phase 3)
-- Extends the single-row system_settings table with 9 new columns per D-57.
-- DB CHECK constraints mirror the Pydantic Literal sets in app.config.Settings
-- and the SystemSettingsUpdate model (defense in depth — D-60).

alter table system_settings
  add column entity_resolution_mode text not null default 'algorithmic'
    check (entity_resolution_mode in ('algorithmic','llm','none')),
  -- ... 8 more columns ...
;

comment on column system_settings.entity_resolution_mode is
  'Phase 3 entity resolution mode: algorithmic | llm | none. PRD §4.FR-4.1.';
```

From admin_settings.py L29 (existing Literal pattern Phase 4 mirrors):
```python
rag_rerank_mode: Literal["none", "llm", "cohere"] | None = None
```

From CLAUDE.md gotchas:
- "Migrations are numbered sequentially (`001_` through `027_`). Use `/create-migration` to generate the next one. Never edit applied migrations (hook blocks 001-027)."
- Note: as of 2026-04-27, applied migrations are 001-030 (Phase 3 added 030). Migration 031 is the next free number.
- "Supabase project: `qedhulpfezucnfadlfiz`"
</interfaces>
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: Extend Settings with fuzzy_deanon_mode + fuzzy_deanon_threshold fields (D-67/D-69)</name>
  <files>backend/app/config.py</files>
  <read_first>
    - backend/app/config.py (the file being modified — read entirely; locate the existing Phase 1+2+3 PII fields and the line where `pii_missed_scan_enabled: bool = True` is defined)
    - .planning/phases/04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance/04-PATTERNS.md "MODIFIED · backend/app/config.py" section (verbatim splice template lines 762-781)
    - .planning/phases/04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance/04-CONTEXT.md decisions D-67 (rapidfuzz), D-69 (default 0.85, range 0.50-1.00), D-70 (normalization invariants)
    - .planning/phases/03-entity-resolution-llm-provider-configuration/03-01-config-and-migration-030-PLAN.md (Phase 3 analog — same Literal + Field pattern at the same call site)
  </read_first>
  <action>
Extend `backend/app/config.py` with two new Pydantic Settings fields, appended IMMEDIATELY AFTER the existing `pii_missed_scan_enabled: bool = True` line (Phase 3 forward-compat marker).

**Imports** — verify `Field` from `pydantic` is imported at the top of the file. If not present, add:
```python
from pydantic import Field
```
(Pydantic v2 re-exports `Field` from the top-level `pydantic` package; this is the same import already used elsewhere in the codebase per the Phase 3 pattern.)

**Field additions** (verbatim — D-67/D-69 / FR-5.4):
```python
    # Phase 4: Fuzzy de-anonymization (D-67..D-70 / FR-5.4)
    # Mirrors entity_resolution_mode pattern (Phase 3) — same Literal set.
    fuzzy_deanon_mode: Literal["algorithmic", "llm", "none"] = "none"
    # D-69: PRD-mandated default 0.85; range [0.50, 1.00] (Pydantic + DB CHECK defense in depth).
    fuzzy_deanon_threshold: float = Field(default=0.85, ge=0.50, le=1.00)
```

**Placement rule**: these two fields MUST be appended AFTER the existing `pii_missed_scan_enabled` field (Phase 3 D-57 shipped that column to avoid Phase 4 migration churn). Do NOT reorder existing Phase 1+2+3 fields. Do NOT change any existing field's default.

**Env-var contract** (pydantic-settings auto-binds field name → `FUZZY_DEANON_MODE` and `FUZZY_DEANON_THRESHOLD` env vars per the existing `model_config` in this Settings class). Acceptable values:
- `FUZZY_DEANON_MODE`: one of `algorithmic` / `llm` / `none` (Pydantic Literal validates; mismatch raises `ValidationError` at app startup — fail-fast).
- `FUZZY_DEANON_THRESHOLD`: float in `[0.50, 1.00]`. Out-of-range raises `ValidationError` at app startup.

**Verification immediately after edit**:
```bash
cd /Users/erikgunawansupriatna/claude-code-agentic-rag-masterclass-1/backend
source venv/bin/activate
python -c "from app.config import get_settings; s = get_settings(); assert s.fuzzy_deanon_mode == 'none' and s.fuzzy_deanon_threshold == 0.85; print('OK', s.fuzzy_deanon_mode, s.fuzzy_deanon_threshold)"
python -c "from app.main import app; print('main OK')"
```
Both lines must print `OK …` / `main OK` without traceback.
  </action>
  <verify>
    <automated>cd /Users/erikgunawansupriatna/claude-code-agentic-rag-masterclass-1/backend &amp;&amp; source venv/bin/activate &amp;&amp; python -c "from app.config import get_settings; s = get_settings(); assert s.fuzzy_deanon_mode == 'none', f'expected none got {s.fuzzy_deanon_mode}'; assert s.fuzzy_deanon_threshold == 0.85, f'expected 0.85 got {s.fuzzy_deanon_threshold}'; assert hasattr(s, 'pii_missed_scan_enabled'), 'pii_missed_scan_enabled regression'; print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n 'fuzzy_deanon_mode' backend/app/config.py` returns at least 1 line and that line is INSIDE the `Settings` class block.
    - `grep -n 'fuzzy_deanon_threshold' backend/app/config.py` returns at least 1 line and that line is INSIDE the `Settings` class block.
    - `grep -n 'Literal\["algorithmic", "llm", "none"\]' backend/app/config.py | grep -v '^#'` returns ≥ 2 lines (entity_resolution_mode + fuzzy_deanon_mode).
    - `grep -nE 'fuzzy_deanon_threshold:\s*float\s*=\s*Field\(default=0\.85,\s*ge=0\.50,\s*le=1\.00\)' backend/app/config.py` matches exactly 1 line.
    - `cd backend &amp;&amp; source venv/bin/activate &amp;&amp; python -c "from app.config import get_settings; s = get_settings(); assert s.fuzzy_deanon_mode == 'none'; assert s.fuzzy_deanon_threshold == 0.85"` exits 0.
    - `cd backend &amp;&amp; source venv/bin/activate &amp;&amp; FUZZY_DEANON_MODE=algorithmic python -c "from app.config import Settings; s = Settings(); assert s.fuzzy_deanon_mode == 'algorithmic'"` exits 0 (env-var binding works).
    - `cd backend &amp;&amp; source venv/bin/activate &amp;&amp; FUZZY_DEANON_MODE=bogus python -c "from app.config import Settings; Settings()" 2>&amp;1 | grep -qi 'validation\|literal\|input should be'` exits 0 (invalid enum rejected at API layer).
    - `cd backend &amp;&amp; source venv/bin/activate &amp;&amp; FUZZY_DEANON_THRESHOLD=0.49 python -c "from app.config import Settings; Settings()" 2>&amp;1 | grep -qiE 'validation|greater than|ge=' ` exits 0 (out-of-range rejected at API layer).
    - `cd backend &amp;&amp; source venv/bin/activate &amp;&amp; python -c "from app.main import app; print('OK')"` prints OK (PostToolUse hook full-import check passes).
    - No regression: `grep -c 'pii_missed_scan_enabled' backend/app/config.py` returns ≥ 1 (Phase 3 forward-compat field still present).
  </acceptance_criteria>
  <done>
config.py exposes fuzzy_deanon_mode + fuzzy_deanon_threshold as Pydantic-validated env-var-backed fields with the exact defaults from D-69 (none / 0.85). Pydantic enforces the Literal set and the numeric range. App imports cleanly.
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 2: Write migration 031_pii_fuzzy_settings.sql with CHECK constraints (D-69 / D-70)</name>
  <files>supabase/migrations/031_pii_fuzzy_settings.sql</files>
  <read_first>
    - supabase/migrations/030_pii_provider_settings.sql (exact-match analog — mirror its header comment style, ALTER TABLE shape, and `comment on column` block verbatim)
    - .planning/phases/04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance/04-PATTERNS.md "supabase/migrations/031_pii_fuzzy_settings.sql" section (full template lines 313-336)
    - .planning/phases/04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance/04-CONTEXT.md "Schema & Configuration Changes" section (canonical SQL block lines 192-200)
    - CLAUDE.md "Migrations are numbered sequentially. Never edit applied migrations." (PreToolUse hook blocks 001-027; current applied set extends to 030)
  </read_first>
  <action>
Write a NEW file `supabase/migrations/031_pii_fuzzy_settings.sql` containing the exact DDL below.

**File content (verbatim — copy-paste this block):**
```sql
-- 031: PII Fuzzy De-Anonymization Settings — fuzzy_deanon_mode + threshold (Phase 4)
-- Extends the single-row system_settings table with 2 new columns per D-67/D-69/D-70.
-- DB CHECK constraints mirror the Pydantic Literal sets in app.config.Settings
-- and the SystemSettingsUpdate model (defense in depth — D-60 / FR-5.4 / NFR-2).
-- See PRD-PII-Redaction-System-v1.1.md §4.FR-5.4 and 04-CONTEXT.md D-67..D-70.

alter table system_settings
  add column fuzzy_deanon_mode text not null default 'none'
    check (fuzzy_deanon_mode in ('algorithmic','llm','none')),
  add column fuzzy_deanon_threshold numeric(3,2) not null default 0.85
    check (fuzzy_deanon_threshold >= 0.50 and fuzzy_deanon_threshold <= 1.00);

-- system_settings already has RLS + service-role-only policy from earlier
-- migrations; no policy changes needed here. Per Phase 2 D-25 invariant the
-- registry/system_settings tables are service-role-only — no end-user PostgREST
-- access path. The PATCH route at /admin/settings is gated by require_admin.

comment on column system_settings.fuzzy_deanon_mode is
  'Phase 4 fuzzy de-anon mode: algorithmic (Jaro-Winkler) | llm | none. PRD §4.FR-5.4.';
comment on column system_settings.fuzzy_deanon_threshold is
  'D-69: Jaro-Winkler match threshold; PRD-mandated default 0.85. Range [0.50, 1.00].';
```

**Constraints** (must hold; verified by Task 4 against the live DB):
- Column `fuzzy_deanon_mode` is `text NOT NULL DEFAULT 'none'`, CHECK ∈ `{'algorithmic','llm','none'}`.
- Column `fuzzy_deanon_threshold` is `numeric(3,2) NOT NULL DEFAULT 0.85`, CHECK `>= 0.50 AND <= 1.00`.
- ZERO new tables. ZERO new policies. Single ALTER TABLE.
- DO NOT use `IF NOT EXISTS` — Supabase migrations track applied state via `supabase_migrations.schema_migrations`; the file is single-apply by design.

**Hook awareness**: the file path `supabase/migrations/031_pii_fuzzy_settings.sql` is NEW (not in the 001-030 hook-blocked set). Writing this file is allowed. Do NOT edit any of `001_*.sql` through `030_*.sql`.
  </action>
  <verify>
    <automated>cd /Users/erikgunawansupriatna/claude-code-agentic-rag-masterclass-1 &amp;&amp; test -f supabase/migrations/031_pii_fuzzy_settings.sql &amp;&amp; grep -qc 'alter table system_settings' supabase/migrations/031_pii_fuzzy_settings.sql &amp;&amp; grep -qE "check \(fuzzy_deanon_mode in \('algorithmic','llm','none'\)\)" supabase/migrations/031_pii_fuzzy_settings.sql &amp;&amp; grep -qE 'check \(fuzzy_deanon_threshold &gt;= 0\.50 and fuzzy_deanon_threshold &lt;= 1\.00\)' supabase/migrations/031_pii_fuzzy_settings.sql &amp;&amp; echo OK</automated>
  </verify>
  <acceptance_criteria>
    - `test -f supabase/migrations/031_pii_fuzzy_settings.sql` exits 0 (file exists).
    - `grep -v '^--' supabase/migrations/031_pii_fuzzy_settings.sql | grep -c 'alter table system_settings'` returns exactly 1.
    - `grep -v '^--' supabase/migrations/031_pii_fuzzy_settings.sql | grep -c 'add column fuzzy_deanon_mode text not null default '"'"'none'"'"'$\|add column fuzzy_deanon_mode text not null default '"'"'none'"'"','` returns ≥ 1 (column declaration present, allowing trailing comma OR end-of-line). A simpler check: `grep -c 'fuzzy_deanon_mode text not null default' supabase/migrations/031_pii_fuzzy_settings.sql` returns ≥ 1.
    - `grep -c 'fuzzy_deanon_threshold numeric(3,2) not null default 0.85' supabase/migrations/031_pii_fuzzy_settings.sql` returns ≥ 1.
    - `grep -cE "check \(fuzzy_deanon_mode in \('algorithmic','llm','none'\)\)" supabase/migrations/031_pii_fuzzy_settings.sql` returns ≥ 1.
    - `grep -cE 'check \(fuzzy_deanon_threshold >= 0\.50 and fuzzy_deanon_threshold <= 1\.00\)' supabase/migrations/031_pii_fuzzy_settings.sql` returns ≥ 1.
    - `grep -c 'comment on column system_settings.fuzzy_deanon_mode' supabase/migrations/031_pii_fuzzy_settings.sql` returns exactly 1.
    - `grep -c 'comment on column system_settings.fuzzy_deanon_threshold' supabase/migrations/031_pii_fuzzy_settings.sql` returns exactly 1.
    - NO file edits to `001_*.sql` through `030_*.sql` — `git status --porcelain supabase/migrations/ | grep -E 'M\s+supabase/migrations/0(0[0-9]|1[0-9]|2[0-9]|30)_'` returns empty (no modifications to applied migrations).
  </acceptance_criteria>
  <done>
Migration 031 file exists on disk with the exact DDL above. CHECK constraints encode D-69's range and D-67's mode set. No applied migrations were touched.
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 3: [BLOCKING] Apply migration 031 to live Supabase project qedhulpfezucnfadlfiz</name>
  <files></files>
  <read_first>
    - supabase/migrations/031_pii_fuzzy_settings.sql (Task 2 output — verify present and well-formed before applying)
    - .planning/phases/03-entity-resolution-llm-provider-configuration/03-02-apply-migration-030-PLAN.md (Phase 3 precedent — exact same shape; that plan applied migration 030 via Supabase MCP `apply_migration` against project qedhulpfezucnfadlfiz)
    - .planning/phases/02-conversation-scoped-registry-and-round-trip/02-03-supabase-db-push-PLAN.md (Phase 2 precedent — first use of Supabase MCP apply_migration)
    - CLAUDE.md "Supabase project: qedhulpfezucnfadlfiz" reference
  </read_first>
  <action>
**[BLOCKING]** This task gates every Plan 04-03 / 04-04 / 04-06 / 04-07 task that reads new system_settings columns. Without it, `get_system_settings()` raises at runtime when any code path touches `fuzzy_deanon_mode` or `fuzzy_deanon_threshold` — false-positive build/type checks pass while runtime fails.

**Pre-check** (fail fast if Task 2 did not run):
```bash
test -f supabase/migrations/031_pii_fuzzy_settings.sql || { echo "MIGRATION FILE MISSING — Task 2 did not run"; exit 1; }
```

**Apply path A (PROJECT PRECEDENT — Phase 2 plan 02-03 + Phase 3 plan 03-02):** Use the Supabase MCP `apply_migration` tool directly against project `qedhulpfezucnfadlfiz`. Read the SQL content from `supabase/migrations/031_pii_fuzzy_settings.sql` and call:

```
mcp__supabase__apply_migration(
  project_id="qedhulpfezucnfadlfiz",
  name="pii_fuzzy_settings",
  query="<full content of 031_pii_fuzzy_settings.sql>"
)
```

The version row in `supabase_migrations.schema_migrations` will be a timestamp + `pii_fuzzy_settings`.

**Apply path B (CLI fallback if MCP unavailable):**
```bash
cd /Users/erikgunawansupriatna/claude-code-agentic-rag-masterclass-1
yes | supabase db push --include-all
```
If non-TTY: `SUPABASE_ACCESS_TOKEN="$SUPABASE_ACCESS_TOKEN" supabase db push --include-all` (the env var is configured in the dev environment per Phase 3 precedent).

**Idempotence check before applying** — the migration is non-destructive (additive ALTER TABLE), but Supabase's tracking table prevents double-apply. If the version is already recorded (e.g., if a prior task partially ran), `apply_migration` will return an error like "migration already applied" — this is a benign success-state-equivalent for our purposes; log and proceed to verification.

**Verification AGAINST THE LIVE DB** (this is the load-bearing acceptance check — D-60 defense-in-depth, mandated by `<schema_push_requirement>` in the planning context):

Use the Supabase MCP `execute_sql` tool (or `psql` against the project URL with the service-role connection string) to run:
```sql
SELECT column_name, data_type, column_default, is_nullable
FROM information_schema.columns
WHERE table_name = 'system_settings'
  AND column_name IN ('fuzzy_deanon_mode', 'fuzzy_deanon_threshold')
ORDER BY column_name;
```

Expected result: exactly 2 rows.
- `fuzzy_deanon_mode` | `text` | `'none'::text` | `NO`
- `fuzzy_deanon_threshold` | `numeric` | `0.85` | `NO`

Also verify the CHECK constraint via:
```sql
SELECT conname, pg_get_constraintdef(oid)
FROM pg_constraint
WHERE conrelid = 'public.system_settings'::regclass
  AND contype = 'c'
  AND (pg_get_constraintdef(oid) LIKE '%fuzzy_deanon%');
```
Expected: 2 rows containing the expected CHECK clauses.

**On verification failure** — STOP. Do NOT proceed to other Phase 4 plans. Report the verification output to the user and request investigation. The wave-2/3 plans cannot run without this column being live.
  </action>
  <verify>
    <automated>cd /Users/erikgunawansupriatna/claude-code-agentic-rag-masterclass-1/backend &amp;&amp; source venv/bin/activate &amp;&amp; TEST_EMAIL="test@test.com" TEST_PASSWORD='!*-3-3?3uZ?b$v&amp;' python -c "
from app.database import get_supabase_client
client = get_supabase_client()
res = client.table('system_settings').select('id,fuzzy_deanon_mode,fuzzy_deanon_threshold').eq('id', 1).single().execute()
row = res.data
assert row['fuzzy_deanon_mode'] == 'none', f'expected none got {row[\"fuzzy_deanon_mode\"]}'
assert float(row['fuzzy_deanon_threshold']) == 0.85, f'expected 0.85 got {row[\"fuzzy_deanon_threshold\"]}'
print('LIVE-DB OK', row['fuzzy_deanon_mode'], row['fuzzy_deanon_threshold'])
"</automated>
  </verify>
  <acceptance_criteria>
    - The Supabase MCP `apply_migration` call (or `supabase db push`) returned success (or "already applied" — also acceptable; verify state via the next checks).
    - `information_schema.columns` query against the live DB returns exactly 2 rows for `system_settings` columns named `fuzzy_deanon_mode` and `fuzzy_deanon_threshold` with the documented data types / defaults / NOT NULL.
    - `pg_constraint` query against the live DB returns 2 CHECK constraint rows referencing `fuzzy_deanon_mode` (mode IN set) and `fuzzy_deanon_threshold` (range [0.50, 1.00]).
    - Reading row id=1 of `system_settings` via the application's `get_supabase_client()` returns `fuzzy_deanon_mode='none'` and `fuzzy_deanon_threshold=0.85` (default values applied to the existing single row).
    - Negative test (run via Supabase MCP `execute_sql` or psql): `UPDATE system_settings SET fuzzy_deanon_mode='bogus' WHERE id=1;` MUST raise SQLSTATE 23514 (check_violation). Roll back if it accidentally succeeds.
    - Negative test: `UPDATE system_settings SET fuzzy_deanon_threshold=0.49 WHERE id=1;` MUST raise SQLSTATE 23514. Roll back.
    - Negative test: `UPDATE system_settings SET fuzzy_deanon_threshold=1.01 WHERE id=1;` MUST raise SQLSTATE 23514. Roll back.
    - No regression: the existing `system_settings` row preserves all Phase 1+2+3 column values (spot-check `entity_resolution_mode`, `llm_provider`, `pii_missed_scan_enabled` are unchanged).
  </acceptance_criteria>
  <done>
Migration 031 is APPLIED on live Supabase qedhulpfezucnfadlfiz. The 2 new columns are queryable from the live DB. CHECK constraints reject bad values at the DB layer (defense-in-depth verified). Downstream Phase 4 plans can now run.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Env var → application memory | Deploy-time secret surface; no runtime user input. Pydantic Settings reads at app startup; validation is fail-fast at instance construction. |
| Migration SQL file → live DB | One-time admin DDL via Supabase MCP; service-role context; no end-user path. |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation |
|-----------|----------|-----------|----------|-------------|------------|
| T-04-01-1 | Tampering | `fuzzy_deanon_threshold` env var / DB column | low | mitigate | Pydantic `Field(ge=0.50, le=1.00)` at API layer + DB CHECK `>= 0.50 AND <= 1.00` at data layer (defense-in-depth per D-60). Out-of-range cannot enter via either surface — verified by Task 1 negative test (env-var) and Task 3 negative test (direct SQL UPDATE). |
| T-04-01-2 | Tampering | `fuzzy_deanon_mode` env var / DB column | low | mitigate | Pydantic `Literal['algorithmic','llm','none']` + DB CHECK with same enum. Invalid mode strings rejected at both layers — verified by Task 1 (`FUZZY_DEANON_MODE=bogus` startup) and Task 3 (`UPDATE … SET fuzzy_deanon_mode='bogus'`). |
| T-04-01-3 | Information Disclosure | Migration 031 SQL file in repo | low | accept | DDL only; no data; no secrets. `system_settings` already has service-role-only RLS from earlier migrations — no new policy surface. |

## Phase 4 cross-plan threats deferred to consumer plans
- **T-1 (Privacy regression):** Plan 04-03 (`de_anonymize_text` LLM mode invokes `LLMProviderClient.call(feature='fuzzy_deanon')`) and Plan 04-04 (missed-scan) are the trust-boundary callsites. Phase 3's pre-flight egress filter (D-53..D-56) is the runtime control; this plan only ships the config surface that gates entry into those callsites.
- **T-3 (Missed-scan injecting fabricated entity types):** Plan 04-04 enforces — this plan only ships the `fuzzy_deanon_*` columns, not `pii_missed_scan_enabled` (already shipped in Phase 3 D-57 migration 030).
</threat_model>

<verification>
- `pytest tests/` regression: 79/79 Phase 1+2+3 tests still pass post-config-edit (run from `backend/` after Task 1).
- `python -c "from app.main import app"` succeeds (PostToolUse hook full-import check; runs automatically after Task 1's edit to config.py).
- Live-DB column query returns 2 rows with the expected shape (Task 3 verify).
- Live-DB CHECK constraints reject 3 negative-test values (Task 3 acceptance).
</verification>

<success_criteria>
- D-67/D-69 config surface live in `app.config.Settings`: `fuzzy_deanon_mode` Literal field + `fuzzy_deanon_threshold` Field(ge,le) — verified at module import.
- Migration 031 file written to disk with the exact DDL.
- Migration 031 APPLIED to live Supabase qedhulpfezucnfadlfiz — verified by `information_schema.columns` query AND by negative-test CHECK violations.
- ZERO regression on Phase 1-3 tests (`pytest tests/` still 79/79).
</success_criteria>

<output>
After completion, create `.planning/phases/04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance/04-01-SUMMARY.md` mirroring Phase 3's `03-01-config-and-migration-030-SUMMARY.md` shape: list the 2 new Settings fields, the migration file path, the apply outcome (MCP path or CLI), the live-DB verification query results, and any deviations.
</output>
</content>
