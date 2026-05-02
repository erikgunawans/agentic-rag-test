---
phase: 17-deep-mode-foundation-planning-todos-plan-panel
plan: 03
type: execute
wave: 2
depends_on: [01]
files_modified:
  - backend/app/services/agent_todos_service.py
  - backend/app/services/tool_service.py
  - backend/app/services/tool_registry.py
  - backend/tests/unit/test_agent_todos_service.py
  - backend/tests/integration/test_write_read_todos_tools.py
autonomous: true
requirements: [TODO-02, TODO-03, TODO-05]
must_haves:
  truths:
    - "backend/app/services/agent_todos_service.py exposes async functions write_todos(thread_id, user_id, token, todos) and read_todos(thread_id, user_id, token) -> list[dict]."
    - "write_todos() performs full-replacement: deletes ALL existing rows for thread_id then INSERTS the new list within a single transaction (Supabase RPC delete-then-insert acceptable; D-06)."
    - "write_todos() auto-assigns position from list order (0..N-1, ascending)."
    - "write_todos() truncates to 50 items (D-29 defensive cap) and logs a warning when truncated."
    - "write_todos() uses get_supabase_authed_client(token) — RLS-scoped, NEVER service-role."
    - "read_todos() returns the current list ordered by position ASC, with fields id, content, status, position."
    - "Both functions log audit entries via audit_service.log_action(action='write_todos'|'read_todos', resource_type='agent_todos', resource_id=thread_id) — D-34."
    - "tool_service.execute_tool() routes 'write_todos' and 'read_todos' tool names to the new service via the unified ToolRegistry adapter wrap (D-31, v1.2 D-P13-01 invariant — NO edits to tool_service.py lines 1-1283)."
    - "ToolRegistry.register() entries for write_todos and read_todos appear with correct OpenAI/OpenRouter function-tool schema (parameters, description); registration only fires when settings.tool_registry_enabled is True."
    - "When TOOL_REGISTRY_ENABLED=false, the LLM does not see write_todos/read_todos in the tool catalog (byte-identical fallback for Phase 17 to v1.2 prior behavior, gated by deep_mode flag in Plan 17-04)."
  artifacts:
    - path: "backend/app/services/agent_todos_service.py"
      provides: "Service layer for agent_todos full-replacement write + ordered read."
      contains: "async def write_todos"
    - path: "backend/app/services/tool_service.py"
      provides: "Dispatch wiring for write_todos / read_todos tool names (via registry adapter, no edits to lines 1-1283)."
      contains: "write_todos"
    - path: "backend/app/services/tool_registry.py"
      provides: "Registry entries for write_todos + read_todos with OpenAI function-tool JSON schemas."
      contains: "write_todos"
    - path: "backend/tests/unit/test_agent_todos_service.py"
      provides: "Unit tests for full-replacement semantic, position assignment, truncation cap, audit log call."
      contains: "test_write_todos_full_replacement"
    - path: "backend/tests/integration/test_write_read_todos_tools.py"
      provides: "Integration tests calling tool_service.execute_tool('write_todos', ...) end-to-end against Supabase."
      contains: "test_write_todos_via_execute_tool"
  key_links:
    - from: "backend/app/services/agent_todos_service.py"
      to: "supabase.table('agent_todos')"
      via: "get_supabase_authed_client(token)"
      pattern: "get_supabase_authed_client"
    - from: "backend/app/services/tool_registry.py"
      to: "agent_todos_service.write_todos"
      via: "ToolRegistry.register(...) adapter wrap"
      pattern: "register.*write_todos"
    - from: "backend/app/services/agent_todos_service.py"
      to: "audit_service.log_action"
      via: "audit logging on every mutation/read"
      pattern: "log_action"
---

<objective>
Build the backend service layer + LLM tool registration for `write_todos` and `read_todos` per D-29..D-31 (CONTEXT.md). These are the LLM-facing tools that Deep Mode will dispatch (Plan 17-04 wires them into the loop).

Per D-06: full-replacement semantic — `write_todos(todos)` deletes ALL existing rows for the thread then re-inserts the new list. Avoids partial-update edge cases and matches PRD Feature 1.2.

Per D-29: max 50 todos per thread (defensive cap; truncates with warning).

Per D-30: `read_todos()` is parameterless — returns the current list ordered by position. Per PRD recitation pattern (TODO-04), the deep-mode prompt instructs the agent to call `read_todos` after each step.

Per D-31: registration goes through the v1.2 unified `ToolRegistry` adapter wrap — NO edits to `tool_service.py` lines 1-1283 (preserves the byte-identical fallback invariant).

Per D-34: every call audit-logged via `audit_service.log_action(...)`.

Wave 2: depends on Plan 17-01 (table must exist). Independent of Plan 17-02 (config loop caps); Wave 1 caps don't gate this plan's tests.

Output: agent_todos_service.py + tool_registry registration + unit tests + integration tests.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/STATE.md
@.planning/phases/17-deep-mode-foundation-planning-todos-plan-panel/17-CONTEXT.md
@.planning/phases/17-deep-mode-foundation-planning-todos-plan-panel/17-01-migration-agent-todos-and-deep-mode-PLAN.md
@backend/app/services/tool_service.py
@backend/app/services/tool_registry.py
@backend/app/services/audit_service.py

<interfaces>
**`get_supabase_authed_client(token: str)` (existing helper)** — returns Supabase client whose JWT scopes RLS to `auth.uid()`. Standard pattern across v1.0–v1.2 services.

**`audit_service.log_action(user_id, user_email, action, resource_type, resource_id)` (existing)** — async; called on every mutation in v1.0–v1.2. We use it on both write and read for consistency with v1.0 redaction logging convention.

**`ToolRegistry` (v1.2 D-P13-01)** — `register(name, description, parameters, source, handler, available=True)`. Adapter-wrap idiom: handler is an async function `(params: dict, ctx: ToolContext) -> dict`. ctx exposes `thread_id`, `user_id`, `token`. Registration is conditional on `settings.tool_registry_enabled`. NO edits to `tool_service.py` lines 1-1283; the registry hooks into the existing dispatcher via the v1.2 wrapper that already exists at the bottom of tool_service.py.

**OpenAI/OpenRouter function-tool JSON schema** — used by every existing tool entry. Parameters per OpenAI spec (`type: "object"`, `properties`, `required`).

**`agent_todos` schema (Plan 17-01):** id, thread_id, user_id, content, status, position, created_at, updated_at. RLS enforced on user_id = auth.uid().
</interfaces>

</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Write failing unit + integration tests for service + tool dispatch</name>
  <files>backend/tests/unit/test_agent_todos_service.py, backend/tests/integration/test_write_read_todos_tools.py</files>
  <behavior>
    Unit tests (`test_agent_todos_service.py`) — mock the Supabase client:
    - test_write_todos_full_replacement: pre-existing 3 rows for thread_id, call write_todos with 2 new todos → mock client receives `delete().eq("thread_id", thread_id)` followed by `insert([{...}, {...}])` with `position=0,1`.
    - test_write_todos_assigns_positions_in_order: input list of 3 todos with arbitrary content → INSERTed positions are 0, 1, 2.
    - test_write_todos_truncates_at_50: input list of 60 todos → INSERT batch length is 50; warning logged via caplog.
    - test_write_todos_uses_authed_client: assert get_supabase_authed_client(token) is called and service-role client is NOT.
    - test_write_todos_calls_audit_log: assert audit_service.log_action is awaited with action="write_todos", resource_type="agent_todos", resource_id=thread_id.
    - test_read_todos_returns_ordered_list: mock SELECT returns 3 rows in non-positional order → service returns list sorted by position ASC.
    - test_read_todos_calls_audit_log: assert audit_service.log_action awaited with action="read_todos".
    - test_read_todos_empty: SELECT returns [] → service returns [].

    Integration tests (`test_write_read_todos_tools.py`) — use real Supabase test fixtures:
    - test_write_todos_via_execute_tool: with TOOL_REGISTRY_ENABLED=true, sign in as User A, create thread, call tool_service.execute_tool("write_todos", {"todos": [{"content": "step 1", "status": "pending"}]}, ctx) → DB has 1 row with position=0, content="step 1", status="pending".
    - test_read_todos_via_execute_tool: write 2 todos, call read_todos via execute_tool → returns list of 2 items in position order.
    - test_full_replacement_semantic: write 3 todos, then write 1 todo with different content → DB has exactly 1 row (the latest).
    - test_rls_isolation: User A writes todos to their thread; sign in as User B; User B execute_tool("read_todos", ...) on User A's thread_id → returns [] (RLS blocks; never raises).
    - test_tool_registry_disabled_byte_identical: with TOOL_REGISTRY_ENABLED=false, attempt to invoke write_todos via execute_tool → ToolRegistry has no entry; legacy tool_service path raises a "tool not found" KeyError or returns the existing not-found response (matches v1.2 fallback behavior).

    All tests should fail at RED (services not implemented).
  </behavior>
  <action>
    Create both test files. Use existing pytest fixture conventions in `backend/tests/unit/` and `backend/tests/integration/` (look at `test_tool_registry.py` for v1.2 ToolRegistry test idioms — that's the closest analog).

    Run:
    ```
    cd backend && source venv/bin/activate && \
      pytest tests/unit/test_agent_todos_service.py tests/integration/test_write_read_todos_tools.py -v
    ```
    Expect all tests fail (modules not yet implemented — RED).
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pytest tests/unit/test_agent_todos_service.py tests/integration/test_write_read_todos_tools.py -v 2>&1 | grep -cE "FAILED|ERROR" | grep -q "[1-9]"</automated>
  </verify>
  <done>Both test files exist, ~13 tests defined total, all currently failing (ImportError or AttributeError on missing service / registry entry).</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Implement agent_todos_service.py — write_todos + read_todos + audit logging</name>
  <files>backend/app/services/agent_todos_service.py</files>
  <action>
    Create `backend/app/services/agent_todos_service.py` with the following:

    ```python
    """
    Phase 17 / v1.3 — Agent Todos service (TODO-02, TODO-03, TODO-05).

    Full-replacement write semantic per D-06 (CONTEXT.md):
    write_todos deletes ALL existing rows for thread_id then re-inserts the new list.
    50-item defensive truncation cap (D-29) with warning.
    All operations audit-logged via audit_service.log_action (D-34).
    """
    from __future__ import annotations
    import logging
    from typing import Literal, TypedDict

    from app.db.supabase import get_supabase_authed_client
    from app.services import audit_service

    logger = logging.getLogger(__name__)

    MAX_TODOS_PER_THREAD = 50  # D-29

    TodoStatus = Literal["pending", "in_progress", "completed"]

    class TodoInput(TypedDict):
        content: str
        status: TodoStatus

    class TodoRecord(TypedDict):
        id: str
        content: str
        status: TodoStatus
        position: int

    async def write_todos(
        thread_id: str,
        user_id: str,
        user_email: str,
        token: str,
        todos: list[TodoInput],
    ) -> list[TodoRecord]:
        """Full-replacement write of the per-thread todo list. Returns canonical state."""
        if len(todos) > MAX_TODOS_PER_THREAD:
            logger.warning(
                "write_todos truncating %d -> %d items (thread_id=%s, D-29 cap)",
                len(todos), MAX_TODOS_PER_THREAD, thread_id,
            )
            todos = todos[:MAX_TODOS_PER_THREAD]

        client = get_supabase_authed_client(token)

        # Delete-then-insert (Supabase doesn't expose multi-row UPSERT-by-thread cleanly).
        # RLS already scopes to auth.uid(); the eq() is defense-in-depth.
        client.table("agent_todos").delete().eq("thread_id", thread_id).execute()

        if todos:
            rows = [
                {
                    "thread_id": thread_id,
                    "user_id": user_id,
                    "content": t["content"],
                    "status": t["status"],
                    "position": idx,
                }
                for idx, t in enumerate(todos)
            ]
            client.table("agent_todos").insert(rows).execute()

        # Audit (D-34)
        await audit_service.log_action(
            user_id=user_id,
            user_email=user_email,
            action="write_todos",
            resource_type="agent_todos",
            resource_id=thread_id,
        )

        return await read_todos(thread_id, user_id, user_email, token, _audit=False)

    async def read_todos(
        thread_id: str,
        user_id: str,
        user_email: str,
        token: str,
        *,
        _audit: bool = True,
    ) -> list[TodoRecord]:
        """Return current todo list ordered by position ASC."""
        client = get_supabase_authed_client(token)
        result = (
            client.table("agent_todos")
            .select("id, content, status, position")
            .eq("thread_id", thread_id)
            .order("position")
            .execute()
        )
        rows = result.data or []

        if _audit:
            await audit_service.log_action(
                user_id=user_id,
                user_email=user_email,
                action="read_todos",
                resource_type="agent_todos",
                resource_id=thread_id,
            )
        return rows
    ```

    Note: signature includes `user_email` because audit_service requires it. Plan 17-04 will pass this through from `get_current_user` in chat.py.

    Verify imports cleanly:
    ```
    cd backend && source venv/bin/activate && python -c "from app.services.agent_todos_service import write_todos, read_todos; print('OK')"
    ```
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && python -c "from app.services.agent_todos_service import write_todos, read_todos, MAX_TODOS_PER_THREAD; assert MAX_TODOS_PER_THREAD == 50; print('OK')" | grep -q "OK"</automated>
  </verify>
  <done>Service module imports cleanly, exports write_todos / read_todos / MAX_TODOS_PER_THREAD. No hard dependency on chat.py.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Register write_todos / read_todos via ToolRegistry adapter wrap</name>
  <files>backend/app/services/tool_registry.py, backend/app/services/tool_service.py</files>
  <action>
    Add registry entries for `write_todos` and `read_todos` in `tool_registry.py`. The exact location and shape MUST follow the v1.2 D-P13-01 adapter-wrap pattern — register entries inside the existing `_register_native_tools()` (or equivalent) function that runs only when `settings.tool_registry_enabled` is True. Do NOT edit `tool_service.py` lines 1-1283 (the byte-identical fallback boundary).

    Pseudocode (final form must match the actual idiom in tool_registry.py — read it first):

    ```python
    # Phase 17 / TODO-02 / TODO-05 — register write_todos and read_todos as native tools.
    # Adapter wrap per v1.2 D-P13-01: NO edits to tool_service.py:1-1283.

    from app.services import agent_todos_service

    async def _write_todos_handler(params: dict, ctx) -> dict:
        todos = params.get("todos") or []
        result = await agent_todos_service.write_todos(
            thread_id=ctx.thread_id,
            user_id=ctx.user_id,
            user_email=ctx.user_email,
            token=ctx.token,
            todos=todos,
        )
        return {"todos": result}

    async def _read_todos_handler(params: dict, ctx) -> dict:
        result = await agent_todos_service.read_todos(
            thread_id=ctx.thread_id,
            user_id=ctx.user_id,
            user_email=ctx.user_email,
            token=ctx.token,
        )
        return {"todos": result}

    registry.register(
        name="write_todos",
        description=(
            "Replace the entire per-thread todo list. Use this to plan a multi-step task "
            "or update progress (set status='in_progress' before working on a step, "
            "'completed' after). Pass the full updated list every time — partial updates "
            "are not supported."
        ),
        parameters={
            "type": "object",
            "properties": {
                "todos": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "content": {"type": "string", "description": "Step description"},
                            "status": {
                                "type": "string",
                                "enum": ["pending", "in_progress", "completed"],
                            },
                        },
                        "required": ["content", "status"],
                    },
                    "description": "Full todo list (max 50). Position assigned by order.",
                },
            },
            "required": ["todos"],
        },
        source="native",
        handler=_write_todos_handler,
    )

    registry.register(
        name="read_todos",
        description=(
            "Return the current todo list for this thread. Call after each completed step "
            "to confirm your plan and progress before deciding the next action."
        ),
        parameters={
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        source="native",
        handler=_read_todos_handler,
    )
    ```

    `ctx` must carry `user_email` — if it doesn't already (Phase 13 v1.2 baseline), extend `ToolContext` to include it. Plan 17-04 also depends on this.

    Verify import + registration smoke:
    ```
    cd backend && source venv/bin/activate && \
      TOOL_REGISTRY_ENABLED=true python -c "from app.services.tool_registry import get_registry; reg=get_registry(); names=[t.name for t in reg.list()]; assert 'write_todos' in names and 'read_todos' in names; print('OK')"
    ```

    Re-run all tests:
    ```
    cd backend && source venv/bin/activate && pytest tests/unit/test_agent_todos_service.py tests/integration/test_write_read_todos_tools.py -v
    ```
    All ~13 tests should now PASS.
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pytest tests/unit/test_agent_todos_service.py tests/integration/test_write_read_todos_tools.py -v 2>&1 | grep -E "passed|failed" | tail -1 | grep -qE "passed.*0 failed|^[0-9]+ passed"</automated>
  </verify>
  <done>All ~13 unit + integration tests pass (TDD GREEN). write_todos/read_todos appear in registry when TOOL_REGISTRY_ENABLED=true; absent when off (v1.2 fallback invariant intact).</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| LLM→tool_service | Untrusted LLM input crosses into write_todos params; could attempt to inject thread_id mismatched to ctx.thread_id |
| service→Supabase | service-role bypass would defeat RLS; must use authed client only |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-17-06 | T (Tampering) | LLM passes adversarial thread_id | mitigate | Handler reads thread_id from ctx (server-set) — params payload thread_id is ignored. Schema does not include thread_id parameter. |
| T-17-07 | I (Information Disclosure) | service-role bypass leaks cross-tenant todos | mitigate | agent_todos_service uses get_supabase_authed_client(token) exclusively; unit test asserts service-role client is NEVER instantiated |
| T-17-08 | R (Repudiation) | mutations not auditable | mitigate | Both write_todos AND read_todos call audit_service.log_action with thread_id resource_id, mirroring v1.0–v1.2 mutation audit convention |

</threat_model>

<verification>
- agent_todos_service.py exists with write_todos, read_todos, MAX_TODOS_PER_THREAD = 50.
- ToolRegistry contains entries for write_todos and read_todos when TOOL_REGISTRY_ENABLED=true; absent when off.
- Full-replacement semantic verified end-to-end (write 3 → write 1 → DB has 1).
- Position auto-assignment verified.
- 50-item truncation cap verified with warning log.
- RLS isolation verified (User A todos invisible to User B).
- Audit log call verified for both write and read.
- All ~13 pytest cases pass.
</verification>

<success_criteria>
- TODO-02 covered: write_todos / read_todos LLM tools dispatchable.
- TODO-05 covered: full-replacement semantic enables adaptive replanning (LLM rewrites the whole list mid-execution).
- TODO-03 partially covered: tool dispatch infrastructure ready; SSE event emission lands in Plan 17-04.
- v1.2 byte-identical fallback preserved: tool_service.py lines 1-1283 untouched; registry registration is the sole integration surface.
- SEC-01 enforced through auth-scoped client (RLS already enforced by Plan 17-01 schema).
- D-34 audit logging in place for both tools.
</success_criteria>

<output>
After completion, create `.planning/phases/17-deep-mode-foundation-planning-todos-plan-panel/17-03-SUMMARY.md`
</output>
