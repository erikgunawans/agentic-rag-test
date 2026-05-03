-- Migration 042: harness_runs table + messages.harness_mode column
-- Phase 20 / Plan 20-01 — foundation for HARN-01, MIG-03, SEC-01 (extension), D-01, D-04.
--
-- This migration mirrors 040_agent_runs.sql partial-unique-on-active-row + RLS pattern.
-- Status enum reserves 'paused' for Phase 21 llm_human_input; Phase 20 uses
-- pending → running → completed/failed/cancelled only.
--
-- Also adds messages.harness_mode TEXT NULL — used by gatekeeper (D-08) and
-- post-harness summary (D-09) to tag assistant messages produced by the harness flow.

-- ============================================================
-- 1. TABLE: public.harness_runs (D-01)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.harness_runs (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  thread_id       UUID NOT NULL REFERENCES public.threads(id) ON DELETE CASCADE,
  user_id         UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  harness_type    TEXT NOT NULL,
  status          TEXT NOT NULL CHECK (status IN ('pending','running','paused','completed','failed','cancelled')),
  current_phase   INTEGER NOT NULL DEFAULT 0,
  phase_results   JSONB NOT NULL DEFAULT '{}'::jsonb,
  input_file_ids  UUID[] NOT NULL DEFAULT '{}',
  error_detail    TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- 2. Partial unique index: at most one active run per thread (D-01)
-- ============================================================
CREATE UNIQUE INDEX IF NOT EXISTS idx_harness_runs_thread_active
  ON public.harness_runs(thread_id)
  WHERE status IN ('pending','running','paused');

-- ============================================================
-- 3. Auditing index
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_harness_runs_user_created
  ON public.harness_runs(user_id, created_at DESC);

-- ============================================================
-- 4. updated_at trigger (reuses handle_updated_at from migration 001 — DO NOT redefine)
-- ============================================================
DROP TRIGGER IF EXISTS handle_harness_runs_updated_at ON public.harness_runs;
CREATE TRIGGER handle_harness_runs_updated_at
  BEFORE UPDATE ON public.harness_runs
  FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

-- ============================================================
-- 5. ROW-LEVEL SECURITY — thread-ownership scope
-- ============================================================
ALTER TABLE public.harness_runs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "harness_runs_select" ON public.harness_runs;
CREATE POLICY "harness_runs_select" ON public.harness_runs
  FOR SELECT
  USING (
    thread_id IN (SELECT id FROM public.threads WHERE user_id = auth.uid())
    OR (auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin'
  );

DROP POLICY IF EXISTS "harness_runs_insert" ON public.harness_runs;
CREATE POLICY "harness_runs_insert" ON public.harness_runs
  FOR INSERT
  WITH CHECK (
    thread_id IN (SELECT id FROM public.threads WHERE user_id = auth.uid())
    OR (auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin'
  );

DROP POLICY IF EXISTS "harness_runs_update" ON public.harness_runs;
CREATE POLICY "harness_runs_update" ON public.harness_runs
  FOR UPDATE
  USING (
    thread_id IN (SELECT id FROM public.threads WHERE user_id = auth.uid())
    OR (auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin'
  )
  WITH CHECK (
    thread_id IN (SELECT id FROM public.threads WHERE user_id = auth.uid())
    OR (auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin'
  );

DROP POLICY IF EXISTS "harness_runs_delete" ON public.harness_runs;
CREATE POLICY "harness_runs_delete" ON public.harness_runs
  FOR DELETE
  USING (
    thread_id IN (SELECT id FROM public.threads WHERE user_id = auth.uid())
    OR (auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin'
  );

-- ============================================================
-- 6. ALTER TABLE: messages.harness_mode (D-04, D-08)
-- ============================================================
-- D-04 / D-08: tag assistant messages produced by harness flow.
-- NULL = normal/deep-mode message; non-NULL = harness flow (gatekeeper turns,
-- post-harness summary, harness-context follow-ups). Value matches the registered
-- harness key (e.g. 'contract-review', 'smoke-echo').
ALTER TABLE public.messages
  ADD COLUMN IF NOT EXISTS harness_mode TEXT NULL;

-- ============================================================
-- 7. Index for harness-mode message lookup (gatekeeper conversation reconstruction per D-08)
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_messages_harness_mode_thread
  ON public.messages(thread_id, created_at)
  WHERE harness_mode IS NOT NULL;
