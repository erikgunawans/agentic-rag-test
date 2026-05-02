---
phase: 17-deep-mode-foundation-planning-todos-plan-panel
reviewed: 2026-05-03T05:51:00+07:00
depth: standard
files_reviewed: 27
files_reviewed_list:
  - backend/.env.example
  - backend/app/config.py
  - backend/app/routers/chat.py
  - backend/app/routers/settings.py
  - backend/app/routers/threads.py
  - backend/app/services/agent_todos_service.py
  - backend/app/services/deep_mode_prompt.py
  - backend/app/services/tool_registry.py
  - backend/tests/integration/test_deep_mode_byte_identical_fallback.py
  - backend/tests/integration/test_deep_mode_chat_loop.py
  - backend/tests/integration/test_migration_038_agent_todos.py
  - backend/tests/integration/test_threads_todos_endpoint.py
  - backend/tests/integration/test_write_read_todos_tools.py
  - backend/tests/unit/test_agent_todos_service.py
  - backend/tests/unit/test_config_deep_mode.py
  - frontend/src/components/chat/AgentBadge.tsx
  - frontend/src/components/chat/InputActionBar.tsx
  - frontend/src/components/chat/MessageInput.tsx
  - frontend/src/components/chat/MessageView.tsx
  - frontend/src/components/chat/PlanPanel.tsx
  - frontend/src/components/chat/WelcomeInput.tsx
  - frontend/src/hooks/useChatState.ts
  - frontend/src/i18n/translations.ts
  - frontend/src/lib/api.ts
  - frontend/src/lib/database.types.ts
  - frontend/src/pages/ChatPage.tsx
  - supabase/migrations/038_agent_todos_and_deep_mode.sql
findings:
  critical: 5
  warning: 6
  info: 4
  total: 15
status: issues_found
---

# Phase 17: Code Review Report

**Reviewed:** 2026-05-03T05:51:00+07:00
**Depth:** standard
**Files Reviewed:** 27
**Status:** issues_found

## Summary

Phase 17 ships the Deep Mode foundation: loop caps config, `agent_todos` migration, `write_todos`/`read_todos` tool pair, `run_deep_mode_loop` chat branch, `GET /threads/{id}/todos` endpoint, frontend Deep Mode toggle, and the Plan Panel sidebar. The overall architecture is sound — RLS is present on `agent_todos`, the SC#5 byte-identical invariant is preserved by front-gating `run_deep_mode_loop` behind `body.deep_mode`, and the tool-registry integration follows the established adapter pattern.

Several correctness and security issues were found:

1. **Race condition in `write_todos`**: the delete and insert are not wrapped in a transaction, so a concurrent LLM write can corrupt the list.
2. **`run_deep_mode_loop` passes `messages` (pre-anonymization history) directly to the deep loop**, bypassing the per-turn anonymization that `event_generator` applies.
3. **`_run_tool_loop_for_test` references undeclared closure variables** (`_bridge_active`, `_bridge_event_sent`) and will raise `NameError` in tests that exercise the `execute_code` branch.
4. **`tool_registry._register_phase17_todos()` fires unconditionally at module import**, so `write_todos`/`read_todos` are always registered even when `TOOL_REGISTRY_ENABLED=false`; the integration test that asserts they are absent after `_clear_for_tests()` is testing the wrong invariant.
5. **`get_thread_todos` endpoint does not verify thread ownership** — it relies solely on RLS, which returns an empty list rather than a 403 when User B queries User A's thread. The endpoint provides no ownership error for an authenticated user querying a thread that belongs to someone else.

---

## Critical Issues

### CR-01: `write_todos` delete + insert not atomic — race condition corrupts todo list

**File:** `backend/app/services/agent_todos_service.py:107-120`

**Issue:** The full-replacement write is implemented as two separate Supabase calls: `DELETE … WHERE thread_id = ?` followed by `INSERT …`. There is no transaction wrapping them. In a multi-round deep-mode loop where the LLM emits two rapid `write_todos` calls, the second delete can execute between the first delete and the first insert, resulting in a permanently empty list (or in the opposite ordering, a list containing rows from both writes). The `agent_todos_service` docstring explicitly requires "full-replacement" semantics but does not enforce atomicity.

Supabase PostgREST does not expose `BEGIN`/`COMMIT` directly, but the delete + insert can be made atomic by using an RPC (PostgreSQL function) that wraps both in a single transaction.

**Fix:**
```sql
-- Add to a migration:
CREATE OR REPLACE FUNCTION public.replace_agent_todos(
  p_thread_id UUID,
  p_user_id   UUID,
  p_todos     JSONB   -- array of {content, status, position}
) RETURNS SETOF public.agent_todos
LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
  DELETE FROM public.agent_todos
  WHERE thread_id = p_thread_id AND user_id = p_user_id;

  RETURN QUERY
  INSERT INTO public.agent_todos (thread_id, user_id, content, status, position)
  SELECT p_thread_id, p_user_id,
         (el->>'content')::text,
         (el->>'status')::text,
         (el->>'position')::int
  FROM jsonb_array_elements(p_todos) WITH ORDINALITY AS t(el, ord)
  RETURNING *;
END;
$$;
```
Then call `client.rpc("replace_agent_todos", {...})` from `write_todos`. Until an RPC is available, at minimum document the race in the service docstring and add a NOTE in CONTEXT.md, and consider serialising deep-mode loop tool dispatches so two `write_todos` calls cannot overlap within the same loop iteration set.

---

### CR-02: `run_deep_mode_loop` passes raw (un-anonymized) history to the LLM when `tool_registry_enabled=false`

**File:** `backend/app/routers/chat.py:1546-1583`

**Issue:** When `redaction_on=True`, the code correctly anonymizes `messages` into `anon_history`. However, `anon_history` is only built from `m for m in messages if m.get("content")` — messages that carry a non-null `content` field. Tool-call assistant rows have `content: None` (or `content: ""`); they are silently dropped from the anonymized history list. This means the LLM receives a history missing all prior tool-call assistant turns, which can produce incorrect continuations for multi-turn deep-mode sessions.

Compare this with `event_generator`, which uses `_expand_history_row` to reconstruct the full OpenAI tool-call triplet from persisted rows, and applies redaction to the reconstructed `content` fields only — tool structure is preserved.

Additionally, `anon_history` at line 1540 is built with index-based assignment (`for i, h in enumerate(...)`) but the generator expression producing the enumerated items is not a list — it is a lazy generator. The `enumerate(m for m in messages if m.get("content"))` produces correct results but the outer list comprehension means `anonymized_strings[i]` and `h` stay in sync only if both generators advance at the same rate. This is currently safe but fragile.

**Fix:**
```python
# Filter messages that have content — but preserve full structure for tool rows
content_messages = [m for m in messages if m.get("content")]
raw_strings = [m["content"] for m in content_messages] + [user_message]
anonymized_strings = await redaction_service.redact_text_batch(raw_strings, registry)
anon_history = [
    {**h, "content": anonymized_strings[i]}
    for i, h in enumerate(content_messages)
]
# Non-content messages (tool-call assistant rows) must still be included
# for correct LLM context; merge back preserving order:
full_anon_history = []
content_idx = 0
for m in messages:
    if m.get("content"):
        full_anon_history.append({**m, "content": anonymized_strings[content_idx]})
        content_idx += 1
    else:
        full_anon_history.append(m)
anon_history = full_anon_history
```

---

### CR-03: `_run_tool_loop_for_test` references undeclared variables `_bridge_active` and `_bridge_event_sent`

**File:** `backend/app/routers/chat.py:1300-1308`

**Issue:** The module-level test helper `_run_tool_loop_for_test` is a copy of the inner `_run_tool_loop` closure but references `_bridge_active` and `_bridge_event_sent` at lines 1300-1308 (inside the `if func_name == "execute_code":` branch). These names are local variables of `event_generator` — they do not exist in the module-level scope. Any test that dispatches an `execute_code` tool call through `_run_tool_loop_for_test` will raise `NameError: name '_bridge_active' is not defined` at runtime.

**Fix:**
```python
async def _run_tool_loop_for_test(
    messages, tools, max_iterations, user_id, tool_context,
    *,
    registry=None, redaction_service=None, redaction_on=False,
    available_tool_names=None, token=None,
    # Add these to make the test helper self-contained:
    bridge_active: bool = False,
):
    ...
    if func_name == "execute_code":
        _bridge_event_sent_local = False   # local to this invocation
        if bridge_active and not _bridge_event_sent_local:
            ...
```
Or simply replace the two references with `False` (the sandbox is never active in unit test context).

---

### CR-04: `_register_phase17_todos()` is called unconditionally at module import, defeating the `TOOL_REGISTRY_ENABLED=false` dark-launch gate

**File:** `backend/app/services/tool_registry.py:705`

**Issue:** `_register_phase17_todos()` is called at module load time (line 705), directly after `_register_tool_search()` (line 546). The module-level comment at line 556 states "This module is only imported when settings.tool_registry_enabled is True (lazy import in `_register_natives_with_registry`)". However, any code path that imports `tool_registry` — including test files that call `from app.services import tool_registry` unconditionally — will register `write_todos` and `read_todos` regardless of the flag value.

The integration test at `test_write_read_todos_tools.py:394-421` asserts that after `_clear_for_tests()`, `write_todos` is NOT in `_REGISTRY`. But `_clear_for_tests()` calls `_register_tool_search()` only — it does NOT re-call `_register_phase17_todos()`. So the test passes for the wrong reason: the tools are absent only because `_clear_for_tests()` removed them, not because the flag is off.

More critically: if any non-flag-gated code path imports `tool_registry`, `write_todos` will be callable even with `TOOL_REGISTRY_ENABLED=false`, violating the TOOL-05 byte-identical invariant.

**Fix:** Move `_register_phase17_todos()` call inside a flag check, consistent with how `sandbox_enabled` gates `execute_code`:
```python
# At bottom of tool_registry.py, replace unconditional call:
from app.config import get_settings as _get_settings
if _get_settings().tool_registry_enabled:
    _register_phase17_todos()
```
Alternatively, gate the import of `tool_registry` itself to only happen through the lazy `if settings.tool_registry_enabled:` path in `chat.py`, which already exists — but requires auditing all other import sites.

---

### CR-05: `run_deep_mode_loop` calls `_dispatch_tool_deep` without passing `registry` and `stream_callback`, silently dropping redaction on sandbox tool outputs

**File:** `backend/app/routers/chat.py:1694-1706`

**Issue:** `_dispatch_tool_deep` (lines 1891-1917) only accepts `arguments`, `user_id`, `context`, and `token`. It does not accept `registry` or `stream_callback`. When `func_name == "execute_code"` in the deep-mode loop, no sandbox streaming occurs (no `asyncio.Queue` drain pattern), because `_dispatch_tool_deep` does not implement the `sandbox_event_queue` / callback pattern that `_dispatch_tool` uses.

Additionally, when `redaction_on=True` and the tool is not `web_search`, `anonymize_tool_output` is called on the `tool_output` (line 1700-1702), but `_dispatch_tool_deep` is called with `real_args` derived from the redaction branch — yet the `registry` is not passed to `_dispatch_tool_deep`, so inside the registry executor, the `context` dict does not have `active_set` from the deep-mode `tool_context` set at line 1589. This means `tool_search` deferred-tool mutations are lost for the deep-mode loop.

**Fix:**
```python
async def _dispatch_tool_deep(
    name: str,
    arguments: dict,
    user_id: str,
    context: dict | None = None,
    *,
    token: str | None = None,
    stream_callback=None,   # add this
) -> dict:
    if settings.tool_registry_enabled:
        from app.services import tool_registry as _tr
        if name in _tr._REGISTRY:
            tool_def = _tr._REGISTRY[name]
            return await tool_def.executor(
                arguments, user_id, context,
                token=token,
                stream_callback=stream_callback,
            )
    return await tool_service.execute_tool(
        name, arguments, user_id, context,
        token=token,
        stream_callback=stream_callback,
    )
```
The deep-mode loop caller site must also implement the `asyncio.Queue` drain pattern for `execute_code` if sandbox streaming is desired in deep mode.

---

## Warnings

### WR-01: `write_todos` delete uses authed client but RLS `agent_todos_delete` policy only checks `user_id = auth.uid()`, not `thread_id` ownership

**File:** `backend/app/services/agent_todos_service.py:107` and `supabase/migrations/038_agent_todos_and_deep_mode.sql:67-71`

**Issue:** The DELETE RLS policy is:
```sql
USING (user_id = auth.uid())
```
This allows a user to delete any of their own todos across ALL their threads via the authed client. The `write_todos` function correctly adds `.eq("thread_id", thread_id)` as defense-in-depth, but the RLS layer itself does not enforce that the deleted rows belong to the stated `thread_id`. If `write_todos` were called with a spoofed `thread_id`, the RLS would not catch it (the spoofed ID check would simply return 0 rows). This is not exploitable given the current `thread_id` is always sourced from `ctx` (T-17-06), but the RLS is weaker than the INSERT policy (which does verify thread ownership).

**Fix:** Add thread ownership to the DELETE policy for defense-in-depth parity with INSERT:
```sql
CREATE POLICY "agent_todos_delete"
  ON public.agent_todos
  FOR DELETE
  USING (
    user_id = auth.uid()
    AND EXISTS (
      SELECT 1 FROM public.threads t
      WHERE t.id = agent_todos.thread_id AND t.user_id = auth.uid()
    )
  );
```

---

### WR-02: `run_deep_mode_loop` title fallback uses raw `user_message` instead of `anonymized_message`

**File:** `backend/app/routers/chat.py:1872`

**Issue:** In the title-generation fallback path (exception handler), the code does:
```python
stub = " ".join(user_message.split()[:6]) or "New Thread"
```
`user_message` is the **raw** (pre-anonymization) user message. When `redaction_on=True`, this emits real PII into the thread title (persisted to DB and emitted as a `thread_title` SSE event to the frontend) without going through the anonymization + de-anonymization cycle.

Compare with the standard `event_generator` path where the fallback stub uses `anonymized_message` and then applies `de_anonymize_text` before persisting.

**Fix:**
```python
stub = " ".join(anonymized_message.split()[:6]) or "New Thread"
if stub and stub != "New Thread" and redaction_on:
    stub = await redaction_service.de_anonymize_text(stub, registry, mode="none")
```

---

### WR-03: `tool_registry._clear_for_tests()` docstring says it re-registers `tool_search` to match production state, but does NOT re-register `write_todos`/`read_todos`

**File:** `backend/app/services/tool_registry.py:269-281`

**Issue:** After Phase 17 ships, production state at module load includes `tool_search` + `write_todos` + `read_todos`. `_clear_for_tests()` only re-registers `tool_search`. Tests that call `_clear_for_tests()` then assume production state will be missing `write_todos`/`read_todos`, which is only true when `TOOL_REGISTRY_ENABLED=false` — a separate concern. This docstring mismatch will confuse future test authors and may cause test-order-dependent failures if a test expects `write_todos` to be present after `_clear_for_tests()`.

**Fix:** Either update the docstring to accurately document the post-clear state, or update `_clear_for_tests()` to also call `_register_phase17_todos()` when the settings flag is on:
```python
def _clear_for_tests() -> None:  # pragma: no cover
    _REGISTRY.clear()
    _register_tool_search()
    # Re-register Phase 17 todos to match production state when flag is on.
    from app.config import get_settings
    if get_settings().tool_registry_enabled:
        _register_phase17_todos()
```

---

### WR-04: `useChatState` todo hydration on thread switch has a stale-closure race condition

**File:** `frontend/src/hooks/useChatState.ts:79-96`

**Issue:** The `useEffect` that hydrates todos on thread switch calls `fetchThreadTodos` asynchronously. If the user switches threads rapidly before the fetch resolves, the resolved data from the first fetch can overwrite the second thread's `[]` initial state with the first thread's todos. The code comment at line 89 mentions this ("Guard against stale responses if user switched thread again quickly") but the guard is not implemented — the `setTodos(fetched)` call at line 90 runs unconditionally regardless of whether `activeThreadId` has changed since the fetch was initiated.

**Fix:** Use a cancellation flag or compare the thread ID at resolution time:
```typescript
useEffect(() => {
  setTodos([])
  setIsCurrentMessageDeepMode(false)
  if (!activeThreadId) return

  let cancelled = false
  supabase.auth.getSession().then(({ data }) => {
    const token = data.session?.access_token
    if (!token || !activeThreadId) return
    fetchThreadTodos(activeThreadId, token)
      .then(({ todos: fetched }) => {
        if (!cancelled) setTodos(fetched)
      })
      .catch(() => {})
  })
  return () => { cancelled = true }
}, [activeThreadId])
```

---

### WR-05: `InputActionBar` Deep Mode toggle button has no `disabled` state when `onToggleDeepMode` is undefined

**File:** `frontend/src/components/chat/InputActionBar.tsx:53-69`

**Issue:** The Deep Mode toggle button is rendered when `deepModeEnabled` is true, and calls `onClick={onToggleDeepMode}`. However, `onToggleDeepMode` is typed as `(() => void) | undefined`. If `deepModeEnabled=true` but `onToggleDeepMode` is not provided, clicking the button silently does nothing — no error, no visual feedback. This can happen if a consumer renders `<InputActionBar deepModeEnabled={true} />` without wiring the callback.

**Fix:**
```tsx
<button
  type="button"
  data-testid="deep-mode-toggle"
  aria-pressed={deepMode}
  aria-label={t('chat.deepMode.toggleAriaLabel')}
  onClick={onToggleDeepMode}
  disabled={!onToggleDeepMode}
  className={`h-8 px-2 rounded-lg flex items-center gap-1 text-xs transition-colors
    disabled:opacity-50 disabled:cursor-not-allowed
    ${deepMode ? '...' : '...'}`}
>
```

---

### WR-06: `MessageView.tsx` assistant message bubble applies `backdrop-blur-sm` on non-user messages, violating CLAUDE.md persistent-panel rule

**File:** `frontend/src/components/chat/MessageView.tsx:119`

**Issue:** The assistant message bubble at line 119 uses:
```tsx
className={`rounded-lg px-4 py-2 text-sm ${
  msg.role === 'user'
    ? 'bg-gradient-to-br ...'
    : 'bg-muted/80 text-foreground backdrop-blur-sm'
}`}
```
`backdrop-blur-sm` is applied to every assistant message bubble. CLAUDE.md explicitly states: "Glass (backdrop-blur): transient overlays ONLY (tooltips, popovers). NEVER on persistent panels (sidebars, input cards)." While individual message bubbles are not sidebars, they are persistent rendered elements in the message list (not transient overlays), and this pattern directly contradicts the design system rule. This was not introduced in Phase 17 but PlanPanel.tsx (same phase) explicitly avoids this, making the inconsistency visible.

**Fix:** Remove `backdrop-blur-sm` from the assistant message bubble class:
```tsx
: 'bg-muted/80 text-foreground'
```

---

## Info

### IN-01: `test_tool_registry_disabled_byte_identical` tests the wrong invariant after Phase 17

**File:** `backend/tests/integration/test_write_read_todos_tools.py:393-421`

**Issue:** This test calls `_clear_for_tests()` and then asserts `write_todos` is not in the registry. As noted in CR-04, `_clear_for_tests()` removes all entries and only re-registers `tool_search` — so `write_todos` will always be absent after `_clear_for_tests()` regardless of the flag. The test does not actually verify the flag-off invariant; it verifies that `_clear_for_tests()` works. The test name and assertion message are misleading.

**Fix:** To actually test the flag-off invariant, the test should reload the `tool_registry` module in a subprocess or use importlib reload with the env var unset — or simply document that the test is checking the `_clear_for_tests` helper behavior.

---

### IN-02: `test_deep_mode_byte_identical_fallback.py` uses source inspection (`inspect.getsource`) as a proxy for behavioral guarantees

**File:** `backend/tests/integration/test_deep_mode_byte_identical_fallback.py:42-152`

**Issue:** Most tests in this file use `inspect.getsource(...)` to assert that certain strings appear or do not appear in source code. This is fragile: renaming a variable, extracting a helper function, or restructuring the code could silently break the behavioral guarantee while the tests continue to pass. For example, `test_deep_mode_off_no_todos_updated_sse_in_standard_loop` at line 79 asserts `"todos_updated" not in src` by inspecting `_run_tool_loop_for_test` source — but if the todos_updated emission moved to a helper called from `_run_tool_loop_for_test`, the test would still pass while the invariant would be violated.

**Fix:** Supplement with behavioral tests: mock `openrouter_service.complete_with_tools` to return a `write_todos` tool call, drive `_run_tool_loop_for_test`, and assert that no `todos_updated` event is yielded.

---

### IN-03: `run_deep_mode_loop` creates a second `make_active_set()` for `tool_context` at line 1589 that is separate from `_deep_active_set` used for building `deep_tools`

**File:** `backend/app/routers/chat.py:1587-1590`

**Issue:**
```python
if settings.tools_enabled and settings.tool_registry_enabled:
    from app.services import tool_registry as _tr2
    tool_context["active_set"] = _tr2.make_active_set()  # <-- NEW empty set
    tool_context["agent_allowed_tools"] = None
```
The `deep_tools` list was built using `_deep_active_set` (line 1554), but `tool_context["active_set"]` is a fresh empty set. When `tool_search` is invoked and adds tools to `tool_context["active_set"]`, those tools will not be reflected in `current_tools` (which is a snapshot of `deep_tools` taken at line 1613). The `_dispatch_tool_deep` call does use `tool_context` as the `context` dict, so `tool_search` mutations will correctly update `tool_context["active_set"]`, but subsequent LLM iterations will still use `current_tools` which was snapshotted before any `tool_search` calls. This is the same limitation in the standard loop, but it means `tool_search` in deep mode cannot dynamically add tools to subsequent LLM calls.

**Fix:** Use `_deep_active_set` for `tool_context["active_set"]` so that `tool_search` mutations to the active set are visible to `build_llm_tools` if `current_tools` is rebuilt per iteration. Document this limitation if dynamic tool discovery in deep mode is out of scope for Phase 17.

---

### IN-04: `DeepModeBadge` imports `useI18n` but `AgentBadge` (in the same file) does not use the returned `t` function for agent labels

**File:** `frontend/src/components/chat/AgentBadge.tsx:2-3, 46`

**Issue:** `AgentBadge` imports `useI18n` at line 2, destructures `{ t }` at line 18 — but line 18's `const { t } = useI18n()` is actually inside `DeepModeBadge`. Looking again: `AgentBadge` at line 16 does NOT call `useI18n()`. The import at line 2 is used only by `DeepModeBadge`. The import is at module level and is correctly used, so there is no dead import. However, agent label strings like `'Research Agent'`, `'Data Analyst'`, `'General Assistant'` in `AGENT_CONFIG` at lines 4-8 are hardcoded English strings that are not run through the i18n system, while `DeepModeBadge` in the same file correctly uses `t('chat.deepMode.badge')`. This inconsistency means agent badge labels will always appear in English regardless of locale.

**Fix:** Either add i18n keys for agent labels or document that agent names are intentionally locale-invariant (they are system names, not UI copy). If the latter, add a comment to `AGENT_CONFIG` to prevent future confusion.

---

_Reviewed: 2026-05-03T05:51:00+07:00_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
