-- Migration 036: code_executions table + sandbox-outputs storage bucket
-- Phase 10 / Plan 10-01 — foundation for SANDBOX-04 (file storage), SANDBOX-06 (execution logging)
-- Depends on: 035_skill_files_table_and_bucket.sql
-- All table DDL uses CREATE IF NOT EXISTS; bucket INSERT uses ON CONFLICT DO NOTHING.
-- Storage RLS uses 4-segment path: {user_id}/{thread_id}/{execution_id}/{filename} (D-P10-13).

-- ============================================================
-- 1. TABLE: public.code_executions
-- ============================================================
-- Immutable audit log of code execution events (D-P10-15).
-- NO UPDATE or DELETE policies — records are write-once.
-- Path scheme for files column: {user_id}/{thread_id}/{execution_id}/{filename}

CREATE TABLE IF NOT EXISTS public.code_executions (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  thread_id     UUID NOT NULL REFERENCES public.threads(id) ON DELETE CASCADE,
  code          TEXT NOT NULL,
  description   TEXT,
  stdout        TEXT NOT NULL DEFAULT '',
  stderr        TEXT NOT NULL DEFAULT '',
  exit_code     INTEGER NOT NULL DEFAULT 0,
  execution_ms  INTEGER NOT NULL DEFAULT 0,
  status        TEXT NOT NULL CHECK (status IN ('success','error','timeout')),
  files         JSONB NOT NULL DEFAULT '[]'::jsonb,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- 2. INDEXES
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_code_executions_thread
  ON public.code_executions(thread_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_code_executions_user
  ON public.code_executions(user_id, created_at DESC);

-- ============================================================
-- 3. ROW-LEVEL SECURITY — code_executions table
-- ============================================================
-- D-P10-15: SELECT for own rows + super_admin; INSERT for own rows.
-- No UPDATE / DELETE — execution log is immutable audit record.

ALTER TABLE public.code_executions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "code_executions_select"
  ON public.code_executions
  FOR SELECT
  USING (
    user_id = auth.uid()
    OR (auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin'
  );

CREATE POLICY "code_executions_insert"
  ON public.code_executions
  FOR INSERT
  WITH CHECK (user_id = auth.uid());

-- No UPDATE / DELETE policies — execution log is immutable audit record (D-P10-15).

-- ============================================================
-- 4. STORAGE BUCKET: sandbox-outputs (D-P10-13)
-- ============================================================
-- Private bucket (public = false). Objects accessed via signed URLs (1-hour TTL, D-P10-14).

INSERT INTO storage.buckets (id, name, public)
VALUES ('sandbox-outputs', 'sandbox-outputs', false)
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- 5. STORAGE RLS — sandbox-outputs (4-segment path: user_id/thread_id/execution_id/filename)
-- ============================================================
-- D-P10-13: path = {user_id}/{thread_id}/{execution_id}/{filename}.
-- Only segment [1] (user_id) is gated. Unlike skills (3-segment with FK on segment [2]),
-- we have no parent-row constraint per-execution; the bucket is private so SELECT is
-- gated solely by ownership of the top-level folder.
-- BUG FIX FROM 035: Use objects.name (not bare `name`) inside any subquery to avoid
-- PostgreSQL resolving `name` against an outer table.

CREATE POLICY "sandbox-outputs SELECT"
  ON storage.objects
  FOR SELECT
  USING (
    bucket_id = 'sandbox-outputs'
    AND (storage.foldername(objects.name))[1] = auth.uid()::text
  );

-- INSERT: backend uploads via service-role (bypasses RLS) per CONTEXT.md line 102.
-- The policy still gates direct user uploads — caller UID must match segment [1].
CREATE POLICY "sandbox-outputs INSERT"
  ON storage.objects
  FOR INSERT
  WITH CHECK (
    bucket_id = 'sandbox-outputs'
    AND (storage.foldername(objects.name))[1] = auth.uid()::text
  );

-- No DELETE policy — generated files retention-managed at bucket level (future).
-- No UPDATE policy — files are immutable.
