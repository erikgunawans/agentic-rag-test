-- ============================================================
-- Module 4: Metadata Extraction
-- ============================================================

-- Add metadata JSONB column to documents (nullable for backward compat)
alter table public.documents add column metadata jsonb;

-- GIN index for efficient JSONB containment queries
create index idx_documents_metadata
  on public.documents
  using gin (metadata);

-- ============================================================
-- Enhanced retrieval RPC: chunks joined with document metadata
-- ============================================================
create or replace function match_document_chunks_with_metadata(
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
  doc_metadata  jsonb
)
language sql stable
as $$
  select
    dc.id,
    dc.document_id,
    dc.content,
    1 - (dc.embedding <=> query_embedding) as similarity,
    d.filename  as doc_filename,
    d.metadata  as doc_metadata
  from public.document_chunks dc
  join public.documents d on d.id = dc.document_id
  where dc.user_id = match_user_id
    and 1 - (dc.embedding <=> query_embedding) > match_threshold
    and (filter_category is null or d.metadata->>'category' = filter_category)
  order by dc.embedding <=> query_embedding
  limit match_count;
$$;
