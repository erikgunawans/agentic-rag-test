-- 037_pii_domain_deny_list_extra.sql
-- REDACT-01 / D-P16-01: runtime-configurable extension to the PII
-- domain-term deny list. Comma-separated case-insensitive terms.
-- Empty default ('') means "use baked-in _DENY_LIST_CASEFOLD only" --
-- byte-identical to pre-Phase-16 behavior (D-P16-02 zero-regression).

ALTER TABLE public.system_settings
  ADD COLUMN IF NOT EXISTS pii_domain_deny_list_extra TEXT NOT NULL DEFAULT '';

COMMENT ON COLUMN public.system_settings.pii_domain_deny_list_extra IS
  'REDACT-01: runtime extras for the PII domain-term deny list. '
  'Comma-separated, case-insensitive. Unioned with the baked-in '
  '_DENY_LIST_CASEFOLD frozenset in detection.py. NEVER add cities '
  '(Jakarta, Surabaya, Bandung) -- they can appear in real personal '
  'addresses (D-09 reasoning).';
