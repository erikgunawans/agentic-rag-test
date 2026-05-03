-- ============================================================
-- RAG Pipeline Improvements — Phase 1 (LEGACY — renumbered from 024)
-- ============================================================
-- HISTORY: Originally shipped as 024_rag_improvements.sql alongside
-- 024_knowledge_base_explorer.sql, causing a duplicate-version PK
-- collision in supabase_migrations.schema_migrations. The DDL below
-- has already been applied to production via an earlier --include-all
-- push. Renaming to 041 lets the CLI register a unique version row.
--
-- The DDL is idempotent (DROP IF EXISTS / IF NOT EXISTS), so re-running
-- it is a no-op. The closing UPDATE has been COMMENTED OUT to prevent
-- it from clobbering live system_settings values.
-- ============================================================

-- Drop existing functions (return type changed — cannot use CREATE OR REPLACE)
drop function if exists match_document_chunks_with_metadata(vector, uuid, int, float, text);
drop function if exists match_document_chunks_fulltext(text, uuid, int, text);

-- 1. Vector search with metadata — now includes chunk_index
create function match_document_chunks_with_metadata(
  query_embedding  vector(1536),
  match_user_id    uuid,
  match_count      int   default 5,
  match_threshold  float default 0.7,
  filter_category  text  default null
)
returns table (
  id            uuid,
  document_id   uuid,
  content       text,
  similarity    float,
  doc_filename  text,
  doc_metadata  jsonb,
  chunk_index   int
)
language sql stable
as $$
  select
    dc.id,
    dc.document_id,
    dc.content,
    1 - (dc.embedding <=> query_embedding) as similarity,
    d.filename  as doc_filename,
    d.metadata  as doc_metadata,
    dc.chunk_index
  from public.document_chunks dc
  join public.documents d on d.id = dc.document_id
  where dc.user_id = match_user_id
    and 1 - (dc.embedding <=> query_embedding) > match_threshold
    and (filter_category is null or d.metadata->>'category' = filter_category)
  order by dc.embedding <=> query_embedding
  limit match_count;
$$;

-- 2. Fulltext search — now includes chunk_index
create function match_document_chunks_fulltext(
  search_query    text,
  match_user_id   uuid,
  match_count     int  default 20,
  filter_category text default null
)
returns table (
  id            uuid,
  document_id   uuid,
  content       text,
  rank          float,
  doc_filename  text,
  doc_metadata  jsonb,
  chunk_index   int
)
language sql stable
as $$
  select
    dc.id,
    dc.document_id,
    dc.content,
    ts_rank(dc.fts, websearch_to_tsquery('simple', search_query)) as rank,
    d.filename  as doc_filename,
    d.metadata  as doc_metadata,
    dc.chunk_index
  from public.document_chunks dc
  join public.documents d on d.id = dc.document_id
  where dc.user_id = match_user_id
    and dc.fts @@ websearch_to_tsquery('simple', search_query)
    and (filter_category is null or d.metadata->>'category' = filter_category)
  order by rank desc
  limit match_count;
$$;

-- 3. New RAG settings columns
alter table public.system_settings
  add column if not exists rag_context_enabled boolean not null default true,
  add column if not exists rag_neighbor_window int not null default 1,
  add column if not exists rag_query_expansion_enabled boolean not null default false;

-- COMMENTED OUT 2026-05-03: re-running this UPDATE on prod would clobber any
-- live admin-UI changes to these three RAG settings. The columns above have
-- IF NOT EXISTS guards, so initial defaults still apply on first install.
-- update public.system_settings
--   set rag_context_enabled = true, rag_neighbor_window = 1, rag_query_expansion_enabled = false
--   where id = 1;
