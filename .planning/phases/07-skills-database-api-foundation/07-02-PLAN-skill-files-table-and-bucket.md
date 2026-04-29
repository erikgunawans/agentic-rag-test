---
id: 07-02
phase: 7
title: Migration 035 — skill_files table + skills-files storage bucket
wave: 2
depends_on: [07-01]
closes: []
estimated_atomic_commits: 1
---

# 07-02-PLAN — Migration 035: skill_files table + skills-files storage bucket

## Goal

Create the `public.skill_files` table (FK → `skills.id`, cascade delete) and a private Supabase Storage bucket `skills-files` with two RLS policies that gate access by path prefix. This is the foundation for SFILE-* requirements (Phase 8+) and the per-skill file payload that 07-04's export endpoint streams out.

## Closes

- None directly. Foundation for SFILE-* (Phase 8+).

## Files to create

- `supabase/migrations/035_skill_files_table_and_bucket.sql` — at the **repo root**.

## Schema (D-P7-09)

```sql
CREATE TABLE public.skill_files (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  skill_id      UUID NOT NULL REFERENCES public.skills(id) ON DELETE CASCADE,
  filename      TEXT NOT NULL,
  size_bytes    BIGINT NOT NULL CHECK (size_bytes >= 0 AND size_bytes <= 10485760),  -- 10 MB cap (D-P7-08)
  mime_type     TEXT,
  storage_path  TEXT NOT NULL UNIQUE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by    UUID REFERENCES auth.users(id) ON DELETE SET NULL
);
CREATE INDEX idx_skill_files_skill_id ON public.skill_files(skill_id);
```

`storage_path` is globally unique because the bucket is single-tenanted from a path-prefix perspective; uniqueness prevents two rows pointing at the same blob.

## RLS (table policies)

`ALTER TABLE public.skill_files ENABLE ROW LEVEL SECURITY;`

- **SELECT** — `EXISTS (SELECT 1 FROM public.skills s WHERE s.id = skill_files.skill_id AND (s.user_id = auth.uid() OR s.user_id IS NULL))`
- **INSERT** — `EXISTS (SELECT 1 FROM public.skills s WHERE s.id = skill_files.skill_id AND s.user_id = auth.uid())` (own private skill files only — global skills are immutable to non-creators; if owner unshares + edits, they'll re-share later)
- **DELETE** — same predicate as INSERT
- **No UPDATE policy** — files are immutable (replace = delete + insert)

## Storage bucket (D-P7-07)

```sql
INSERT INTO storage.buckets (id, name, public)
VALUES ('skills-files', 'skills-files', false)
ON CONFLICT (id) DO NOTHING;
```

Plus 2 storage RLS policies on `storage.objects`:

1. **`skills-files SELECT`** — `bucket_id = 'skills-files' AND ((storage.foldername(name))[1] = auth.uid()::text OR (storage.foldername(name))[1] = '_system' OR EXISTS (SELECT 1 FROM public.skills s WHERE s.user_id IS NULL AND s.created_by::text = (storage.foldername(name))[1]))`
   - Allow: own folder, `_system` folder (seeded skills), or any global skill's creator folder.
2. **`skills-files INSERT/DELETE`** — `bucket_id = 'skills-files' AND (storage.foldername(name))[1] = auth.uid()::text` (own folder only — global skill files written via service-role escape hatch in router)

## Path scheme

`{owner_id}/{skill_id}/{filename}` where:
- `owner_id = user_id` for private skills,
- `owner_id = created_by` for shared (global) skills,
- `owner_id = '_system'` for the seed-time `skill-creator` skill (D-P7-07).

The router (07-04) computes the prefix; storage RLS enforces it.

## Verification (executor must run before commit)

1. **Local apply**: `supabase migration up`.
2. **Schema check**: `\d public.skill_files` shows all 8 columns, FK to skills, the index.
3. **Bucket check**: `SELECT * FROM storage.buckets WHERE id = 'skills-files'` returns one row with `public = false`.
4. **RLS positive smoke**: as test@test.com, upload a file at `<my_uid>/<skill_id>/test.md` — succeeds.
5. **RLS negative smoke**: as test-2@test.com, attempt SELECT on `<test_uid>/<skill_id>/test.md` — denied (403).
6. **Cascade smoke**: delete a skill row → corresponding `skill_files` rows are gone (FK cascade fires).

## Atomic commit

```
feat(skills): migration 035 — skill_files table + skills-files storage bucket
```

## Risks / open verifications

- **Storage RLS path-prefix syntax must be verified before writing the migration.** Run `grep -rn "storage.foldername" supabase/migrations/` to find a precedent in this repo. If none exists, write a minimal probe migration locally first or consult Supabase docs (`mcp__claude_ai_Supabase__search_docs query="storage.foldername path-prefix RLS"`).
- The "global skill creator folder" branch in the SELECT policy is the riskiest construct here — reviewers should challenge whether a simpler scheme (always read globals through the service-role API only) is cleaner. If accepted, document in 07-04 that all global-skill file reads MUST route through the router's service-role client and never expose direct storage signed URLs to clients.
- The 10 MB cap in the CHECK constraint is duplicated in `skill_zip_service.parse_skill_zip(max_per_file=...)` (07-03) — keep both in sync if the cap ever changes.
