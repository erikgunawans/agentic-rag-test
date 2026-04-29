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

---

## Codex Review (cycle 2)

Reviewed at: 2026-04-29T17:20:00+07:00
Plans rev: post replan-cycle-1 (commit 7339c3e)

### Cycle-1 HIGH Status Table

| ID | Status | Evidence | Notes |
|---|---|---|---|
| H1 | FULLY RESOLVED | 07-02 lines 69–83; 07-05 line 54 | Storage SELECT no longer uses first-segment ownership alone; joins exact `storage_path` to `skill_files` and parent `skills` visibility. Regression coverage planned. |
| H2 | FULLY RESOLVED | 07-02 lines 37–57; 07-04 line 108; 07-05 line 54 | Direct row spoofing blocked by `storage_path` shape/skill checks plus INSERT RLS. Export also revalidates before service-role download. |
| H3 | FULLY RESOLVED | 07-04 line 103; 07-05 line 50 | Plan no longer orders by computed `is_global` field. Orders by `user_id NULLS FIRST, created_at DESC` and tests that listing does not crash. |
| H4 | FULLY RESOLVED | 07-03 line 76; 07-05 line 49 | ZIP export now explicitly emits leading `---\n`; unit and API regression tests assert it. |
| H5 | FULLY RESOLVED | 07-03 lines 43–57 and 87–99; 07-04 line 109; 07-05 line 51 | Oversized files now use `skipped_files`, not fatal `ParsedSkill.error`; created skill semantics match D-P7-08. |
| H6 | PARTIALLY RESOLVED | 07-04 lines 109 + 150; 07-05 lines 52 + 98 | Plan checks `Content-Length` before `await file.read()`, but FastAPI parses multipart `UploadFile` BEFORE endpoint code runs. Avoids one in-process bytes copy, but does not truly cap request-body ingestion. |

### New HIGH Concerns (cycle 2)

- **NEW-H1**: Storage INSERT/DELETE policy allows direct mutation of global skill files by the creator after sharing. The path scheme keeps shared files under `created_by`, while storage INSERT/DELETE only checks first path segment equals `auth.uid()`. A creator can delete or replace blobs for a global skill directly through Supabase Storage, bypassing the router's "cannot edit global skill" rule. Storage write/delete policy should join `skills` by the second path segment and require `s.user_id = auth.uid()` (parent must be private).

- **NEW-H2**: `ParsedSkill` Pydantic model cannot represent fatal parse errors as specified. The model requires `frontmatter: SkillFrontmatter`, `instructions_md: str`, and `files: list[ParsedSkillFile]` (no defaults), but the parser is supposed to return `ParsedSkill.error="..."` for missing delimiters, malformed YAML, and missing required fields. As written, instantiation fails before `.error` can be set. Fix: make those fields optional with defaults, OR split into success/error result models.

### New MEDIUM/LOW Concerns

- **MEDIUM**: `/skills/import` uses `request.headers`, but the planned imports/signature omit `Request` (07-04 lines 35–43, 109).
- **MEDIUM**: Share/unshare conflict checks are non-atomic; unique indexes protect data, but the service-role UPDATE must catch late unique violations and return 409 instead of 500 (07-04 line 107).
- **LOW**: Storage policy syntax is still left as an open verification. The "INSERT/DELETE" wording in 07-02 should be split into exact `FOR INSERT WITH CHECK` and `FOR DELETE USING` policy statements before execution.

### Risk Assessment

HIGH: most cycle-1 HIGHs are fixed, but the multipart size cap is still not an effective pre-body cap, and cycle 2 introduced a direct storage integrity bypass for global skill files.

RISK_LEVEL: HIGH

---

## Cycle 2 Tally

CYCLE_SUMMARY: current_high=3

### Current HIGH Concerns (cycle 2)

1. **H6 (carry-forward, partial)**: Pre-read 50 MB cap relies on FastAPI's `UploadFile` already having parsed the multipart body — the check fires after Starlette buffers the upload. Need an ASGI middleware OR raw-`Request` body streaming with early abort.
2. **NEW-H1**: Storage INSERT/DELETE policy lets a skill's creator mutate blobs of their now-globally-shared skill directly via Storage, bypassing router's "edit global → 403". Add parent-skill privacy check to write/delete policies.
3. **NEW-H2**: `ParsedSkill` required fields prevent constructing the error-only return shape the parser commits to. Make fields optional or split the model.

### Convergence Trend

prev_high=6 → current_high=3 (decreasing, no stall). Cycle 2 of 3 (max=3). One more replan cycle remaining before escalation.

---

## Codex Review (cycle 3, FINAL)

Reviewed at: 2026-04-29T17:36:00+07:00
Plans rev: post replan-cycle-2 (commit 583e5f1)

### Cycle-2 HIGH Status Table

| ID | Status | Evidence | Notes |
|---|---|---|---|
| H6 carry-forward | **PARTIALLY RESOLVED** | 07-04 lines 31, 34–77, 157, 198; 07-05 lines 52, 75, 108 | Plan now adds middleware before route handling and has a concrete `Content-Length` fast-path 413. However, the chunked/no-length path mutates private `request._receive`, returns `http.disconnect` instead of a 413 response, and the test plan makes chunked coverage optional. Line 198 still calls the pre-read defense "best-effort" and defers a hard streaming parser to Phase 8+. This closes the common header-present case, but not the original resource-exhaustion concern completely. |
| NEW-H1 storage write policy | **FULLY RESOLVED** | 07-02 lines 83–95; 07-05 line 69 | Storage INSERT/DELETE now require `s.created_by = auth.uid() AND s.user_id = auth.uid()`. Once shared, `user_id IS NULL`, so direct creator mutation through Storage is denied. Regression test 21 verifies delete + replacement upload denied while global, then allowed after unshare. |
| NEW-H2 ParsedSkill model | **FULLY RESOLVED** | 07-03 lines 52–63, 89–98; 07-05 line 70 | `ParsedSkill` can now represent error-only parse results because `frontmatter` is optional, `instructions_md` defaults to empty, and file lists default empty. The parser explicitly maps malformed YAML/missing fields/bad names to `ParsedSkill.error`; test 22 verifies the import endpoint returns per-skill error instead of 500. |

### New HIGH Concerns (cycle 3)

- None beyond H6 remaining partially resolved.

### Risk Assessment

HIGH: NEW-H1 and NEW-H2 are fixed, but H6 still leaves an upload-body exhaustion path insufficiently specified and insufficiently verified for chunked/no-`Content-Length` requests; reviewer suggests a pure ASGI middleware that wraps `receive` and emits 413 directly, or raw request streaming, before execution.

RISK_LEVEL: HIGH

---

## Cycle 3 Tally

CYCLE_SUMMARY: current_high=1

### Current HIGH Concerns (cycle 3)

1. **H6 (carry-forward, still partial after 2 replan cycles)**: Pre-body 50 MB cap closes the Content-Length fast path but the chunked/no-Content-Length path uses `request._receive` mutation returning `http.disconnect`, which is brittle. Chunked test coverage is marked optional. Reviewer-suggested fix: replace the receive-wrapping approach with a true ASGI middleware that emits an explicit 413 ASGI response when the streaming byte-count exceeds the cap.

### Convergence Trend (FINAL)

prev_high=3 → current_high=1 (decreasing, no stall).
Cycle 3 of 3 (max=3). **Escalation gate triggered** — workflow requires user decision: proceed with H6 partial, or stop here for manual review.

### Known Mitigation If Proceeding

If the user proceeds anyway, the practical risk of H6 partial is bounded:
- Common case (browser uploads, curl) sends Content-Length and is short-circuited by the fast path → 413 before any body read.
- Chunked uploads without Content-Length are rare at the API edge (most clients buffer and set CL). Even if they slip through, the post-read `parse_skill_zip` ValueError catches them at < 100 ms after read completes — a DoS amplification, not a leak or correctness bug.
- Phase 8+ can ship the proper streaming-aware ASGI middleware as part of code-execution sandbox hardening (similar concern there).
