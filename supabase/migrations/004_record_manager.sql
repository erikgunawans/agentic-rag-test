-- ============================================================
-- Module 3: Record Manager
-- Add content_hash for deduplication
-- ============================================================

ALTER TABLE public.documents ADD COLUMN content_hash text;

-- Partial index for fast dedup lookups (skips legacy NULL rows)
CREATE INDEX idx_documents_user_hash
  ON public.documents (user_id, content_hash)
  WHERE content_hash IS NOT NULL;
