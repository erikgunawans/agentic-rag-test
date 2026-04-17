-- ============================================================
-- 023_uu_pdp_toolkit.sql
-- F14: UU PDP Compliance Toolkit
-- 3 tables: data_inventory, pdp_compliance_status, data_breach_incidents
-- ============================================================

-- ── 1. data_inventory ────────────────────────────────────────

create table public.data_inventory (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id),
  processing_activity text not null,
  data_categories text[] not null default '{}',
  lawful_basis text not null check (lawful_basis in ('consent', 'contract', 'legal_obligation', 'vital_interest', 'public_task', 'legitimate_interest')),
  purposes text[] not null default '{}',
  data_subjects text[] not null default '{}',
  processors jsonb not null default '[]',
  retention_period text,
  security_measures text[] not null default '{}',
  dpia_required boolean not null default false,
  dpia_status text not null default 'not_started' check (dpia_status in ('not_started', 'in_progress', 'completed')),
  status text not null default 'active' check (status in ('active', 'archived')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_data_inv_user on public.data_inventory(user_id);
create index idx_data_inv_status on public.data_inventory(status);
create index idx_data_inv_basis on public.data_inventory(lawful_basis);

create trigger data_inventory_updated_at
  before update on public.data_inventory
  for each row execute function public.set_updated_at();

alter table public.data_inventory enable row level security;

create policy "Users can read own inventory"
  on public.data_inventory for select to authenticated
  using (user_id = auth.uid());

create policy "Admins and DPO can read all inventory"
  on public.data_inventory for select to authenticated
  using ((auth.jwt() -> 'app_metadata' ->> 'role') in ('super_admin', 'dpo'));

create policy "Users can insert own inventory"
  on public.data_inventory for insert to authenticated
  with check (user_id = auth.uid());

create policy "Users can update own inventory"
  on public.data_inventory for update to authenticated
  using (user_id = auth.uid());


-- ── 2. pdp_compliance_status ─────────────────────────────────

create table public.pdp_compliance_status (
  id integer primary key default 1 check (id = 1),
  dpo_appointed boolean not null default false,
  dpo_name text,
  dpo_email text,
  dpo_appointed_at timestamptz,
  breach_plan_exists boolean not null default false,
  readiness_score float not null default 0.0,
  last_assessment_at timestamptz,
  updated_at timestamptz not null default now()
);

insert into public.pdp_compliance_status (id) values (1) on conflict do nothing;

alter table public.pdp_compliance_status enable row level security;

create policy "Authenticated users can read PDP status"
  on public.pdp_compliance_status for select to authenticated
  using (true);

create policy "Admins and DPO can update PDP status"
  on public.pdp_compliance_status for update to authenticated
  using ((auth.jwt() -> 'app_metadata' ->> 'role') in ('super_admin', 'dpo'));


-- ── 3. data_breach_incidents ─────────────────────────────────

create table public.data_breach_incidents (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id),
  incident_date timestamptz not null,
  discovered_date timestamptz not null default now(),
  incident_type text not null check (incident_type in ('unauthorized_access', 'ransomware', 'accidental_disclosure', 'data_loss', 'insider_threat')),
  description text,
  affected_data_categories text[] not null default '{}',
  estimated_records int,
  response_status text not null default 'reported' check (response_status in ('reported', 'investigating', 'remediated', 'closed')),
  regulator_notified_at timestamptz,
  subjects_notified_at timestamptz,
  root_cause text,
  remediation_actions text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_breach_user on public.data_breach_incidents(user_id);
create index idx_breach_status on public.data_breach_incidents(response_status);
create index idx_breach_date on public.data_breach_incidents(incident_date desc);

create trigger breach_incidents_updated_at
  before update on public.data_breach_incidents
  for each row execute function public.set_updated_at();

alter table public.data_breach_incidents enable row level security;

create policy "Users can read own incidents"
  on public.data_breach_incidents for select to authenticated
  using (user_id = auth.uid());

create policy "Admins and DPO can read all incidents"
  on public.data_breach_incidents for select to authenticated
  using ((auth.jwt() -> 'app_metadata' ->> 'role') in ('super_admin', 'dpo'));

create policy "Users can insert incidents"
  on public.data_breach_incidents for insert to authenticated
  with check (user_id = auth.uid());

create policy "Users can update own incidents"
  on public.data_breach_incidents for update to authenticated
  using (user_id = auth.uid());

create policy "Admins and DPO can update all incidents"
  on public.data_breach_incidents for update to authenticated
  using ((auth.jwt() -> 'app_metadata' ->> 'role') in ('super_admin', 'dpo'));
