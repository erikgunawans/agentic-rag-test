---
phase: 03-entity-resolution-llm-provider-configuration
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/app/config.py
  - supabase/migrations/030_pii_provider_settings.sql
autonomous: true
requirements_addressed: [RESOLVE-01, PROVIDER-01, PROVIDER-02, PROVIDER-03, PROVIDER-05, PROVIDER-06, PROVIDER-07]
must_haves:
  truths:
    - "Settings class exposes entity_resolution_mode, llm_provider, llm_provider_fallback_enabled, llm_provider_timeout_seconds, 5 per-feature override fields, 5 endpoint/cred fields, pii_missed_scan_enabled — all env-var-backed"
    - "Migration file 030_pii_provider_settings.sql exists and is well-formed SQL"
    - "Migration ALTER TABLE adds exactly 9 columns to system_settings with CHECK constraints mirroring the Pydantic Literal sets (D-57 / D-60)"
    - "No edits to applied migrations 001-029 (CLAUDE.md gotcha)"
  artifacts:
    - path: "backend/app/config.py"
      provides: "Phase 3 env-var-backed Settings fields"
      contains: "entity_resolution_mode"
    - path: "supabase/migrations/030_pii_provider_settings.sql"
      provides: "ALTER TABLE system_settings DDL — 9 new columns with CHECK constraints"
      contains: "alter table system_settings"
  key_links:
    - from: "backend/app/config.py"
      to: "system_settings columns"
      via: "Pydantic Literal type matches DB CHECK enum exactly"
      pattern: "Literal\\[['\"]algorithmic['\"], ['\"]llm['\"], ['\"]none['\"]\\]"
    - from: "supabase/migrations/030_pii_provider_settings.sql"
      to: "existing system_settings table"
      via: "alter table add column × 9"
      pattern: "alter table system_settings"
---

<objective>
Ship the two parallel-independent foundation artifacts: the env-var-backed `Settings` field block on `app/config.py` and the SQL migration `030_pii_provider_settings.sql` that ALTER TABLE's `system_settings` with the matching 9 columns.

Purpose: These are the schema + config primitives every downstream Phase 3 plan reads from. They have no dependencies on each other; they CAN be written in parallel within this single plan. Plan 02-03's [BLOCKING] migration apply task gates everything that consumes the new DB columns.

Output: Two files. `backend/app/config.py` extended with ~12 new fields (D-50 / D-51 / D-57). `supabase/migrations/030_pii_provider_settings.sql` written to disk (NOT pushed yet — Plan 03-02 does that).
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
@.planning/phases/03-entity-resolution-llm-provider-configuration/03-PATTERNS.md
@CLAUDE.md
@backend/app/config.py
@supabase/migrations/029_pii_entity_registry.sql
@backend/app/routers/admin_settings.py

<interfaces>
<!-- Existing primitives this plan extends. Read once; no codebase exploration needed. -->

From backend/app/config.py (Phase 1 baseline — Pydantic BaseSettings field block):
```python
class Settings(BaseSettings):
    pii_redaction_enabled: bool = False
    pii_surrogate_locale: str = "id_ID"
    pii_surrogate_score_threshold: float = 0.7
    pii_redact_score_threshold: float = 0.3
    tracing_provider: str = ""
```
The Settings class uses bare type annotations + default values; pydantic-settings auto-reads env vars (uppercased field names).

From backend/app/routers/admin_settings.py L29 (existing Literal pattern Phase 3 mirrors):
```python
rag_rerank_mode: Literal["none", "llm", "cohere"] | None = None
```

From supabase/migrations/029_pii_entity_registry.sql (Phase 2 — header comment style):
```sql
-- 029: PII Entity Registry — conversation-scoped real↔surrogate map (Phase 2)
-- System-level table; service-role only. End users never query this directly.
-- See PRD-PII-Redaction-System-v1.1.md §4.FR-3 and 02-CONTEXT.md D-21..D-26.
```

The system_settings table is single-row (`id=1`) with typed columns (NOT key-value). Per CLAUDE.md gotcha. Existing CHECK-constraint precedent: `rag_rerank_mode in ('none','llm','cohere')` (mirror this exactly for D-60).
</interfaces>
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: Extend Settings class in backend/app/config.py with Phase 3 fields</name>
  <files>backend/app/config.py</files>
  <read_first>
    - backend/app/config.py (current Phase 1 baseline — see exactly where pii_* fields and tracing_provider live; the new block is appended in the same Settings class)
    - .planning/phases/03-entity-resolution-llm-provider-configuration/03-CONTEXT.md decisions D-50, D-51, D-57, D-58
    - .planning/phases/03-entity-resolution-llm-provider-configuration/03-PATTERNS.md §"backend/app/config.py" (full target field block)
  </read_first>
  <action>
Open `backend/app/config.py`. Locate the Phase 1 `pii_*` field block in the `Settings(BaseSettings)` class. APPEND the following block immediately after the existing `tracing_provider` field (or at the end of the Settings class, whichever is closer to the existing pii_* group — the file owner is the planner's discretion, but order MUST be: existing fields, then this new block, in one contiguous addition).

Ensure `Literal` is imported at the top of the file:
```python
from typing import Literal
```
If `Literal` is not already imported, add it to the existing `from typing import ...` line. Do NOT introduce a new import line if one already exists.

Add these EXACT 13 fields verbatim (D-50 / D-51 / D-57; defaults match PRD §6 / D-50):
```python
    # Phase 3: Entity resolution mode + global LLM provider (D-57, D-60)
    entity_resolution_mode: Literal["algorithmic", "llm", "none"] = "algorithmic"
    llm_provider: Literal["local", "cloud"] = "local"
    llm_provider_fallback_enabled: bool = False
    llm_provider_timeout_seconds: int = 30  # D-50

    # Phase 3: Per-feature provider overrides (None = inherit global) (D-51 / PROVIDER-07)
    entity_resolution_llm_provider: Literal["local", "cloud"] | None = None
    missed_scan_llm_provider: Literal["local", "cloud"] | None = None
    title_gen_llm_provider: Literal["local", "cloud"] | None = None
    metadata_llm_provider: Literal["local", "cloud"] | None = None
    fuzzy_deanon_llm_provider: Literal["local", "cloud"] | None = None

    # Phase 3: Endpoints + creds (D-50, D-58)
    local_llm_base_url: str = "http://localhost:1234/v1"
    local_llm_model: str = "llama-3.1-8b-instruct"
    cloud_llm_base_url: str = "https://api.openai.com/v1"
    cloud_llm_model: str = "gpt-4o-mini"
    cloud_llm_api_key: str = ""  # D-58: env-only; admin UI shows masked status badge

    # Phase 4 forward-compat (ship column + setting now per D-57; consumed in Phase 4)
    pii_missed_scan_enabled: bool = True
```

Field-naming matches D-57 column names exactly (case-sensitive — pydantic-settings will auto-discover env vars `ENTITY_RESOLUTION_MODE`, `LLM_PROVIDER`, `LLM_PROVIDER_FALLBACK_ENABLED`, `ENTITY_RESOLUTION_LLM_PROVIDER`, `CLOUD_LLM_API_KEY`, etc.).

Defaults rationale (do NOT change without explicit decision):
- `entity_resolution_mode = "algorithmic"` — PRD §6 default; safest mode (no LLM dep).
- `llm_provider = "local"` — PRD §6 default; no third-party egress out of the box.
- `llm_provider_fallback_enabled = False` — D-52 default-off; failover knob plumbed for Phase 6.
- `llm_provider_timeout_seconds = 30` — D-50 default; OpenAI SDK passes this as `timeout` arg.
- `local_llm_base_url = "http://localhost:1234/v1"` — LM Studio default port; LM Studio + Ollama both expose `/v1/chat/completions`.
- `local_llm_model = "llama-3.1-8b-instruct"` — sensible LM-Studio-shipped default; deployer overrides via env.
- `cloud_llm_base_url = "https://api.openai.com/v1"` — OpenAI direct.
- `cloud_llm_api_key = ""` — empty string default; D-58 expects the key from Railway environment, never DB.

Do NOT add any computed properties / validators here — Phase 3 D-51's `_resolve_provider` helper lives in `llm_provider.py` (Plan 03-04), not in config.

Run the project's import-check after writing (the PostToolUse hook does this automatically on .py edits, but eyeball the result):
```bash
cd backend && source venv/bin/activate && python -c "from app.config import settings; assert hasattr(settings, 'llm_provider'); assert hasattr(settings, 'entity_resolution_mode'); assert hasattr(settings, 'cloud_llm_api_key'); assert settings.entity_resolution_mode == 'algorithmic'; assert settings.llm_provider == 'local'; print('OK')"
```
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && python -c "from app.config import settings; assert hasattr(settings, 'llm_provider'); assert hasattr(settings, 'entity_resolution_mode'); assert hasattr(settings, 'llm_provider_fallback_enabled'); assert hasattr(settings, 'llm_provider_timeout_seconds'); assert hasattr(settings, 'entity_resolution_llm_provider'); assert hasattr(settings, 'missed_scan_llm_provider'); assert hasattr(settings, 'title_gen_llm_provider'); assert hasattr(settings, 'metadata_llm_provider'); assert hasattr(settings, 'fuzzy_deanon_llm_provider'); assert hasattr(settings, 'local_llm_base_url'); assert hasattr(settings, 'local_llm_model'); assert hasattr(settings, 'cloud_llm_base_url'); assert hasattr(settings, 'cloud_llm_model'); assert hasattr(settings, 'cloud_llm_api_key'); assert hasattr(settings, 'pii_missed_scan_enabled'); assert settings.entity_resolution_mode == 'algorithmic'; assert settings.llm_provider == 'local'; assert settings.llm_provider_fallback_enabled is False; assert settings.llm_provider_timeout_seconds == 30; print('ALL_FIELDS_PRESENT')" 2>&1 | grep -q "ALL_FIELDS_PRESENT"</automated>
  </verify>
  <acceptance_criteria>
    - `backend/app/config.py` contains the literal substring `entity_resolution_mode: Literal["algorithmic", "llm", "none"] = "algorithmic"`.
    - File contains `llm_provider: Literal["local", "cloud"] = "local"`.
    - File contains `llm_provider_fallback_enabled: bool = False`.
    - File contains `llm_provider_timeout_seconds: int = 30`.
    - File contains all 5 per-feature override fields with type `Literal["local", "cloud"] | None = None`: `entity_resolution_llm_provider`, `missed_scan_llm_provider`, `title_gen_llm_provider`, `metadata_llm_provider`, `fuzzy_deanon_llm_provider`.
    - File contains 5 endpoint/cred fields: `local_llm_base_url`, `local_llm_model`, `cloud_llm_base_url`, `cloud_llm_model`, `cloud_llm_api_key`.
    - File contains `pii_missed_scan_enabled: bool = True` (Phase 4 forward-compat).
    - `from typing import Literal` is present in the file.
    - The import-check command above prints `ALL_FIELDS_PRESENT` (exit 0).
  </acceptance_criteria>
  <done>Settings class extended; all 14 new fields present; defaults match D-50/D-51/D-57; backend imports cleanly.</done>
</task>

<task type="auto" tdd="false">
  <name>Task 2: Write supabase/migrations/030_pii_provider_settings.sql</name>
  <files>supabase/migrations/030_pii_provider_settings.sql</files>
  <read_first>
    - supabase/migrations/029_pii_entity_registry.sql (immediate predecessor — header comment style + lowercase SQL convention)
    - .planning/phases/03-entity-resolution-llm-provider-configuration/03-CONTEXT.md D-57, D-60
    - .planning/phases/03-entity-resolution-llm-provider-configuration/03-PATTERNS.md §"supabase/migrations/030_pii_provider_settings.sql"
    - CLAUDE.md "Migrations are numbered sequentially (`001_` through `029_` applied)" gotcha — this is the next sequential migration; never edit applied migrations
  </read_first>
  <action>
Create the file `supabase/migrations/030_pii_provider_settings.sql` directly via the Write tool. Do NOT use `/create-migration` skill — the file number is locked by the next-sequential rule (029 was the last applied per Phase 2 STATE.md L29). Use lowercase SQL keywords (matches project convention — see migrations 001, 011, 029).

Write the file with this exact content:

```sql
-- 030: PII Provider Settings — entity-resolution mode + LLM provider columns (Phase 3)
-- Extends the single-row system_settings table with 9 new columns per D-57.
-- DB CHECK constraints mirror the Pydantic Literal sets in app.config.Settings
-- and the SystemSettingsUpdate model (defense in depth — D-60 / FR-9 / NFR-2).
-- See PRD-PII-Redaction-System-v1.1.md §4.FR-4, §4.FR-9 and 03-CONTEXT.md D-57..D-60.

alter table system_settings
  add column entity_resolution_mode text not null default 'algorithmic'
    check (entity_resolution_mode in ('algorithmic','llm','none')),
  add column llm_provider text not null default 'local'
    check (llm_provider in ('local','cloud')),
  add column llm_provider_fallback_enabled boolean not null default false,
  add column entity_resolution_llm_provider text null
    check (entity_resolution_llm_provider in ('local','cloud')),
  add column missed_scan_llm_provider text null
    check (missed_scan_llm_provider in ('local','cloud')),
  add column title_gen_llm_provider text null
    check (title_gen_llm_provider in ('local','cloud')),
  add column metadata_llm_provider text null
    check (metadata_llm_provider in ('local','cloud')),
  add column fuzzy_deanon_llm_provider text null
    check (fuzzy_deanon_llm_provider in ('local','cloud')),
  add column pii_missed_scan_enabled boolean not null default true;

-- system_settings already has RLS + service-role-only policy from earlier
-- migrations; no policy changes needed here. Per Phase 2 D-25 invariant the
-- registry/system_settings tables are service-role-only — no end-user PostgREST
-- access path. The PATCH route at /admin/settings is gated by require_admin.

comment on column system_settings.entity_resolution_mode is
  'PII entity resolution mode: algorithmic (Union-Find) | llm (provider-aware) | none (passthrough). PRD §4.FR-4.1.';
comment on column system_settings.llm_provider is
  'Global LLM provider for auxiliary calls (entity resolution, missed-scan, fuzzy de-anon, title gen, metadata). PRD §4.FR-9.1.';
comment on column system_settings.llm_provider_fallback_enabled is
  'D-52: cross-provider failover toggle. Plumbed in Phase 3, behavior shipped in Phase 6 (PERF-04).';
```

Hard requirements that the executor MUST verify after writing:
- File path is EXACTLY `supabase/migrations/030_pii_provider_settings.sql`.
- Contains exactly one `alter table system_settings` statement (multi-clause; ALL 9 add-column clauses inside ONE alter table per Postgres atomic-DDL hygiene).
- All 9 column names match D-57 / D-60 / Plan-01-Task-1 exactly: `entity_resolution_mode`, `llm_provider`, `llm_provider_fallback_enabled`, `entity_resolution_llm_provider`, `missed_scan_llm_provider`, `title_gen_llm_provider`, `metadata_llm_provider`, `fuzzy_deanon_llm_provider`, `pii_missed_scan_enabled`.
- 5 CHECK constraints on text-enum columns; check expressions exactly mirror the Pydantic Literal sets:
  - `entity_resolution_mode in ('algorithmic','llm','none')`
  - `llm_provider in ('local','cloud')`
  - `entity_resolution_llm_provider in ('local','cloud')` (and 4 more per-feature override fields, same expression)
- Two NOT-NULL boolean columns with explicit defaults: `llm_provider_fallback_enabled boolean not null default false`, `pii_missed_scan_enabled boolean not null default true`.
- 5 nullable per-feature override columns: `text null check (...)` (no NOT NULL — None means "inherit global").
- NO `create policy` lines — system_settings RLS already exists from earlier migrations (D-25 invariant carries).
- Header comment block references PRD §4.FR-4 / §4.FR-9 + 03-CONTEXT.md D-57..D-60.

CLAUDE.md gotcha: Once this file is committed, the PreToolUse hook locks 001-029. NEVER edit applied migrations. The 030 file should be apply-clean before Plan 03-02 runs.
  </action>
  <verify>
    <automated>test -f supabase/migrations/030_pii_provider_settings.sql && grep -c "alter table system_settings" supabase/migrations/030_pii_provider_settings.sql | grep -q "^1$" && grep -q "add column entity_resolution_mode text not null default 'algorithmic'" supabase/migrations/030_pii_provider_settings.sql && grep -q "check (entity_resolution_mode in ('algorithmic','llm','none'))" supabase/migrations/030_pii_provider_settings.sql && grep -q "add column llm_provider text not null default 'local'" supabase/migrations/030_pii_provider_settings.sql && grep -q "check (llm_provider in ('local','cloud'))" supabase/migrations/030_pii_provider_settings.sql && grep -q "add column llm_provider_fallback_enabled boolean not null default false" supabase/migrations/030_pii_provider_settings.sql && grep -q "add column entity_resolution_llm_provider text null" supabase/migrations/030_pii_provider_settings.sql && grep -q "add column missed_scan_llm_provider text null" supabase/migrations/030_pii_provider_settings.sql && grep -q "add column title_gen_llm_provider text null" supabase/migrations/030_pii_provider_settings.sql && grep -q "add column metadata_llm_provider text null" supabase/migrations/030_pii_provider_settings.sql && grep -q "add column fuzzy_deanon_llm_provider text null" supabase/migrations/030_pii_provider_settings.sql && grep -q "add column pii_missed_scan_enabled boolean not null default true" supabase/migrations/030_pii_provider_settings.sql && ! grep -q "create policy" supabase/migrations/030_pii_provider_settings.sql && echo "MIGRATION_FILE_VALID"</automated>
  </verify>
  <acceptance_criteria>
    - File `supabase/migrations/030_pii_provider_settings.sql` exists.
    - Contains exactly one `alter table system_settings` statement.
    - Contains 9 `add column` clauses (one for each D-57 column).
    - Contains literal `check (entity_resolution_mode in ('algorithmic','llm','none'))`.
    - Contains literal `check (llm_provider in ('local','cloud'))`.
    - Contains 5 per-feature CHECK constraints on `entity_resolution_llm_provider`, `missed_scan_llm_provider`, `title_gen_llm_provider`, `metadata_llm_provider`, `fuzzy_deanon_llm_provider` — each `check (... in ('local','cloud'))`.
    - Contains literal `add column llm_provider_fallback_enabled boolean not null default false`.
    - Contains literal `add column pii_missed_scan_enabled boolean not null default true`.
    - Contains ZERO `create policy` lines (system_settings RLS already exists — D-25 invariant).
    - Header comment references `PRD-PII-Redaction-System-v1.1.md §4.FR-4` and `03-CONTEXT.md D-57..D-60`.
  </acceptance_criteria>
  <done>Migration 030 SQL written to disk; well-formed SQL; ready for Plan 03-02 [BLOCKING] apply.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| env → backend | `CLOUD_LLM_API_KEY` and provider config arrive via OS env at process start; never echoed in logs |
| admin client → PATCH /admin/settings | Future plan (03-06) gates this; this plan only DEFINES the columns |
| local DDL file → live DB | Plan 03-02 crosses this boundary; this plan only writes the file |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-CONFIG-01 | Tampering | system_settings row inserted via direct SQL with bad enum value | mitigate | DB CHECK constraints on each enum-typed column (`entity_resolution_mode`, `llm_provider`, 5 per-feature) — 23514 at DB layer (defense-in-depth with Pydantic Literal at API edge per D-60) |
| T-AUTH-01 | Information Disclosure | `CLOUD_LLM_API_KEY` exfiltration via DB column or admin UI round-trip | mitigate | D-58 — env-var only; NO DB column for the cloud key in this migration (verified by acceptance criterion: only 9 columns, none named `*_api_key` or `*_key`); admin UI surfaces masked badge only (Plan 03-06) |
| T-INFO-01 | Information Disclosure | Provider switch unaudited (compliance / forensic gap) | accept | Existing `log_action()` from PATCH /admin/settings audits all changed_fields automatically (Plan 03-06 inherits); D-59 invariant carries; no new audit code needed |
</threat_model>

<verification>
After this plan completes:
- `git status` shows `backend/app/config.py` modified and `supabase/migrations/030_pii_provider_settings.sql` new.
- Backend imports cleanly: `cd backend && source venv/bin/activate && python -c "from app.main import app; print('OK')"` (PostToolUse hook runs this automatically).
- Phase 1 + Phase 2 regression: `cd backend && source venv/bin/activate && pytest tests/ -x` returns 39/39 pass (no fields removed from prior phases).
- Plan 03-02 [BLOCKING] (apply migration) is now unblocked.
</verification>

<success_criteria>
- All 14 Phase 3 Settings fields present in `app/config.py` with correct types and defaults.
- All 9 `system_settings` columns defined in migration 030 with correct types, defaults, and CHECK constraints.
- Pydantic Literal sets and DB CHECK enums match exactly (D-60 defense-in-depth invariant).
- No edits to applied migrations 001-029 (CLAUDE.md gotcha).
- No `cloud_llm_api_key` DB column (D-58 invariant).
- Backend imports cleanly; existing tests still pass.
</success_criteria>

<output>
Create `.planning/phases/03-entity-resolution-llm-provider-configuration/03-01-SUMMARY.md` with:
- Settings fields added (count + names)
- Migration file path written
- All 9 columns confirmed present with CHECK constraints
- Note: migration NOT yet pushed — Plan 03-02 handles that.
- Phase 1+2 regression: 39/39 still pass.
</output>
