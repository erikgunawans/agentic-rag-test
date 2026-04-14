-- ============================================================
-- Feature 8: Regulatory Intelligence Engine
-- Automated regulatory monitoring with relevance scoring
-- ============================================================

-- 1. Regulatory sources (crawl targets)
create table public.regulatory_sources (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  url text not null,
  source_type text not null default 'jdih'
    check (source_type in ('jdih', 'idx', 'perda', 'ojk', 'custom')),
  crawl_schedule text not null default 'weekly'
    check (crawl_schedule in ('daily', 'weekly', 'monthly', 'manual')),
  css_selector text,
  metadata jsonb default '{}'::jsonb,
  is_active boolean not null default true,
  last_crawled_at timestamptz,
  created_by uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- 2. Regulatory updates (crawled content)
create table public.regulatory_updates (
  id uuid primary key default gen_random_uuid(),
  source_id uuid not null references public.regulatory_sources(id) on delete cascade,
  title text not null,
  content text not null,
  url text,
  published_at timestamptz,
  regulation_number text,
  regulation_type text,
  relevance_score float default 0.0,
  relevance_summary text,
  embedding vector(1536),
  is_read boolean not null default false,
  crawled_at timestamptz not null default now()
);

-- 3. Regulatory alerts (per-user notifications)
create table public.regulatory_alerts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  update_id uuid not null references public.regulatory_updates(id) on delete cascade,
  alert_type text not null default 'relevance'
    check (alert_type in ('relevance', 'keyword', 'category')),
  is_dismissed boolean not null default false,
  created_at timestamptz not null default now()
);

-- 4. Enable RLS
alter table public.regulatory_sources enable row level security;
alter table public.regulatory_updates enable row level security;
alter table public.regulatory_alerts enable row level security;

-- 5. RLS — sources (all can read active, admin manages)
create policy "reg_sources_select"
  on public.regulatory_sources for select to authenticated
  using (true);

create policy "reg_sources_admin_insert"
  on public.regulatory_sources for insert to authenticated
  with check ((auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin');

create policy "reg_sources_admin_update"
  on public.regulatory_sources for update to authenticated
  using ((auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin');

create policy "reg_sources_admin_delete"
  on public.regulatory_sources for delete to authenticated
  using ((auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin');

-- 6. RLS — updates (all authenticated can read)
create policy "reg_updates_select"
  on public.regulatory_updates for select to authenticated
  using (true);

-- 7. RLS — alerts (users see own)
create policy "reg_alerts_select"
  on public.regulatory_alerts for select to authenticated
  using (auth.uid() = user_id);

create policy "reg_alerts_update"
  on public.regulatory_alerts for update to authenticated
  using (auth.uid() = user_id);

-- 8. Indexes
create index idx_reg_sources_active on public.regulatory_sources(is_active) where is_active = true;
create index idx_reg_updates_source on public.regulatory_updates(source_id);
create index idx_reg_updates_crawled on public.regulatory_updates(crawled_at desc);
create index idx_reg_updates_relevance on public.regulatory_updates(relevance_score desc);
create index idx_reg_alerts_user on public.regulatory_alerts(user_id);
create index idx_reg_alerts_dismissed on public.regulatory_alerts(is_dismissed) where is_dismissed = false;

-- 9. Triggers
create trigger handle_reg_sources_updated_at
  before update on public.regulatory_sources
  for each row execute function public.handle_updated_at();

-- 10. Seed default Indonesian regulatory sources
insert into public.regulatory_sources (name, url, source_type, crawl_schedule, is_active)
values
  ('JDIH Kemenkumham', 'https://jdih.kemenkumham.go.id', 'jdih', 'weekly', true),
  ('IDX Regulations', 'https://www.idx.co.id/id/peraturan', 'idx', 'weekly', true),
  ('OJK Regulations', 'https://www.ojk.go.id/id/regulasi', 'ojk', 'weekly', true),
  ('Perda DKI Jakarta', 'https://jdih.jakarta.go.id', 'perda', 'monthly', true);
