-- ============================================================
-- user_settings table — per-user LLM and embedding model config
-- ============================================================
create table public.user_settings (
  user_id         uuid primary key references auth.users(id) on delete cascade,
  llm_model       text not null default 'openai/gpt-4o-mini',
  embedding_model text not null default 'text-embedding-3-small',
  updated_at      timestamptz not null default now()
);

create trigger handle_user_settings_updated_at
  before update on public.user_settings
  for each row execute function public.handle_updated_at();

-- ============================================================
-- RLS — users see and edit only their own settings
-- ============================================================
alter table public.user_settings enable row level security;

create policy "users can see own settings"
  on public.user_settings for select
  using (auth.uid() = user_id);

create policy "users can create own settings"
  on public.user_settings for insert
  with check (auth.uid() = user_id);

create policy "users can update own settings"
  on public.user_settings for update
  using (auth.uid() = user_id);
