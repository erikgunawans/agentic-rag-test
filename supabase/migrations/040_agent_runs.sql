-- Migration 040: agent_runs table + messages.parent_task_id column
-- Phase 19 / Plan 19-01 — foundation for TASK-04 (paused/resumable runs), ASK-04 (resume detection), STATUS-05 (DB-backed loop state).
-- Bundles agent_runs + messages.parent_task_id ALTER per CONTEXT.md D-03 / D-10.
-- Depends on: 039_workspace_files.sql

-- ============================================================
-- 1. TABLE: public.agent_runs (D-03)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.agent_runs (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  thread_id         UUID NOT NULL REFERENCES public.threads(id) ON DELETE CASCADE,
  user_id           UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  status            TEXT NOT NULL CHECK (status IN ('working','waiting_for_user','complete','error')),
  pending_question  TEXT,
  last_round_index  INTEGER NOT NULL DEFAULT 0,
  error_detail      TEXT,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT agent_runs_pending_question_invariant CHECK (
    (status = 'waiting_for_user') = (pending_question IS NOT NULL)
  )
);

-- ============================================================
-- 2. INDEXES
-- ============================================================
-- Partial unique index: at most one active run per thread (D-03 / T-19-RACE mitigation)
CREATE UNIQUE INDEX IF NOT EXISTS idx_agent_runs_thread_active
  ON public.agent_runs(thread_id)
  WHERE status IN ('working','waiting_for_user');

-- Covering index for admin audit queries (user × time descending)
CREATE INDEX IF NOT EXISTS idx_agent_runs_user_created
  ON public.agent_runs(user_id, created_at DESC);

-- ============================================================
-- 3. updated_at trigger (reuses handle_updated_at from migration 001 — DO NOT redefine)
-- ============================================================
DROP TRIGGER IF EXISTS handle_agent_runs_updated_at ON public.agent_runs;
CREATE TRIGGER handle_agent_runs_updated_at
  BEFORE UPDATE ON public.agent_runs
  FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

-- ============================================================
-- 4. ROW-LEVEL SECURITY (T-19-03 mitigation) — thread-ownership scope
--    Uses thread_id IN (SELECT id FROM threads WHERE user_id = auth.uid()) form
--    per D-03 (mirrors workspace_files 039 pattern, NOT agent_todos 038 pattern)
-- ============================================================
ALTER TABLE public.agent_runs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "agent_runs_select" ON public.agent_runs;
CREATE POLICY "agent_runs_select" ON public.agent_runs
  FOR SELECT
  USING (
    thread_id IN (SELECT id FROM public.threads WHERE user_id = auth.uid())
    OR (auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin'
  );

DROP POLICY IF EXISTS "agent_runs_insert" ON public.agent_runs;
CREATE POLICY "agent_runs_insert" ON public.agent_runs
  FOR INSERT
  WITH CHECK (
    thread_id IN (SELECT id FROM public.threads WHERE user_id = auth.uid())
    OR (auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin'
  );

DROP POLICY IF EXISTS "agent_runs_update" ON public.agent_runs;
CREATE POLICY "agent_runs_update" ON public.agent_runs
  FOR UPDATE
  USING (
    thread_id IN (SELECT id FROM public.threads WHERE user_id = auth.uid())
    OR (auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin'
  )
  WITH CHECK (
    thread_id IN (SELECT id FROM public.threads WHERE user_id = auth.uid())
    OR (auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin'
  );

DROP POLICY IF EXISTS "agent_runs_delete" ON public.agent_runs;
CREATE POLICY "agent_runs_delete" ON public.agent_runs
  FOR DELETE
  USING (
    thread_id IN (SELECT id FROM public.threads WHERE user_id = auth.uid())
    OR (auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin'
  );

-- ============================================================
-- 5. ALTER TABLE: messages.parent_task_id (D-10)
--    Nullable UUID — links sub-agent messages to the parent task tool call.
--    Enables message-tree reconstruction on thread reload.
-- ============================================================
ALTER TABLE public.messages
  ADD COLUMN IF NOT EXISTS parent_task_id UUID NULL;

CREATE INDEX IF NOT EXISTS idx_messages_parent_task
  ON public.messages(parent_task_id) WHERE parent_task_id IS NOT NULL;
