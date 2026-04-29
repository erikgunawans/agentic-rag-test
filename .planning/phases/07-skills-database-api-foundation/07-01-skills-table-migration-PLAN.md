---
id: 07-01
phase: 7
title: Migration 034 — skills table + RLS + seed skill-creator
wave: 1
depends_on: []
closes: [SKILL-10]
estimated_atomic_commits: 1
---

# 07-01-PLAN — Migration 034: skills table + RLS + seed skill-creator

## Goal

Create the `public.skills` table with the composite-ownership model (`user_id` for ownership, `created_by` for immutable provenance), the four RLS policies that gate it, and a deterministic system seed for the `skill-creator` skill that ships with v1.1. All in a single transactional migration.

## Closes

- **SKILL-10** — System ships with a `skill-creator` skill seeded at migration time (REQUIREMENTS.md).

## Files to create

- `supabase/migrations/034_skills_table_and_seed.sql` — at the **repo root**, NOT `backend/supabase/migrations/`. Current head is `033_web_search_toggle.sql`; 034 is the next free number.

## Schema (D-P7-01, D-P7-09 alignment)

```sql
CREATE TABLE public.skills (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       UUID REFERENCES auth.users(id) ON DELETE CASCADE,  -- NULL = global
  created_by    UUID REFERENCES auth.users(id) ON DELETE SET NULL, -- NULL = system seed
  name          TEXT NOT NULL,
  description   TEXT NOT NULL,
  instructions  TEXT NOT NULL,
  enabled       BOOLEAN NOT NULL DEFAULT true,
  metadata      JSONB NOT NULL DEFAULT '{}'::jsonb,   -- license, compatibility, freeform
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX idx_skills_user_name        ON public.skills (user_id, lower(name)) WHERE user_id IS NOT NULL;
CREATE UNIQUE INDEX idx_skills_global_name      ON public.skills (lower(name))          WHERE user_id IS NULL;
CREATE INDEX        idx_skills_created_by       ON public.skills (created_by);
```

Add an `updated_at` trigger reusing the existing `public.handle_updated_at()` function defined in migration 001 (verified used by migrations 002, 003, 013, 014, 015, 024, 025 — `grep -rn "handle_updated_at" supabase/migrations/`).

```sql
CREATE TRIGGER skills_handle_updated_at
  BEFORE UPDATE ON public.skills
  FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();
```

## RLS policies (D-P7-05)

`ALTER TABLE public.skills ENABLE ROW LEVEL SECURITY;`

1. **SELECT** — `user_id = auth.uid() OR user_id IS NULL` (own + global)
2. **INSERT** — `created_by = auth.uid() AND user_id = auth.uid()` (caller can only create as themselves; no inserting global rows from the API — those come from migrations only)
3. **UPDATE (general)** — `user_id = auth.uid()` (cannot edit global rows; the share/unshare flow is a service-role escape hatch documented in 07-04)
4. **DELETE** — `(user_id = auth.uid() AND created_by = auth.uid()) OR (auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin'` — the row must be **private and owned** by the caller, OR the caller is super_admin. Creators cannot DELETE a globally-shared skill directly: they must first PATCH `/skills/{id}/share {global: false}` to bring the row back into their private namespace. Only super_admin deletes globals directly (admin moderation per D-P7-04). Addresses cycle-1 review MEDIUM: "DELETE semantics inconsistent". The product requirement (REQ SKILL-05) says "User can delete their own private skills" — this RLS now enforces that literally.

## Seed (D-P7-10, D-P7-11)

Single idempotent INSERT for the `skill-creator` skill:

```sql
INSERT INTO public.skills (id, user_id, created_by, name, description, instructions, enabled)
VALUES (
  '00000000-0000-0000-0000-000000000007',  -- deterministic UUID literal (phase 7)
  NULL,                                     -- global
  NULL,                                     -- system seed
  'skill-creator',
  'Helps users author new agent skills following the v1.1 SKILL.md format.',
  $skill_creator_body$
... full instructions heredoc, covering:
  - name regex and 64-char cap
  - description guidance (what / when triggered)
  - conciseness rule (< 500 lines preferred)
  - three legal-domain examples: reviewing-nda-clauses, summarizing-board-decisions, extracting-payment-terms
  - explicit "call save_skill when ready" closing paragraph
$skill_creator_body$,
  true
)
ON CONFLICT (id) DO NOTHING;
```

Authoring the heredoc body is part of this plan's atomic execution — the executor copies the bullet list above into prose paragraphs before applying.

## Verification (executor must run before commit)

1. **Local apply**: `supabase migration up` (or `mcp__claude_ai_Supabase__apply_migration` against the `qedhulpfezucnfadlfiz` dev branch).
2. **Schema check**: `psql -c "\d public.skills"` shows all 9 columns + the 3 indexes + RLS enabled.
3. **Seed check**: `SELECT id, name, user_id, created_by FROM public.skills WHERE name = 'skill-creator'` returns exactly 1 row with `user_id IS NULL`, `created_by IS NULL`, and `id = '00000000-0000-0000-0000-000000000007'`.
4. **Idempotency**: re-applying the migration returns no error and creates no duplicate.
5. **RLS smoke**: as test@test.com (non-admin), `SELECT * FROM public.skills` returns the seed row only (until they create their own).

## Atomic commit

```
feat(skills): migration 034 — skills table, RLS, seed skill-creator (SKILL-10)
```

## Risks / open verifications

- `public.handle_updated_at()` confirmed present (used in 7 prior migrations); no fallback needed.
- Deterministic UUID `0000...0007` collides only if a test fixture uses the same literal. None known; rerun `grep -r "00000000-0000-0000-0000-000000000007"` before writing.
- The `auth.jwt()` JSONB selector for `super_admin` matches the project pattern in CLAUDE.md ("RLS admin pattern"). Re-confirm against `028_global_folders.sql` if present, else against `migration 014` (RBAC settings).
