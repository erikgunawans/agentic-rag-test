-- Migration 032: PII Redaction System-Settings Column
--
-- Plan 05-08 gap-closure. Moves pii_redaction_enabled from config.py env var
-- (always True default, never admin-queryable) into system_settings as a
-- runtime-toggleable feature flag.
--
-- Default TRUE preserves production current behavior (PII redaction is ON in
-- production after the v0.3.0.0 ship; no operational change).
--
-- system_settings is a single-row table (id=1). RLS already gates writes via
-- the super_admin role check. No new RLS policy needed.

ALTER TABLE system_settings
  ADD COLUMN IF NOT EXISTS pii_redaction_enabled BOOLEAN NOT NULL DEFAULT TRUE;

-- Idempotent backfill — the singleton row already exists.
UPDATE system_settings SET pii_redaction_enabled = TRUE WHERE id = 1;

COMMENT ON COLUMN system_settings.pii_redaction_enabled IS
  'Master toggle for the v1.0 PII Redaction milestone. When TRUE, every chat turn '
  'runs the full Phase 5 redaction pipeline (anonymize → LLM with surrogates → de-anonymize). '
  'When FALSE, behavior is byte-identical to pre-v0.3 baseline (SC#5 invariant). '
  'Replaces the deprecated config.py PII_REDACTION_ENABLED env var (Plan 05-08).';
