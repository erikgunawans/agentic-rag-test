-- Migration 039: workspace_files table + workspace-files private storage bucket
-- Phase 18 / WS-01, WS-04, MIG-02
-- Depends on: 037_pii_domain_deny_list_extra.sql (and Phase 17's 038 if landed)
-- Sandbox-outputs bucket from migration 036 is reused for sandbox-generated binaries — NOT recreated here.

BEGIN;

-- ============================================================
-- 1. TABLE: public.workspace_files
-- ============================================================
CREATE TABLE IF NOT EXISTS public.workspace_files (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  thread_id       UUID NOT NULL REFERENCES public.threads(id) ON DELETE CASCADE,
  file_path       TEXT NOT NULL,
  content         TEXT,
  storage_path    TEXT,
  storage_bucket  TEXT,
  source          TEXT NOT NULL CHECK (source IN ('agent','sandbox','upload')),
  size_bytes      INTEGER NOT NULL DEFAULT 0,
  mime_type       TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

  -- D-02: file_path defence-in-depth checks
  CONSTRAINT workspace_files_path_length CHECK (char_length(file_path) <= 500 AND char_length(file_path) > 0),
  CONSTRAINT workspace_files_path_no_leading_slash CHECK (file_path NOT LIKE '/%'),
  CONSTRAINT workspace_files_path_no_backslash CHECK (file_path NOT LIKE '%\%'),
  CONSTRAINT workspace_files_path_no_traversal CHECK (file_path NOT LIKE '%..%'),

  -- D-02: exactly one of (content, storage_path) populated
  CONSTRAINT workspace_files_storage_xor CHECK (
    (content IS NOT NULL AND storage_path IS NULL)
    OR (content IS NULL AND storage_path IS NOT NULL)
  ),
  -- D-04: storage_bucket must be set when storage_path is set, must be one of two buckets
  CONSTRAINT workspace_files_bucket_check CHECK (
    storage_path IS NULL
    OR storage_bucket IN ('sandbox-outputs','workspace-files')
  ),
  CONSTRAINT workspace_files_bucket_set CHECK (
    (storage_path IS NULL AND storage_bucket IS NULL)
    OR (storage_path IS NOT NULL AND storage_bucket IS NOT NULL)
  ),

  -- WS-01: unique per-thread file path
  CONSTRAINT workspace_files_thread_path_unique UNIQUE (thread_id, file_path)
);

-- ============================================================
-- 2. INDEXES
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_workspace_files_thread_updated
  ON public.workspace_files(thread_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_workspace_files_thread_created
  ON public.workspace_files(thread_id, created_at DESC);

-- ============================================================
-- 3. updated_at TRIGGER
-- ============================================================
CREATE OR REPLACE FUNCTION public.workspace_files_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS workspace_files_updated_at ON public.workspace_files;
CREATE TRIGGER workspace_files_updated_at
  BEFORE UPDATE ON public.workspace_files
  FOR EACH ROW EXECUTE FUNCTION public.workspace_files_set_updated_at();

-- ============================================================
-- 4. ROW-LEVEL SECURITY — workspace_files (D-03)
-- ============================================================
ALTER TABLE public.workspace_files ENABLE ROW LEVEL SECURITY;

CREATE POLICY "workspace_files_select" ON public.workspace_files
  FOR SELECT
  USING (
    thread_id IN (SELECT id FROM public.threads WHERE user_id = auth.uid())
    OR (auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin'
  );

CREATE POLICY "workspace_files_insert" ON public.workspace_files
  FOR INSERT
  WITH CHECK (
    thread_id IN (SELECT id FROM public.threads WHERE user_id = auth.uid())
    OR (auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin'
  );

CREATE POLICY "workspace_files_update" ON public.workspace_files
  FOR UPDATE
  USING (
    thread_id IN (SELECT id FROM public.threads WHERE user_id = auth.uid())
    OR (auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin'
  )
  WITH CHECK (
    thread_id IN (SELECT id FROM public.threads WHERE user_id = auth.uid())
    OR (auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin'
  );

CREATE POLICY "workspace_files_delete" ON public.workspace_files
  FOR DELETE
  USING (
    thread_id IN (SELECT id FROM public.threads WHERE user_id = auth.uid())
    OR (auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin'
  );

-- ============================================================
-- 5. STORAGE BUCKET: workspace-files (D-04)
-- ============================================================
INSERT INTO storage.buckets (id, name, public)
VALUES ('workspace-files', 'workspace-files', false)
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- 6. STORAGE RLS — workspace-files
-- 4-segment path: {user_id}/{thread_id}/{workspace_file_id}/{filename}
-- Segment [1] = user_id gates access (mirrors sandbox-outputs).
-- ============================================================

CREATE POLICY "workspace-files SELECT"
  ON storage.objects FOR SELECT
  USING (
    bucket_id = 'workspace-files'
    AND (storage.foldername(objects.name))[1] = auth.uid()::text
  );

CREATE POLICY "workspace-files INSERT"
  ON storage.objects FOR INSERT
  WITH CHECK (
    bucket_id = 'workspace-files'
    AND (storage.foldername(objects.name))[1] = auth.uid()::text
  );

CREATE POLICY "workspace-files UPDATE"
  ON storage.objects FOR UPDATE
  USING (
    bucket_id = 'workspace-files'
    AND (storage.foldername(objects.name))[1] = auth.uid()::text
  )
  WITH CHECK (
    bucket_id = 'workspace-files'
    AND (storage.foldername(objects.name))[1] = auth.uid()::text
  );

CREATE POLICY "workspace-files DELETE"
  ON storage.objects FOR DELETE
  USING (
    bucket_id = 'workspace-files'
    AND (storage.foldername(objects.name))[1] = auth.uid()::text
  );

COMMIT;
