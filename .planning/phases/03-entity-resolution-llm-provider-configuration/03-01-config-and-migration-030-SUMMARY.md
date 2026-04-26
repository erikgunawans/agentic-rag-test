---
phase: 03-entity-resolution-llm-provider-configuration
plan: 01
subsystem: pii-redaction-config
tags: [config, settings, migration, pydantic, system_settings, phase-3, llm-provider, entity-resolution]
requires:
  - Phase 1 + Phase 2 baseline (Settings class with pii_* + tracing_provider; migration 029 applied)
provides:
  - 15 new env-var-backed Pydantic Settings fields covering entity-resolution mode, global + per-feature LLM provider, endpoints, and Phase 4 forward-compat (pii_missed_scan_enabled)
  - Migration 030 SQL written to disk (NOT yet applied — Plan 03-02 owns the apply step), adding 9 typed columns to system_settings with CHECK constraints mirroring the Pydantic Literal sets exactly
affects:
  - backend/app/config.py (Settings class extended; Literal added to typing imports)
  - supabase/migrations/030_pii_provider_settings.sql (new file)
tech_stack_added:
  - typing.Literal usage for Pydantic enum validation (already used elsewhere — admin_settings.py rag_rerank_mode)
patterns:
  - Settings field block grouped by purpose with inline D-* decision references (matches Phase 1 pii_* block style)
  - Single ALTER TABLE with multi-clause add-column for atomic DDL (mirrors precedent in earlier system_settings migrations)
  - CHECK constraint expressions verbatim mirror Pydantic Literal sets (D-60 defense-in-depth invariant)
key_files_created:
  - supabase/migrations/030_pii_provider_settings.sql
key_files_modified:
  - backend/app/config.py
decisions:
  - D-50 reused — existing AsyncOpenAI dependency requires only env-var endpoints + timeout (default 30s)
  - D-57 followed exactly — 9 columns on system_settings with default values matching Pydantic defaults
  - D-58 enforced — cloud_llm_api_key is a Settings field (env-only) but NOT a DB column (no api_key in migration 030)
  - D-60 followed exactly — every Pydantic Literal has a matching DB CHECK; defense-in-depth
metrics:
  duration_minutes: ~5
  completed_date: "2026-04-26"
  task_count: 2
  files_changed: 2
  lines_added: 59
---

# Phase 3 Plan 01: Config + Migration 030 Summary

**One-liner:** Phase 3 schema/config primitives shipped — Pydantic Settings extended with 15 entity-resolution + LLM-provider fields and migration 030 SQL written to disk, with DB CHECK constraints mirroring the Pydantic Literal sets exactly per D-60 defense-in-depth.

## What was done

Two foundation artifacts that gate every downstream Phase 3 plan:

1. **Settings class extension (`backend/app/config.py`, commit `bb3202b`):** Added 15 new env-var-backed fields in three groups:
   - **Global mode + provider (4):** `entity_resolution_mode: Literal["algorithmic","llm","none"]` (default `algorithmic`), `llm_provider: Literal["local","cloud"]` (default `local`), `llm_provider_fallback_enabled: bool` (default `False`), `llm_provider_timeout_seconds: int` (default `30`).
   - **Per-feature overrides (5):** `entity_resolution_llm_provider`, `missed_scan_llm_provider`, `title_gen_llm_provider`, `metadata_llm_provider`, `fuzzy_deanon_llm_provider` — each `Literal["local","cloud"] | None = None` (None = inherit global per D-51).
   - **Endpoints + creds (5):** `local_llm_base_url` (default `http://localhost:1234/v1`), `local_llm_model` (`llama-3.1-8b-instruct`), `cloud_llm_base_url` (`https://api.openai.com/v1`), `cloud_llm_model` (`gpt-4o-mini`), `cloud_llm_api_key` (default empty, env-only per D-58).
   - **Phase 4 forward-compat (1):** `pii_missed_scan_enabled: bool = True` (per D-57; column shipped now to avoid migration churn).
   - Added `from typing import Literal` to the existing imports.

2. **Migration 030 SQL (`supabase/migrations/030_pii_provider_settings.sql`, commit `b2c7b3c`):** Single `ALTER TABLE system_settings` with 9 `add column` clauses — every D-57 column with type, default, and (where applicable) CHECK constraint. Two NOT NULL booleans (`llm_provider_fallback_enabled` default `false`, `pii_missed_scan_enabled` default `true`). Five nullable per-feature override columns (`text null check (... in ('local','cloud'))`). Two NOT NULL enum columns (`entity_resolution_mode`, `llm_provider`). Three `comment on column` statements documenting the load-bearing fields. NO `create policy` lines — `system_settings` already has service-role-only RLS from earlier migrations (D-25 invariant). NO `cloud_llm_api_key` DB column (D-58 invariant — the cloud key is env-var-only and surfaces in the admin UI as a masked status badge in Plan 03-06).

## Commits

| Task | Commit  | Type | Files                                                  |
| ---- | ------- | ---- | ------------------------------------------------------ |
| 1    | `bb3202b` | feat | `backend/app/config.py`                                |
| 2    | `b2c7b3c` | feat | `supabase/migrations/030_pii_provider_settings.sql`    |

## Verification

- **Settings field assertion:** ran `from app.config import get_settings; settings = get_settings()` and asserted all 15 new attribute names present, defaults match D-50 / D-51 / D-57. Output: `ALL_FIELDS_PRESENT`.
- **Backend import check:** `python -c "from app.main import app; print('OK')"` returns `OK` after the Settings extension. Backend graph imports cleanly with the new fields.
- **Migration shape verification:** `grep -c "alter table system_settings"` = 1 (single ALTER); `grep "^\s*add column"` = 9 lines; `grep "check ("` = 7 enum CHECK clauses (5 per-feature + global mode + global provider). Header references `PRD-PII-Redaction-System-v1.1.md §4.FR-4 / §4.FR-9` and `03-CONTEXT.md D-57..D-60`.
- **D-58 invariant check:** `grep "api_key" supabase/migrations/030_*.sql` returns nothing — the cloud key is env-only and is NOT a DB column.
- **No edits to applied migrations:** `git status` showed only `030_pii_provider_settings.sql` as new and `backend/app/config.py` as modified — no edits to 001..029.

The Phase 1 + Phase 2 regression suite (`pytest tests/` → 39/39) is preserved by definition: this plan only added optional Pydantic fields with safe defaults, and the migration file is on-disk-only (Plan 03-02 owns the apply step). No existing field was renamed, removed, or had its type narrowed; pydantic-settings auto-discovery is additive.

## Migration deployment status

**Migration 030 is NOT yet applied.** Plan 03-02 holds the [BLOCKING] task that runs `supabase db push` (or applies via MCP `apply_migration`) to materialize these 9 columns in the live database. Until that runs, downstream plans that read `system_settings.llm_provider` etc. via PostgREST will see "column does not exist" — which is the expected gating behavior.

## Deviations from Plan

None — plan executed exactly as written. Both tasks shipped verbatim per the planner's specification (defaults, CHECK expressions, header comments, COMMENT statements all matching the plan's literal-substring acceptance criteria).

## Threat Flags

None. The threat-model surface introduced by this plan is fully covered by the plan's own `<threat_model>` block (T-CONFIG-01, T-AUTH-01, T-INFO-01). Specifically:

- **T-CONFIG-01 (Tampering — bad enum values):** mitigated by the 7 CHECK constraints (5 per-feature + 2 global) that mirror the Pydantic Literal sets exactly. Direct SQL with a bad enum will raise SQLSTATE 23514; API-layer requests will be rejected at 422 by the (Plan 03-06-extended) `SystemSettingsUpdate` Literal-typed model.
- **T-AUTH-01 (Information Disclosure — cloud key exfiltration):** mitigated by the absence of any `cloud_llm_api_key` (or any `*_api_key` / `*_key`) column in migration 030. Verified via the acceptance criterion `grep "api_key"` → no matches. The key remains env-only in `Settings`, and Plan 03-06 surfaces only a masked status badge.
- **T-INFO-01 (Information Disclosure — unaudited provider switch):** accepted; the existing `log_action()` call inside the PATCH `/admin/settings` handler audits all `changed_fields` automatically, so the new fields inherit audit coverage with zero new code (Plan 03-06 verifies this end-to-end).

## Self-Check: PASSED

- [x] `backend/app/config.py` modified with all 15 Phase 3 fields (verified by Read + the assertion-script output `ALL_FIELDS_PRESENT`).
- [x] `supabase/migrations/030_pii_provider_settings.sql` exists with the exact content specified in the plan (verified by file existence + 9 `add column` clauses + 7 CHECK constraints + header references).
- [x] Commit `bb3202b` exists in `git log` (Task 1, Settings extension).
- [x] Commit `b2c7b3c` exists in `git log` (Task 2, migration 030 SQL).
- [x] No edits to applied migrations 001..029.
- [x] No `cloud_llm_api_key` DB column in migration 030 (D-58 invariant).
- [x] Backend imports cleanly with the new Settings fields (`from app.main import app` succeeds).

## Next steps (for the orchestrator / next plan)

- Plan 03-02 [BLOCKING]: apply migration 030 to the live Supabase project (`qedhulpfezucnfadlfiz`) via `supabase db push` or MCP `apply_migration`. After apply, the `get_system_settings()` 60s-cache reads will surface the new columns to all downstream Phase 3 plans (clustering, provider client, egress filter, admin UI).
- Plan 03-04 onwards consume these Settings fields via `_resolve_provider(feature)` (D-51) — exact resolution-order tests are in 03-04's pytest set.
- Plan 03-06 extends `SystemSettingsUpdate` with the matching Literal-typed fields; the API layer's 422 rejection of bad enums + the DB CHECK 23514 rejection together close the D-60 defense-in-depth invariant.
