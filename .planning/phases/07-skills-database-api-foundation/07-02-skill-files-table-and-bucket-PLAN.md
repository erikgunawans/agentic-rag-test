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
  created_by    UUID REFERENCES auth.users(id) ON DELETE SET NULL,
  -- Cycle-1 review HIGH #2: bind storage_path to (owner, skill_id) so a malicious
  -- direct insert can't point a row at someone else's object. The constraint splits
  -- on '/'; first segment must be the owner-folder, second must be the skill_id.
  CONSTRAINT skill_files_storage_path_shape CHECK (
    storage_path ~ '^[a-zA-Z0-9_-]+/[0-9a-fA-F-]{36}/[^/]+$'
  ),
  CONSTRAINT skill_files_storage_path_skill_match CHECK (
    split_part(storage_path, '/', 2) = skill_id::text
  )
);
CREATE INDEX idx_skill_files_skill_id ON public.skill_files(skill_id);
```

`storage_path` is globally unique because the bucket is single-tenanted from a path-prefix perspective; uniqueness prevents two rows pointing at the same blob. The two CHECK constraints additionally bind the path's structure: `{owner}/{skill_id}/{filename}` where `skill_id` MUST equal the row's `skill_id` column. This blocks the cycle-1 HIGH #2 attack of pointing a fabricated row at another skill's blob.

## RLS (table policies)

`ALTER TABLE public.skill_files ENABLE ROW LEVEL SECURITY;`

- **SELECT** — `EXISTS (SELECT 1 FROM public.skills s WHERE s.id = skill_files.skill_id AND (s.user_id = auth.uid() OR s.user_id IS NULL))` (visible if the parent skill is visible)
- **INSERT** — `EXISTS (SELECT 1 FROM public.skills s WHERE s.id = skill_files.skill_id AND s.user_id = auth.uid()) AND created_by = auth.uid() AND split_part(storage_path, '/', 1) = auth.uid()::text` — additionally constrains `created_by` to caller and the path's first segment to caller's UID. This addresses cycle-1 HIGH #2: a row's `storage_path` cannot be inserted with someone else's owner-folder, even if the parent-skill check passes.
- **DELETE** — `EXISTS (SELECT 1 FROM public.skills s WHERE s.id = skill_files.skill_id AND s.user_id = auth.uid()) AND created_by = auth.uid()` (own files on private skills only)
- **No UPDATE policy** — files are immutable (replace = delete + insert)

## Storage bucket (D-P7-07)

```sql
INSERT INTO storage.buckets (id, name, public)
VALUES ('skills-files', 'skills-files', false)
ON CONFLICT (id) DO NOTHING;
```

Plus 2 storage RLS policies on `storage.objects`. **Cycle-1 review HIGH #1 fix:** the SELECT policy is now joined to `skill_files` by exact `storage_path`, not just first-segment matching, so it cannot leak unrelated objects under the same owner folder.

1. **`skills-files SELECT`** — visibility is delegated to `skill_files` table RLS via an EXISTS join on the full path:
   ```sql
   bucket_id = 'skills-files'
   AND EXISTS (
     SELECT 1
     FROM public.skill_files sf
     JOIN public.skills s ON s.id = sf.skill_id
     WHERE sf.storage_path = storage.objects.name
       AND (s.user_id = auth.uid() OR s.user_id IS NULL)
   )
   ```
   This means an object is readable iff there is a `skill_files` row pointing at it AND the parent skill is visible to the caller. No first-segment-only heuristic. Private files of users with global skills are NOT exposed.
2. **`skills-files INSERT`** (separate `FOR INSERT WITH CHECK` policy) — caller's UID matches first segment AND there exists a **private** parent skill they own with id matching the second segment. Cycle-2 review NEW-H1 fix: parent-privacy join blocks creators from mutating their globally-shared skill's files directly via Storage.
   ```sql
   bucket_id = 'skills-files'
   AND (storage.foldername(name))[1] = auth.uid()::text
   AND (storage.foldername(name))[2] ~ '^[0-9a-fA-F-]{36}$'
   AND EXISTS (
     SELECT 1 FROM public.skills s
     WHERE s.id::text = (storage.foldername(name))[2]
       AND s.created_by = auth.uid()
       AND s.user_id    = auth.uid()   -- parent must be PRIVATE; creator must unshare to edit
   )
   ```
3. **`skills-files DELETE`** (separate `FOR DELETE USING` policy) — same predicate as INSERT. After this policy, a creator who has shared their skill cannot delete its blobs through Storage; they must `PATCH /skills/{id}/share {global: false}` first. Mirrors the table-level skills DELETE policy.

Service-role escapes in 07-04 are only used for the `_system` seed folder (created at migration time, never modified at runtime).

**Cycle-2 review LOW fix**: policies are now expressed as the precise Postgres forms (`CREATE POLICY ... FOR INSERT WITH CHECK (...)`, `CREATE POLICY ... FOR DELETE USING (...)`), not the loose "INSERT/DELETE" combined wording.

## Path scheme

`{owner_id}/{skill_id}/{filename}` where:
- `owner_id = user_id` for private skills,
- `owner_id = created_by` for shared (global) skills,
- `owner_id = '_system'` for the seed-time `skill-creator` skill (D-P7-07).

The router (07-04) computes the prefix; storage RLS enforces it.

## Verification (executor must run before commit)

1. **Local apply**: `supabase migration up`.
2. **Schema check**: `\d public.skill_files` shows all 8 columns + the 2 CHECK constraints, FK to skills, the index.
3. **CHECK constraint smoke**: try to INSERT a `skill_files` row with `storage_path = '<my_uid>/<wrong_skill_id>/test.md'` (skill_id mismatch) — fails with check constraint violation. Same for `storage_path = 'malformed-only-one-segment'` — fails the regex CHECK.
4. **Bucket check**: `SELECT * FROM storage.buckets WHERE id = 'skills-files'` returns one row with `public = false`.
5. **RLS positive smoke**: as test@test.com, upload a file at `<my_uid>/<skill_id>/test.md` and INSERT matching `skill_files` row — succeeds.
6. **RLS negative smoke (HIGH #1 regression)**: as test-2@test.com, while test@test.com has a global skill `g1`, try to SELECT a private file under test@test.com's owner folder `<test_uid>/<other_private_skill_id>/secret.md` — denied (no `skill_files` row + parent-skill match exists for test-2).
7. **Storage-path spoofing (HIGH #2 regression)**: as test@test.com, INSERT `skill_files` row whose `storage_path` points at test-2's blob — fails the CHECK + INSERT RLS.
8. **Cascade smoke**: delete a skill row → corresponding `skill_files` rows are gone (FK cascade fires).

## Atomic commit

```
feat(skills): migration 035 — skill_files table + skills-files storage bucket
```

## Risks / open verifications

- **Storage RLS syntax must be verified before writing the migration.** Run `grep -rn "storage.foldername\|storage.buckets" supabase/migrations/` to find a precedent in this repo. If none exists, write a minimal probe migration locally first or consult Supabase docs (`mcp__claude_ai_Supabase__search_docs query="storage RLS exists join"`). The new EXISTS-join policy is more conservative than first-segment matching and should be the safe default.
- **Service-role policy for `_system` skill files**: the SELECT policy above does not include the `_system` folder in its first-segment heuristic anymore. For the `skill-creator` seed (which has `user_id IS NULL`), the EXISTS join still resolves because the parent skill is global. So no special-casing is required — but do verify with a positive smoke test on the seed file before commit.
- The 10 MB cap in the CHECK constraint is duplicated in `skill_zip_service.parse_skill_zip(max_per_file=...)` (07-03) — keep both in sync if the cap ever changes.
- **`split_part` and regex are Postgres-native** (no extension required) — but confirm the regex in the CHECK matches Supabase's UUID format (lowercase hex with dashes; current regex is case-insensitive `[0-9a-fA-F-]{36}`).
