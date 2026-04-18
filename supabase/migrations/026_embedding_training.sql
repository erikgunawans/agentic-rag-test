-- ============================================================
-- Embedding Fine-Tuning Infrastructure
-- Query logging for training data collection + custom model config
-- ============================================================

-- 1. query_logs — captures search queries and retrieved chunk IDs
create table public.query_logs (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid not null references auth.users(id) on delete cascade,
  query           text not null,
  retrieved_ids   uuid[] not null default '{}',
  retrieved_scores float[] not null default '{}',
  thread_id       uuid,
  tool_name       text not null default 'search_documents',
  created_at      timestamptz not null default now()
);

create index idx_query_logs_user on public.query_logs(user_id);
create index idx_query_logs_created on public.query_logs(created_at desc);

-- RLS: users see only own logs, service-role writes
alter table public.query_logs enable row level security;

create policy "users can see own query logs"
  on public.query_logs for select using (auth.uid() = user_id);

create policy "service can insert query logs"
  on public.query_logs for insert with check (true);

-- 2. Custom embedding model setting
alter table public.system_settings
  add column if not exists custom_embedding_model text not null default '';

update public.system_settings
  set custom_embedding_model = ''
  where id = 1;
