---
status: clean
phase: 19
severity_counts:
  critical: 0
  warning: 0
  info: 3
fixed_by: 19-REVIEW-FIX.md
---

# Phase 19 Code Review

Reviewed 12 source files: `backend/app/routers/chat.py` (Phase 19 sections), `backend/app/services/agent_runs_service.py`, `backend/app/services/sub_agent_loop.py`, `backend/app/services/tool_service.py` (Phase 19 registrations), `backend/app/services/deep_mode_prompt.py`, `frontend/src/components/chat/AgentStatusChip.tsx`, `frontend/src/components/chat/TaskPanel.tsx`, `frontend/src/components/chat/MessageView.tsx` (question-bubble section), `frontend/src/hooks/useChatState.ts`, `frontend/src/contexts/ChatContext.tsx`, `frontend/src/pages/ChatPage.tsx`, `supabase/migrations/040_agent_runs.sql`.

## Critical

### C-01: `agent_runs.start_run` outside try/except — uncaught DB exception hangs SSE stream with no `done` event

**File:** `backend/app/routers/chat.py` — Site A block before `try:` in `run_deep_mode_loop`

`agent_runs_service.start_run()` is awaited before the `try` block that owns all error handling for `run_deep_mode_loop`. If `start_run` raises (most likely: unique-violation from the partial-unique index when a concurrent request has already opened a `working` run for the same thread, or a transient DB connection failure), the exception escapes the generator entirely. FastAPI has already sent `200 OK` and `Content-Type: text/event-stream` response headers; no HTTP error can be returned. The frontend SSE reader receives no `done: true` terminator and no `agent_status:error` event — it hangs until TCP timeout. The `agent_runs` row is never inserted, but the user sees a permanently-stuck "Working…" chip.

**Fix:** Move the Site A block inside the `try` block. The existing `except Exception` handler already guards `if run_id is not None` before calling `agent_runs_service.error`, so the move is safe with no other changes required.

---

### C-02: `transition_status` audit log passes `user_id=None`, `user_email=None` — unattributed security audit records

**File:** `backend/app/services/agent_runs_service.py` — `transition_status` function

`transition_status` is called at every status change including the resume path in `stream_chat`. Its `audit_service.log_action` call hardcodes `user_id=None` and `user_email=None`. Every `agent_run_transition_*` audit record is orphaned — no user is associated. The function signature accepts no identity parameters. CLAUDE.md requires `log_action(user_id, user_email, …)` on all mutations.

**Fix:** Add `user_id: str | None = None` and `user_email: str | None = None` keyword parameters to `transition_status`. The resume call site in `chat.py` has `user["id"]` and `user.get("email", "")` in scope and should pass them.

---

## Warning

### W-01: `sub_agent_loop._execute_tool_call` returns error for every tool when `tool_registry_enabled=False` — sub-agent silently non-functional

**File:** `backend/app/services/sub_agent_loop.py` — `_execute_tool_call`

When `settings.tool_registry_enabled` is False, the function falls through to `return {"error": f"Tool '{func_name}' is not available."}` for every call. A deployment with `sub_agent_enabled=True` and `tool_registry_enabled=False` runs sub-agents that silently fail every tool call, exhausting iterations with no user-visible error surface.

**Fix:** Either add `assert settings.tool_registry_enabled` at module load (consistent with D-17), or add a fallback to `tool_service.execute_tool` mirroring `_dispatch_tool_deep`.

---

### W-02: Duplicate egress filter block in `sub_agent_loop._run_sub_agent_loop_inner` — unreachable `elif` branch

**File:** `backend/app/services/sub_agent_loop.py` — pre-LLM egress check

The `if redaction_on and registry is not None:` block and the `elif registry is not None:` block execute identical ~20 lines of logic. The `elif` branch is unreachable: `registry` is only non-None when the parent loop had `redaction_on=True`, so the `elif` (fires when `redaction_on=False` but `registry is not None`) cannot be reached via any current call path. The duplicated code adds maintenance risk.

**Fix:** Remove the `elif` branch. If the intent is to always filter when a registry exists, collapse to a single `if registry is not None:` guard.

---

### W-03: `isAskUserQuestion` in MessageView matches tool results by name only — question bubble incorrectly dismissed

**File:** `frontend/src/components/chat/MessageView.tsx` — `isAskUserQuestion` helper

The unmatched detection uses `toolResults.some((tr) => tr.tool === 'ask_user')` without comparing `tool_call_id`. If any `ask_user` tool_result exists in the buffer (from any round), all ask_user question bubbles in the current render pass are suppressed. The `ToolResultEvent` type has `tool_call_id` for precise matching.

**Fix:**
```typescript
const matched = toolResults.some(
  (tr) => tr.tool === 'ask_user' &&
    (!c.tool_call_id || !tr.tool_call_id || tr.tool_call_id === c.tool_call_id)
)
```

---

## Info

### I-01: Dead import alias `_gss` in resume branch — never used

**File:** `backend/app/routers/chat.py` — resume detection section

```python
from app.services.system_settings_service import get_system_settings as _gss  # already imported above
```

`_gss` is never referenced. The comment acknowledges re-import is unnecessary. Remove the line.

---

### I-02: `transition_status` and `error()` do not clear `pending_question` on transition out of `waiting_for_user` — potential CHECK constraint violation

**File:** `backend/app/services/agent_runs_service.py`

The DB CHECK `(status = 'waiting_for_user') = (pending_question IS NOT NULL)` is violated if a `waiting_for_user` run is transitioned to `error` via `transition_status(..., 'error')` or the `error()` function — neither clears `pending_question`. The scenario occurs if a crash interrupts the loop after `set_pending_question` but before a clean completion.

**Fix:** In `transition_status`, add `if new_status != "waiting_for_user": update_payload["pending_question"] = None`. Apply same in `error()`.

---

### I-03: Title-gen fallback uses raw `user_message` instead of `anonymized_message` — PII written to thread title when `redaction_on=True`

**File:** `backend/app/routers/chat.py` — `run_deep_mode_loop` title-gen fallback

The fallback stub path uses `user_message` (raw, pre-redaction) for the thread title. The primary title-gen path correctly uses `anonymized_message` + de-anon. This pre-exists in `event_generator` but the deep mode path introduces a second instance.

**Fix:** Replace `user_message` with `anonymized_message` in the fallback path and add the same de-anon guard as the primary path.

---

## Invariant Verification

| Invariant | Result |
|---|---|
| D-17: all Phase 19 paths gated by `sub_agent_enabled` | PASS |
| D-P13-01: `tool_service.py` lines 1–1283 boundary intact | PASS — Phase 19 registrations at lines 1651+ |
| T-19-03: RLS uses `thread_id IN (SELECT ...)` subquery form | PASS — all 4 policies in `040_agent_runs.sql` |
| D-12: sub_agent_loop failures wrapped, never raw-propagate | PASS |
| D-21: sub-agent reuses parent registry, no fresh load | PASS |
| No LangChain imports | PASS |
| No glass/backdrop-blur on new persistent panels | PASS |
