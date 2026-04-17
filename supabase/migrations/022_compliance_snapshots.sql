-- ============================================================
-- 022_compliance_snapshots.sql
-- F13: Point-in-Time Compliance Querying
-- ============================================================

create table public.compliance_snapshots (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id),
  document_id uuid references public.documents(id) on delete set null,
  trigger_type text not null default 'manual' check (trigger_type in ('manual', 'regulatory_update', 'scheduled')),
  framework text not null check (framework in ('ojk', 'gdpr', 'international', 'custom')),
  scopes text[] not null default '{}',
  snapshot_date timestamptz not null default now(),
  overall_status text not null check (overall_status in ('pass', 'review', 'fail')),
  result jsonb not null default '{}',
  confidence_score float,
  regulatory_context text,
  created_at timestamptz not null default now()
);

create index idx_compliance_snap_user on public.compliance_snapshots(user_id);
create index idx_compliance_snap_framework on public.compliance_snapshots(framework);
create index idx_compliance_snap_date on public.compliance_snapshots(snapshot_date desc);
create index idx_compliance_snap_document on public.compliance_snapshots(document_id) where document_id is not null;

alter table public.compliance_snapshots enable row level security;

create policy "Users can read own snapshots"
  on public.compliance_snapshots for select to authenticated
  using (user_id = auth.uid());

create policy "Admins can read all snapshots"
  on public.compliance_snapshots for select to authenticated
  using ((auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin');

create policy "Users can insert own snapshots"
  on public.compliance_snapshots for insert to authenticated
  with check (user_id = auth.uid());
