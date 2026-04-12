-- ============================================================
-- Fix: Switch FTS from English-only to language-agnostic
-- ============================================================
-- PostgreSQL has no native Indonesian text search config.
-- 'simple' tokenizes/lowercases without language-specific stemming,
-- which works correctly for both Bahasa Indonesia and English.

-- 1. Replace the FTS trigger function
create or replace function document_chunks_fts_trigger()
returns trigger as $$
begin
  new.fts := to_tsvector('simple', new.content);
  return new;
end;
$$ language plpgsql;

-- 2. Backfill existing rows with new config
update public.document_chunks set fts = to_tsvector('simple', content);

-- 3. Replace the full-text search RPC function
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
    ts_rank(dc.fts, websearch_to_tsquery('simple', search_query)) as rank,
    d.filename  as doc_filename,
    d.metadata  as doc_metadata
  from public.document_chunks dc
  join public.documents d on d.id = dc.document_id
  where dc.user_id = match_user_id
    and dc.fts @@ websearch_to_tsquery('simple', search_query)
    and (filter_category is null or d.metadata->>'category' = filter_category)
  order by rank desc
  limit match_count;
$$;
