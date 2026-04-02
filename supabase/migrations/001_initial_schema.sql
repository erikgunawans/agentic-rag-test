-- Enable pgvector extension (used from Module 2+)
create extension if not exists vector;

-- ============================================================
-- Threads table
-- ============================================================
create table public.threads (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  title text not null default 'New Thread',
  openai_thread_id text,
  last_response_id text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- ============================================================
-- Messages table
-- ============================================================
create table public.messages (
  id uuid primary key default gen_random_uuid(),
  thread_id uuid not null references public.threads(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role text not null check (role in ('user', 'assistant')),
  content text not null,
  created_at timestamptz not null default now()
);

-- ============================================================
-- updated_at trigger
-- ============================================================
create or replace function public.handle_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

create trigger handle_threads_updated_at
  before update on public.threads
  for each row execute function public.handle_updated_at();

-- ============================================================
-- Row-Level Security — threads
-- ============================================================
alter table public.threads enable row level security;

create policy "users can see own threads"
  on public.threads for select
  using (auth.uid() = user_id);

create policy "users can create own threads"
  on public.threads for insert
  with check (auth.uid() = user_id);

create policy "users can update own threads"
  on public.threads for update
  using (auth.uid() = user_id);

create policy "users can delete own threads"
  on public.threads for delete
  using (auth.uid() = user_id);

-- ============================================================
-- Row-Level Security — messages
-- ============================================================
alter table public.messages enable row level security;

create policy "users can see own messages"
  on public.messages for select
  using (auth.uid() = user_id);

create policy "users can create own messages"
  on public.messages for insert
  with check (auth.uid() = user_id);

create policy "users can delete own messages"
  on public.messages for delete
  using (auth.uid() = user_id);
