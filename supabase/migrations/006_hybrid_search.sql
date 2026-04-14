-- ============================================================
-- Module 6: Hybrid Search & Reranking
-- ============================================================

-- 1. Add tsvector column for full-text search
alter table public.document_chunks add column fts tsvector;

-- 2. Backfill existing rows
update public.document_chunks set fts = to_tsvector('english', content);

-- 3. GIN index for full-text search performance
create index idx_document_chunks_fts
  on public.document_chunks
  using gin (fts);

-- 4. Trigger to auto-populate fts on INSERT / UPDATE
create or replace function document_chunks_fts_trigger()
returns trigger as $$
begin
  new.fts := to_tsvector('english', new.content);
  return new;
end;
$$ language plpgsql;

create trigger trg_document_chunks_fts
  before insert or update of content on public.document_chunks
  for each row execute function document_chunks_fts_trigger();

-- ============================================================
-- Full-text search RPC: chunks ranked by ts_rank with metadata
-- ============================================================
create or replace function match_document_chunks_fulltext(
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
  doc_metadata  jsonb
)
language sql stable
as $$
  select
    dc.id,
    dc.document_id,
    dc.content,
    ts_rank(dc.fts, websearch_to_tsquery('english', search_query)) as rank,
    d.filename  as doc_filename,
    d.metadata  as doc_metadata
  from public.document_chunks dc
  join public.documents d on d.id = dc.document_id
  where dc.user_id = match_user_id
    and dc.fts @@ websearch_to_tsquery('english', search_query)
    and (filter_category is null or d.metadata->>'category' = filter_category)
  order by rank desc
  limit match_count;
$$;
