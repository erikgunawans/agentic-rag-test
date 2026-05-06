-- Migration 043: Widen workspace_files.source CHECK constraint to include 'harness'
-- Phase 22 / UAT Gap 1 (BLOCKER) / 2026-05-06
-- Depends on: 039_workspace_files.sql (original CHECK), 042_harness_runs.sql (latest)
--
-- Background: Plan 22-11 widened frontend WorkspaceFile.source to include 'harness'
-- but the DB CHECK constraint was never updated. Live harness CR-01 phase fails with
-- 'new row for relation "workspace_files" violates check constraint
-- "workspace_files_source_check"' when contract_review_enabled=True.
--
-- Idempotent: uses DROP CONSTRAINT IF EXISTS so re-running this migration is safe
-- (matches the pattern documented in CLAUDE.md for RLS policies).

BEGIN;

ALTER TABLE public.workspace_files
  DROP CONSTRAINT IF EXISTS workspace_files_source_check;

ALTER TABLE public.workspace_files
  ADD CONSTRAINT workspace_files_source_check
  CHECK (source IN ('agent','sandbox','upload','harness'));

COMMIT;
