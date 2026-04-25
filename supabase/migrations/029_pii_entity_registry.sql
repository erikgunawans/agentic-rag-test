-- 029: PII Entity Registry — conversation-scoped real↔surrogate map (Phase 2)
-- System-level table; service-role only. End users never query this directly.
-- See PRD-PII-Redaction-System-v1.1.md §4.FR-3 and 02-CONTEXT.md D-21..D-26.
--
-- FUTURE-WORK (D-31, Phase 6 hardening): the application-side per-thread
-- asyncio.Lock used in redaction_service.py is correct only while Railway
-- runs a single Uvicorn worker. Under multi-worker / horizontally scaled
-- instances, replace with `pg_advisory_xact_lock(hashtext(thread_id::text))`
-- inside a transaction. The composite UNIQUE constraint below already
-- provides the cross-process serialisation safety net regardless.

-- 1. Table
create table public.entity_registry (
  id uuid primary key default gen_random_uuid(),
  thread_id uuid not null references public.threads(id) on delete cascade,
  real_value text not null,
  real_value_lower text not null,         -- str.casefold()'d at write time; case-insensitive lookup path (D-36)
  surrogate_value text not null,
  entity_type text not null,              -- Presidio type: PERSON / EMAIL_ADDRESS / PHONE_NUMBER / LOCATION / DATE_TIME / URL / IP_ADDRESS (D-22)
  source_message_id uuid null references public.messages(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (thread_id, real_value_lower)    -- D-23: enforces "same real → same surrogate" at DB layer (cross-process serialisation safety net for D-31 future)
);

-- 2. Indexes
create index idx_entity_registry_thread_id
  on public.entity_registry (thread_id);
-- The unique constraint above already provides the composite index for the
-- (thread_id, real_value_lower) lookup path used by ConversationRegistry.lookup.

-- 3. updated_at trigger (function defined in migration 001)
create trigger handle_entity_registry_updated_at
  before update on public.entity_registry
  for each row execute function public.handle_updated_at();

-- 4. RLS — system-level table, service-role only. NO user-facing policies (D-25).
alter table public.entity_registry enable row level security;
-- Intentionally no SELECT/INSERT/UPDATE/DELETE policies. End users have ZERO
-- direct PostgREST access; backend uses get_supabase_client() (service-role)
-- for all reads and writes. See 02-CONTEXT.md D-25 / D-26.

comment on table public.entity_registry is
  'System-wide PII real↔surrogate registry per thread. RLS enabled — service-role only (no policies). See PRD-PII-Redaction-System-v1.1.md §4.FR-3.';
