---
phase: 20-harness-engine-core-gatekeeper-post-harness-file-upload-lock
plan: 12
status: complete
commit: ef2c59e
---

# Plan 20-12 Summary — CR-01/CR-02/CR-03 Gap Closure

## What was done

Applied three one-to-three-line code fixes paired with regression tests for the bugs identified in the Phase 20 code review.

### CR-01 — `gatekeeper.py` sentinel window too small

**Root cause:** `_WINDOW_SIZE = len(SENTINEL) + 8 = 25`. `SENTINEL = "[TRIGGER_HARNESS]"` is 17 chars, not 12 as the comment claimed. When the LLM appended 9+ trailing spaces (17+9=26 > 25), the opening `[` flushed as a `delta` event before end-of-stream detection fired.

**Fix:** `_WINDOW_SIZE = len(SENTINEL) + 8 + 8 = 33`. Corrected comment from `12 + 8 = 20` to `17 + 8 + 8 = 33`.

**Regression test:** `test_run_gatekeeper_sentinel_with_9_trailing_spaces_no_leak` — streams the sentinel with exactly 9 trailing spaces character-by-character, asserts no `delta` event contains `[TRIGGER_HARNESS]` and that `gatekeeper_complete.triggered=True`.

### CR-02 — `harness_engine.py` `ws` unbound on constructor failure

**Root cause:** `ws = WorkspaceService(token=token)` was inside a `try` block. If the constructor raised, `ws` was never bound. Lines 338-346 and 384-392 called `_append_progress(workspace=ws)` unconditionally, producing `NameError`.

**Fix:** Added `ws: WorkspaceService | None = None` as a single line immediately before the `try` block. `_append_progress` already accepts `workspace=None` as a safe fallback.

**Regression test:** `test_harness_engine_ws_unbound_does_not_raise_name_error` — patches `WorkspaceService` to raise `RuntimeError` on construction, asserts `NameError` is not raised, allows all other exceptions through.

### CR-03 — `chat.py` 409 response missing `phase_count`

**Root cause:** The `harness_in_progress` 409 `JSONResponse` content dict omitted `phase_count`. Frontend `useChatState.ts` reads `err.body.phase_count` with fallback `harnessRun?.phaseCount ?? 1`. When `harnessRun` is null on fresh page load, the denominator defaulted to 1, producing an invalid `phase N/1` display.

**Fix:** Added `"phase_count": len(h.phases) if h else 0` to the `content` dict. `h` was already fetched at line 374 in the enclosing scope.

**Regression test:** `test_409_harness_in_progress_includes_phase_count` — mocks a 3-phase harness, asserts `response.status_code == 409`, `payload["phase_count"] == 3`, `payload["error"] == "harness_in_progress"`.

## Verification results

All 7 plan acceptance checks passed:
- `grep "_WINDOW_SIZE = len(SENTINEL) + 8 + 8"` — ✓
- `grep "17 + 8 + 8 = 33"` — ✓
- `grep "ws: WorkspaceService | None = None"` — ✓
- `grep '"phase_count": len(h.phases) if h else 0'` — ✓
- All 3 new test names present in their respective files — ✓
- Import check `from app.main import app` — ✓
- `pytest tests/services/test_gatekeeper.py tests/services/test_harness_engine.py tests/routers/test_chat_harness_routing.py` — **42 passed, 0 failed**

## Files changed

- `backend/app/services/gatekeeper.py` — 3 lines changed (comment + `_WINDOW_SIZE`)
- `backend/app/services/harness_engine.py` — 1 line added
- `backend/app/routers/chat.py` — 1 line added
- `backend/tests/services/test_gatekeeper.py` — 50 lines added (test + header)
- `backend/tests/services/test_harness_engine.py` — 42 lines added (test + header)
- `backend/tests/routers/test_chat_harness_routing.py` — 52 lines added (test + header)
