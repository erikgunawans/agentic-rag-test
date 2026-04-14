-- ============================================================
-- Feature 4: Obligation Lifecycle Tracker
-- ============================================================

-- 1. Obligations table
create table public.obligations (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  document_id uuid references public.documents(id) on delete set null,
  analysis_id uuid references public.document_tool_results(id) on delete set null,
  party text not null,
  obligation_text text not null,
  obligation_type text not null default 'general'
    check (obligation_type in ('payment', 'reporting', 'delivery', 'renewal', 'termination', 'compliance', 'general')),
  deadline timestamptz,
  recurrence text check (recurrence is null or recurrence in ('monthly', 'quarterly', 'annually')),
  status text not null default 'active'
    check (status in ('active', 'completed', 'overdue', 'upcoming', 'cancelled')),
  priority text not null default 'medium'
    check (priority in ('critical', 'high', 'medium', 'low')),
  reminder_days int not null default 7,
  notes text,
  contract_title text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- 2. Enable RLS
alter table public.obligations enable row level security;

create policy "users_see_own_obligations"
  on public.obligations for select to authenticated
  using (auth.uid() = user_id);

create policy "users_create_own_obligations"
  on public.obligations for insert to authenticated
  with check (auth.uid() = user_id);

create policy "users_update_own_obligations"
  on public.obligations for update to authenticated
  using (auth.uid() = user_id);

create policy "users_delete_own_obligations"
  on public.obligations for delete to authenticated
  using (auth.uid() = user_id);

-- 3. Indexes
create index idx_obligations_user_deadline on public.obligations(user_id, deadline);
create index idx_obligations_status on public.obligations(status);
create index idx_obligations_document on public.obligations(document_id);

-- 4. Auto-update updated_at trigger
create trigger handle_obligations_updated_at
  before update on public.obligations
  for each row execute function public.handle_updated_at();

-- 5. Function to mark overdue and upcoming obligations
create or replace function check_overdue_obligations(p_user_id uuid)
returns void
language plpgsql
as $$
begin
  -- Mark overdue
  update public.obligations
  set status = 'overdue'
  where user_id = p_user_id
    and status = 'active'
    and deadline is not null
    and deadline < now();

  -- Mark upcoming (within reminder_days window)
  update public.obligations
  set status = 'upcoming'
  where user_id = p_user_id
    and status = 'active'
    and deadline is not null
    and deadline >= now()
    and deadline < now() + (reminder_days || ' days')::interval;
end;
$$;
