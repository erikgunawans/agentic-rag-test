---
title: "ADR-0002: Single-Row System Settings Table"
status: "Accepted"
date: "2026-04-28"
authors: "Erik Gunawan Supriatna (LexCore Engineering)"
tags: ["architecture", "decision", "configuration", "database", "feature-flags"]
supersedes: ""
superseded_by: ""
---

# ADR-0002: Single-Row System Settings Table

## Status

**Accepted** — shipped with v0.1.0; the `system_settings` table currently has 30+ admin-toggleable columns including `pii_redaction_enabled`, fusion weights, rerank mode, and per-feature LLM provider overrides.

## Context

LexCore has a growing set of admin-toggleable feature flags and tuning knobs:

- PII redaction master toggle (`pii_redaction_enabled`)
- Hybrid retrieval fusion weights (`vector_weight`, `fulltext_weight`)
- Rerank mode (`rerank_mode`: `none` / `llm` / `cohere`)
- Per-feature LLM provider overrides (entity resolution, missed-scan, fuzzy de-anon, title-gen, metadata)
- Confidence thresholds, semantic-cache TTL, neighbor-expansion size, etc.

These settings are read on virtually every chat turn and document operation. The architectural choice was:

- **Key-value table** — `system_settings(key TEXT, value JSONB)` with one row per setting.
- **Single-row typed-column table** — `system_settings(id=1, ...)` with one column per setting.

Considerations:

- Type safety and Pydantic deserialization
- Read performance and caching simplicity
- Migration and discoverability
- Default values and validation
- Schema evolution (adding new flags)

## Decision

Use a **single-row table** with `id = 1` as the only valid primary key, and define one typed column per setting. Reads go through `system_settings_service.py::get_system_settings()` with a 60-second LRU cache. Writes go through `update_system_settings()` which clears the cache.

## Consequences

### Positive

- **POS-001**: Type safety end-to-end — Postgres column types map cleanly to Pydantic field types; no runtime JSON-schema parsing.
- **POS-002**: One-shot read — entire settings object fetched in a single SELECT, no JOIN, no N+1 risk.
- **POS-003**: Cache invalidation is trivial — `clear_cache()` after every write; no cache-stampede or partial-update anomaly.
- **POS-004**: Defaults live in the migration file — every column has a `DEFAULT` clause, so partial settings rows are impossible.
- **POS-005**: Discovery is trivial — `\d system_settings` lists every flag in the system.
- **POS-006**: Off-mode invariants are easy to enforce — the PII redaction byte-identical-bypass guarantee (SC#5 invariant in ADR-0004) reads `pii_redaction_enabled` exactly once per request.

### Negative

- **NEG-001**: Adding a new toggle requires a migration (`ALTER TABLE system_settings ADD COLUMN ...`), not a single INSERT. This is the explicit design trade-off.
- **NEG-002**: Cannot create runtime-defined feature flags from the admin UI — every flag must be code+migration first.
- **NEG-003**: A misuse pattern exists: developers occasionally try to query `system_settings` as a key-value table. Documented in `CLAUDE.md` gotchas.
- **NEG-004**: Wide rows — the table now has 30+ columns. No real performance impact at this scale, but it would become unwieldy at 100+ columns.

## Alternatives Considered

### Key-Value Table

- **ALT-001**: **Description**: `system_settings(key TEXT PRIMARY KEY, value JSONB, type TEXT)` with one row per setting.
- **ALT-002**: **Rejection Reason**: No type safety at the DB layer; every read needs JSON parsing + runtime type assertion. Cache-invalidation requires per-key tracking, not whole-object. Defaults are scattered. Discovery requires querying the data, not the schema.

### Environment Variables Only

- **ALT-003**: **Description**: All flags live in `.env` / Railway env vars, no DB.
- **ALT-004**: **Rejection Reason**: Admin UI cannot toggle flags at runtime. A redeploy is required for any change. Unacceptable for compliance toggles like `pii_redaction_enabled` that may need emergency rollback.

### Per-Domain Settings Tables

- **ALT-005**: **Description**: One settings table per domain (e.g., `redaction_settings`, `retrieval_settings`).
- **ALT-006**: **Rejection Reason**: Multiple SELECTs per request, multiple cache layers, no global "system status" view. Premature decomposition for the current scale.

## Implementation Notes

- **IMP-001**: Table seeded with `INSERT INTO system_settings (id) VALUES (1) ON CONFLICT DO NOTHING;` in the initial migration. The `id = 1` invariant is enforced by code, not schema (no CHECK constraint), but every read uses `.eq("id", 1).single()`.
- **IMP-002**: Reads go through `get_system_settings()` — never query the table directly from a service or router.
- **IMP-003**: The cache is `functools.lru_cache(maxsize=1)` with a manual TTL check; calling `clear_cache()` resets both.
- **IMP-004**: Writes use `get_supabase_client()` (service-role) since this is admin-only data.
- **IMP-005**: New flags follow the migration template: `ALTER TABLE system_settings ADD COLUMN <name> <type> NOT NULL DEFAULT <safe-default>;`. The default must preserve current behavior.
- **IMP-006**: Both mobile and desktop panels of `AdminSettingsPage.tsx` must be updated when adding a new toggle (CLAUDE.md gotcha).

## References

- **REF-001**: ADR-0004 — PII Surrogate Architecture (relies on `pii_redaction_enabled` flag).
- **REF-002**: `backend/app/services/system_settings_service.py` — implementation.
- **REF-003**: `CLAUDE.md` — "system_settings is a single-row table with columns, NOT a key-value store" (gotcha).
- **REF-004**: `Project_Architecture_Blueprint.md` Section 13 — original ADR-002 entry.
- **REF-005**: Migration `032_redaction_master_toggle.sql` — most recent example of adding a flag column.
