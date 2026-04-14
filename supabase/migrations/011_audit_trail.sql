-- ============================================================
-- Feature 1: Audit Trail & Activity Logging
-- ============================================================

-- 1. Audit logs table (no RLS — admin-only access via service-role)
create table public.audit_logs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete set null,
  user_email text,
  action text not null,
  resource_type text not null,
  resource_id text,
  details jsonb default '{}'::jsonb,
  ip_address text,
  created_at timestamptz not null default now()
);

-- 2. Indexes for query performance
create index idx_audit_logs_user_id on public.audit_logs(user_id);
create index idx_audit_logs_created_at on public.audit_logs(created_at desc);
create index idx_audit_logs_action on public.audit_logs(action);
create index idx_audit_logs_resource_type on public.audit_logs(resource_type);

-- 3. Enable RLS — prevent direct PostgREST access by non-admins
alter table public.audit_logs enable row level security;

create policy "admins_read_audit_logs"
  on public.audit_logs for select to authenticated
  using ((auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin');

-- Backend uses service-role client which bypasses RLS for writes.
-- PostgREST reads are restricted to super_admin only.

comment on table public.audit_logs is
  'System-wide audit trail. RLS enabled — admin-only read via PostgREST, service-role writes.';
