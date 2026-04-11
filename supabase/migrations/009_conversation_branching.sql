-- ============================================================
-- Module 10: Conversation Branching
-- Adds parent_message_id to messages for tree-based conversations.
-- Users can fork at any message to explore different directions.
-- ============================================================

-- 1. Add parent_message_id column (nullable self-FK)
ALTER TABLE public.messages
  ADD COLUMN parent_message_id uuid REFERENCES public.messages(id) ON DELETE SET NULL;

-- 2. Index for efficient tree traversal
CREATE INDEX idx_messages_parent_id ON public.messages(parent_message_id);

-- 3. Backfill existing linear conversations: link each message to its predecessor
WITH ordered AS (
  SELECT id, thread_id,
    LAG(id) OVER (PARTITION BY thread_id ORDER BY created_at) AS prev_id
  FROM public.messages
  WHERE parent_message_id IS NULL
)
UPDATE public.messages m
SET parent_message_id = o.prev_id
FROM ordered o
WHERE m.id = o.id AND o.prev_id IS NOT NULL;
