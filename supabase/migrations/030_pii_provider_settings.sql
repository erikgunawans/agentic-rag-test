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
