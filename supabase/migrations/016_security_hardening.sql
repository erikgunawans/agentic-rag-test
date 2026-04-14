-- ============================================================
-- Feature 6: MFA & Security Hardening
-- User profiles + MFA settings + admin user management
-- ============================================================

-- 1. Add security settings to system_settings
alter table public.system_settings
  add column if not exists mfa_required boolean not null default false,
  add column if not exists session_timeout_minutes int not null default 480;

update public.system_settings set mfa_required = false, session_timeout_minutes = 480 where id = 1;

-- 2. User profiles table
create table public.user_profiles (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null unique references auth.users(id) on delete cascade,
  display_name text,
  department text,
  is_active boolean not null default true,
  deactivated_at timestamptz,
  deactivated_by uuid references auth.users(id) on delete set null,
  last_login_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- 3. Enable RLS
alter table public.user_profiles enable row level security;

-- 4. RLS — user profiles
create policy "profiles_select_own"
  on public.user_profiles for select to authenticated
  using (
    auth.uid() = user_id
    or (auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin'
  );

create policy "profiles_insert_own"
  on public.user_profiles for insert to authenticated
  with check (auth.uid() = user_id);

create policy "profiles_update"
  on public.user_profiles for update to authenticated
  using (
    auth.uid() = user_id
    or (auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin'
  );

-- 5. Indexes
create index idx_user_profiles_user_id on public.user_profiles(user_id);
create index idx_user_profiles_active on public.user_profiles(is_active) where is_active = false;

-- 6. Trigger
create trigger handle_user_profiles_updated_at
  before update on public.user_profiles
  for each row execute function public.handle_updated_at();

-- 7. Auto-create profile for existing users (backfill)
insert into public.user_profiles (user_id, display_name, is_active)
select id, coalesce(raw_user_meta_data->>'full_name', email), true
from auth.users
on conflict (user_id) do nothing;

comment on table public.user_profiles is
  'Extended user profiles with department, active status, and activity tracking. Admins can deactivate users.';
