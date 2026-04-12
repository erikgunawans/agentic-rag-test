-- ============================================================
-- Feature 12: Google Workspace Export
-- OAuth2 token storage for Google Drive export
-- ============================================================

-- 1. Google OAuth2 tokens (per-user)
create table public.google_tokens (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null unique references auth.users(id) on delete cascade,
  access_token text not null,
  refresh_token text,
  token_type text not null default 'Bearer',
  expires_at timestamptz,
  scope text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- 2. Enable RLS
alter table public.google_tokens enable row level security;

-- 3. RLS — tokens (users manage own only)
create policy "google_tokens_select"
  on public.google_tokens for select to authenticated
  using (auth.uid() = user_id);

create policy "google_tokens_insert"
  on public.google_tokens for insert to authenticated
  with check (auth.uid() = user_id);

create policy "google_tokens_update"
  on public.google_tokens for update to authenticated
  using (auth.uid() = user_id);

create policy "google_tokens_delete"
  on public.google_tokens for delete to authenticated
  using (auth.uid() = user_id);

-- 4. Index
create index idx_google_tokens_user on public.google_tokens(user_id);

-- 5. Trigger
create trigger handle_google_tokens_updated_at
  before update on public.google_tokens
  for each row execute function public.handle_updated_at();

-- 6. Add Google OAuth settings to system_settings
alter table public.system_settings
  add column if not exists google_client_id text,
  add column if not exists google_client_secret text;
