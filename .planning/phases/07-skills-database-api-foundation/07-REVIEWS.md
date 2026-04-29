---
phase: 7
reviewers: [codex]
reviewed_at: 2026-04-29T17:08:00+07:00
plans_reviewed:
  - 07-01-skills-table-migration-PLAN.md
  - 07-02-skill-files-table-and-bucket-PLAN.md
  - 07-03-skill-zip-service-PLAN.md
  - 07-04-skills-router-PLAN.md
  - 07-05-skills-api-tests-PLAN.md
cycle: 1
---

# Cross-AI Plan Review — Phase 7

## Codex Review (cycle 1)

1. **Summary** — The plan set is directionally complete and the wave order is mostly sound: 07-01 and 07-03 can run in parallel, 07-02 depends on 07-01, 07-04 correctly depends on all backend foundations, and 07-05 is the right final gate. It intends to close all 9 Phase 7 requirements, but I would not execute it unchanged: storage RLS, service-role export/import boundaries, ZIP result semantics, and one router query bug are serious enough to block safe delivery.

2. **Strengths**
   - Clear phase boundary: LLM tool wiring, UI, and sandbox work are correctly deferred.
   - `user_id` + `created_by` ownership model is a good fit for share/unshare semantics.
   - Plans reuse existing router, audit, auth, and migration patterns instead of inventing a new stack.
   - ZIP parser plan includes the right security themes: `safe_load`, path traversal defense, uncompressed-size ZIP-bomb check.
   - 07-05 covers the main happy paths and several important RLS/share/import failures.
   - `get_current_user` does already return `role`, and `log_action` supports `details`, so those router assumptions are valid.

3. **Concerns**
   - **HIGH**: 07-02 storage SELECT policy is overbroad. Checking only the first path segment means if user A has any global skill, all objects under `A/{skill_id}/...` can become readable, including private skill files.
   - **HIGH**: 07-04 export uses service-role storage downloads based on `skill_files.storage_path`, but 07-02 table RLS does not constrain `storage_path` to `{auth.uid()}/{skill_id}/...`. A malicious direct Supabase insert could point an owned skill file row at another object and leak it through export.
   - **HIGH**: `GET /skills` orders by `is_global`, but `skills` has no `is_global` column. `is_global` is only a computed response field, so the list endpoint will fail unless the DB schema or query changes.
   - **HIGH**: 07-03 ZIP export omits the opening frontmatter delimiter. It should write `---\n` + YAML + `---\n` + instructions; otherwise EXPORT-01 compatibility is broken.
   - **HIGH**: 07-03 uses `ParsedSkill.error` for oversized-file warnings, while 07-04 treats any `ParsedSkill.error` as a failed skill. That contradicts D-P7-08, where the skill should be created and only the oversized file skipped.
   - **HIGH**: 07-04 reads the full uploaded ZIP before enforcing the 50 MB cap. The uncompressed-sum check helps against ZIP bombs after read, but it does not protect the API from oversized request bodies.
   - **MEDIUM**: Share/unshare conflict handling is missing. Sharing can violate the global-name unique index; unsharing can violate the user-name unique index if the creator made another private skill with the same name.
   - **MEDIUM**: DELETE semantics are inconsistent. The requirement says users delete their own private skills, but the proposed RLS allows creators to delete global shared skills directly.
   - **MEDIUM**: 07-01 references `update_updated_at_column()`, but this repo uses `public.handle_updated_at()`. The plan has a fallback note, but the correct fix is to reuse the existing function.
   - **MEDIUM**: 07-04's service-role prefetch wording risks private skill existence disclosure. RLS fetch should be used first; service-role should only perform the share update after visibility and creator checks.
   - **MEDIUM**: EXPORT-03 is mislabeled in 07-04/07-05 as admin moderation. EXPORT-03 is import validation with per-skill errors; the tests partially cover it, but the closure mapping is wrong.
   - **MEDIUM**: 07-05's export-with-file test needs a concrete setup path, since Phase 7 has no standalone file-upload endpoint. It should create files through import or controlled DB/storage fixtures.
   - **LOW**: 07-03 calls itself pure stdlib while adding PyYAML. The dependency is reasonable, but the plan wording should be corrected.

4. **Suggestions**
   - Tighten storage RLS to validate both path owner and skill id: first segment owner, second segment `skill_id`, and an `EXISTS` check against the matching `skills.id`.
   - Add table RLS `WITH CHECK` for `skill_files.storage_path` prefix and `created_by = auth.uid()`, and make export revalidate `storage_path` before service-role download.
   - Avoid service-role for import storage uploads unless truly necessary; use the authed client with strict bucket policy for normal user-owned imports.
   - Fix `GET /skills` ordering by adding a generated `is_global` column, sorting in Python, or ordering by `user_id` with NULLs first if supported by the Supabase client.
   - Split ZIP parser outcomes into fatal skill errors and non-fatal file warnings/skips; extend import response with `skipped_files` or warnings so created skills can report skipped attachments.
   - Enforce upload size before or during read using `Content-Length` plus chunked reads into a capped buffer.
   - Add tests for storage-path spoofing, global-skill private-file leakage, share/unshare name conflicts, malformed YAML, missing description, path traversal, and oversized compressed uploads.
   - Reuse `public.handle_updated_at()` in migration 034.
   - Align DELETE policy with the intended product rule: either require unshare before non-admin delete, or explicitly document that creators may delete shared globals.

5. **Risk Assessment** — HIGH: the plan is complete in scope, but the current RLS/storage/service-role design can leak files, and several implementation details would fail core export/list/import behavior.

RISK_LEVEL: HIGH

---

## Cycle 1 Tally

CYCLE_SUMMARY: current_high=6

### Current HIGH Concerns (cycle 1)

1. Storage RLS first-segment-only policy leaks private files when owner has any global skill (affects 07-02 + 07-04 export).
2. `skill_files.storage_path` is not constrained to `{owner}/{skill_id}/...`; row spoofing → service-role export leak (affects 07-02 + 07-04).
3. `GET /skills` orders by non-existent `is_global` column (affects 07-04 list endpoint — runtime failure).
4. ZIP build emits invalid SKILL.md (missing leading `---\n` delimiter, breaks EXPORT-01 compatibility) (affects 07-03).
5. Oversized-file semantics contradict D-P7-08 (07-03 vs 07-04 disagree on whether skill is created when one file is too big) (affects 07-03 + 07-04 + 07-05 test 13).
6. Upload-body 50 MB cap is enforced post-read; oversized HTTP body is fully buffered before rejection (affects 07-04 import endpoint).

### Consensus Summary

Single reviewer (codex) — no cross-CLI consensus to compute. Concerns above are codex's verdict only.
