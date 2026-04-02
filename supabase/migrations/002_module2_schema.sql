-- ============================================================
-- documents table
-- ============================================================
create table public.documents (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  filename    text not null,
  file_path   text not null,
  file_size   bigint not null,
  mime_type   text not null,
  status      text not null default 'pending'
                check (status in ('pending', 'processing', 'completed', 'failed')),
  error_msg   text,
  chunk_count int,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

create trigger handle_documents_updated_at
  before update on public.documents
  for each row execute function public.handle_updated_at();

-- ============================================================
-- document_chunks table
-- ============================================================
create table public.document_chunks (
  id          uuid primary key default gen_random_uuid(),
  document_id uuid not null references public.documents(id) on delete cascade,
  user_id     uuid not null references auth.users(id) on delete cascade,
  content     text not null,
  chunk_index int not null,
  embedding   vector(1536),
  created_at  timestamptz not null default now()
);

-- IVFFlat index (lists=10 suits dev/small datasets)
create index document_chunks_embedding_idx
  on public.document_chunks
  using ivfflat (embedding vector_cosine_ops)
  with (lists = 10);

-- ============================================================
-- RLS — documents
-- ============================================================
alter table public.documents enable row level security;

create policy "users can see own documents"
  on public.documents for select
  using (auth.uid() = user_id);

create policy "users can create own documents"
  on public.documents for insert
  with check (auth.uid() = user_id);

create policy "users can update own documents"
  on public.documents for update
  using (auth.uid() = user_id);

create policy "users can delete own documents"
  on public.documents for delete
  using (auth.uid() = user_id);

-- ============================================================
-- RLS — document_chunks
-- ============================================================
alter table public.document_chunks enable row level security;

create policy "users can see own chunks"
  on public.document_chunks for select
  using (auth.uid() = user_id);

create policy "users can create own chunks"
  on public.document_chunks for insert
  with check (auth.uid() = user_id);

create policy "users can delete own chunks"
  on public.document_chunks for delete
  using (auth.uid() = user_id);

-- ============================================================
-- Vector similarity search RPC function
-- ============================================================
create or replace function match_document_chunks(
  query_embedding vector(1536),
  match_user_id   uuid,
  match_count     int   default 5,
  match_threshold float default 0.7
)
returns table (
  id         uuid,
  content    text,
  similarity float
)
language sql stable
as $$
  select
    id,
    content,
    1 - (embedding <=> query_embedding) as similarity
  from public.document_chunks
  where user_id = match_user_id
    and 1 - (embedding <=> query_embedding) > match_threshold
  order by embedding <=> query_embedding
  limit match_count;
$$;

-- ============================================================
-- Enable Realtime on documents table
-- ============================================================
alter publication supabase_realtime add table public.documents;
