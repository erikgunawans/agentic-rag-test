-- ============================================================
-- Feature 5: Approval Workflow Engine
-- Sequential approval chains for document tool results
-- ============================================================

-- 1. Approval workflow templates (admin-defined)
create table public.approval_workflow_templates (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  description text,
  steps jsonb not null default '[]'::jsonb,
  -- steps: [{step_order: 1, approver_role: "super_admin", approver_email: null}, ...]
  created_by uuid references auth.users(id) on delete set null,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- 2. Approval requests (submitted items)
create table public.approval_requests (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  template_id uuid references public.approval_workflow_templates(id) on delete set null,
  resource_type text not null default 'document_tool_result',
  resource_id uuid not null,
  title text not null,
  status text not null default 'pending'
    check (status in ('pending', 'in_progress', 'approved', 'rejected', 'cancelled')),
  current_step int not null default 1,
  submitted_at timestamptz not null default now(),
  completed_at timestamptz
);

-- 3. Approval actions (individual approver decisions)
create table public.approval_actions (
  id uuid primary key default gen_random_uuid(),
  request_id uuid not null references public.approval_requests(id) on delete cascade,
  step_order int not null,
  actor_id uuid not null references auth.users(id) on delete cascade,
  actor_email text,
  action text not null
    check (action in ('approve', 'reject', 'return')),
  comments text,
  acted_at timestamptz not null default now()
);

-- 4. Enable RLS
alter table public.approval_workflow_templates enable row level security;
alter table public.approval_requests enable row level security;
alter table public.approval_actions enable row level security;

-- 5. RLS — workflow templates (admin read/write, all authenticated can read active)
create policy "templates_select"
  on public.approval_workflow_templates for select to authenticated
  using (is_active = true or (auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin');

create policy "templates_admin_insert"
  on public.approval_workflow_templates for insert to authenticated
  with check ((auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin');

create policy "templates_admin_update"
  on public.approval_workflow_templates for update to authenticated
  using ((auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin')
  with check ((auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin');

create policy "templates_admin_delete"
  on public.approval_workflow_templates for delete to authenticated
  using ((auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin');

-- 6. RLS — approval requests (users see own, admins see all)
create policy "requests_select"
  on public.approval_requests for select to authenticated
  using (
    auth.uid() = user_id
    or (auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin'
  );

create policy "requests_insert"
  on public.approval_requests for insert to authenticated
  with check (auth.uid() = user_id);

create policy "requests_update"
  on public.approval_requests for update to authenticated
  using (
    auth.uid() = user_id
    or (auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin'
  );

-- 7. RLS — approval actions (admins can insert actions, all can read related)
create policy "actions_select"
  on public.approval_actions for select to authenticated
  using (true);

create policy "actions_insert"
  on public.approval_actions for insert to authenticated
  with check (auth.uid() = actor_id);

-- 8. Indexes
create index idx_approval_requests_user_id on public.approval_requests(user_id);
create index idx_approval_requests_status on public.approval_requests(status);
create index idx_approval_requests_resource on public.approval_requests(resource_type, resource_id);
create index idx_approval_actions_request_id on public.approval_actions(request_id);

-- 9. Triggers
create trigger handle_approval_templates_updated_at
  before update on public.approval_workflow_templates
  for each row execute function public.handle_updated_at();

-- 10. Seed a default approval workflow template
insert into public.approval_workflow_templates (name, description, steps, is_active)
values (
  'Standard Admin Approval',
  'Single-step approval by a super admin',
  '[{"step_order": 1, "approver_role": "super_admin", "approver_email": null}]'::jsonb,
  true
);

comment on table public.approval_workflow_templates is
  'Admin-defined approval workflow definitions with sequential steps.';
comment on table public.approval_requests is
  'Active approval instances tied to document tool results.';
comment on table public.approval_actions is
  'Individual approve/reject/return decisions by approvers.';
