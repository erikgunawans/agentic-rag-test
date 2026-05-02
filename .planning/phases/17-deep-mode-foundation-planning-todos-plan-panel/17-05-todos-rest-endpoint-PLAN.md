---
phase: 17-deep-mode-foundation-planning-todos-plan-panel
plan: 05
type: execute
wave: 2
depends_on: [01]
files_modified:
  - backend/app/routers/threads.py
  - backend/tests/integration/test_threads_todos_endpoint.py
autonomous: true
requirements: [TODO-07]
must_haves:
  truths:
    - "GET /threads/{thread_id}/todos returns the current todo list for the authenticated user, ordered by position ASC."
    - "Endpoint uses get_supabase_authed_client(token) — RLS-scoped, never service-role (D-27)."
    - "Endpoint returns 200 OK with body {\"todos\": [...]} where each todo has id, content, status, position."
    - "Endpoint is RLS-scoped: User A cannot read User B's todos via this endpoint (returns [] when thread_id belongs to another user)."
    - "Endpoint is the ONLY new endpoint for agent_todos — no POST/PATCH/DELETE on this surface (D-27): the LLM is the sole writer via write_todos tool."
    - "Endpoint added to existing routers/threads.py (no new router file per D-28)."
    - "Endpoint registered in main.py as part of the existing threads router; no new app.include_router() call needed."
  artifacts:
    - path: "backend/app/routers/threads.py"
      provides: "GET /threads/{thread_id}/todos read-only endpoint."
      contains: "/todos"
    - path: "backend/tests/integration/test_threads_todos_endpoint.py"
      provides: "Integration tests for the todos GET endpoint (auth, ordering, RLS isolation, empty case)."
      contains: "test_get_todos_returns_ordered_list"
  key_links:
    - from: "backend/app/routers/threads.py"
      to: "agent_todos table"
      via: "SELECT through authed Supabase client"
      pattern: "from.*table.*agent_todos"
---

<objective>
Add a single read-only REST endpoint `GET /threads/{thread_id}/todos` to allow the frontend to hydrate the Plan Panel on thread reload (TODO-07). Per D-27, no POST/PATCH/DELETE — the LLM writes through `write_todos` tool only.

Per D-28, endpoint goes into the existing `routers/threads.py` (consistent with how messages are nested under threads). The surface is too small to justify a new `agent_todos.py` router.

Wave 2: depends only on Plan 17-01 (table must exist).

Output: endpoint in threads.py + integration tests.
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
@backend/app/routers/threads.py

<interfaces>
**Existing `threads.py` router** — already exposes thread CRUD + nested `/threads/{id}/messages` GET. New endpoint follows the same pattern: `@router.get("/{thread_id}/todos")` on the existing `router = APIRouter(prefix="/threads", tags=["threads"])`.

**Existing auth dependency `get_current_user`** — returns `{id, email, token, role}`. The endpoint uses `user.token` for the authed Supabase client.

**Existing pattern for nested thread reads** — see how `GET /threads/{thread_id}/messages` is implemented for the exact idiom. Replicate.

**`agent_todos` schema columns** (Plan 17-01): id, thread_id, user_id, content, status, position, created_at, updated_at. Endpoint returns id, content, status, position — same fields the SSE `todos_updated` event uses (D-17) so the frontend reducer can use one shape.
</interfaces>

</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Write failing integration tests for GET /threads/{id}/todos</name>
  <files>backend/tests/integration/test_threads_todos_endpoint.py</files>
  <behavior>
    - test_get_todos_returns_ordered_list: User A creates thread, inserts 3 todos with positions 0, 1, 2 (via direct Supabase client with service-role for setup); GET /threads/{id}/todos with User A's JWT → 200 OK, body {"todos": [...3 items in position order, with id/content/status/position fields...]}.
    - test_get_todos_empty_thread: User A creates thread with no todos → endpoint returns {"todos": []}.
    - test_get_todos_unauthorized_no_token: GET without Authorization header → 401.
    - test_get_todos_rls_isolation_returns_empty: User A creates thread + todos; sign in as User B; GET /threads/{user_a_thread_id}/todos with User B's JWT → 200 OK with {"todos": []} (RLS blocks; doesn't raise — matches v1.0 behavior).
    - test_get_todos_unknown_thread: GET /threads/{nonexistent_uuid}/todos with valid JWT → 200 OK with {"todos": []} OR 404 (whichever matches existing /threads/{id}/messages behavior — replicate).
    - test_get_todos_response_shape: assert each item has exactly the keys {id, content, status, position} — no extra leakage of user_id, thread_id, created_at, updated_at.

    All fail at RED (endpoint not implemented).
  </behavior>
  <action>
    Create `backend/tests/integration/test_threads_todos_endpoint.py`. Use TestClient or httpx.AsyncClient against the FastAPI app, with TEST_EMAIL/TEST_PASSWORD fixture for User A and TEST_EMAIL_2/TEST_PASSWORD_2 for User B (as documented in CLAUDE.md).

    Run:
    ```
    cd backend && source venv/bin/activate && pytest tests/integration/test_threads_todos_endpoint.py -v
    ```
    Expect 6 tests fail (404 on the route — endpoint doesn't exist yet — RED).
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pytest tests/integration/test_threads_todos_endpoint.py -v 2>&1 | grep -cE "FAILED|ERROR" | grep -q "[1-9]"</automated>
  </verify>
  <done>Test file exists, 6 tests defined, all fail (route 404 / not registered).</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Implement GET /threads/{id}/todos in threads.py</name>
  <files>backend/app/routers/threads.py</files>
  <action>
    Add the following endpoint to `backend/app/routers/threads.py` (place near the existing `/threads/{id}/messages` endpoint, follow the same idiom):

    ```python
    @router.get("/{thread_id}/todos")
    async def get_thread_todos(
        thread_id: str,
        user: dict = Depends(get_current_user),
    ):
        """
        Phase 17 / TODO-07 — Hydrate Plan Panel on thread reload.
        Read-only: the LLM is the sole writer via the write_todos tool (D-27).
        RLS-scoped: User A cannot read User B's todos.
        """
        client = get_supabase_authed_client(user["token"])
        result = (
            client.table("agent_todos")
            .select("id, content, status, position")
            .eq("thread_id", thread_id)
            .order("position")
            .execute()
        )
        return {"todos": result.data or []}
    ```

    No edits to `main.py` — `threads_router` is already mounted.

    Run tests:
    ```
    cd backend && source venv/bin/activate && pytest tests/integration/test_threads_todos_endpoint.py -v
    cd backend && source venv/bin/activate && python -c "from app.main import app; print('OK')"
    ```
    All 6 tests should now pass.
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pytest tests/integration/test_threads_todos_endpoint.py -v 2>&1 | grep -q "6 passed" && grep -q "/threads/{thread_id}/todos\|/{thread_id}/todos" backend/app/routers/threads.py</automated>
  </verify>
  <done>Endpoint live, all 6 integration tests pass. RLS isolation verified. No new router or main.py edit needed.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| client→/threads/{id}/todos | Untrusted thread_id from URL; must respect RLS scope |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-17-12 | I (Information Disclosure) | cross-tenant todo read | mitigate | Endpoint uses get_supabase_authed_client(token); RLS policy `user_id = auth.uid()` (Plan 17-01) blocks cross-user reads; integration test asserts User B sees [] |
| T-17-13 | T (Tampering) | client tries to mutate via this surface | mitigate | Endpoint is GET only — no POST/PATCH/DELETE per D-27. LLM-only write surface preserves single-writer semantic |

</threat_model>

<verification>
- GET /threads/{id}/todos returns ordered list, RLS-scoped.
- 6 integration tests pass.
- No new router or main.py edits.
- Endpoint shape matches the SSE todos_updated event (D-17) — frontend reducer can reuse the same item shape.
</verification>

<success_criteria>
- TODO-07 covered: thread reload hydration endpoint operational.
- D-27 / D-28 honored: GET-only, in existing threads.py.
- RLS isolation verified by integration test.
</success_criteria>

<output>
After completion, create `.planning/phases/17-deep-mode-foundation-planning-todos-plan-panel/17-05-SUMMARY.md`
</output>
