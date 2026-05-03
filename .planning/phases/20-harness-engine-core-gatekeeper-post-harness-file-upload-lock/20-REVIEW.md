---
phase: 20-harness-engine-core-gatekeeper-post-harness-file-upload-lock
reviewed: 2026-05-04T00:36:00+07:00
depth: standard
files_reviewed: 19
files_reviewed_list:
  - backend/app/config.py
  - backend/app/harnesses/__init__.py
  - backend/app/harnesses/smoke_echo.py
  - backend/app/harnesses/types.py
  - backend/app/routers/chat.py
  - backend/app/routers/workspace.py
  - backend/app/services/gatekeeper.py
  - backend/app/services/harness_engine.py
  - backend/app/services/harness_registry.py
  - backend/app/services/harness_runs_service.py
  - backend/app/services/post_harness.py
  - backend/app/services/workspace_service.py
  - supabase/migrations/042_harness_runs.sql
  - frontend/src/components/chat/FileUploadButton.tsx
  - frontend/src/components/chat/HarnessBanner.tsx
  - frontend/src/components/chat/PlanPanel.tsx
  - frontend/src/hooks/useChatState.ts
  - frontend/src/lib/toast.ts
  - frontend/src/pages/ChatPage.tsx
findings:
  critical: 3
  warning: 6
  info: 4
  total: 13
status: issues_found
---

# Phase 20: Code Review Report

**Reviewed:** 2026-05-04T00:36:00+07:00
**Depth:** standard
**Files Reviewed:** 19
**Status:** issues_found

## Summary

Phase 20 delivers the Harness Engine Core — a complete orchestration system for multi-phase LLM workflows, including the gatekeeper dialogue, harness_runs state machine, post-harness summary, file upload, and frontend UI wiring. The architecture is sound: the B4 single-registry invariant is correctly implemented, the dual-layer cancellation mechanism is well-reasoned, the migration RLS patterns are correct, and the feature-flag dark-launch is properly wired at all integration points.

Three genuine bugs were found:

1. **Sentinel leak** in `gatekeeper.py`: the sliding window does not account for the `\s*` trailing whitespace in `SENTINEL_RE`, so a LLM response ending in `[TRIGGER_HARNESS]` + 9 or more trailing whitespace chars causes the `[` character to be flushed to the client before the end-of-stream check, splitting the sentinel across safe_prefix and held_back. The end-of-stream 3b branch then re-emits the held_back fragment (`TRIGGER_HARNESS]...`) verbatim, leaking the sentinel token.

2. **`ws` UnboundLocalError** in `harness_engine.py`: `ws` is assigned inside a `try` block but referenced unconditionally later in the phase loop's failure path via `_append_progress(..., workspace=ws)`. If `WorkspaceService()` raises during initialization, the `NameError` propagates uncaught through the phase loop.

3. **Missing `phase_count` in 409 response** in `chat.py`: the `harness_in_progress` 409 payload omits `phase_count`. The frontend (`useChatState.ts` line 407) references `err.body.phase_count` and falls back to `harnessRun?.phaseCount ?? 1`, which will show `1` for a thread freshly reloaded where `harnessRun` is null — misleading UX.

Six warnings cover a double-storage-write in `register_uploaded_file`, a misleading comment in `gatekeeper.py`, todos using `"completed"` status on the failure path (should be `"failed"`), an unhandled `AbortError`-treated-as-success on the frontend, `harness_runs_service.fail()` lacking a transactional guard (inconsistent with sibling `complete()` / `cancel()`), and the gatekeeper using a non-const model for every call without a `temperature=0` pin.

---

## Critical Issues

### CR-01: Sentinel Leak When Trailing Whitespace Follows `[TRIGGER_HARNESS]`

**File:** `backend/app/services/gatekeeper.py:44-45`

**Issue:** `_WINDOW_SIZE = len(SENTINEL) + 8` is calculated as `17 + 8 = 25`. However `SENTINEL_RE = re.compile(r"\s*\[TRIGGER_HARNESS\]\s*$")` also matches *trailing* whitespace after the sentinel (the second `\s*`). The window only accounts for *leading* whitespace before the sentinel, not trailing whitespace after it.

When the LLM emits `...text [TRIGGER_HARNESS]<9+ trailing spaces>` as a single SSE chunk (length > 25), the sliding-window flush code pushes `safe_prefix = held_back[:safe_len]` to the client. With 9 trailing spaces, `safe_prefix` contains `...text [` (the opening bracket of the sentinel leaks). The remaining `TRIGGER_HARNESS]<spaces>` is in `held_back`. At end-of-stream, `SENTINEL_RE.search(held_back)` returns `None` (the sentinel is split), so the code falls into the 3b branch and yields `held_back` verbatim (`TRIGGER_HARNESS]...`). The client receives the full sentinel token concatenated.

**Verified via simulation:**
- Input: `'Some text. [TRIGGER_HARNESS]         '` (9 trailing spaces, len=37)
- `safe_len = 37 - 25 = 12` → flushed: `'Some text. ['`
- `held_back = 'TRIGGER_HARNESS]         '`
- `SENTINEL_RE.search(held_back)` → `None` → 3b branch → yields `'TRIGGER_HARNESS]         '`
- Client sees: `'Some text. [TRIGGER_HARNESS]         '` — sentinel exposed.

**Fix:** Increase `_WINDOW_SIZE` to include trailing whitespace tolerance, or strip trailing whitespace from `held_back` before the 3b branch, or use a re-check on the combined `safe_prefix + held_back`:

```python
# Option A: increase window to cover trailing whitespace too
_WINDOW_SIZE = len(SENTINEL) + 8 + 8  # 33: 8 leading + 8 trailing whitespace tolerance

# Option B (more robust): at end-of-stream, compute clean from full buffer and
# reconstruct what to yield from held_back vs. full, never relying on the
# sentinel-in-held_back heuristic.
if match:
    clean = SENTINEL_RE.sub("", full)
    # Figure out what was already flushed: full = (already_flushed) + held_back
    already_flushed_len = len(full) - len(held_back)
    clean_remaining = clean[already_flushed_len:]
    if clean_remaining:
        yield {"type": "delta", "content": clean_remaining}
```

---

### CR-02: `ws` May Be Unbound When `_append_progress(workspace=ws)` Is Called

**File:** `backend/app/services/harness_engine.py:183-197, 338-346`

**Issue:** `ws = WorkspaceService(token=token)` is assigned on line 185 **inside** the `try` block of the "Initial progress.md write" step (step 2). If `WorkspaceService.__init__()` raises (e.g., `get_supabase_authed_client` raises due to a malformed token or a client library exception at construction time), the `except` on line 192 swallows the error but `ws` is never bound.

Later in the phase loop's failure path, line 338-346 calls:
```python
await _append_progress(
    ...
    workspace=ws,   # NameError: ws is not defined
)
```
This raises `NameError: name 'ws' is not defined`, which propagates through `_run_harness_engine_inner` and is caught by the outer `run_harness_engine` wrapper — but it emits a confusing `ENGINE_CRASH` event instead of a clean phase failure.

**Fix:** Initialize `ws` before the try block:

```python
ws: WorkspaceService | None = None
try:
    ws = WorkspaceService(token=token)
    await ws.write_text_file(...)
except Exception as exc:
    logger.warning(...)
```

`_append_progress` already accepts `workspace: WorkspaceService | None = None` and falls back to creating its own instance when `None`, so this is a safe change.

---

### CR-03: `phase_count` Missing From 409 `harness_in_progress` Response

**File:** `backend/app/routers/chat.py:379-387`

**Issue:** The 409 response when a harness is active omits `phase_count`:

```python
return JSONResponse(
    status_code=409,
    content={
        "error": "harness_in_progress",
        "harness_type": active_harness["harness_type"],
        "current_phase": phase_idx,
        "phase_name": phase_name,
        # phase_count is absent
    },
)
```

In `useChatState.ts` line 407, the frontend constructs the toast message as:
```ts
`${harnessType} running (phase ${current_phase}/${phase_count ?? harnessRun?.phaseCount ?? 1})`
```

When `harnessRun` is `null` (fresh page load or just after thread switch before the `/harness/active` fetch resolves) and `phase_count` is absent from the 409 body, the denominator falls back to `1`. This renders as e.g., `"Contract Review running (phase 2/1)"` — a logically invalid fraction that misleads the user about progress.

**Fix:**
```python
h = harness_registry.get_harness(active_harness["harness_type"])
return JSONResponse(
    status_code=409,
    content={
        "error": "harness_in_progress",
        "harness_type": active_harness["harness_type"],
        "current_phase": phase_idx,
        "phase_name": phase_name,
        "phase_count": len(h.phases) if h else 0,  # add this
    },
)
```

Note: `h` is already fetched a few lines above at line 374 — reuse that binding.

---

## Warnings

### WR-01: Misleading Comment Gives Wrong Sentinel Length

**File:** `backend/app/services/gatekeeper.py:43-45`

**Issue:** The comment reads `# 12 + 8 = 20 chars` but `SENTINEL = "[TRIGGER_HARNESS]"` is 17 characters, making `_WINDOW_SIZE = 17 + 8 = 25`, not 20. The comment is wrong. This is not a runtime bug (the code uses `len(SENTINEL)` correctly) but it undermines trust in the window-size reasoning and caused the CR-01 analysis gap.

**Fix:**
```python
# Sliding-window size: len(SENTINEL) + 8 for trailing whitespace tolerance
# len("[TRIGGER_HARNESS]") = 17; 17 + 8 = 25 chars
_WINDOW_SIZE = len(SENTINEL) + 8
```

---

### WR-02: Todo Status Set to `"completed"` on Phase Failure Path

**File:** `backend/app/services/harness_engine.py:313`

**Issue:** When a phase fails, the harness engine sets `todos[phase_index]["status"] = "completed"` before writing and yielding `todos_updated`. This marks a failed phase as visually "completed" (green checkmark) in the PlanPanel rather than as failed or errored. The user sees a green checkmark next to a phase that just failed.

```python
# Line 312-313 in failure path:
if isinstance(result, dict) and "error" in result:
    todos[phase_index]["status"] = "completed"  # BUG: should indicate failure
```

The `TodoStatus` type in the frontend is `'pending' | 'in_progress' | 'completed'` — there is no `"failed"` status. The fix requires either (a) adding a `"failed"` status to the `TodoStatus` type and the `StatusIcon` component, or (b) leaving the status as `"in_progress"` so the spinner remains (indicating the phase did not finish cleanly), rather than pretending it completed.

**Fix (minimal — leaves status as in_progress to avoid false green):**
```python
if isinstance(result, dict) and "error" in result:
    # Leave todos[phase_index]["status"] as "in_progress" — do not mark complete
    # A failed phase did not complete; "completed" (green checkmark) is misleading.
    # Phase 21 can add a "failed" TodoStatus variant with a red icon.
```

---

### WR-03: `register_uploaded_file` Performs a Redundant Double Upsert

**File:** `backend/app/services/workspace_service.py:480-517`

**Issue:** `register_uploaded_file` delegates to `write_binary_file` (step 2), which already performs a `workspace_files.upsert()` on `on_conflict="thread_id,file_path"`. Then `register_uploaded_file` immediately performs a **second** `workspace_files.upsert()` on the same conflict key (step 3, lines 498-511) to enforce `source='upload'`. This is two round-trips to the DB for the same row.

The second upsert is intended to enforce `source='upload'` (the comment says "idempotent — reinforces discriminator"), but `write_binary_file` already accepts `source="upload"` passed from `register_uploaded_file`. The second upsert is therefore completely redundant.

**Fix:** Remove the step-3 upsert block. The `write_binary_file` call at step 2 already persists the row with `source="upload"` because the caller passes `source="upload"`. Keep only the audit log from step 3:

```python
# Step 2 writes with source='upload' — step 3 upsert is redundant; keep only audit.
row_id = write_result.get("id", "")
audit_service.log_action(...)
```

Note: `write_binary_file` does not return `"id"` in its current return dict; it returns `storage_path`. This is a companion issue — `register_uploaded_file`'s return value `"id": row_id` may be an empty string if the double upsert is removed. Resolve by having `write_binary_file` return the row id, or keep the upsert but document it as intentional with a comment.

---

### WR-04: `harness_runs_service.fail()` Lacks Transactional Guard

**File:** `backend/app/services/harness_runs_service.py:296-339`

**Issue:** The `fail()` function performs an unconditional update:
```python
result = (
    client.table("harness_runs")
    .update({"status": "failed", "error_detail": truncated})
    .eq("id", run_id)
    # No .in_("status", ...) guard
    .execute()
)
```

The docstring says "No transactional guard — failure can transition from any non-terminal state", but this is inconsistent with `complete()` (which guards `.eq("status", "running")`) and `cancel()` (which guards `.in_("status", ACTIVE_STATUSES)`). The inconsistency means `fail()` can overwrite a `"cancelled"` row with `"failed"`, obliterating the user-initiated cancel signal. Race window: user clicks Cancel → DB row becomes `"cancelled"` → engine's `_append_progress` exception path calls `fail()` → row reverts to `"failed"`.

**Fix:** Add the same guard pattern:
```python
result = (
    client.table("harness_runs")
    .update({"status": "failed", "error_detail": truncated})
    .eq("id", run_id)
    .in_("status", list(ACTIVE_STATUSES))  # Do not overwrite terminal states
    .execute()
)
```

---

### WR-05: Frontend `AbortError` Treated as `completeUpload` (Success Path)

**File:** `frontend/src/components/chat/FileUploadButton.tsx:102-105`

**Issue:** When the user clicks the cancel (X) button on an in-flight upload, the `AbortController` fires, `fetch()` rejects with an `AbortError`, and the code does:
```ts
if (e?.name === 'AbortError') {
    completeUpload(id)           // removes the entry from uploadingFiles Map
    toast({ message: t('upload.cancelled'), duration: 3000 })
    return
}
```

`completeUpload` removes the entry from `uploadingFiles`, which is the correct cleanup. However, calling `completeUpload` on an aborted upload conflates the success and cancellation paths from the state-management perspective. If any downstream consumer of `uploadingFiles` distinguishes between clean-completion and abort (e.g., a future "files uploaded this session" counter or gatekeeper re-trigger check), it will miscount.

**Fix:** Either call a dedicated `cancelUpload(id)` function (or reuse `failUpload(id, '')`) to keep the semantics distinct, then have the Map cleanup handled uniformly:
```ts
if (e?.name === 'AbortError') {
    failUpload(id, '')   // or a new cancelUpload(id) — not "complete"
    toast({ message: t('upload.cancelled'), duration: 3000 })
    return
}
```

---

### WR-06: Gatekeeper Uses `openrouter_model` With No `temperature` Pin

**File:** `backend/app/services/gatekeeper.py:220-224`

**Issue:** The gatekeeper's LLM call does not set `temperature`:
```python
stream = await or_svc.client.chat.completions.create(
    messages=messages,
    model=settings.openrouter_model,
    stream=True,
    # No temperature — defaults to provider default (~1.0)
)
```

The gatekeeper is a **sentinel-emitting** agent: it must consistently emit `[TRIGGER_HARNESS]` at the end of the final message when prerequisites are met. At high temperature the LLM may vary the token order, add stochastic whitespace, or omit/corrupt the sentinel, causing false negatives on the SENTINEL_RE match. At `temperature=0` the output is deterministic and the sentinel is reliably at the very end.

**Fix:**
```python
stream = await or_svc.client.chat.completions.create(
    messages=messages,
    model=settings.openrouter_model,
    stream=True,
    temperature=0.0,   # Deterministic sentinel placement
)
```

---

## Info

### IN-01: Window-Size Arithmetic Comment Refers to Nonexistent `12` Value

**File:** `backend/app/services/gatekeeper.py:43`

**Issue:** Comment says `# 12 + 8 = 20 chars`. The actual value is `len("[TRIGGER_HARNESS]") + 8 = 17 + 8 = 25`. The literal `12` appears nowhere in the code and does not correspond to any intermediate value. The code is correct; only the comment is wrong.

(See WR-01 for the fix — this is a duplicate callout for the same line, noted here as Info-level because the code itself is correct.)

---

### IN-02: `_truncate_phase_results` "Last 2 Phases" Logic Off-By-One for Single-Phase Harnesses

**File:** `backend/app/services/post_harness.py:116`

**Issue:** The condition `if idx >= n_max - 1` means "last 2 phases (indices N-1 and N)". For a single-phase harness (`n_max = 0`), `n_max - 1 = -1`, so all phases satisfy `idx >= -1` and get full content. This is correct. For a 2-phase harness (`n_max = 1`), both phases 0 and 1 satisfy `idx >= 0`, so both get full content — also correct. This is not a bug, but the comment says "Last 2 phases (indices N-1 and N)" which is slightly confusing because `n_max` is the *value* of the last key, not the count. For the smoke_echo harness with phases `{"0": ..., "1": ...}`, `n_max = 1`, so `n_max - 1 = 0`: phases 0 and 1 both get full content. No truncation ever occurs for a 2-phase harness regardless of size. This is likely intentional but should be documented.

**Fix:** Add a clarifying comment:
```python
# For <=2 phases, n_max-1 = 0, so all phases get full content (no truncation).
# Truncation only reduces content when there are 3+ phases AND total JSON > 30k chars.
if idx >= n_max - 1:
```

---

### IN-03: `toast.ts` Has No Registered Listener — Toasts Are Silent No-Ops

**File:** `frontend/src/lib/toast.ts:23-36`

**Issue:** The `toast()` function dispatches a `CustomEvent('lexcore:toast', ...)` to `window`. No Toaster component is currently wired to listen for this event in `AppLayout` or anywhere else in the codebase. The comment acknowledges this: "A Toaster component can subscribe... if a Toaster component is wired up in AppLayout in a future phase."

As a result, all upload error toasts from `FileUploadButton.tsx` (`wrong_mime`, `upload_too_large`, `magic_byte_mismatch`, `serverError`, `cancelled`) are silently dropped. Users see no feedback on upload failures unless they notice the in-progress card disappearing.

**Fix:** Wire a Toaster listener in `AppLayout` before Phase 20 ships, or fall back to `console.warn` in `toast()` during development:
```ts
if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent(TOAST_EVENT, { detail }))
} else {
    // SSR safety — no-op
}
// Development fallback if no listener registered:
// console.warn('[toast]', detail.message)
```

---

### IN-04: `ACTIVE_HARNESS_STATUSES` Declared but Suppressed With `void`

**File:** `frontend/src/hooks/useChatState.ts:65-69`

**Issue:**
```ts
const ACTIVE_HARNESS_STATUSES = new Set<string>(['pending', 'running', 'paused'])
// ...
void ACTIVE_HARNESS_STATUSES  // suppress "declared but never read"
```

`ACTIVE_HARNESS_STATUSES` is never read by any code in the file. The `void` expression is a workaround to silence the TypeScript `noUnusedLocals` error. The comment says it is "kept for documentation and future use by HarnessBanner / PlanPanel." However, both `HarnessBanner.tsx` and `PlanPanel.tsx` already declare their own `ACTIVE_STATUSES` / `ACTIVE_HARNESS_STATUSES` constants locally.

**Fix:** Remove the `useChatState.ts` declaration and the `void` suppression. Each consumer has its own copy, which is the correct pattern since the hook does not export this constant.

---

_Reviewed: 2026-05-04T00:36:00+07:00_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
