-- 028: Global Folders — shared "read-only" folder visibility
-- Any user can mark their own top-level folder as global.
-- Global folders (and their entire subtree) are visible to all users.
-- Only the owner can modify/delete a global folder and its contents.

-- 1. Add is_global column
ALTER TABLE public.document_folders
  ADD COLUMN is_global boolean NOT NULL DEFAULT false;

CREATE INDEX idx_document_folders_global
  ON public.document_folders (is_global)
  WHERE is_global = true;

-- 2. Replace RLS policies to include global folder visibility
-- Helper: check if a folder is inside a global subtree
CREATE OR REPLACE FUNCTION is_in_global_subtree(folder_id UUID)
RETURNS boolean
LANGUAGE SQL STABLE
SECURITY DEFINER
AS $$
  WITH RECURSIVE ancestors AS (
    SELECT id, parent_folder_id, is_global
    FROM public.document_folders
    WHERE id = folder_id

    UNION ALL

    SELECT f.id, f.parent_folder_id, f.is_global
    FROM public.document_folders f
    JOIN ancestors a ON f.id = a.parent_folder_id
  )
  SELECT EXISTS (SELECT 1 FROM ancestors WHERE is_global = true);
$$;

-- SELECT: own folders + any folder in a global subtree
DROP POLICY IF EXISTS "users_select_own_folders" ON public.document_folders;
CREATE POLICY "users_select_own_or_global_folders"
  ON public.document_folders FOR SELECT TO authenticated
  USING (
    auth.uid() = user_id
    OR is_in_global_subtree(id)
  );

-- INSERT: only own folders (unchanged logic)
DROP POLICY IF EXISTS "users_insert_own_folders" ON public.document_folders;
CREATE POLICY "users_insert_own_folders"
  ON public.document_folders FOR INSERT TO authenticated
  WITH CHECK (auth.uid() = user_id);

-- UPDATE: only own folders (owner can toggle is_global)
DROP POLICY IF EXISTS "users_update_own_folders" ON public.document_folders;
CREATE POLICY "users_update_own_folders"
  ON public.document_folders FOR UPDATE TO authenticated
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

-- DELETE: only own folders
DROP POLICY IF EXISTS "users_delete_own_folders" ON public.document_folders;
CREATE POLICY "users_delete_own_folders"
  ON public.document_folders FOR DELETE TO authenticated
  USING (auth.uid() = user_id);

-- 3. Documents in global folders are read-only for non-owners
-- Add SELECT policy for documents in global folder subtrees
CREATE POLICY "users_can_see_documents_in_global_folders"
  ON public.documents FOR SELECT TO authenticated
  USING (
    auth.uid() = user_id
    OR (folder_id IS NOT NULL AND is_in_global_subtree(folder_id))
  );

-- 4. Update get_folder_tree RPC to include global folders from other users
CREATE OR REPLACE FUNCTION get_folder_tree(p_user_id UUID, p_max_depth INT DEFAULT 10)
RETURNS TABLE (
  id UUID,
  name TEXT,
  parent_folder_id UUID,
  depth INT,
  path TEXT,
  document_count BIGINT,
  is_global BOOLEAN,
  owner_id UUID
)
LANGUAGE SQL STABLE
SECURITY DEFINER
AS $$
  WITH RECURSIVE tree AS (
    -- Base: user's own root folders + other users' global root folders
    SELECT f.id, f.name, f.parent_folder_id,
           0 AS depth, '/' || f.name AS path,
           f.is_global, f.user_id AS owner_id
    FROM public.document_folders f
    WHERE f.parent_folder_id IS NULL
      AND (f.user_id = p_user_id OR f.is_global = true)

    UNION ALL

    -- Recurse into children
    SELECT f.id, f.name, f.parent_folder_id,
           t.depth + 1, t.path || '/' || f.name,
           f.is_global, f.user_id AS owner_id
    FROM public.document_folders f
    JOIN tree t ON f.parent_folder_id = t.id
    WHERE t.depth < p_max_depth
  )
  SELECT tree.id, tree.name, tree.parent_folder_id, tree.depth, tree.path,
         (SELECT COUNT(*) FROM public.documents d
          WHERE d.folder_id = tree.id
            AND (d.user_id = p_user_id OR is_in_global_subtree(d.folder_id))
         ) AS document_count,
         tree.is_global,
         tree.owner_id
  FROM tree
  ORDER BY tree.path;
$$;
