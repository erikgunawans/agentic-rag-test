---
status: human_needed
phase: 08
must_haves_verified: 10/10
human_verification_items: 4
---

# Phase 08 Verification — LLM Tool Integration & Discovery

## Must-Have Checks

All 10 code-level must-haves verified (exists / substantive / wired / data-flowing).

| # | Must-Have | Status | Evidence |
|---|-----------|--------|----------|
| 1 | `build_skill_catalog_block` called at both chat system-prompt sites | PASS | Both single-agent and multi-agent paths confirmed; 5 integration tests pass |
| 2 | `execute_tool()` token kwarg + forwarding through `_run_tool_loop` | PASS | Both call sites pass `token=user["token"]`; both `execute_tool` calls inside loop pass `token=token` |
| 3 | `load_skill` registered and fully implemented | PASS | TOOL_DEFINITIONS entry, dispatch branch, auth guard, RLS-scoped query, file list return |
| 4 | `save_skill` registered and fully implemented | PASS | TOOL_DEFINITIONS entry, name regex, create/update paths, 23505 conflict response |
| 5 | `read_skill_file` registered and fully implemented | PASS | TOOL_DEFINITIONS entry, text inline 8K cap, binary metadata-only, missing-file error |
| 6 | `skill_catalog_service.py` — async, RLS-scoped, fail-soft, D-P8-02/06/07 | PASS | Authed client, "" on DB exception, cap 20 alphabetically, count-free footer |
| 7 | POST upload endpoint `/skills/{id}/files` | PASS | Registered, auth guard, RLS client, `log_action`, returns 201 |
| 8 | DELETE endpoint `/skills/{id}/files/{file_id}` | PASS | Registered, auth guard, RLS client, `log_action`, returns 204 |
| 9 | GET content endpoint `/skills/{id}/files/{file_id}/content` | PASS | Registered, text inline / binary download, service-role fallback for global skills |
| 10 | Middleware gates `/skills/{id}/files` at 10 MB, `/import` at 50 MB | PASS | Dual-regex dispatch confirmed; in-handler size check is authoritative gate |

**Regression check:** 286 unit tests pass including Phase 5–7 regression suites. No cross-phase conflicts.

---

## Human Verification Items

These 4 items require a live backend + Supabase connection.

### 1. End-to-end chat with skill catalog injection and `load_skill` tool call
**Expected:** LLM sees skill catalog in system prompt; `load_skill` returns skill details with attached files list.
**Test:** Start backend, send chat message prompting LLM to use `load_skill`, verify `tool_start`/`tool_result` SSE events.

### 2. File upload/download against live Supabase Storage
**Test:**
```bash
TEST_EMAIL="test@test.com" TEST_PASSWORD='!*-3-3?3uZ?b$v&' \
TEST_EMAIL_2="test-2@test.com" TEST_PASSWORD_2='fK4$Wd?HGKmb#A2' \
API_BASE_URL="http://localhost:8000" \
pytest tests/api/test_skills.py -v -k "file" --tb=short
```

### 3. 10 MB 413 enforcement (pre-upload rejection)
**Expected:** Upload >10 MB returns HTTP 413 before any storage write.
**Test:** `dd if=/dev/urandom of=/tmp/big.bin bs=1M count=11` then `curl -F "file=@/tmp/big.bin" .../skills/$ID/files` → 413

### 4. Cross-user RLS enforcement
**Expected:** User 2 cannot upload/delete files from User 1's private skills. User 2 CAN read globally-shared skill files.
**Test:**
```bash
pytest tests/api/test_skills.py -v -k "cross_user or nonowned" --tb=short
```

---

## Code Review Findings

Two critical issues found in 08-REVIEW.md — address before shipping to production:
- **CR-01**: `_execute_save_skill` missing `log_action` — LLM skill mutations produce no audit record
- **CR-02**: `_execute_read_skill_file` missing service-role storage fallback — global skill files will fail

Run `/gsd-code-review-fix 08` after UAT approval.
