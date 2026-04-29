---
status: findings
phase: "07"
depth: standard
files_reviewed: 10
findings:
  critical: 2
  warning: 5
  info: 3
  total: 10
---

# Phase 07 Code Review — Skills Database & API Foundation

## Critical

### CR-1 — `parse_skill_zip`: ZipFile not closed on exception — file descriptor leak

**File:** `backend/app/services/skill_zip_service.py` (parse_skill_zip function)
**Risk:** FD pressure under concurrent load with many failed imports

`zipfile.ZipFile(io.BytesIO(zip_bytes))` is opened without a `with` block. If `ValueError` is raised on the bomb-check, or if any downstream code throws, the `ZipFile` handle is never explicitly closed.

**Fix:**
```python
with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
    total_uncompressed = sum(info.file_size for info in zf.infolist())
    if total_uncompressed > max_total:
        raise ValueError("ZIP exceeds 50 MB limit")
    # ... rest of function using zf
```

---

### CR-2 — Chunked overflow returns `http.disconnect` not 413 — caller receives TCP RST

**File:** `backend/app/middleware/skills_upload_size.py` (lines ~36-46)
**Risk:** Inconsistent error handling — Content-Length path returns 413, chunked path silently drops connection

When chunked transfer-encoding exceeds 50 MB, `capped_receive()` returns `{"type": "http.disconnect"}`. Starlette interprets this as a client abort and closes the TCP connection without sending any HTTP response. The existing test (test 13) only exercises the Content-Length fast-path, so it does not catch the broken chunked path.

**Fix:** Check overflow flag in `dispatch()` and return a JSONResponse:
```python
async def capped_receive():
    msg = await original_receive()
    if msg["type"] == "http.request":
        total["n"] += len(msg.get("body", b""))
        if total["n"] > MAX_IMPORT_BYTES:
            total["overflow"] = True
    return msg

request._receive = capped_receive
response = await call_next(request)
if total.get("overflow"):
    return JSONResponse({"detail": "ZIP exceeds 50 MB limit"}, status_code=413)
return response
```

---

## Warning

### WR-1 — `import_skills`: `BadZipFile` not caught — non-ZIP uploads return HTTP 500

**File:** `backend/app/routers/skills.py` (import endpoint)
**Risk:** Any authenticated user can trigger 500 by uploading a non-ZIP file

`parse_skill_zip` raises `zipfile.BadZipFile` for non-ZIP bytes. The endpoint only catches `ValueError`. Any `.txt`, `.pdf`, or corrupted upload triggers an unhandled exception that FastAPI renders as 500.

**Fix:**
```python
except (ValueError, zipfile.BadZipFile) as exc:
    status = 413 if isinstance(exc, ValueError) else 422
    detail = str(exc) if isinstance(exc, ValueError) else "Uploaded file is not a valid ZIP"
    raise HTTPException(status_code=status, detail=detail)
```

---

### WR-2 — `build_skill_zip` leaks DB columns into exported SKILL.md frontmatter

**File:** `backend/app/services/skill_zip_service.py` (build_skill_zip function)
**Risk:** `user_id`, `created_by`, `id`, timestamps exposed in exported ZIPs

The catch-all loop adds every key from the raw Supabase row that is not in the explicit allow-list into the frontmatter. Fields like `id`, `user_id`, `created_by`, `created_at`, `updated_at`, `enabled` all leak into the exported SKILL.md.

**Fix:** Use an explicit allow-list instead of a deny-list:
```python
FRONTMATTER_KEYS = {"name", "description", "license", "compatibility"}
fm = {k: skill[k] for k in FRONTMATTER_KEYS if skill.get(k)}
fm.update(skill.get("metadata") or {})
```

---

### WR-3 — Upload size cap bypassed by trailing slash or proxy path normalisation

**File:** `backend/app/middleware/skills_upload_size.py` (line ~16)
**Risk:** Reverse-proxy that strips trailing slash bypasses the 50 MB cap

`SKILLS_IMPORT_PATH = "/skills/import"` is matched with `==`. A proxy that normalises `/skills/import/` before routing hits the middleware with the slash variant, which skips the cap.

**Fix:**
```python
if request.method != "POST" or request.url.path.rstrip("/") != SKILLS_IMPORT_PATH:
```

---

### WR-4 — NEW-H1 test has no enforceable assertion — Storage RLS regression goes undetected

**File:** `backend/tests/api/test_skills.py` (TestGlobalSkillCreatorCannotMutateStorage)
**Risk:** RLS policy removal or mis-application would silently pass the test

Both DELETE and UPLOAD storage operations while globally shared are wrapped in `try/except: pass`. If the RLS policy fails open, the test still passes. The test comment explicitly acknowledges this.

**Fix:** Assert on the result:
```python
deleted = []
try:
    deleted = a_storage.storage.from_("skills-files").remove([file_path])
except Exception:
    pass  # RLS raised — correct
assert not deleted, f"Storage RLS failed: creator deleted from global skill. deleted={deleted}"
```

---

### WR-5 — `%` and `_` LIKE wildcards not sanitised in `ilike` search

**File:** `backend/app/routers/skills.py` (list_skills)
**Risk:** Wildcard abuse — `%` returns all visible skills regardless of search intent

The sanitisation strips `,`, `(`, `)`, `.` but leaves `%` and `_` intact. A search for `%` matches every skill. This matches the pattern in `clause_library.py:53` — a project-wide issue worth fixing in both places.

**Fix:** Add to sanitisation chain:
```python
search = search.replace("%", "").replace("_", "")
```

---

## Info

### IN-1 — `pytest-asyncio` unused in Phase 7 test files

**File:** `backend/requirements.txt`

`pytest-asyncio>=0.24.0` was added but neither `test_skills.py` nor `test_skill_zip_service.py` contains `async def` test functions. Harmless if planned for a future phase.

---

### IN-2 — Bulk import audit log omits individual created skill IDs

**File:** `backend/app/routers/skills.py` (import endpoint)

`log_action` is called once per import batch with `resource_id=None`. Individual IDs of created skills are not recorded. Auditors cannot reconstruct exactly which skills were created in a batch import from the audit table alone.

---

### IN-3 — `middleware/__init__.py` is empty

**File:** `backend/app/middleware/__init__.py`

Empty package marker. `main.py` imports directly from the module path — correct and consistent with other packages.
