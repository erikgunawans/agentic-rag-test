---
status: partial
phase: "07"
findings_in_scope: 7
fixed: 6
skipped: 1
iteration: 1
fixed_at: 2026-04-29T00:00:00Z
review_path: .planning/phases/07-skills-database-api-foundation/07-REVIEW.md
---

# Phase 07: Code Review Fix Report

**Fixed at:** 2026-04-29
**Source review:** `.planning/phases/07-skills-database-api-foundation/07-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 7 (CR-1, CR-2, WR-1, WR-2, WR-3, WR-4, WR-5)
- Fixed: 6
- Skipped: 1 (WR-2 — already fixed in prior commit 4e0120e)

## Fixed Issues

### CR-1: ZipFile not closed on exception — file descriptor leak

**Files modified:** `backend/app/services/skill_zip_service.py`
**Commit:** `b542da9`
**Applied fix:** Wrapped `zipfile.ZipFile(io.BytesIO(zip_bytes))` in a `with` block so the handle is closed on any exception (ValueError for bomb-check, BadZipFile for invalid ZIPs, or any downstream error). All layout detection and parsing logic is now correctly indented inside the context manager.

---

### CR-2: Chunked overflow returns http.disconnect not 413

**Files modified:** `backend/app/middleware/skills_upload_size.py`
**Commit:** `a97ce4e`
**Applied fix:** Added `"overflow": False` to the `total` dict. `capped_receive()` now sets `total["overflow"] = True` when the byte count exceeds the cap (without returning `http.disconnect`). After `call_next(request)` completes, `dispatch()` checks the overflow flag and returns a `JSONResponse({"detail": "ZIP exceeds 50 MB limit"}, status_code=413)`. This ensures the client receives a proper HTTP 413 response instead of a silent TCP RST for chunked uploads.

---

### WR-1: BadZipFile not caught — non-ZIP uploads return HTTP 500

**Files modified:** `backend/app/routers/skills.py`
**Commit:** `992a62a`
**Applied fix:** Added `import zipfile` to the router imports. Changed the bare `except ValueError:` to `except (ValueError, zipfile.BadZipFile) as exc:` with conditional status (413 for ValueError, 422 for BadZipFile) and appropriate detail messages. Non-ZIP uploads now return 422 with "Uploaded file is not a valid ZIP" instead of 500.

---

### WR-3: Upload size cap bypassed by trailing slash

**Files modified:** `backend/app/middleware/skills_upload_size.py`
**Commit:** `a1c05a9`
**Applied fix:** Changed `request.url.path != SKILLS_IMPORT_PATH` to `request.url.path.rstrip("/") != SKILLS_IMPORT_PATH`. A reverse proxy normalising `/skills/import/` to include a trailing slash now correctly hits the size cap middleware.

---

### WR-4: NEW-H1 test has no enforceable assertion

**Files modified:** `backend/tests/api/test_skills.py`
**Commit:** `9d6de4d`
**Applied fix:** Replaced the `try/except: pass` block (with its commented-out unenforced check) with a pattern that captures the `deleted` list before the try block, assigns to it inside try, and then asserts `not deleted` after the except clause. If RLS fails open and the storage DELETE actually removes the file, the test now fails with a descriptive message: `"Storage RLS failed: creator deleted from global skill. deleted={deleted}"`.

---

### WR-5: % and _ LIKE wildcards not sanitised in ilike search

**Files modified:** `backend/app/routers/skills.py`
**Commit:** `551a589`
**Applied fix:** Added `.replace("%", "").replace("_", "")` to the sanitisation chain in `list_skills`. A search for `%` or `_` now returns results matching the literal empty-string pattern rather than all visible skills. This mirrors the fix pattern recommended for `clause_library.py:53`.

---

## Skipped Issues

### WR-2: build_skill_zip leaks DB columns into exported SKILL.md frontmatter

**File:** `backend/app/services/skill_zip_service.py` (build_skill_zip function)
**Reason:** Already fixed in commit `4e0120e` prior to this review-fix run. The current `build_skill_zip` implementation already uses an explicit allow-list: `fm` is built with only `name`, `description`, `license`, and `compatibility`, then extended with `skill.get("metadata") or {}`. A comment in the code reads "Merge only user-authored metadata JSONB — never expose DB columns (id, user_id, etc.)". No action needed.
**Original issue:** `user_id`, `created_by`, `id`, timestamps exposed in exported ZIPs via catch-all loop.

---

_Fixed: 2026-04-29_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
