-- ============================================================
-- Feature 9: WhatsApp Notifications
-- Multi-channel notification system with delivery tracking
-- ============================================================

-- 1. Notification channels (per-user channel registration)
create table public.notification_channels (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  channel_type text not null
    check (channel_type in ('whatsapp', 'email', 'in_app')),
  channel_value text not null,
  is_verified boolean not null default false,
  is_enabled boolean not null default true,
  preferences jsonb not null default '{"approvals": true, "deadlines": true, "regulatory": true, "system": true}'::jsonb,
  verified_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, channel_type)
);

-- 2. Notification log (delivery tracking)
create table public.notification_log (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  channel_id uuid references public.notification_channels(id) on delete set null,
  notification_type text not null
    check (notification_type in ('approval_request', 'approval_action', 'deadline_reminder', 'regulatory_alert', 'system')),
  title text not null,
  body text not null,
  status text not null default 'pending'
    check (status in ('pending', 'sent', 'delivered', 'failed', 'read')),
  external_id text,
  error_message text,
  metadata jsonb default '{}'::jsonb,
  created_at timestamptz not null default now(),
  sent_at timestamptz,
  delivered_at timestamptz,
  read_at timestamptz
);

-- 3. Add WhatsApp settings to system_settings
alter table public.system_settings
  add column if not exists whatsapp_enabled boolean not null default false,
  add column if not exists whatsapp_phone_number_id text,
  add column if not exists whatsapp_access_token text;

-- 4. Enable RLS
alter table public.notification_channels enable row level security;
alter table public.notification_log enable row level security;

-- 5. RLS — channels (users manage own)
create policy "channels_select_own"
  on public.notification_channels for select to authenticated
  using (auth.uid() = user_id);

create policy "channels_insert_own"
  on public.notification_channels for insert to authenticated
  with check (auth.uid() = user_id);

create policy "channels_update_own"
  on public.notification_channels for update to authenticated
  using (auth.uid() = user_id);

create policy "channels_delete_own"
  on public.notification_channels for delete to authenticated
  using (auth.uid() = user_id);

-- 6. RLS — notification log (users see own, admins see all)
create policy "notif_log_select"
  on public.notification_log for select to authenticated
  using (
    auth.uid() = user_id
    or (auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin'
  );

-- 7. Indexes
create index idx_notif_channels_user on public.notification_channels(user_id);
create index idx_notif_log_user on public.notification_log(user_id);
create index idx_notif_log_status on public.notification_log(status) where status = 'pending';
create index idx_notif_log_type on public.notification_log(notification_type);

-- 8. Triggers
create trigger handle_notif_channels_updated_at
  before update on public.notification_channels
  for each row execute function public.handle_updated_at();
