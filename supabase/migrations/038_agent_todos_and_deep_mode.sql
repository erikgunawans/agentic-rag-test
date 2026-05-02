-- Migration 038: agent_todos table + messages.deep_mode column
-- Phase 17 / Plan 17-01 — foundation for TODO-01 (planning todos), MIG-04 (deep_mode persistence), SEC-01 (RLS).
-- Bundles MIG-01 + MIG-04 per CONTEXT.md D-01.
-- Depends on: 037_pii_domain_deny_list_extra.sql

-- ============================================================
-- 1. TABLE: public.agent_todos (TODO-01)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.agent_todos (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  thread_id   UUID NOT NULL REFERENCES public.threads(id) ON DELETE CASCADE,
  user_id     UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  content     TEXT NOT NULL,
  status      TEXT NOT NULL CHECK (status IN ('pending','in_progress','completed')),
  position    INTEGER NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- 2. INDEXES
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_agent_todos_thread
  ON public.agent_todos(thread_id, position);
CREATE INDEX IF NOT EXISTS idx_agent_todos_user
  ON public.agent_todos(user_id, created_at DESC);

-- ============================================================
-- 3. updated_at trigger (reuses handle_updated_at from migration 001)
-- ============================================================
DROP TRIGGER IF EXISTS handle_agent_todos_updated_at ON public.agent_todos;
CREATE TRIGGER handle_agent_todos_updated_at
  BEFORE UPDATE ON public.agent_todos
  FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

-- ============================================================
-- 4. ROW-LEVEL SECURITY (SEC-01) — thread-ownership scope
-- ============================================================
ALTER TABLE public.agent_todos ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "agent_todos_select" ON public.agent_todos;
CREATE POLICY "agent_todos_select"
  ON public.agent_todos
  FOR SELECT
  USING (user_id = auth.uid());

DROP POLICY IF EXISTS "agent_todos_insert" ON public.agent_todos;
CREATE POLICY "agent_todos_insert"
  ON public.agent_todos
  FOR INSERT
  WITH CHECK (
    user_id = auth.uid()
    AND EXISTS (
      SELECT 1 FROM public.threads t
      WHERE t.id = agent_todos.thread_id
        AND t.user_id = auth.uid()
    )
  );

DROP POLICY IF EXISTS "agent_todos_update" ON public.agent_todos;
CREATE POLICY "agent_todos_update"
  ON public.agent_todos
  FOR UPDATE
  USING (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

DROP POLICY IF EXISTS "agent_todos_delete" ON public.agent_todos;
CREATE POLICY "agent_todos_delete"
  ON public.agent_todos
  FOR DELETE
  USING (user_id = auth.uid());

-- ============================================================
-- 5. ALTER TABLE: messages.deep_mode (MIG-04 / DEEP-04)
-- ============================================================
-- Default false applies to existing rows automatically.
ALTER TABLE public.messages
  ADD COLUMN IF NOT EXISTS deep_mode BOOLEAN NOT NULL DEFAULT false;
