---
id: 07-05
phase: 7
title: API integration tests for Phase 7
wave: 4
depends_on: [07-04]
closes: [SKILL-01, SKILL-03, SKILL-04, SKILL-05, SKILL-06, SKILL-10, EXPORT-01, EXPORT-02, EXPORT-03]
estimated_atomic_commits: 1
---

# 07-05-PLAN — `tests/api/test_skills.py` (integration tests)

## Goal

Twenty-three integration tests that exercise every Phase 7 endpoint against a live backend, verifying RLS (including cycle-1 review HIGH #1/#2 + cycle-2 NEW-H1 regressions), share/unshare semantics with name-conflict guards (incl. unique-violation race), ZIP round-trips with per-file warnings, error-only ParsedSkill construction, and admin moderation. This is the verification gate for ALL nine of Phase 7's requirements; convergence on this plan means Phase 7 is done.

## Closes

Verifies all 9 Phase 7 requirements: SKILL-01, 03, 04, 05, 06, 10 + EXPORT-01, 02, 03.

## Files to create

- `backend/tests/api/test_skills.py`

## Fixtures reused (from `backend/tests/api/conftest.py`)

- `auth_token` — `test@test.com` (super_admin per CLAUDE.md)
- `auth_token_2` — `test-2@test.com` (non-admin)
- `admin_token` — same user as `auth_token` but explicitly typed for moderation tests; if absent in `conftest.py`, alias to `auth_token` and document.

If any fixture is missing, fall back to inline login helpers using the credentials from CLAUDE.md `## Testing` block.

## Test cases (20)

### Core CRUD + share + admin (1–9)

1. **`test_seed_skill_creator_exists`** — `GET /skills` as any authed user returns a row with `name == "skill-creator"`, `is_global is True`, `created_by is None`. Closes SKILL-10.
2. **`test_create_read_update_delete_cycle`** — POST creates → 201 with returned `id`; GET returns the row; PATCH `name` → 200 with new name; DELETE → 204; GET → 404. Closes SKILL-01, 03, 04, 05.
3. **`test_create_invalid_name_422`** — POST with `name="Bad Name"` → 422 (Pydantic). Try other invalids: empty, leading digit, consecutive dashes, > 64 chars. SKILL-01 negative.
4. **`test_create_duplicate_name_409`** — same user POSTs `legal-review` twice → second call returns 409 with `"Skill name already exists"`.
5. **`test_global_skill_visible_to_other_user`** — user A creates + shares (PATCH share global=true); user B GETs and sees it in their list. SKILL-06 positive.
6. **`test_share_unshare_roundtrip`** — A shares (200, `is_global=true`); B GETs → visible; A unshares (200, `is_global=false`); B GETs → 404 on direct fetch and absent from list. SKILL-06 round-trip.
7. **`test_share_only_creator_403`** — A creates + shares; B tries `PATCH /skills/{id}/share {global: false}` → 403 with `"Only the creator can change sharing"` (or equivalent).
8. **`test_edit_global_skill_403`** — A creates and shares; A tries `PATCH /skills/{id} {name: "x"}` → 403 with the exact `"Cannot edit a global skill — unshare it first"` detail string.
9. **`test_admin_can_delete_any_skill`** — A creates a private skill; admin (super_admin) DELETEs → 204; subsequent GET → 404. Closes admin moderation (D-P7-04). **Note (cycle-1 review fix)**: this test does NOT close EXPORT-03 — that is closed by tests 12 + 17 below.

### Cycle-1 review HIGH regressions (10–15)

10. **`test_export_returns_valid_zip_with_frontmatter_delimiter`** (HIGH #4) — Create skill + 1 file in `references/`; GET `/skills/{id}/export` → 200, `Content-Type: application/zip`, body parses via `parse_skill_zip` and yields a single `ParsedSkill`. Open the inner `SKILL.md` raw bytes and assert it starts with `b"---\n"`. Frontmatter `name`/`description` round-trip equal. Closes EXPORT-01.
11. **`test_list_skills_orders_globals_first`** (HIGH #3) — Create one private skill, share another (or rely on seed `skill-creator`); `GET /skills` → 200; assert all rows where `is_global is True` appear before any private rows in `data`. The endpoint must NOT crash with a "column is_global does not exist" error.
12. **`test_import_oversized_file_skipped_skill_still_created`** (HIGH #5 + EXPORT-03) — ZIP with one valid skill containing a `references/big.bin` file at 11 MB and a `references/ok.md` at 9 MB. POST → 200 with `created_count=1`, `error_count=0`; `results[0].status == "created"`; `results[0].skipped_files` contains exactly one entry with `relative_path="references/big.bin"` and `reason="oversized"`; the in-DB `skill_files` row count for the new skill is 1 (only ok.md). Asserts the new soft-skip semantics hold.
13. **`test_import_oversized_zip_413_pre_read`** (HIGH #6) — Send a multipart upload with `Content-Length: 60000000` (60 MB) but a tiny payload; expect 413 BEFORE the body is fully read (use httpx `event_hooks` or measure response time vs. body size to confirm short-circuit).
14. **`test_import_oversized_zip_413_post_read`** — Build a real 51 MB synthetic ZIP body; POST → 413 with `"ZIP exceeds 50 MB limit"` (this exercises the `parse_skill_zip` defense).
15. **`test_storage_path_spoofing_rejected`** (HIGH #2 + storage RLS HIGH #1) — As user A, attempt direct Supabase INSERT into `skill_files` with `storage_path = "<other_user_uid>/<some_skill_id>/secret.md"` (mismatched skill_id and/or wrong owner). Expect failure (CHECK constraint violation OR INSERT RLS denial). Then attempt cross-user storage read of a private file via the export endpoint of a global skill — confirm only the global skill's own files come back.

### Share/unshare conflict + cross-user RLS (16–18)

16. **`test_share_name_conflict_409`** (cycle-1 MEDIUM) — User A creates `legal-review` (private). User B creates `legal-review` (private). User A `PATCH share {global: true}` → 200 (no global with that name yet). User B `PATCH share {global: true}` → **409** with `"Skill name already exists"`. Validates the new step-3 conflict guard.
17. **`test_unshare_name_conflict_409`** (cycle-1 MEDIUM + EXPORT-03 partial) — User A creates `legal-review` (private), shares it (now global), then creates a second private `legal-review`. PATCH unshare on the first → **409** (would collide with their own private one). Validates the symmetric guard.
18. **`test_other_user_cannot_see_private_skill`** — User A creates a private skill; user B's `GET /skills` does NOT include it; user B's direct `GET /skills/{A_id}` → 404. RLS positive smoke.

### Open-standard import — bulk + per-skill error reporting (19–20, EXPORT-03)

19. **`test_import_single_skill_zip`** — Build a ZIP via `build_skill_zip` round-trip helper; POST as multipart `{"file": ("skill.zip", data, "application/zip")}` → 200 with `created_count=1`, `results[0].status="created"`, `skipped_files=[]`. Closes EXPORT-02 single.
20. **`test_import_bulk_zip_with_mixed_results`** (EXPORT-03 closure) — 3 skills in ZIP: one valid (`approving-clause-x`), one with bad name (`Bad Name`), one duplicate of an existing user-owned skill. Expect `created_count=1`, `error_count=2`, results indexed in order: valid → `status="created"`; bad-name → `status="error", error contains "Invalid name"`; duplicate → `status="error", error="Skill name already exists"`. Asserts that one error does NOT block the others (= EXPORT-03 verbatim). Closes EXPORT-02 bulk + EXPORT-03.

### Cycle-2 review regressions (21–23)

21. **`test_global_skill_creator_cannot_mutate_storage`** (NEW-H1) — User A creates a private skill `s1` and uploads `references/note.md`. A shares `s1` (now global). A then attempts (via raw Supabase Storage SDK with their own JWT) to DELETE `<A_uid>/<s1_id>/note.md` from the `skills-files` bucket — expect denial (storage RLS DELETE policy now requires `s.user_id = auth.uid()`, which is NULL for globals). A also attempts to UPLOAD a replacement at the same path — denied. Then A unshares `s1`; the same delete + upload now succeed. Validates the parent-private join in storage INSERT/DELETE policies.
22. **`test_parser_returns_error_only_skill_for_bad_yaml`** (NEW-H2) — Build a ZIP whose SKILL.md has malformed YAML frontmatter (e.g., `description: : :`). Invoke `parse_skill_zip` directly (this is a unit-test cross-over but is run via the API: POST `/skills/import` with such a ZIP → response includes `results[0].status="error"`, `error` contains "Malformed YAML"; the endpoint did NOT 500). Validates that ParsedSkill's optional success fields permit error-only construction.
23. **`test_share_unique_violation_race_returns_409`** (cycle-2 MEDIUM) — Two clients race: both PATCH `share {global: true}` on different private skills with the same name (between step-3 conflict-check and step-4 UPDATE). One wins with 200; the loser's UPDATE hits a unique violation and gets translated to 409 "Skill name already exists" (NOT 500). Note: easier to simulate with a fixture that monkeypatches the conflict-check to no-op so the race is forced; document this in the test docstring.

### Pre-body 413 — true ASGI cap (replacement for cycle-1 test 13)

Test 13 (`test_import_oversized_zip_413_pre_read`) is **upgraded** to assert the middleware's behavior: send a request with `Content-Length: 60000000` and a small actual body; expect 413 returned in < 200ms (no body parsing). The streaming-counter path (chunked transfer-encoding) is exercised in a sibling test if httpx supports it; otherwise document as Phase 8+ coverage.

## Run target

Per CLAUDE.md `## Code Quality`:

```bash
cd backend && source venv/bin/activate && \
  TEST_EMAIL="test@test.com" TEST_PASSWORD='!*-3-3?3uZ?b$v&' \
  TEST_EMAIL_2="test-2@test.com" TEST_PASSWORD_2='fK4$Wd?HGKmb#A2' \
  API_BASE_URL="http://localhost:8000" \
  pytest tests/api/test_skills.py -v --tb=short
```

For CI parity, the same command with `API_BASE_URL="https://api-production-cde1.up.railway.app"` runs against deployed backend after `railway up`.

## Verification (executor must do)

1. All 23 test cases pass against `http://localhost:8000` (backend running with migrations 034 + 035 applied).
2. `cd backend && source venv/bin/activate && python -c "from app.main import app; print('OK')"` still prints OK (no import-side breakage).
3. PostToolUse lint hook is green for `test_skills.py`.
4. Re-run all 23 against deployed backend after `railway up` — all pass (Phase 7 closure confirmation).

## Atomic commit

```
test(skills): API integration tests for Phase 7 (23 cases)
```

## Risks / open verifications

- **`test-2@test.com` super_admin status**: CLAUDE.md says only `test@test.com` is super_admin. Confirm `test-2@test.com` is NOT promoted before relying on it for the negative-RLS tests. If it is, demote with `python -m scripts.set_admin_role` before the test run.
- **Test 12's oversized-file surface is now decided**: 07-03's `ParsedSkill.skipped_files: list[SkippedFile]` channel surfaces oversized files; this test asserts that exact shape. If 07-03's API changes, 07-04 and this test must change in lockstep.
- **Test 13 (pre-read 413)**: confirming a 413 BEFORE the body is fully read requires the client to lie about Content-Length. The httpx + Starlette plumbing may surface this differently across versions; if the assertion is unreliable, fall back to asserting that the response time is < 500ms regardless of payload size (i.e., the server short-circuited).
- **Test 15 (storage spoofing)**: this test issues raw INSERTs against Supabase as a non-admin user. Use the user's authed Supabase client; expect either CHECK constraint violation or INSERT RLS denial. Either is acceptable evidence that HIGH #2 is mitigated.
- **Multipart `httpx` quirks**: bulk ZIP tests at 51 MB body may stress the test client's default timeout. Use `httpx.AsyncClient(timeout=60)` explicitly.
- **Test isolation**: each test that creates skills must clean up via DELETE in a fixture teardown OR use unique names per run (e.g., `f"legal-review-{uuid.uuid4().hex[:6]}"`); without isolation, repeated runs hit duplicate-name 409s.
