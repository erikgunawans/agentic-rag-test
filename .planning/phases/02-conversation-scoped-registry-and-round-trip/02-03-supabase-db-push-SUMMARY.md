---
phase: 02-conversation-scoped-registry-and-round-trip
plan: 03
status: complete
completed: 2026-04-26
---

# Plan 02-03: supabase db push — SUMMARY

## What shipped

Migration `029_pii_entity_registry` applied to live Supabase project `qedhulpfezucnfadlfiz`. Wave 3 (registry DB methods) and Wave 5 (real-DB integration tests) are now unblocked.

## Execution path (deviation from plan)

The plan assumed the local `supabase` CLI would be available. It is not installed on this machine. With user approval, the migration was applied via the Supabase MCP `apply_migration` tool instead. Functionally identical: the migration is recorded in Supabase's server-side migration history, the schema is live, and downstream plans can hit `public.entity_registry` immediately.

The local migration file (`supabase/migrations/029_pii_entity_registry.sql`) remains the canonical, version-controlled source of truth. Future devs running `supabase db push` from a clean checkout will see "no migrations to apply" because the table already exists — this is expected and matches how the rest of the codebase manages migrations applied through similar paths.

## Verification (live Supabase, post-apply)

```sql
-- Result: rls_enabled=true, policy_count=0, column_count=9,
--         unique_constraint_count=1, fk_count=2, trigger_count=1
select
  (select relrowsecurity from pg_class where oid = 'public.entity_registry'::regclass) as rls_enabled,
  (select count(*) from pg_policies where schemaname='public' and tablename='entity_registry') as policy_count,
  (select count(*) from information_schema.columns where table_schema='public' and table_name='entity_registry') as column_count,
  (select count(*) from information_schema.table_constraints
     where table_schema='public' and table_name='entity_registry' and constraint_type='UNIQUE') as unique_constraint_count,
  (select count(*) from information_schema.table_constraints
     where table_schema='public' and table_name='entity_registry' and constraint_type='FOREIGN KEY') as fk_count,
  (select count(*) from pg_trigger
     where tgrelid='public.entity_registry'::regclass and tgname='handle_entity_registry_updated_at') as trigger_count;
```

Constraint definitions confirmed:

- `entity_registry_pkey`: PRIMARY KEY (id)
- `entity_registry_thread_id_real_value_lower_key`: UNIQUE (thread_id, real_value_lower) — D-23
- `entity_registry_thread_id_fkey`: FOREIGN KEY (thread_id) REFERENCES threads(id) ON DELETE CASCADE — D-22
- `entity_registry_source_message_id_fkey`: FOREIGN KEY (source_message_id) REFERENCES messages(id) ON DELETE SET NULL — D-22

## Must-haves status

| Must-have | Status |
|-----------|--------|
| Migration 029 applied to live DB | ✓ |
| `public.entity_registry` exists | ✓ |
| RLS enabled, no policies (D-25) | ✓ (relrowsecurity=true, policy_count=0) |
| Composite UNIQUE (thread_id, real_value_lower) queryable | ✓ |
| Trigger `handle_entity_registry_updated_at` wired | ✓ |
| FK actions: thread_id CASCADE, source_message_id SET NULL | ✓ |

## Self-Check: PASSED

All 4 plan-level acceptance criteria pass against the live database. No deviations from the schema defined in plan 02-01.

## Next gate

Wave 3 / Plan 02-04 (`ConversationRegistry.load` + `upsert_delta` against the live table) can proceed.
