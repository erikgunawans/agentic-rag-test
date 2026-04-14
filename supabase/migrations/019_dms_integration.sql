-- ============================================================
-- Feature 11: Dokmee DMS Integration
-- Bidirectional document management system integration
-- ============================================================

-- 1. Add DMS settings to system_settings
alter table public.system_settings
  add column if not exists dokmee_api_url text,
  add column if not exists dokmee_api_key text,
  add column if not exists dokmee_default_cabinet text;

-- 2. Add external source tracking to documents
alter table public.documents
  add column if not exists external_source text,
  add column if not exists external_id text;

-- 3. Index for external source lookups
create index if not exists idx_documents_external
  on public.documents(external_source, external_id)
  where external_source is not null;
