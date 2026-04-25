---
phase: 02-conversation-scoped-registry-and-round-trip
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - supabase/migrations/029_pii_entity_registry.sql
autonomous: true
requirements: [REG-01, REG-02, REG-03, REG-04, REG-05]
must_haves:
  truths:
    - "Migration file 029_pii_entity_registry.sql exists and is well-formed SQL"
    - "Table entity_registry has all 8 columns from D-22 with exact types"
    - "Composite UNIQUE constraint on (thread_id, real_value_lower) is present (D-23)"
    - "thread_id FK has ON DELETE CASCADE; source_message_id FK is nullable + ON DELETE SET NULL"
    - "RLS is enabled with NO user-facing policies (D-25)"
    - "handle_updated_at trigger is wired (handle_entity_registry_updated_at)"
  artifacts:
    - path: "supabase/migrations/029_pii_entity_registry.sql"
      provides: "PII entity registry table DDL"
      contains: "create table public.entity_registry"
  key_links:
    - from: "supabase/migrations/029_pii_entity_registry.sql"
      to: "public.threads(id)"
      via: "FK on entity_registry.thread_id"
      pattern: "references public\\.threads\\(id\\) on delete cascade"
    - from: "supabase/migrations/029_pii_entity_registry.sql"
      to: "public.messages(id)"
      via: "Nullable FK on entity_registry.source_message_id"
      pattern: "references public\\.messages\\(id\\) on delete set null"
    - from: "supabase/migrations/029_pii_entity_registry.sql"
      to: "public.handle_updated_at()"
      via: "trigger handle_entity_registry_updated_at"
      pattern: "execute function public\\.handle_updated_at"
---

<objective>
Ship migration 029 — the `entity_registry` Postgres table that backs the conversation-scoped real↔surrogate map.

Purpose: Establish the durable, RLS-locked storage layer Phase 2 builds on. Same real entity → same surrogate within a thread is enforced at the DB layer (composite UNIQUE) so even under multi-worker scale-out (D-31 future) the invariant survives.

Output: `supabase/migrations/029_pii_entity_registry.sql` — table, indexes, RLS, updated_at trigger. NOT pushed yet (Wave 2 task does the push).
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/02-conversation-scoped-registry-and-round-trip/02-CONTEXT.md
@.planning/phases/02-conversation-scoped-registry-and-round-trip/02-PATTERNS.md
@CLAUDE.md
@supabase/migrations/001_initial_schema.sql
@supabase/migrations/011_audit_trail.sql
@supabase/migrations/013_obligations.sql

<interfaces>
<!-- Existing primitives this migration reuses. Read once; no codebase exploration needed. -->

From supabase/migrations/001_initial_schema.sql L7-42:
- `public.threads(id uuid primary key)` — FK target for thread_id
- `public.messages(id uuid primary key)` — FK target for source_message_id
- `public.handle_updated_at()` plpgsql trigger function (already defined; just wire it)

From supabase/migrations/011_audit_trail.sql L1-35:
- The "system-level RLS-no-user-policies" pattern (audit_logs precedent — but Phase 2 drops EVEN the super_admin SELECT policy because there is no PostgREST consumer per D-26)
- `comment on table ... is '...'` annotation form
- Index naming convention: `idx_<table>_<columns>`
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create migration 029_pii_entity_registry.sql with table, indexes, RLS, trigger</name>
  <files>supabase/migrations/029_pii_entity_registry.sql</files>
  <read_first>
    - supabase/migrations/028_global_folders.sql (last applied — confirms 029 is next sequential per CLAUDE.md gotcha)
    - supabase/migrations/011_audit_trail.sql (system-level RLS-no-user-policies analog — D-25)
    - supabase/migrations/001_initial_schema.sql L7-42 (FK shapes + handle_updated_at function definition)
    - supabase/migrations/013_obligations.sql (handle_updated_at trigger wiring precedent)
    - .planning/phases/02-conversation-scoped-registry-and-round-trip/02-PATTERNS.md §"Composed migration 029 sketch" (the full target SQL with line-by-line rationale)
    - .planning/phases/02-conversation-scoped-registry-and-round-trip/02-CONTEXT.md decisions D-21, D-22, D-23, D-24, D-25, D-26, D-36
  </read_first>
  <action>
Create exactly the file `supabase/migrations/029_pii_entity_registry.sql` (NOT via /create-migration skill — write directly; the file number is locked by D-21 and the next-sequential rule from CLAUDE.md). The file is a single SQL script with FOUR sections. Use lowercase SQL keywords (matches the project's existing migration style — see migrations 001, 011, 013, 028).

Header comment block (mandatory):
```sql
-- 029: PII Entity Registry — conversation-scoped real↔surrogate map (Phase 2)
-- System-level table; service-role only. End users never query this directly.
-- See PRD-PII-Redaction-System-v1.1.md §4.FR-3 and 02-CONTEXT.md D-21..D-26.
```

Section 1 — Table (D-22 column-by-column, NOTHING else):
```sql
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
```

Hard requirements that the executor MUST verify after writing:
- `thread_id` is `not null` AND has `references public.threads(id) on delete cascade` (D-22).
- `source_message_id` is `null` (nullable) AND has `references public.messages(id) on delete set null` — NOT cascade. Reason: Phase 5 chat router backfills this AFTER message commit; deleting one message must NOT delete its registry rows because the surrogates are still the active mapping (D-22 + per CONTEXT.md "specifics" §"`source_message_id` is nullable for a real reason").
- `entity_type` is `text not null` — NO check constraint. Phase 1's `_HARD_REDACT_TYPES` set is application-side; adding a SQL CHECK creates a coupling point that breaks when Presidio adds new types.
- The composite UNIQUE constraint goes INLINE in the table body (not a separate `alter table` later) — matches the pattern in `001_initial_schema.sql`.

Section 2 — Indexes:
```sql
-- 2. Indexes
create index idx_entity_registry_thread_id
  on public.entity_registry (thread_id);
-- The unique constraint above already provides the composite index for the
-- (thread_id, real_value_lower) lookup path used by ConversationRegistry.lookup.
```

Do NOT add an index on `real_value_lower` alone — the composite UNIQUE constraint already serves both the equality lookup and the thread_id-scoped scan (Postgres uses the composite index leftmost-prefix-friendly).

Section 3 — Trigger (function already exists from migration 001):
```sql
-- 3. updated_at trigger (function defined in migration 001)
create trigger handle_entity_registry_updated_at
  before update on public.entity_registry
  for each row execute function public.handle_updated_at();
```

Trigger name `handle_entity_registry_updated_at` matches the project convention (see `handle_threads_updated_at`, `handle_obligations_updated_at`).

Section 4 — RLS (D-25; STRICTER than `audit_logs` — no super_admin policy because there is no HTTP route per D-26):
```sql
-- 4. RLS — system-level table, service-role only. NO user-facing policies (D-25).
alter table public.entity_registry enable row level security;
-- Intentionally no SELECT/INSERT/UPDATE/DELETE policies. End users have ZERO
-- direct PostgREST access; backend uses get_supabase_client() (service-role)
-- for all reads and writes. See 02-CONTEXT.md D-25 / D-26.

comment on table public.entity_registry is
  'System-wide PII real↔surrogate registry per thread. RLS enabled — service-role only (no policies). See PRD-PII-Redaction-System-v1.1.md §4.FR-3.';
```

DO NOT add ANY `create policy` statements. The audit_logs migration adds a `super_admin` SELECT policy because there's a `/admin/audit` page; the entity_registry has NO such page in v1.0 (D-26 — admin UI is PRD §10 future work).

CLAUDE.md gotcha refresher: Once this file is committed, it is immutable per the PreToolUse hook. Get it right in this single write. NEVER edit applied migrations 001-028.
  </action>
  <verify>
    <automated>test -f supabase/migrations/029_pii_entity_registry.sql && grep -c "create table public.entity_registry" supabase/migrations/029_pii_entity_registry.sql | grep -q "^1$" && grep -q "unique (thread_id, real_value_lower)" supabase/migrations/029_pii_entity_registry.sql && grep -q "references public.threads(id) on delete cascade" supabase/migrations/029_pii_entity_registry.sql && grep -q "references public.messages(id) on delete set null" supabase/migrations/029_pii_entity_registry.sql && grep -q "alter table public.entity_registry enable row level security" supabase/migrations/029_pii_entity_registry.sql && ! grep -q "create policy" supabase/migrations/029_pii_entity_registry.sql && grep -q "handle_entity_registry_updated_at" supabase/migrations/029_pii_entity_registry.sql && grep -q "comment on table public.entity_registry" supabase/migrations/029_pii_entity_registry.sql && echo "ALL_CHECKS_PASS"</automated>
  </verify>
  <acceptance_criteria>
    - File `supabase/migrations/029_pii_entity_registry.sql` exists.
    - Contains exactly one `create table public.entity_registry` statement.
    - Contains literal `unique (thread_id, real_value_lower)` (D-23 composite unique).
    - Contains `references public.threads(id) on delete cascade` for thread_id FK.
    - Contains `references public.messages(id) on delete set null` for source_message_id FK (NOT cascade).
    - Contains `alter table public.entity_registry enable row level security`.
    - Contains ZERO `create policy` lines (grep returns no match).
    - Contains `create trigger handle_entity_registry_updated_at` wired to `public.handle_updated_at()`.
    - Contains `create index idx_entity_registry_thread_id`.
    - Contains a `comment on table public.entity_registry is '...'` line annotating the RLS posture.
    - Header comment references `PRD-PII-Redaction-System-v1.1.md §4.FR-3` and `02-CONTEXT.md D-21..D-26`.
  </acceptance_criteria>
  <done>The SQL file exists, has all required clauses, has zero RLS policies, and is ready for `supabase db push` (Wave 2). The file is NOT executed yet — it is only written to disk and committed.</done>
</task>

</tasks>

<verification>
After this plan completes:
- `git status` shows `supabase/migrations/029_pii_entity_registry.sql` as a new file.
- The verify automated command above returns `ALL_CHECKS_PASS`.
- File is under 80 lines (sanity bound — this is a small migration).
- Wave 2's `supabase db push` task can now run; it depends only on this file existing on disk.
</verification>

<success_criteria>
- Migration file exists at the exact path `supabase/migrations/029_pii_entity_registry.sql`.
- All D-22 columns present with correct types.
- D-23 composite UNIQUE constraint present.
- D-25 RLS enabled with no user-facing policies.
- D-26 honored — no HTTP route changes, no policy that would expose to PostgREST.
- handle_updated_at trigger wired correctly.
- File is well-formed SQL (parseable by Postgres — Wave 2's `supabase db push` will be the runtime verification).
</success_criteria>

<output>
Create `.planning/phases/02-conversation-scoped-registry-and-round-trip/02-01-SUMMARY.md` with:
- Migration file path written
- All 8 columns confirmed present
- RLS posture (enabled, no policies)
- Note: schema not yet pushed — Wave 2 plan handles that.
</output>
