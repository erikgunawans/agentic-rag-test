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

Fourteen integration tests that exercise every Phase 7 endpoint against a live backend, verifying RLS, share/unshare semantics, ZIP round-trips, and admin moderation. This is the verification gate for ALL nine of Phase 7's requirements; convergence on this plan means Phase 7 is done.

## Closes

Verifies all 9 Phase 7 requirements: SKILL-01, 03, 04, 05, 06, 10 + EXPORT-01, 02, 03.

## Files to create

- `backend/tests/api/test_skills.py`

## Fixtures reused (from `backend/tests/api/conftest.py`)

- `auth_token` — `test@test.com` (super_admin per CLAUDE.md)
- `auth_token_2` — `test-2@test.com` (non-admin)
- `admin_token` — same user as `auth_token` but explicitly typed for moderation tests; if absent in `conftest.py`, alias to `auth_token` and document.

If any fixture is missing, fall back to inline login helpers using the credentials from CLAUDE.md `## Testing` block.

## Test cases (14)

1. **`test_seed_skill_creator_exists`** — `GET /skills` as any authed user returns a row with `name == "skill-creator"`, `is_global is True`, `created_by is None`. Closes SKILL-10.
2. **`test_create_read_update_delete_cycle`** — POST creates → 201 with returned `id`; GET returns the row; PATCH `name` → 200 with new name; DELETE → 204; GET → 404. Closes SKILL-01, 03, 04, 05.
3. **`test_create_invalid_name_422`** — POST with `name="Bad Name"` → 422 (Pydantic). Try other invalids: empty, leading digit, consecutive dashes, > 64 chars. SKILL-01 negative.
4. **`test_create_duplicate_name_409`** — same user POSTs `legal-review` twice → second call returns 409 with `"Skill name already exists"`.
5. **`test_global_skill_visible_to_other_user`** — user A creates + shares (PATCH share global=true); user B GETs and sees it in their list. SKILL-06 positive.
6. **`test_share_unshare_roundtrip`** — A shares (200, `is_global=true`); B GETs → visible; A unshares (200, `is_global=false`); B GETs → 404 on direct fetch and absent from list. SKILL-06 round-trip.
7. **`test_share_only_creator_403`** — A creates + shares; B tries `PATCH /skills/{id}/share {global: false}` → 403 with `"Only the creator can change sharing"` (or equivalent).
8. **`test_edit_global_skill_403`** — A creates and shares; A tries `PATCH /skills/{id} {name: "x"}` → 403 with the exact `"Cannot edit a global skill — unshare it first"` detail string.
9. **`test_admin_can_delete_any_skill`** — A creates a private skill; admin (super_admin) DELETEs → 204; subsequent GET → 404. Closes EXPORT-03 (admin moderation).
10. **`test_export_returns_valid_zip`** — Create skill + 1 file; GET `/skills/{id}/export` → 200, `Content-Type: application/zip`, body parses via `parse_skill_zip` and yields a single `ParsedSkill` whose `frontmatter.name` and `frontmatter.description` match the original. Closes EXPORT-01.
11. **`test_import_single_skill_zip`** — Build a ZIP via `build_skill_zip` round-trip helper; POST as multipart `{"file": ("skill.zip", data, "application/zip")}` → 200 with `created_count=1`. Closes EXPORT-02 single.
12. **`test_import_bulk_zip_with_mixed_results`** — 3 skills in ZIP: one valid (`approving-clause-x`), one with bad name (`Bad Name`), one duplicate of an existing user-owned skill. Expect `created_count=1`, `error_count=2`, errors indexed by name in `results`. Closes EXPORT-02 bulk.
13. **`test_import_oversized_file_skipped`** — ZIP with one 11 MB file inside an otherwise-valid skill → response is 200, `created_count=1`, but the per-skill `skill_files` row count is 0 for the oversized file (or surfaced via the `results[].error` channel — exact field per D-P7-08).
14. **`test_import_oversized_zip_413`** — Build a synthetic 51 MB ZIP body (simply pad an entry); POST → 413 with `"ZIP exceeds 50 MB limit"`.

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

1. All 14 test cases pass against `http://localhost:8000` (backend running with migrations 034 + 035 applied).
2. `cd backend && source venv/bin/activate && python -c "from app.main import app; print('OK')"` still prints OK (no import-side breakage).
3. PostToolUse lint hook is green for `test_skills.py`.
4. Re-run all 14 against deployed backend after `railway up` — all pass (Phase 7 closure confirmation).

## Atomic commit

```
test(skills): API integration tests for Phase 7 (14 cases)
```

## Risks / open verifications

- **`test-2@test.com` super_admin status**: CLAUDE.md says only `test@test.com` is super_admin. Confirm `test-2@test.com` is NOT promoted before relying on it for the negative-RLS tests. If it is, demote with `python -m scripts.set_admin_role` before the test run.
- **Test 13's surface for oversized files**: D-P7-08 leaves the surface ambiguous between "drop file silently" vs "report in `results[].error`". Whichever 07-03 chose, this test must mirror — fail loudly if 07-03 changes.
- **Multipart `httpx` quirks**: bulk ZIP tests at 51 MB body may stress the test client's default timeout. Use `httpx.AsyncClient(timeout=60)` explicitly.
- **Test isolation**: each test that creates skills must clean up via DELETE in a fixture teardown OR use unique names per run (e.g., `f"legal-review-{uuid.uuid4().hex[:6]}"`); without isolation, repeated runs hit duplicate-name 409s.
