-- ============================================================
-- RAG Pipeline Improvements — Phase 1
-- Adds chunk_index to search RPCs + new settings columns
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

update public.system_settings
  set rag_context_enabled = true, rag_neighbor_window = 1, rag_query_expansion_enabled = false
  where id = 1;
