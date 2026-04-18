-- ============================================================
-- 024: Knowledge Base Explorer — Folders + Exploration RPCs
-- ============================================================

-- 1. document_folders table
CREATE TABLE public.document_folders (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id          UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  name             TEXT NOT NULL,
  parent_folder_id UUID REFERENCES public.document_folders(id) ON DELETE CASCADE,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- No duplicate folder names in same parent for same user
CREATE UNIQUE INDEX idx_folders_unique_name
  ON public.document_folders (
    user_id,
    COALESCE(parent_folder_id, '00000000-0000-0000-0000-000000000000'::uuid),
    name
  );

-- Reuse handle_updated_at trigger from migration 001
CREATE TRIGGER handle_document_folders_updated_at
  BEFORE UPDATE ON public.document_folders
  FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

-- 2. Add folder_id to documents (null = root level)
ALTER TABLE public.documents
  ADD COLUMN folder_id UUID REFERENCES public.document_folders(id) ON DELETE SET NULL;

CREATE INDEX idx_documents_folder_id ON public.documents (user_id, folder_id);

-- 3. RLS for document_folders
ALTER TABLE public.document_folders ENABLE ROW LEVEL SECURITY;

CREATE POLICY "users_select_own_folders"
  ON public.document_folders FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "users_insert_own_folders"
  ON public.document_folders FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "users_update_own_folders"
  ON public.document_folders FOR UPDATE
  USING (auth.uid() = user_id);

CREATE POLICY "users_delete_own_folders"
  ON public.document_folders FOR DELETE
  USING (auth.uid() = user_id);

-- 4. RPC: Recursive folder tree with document counts
CREATE OR REPLACE FUNCTION get_folder_tree(p_user_id UUID, p_max_depth INT DEFAULT 10)
RETURNS TABLE (
  id UUID,
  name TEXT,
  parent_folder_id UUID,
  depth INT,
  path TEXT,
  document_count BIGINT
)
LANGUAGE SQL STABLE
SECURITY DEFINER
AS $$
  WITH RECURSIVE tree AS (
    SELECT
      f.id, f.name, f.parent_folder_id,
      0 AS depth,
      '/' || f.name AS path
    FROM public.document_folders f
    WHERE f.user_id = p_user_id AND f.parent_folder_id IS NULL

    UNION ALL

    SELECT
      f.id, f.name, f.parent_folder_id,
      t.depth + 1,
      t.path || '/' || f.name
    FROM public.document_folders f
    JOIN tree t ON f.parent_folder_id = t.id
    WHERE t.depth < p_max_depth
  )
  SELECT
    tree.id, tree.name, tree.parent_folder_id, tree.depth, tree.path,
    (SELECT COUNT(*) FROM public.documents d
     WHERE d.folder_id = tree.id AND d.user_id = p_user_id) AS document_count
  FROM tree
  ORDER BY tree.path;
$$;

-- 5. RPC: POSIX regex search across document chunks
CREATE OR REPLACE FUNCTION search_chunks_by_pattern(
  p_user_id         UUID,
  p_pattern         TEXT,
  p_case_insensitive BOOLEAN DEFAULT true,
  p_max_results     INT DEFAULT 20
)
RETURNS TABLE (
  chunk_id     UUID,
  document_id  UUID,
  doc_filename TEXT,
  chunk_index  INT,
  content      TEXT
)
LANGUAGE plpgsql STABLE
SECURITY DEFINER
AS $$
BEGIN
  IF p_case_insensitive THEN
    RETURN QUERY
      SELECT dc.id, dc.document_id, d.filename, dc.chunk_index, dc.content
      FROM public.document_chunks dc
      JOIN public.documents d ON d.id = dc.document_id
      WHERE dc.user_id = p_user_id
        AND dc.content ~* p_pattern
      ORDER BY d.filename, dc.chunk_index
      LIMIT p_max_results;
  ELSE
    RETURN QUERY
      SELECT dc.id, dc.document_id, d.filename, dc.chunk_index, dc.content
      FROM public.document_chunks dc
      JOIN public.documents d ON d.id = dc.document_id
      WHERE dc.user_id = p_user_id
        AND dc.content ~ p_pattern
      ORDER BY d.filename, dc.chunk_index
      LIMIT p_max_results;
  END IF;
END;
$$;
