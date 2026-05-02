---
phase: 17-deep-mode-foundation-planning-todos-plan-panel
plan: 04
type: execute
wave: 3
depends_on: [02, 03]
files_modified:
  - backend/app/routers/chat.py
  - backend/app/services/deep_mode_prompt.py
  - backend/tests/integration/test_deep_mode_chat_loop.py
  - backend/tests/integration/test_deep_mode_byte_identical_fallback.py
autonomous: true
requirements: [DEEP-01, DEEP-02, DEEP-03, DEEP-04, DEEP-05, DEEP-06, DEEP-07, TODO-03, TODO-04]
must_haves:
  truths:
    - "POST /chat accepts a new boolean field deep_mode in the request payload (defaults to false when absent)."
    - "When DEEP_MODE_ENABLED env is false, the endpoint returns HTTP 400 'deep mode disabled' if deep_mode=true is passed; behavior with deep_mode=false is byte-identical to pre-Phase-17 v1.2 (DEEP-03)."
    - "When DEEP_MODE_ENABLED=true and deep_mode=true, the endpoint routes through a NEW deep-mode branch (run_deep_mode_loop) — separate from the existing run_tool_calling_loop, with its own iteration cap MAX_DEEP_ROUNDS=50 (DEEP-02)."
    - "Deep-mode branch assembles an extended system prompt via build_deep_mode_system_prompt() that appends 4 deterministic sections (planning instructions, recitation pattern, sub-agent stub, ask-user stub) to the base prompt — no timestamps, no volatile data (DEEP-05 KV-cache friendliness)."
    - "Deep-mode branch loads write_todos and read_todos as additional tools alongside existing search_documents / query_database / web_search / code execution / skills / MCP — but NOT task / ask_user / write_file / read_file (those land in Phases 18 / 19)."
    - "Every write_todos and read_todos tool call emits a `todos_updated` SSE event AFTER the DB write commits and BEFORE the tool result is appended (D-17, D-18, TODO-03)."
    - "todos_updated event payload format: data: {\"type\": \"todos_updated\", \"todos\": [{\"id\": ..., \"content\": ..., \"status\": ..., \"position\": ...}, ...]}\n\n (D-17)."
    - "On the final iteration (MAX_DEEP_ROUNDS - 1), the loop swaps tools to [] AND injects a system message forcing summarize-and-deliver — the next round produces only text and exits (DEEP-06)."
    - "When the user message is sent with deep_mode=true, the assistant message row created by the loop has messages.deep_mode = true (DEEP-04 / MIG-04)."
    - "All deep-mode LLM payloads route through the existing PII redaction egress filter (D-32, SEC-01 privacy invariant preserved)."
    - "Mid-loop SSE disconnect preserves committed work — existing per-round persistence pattern from chat.py lines 696-700 reused; agent_todos rows are committed by write_todos before the SSE event is emitted, so disconnect after a write keeps the todos (DEEP-07)."
    - "tools_max_iterations reads in chat.py:992 are migrated to settings.max_tool_rounds (D-15) — legacy alias still works for one milestone."
  artifacts:
    - path: "backend/app/routers/chat.py"
      provides: "deep_mode payload field, branch dispatch (run_deep_mode_loop), todos_updated SSE emit, deep_mode persistence on assistant message rows."
      contains: "run_deep_mode_loop"
    - path: "backend/app/services/deep_mode_prompt.py"
      provides: "build_deep_mode_system_prompt(base_prompt: str) -> str — 4-section deterministic deep-mode prompt builder."
      contains: "build_deep_mode_system_prompt"
    - path: "backend/tests/integration/test_deep_mode_chat_loop.py"
      provides: "Integration tests for the deep-mode loop (extended prompt, write/read tools, todos_updated SSE, MAX_DEEP_ROUNDS exhaustion, deep_mode persistence)."
      contains: "test_todos_updated_sse_emitted"
    - path: "backend/tests/integration/test_deep_mode_byte_identical_fallback.py"
      provides: "DEEP-03 invariant test: deep_mode=false path is byte-identical to v1.2 (no extra tools, no extended prompt, no agent_todos writes)."
      contains: "test_deep_mode_off_byte_identical"
  key_links:
    - from: "backend/app/routers/chat.py"
      to: "backend/app/services/deep_mode_prompt.py"
      via: "build_deep_mode_system_prompt() in run_deep_mode_loop"
      pattern: "build_deep_mode_system_prompt"
    - from: "backend/app/routers/chat.py"
      to: "agent_todos_service via tool_registry"
      via: "tool dispatch on deep-mode iterations"
      pattern: "write_todos|read_todos"
    - from: "backend/app/routers/chat.py"
      to: "redaction/egress.py"
      via: "_pii_safe_request wrapper inside the deep-mode branch"
      pattern: "egress|redaction"
---

<objective>
Wire the new Deep Mode branch into `chat.py`. This is the largest plan in Phase 17 — it integrates Plans 17-02 (config) and 17-03 (tools) into a working LLM agent loop and adds:

1. **Endpoint payload field** — `deep_mode: bool = false` on POST /chat (DEEP-01 partial; UI button lands in Plan 17-06).
2. **Branch dispatch** — `run_deep_mode_loop(...)` is a NEW function that mirrors the existing `run_tool_calling_loop(...)` pattern but with `MAX_DEEP_ROUNDS=50`, extended prompt, and deep-mode tools (DEEP-02). Existing standard loop unchanged (DEEP-03 byte-identical).
3. **Extended system prompt** — `backend/app/services/deep_mode_prompt.py` exposes `build_deep_mode_system_prompt(base_prompt)` returning base + 4 deterministic sections (planning instructions, recitation pattern, sub-agent stub, ask-user stub). KV-cache friendly: no timestamps, no volatile state, todo state flows through tools (DEEP-05, TODO-04).
4. **SSE `todos_updated` event** — emitted after every successful write_todos / read_todos call (TODO-03, D-17, D-18). Full snapshot payload (D-17).
5. **Loop exhaustion fallback** — at iteration `MAX_DEEP_ROUNDS - 1`, swap tools to [] and inject "summarize and deliver" system message (DEEP-06).
6. **`messages.deep_mode` persistence** — assistant message rows created in the deep branch carry `deep_mode=true` (DEEP-04, MIG-04 consumer).
7. **Egress filter** — deep-mode payloads route through `_pii_safe_request` (D-32 / privacy invariant).
8. **Mid-loop interrupt safety** — committed work survives SSE disconnect (DEEP-07). Reuses existing per-round persistence pattern (chat.py lines 696-700).
9. **Migrate `tools_max_iterations` reads to `max_tool_rounds`** (D-15 finalization).
10. **Feature gate** — `DEEP_MODE_ENABLED=false` rejects deep_mode=true with HTTP 400.

Wave 3: depends on Plan 17-02 (max_deep_rounds setting) and Plan 17-03 (write_todos / read_todos tools registered).

Output: chat.py edits + new deep_mode_prompt.py module + 2 integration test files.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/STATE.md
@.planning/phases/17-deep-mode-foundation-planning-todos-plan-panel/17-CONTEXT.md
@.planning/phases/17-deep-mode-foundation-planning-todos-plan-panel/17-02-config-loop-caps-and-feature-flag-PLAN.md
@.planning/phases/17-deep-mode-foundation-planning-todos-plan-panel/17-03-write-todos-read-todos-tools-PLAN.md
@backend/app/routers/chat.py
@backend/app/services/redaction/egress.py
@backend/app/services/tool_registry.py
@backend/app/services/agent_todos_service.py

<interfaces>
**Existing chat.py loop signature** (line 373):
```python
async def run_tool_calling_loop(messages, tools, max_iterations, user_id, tool_context, ...):
    ...
    for _iteration in range(max_iterations):
        ...
```

The deep-mode branch is a NEW sibling function `run_deep_mode_loop(...)` with the same shape but:
- max_iterations sourced from `settings.max_deep_rounds`
- tools list extended with `write_todos` / `read_todos` from registry
- system prompt assembled via `build_deep_mode_system_prompt(base)`
- Final iteration injects a forcing system message + empty tool list
- After every successful write_todos / read_todos, the loop emits a `todos_updated` SSE event

**Existing chat.py SSE emit pattern**:
```python
yield f"data: {json.dumps({'type': 'tool_start', ...})}\n\n"
```
The `todos_updated` event follows this pattern.

**Existing per-round persistence (HIST-* / Phase 12)** at chat.py lines 696-700:
- After each iteration's tool_calls complete, a messages row is INSERTed with role='assistant', content=accumulated_text, tool_calls=JSONB(this_iteration's records).
- Phase 17 ADDS: when the request payload had `deep_mode=true`, this row also sets `deep_mode=true` (column added in Plan 17-01 migration 038).

**Existing egress filter** (`_pii_safe_request` in chat.py / redaction/egress.py): wraps the LLM call to ensure no real PII leaks. Used by the standard loop. Deep-mode loop reuses the SAME wrapper — no new egress code.

**Existing dispatch entry** at chat.py around line 200-300 (the `/chat` POST endpoint): currently routes to single-agent or multi-agent path based on agent_service.classify_intent(). We add a NEW front gate: if deep_mode=true, skip classify_intent and dispatch to run_deep_mode_loop. If deep_mode=false, existing behavior unchanged.

**`build_deep_mode_system_prompt` deterministic sections** (per D-09):
1. Planning instructions: "You can plan multi-step work via write_todos/read_todos. Use write_todos to set the full updated list at once."
2. Recitation pattern (TODO-04): "After completing each step, call read_todos to confirm your plan and progress before deciding the next action."
3. Sub-agent stub (Phase 19 placeholder): "Sub-agent delegation tools (`task`) will be available in a future release. For now, do all work in the main loop."
4. Ask-user stub (Phase 19 placeholder): "If you need clarification, the user will provide it in a follow-up message — do not pause mid-loop."

These sections are fixed strings — no f-string interpolation of timestamps / variable state. Todo state flows through the tools, never into this prompt.

**`tools_max_iterations` migration (D-15)**:
- chat.py line 992: `settings.tools_max_iterations` → `settings.max_tool_rounds`.
- chat.py line 886: same migration if applicable to multi-agent path. Verify and migrate.
- Pydantic Settings already has both fields (Plan 17-02). The deprecated alias warning fires only when env TOOLS_MAX_ITERATIONS is set without MAX_TOOL_ROUNDS.
</interfaces>

</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Build deep_mode_prompt.py + write failing chat-loop integration tests</name>
  <files>backend/app/services/deep_mode_prompt.py, backend/tests/integration/test_deep_mode_chat_loop.py, backend/tests/integration/test_deep_mode_byte_identical_fallback.py</files>
  <action>
    Create `backend/app/services/deep_mode_prompt.py`:

    ```python
    """
    Phase 17 / DEEP-05 + TODO-04 — Deep Mode system prompt builder.

    Deterministic, KV-cache-friendly. No timestamps, no volatile state.
    Todo state flows through write_todos/read_todos tools, NOT this prompt.
    """
    from __future__ import annotations

    DEEP_MODE_SECTIONS = """\

    ## Deep Mode — Planning

    You can plan multi-step work via the write_todos and read_todos tools.
    Use write_todos to set the FULL updated todo list at once (full-replacement semantic, max 50 items).
    Each todo has content (the step) and status: pending, in_progress, or completed.
    Set status to in_progress before starting a step; set it to completed when the step is done.

    ## Deep Mode — Recitation Pattern

    After completing each step, call read_todos to confirm your plan and progress before
    deciding the next action. This prevents drift during long sessions.

    ## Deep Mode — Sub-Agent Delegation

    Sub-agent delegation tools (`task`) will be available in a future release.
    For now, do all work in the main loop.

    ## Deep Mode — Asking the User

    If you need clarification, the user will provide it in a follow-up message.
    Do not pause mid-loop — finish your current plan or summarize and stop, then the user can reply.
    """

    def build_deep_mode_system_prompt(base_prompt: str) -> str:
        """Append 4 deterministic Deep Mode sections to the base system prompt."""
        return base_prompt.rstrip() + DEEP_MODE_SECTIONS
    ```

    Then create the test files. Tests for `test_deep_mode_chat_loop.py`:
    - test_deep_mode_endpoint_accepts_payload_field: POST /chat with `{"deep_mode": true, "thread_id": ..., "content": ...}` and DEEP_MODE_ENABLED=true returns 200 SSE.
    - test_deep_mode_disabled_returns_400: DEEP_MODE_ENABLED=false + deep_mode=true → 400 "deep mode disabled".
    - test_extended_system_prompt_contains_planning_section: capture the assembled system prompt sent to LLM (mock OpenRouter); assert "## Deep Mode — Planning" present.
    - test_extended_system_prompt_kv_cache_friendly: assert no current timestamp / no UTC iso string / no volatile values are present in the system prompt; assert that running build_deep_mode_system_prompt twice with same input yields identical bytes.
    - test_write_todos_emits_todos_updated_sse: simulate LLM emitting a write_todos tool_call; assert the SSE stream contains a `todos_updated` event with full snapshot payload.
    - test_read_todos_emits_todos_updated_sse: simulate LLM emitting a read_todos tool_call; assert SSE stream contains `todos_updated`.
    - test_todos_updated_event_format: validate JSON shape `{"type": "todos_updated", "todos": [...]}` and field names match D-17.
    - test_max_deep_rounds_exhaustion_forces_summary: drive LLM to keep emitting tool_calls beyond MAX_DEEP_ROUNDS - 1; assert that on the final iteration tools list is empty AND a "summarize and deliver" system message is appended; assert next iteration produces only text.
    - test_messages_deep_mode_column_set_true: after a deep-mode chat completes, the resulting assistant message row has `deep_mode = true`.
    - test_messages_deep_mode_false_for_standard_chat: a chat with deep_mode=false (or absent) writes assistant rows with deep_mode=false.
    - test_egress_filter_invoked_for_deep_mode: assert the egress filter wrapper is called for every LLM request inside the deep-mode loop.

    Tests for `test_deep_mode_byte_identical_fallback.py`:
    - test_deep_mode_off_no_extended_prompt: with deep_mode=false, the system prompt sent to LLM does NOT contain "## Deep Mode" sections.
    - test_deep_mode_off_no_write_todos_in_tool_list: with deep_mode=false, write_todos and read_todos are NOT in the tools list passed to the LLM.
    - test_deep_mode_off_no_agent_todos_writes: with deep_mode=false, no rows are inserted into agent_todos table.
    - test_deep_mode_off_uses_max_tool_rounds_not_deep_rounds: assert the loop iterates with max_tool_rounds (default 25) cap, not max_deep_rounds (50).
    - test_v12_compatibility_byte_identical: take a curl trace of POST /chat with deep_mode omitted from payload (Phase 12 baseline) and assert the SSE event sequence and system prompt are identical to a pre-Phase-17 baseline (snapshot test).

    All tests should fail at RED (deep-mode branch not implemented).

    Run:
    ```
    cd backend && source venv/bin/activate && pytest tests/integration/test_deep_mode_chat_loop.py tests/integration/test_deep_mode_byte_identical_fallback.py -v
    ```
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && python -c "from app.services.deep_mode_prompt import build_deep_mode_system_prompt; out = build_deep_mode_system_prompt('Base.'); assert '## Deep Mode — Planning' in out and '## Deep Mode — Recitation Pattern' in out; assert build_deep_mode_system_prompt('Base.') == out; print('OK')" | grep -q OK</automated>
  </verify>
  <done>deep_mode_prompt.py exports build_deep_mode_system_prompt; deterministic output. Both integration test files exist with ~16 tests defined; all fail at RED.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Implement run_deep_mode_loop branch in chat.py + payload field + feature gate + SSE event + deep_mode persistence</name>
  <files>backend/app/routers/chat.py</files>
  <action>
    Edit `backend/app/routers/chat.py`. Concrete edits per D-08..D-13, D-17..D-19, D-32, D-15:

    **1. Payload field:** Extend the `ChatRequest` Pydantic model to include `deep_mode: bool = False`. Keep all existing fields unchanged.

    **2. Endpoint front-gate (around the existing /chat handler entry, ~line 200-300):** Add at the top of the handler, AFTER auth resolution and request parsing:

    ```python
    if request.deep_mode:
        if not settings.deep_mode_enabled:
            raise HTTPException(
                status_code=400,
                detail="deep mode disabled",
            )
        # route to deep-mode branch
        return EventSourceResponse(
            run_deep_mode_loop(
                messages=messages,
                user_id=user.id,
                user_email=user.email,
                token=user.token,
                tool_context=tool_context,
                thread_id=request.thread_id,
                deep_mode=True,
            )
        )
    ```

    **3. New function `run_deep_mode_loop(...)` (sibling of `run_tool_calling_loop` at line 373):** Mirrors the existing loop pattern but:
    - `max_iterations = settings.max_deep_rounds` (default 50)
    - System prompt assembled via `build_deep_mode_system_prompt(base_prompt)` from `app.services.deep_mode_prompt`.
    - Tools list = existing standard tools + ToolRegistry.get("write_todos") + ToolRegistry.get("read_todos"). EXCLUDE task/ask_user/write_file/read_file/edit_file/list_files (those land in Phases 18/19).
    - Per-iteration LLM call MUST go through the existing `_pii_safe_request` egress filter wrapper (D-32). Reuse the same wrapper as the standard loop.
    - On final iteration (`_iteration == max_iterations - 1`), AFTER the LLM emits tool_calls, force summary: replace tools = [] and append `{"role": "system", "content": "You have reached the iteration limit. Please summarize what you have completed and deliver a final answer to the user."}`. Next iteration produces only text and exits.
    - Per-round persistence (existing pattern at lines 696-700): when INSERTing the assistant message row for this iteration, set `deep_mode=True` in the row.
    - After every successful tool call to write_todos OR read_todos, after the registry handler returns, emit:
      ```python
      yield f"data: {json.dumps({'type': 'todos_updated', 'todos': result['todos']})}\n\n"
      ```
      (D-17, D-18 — emit AFTER DB commit, BEFORE tool_result event)
    - Egress filter coverage: every LLM request runs through `_pii_safe_request`.

    **4. Migrate `tools_max_iterations` → `max_tool_rounds`** (D-15):
    - chat.py:992 (and line 886 if applicable): replace `settings.tools_max_iterations` → `settings.max_tool_rounds`.
    - The deprecated alias logic in Plan 17-02 keeps legacy env compat.

    **5. Mid-loop interrupt:** No new code needed beyond ensuring `write_todos` commits to DB BEFORE the SSE event is emitted (handler returns the saved list per Plan 17-03; the await-then-yield order naturally satisfies this).

    Run:
    ```
    cd backend && source venv/bin/activate && python -c "from app.main import app; print('OK')"
    cd backend && source venv/bin/activate && pytest tests/integration/test_deep_mode_chat_loop.py tests/integration/test_deep_mode_byte_identical_fallback.py -v
    ```

    All ~16 tests should pass.
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && python -c "from app.main import app; print('OK')" | grep -q OK && pytest tests/integration/test_deep_mode_chat_loop.py tests/integration/test_deep_mode_byte_identical_fallback.py -v 2>&1 | tail -1 | grep -qE "passed"</automated>
  </verify>
  <done>FastAPI app imports cleanly. Deep-mode branch operational. All integration tests pass: payload field, feature gate, extended prompt, todos_updated SSE, MAX_DEEP_ROUNDS exhaustion, deep_mode persistence, egress coverage, byte-identical fallback. tools_max_iterations migration complete.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| client→/chat | Untrusted deep_mode boolean from client; must respect DEEP_MODE_ENABLED feature gate |
| LLM→tool dispatch (deep-mode) | Untrusted LLM emits write_todos/read_todos tool calls; ctx-bound thread_id prevents cross-thread tampering (Plan 17-03 already mitigates) |
| chat-loop→cloud LLM | Real PII must not leak; existing egress filter applies to deep-mode branch |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-17-09 | E (Elevation of Privilege) | deep_mode=true accepted while feature disabled | mitigate | Front-gate check `if request.deep_mode and not settings.deep_mode_enabled: raise HTTPException(400)`; integration test asserts 400 |
| T-17-10 | I (Information Disclosure) | deep-mode payload bypasses egress filter | mitigate | `_pii_safe_request` wrapper applied to every LLM call inside run_deep_mode_loop; integration test asserts wrapper is invoked |
| T-17-11 | D (Denial of Service) | infinite loop above MAX_DEEP_ROUNDS | mitigate | Hard cap at 50 (default); on iteration N-1 tools = [] + summary system message forces terminal text round |

</threat_model>

<verification>
- POST /chat accepts deep_mode field; defaults to false.
- DEEP_MODE_ENABLED=false + deep_mode=true → 400.
- run_deep_mode_loop iterates with max_deep_rounds cap; standard run_tool_calling_loop unaffected.
- Extended prompt assembled via deterministic build_deep_mode_system_prompt; KV-cache stable.
- write_todos and read_todos available as tools in deep mode; absent in standard mode.
- todos_updated SSE event emitted on every successful write/read.
- Loop exhaustion at iteration N-1 forces summary.
- messages.deep_mode column populated correctly per request.
- tools_max_iterations references migrated to max_tool_rounds; legacy alias still works.
- Egress filter coverage verified.
- Mid-loop disconnect preserves committed work (existing per-round persistence pattern).
- ~16 integration tests pass.
- Byte-identical fallback test (deep_mode=false path) PASSES.
</verification>

<success_criteria>
- DEEP-01 (partial — UI button in Plan 17-06): payload field, dispatch, gate.
- DEEP-02: extended loop with MAX_DEEP_ROUNDS cap.
- DEEP-03: byte-identical fallback when deep_mode=false (regression test green).
- DEEP-04: messages.deep_mode persisted per row.
- DEEP-05: KV-cache friendly extended prompt (deterministic sections, no volatile data).
- DEEP-06: loop exhaustion forces summarize-and-deliver.
- DEEP-07: mid-loop interrupt preserves committed work.
- TODO-03: todos_updated SSE event emitted on every write_todos/read_todos.
- TODO-04: recitation pattern present in extended prompt.
- D-32 / SEC-04 invariant: PII egress filter applies to deep-mode payloads.
</success_criteria>

<output>
After completion, create `.planning/phases/17-deep-mode-foundation-planning-todos-plan-panel/17-04-SUMMARY.md`
</output>
