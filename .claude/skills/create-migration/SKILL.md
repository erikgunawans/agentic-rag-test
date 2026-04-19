---
name: create-migration
description: Generate a new numbered Supabase migration with RLS template and correct sequencing
---

# /create-migration — Generate a Supabase Migration

Create a new migration file in `supabase/migrations/` with the correct sequence number and standard boilerplate.

## Usage
`/create-migration <name>` — e.g., `/create-migration add_notifications_table`

## Steps

### 1. Detect next migration number

```bash
ls supabase/migrations/*.sql 2>/dev/null | sort | tail -1 | grep -oE '[0-9]+' | head -1
```

Parse the highest number and increment by 1. Zero-pad to 3 digits.

### 2. Create migration file

Write to `supabase/migrations/{NNN}_{name}.sql` with this template:

```sql
-- ============================================================
-- Migration {NNN}: {name (human-readable)}
-- {one-line description from user or inferred from name}
-- ============================================================

-- Tables
-- CREATE TABLE IF NOT EXISTS public.{table_name} (
--   id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
--   user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
--   created_at timestamptz NOT NULL DEFAULT now(),
--   updated_at timestamptz NOT NULL DEFAULT now()
-- );

-- Indexes
-- CREATE INDEX idx_{table}_user ON public.{table}(user_id);

-- RLS (REQUIRED for all new tables)
-- ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "{table}_user_isolation" ON public.{table}
--   FOR ALL USING (auth.uid() = user_id);
-- CREATE POLICY "{table}_admin_access" ON public.{table}
--   FOR ALL USING ((auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin');

-- Triggers
-- CREATE TRIGGER set_{table}_updated_at
--   BEFORE UPDATE ON public.{table}
--   FOR EACH ROW EXECUTE FUNCTION moddatetime(updated_at);
```

### 3. Remind

Output:
```
Created: supabase/migrations/{NNN}_{name}.sql

Reminders:
- All tables MUST have RLS enabled
- Users only see their own data (auth.uid() = user_id)
- Admin access: (auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin'
- Global/shared data uses is_global = true pattern
- Apply with: Supabase MCP apply_migration tool
- After applying, update the PreToolUse hook range in .claude/settings.json
```
