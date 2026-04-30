---
status: findings
phase: 08
files_reviewed: 9
findings:
  critical: 2
  warning: 1
  info: 0
  total: 3
---

# Phase 08 Code Review — LLM Tool Integration & Discovery

**Depth:** standard
**Files reviewed:** 9
**Scope:** backend/app/middleware/skills_upload_size.py, backend/app/routers/chat.py, backend/app/routers/skills.py, backend/app/services/skill_catalog_service.py, backend/app/services/tool_service.py, backend/tests/api/test_chat_skill_catalog.py, backend/tests/api/test_skills.py, backend/tests/unit/test_skill_catalog_service.py, backend/tests/unit/test_tool_service_skill_tools.py

---

## Critical (CR-*)

### CR-01 — `save_skill` LLM tool bypasses audit trail on all mutations

**Confidence:** 95
**File:** `backend/app/services/tool_service.py` (create branch ~lines 1009–1034, update branch ~lines 976–1007)

`_execute_save_skill` creates or updates a skill row in Postgres but never calls `log_action()`. CLAUDE.md states: "All mutations must call `log_action(...)` for audit trail." Both HTTP router equivalents call it: `create_skill` in `skills.py` and `update_skill` in `skills.py`. The LLM tool path is a silent exception — any skill create/update triggered by the LLM produces no audit record.

**Fix:** Add `log_action` calls at both branch exits in `_execute_save_skill`, mirroring the HTTP router pattern. Pass `user_email=None` since email is not available in the tool handler context.

```python
# After successful create:
try:
    log_action(user_id=user_id, user_email=None, action="create",
               resource_type="skill", resource_id=str(row["id"]),
               details={"via": "llm_tool"})
except Exception:
    pass

# After successful update:
try:
    log_action(user_id=user_id, user_email=None, action="update",
               resource_type="skill", resource_id=str(row["id"]),
               details={"via": "llm_tool"})
except Exception:
    pass
```

---

### CR-02 — `read_skill_file` LLM tool fails for globally-shared skill files

**Confidence:** 90
**File:** `backend/app/services/tool_service.py` (~lines 1083–1087)

`_execute_read_skill_file` performs a single RLS-scoped storage download with no fallback:

```python
raw = client.storage.from_("skills-files").download(f["storage_path"])
```

Storage paths are structured as `{creator_user_id}/{skill_id}/{filename}`. When a skill is globally shared by user X and user Y calls `read_skill_file`, the RLS-scoped client uses Y's JWT. The DB query correctly returns the file row (global skills are visible to all), but the subsequent storage download fails because the bucket policy requires the JWT `uid()` to match the first path segment (creator's user_id). The LLM receives an unhelpful `download_failed` error for a skill it was just told it has access to via `load_skill`.

The HTTP counterpart `get_skill_file_content` in `skills.py` has an explicit service-role fallback with the comment: *"service-role: required to download files for globally-shared skills per D-P7-07."*

**Fix:** Mirror the HTTP endpoint pattern — try authed download first, fall back to service-role on exception:

```python
try:
    raw = client.storage.from_("skills-files").download(f["storage_path"])
except Exception:
    # service-role fallback: required for globally-shared skill files per D-P7-07
    try:
        svc = get_supabase_client()
        raw = svc.storage.from_("skills-files").download(f["storage_path"])
    except Exception as e:
        logger.warning("read_skill_file download failed: %s", e)
        return {"error": "download_failed", "message": str(e)}
```

---

## Warnings (WR-*)

### WR-01 — Middleware chunked-overflow guard is dead code for `/skills/{id}/files`

**Confidence:** 85
**File:** `backend/app/middleware/skills_upload_size.py` (lines 57–74)

The `SkillsUploadSizeMiddleware` docstring claims the per-file 10 MB cap is enforced via "Content-Length header when present; streaming byte counter when absent (chunked transfer-encoding)." For the `/skills/{id}/files` endpoint, the chunked-streaming path is effectively dead code.

The chunked path wraps `request._receive`, counts bytes, sets `total["overflow"] = True`, then calls `response = await call_next(request)`. By the time `total["overflow"]` is checked after `call_next` returns, the route handler has already executed `content = await file.read()`, run the in-handler size check (`skills.py:615`), uploaded to storage, and inserted the DB row. The 413 response is returned, but the upload has already been committed.

The actual gate for chunked uploads is the in-handler `len(content) > _PER_FILE_MAX_BYTES` check at `skills.py:615`, which correctly raises HTTP 413 before storage or DB operations. No security regression — the in-handler check is authoritative. However, the docstring misleads readers about where enforcement actually occurs.

**Fix (minimal):** Update the `SkillsUploadSizeMiddleware` docstring to note that the chunked counter is a best-effort signal only, and that the authoritative in-handler check at `skills.py` is the real gate for `/skills/{id}/files`.

---

## Passing Checks

**chat.py — Token plumbing:** `token=user["token"]` forwarded at both `_run_tool_loop` call sites (multi-agent and single-agent paths). Inside `_run_tool_loop`, `token=token` forwarded at both `execute_tool` call sites (redaction-on and redaction-off paths). Complete and symmetric. ✓

**chat.py — Catalog injection:** `build_skill_catalog_block(user["id"], user["token"])` called at both the multi-agent and single-agent system-prompt assembly sites. D-P8-02 empty-string invariant ensures pre-Phase-8 behavior when no skills are enabled. ✓

**skill_catalog_service.py — RLS correctness:** Uses `get_supabase_authed_client(token)` (not service-role). Fail-soft: any DB exception returns `""` with warning log. D-P8-06 (cap 20) and D-P8-07 (count-free truncation footer via `limit(21)` probe) correctly implemented. ✓

**skills.py — File endpoint auth:** All three new endpoints have `get_current_user` dependency guard and use RLS-scoped client for all DB operations. `log_action` called on upload and delete mutations. ✓

**skills.py — Middleware registration:** Route pattern `^/skills/[^/]+/files$` correctly matches only `POST /skills/{id}/files`. DELETE and GET paths correctly excluded. ✓

**tool_service.py — Skill tool auth guards:** All three handlers guard on `not token` at entry and return structured `{"error": "auth_required"}` dicts (correct — tool handlers must not raise exceptions). ✓

**tool_service.py — Skill tool RLS:** All three handlers use `get_supabase_authed_client(token)` for DB queries. Service-role not used. ✓

**Tests:** Unit and integration tests cover primary happy-path and key negative cases. `test_upload_to_nonowned_skill_403_or_404` accepting both status codes is correct — 404 from RLS-hidden private skills, 403 from visible-but-unowned global skills. ✓
