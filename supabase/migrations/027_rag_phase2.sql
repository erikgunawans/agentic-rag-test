-- ============================================================
-- RAG Pipeline Phase 2
-- Extends RPCs with metadata filters, adds fusion weights
-- and rerank mode to system_settings
-- ============================================================

-- 1. Drop existing RPCs (signatures must match migration 024)
drop function if exists match_document_chunks_with_metadata(vector, uuid, int, float, text);
drop function if exists match_document_chunks_fulltext(text, uuid, int, text);

-- 2. Vector search with metadata filters
create function match_document_chunks_with_metadata(
  query_embedding   vector(1536),
  match_user_id     uuid,
  match_count       int            default 5,
  match_threshold   float          default 0.7,
  filter_category   text           default null,
  filter_tags       text[]         default null,
  filter_folder_id  uuid           default null,
  filter_date_from  timestamptz    default null,
  filter_date_to    timestamptz    default null
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
    and (filter_tags is null or d.metadata->'tags' ?| filter_tags)
    and (filter_folder_id is null or d.folder_id = filter_folder_id)
    and (filter_date_from is null or d.created_at >= filter_date_from)
    and (filter_date_to is null or d.created_at <= filter_date_to)
  order by dc.embedding <=> query_embedding
  limit match_count;
$$;

-- 3. Fulltext search with metadata filters
create function match_document_chunks_fulltext(
  search_query      text,
  match_user_id     uuid,
  match_count       int            default 20,
  filter_category   text           default null,
  filter_tags       text[]         default null,
  filter_folder_id  uuid           default null,
  filter_date_from  timestamptz    default null,
  filter_date_to    timestamptz    default null
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
    and (filter_tags is null or d.metadata->'tags' ?| filter_tags)
    and (filter_folder_id is null or d.folder_id = filter_folder_id)
    and (filter_date_from is null or d.created_at >= filter_date_from)
    and (filter_date_to is null or d.created_at <= filter_date_to)
  order by rank desc
  limit match_count;
$$;

-- 4. New system_settings columns for fusion weights and rerank mode
alter table public.system_settings
  add column if not exists rag_vector_weight float not null default 1.0,
  add column if not exists rag_fulltext_weight float not null default 1.0,
  add column if not exists rag_rerank_mode text not null default 'none';

update public.system_settings
  set rag_vector_weight = 1.0, rag_fulltext_weight = 1.0, rag_rerank_mode = 'none'
  where id = 1;
