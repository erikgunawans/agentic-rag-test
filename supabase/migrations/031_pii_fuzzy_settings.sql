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
