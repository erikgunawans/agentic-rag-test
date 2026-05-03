# Phase 19: Sub-Agent Delegation + Ask User + Status & Recovery — Pattern Map

**Mapped:** 2026-05-03
**Files analyzed:** 17 (8 NEW + 7 MODIFIED + 2 NEW frontend test files)
**Analogs found:** 17 / 17 (full coverage — Phase 17 + Phase 18 are direct ancestors)

---

## File Classification

| File | New / Mod | Role | Data Flow | Closest Analog | Match Quality |
|------|-----------|------|-----------|----------------|---------------|
| `supabase/migrations/040_agent_runs.sql` | NEW | migration | DDL + RLS | `supabase/migrations/038_agent_todos_and_deep_mode.sql` (table+RLS+trigger), `036_code_executions_and_sandbox_outputs.sql` (partial unique constraint) | exact |
| `backend/app/services/agent_runs_service.py` | NEW | service | CRUD + state-machine | `backend/app/services/agent_todos_service.py` | exact (mirror Phase 17 service pattern) |
| `backend/app/services/sub_agent_loop.py` | NEW | service | event-driven async generator | `backend/app/routers/chat.py` lines 1545–1993 (`run_deep_mode_loop`) | exact (variant: minus task/write_todos/read_todos, MAX_SUB_AGENT_ROUNDS=15) |
| `backend/app/services/tool_service.py` | MOD (registration only) | tool registry | adapter-wrap | `_register_workspace_tools()` (lines 1595–1647) | exact |
| `backend/app/routers/chat.py` | MOD | router | SSE + state-machine | self (`run_deep_mode_loop` + `stream_chat` entry) | self-extension |
| `backend/app/services/deep_mode_prompt.py` | MOD | service | prompt assembly | self (lines 28–36 stubs) | self-extension |
| `backend/app/config.py` | MOD | config | Pydantic Settings | `workspace_enabled` (line 173–176), `deep_mode_enabled` (line 159–171) | exact |
| `frontend/src/components/chat/AgentStatusChip.tsx` | NEW | component | request-response (state-driven) | `frontend/src/components/chat/AgentBadge.tsx`, `PlanPanel.tsx` (status-icon precedent) | partial (no exact chip analog — synthesize from `DeepModeBadge` + `StatusIcon`) |
| `frontend/src/components/chat/TaskPanel.tsx` | NEW | component | event-driven panel | `frontend/src/components/chat/PlanPanel.tsx` (panel slot + StatusIcon), `WorkspacePanel.tsx` (visibility rule + collapse), `SubAgentPanel.tsx` (mode/doc badges + nested tool calls font-mono row) | exact (compose 3 analogs) |
| `frontend/src/components/chat/MessageView.tsx` | MOD | component | message rendering | self (lines 91–146 assistant bubble path) | self-extension |
| `frontend/src/hooks/useChatState.ts` | MOD | state hook | reducer/state slices | self (Phase 17 `todos` slice + Phase 18 `workspaceFiles` slice) | self-extension |
| `frontend/src/i18n/translations.ts` | MOD | i18n | static strings | self (Phase 17 `planPanel.*` block lines 24–29 / 727–732, Phase 18 `workspace.*` block lines 675–685 / 1378–1388) | exact |
| `backend/tests/integration/test_migration_040_agent_runs.py` | NEW | test | RLS + schema verification | `backend/tests/integration/test_migration_038_agent_todos.py` | exact |
| `backend/tests/services/test_agent_runs_service.py` | NEW | test | service unit | `backend/tests/services/test_workspace_service.py` | exact |
| `backend/tests/integration/test_sub_agent_loop.py` | NEW | test | async-generator integration | `backend/tests/integration/test_deep_mode_chat_loop.py` | exact |
| `frontend/src/components/chat/AgentStatusChip.test.tsx` | NEW | test | Vitest component | `frontend/src/components/chat/CodeExecutionPanel.test.tsx` | exact |
| `frontend/src/components/chat/TaskPanel.test.tsx` | NEW | test | Vitest component | `frontend/src/components/chat/CodeExecutionPanel.test.tsx`, `WorkspacePanel.test.tsx` | exact |

---

## Pattern Assignments

### `supabase/migrations/040_agent_runs.sql` (migration, DDL+RLS)

**Primary analog:** `supabase/migrations/038_agent_todos_and_deep_mode.sql`
**Why:** Same pattern — new table + thread-scoped RLS + reuse of `handle_updated_at` trigger from migration 001 + bundled `messages.*` ALTER. Only twist: D-03 partial-unique constraint (precedent from 036).

**Header pattern** (mirror 038 lines 1–4):
```sql
-- Migration 040: agent_runs table + messages.parent_task_id column
-- Phase 19 / Plan 19-01 — foundation for TASK-04 (paused/resumable runs), ASK-04 (resume detection), STATUS-05 (DB-backed loop state), MIG bundling per D-31.
-- Bundles agent_runs + messages.parent_task_id ALTER per CONTEXT.md D-03 / D-10.
-- Depends on: 039_workspace_files.sql
```

**Table DDL pattern** (mirror 038 lines 9–18 — UUID PK, thread_id FK ON DELETE CASCADE, user_id defense-in-depth, status CHECK, timestamps):
```sql
CREATE TABLE IF NOT EXISTS public.agent_runs (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  thread_id         UUID NOT NULL REFERENCES public.threads(id) ON DELETE CASCADE,
  user_id           UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  status            TEXT NOT NULL CHECK (status IN ('working','waiting_for_user','complete','error')),
  pending_question  TEXT,
  last_round_index  INTEGER NOT NULL DEFAULT 0,
  error_detail      TEXT,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT agent_runs_pending_question_invariant CHECK (
    (status = 'waiting_for_user') = (pending_question IS NOT NULL)
  )
);
```

**Partial UNIQUE index pattern** (D-03 — precedent: 036 has only full-row uniqueness, but Postgres `WHERE`-clause partial-unique is the standard idiom; the closest in-repo precedent is 039's `workspace_files_thread_path_unique`. Plan 19-01 introduces the partial form — codify it):
```sql
CREATE UNIQUE INDEX IF NOT EXISTS idx_agent_runs_thread_active
  ON public.agent_runs(thread_id)
  WHERE status IN ('working','waiting_for_user');
CREATE INDEX IF NOT EXISTS idx_agent_runs_user_created
  ON public.agent_runs(user_id, created_at DESC);
```

**Trigger pattern — REUSE `handle_updated_at`** (mirror 038 lines 30–34, do NOT redefine the function):
```sql
DROP TRIGGER IF EXISTS handle_agent_runs_updated_at ON public.agent_runs;
CREATE TRIGGER handle_agent_runs_updated_at
  BEFORE UPDATE ON public.agent_runs
  FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();
```

**RLS pattern** (mirror 038 lines 39–71 — thread-ownership scope, four policies; D-03 in CONTEXT.md says use `EXISTS (… threads … user_id = auth.uid())` form, but 038's `agent_todos_*` uses `user_id = auth.uid()` directly because user_id is denormalized onto the row. ALSO 039 uses the `IN (SELECT id FROM threads WHERE user_id=auth.uid())` form with super_admin override. Plan 19-01 should follow the 039 pattern because CONTEXT.md D-03 explicitly says "mirrors `workspace_files` D-03"):
```sql
ALTER TABLE public.agent_runs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "agent_runs_select" ON public.agent_runs
  FOR SELECT
  USING (
    thread_id IN (SELECT id FROM public.threads WHERE user_id = auth.uid())
    OR (auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin'
  );

CREATE POLICY "agent_runs_insert" ON public.agent_runs
  FOR INSERT
  WITH CHECK (
    thread_id IN (SELECT id FROM public.threads WHERE user_id = auth.uid())
    OR (auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin'
  );

CREATE POLICY "agent_runs_update" ON public.agent_runs
  FOR UPDATE
  USING (
    thread_id IN (SELECT id FROM public.threads WHERE user_id = auth.uid())
    OR (auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin'
  )
  WITH CHECK (
    thread_id IN (SELECT id FROM public.threads WHERE user_id = auth.uid())
    OR (auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin'
  );

CREATE POLICY "agent_runs_delete" ON public.agent_runs
  FOR DELETE
  USING (
    thread_id IN (SELECT id FROM public.threads WHERE user_id = auth.uid())
    OR (auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin'
  );
```

**`messages.parent_task_id` ALTER** (mirror 038 lines 73–78 — `ADD COLUMN IF NOT EXISTS`, nullable, no default needed):
```sql
ALTER TABLE public.messages
  ADD COLUMN IF NOT EXISTS parent_task_id UUID NULL;
CREATE INDEX IF NOT EXISTS idx_messages_parent_task
  ON public.messages(parent_task_id) WHERE parent_task_id IS NOT NULL;
```

**Pitfalls / anti-patterns:**
- **DO NOT** wrap in `BEGIN; … COMMIT;` (038 doesn't; 039 does — go with 038's pattern since this migration has no storage-bucket coupling).
- **DO NOT** redefine `handle_updated_at` — it lives in `001_initial_schema.sql`. Just `CREATE TRIGGER`.
- **DO NOT** use `user_id = auth.uid()` for RLS (CONTEXT.md D-03 explicitly says use the threads-IN-subquery form to mirror Phase 18 D-03).
- **Wave invariant:** plan 19-01 commits + `supabase db push` BEFORE plans 19-02..N reference the new schema. After commit, PreToolUse hook will block re-edits to migration 040 (currently blocks 001–037; will extend automatically).

---

### `backend/app/services/agent_runs_service.py` (service, CRUD + state-machine)

**Primary analog:** `backend/app/services/agent_todos_service.py`
**Why:** Phase 17 service-layer template for v1.3 thread-scoped agent state. Same RLS-scoped client pattern, same audit-log hook, same `from __future__ import annotations` + `TypedDict` type helpers.

**Module header pattern** (mirror agent_todos_service.py lines 1–36):
```python
"""Phase 19 / v1.3 — Agent Runs service (TASK-04, ASK-04, STATUS-05).

Tracks paused/resumable agent runs per thread (D-03 schema, D-04 resume detection).
Partial-unique constraint enforces at-most-one active run per thread (working|waiting_for_user).

All operations audit-logged via audit_service.log_action (D-23):
  - start_run, transition_status, complete, error → resource_type='agent_runs'

Security:
  - Reads thread_id from server-set ctx, NOT from LLM params.
  - Uses get_supabase_authed_client(token) exclusively (RLS-scoped).

Plan 19-05 wires this into the deep-mode chat loop (resume-detection branch in
stream_chat entry; ask_user pause persistence inside run_deep_mode_loop).
"""
from __future__ import annotations

import logging
from typing import Literal, TypedDict

from app.database import get_supabase_authed_client
from app.services import audit_service

logger = logging.getLogger(__name__)
```

**Type helper pattern** (mirror agent_todos_service.py lines 46–58):
```python
RunStatus = Literal["working", "waiting_for_user", "complete", "error"]

class AgentRunRecord(TypedDict):
    id: str
    thread_id: str
    status: RunStatus
    pending_question: str | None
    last_round_index: int
    error_detail: str | None
```

**RLS-scoped CRUD pattern** (mirror agent_todos_service.py lines 102–132 — `get_supabase_authed_client(token)`, NEVER service-role; `eq()` defense-in-depth even with RLS):
```python
async def start_run(
    thread_id: str,
    user_id: str,
    user_email: str,
    token: str,
) -> AgentRunRecord:
    """Insert a new 'working' run. Partial-unique index enforces at-most-one active row."""
    client = get_supabase_authed_client(token)
    result = client.table("agent_runs").insert({
        "thread_id": thread_id,
        "user_id": user_id,
        "status": "working",
        "last_round_index": 0,
    }).execute()
    audit_service.log_action(
        user_id=user_id, user_email=user_email,
        action="agent_run_start", resource_type="agent_runs",
        resource_id=thread_id,
    )
    return result.data[0]
```

**Resume-detection lookup pattern** (CONTEXT.md D-04 — needs `(thread_id, status='waiting_for_user')` lookup; mirror agent_todos_service.py L159–166 for query shape):
```python
async def get_active_run(thread_id: str, token: str) -> AgentRunRecord | None:
    client = get_supabase_authed_client(token)
    result = (
        client.table("agent_runs")
        .select("id, thread_id, status, pending_question, last_round_index, error_detail")
        .eq("thread_id", thread_id)
        .in_("status", ["working", "waiting_for_user"])
        .maybe_single()
        .execute()
    )
    return result.data
```

**Public API surface** (matches CONTEXT.md D-31 plan 19-02 specification):
- `start_run(thread_id, user_id, user_email, token) -> AgentRunRecord`
- `set_pending_question(run_id, question, last_round_index, token) -> None` (UPDATE WHERE status='working' transactional guard, see D-04)
- `transition_status(run_id, new_status, token, *, error_detail=None) -> None`
- `complete(run_id, token, user_id, user_email) -> None`
- `error(run_id, token, user_id, user_email, *, error_detail) -> None`
- `get_active_run(thread_id, token) -> AgentRunRecord | None` — used by `/chat` resume detection

**Pitfalls:**
- **NEVER instantiate the service-role client** (agent_todos_service.py module docstring line 14 — "service-role client is never instantiated here"). RLS scope only.
- **The transactional UPDATE** for ask-user resume must be `UPDATE … SET status='working' WHERE id=run_id AND status='waiting_for_user'` — protects against the documented v1.3 deferred multi-worker race (deferred-ideas list "Cross-process advisory lock for ask_user resume race conditions").

---

### `backend/app/services/sub_agent_loop.py` (NEW — service, event-driven async generator)

**Primary analog:** `backend/app/routers/chat.py` lines 1545–1993 (`run_deep_mode_loop`)
**Why:** CONTEXT.md L344 explicitly states "near-clone with reduced tool list and lower round cap". Same iteration loop, same egress filter, same per-round persistence, same redaction-aware buffering.

**Function signature** (mirror chat.py L1545–1576 with these reductions):
```python
async def run_sub_agent_loop(
    description: str,                         # NEW — sub-agent's first user message body
    context_files: list[str],                 # NEW — workspace paths to pre-load (D-08)
    parent_user_id: str,                      # inherited from parent (D-22)
    parent_user_email: str,
    parent_token: str,                        # SAME JWT — RLS scope shared (D-22)
    parent_tool_context: dict,                # tool_context inherited
    parent_thread_id: str,
    parent_user_msg_id: str,
    client,
    sys_settings: dict,
    web_search_effective: bool,
    task_id: str,                             # NEW — server-generated UUID (per Specifics)
    parent_redaction_registry,                # NEW — share parent's ConversationRegistry (D-21)
):
    """Phase 19 / TASK-* — Sub-agent inner loop.

    Mirrors run_deep_mode_loop minus:
      - `task` tool (D-09 — no recursion)
      - `write_todos` / `read_todos` (D-09 — todos parent-scoped)

    Capped at MAX_SUB_AGENT_ROUNDS=15 (D-11 forced summary on cap, mirroring DEEP-06).
    Yields parent's SSE events tagged with task_id (D-06).
    """
```

**Tool-list reduction pattern** (mirror chat.py L1607–1626, then filter):
```python
# Build tool list — inherit parent minus task/write_todos/read_todos (D-09)
if settings.tools_enabled and settings.tool_registry_enabled:
    from app.services import tool_registry as _tr
    active_set = _tr.make_active_set()
    full_tools = _tr.build_llm_tools(
        active_set=active_set,
        web_search_enabled=web_search_effective,
        sandbox_enabled=settings.sandbox_enabled,
        agent_allowed_tools=None,
    )
    EXCLUDED = {"task", "write_todos", "read_todos"}
    sub_tools = [t for t in full_tools if t["function"]["name"] not in EXCLUDED]
else:
    sub_tools = [...]
available_tool_names = [t["function"]["name"] for t in sub_tools]
```

**Loop-cap fallback pattern** (mirror chat.py L1673–1684 — DEEP-06 force-summarize on final iteration; CONTEXT.md D-11 says use this exact pattern):
```python
max_iterations = settings.max_sub_agent_rounds  # 15 per config.py:164
for _iteration in range(max_iterations):
    if _iteration == max_iterations - 1 and current_tools:
        loop_messages.append({
            "role": "system",
            "content": (
                "You have reached the iteration limit. "
                "Please summarize what you have completed and deliver "
                "a final answer to the parent agent."
            ),
        })
        current_tools = []
```

**Egress filter pattern** (mirror chat.py L1689–1700 — D-21 reuses parent's registry):
```python
if redaction_on and registry is not None:
    payload = json.dumps(loop_messages, ensure_ascii=False)
    egress_result = egress_filter(payload, registry, None)
    if egress_result.tripped:
        logger.warning("egress_blocked feature=sub_agent_loop ...")
        raise EgressBlockedAbort("sub_agent_loop egress blocked")
```

**First-message shape — D-08 `<context_file>` pre-load** (NEW pattern, no analog — codify here):
```python
def _build_first_user_message(description: str, context_files_content: dict[str, str]) -> str:
    parts = [f"<task>\n{description}\n</task>\n"]
    for path, content in context_files_content.items():
        parts.append(f"\n<context_file path=\"{path}\">\n{content}\n</context_file>\n")
    return "".join(parts)
```

**Failure isolation wrapper — D-12 / TASK-05 / STATUS-04** (NEW pattern; no exact analog. The closest is chat.py L1876–1879 EgressBlockedAbort handling. Codify):
```python
try:
    async for event in _run_sub_agent_loop_inner(...):
        yield event
except Exception as exc:
    logger.error("sub_agent_loop failure task_id=%s exc=%s", task_id, exc, exc_info=True)
    # Structured error returned to parent's tool_result (D-18 shape):
    yield {"_terminal_result": {
        "error": "sub_agent_failed",
        "code": "TASK_LOOP_CRASH",
        "detail": str(exc)[:500],  # D-19 sanitized — no stack trace
    }}
```

**Pitfalls:**
- **DO NOT** emit `agent_status` events from inside the sub-agent (D-07 — only outermost loop).
- **DO** tag every nested `tool_start` / `tool_result` with `task_id` (D-06) — apply at the wrapper boundary, not inside the inner loop.
- **DO NOT** call `audit_service.log_action(...)` with a separate sub-agent identity — D-23: sub-agent tool calls log under parent's `user_id`.
- **DO NOT** persist sub-agent rounds to `messages` without `parent_task_id` (D-10 — required for tree reconstruction).
- **DO NOT** load a fresh `ConversationRegistry` — D-21 reuses parent's so privacy invariant is preserved.

---

### `backend/app/routers/chat.py` (MODIFIED — resume-detection branch + agent_status SSE + task tool dispatch)

**Primary analog:** self — extension of `run_deep_mode_loop` (L1545–1993) and `stream_chat` entry (L244–1259).

**Resume-detection branch** (D-04 — insert at the very top of `stream_chat` body, after thread-ownership validation L252–261, BEFORE history load L263+):
```python
# Phase 19 / D-04: resume-detection branch (gated by SUB_AGENT_ENABLED)
if settings.sub_agent_enabled and settings.deep_mode_enabled:
    from app.services import agent_runs_service
    active_run = await agent_runs_service.get_active_run(body.thread_id, user["token"])
    if active_run and active_run["status"] == "waiting_for_user":
        # body.message → ask_user tool result string; body.deep_mode ignored (D-04)
        return StreamingResponse(
            run_deep_mode_loop(
                ...,
                resume_run_id=active_run["id"],
                resume_tool_result=body.message,
                resume_round_index=active_run["last_round_index"],
            ),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
```

**Deep-mode dispatch (existing, L1232–1254)** — extend `run_deep_mode_loop` signature with optional resume kwargs.

**`agent_status` SSE emission inside `run_deep_mode_loop`** (D-16 — add at four sites mirroring the existing emission patterns):

Site A — loop start (after L1606, before L1633):
```python
yield f"data: {json.dumps({'type':'agent_status','status':'working'})}\n\n"
```

Site B — before ask_user pause + close (NEW path inside tool-call dispatch L1721+):
```python
if func_name == "ask_user":
    question = func_args.get("question", "")
    await agent_runs_service.set_pending_question(
        run_id=run_id, question=question,
        last_round_index=_iteration, token=token,
    )
    yield f"data: {json.dumps({'type':'agent_status','status':'waiting_for_user','detail':question})}\n\n"
    yield f"data: {json.dumps({'type':'ask_user','question':question})}\n\n"
    yield f"data: {json.dumps({'type':'delta','delta':'','done':True})}\n\n"
    return  # close generator cleanly per D-01
```

Site C — final assistant text + done (after L1959–1964):
```python
yield f"data: {json.dumps({'type':'agent_status','status':'complete'})}\n\n"
yield f"data: {json.dumps({'type':'delta','delta':'','done':True})}\n\n"
```

Site D — uncaught exception (extend the L1880–1881 `except Exception` block):
```python
yield f"data: {json.dumps({'type':'agent_status','status':'error','detail':str(exc)[:200]})}\n\n"
```

**`task` tool dispatch + sub-agent SSE forwarding** (D-05/D-06 — add inside the tool-call dispatch loop L1721+, parallel to the existing workspace_updated emission):

Pattern reference: chat.py **L470–632** is the canonical "executor-emitted SSE event queue" pattern (sandbox callback → asyncio.Queue → drain between events). The sub-agent SSE forwarding MUST reuse this exact pattern. Quote (chat.py L484, L511, L519–523, L570, L576–578):
```python
sandbox_event_queue = asyncio.Queue()
# inside callback:
await sandbox_event_queue.put({...event...})
# in main loop, drain between events:
evt = await asyncio.wait_for(sandbox_event_queue.get(), timeout=0.1)
yield f"data: {json.dumps(evt)}\n\n"
while not sandbox_event_queue.empty():
    evt = sandbox_event_queue.get_nowait()
    yield f"data: {json.dumps(evt)}\n\n"
```

For Phase 19 task dispatch (codify):
```python
if func_name == "task":
    task_id = str(uuid.uuid4())
    yield f"data: {json.dumps({'type':'task_start','task_id':task_id,'description':func_args.get('description',''),'context_files':func_args.get('context_files',[])})}\n\n"
    # Sub-agent's inner generator yields events; wrapper tags + forwards.
    sub_gen = run_sub_agent_loop(..., task_id=task_id)
    final_result = None
    async for evt in sub_gen:
        if isinstance(evt, dict) and "_terminal_result" in evt:
            final_result = evt["_terminal_result"]
        else:
            # Tag nested tool_start/tool_result with task_id (D-06)
            tagged = {**evt, "task_id": task_id}
            yield f"data: {json.dumps(tagged)}\n\n"
    if final_result and "error" in final_result:
        yield f"data: {json.dumps({'type':'task_error','task_id':task_id, **final_result})}\n\n"
        tool_output = final_result  # D-12 — structured error returned to parent
    else:
        yield f"data: {json.dumps({'type':'task_complete','task_id':task_id,'result':final_result})}\n\n"
        tool_output = {"result": final_result}
```

**Pitfalls:**
- **DO NOT** modify the standard tool-calling `event_generator` (L373–700+) — Phase 19 features are gated to deep mode only (CONTEXT.md L156 — sub-agent tools "NEVER registered for the standard tool-calling loop").
- **DO NOT** emit nested `agent_status` from inside the sub-agent dispatch — D-07 mandates only outermost emits status.
- **DO** treat `func_name == "ask_user"` as a special early-return inside the dispatch loop — DO NOT continue to the per-round persistence step (`_persist_round_message`) for this round; the persisted state is `agent_runs.last_round_index`, not a messages row.
- **Resume detection is gated by BOTH `sub_agent_enabled` AND `deep_mode_enabled`** (D-17 — when either is off, the resume branch short-circuits).

---

### `backend/app/services/tool_service.py` (REGISTRATION ONLY)

**Primary analog:** `_register_workspace_tools()` (L1595–1647)
**Why:** Phase 18 D-07/D-08 codified the dual-flag-gate registration pattern (`tool_registry_enabled AND workspace_enabled`). Phase 19 D-30 mirrors exactly with `sub_agent_enabled` substituted.

**Pattern to copy verbatim from L1595–1647** with these substitutions:
```python
def _register_sub_agent_tools() -> None:
    """Register the task and ask_user tools as native tools (Phase 19 / D-30).

    Gated by settings.sub_agent_enabled — early return when False so the
    two tools are completely absent from the registry (D-17 kill-switch).
    Only runs when tool_registry_enabled is also True (registry must exist).
    """
    if not settings.tool_registry_enabled:
        return
    if not settings.sub_agent_enabled:
        return

    from app.services import tool_registry  # noqa: PLC0415

    tool_registry.register(
        name="task",
        description=_TASK_SCHEMA["function"]["description"],
        schema=_TASK_SCHEMA,
        source="native",
        loading="immediate",
        executor=_task_executor,
    )
    tool_registry.register(
        name="ask_user",
        description=_ASK_USER_SCHEMA["function"]["description"],
        schema=_ASK_USER_SCHEMA,
        source="native",
        loading="immediate",
        executor=_ask_user_executor,
    )

# Run at module load. No-op when sub_agent_enabled or tool_registry_enabled is False.
_register_sub_agent_tools()
```

**Schema constants** — copy verbatim from CONTEXT.md D-28 / D-29 into module-level `_TASK_SCHEMA` / `_ASK_USER_SCHEMA` dicts (mirror `_WORKSPACE_WRITE_FILE_SCHEMA` shape from L1499–1523).

**Executor signature pattern** (mirror `_workspace_write_file_executor` L1388–1416):
```python
async def _task_executor(
    arguments: dict,
    user_id: str,
    context: dict | None = None,
    *,
    token: str | None = None,
    **kwargs,
) -> dict:
    """Executor: task → run_sub_agent_loop wrapper. Returns final result OR structured error."""
    # Note: actual sub-agent SSE event forwarding happens at chat.py wrapper boundary,
    # not here — this executor returns only the FINAL result that becomes the parent's
    # tool_output. Live SSE events bubble up via the chat.py task dispatch path.
    ...

async def _ask_user_executor(
    arguments: dict,
    user_id: str,
    context: dict | None = None,
    *,
    token: str | None = None,
    **kwargs,
) -> dict:
    """Executor: ask_user → resume-pause sentinel.

    Returns a sentinel dict that signals the chat.py loop to:
    1. Persist agent_runs.status='waiting_for_user'
    2. Emit ask_user SSE
    3. Yield done + return from generator (D-01)
    The sentinel is consumed at the chat.py wrapper, NOT propagated as a normal tool_output.
    """
    return {"_ask_user_pause": True, "question": arguments.get("question", "")}
```

**Pitfalls — CRITICAL — D-P13-01 ADAPTER-WRAP INVARIANT (v1.2):**
- **DO NOT EDIT lines 1–1283** of `tool_service.py`. The adapter-wrap invariant (chat.py L1304–1311 docstring + Phase 13 D-P13-01) requires that all native-tool registration be additive splices BELOW the existing `_register_natives_with_registry()` block (L1312–1363). Plan 19-04's only diff to `tool_service.py` is appending the new schemas + `_register_sub_agent_tools()` block, mirroring how `_register_workspace_tools()` was appended in Phase 18.
- **DO NOT** add `task` or `ask_user` to the `TOOL_DEFINITIONS` dict (lines 1–1283). They are registered exclusively through the adapter wrap — they MUST NOT appear in the legacy native `execute_tool()` dispatch path.
- **DO NOT** dispatch `ask_user` like a regular tool — it's a pause sentinel; the chat.py wrapper detects `tool_output.get("_ask_user_pause")` and short-circuits to the close-and-resume protocol.

---

### `backend/app/services/deep_mode_prompt.py` (MODIFIED — replace stubs)

**Primary analog:** self (lines 28–36 STUBS).
**Why:** Phase 17 D-09 documented these as Phase 19 placeholders; Phase 19 plan 19-08 swaps them for real guidance.

**Replace lines 28–36 of `DEEP_MODE_SECTIONS`** (keep KV-cache stable — same section count, no timestamps, deterministic). New copy guidance per CONTEXT.md D-20 (no auto retries, LLM-driven recovery):

```python
DEEP_MODE_SECTIONS = """\

## Deep Mode — Planning
[unchanged — lines 16–22]

## Deep Mode — Recitation Pattern
[unchanged — lines 24–26]

## Deep Mode — Sub-Agent Delegation

Use the `task(description, context_files)` tool to delegate focused work to a sub-agent
with isolated context. The sub-agent shares your workspace (read+write) but has its own
message history. Use it for: scoped research, single-pass analysis, or any work where
isolating context would clarify the task. The sub-agent cannot recursively call task,
write_todos, or read_todos. Sub-agent failures are returned as structured tool errors
— your loop continues. Limit: 15 sub-agent rounds per delegation.

## Deep Mode — Asking the User

Use the `ask_user(question)` tool ONLY when you genuinely need user clarification to
proceed. The loop pauses; the user's next message is delivered as this tool's result,
verbatim. If their reply doesn't directly answer, you may call ask_user again or
proceed with what they said. Do not use for status updates or rhetorical pauses.

## Deep Mode — Error Recovery

When a tool call fails it returns a structured error result like
{"error": "...", "code": "...", "detail": "..."}. Read the error, then decide:
retry with different inputs, try an alternative tool, or escalate via ask_user.
There is no automatic retry. Every recovery decision is your choice and is visible
in the conversation transcript.
"""
```

**Pitfalls:**
- **Function signature unchanged** (CONTEXT.md L349 — KV-cache stability). `build_deep_mode_system_prompt(base_prompt) -> str` MUST remain the same.
- **Determinism invariant** — no timestamps, no thread/user-specific data inside the prompt body. Tests assert `build_deep_mode_system_prompt(p) == build_deep_mode_system_prompt(p)`.
- **Section count is 5 now (was 4)** — update the docstring at L6–10. The KV-cache concern is content stability, not section count.

---

### `backend/app/config.py` (MODIFIED — add `sub_agent_enabled`)

**Primary analog:** `workspace_enabled` (lines 173–176) and `deep_mode_enabled` (lines 159–171)
**Why:** Identical dark-launch flag pattern. Plain Pydantic `bool` field with `default=False`.

**Add immediately after `workspace_enabled` (L176)**:
```python
# Phase 19 / v1.3 (TASK-*, ASK-*, STATUS-*; D-17): Sub-Agent Delegation feature flag.
# When False: task and ask_user tools NOT registered, agent_runs unused, resume-detection
# branch in /chat short-circuits, no task_*/agent_status SSE events emitted. Default OFF —
# opt-in via SUB_AGENT_ENABLED env var. Mirrors WORKSPACE_ENABLED dark-launch precedent.
sub_agent_enabled: bool = False
```

**Pitfalls:**
- **DO NOT** add a `model_validator` for this flag — D-17 explicitly couples it with `deep_mode_enabled` at runtime (chat.py gating), not at config-validation time. A validator would force operators to set both env vars together — over-rigid.
- **DO NOT** export through `system_settings` (single-row DB-backed config) — this is a deployment knob, like `max_sub_agent_rounds` (config.py:164 comment line 161: "Env-driven (NOT system_settings) — these are deployment knobs").

---

### `frontend/src/components/chat/AgentStatusChip.tsx` (NEW — component, state-driven)

**Primary analogs (compose):**
- `frontend/src/components/chat/AgentBadge.tsx` (DeepModeBadge) — chip styling + lucide icon precedent
- `frontend/src/components/chat/PlanPanel.tsx` lines 34–60 — `StatusIcon` color/animation pattern
- UI-SPEC.md §"AgentStatusChip" — full visual contract

**Imports pattern** (mirror PlanPanel.tsx L24–30):
```tsx
import { useEffect, useState } from 'react'
import { MessageCircleQuestion, CheckCircle2, AlertCircle } from 'lucide-react'
import { useI18n } from '@/i18n/I18nContext'
import { useChatContext } from '@/contexts/ChatContext'
import { cn } from '@/lib/utils'
```

**Status-icon switch pattern** (mirror PlanPanel.tsx StatusIcon L34–60 — same icon+color idiom):
```tsx
function ChipIcon({ status }: { status: AgentStatus }) {
  if (status === 'working') {
    return <span className="h-1 w-1 rounded-full bg-primary animate-pulse" aria-hidden="true" />
  }
  if (status === 'waiting_for_user') {
    return <MessageCircleQuestion size={14} className="text-purple-600 dark:text-purple-400" aria-hidden="true" />
  }
  if (status === 'complete') {
    return <CheckCircle2 size={14} className="text-green-600 dark:text-green-400" aria-hidden="true" />
  }
  return <AlertCircle size={14} className="text-red-600 dark:text-red-400" aria-hidden="true" />
}
```

**Visibility-rule + auto-fade pattern** (UI-SPEC §"Auto-fade implementation" + AgentBadge.tsx visibility precedent):
```tsx
export function AgentStatusChip() {
  const { t } = useI18n()
  const { agentStatus, setAgentStatus } = useChatContext()

  useEffect(() => {
    if (agentStatus === 'complete') {
      const timer = setTimeout(() => setAgentStatus(null), 3000)  // UI-SPEC L139
      return () => clearTimeout(timer)
    }
  }, [agentStatus, setAgentStatus])

  if (agentStatus === null) {
    // UI-SPEC L147: keep aria-live container in DOM for reliable announcements
    return <div role="status" aria-live="polite" className="sr-only" />
  }

  const labelKey = `agentStatus.${
    agentStatus === 'waiting_for_user' ? 'waitingForUser' : agentStatus
  }` as const

  return (
    <div
      role="status"
      aria-live="polite"
      aria-label={t(labelKey)}
      className={cn(
        'inline-flex items-center gap-2 px-2 py-1 rounded-full',
        'border border-current/20 transition-all duration-200',
        agentStatus === 'working' && 'bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300',
        agentStatus === 'waiting_for_user' && 'bg-purple-50 dark:bg-purple-950/40 text-purple-700 dark:text-purple-300',
        agentStatus === 'complete' && 'bg-green-50 dark:bg-green-950/40 text-green-700 dark:text-green-300',
        agentStatus === 'error' && 'bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-300',
      )}
    >
      <ChipIcon status={agentStatus} />
      <span className="text-sm font-semibold">{t(labelKey)}</span>
    </div>
  )
}
```

**Pitfalls:**
- **NO `backdrop-blur`** — chip is rendered in a sticky chat-header slot (UI-SPEC L455 — `sticky top-0 z-10`); could be perceived as overlay-ish but UI-SPEC explicitly bans glass on this surface (CLAUDE.md persistent-panel rule extends to header chips).
- **DO NOT** render in `AppLayout.tsx` directly — UI-SPEC L455 says "Do NOT add it inside AppLayout.tsx itself … render at the top of the chat column". The chip is chat-route specific.
- **`sr-only` aria-live container MUST stay in the DOM when null** (UI-SPEC L147) — otherwise screen readers miss the next state change.

---

### `frontend/src/components/chat/TaskPanel.tsx` (NEW — component, event-driven panel)

**Primary analogs (compose):**
1. `WorkspacePanel.tsx` — visibility rule (L120: `if (files.length === 0) return null`), `<aside>` shape (L154–161), header with collapse toggle (L162–176), `bg-background` panel surface
2. `PlanPanel.tsx` — `StatusIcon` 16px icons with same colors (L34–60), collapse pattern (L91–102), `bg-background border-l border-border/50 w-72 shrink-0`
3. `SubAgentPanel.tsx` — mode/source badge styling (L36–46: `rounded-full bg-zinc-200 dark:bg-zinc-800 px-2 py-0.5 text-[11px]`), nested tool calls list (L52–61: `font-mono text-[11px]` + `text-[10px] opacity-60` for tool_call_id)

**Imports pattern** (mirror WorkspacePanel.tsx L24–37):
```tsx
import { useState } from 'react'
import { ChevronDown, ChevronRight, Loader2, CheckCircle2, AlertCircle } from 'lucide-react'
import { useI18n } from '@/i18n/I18nContext'
import { useChatContext } from '@/contexts/ChatContext'
import { cn } from '@/lib/utils'
```

**Visibility rule + `<aside>` shell** (mirror WorkspacePanel.tsx L112–177 + PlanPanel.tsx L77–103 — composite):
```tsx
export function TaskPanel() {
  const { t } = useI18n()
  const { tasks } = useChatContext()
  const [collapsed, setCollapsed] = useState(false)

  // Visibility rule (UI-SPEC L159 — same as WorkspacePanel L120)
  if (tasks.size === 0) return null

  return (
    <aside
      role="complementary"
      data-testid="task-panel"
      aria-label={t('taskPanel.title')}
      className={cn(
        'flex flex-col w-72 shrink-0 border-l border-border/50',
        'bg-background',  // CLAUDE.md persistent-panel rule — NO backdrop-blur
      )}
    >
      <div className="flex items-center justify-between px-4 py-3 border-b border-border/50">
        <h3 className="text-sm font-semibold text-foreground">
          {t('taskPanel.title')}{' '}
          <span className="text-muted-foreground font-normal">({tasks.size})</span>
        </h3>
        <button
          type="button"
          onClick={() => setCollapsed((c) => !c)}
          aria-label={collapsed ? t('taskPanel.expand') : t('taskPanel.collapse')}
          className="flex h-6 w-6 items-center justify-center rounded hover:bg-accent transition-colors text-muted-foreground"
        >
          {collapsed ? <ChevronRight size={14} /> : <ChevronDown size={14} />}
        </button>
      </div>
      {!collapsed && (
        <div className="flex-1 overflow-y-auto px-4 py-3">
          <ul className="space-y-2">
            {[...tasks.values()].map((task) => <TaskCard key={task.taskId} task={task} />)}
          </ul>
        </div>
      )}
    </aside>
  )
}
```

**Task card pattern** (compose SubAgentPanel.tsx L36–61 + PlanPanel StatusIcon L34–60):
```tsx
function TaskStatusIcon({ status }: { status: TaskState['status'] }) {
  if (status === 'running')  return <Loader2     size={16} className="animate-spin text-purple-500 shrink-0" aria-hidden="true" />
  if (status === 'complete') return <CheckCircle2 size={16} className="text-green-500 shrink-0" aria-hidden="true" />
  return                         <AlertCircle    size={16} className="text-red-500 shrink-0" aria-hidden="true" />
}

function TaskCard({ task }: { task: TaskState }) {
  return (
    <li
      className="rounded-lg border bg-muted/40 p-3 text-sm space-y-2"
      aria-label={`${task.status}: ${task.description.slice(0, 60)}`}
    >
      <div className="flex items-start gap-2">
        <TaskStatusIcon status={task.status} />
        <span className="text-sm text-foreground leading-tight">{task.description}</span>
      </div>
      {task.contextFiles.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {task.contextFiles.map((p) => (
            <span key={p} title={p}
              className="rounded-full bg-zinc-200 dark:bg-zinc-800 px-2 py-1 text-[11px] max-w-[120px] truncate">
              {p}
            </span>
          ))}
        </div>
      )}
      {task.toolCalls.length > 0 && (
        <ul className="space-y-1 pl-4">
          {task.toolCalls.map((c) => (
            <li key={c.toolCallId} className="flex items-center gap-2 text-muted-foreground">
              <span className="font-mono text-[11px]">{c.tool}</span>
              <span className="text-[10px] opacity-60">{c.toolCallId}</span>
            </li>
          ))}
        </ul>
      )}
      {task.status === 'complete' && task.result && (
        <p className="text-xs text-muted-foreground line-clamp-2">{task.result}</p>
      )}
      {task.status === 'error' && task.error && (
        <p className="text-xs text-red-600 dark:text-red-400 line-clamp-2">{task.error.detail ?? task.error.error}</p>
      )}
    </li>
  )
}
```

**Pitfalls:**
- **DO NOT extend `SubAgentPanel.tsx`** (UI-SPEC L212 + L459 — "SubAgentPanel.tsx is NOT modified. It remains the history-reload renderer for v1.0 multi-agent classifier tool calls. TaskPanel is a new independent component"). They coexist.
- **NO `backdrop-blur`** — UI-SPEC L161 + CLAUDE.md persistent-panel rule.
- **DO NOT auto-hide on all-complete** — UI-SPEC L200: "When all tasks are `complete` or `error` (no `running` tasks), the panel remains visible until the thread is changed".
- **Render in `ChatPage.tsx` (or route component), NOT `AppLayout.tsx`** — UI-SPEC L457: rendered to the right of `WorkspacePanel` in the same flex row.

---

### `frontend/src/components/chat/MessageView.tsx` (MODIFIED — question-bubble variant)

**Primary analog:** self (lines 91–146 — assistant bubble path).

**Detection logic** (D-27 — derive `isAskUserQuestion` from existing `tool_calls` JSONB; UI-SPEC L219–220):
```tsx
function isAskUserQuestion(msg: Message, toolResults: ToolResultEvent[]): { is: boolean; question?: string } {
  const calls = msg.tool_calls?.calls ?? []
  for (const c of calls) {
    if (c.tool === 'ask_user') {
      const matched = toolResults.some((tr) => tr.tool === 'ask_user' /* + tool_call_id linkage if available */)
      if (!matched) {
        const q = (c.input as { question?: string } | undefined)?.question ?? ''
        return { is: true, question: q }
      }
    }
  }
  return { is: false }
}
```

**Variant render block** (UI-SPEC L237–241 verbatim — insert after the existing `<div className="rounded-lg px-4 py-2 ...">` bubble at MessageView.tsx L116–124, when `isAskUserQuestion.is === true`):
```tsx
{askUser.is && askUser.question && (
  <div
    role="note"
    aria-label={t('askUser.questionBubble.ariaLabel')}
    className="flex items-start gap-2 border-l-[3px] border-primary pl-3 mt-2"
  >
    <MessageCircleQuestion size={16} className="text-primary shrink-0 mt-1" aria-hidden="true" />
    <p className="text-sm text-foreground leading-relaxed">{askUser.question}</p>
  </div>
)}
```

**Pitfalls:**
- **No DB or schema change required** — UI-SPEC L461: "isAskUserQuestion flag is derived at render time from the message's tool_calls JSONB content. No new DB columns or message fields are needed."
- **Render the question AFTER any normal assistant content** — UI-SPEC L235: "If the assistant message has additional text content before the tool call, render both: content first (normal), then the question-bubble block below."
- **Form-duplication rule (CLAUDE.md):** MessageView.tsx is NOT a form — there is no mobile/desktop branch in this file. The CLAUDE.md form-duplication rule applies to `DocumentCreationPage`, not chat surfaces. No duplication needed.
- **DO NOT** introduce a "reply mode" UI — UI-SPEC L394: "input box remains normal (no special 'reply mode')".

---

### `frontend/src/hooks/useChatState.ts` (MODIFIED — `agentStatus` and `tasks` slices)

**Primary analog:** self — Phase 17 `todos` slice (L60) and Phase 18 `workspaceFiles` slice (L70).

**Type definitions** (mirror `WorkspaceFile` definition at L10–16):
```ts
// Phase 19 / D-24
export type AgentStatus = 'working' | 'waiting_for_user' | 'complete' | 'error' | null

export type TaskToolCall = {
  toolCallId: string
  tool: string
  input?: Record<string, unknown>
  output?: Record<string, unknown> | string
}

export type TaskState = {
  taskId: string
  description: string
  contextFiles: string[]
  toolCalls: TaskToolCall[]
  status: 'running' | 'complete' | 'error'
  result?: string
  error?: { error: string; code: string; detail?: string }
}
```

**Slice declarations** (mirror `todos` at L60 and `workspaceFiles` at L70):
```ts
// Phase 19 / D-24 — Header chip status
const [agentStatus, setAgentStatus] = useState<AgentStatus>(null)
// Phase 19 / D-24 — Sub-agent task panel state (Map keyed by task_id)
const [tasks, setTasks] = useState<Map<string, TaskState>>(new Map())
```

**SSE handler additions** (mirror the existing `else if (event.type === 'todos_updated')` block at L337–341 and `workspace_updated` at L342–374 — add a parallel block for `agent_status`, `task_start`, `tool_start` (with task_id), `tool_result` (with task_id), `task_complete`, `task_error`, `ask_user`):
```ts
} else if (event.type === 'agent_status') {
  setAgentStatus(event.status)
} else if (event.type === 'task_start') {
  setTasks((prev) => {
    const next = new Map(prev)
    next.set(event.task_id, {
      taskId: event.task_id,
      description: event.description,
      contextFiles: event.context_files ?? [],
      toolCalls: [],
      status: 'running',
    })
    return next
  })
} else if (event.type === 'tool_start' && 'task_id' in event && event.task_id) {
  setTasks((prev) => {
    const next = new Map(prev)
    const t = next.get(event.task_id)
    if (t) next.set(event.task_id, { ...t, toolCalls: [...t.toolCalls, { toolCallId: event.tool_call_id ?? '', tool: event.tool, input: event.input }] })
    return next
  })
} else if (event.type === 'task_complete') {
  setTasks((prev) => {
    const next = new Map(prev)
    const t = next.get(event.task_id)
    if (t) next.set(event.task_id, { ...t, status: 'complete', result: event.result })
    return next
  })
} else if (event.type === 'task_error') {
  setTasks((prev) => {
    const next = new Map(prev)
    const t = next.get(event.task_id)
    if (t) next.set(event.task_id, { ...t, status: 'error', error: { error: event.error, code: event.code, detail: event.detail } })
    return next
  })
}
```

**Reset-on-thread-switch pattern** (mirror L96–113 todos reset and L118–126 workspaceFiles reset — clear `agentStatus` and `tasks` when `activeThreadId` changes):
```ts
useEffect(() => {
  setAgentStatus(null)
  setTasks(new Map())
}, [activeThreadId])
```

**Reset on send** (mirror L223–231 — clear at send-start so prior turn's tasks/chip don't leak):
```ts
// Inside sendMessageToThread, alongside setActiveTools([]) etc.
setAgentStatus(null)
setTasks(new Map())
```

**Return-tuple addition** (mirror L437–466 — append new fields to the returned object):
```ts
agentStatus,                 // Phase 19 / D-24
setAgentStatus,              // Phase 19 — used by AgentStatusChip auto-fade effect
tasks,                       // Phase 19 / D-24
```

**Pitfalls:**
- **`tool_start` and `tool_result` events are POLYMORPHIC after Phase 19** — when `task_id` is present, route to the tasks slice; otherwise, fall through to the existing `setActiveTools` / `setToolResults` paths (L287–295). DO NOT remove the existing fall-through.
- **Map<>** keyed by `task_id` (UI-SPEC L181) — never replace with array; lookup-by-id required for nested tool-call updates.
- **`SSEEvent` union must be extended** in `frontend/src/lib/database.types.ts` — add `agent_status`, `task_start`, `task_complete`, `task_error`, `ask_user`, plus optional `task_id` field on existing `tool_start` / `tool_result` event variants. (No analog file shown; pattern is in `database.types.ts` per Phase 17 + 18 precedent.)

---

### `frontend/src/i18n/translations.ts` (MODIFIED — ID + EN strings)

**Primary analog:** self (Phase 17 `planPanel.*` block at L24–29 / L727–732, Phase 18 `workspace.*` block at L675–685 / L1378–1388).

**Insertion pattern** — add a `// Phase 19` block adjacent to the Phase 18 block in BOTH locales (ID locale ends ~line 706, EN locale starts line 707).

**ID locale** (insert after line ~688, before the locale boundary at line 706):
```ts
// Phase 19 / TASK-07 / ASK-02 / STATUS-01 / STATUS-05 — AgentStatusChip + TaskPanel + question-bubble
'agentStatus.working': 'Agen sedang bekerja',
'agentStatus.waitingForUser': 'Agen menunggu balasan Anda',
'agentStatus.complete': 'Selesai',
'agentStatus.error': 'Terjadi kesalahan — ulangi?',
'taskPanel.title': 'Sub-agen',
'taskPanel.collapse': 'Sembunyikan',
'taskPanel.expand': 'Tampilkan',
'taskPanel.status.running': 'Sedang berjalan',
'taskPanel.status.complete': 'Selesai',
'taskPanel.status.error': 'Error',
'taskPanel.contextFiles': 'Berkas konteks',
'askUser.questionBubble.ariaLabel': 'Pertanyaan dari agen',
```

**EN locale** (insert after line ~1390 — symmetric to ID block):
```ts
'agentStatus.working': 'Agent working',
'agentStatus.waitingForUser': 'Agent waiting for your reply',
'agentStatus.complete': 'Complete',
'agentStatus.error': 'Error — retry?',
'taskPanel.title': 'Sub-agents',
'taskPanel.collapse': 'Collapse',
'taskPanel.expand': 'Expand',
'taskPanel.status.running': 'Running',
'taskPanel.status.complete': 'Complete',
'taskPanel.status.error': 'Error',
'taskPanel.contextFiles': 'Context files',
'askUser.questionBubble.ariaLabel': 'Question from agent',
```

**Pitfalls:**
- **Both locales must be updated together** — Phase 17 / 18 both ship ID + EN in the same commit. Skipping one will surface as a missing-key fallback (ID strings appearing in the EN UI).
- **Key naming convention** — flat dotted keys (`'taskPanel.title'`, NOT `'taskPanel': { 'title': ... }`); matches existing `planPanel.*` and `workspace.*` shape.
- **Verbatim copy from UI-SPEC §"Phase 19 i18n Key Additions"** — the gsd-ui-checker has APPROVED these strings. DO NOT paraphrase.

---

### `backend/tests/integration/test_migration_040_agent_runs.py` (NEW — RLS + schema)

**Primary analog:** `backend/tests/integration/test_migration_038_agent_todos.py`
**Why:** Same test class — schema verification + RLS regression for a new RLS-scoped table. Phase 17 codified the pattern (functional INSERT/SELECT assertions, NOT information_schema introspection — see L13–14 of the analog: "Tests 1–4 use functional assertions … Supabase PostgREST only exposes the public schema").

**Helper pattern** (copy from analog L53–80 verbatim — `_login`, `_get_user_id`, `_create_thread_svc`, `_delete_thread_svc`):
```python
def _login(email: str, password: str) -> str:
    client = get_supabase_client()
    result = client.auth.sign_in_with_password({"email": email, "password": password})
    return result.session.access_token
```

**Test list** (covered cases for Phase 19):
1. `test_agent_runs_table_exists_with_expected_columns` — INSERT a minimal row through authed client, SELECT it back.
2. `test_agent_runs_partial_unique_constraint_active_run` — INSERT working row, attempt second working row in same thread → assert IntegrityError on unique idx.
3. `test_agent_runs_pending_question_invariant` — attempt INSERT `status='waiting_for_user'` with NULL `pending_question` → CHECK violation.
4. `test_agent_runs_status_check_constraint` — attempt INSERT bad status string → CHECK violation.
5. `test_agent_runs_handle_updated_at_trigger` — UPDATE row, assert `updated_at` advanced.
6. `test_agent_runs_rls_user_isolation` — User A inserts row, User B SELECT returns 0 rows. (mirrors analog L86+ pattern verbatim with `agent_runs` substituted)
7. `test_messages_parent_task_id_column_exists` — INSERT message with `parent_task_id` set, SELECT back.

**Pitfalls (from analog observations 7943, 8130 — already codified):**
- **DO NOT query information_schema or pg_indexes directly** — PostgREST does not expose these. Use functional INSERT/SELECT assertions.
- **Test must apply post-migration only** — pre-migration the file fails with HTTP 404 / `relation "agent_runs" does not exist`. Document in module docstring (mirror analog L17–25).
- **Always clean up** — DELETE thread row in fixture teardown (cascade deletes `agent_runs` rows automatically via `ON DELETE CASCADE`).

---

### `backend/tests/services/test_agent_runs_service.py` (NEW — service unit)

**Primary analog:** `backend/tests/services/test_workspace_service.py`
**Why:** Same scope — service-layer CRUD operations against a real Supabase test project; user JWT login + per-test thread fixture; teardown via service-role.

**Pattern** — copy fixture/teardown shape from analog. Test cases:
1. `start_run_creates_working_row`
2. `set_pending_question_transitions_to_waiting_for_user`
3. `transition_status_completes_run`
4. `error_run_records_error_detail`
5. `get_active_run_returns_waiting_row`
6. `get_active_run_returns_none_when_only_completed_rows_exist`
7. `start_run_fails_when_active_run_already_exists` — partial unique constraint guard

---

### `backend/tests/integration/test_sub_agent_loop.py` (NEW — async-generator integration)

**Primary analog:** `backend/tests/integration/test_deep_mode_chat_loop.py`
**Why:** Test the inner async generator with a stub LLM that returns deterministic tool-call responses; assert SSE events yielded match expected sequence.

**Test scope** (per CONTEXT.md D-32):
- task tool happy path (sub-agent runs and returns)
- task with `context_files` pre-load
- sub-agent failure isolation (TASK-05) — uncaught exception → `task_error` SSE
- ask_user pause-and-resume two-request sequence (POST → ask_user emitted + close → POST again with answer → resume)
- RLS isolation on `agent_runs`
- sub-agent inherits parent JWT (workspace sharing)
- `agent_status` transitions: `working` → `waiting_for_user` → `working` → `complete`
- append-only error roundtrip (LLM sees `{"error": "...", "code": "..."}` and recovers without retry helper code)
- privacy invariant: write file with PII via parent → call task with `context_files=[file]` → capture LLM-bound payload → assert anonymized (mirrors Phase 18 D-15 pattern)
- byte-identical fallback: `SUB_AGENT_ENABLED=False` → no `agent_runs` writes, no `task_*`/`agent_status` SSE

---

### `frontend/src/components/chat/AgentStatusChip.test.tsx` (NEW — Vitest)
### `frontend/src/components/chat/TaskPanel.test.tsx` (NEW — Vitest)

**Primary analog:** `frontend/src/components/chat/CodeExecutionPanel.test.tsx`
**Why:** Vitest 3.2 co-located convention bootstrapped in v1.2 D-P16-02. `WorkspacePanel.test.tsx` is a closer ChatContext-integration analog; both follow the same import shape.

**Imports + render-helper pattern** (copy verbatim from CodeExecutionPanel.test.tsx L1–35):
```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { I18nProvider } from '@/i18n/I18nContext'
import { AgentStatusChip } from './AgentStatusChip'

// D-P16-08: mock the network layer; do NOT spin up MSW.
vi.mock('@/lib/api', () => ({ apiFetch: vi.fn() }))

beforeEach(() => {
  vi.clearAllMocks()
  vi.useFakeTimers()  // for the 3s auto-fade timer
})
```

**Test list — AgentStatusChip:**
1. renders nothing (only `sr-only` aria-live container) when `agentStatus === null`
2. renders pulsing dot + "Agent working" copy on `working`
3. renders MessageCircleQuestion icon on `waiting_for_user`
4. renders CheckCircle2 + auto-fades after 3000ms on `complete`
5. renders AlertCircle on `error` and persists (no auto-fade)
6. has `role="status" aria-live="polite"` on container

**Test list — TaskPanel:**
1. renders nothing when `tasks.size === 0`
2. renders one card per task entry
3. running task shows Loader2 spinner with `animate-spin text-purple-500`
4. complete task shows CheckCircle2 + result preview (`line-clamp-2`)
5. error task shows AlertCircle + error detail (red)
6. context_files render as truncated chips with title tooltip
7. nested tool calls list renders `font-mono text-[11px]`
8. collapse button toggles content area
9. has `role="complementary" aria-label`

---

## Shared Patterns

### Authentication / RLS scope
**Source:** `backend/app/database.get_supabase_authed_client(token)` (used identically in `agent_todos_service.py`, `workspace_service.py`)
**Apply to:** Every backend service touching `agent_runs` or `messages`.
```python
from app.database import get_supabase_authed_client
client = get_supabase_authed_client(token)  # RLS-scoped — NEVER service-role
```
Pitfall: Phase 18 8199 observation — supabase client functions import from `app.database`, NOT `app.services.supabase_clients`.

### Audit logging
**Source:** `audit_service.log_action(...)` at `backend/app/services/audit_service.py:7–31`
**Apply to:** Every `task` and `ask_user` tool dispatch (D-23), every `agent_runs_service` mutation.
```python
audit_service.log_action(
    user_id=user_id, user_email=user_email,
    action="agent_run_start" | "agent_run_complete" | "agent_run_error" | "ask_user" | "task",
    resource_type="agent_runs",
    resource_id=thread_id,
)
```
Fire-and-forget — never raises.

### Egress filter (PII privacy invariant — D-21 / SEC-04)
**Source:** `backend/app/services/redaction/egress.py:63` `egress_filter(payload: str, registry, provisional)`
**Apply to:** Every LLM payload emitted from `sub_agent_loop.py` (mirror chat.py L1689–1700 inside `run_deep_mode_loop`). Sub-agent reuses PARENT'S registry (D-21) — do NOT instantiate a new one.
```python
egress_result = egress_filter(json.dumps(loop_messages, ensure_ascii=False), parent_redaction_registry, None)
if egress_result.tripped:
    raise EgressBlockedAbort("sub_agent_loop egress blocked")
```

### SSE event format
**Source:** chat.py existing yields throughout `run_deep_mode_loop`
**Apply to:** All Phase 19 events.
```python
yield f"data: {json.dumps({'type': '<event_name>', ...})}\n\n"
```
New event types: `agent_status`, `task_start`, `task_complete`, `task_error`, `ask_user`. The `tool_start` and `tool_result` events gain an OPTIONAL `task_id` field when emitted from inside a sub-agent.

### Executor-emitted SSE event queue (asyncio.Queue drain pattern)
**Source:** chat.py L470–632 (sandbox path) — canonical pattern referenced by CONTEXT.md L351.
**Apply to:** Sub-agent SSE forwarding from inside `task` tool dispatch in chat.py. Use `asyncio.Queue` + drain-between-events idiom. The redaction-aware buffering wrapper in chat.py continues to apply (D-06 explicit).

### Feature flag gating (dual-flag idiom)
**Source:** `_register_workspace_tools()` at tool_service.py L1602–1606
**Apply to:** `_register_sub_agent_tools()`. Pattern: outer flag (`tool_registry_enabled`) AND inner phase flag (`sub_agent_enabled`). Both early-return if False.

### Per-round persistence (DEEP-04 / STATUS-05)
**Source:** chat.py L1839–1849 `_persist_round_message(... deep_mode=True)`
**Apply to:** Sub-agent rounds — pass `parent_task_id=task_id` so the message tree can be reconstructed (D-10). For `ask_user` round persistence: write the assistant message with `tool_calls.calls=[ask_user_call]` and NO matching tool_result (this is what the frontend `isAskUserQuestion` flag detects).

### Frontend i18n key convention
**Source:** translations.ts L24–29 (`planPanel.*`), L675–685 (`workspace.*`)
**Apply to:** All Phase 19 strings — flat dotted keys, both ID + EN locales updated in same commit.

---

## No Analog Found

| File / Pattern | Why no analog | Resolution |
|----------------|---------------|------------|
| `<context_file path="...">` XML pre-load wrapping in sub-agent's first message | Phase 19 D-08 introduces this format; no prior file uses XML-ish pre-load | Codify the helper inside `sub_agent_loop.py` (see pattern excerpt above) — RESEARCH.md "Specific Ideas" line 401 confirmed the format |
| Resume-detection branch at top of `stream_chat` | Phase 19 D-04 is a new concept (no prior endpoint paused-and-resumed via DB state) | Closest analog: chat.py L1232–1254 (deep-mode dispatch branch) — same shape (early `return StreamingResponse(...)`), different trigger condition |
| `agentStatus` chip (header-area transient indicator) | No prior UI element appears in chat header with auto-fade timing | Compose from `AgentBadge.tsx` (chip styling) + `PlanPanel.tsx StatusIcon` (status-icon idiom). UI-SPEC §"AgentStatusChip" is the authoritative spec |
| Sub-agent failure isolation wrapper (D-12) | No prior async-generator wraps a try/except into a structured error result | Pattern codified in `sub_agent_loop.py` excerpt above; closest analog is chat.py L1876–1879 EgressBlockedAbort handler |

---

## Metadata

**Analog search scope:**
- `supabase/migrations/{036,038,039}*.sql`
- `backend/app/services/{agent_todos,workspace,audit,deep_mode_prompt,tool}*.py`
- `backend/app/services/redaction/egress.py`
- `backend/app/routers/chat.py`
- `backend/app/config.py`
- `backend/tests/integration/test_migration_038_agent_todos.py`
- `backend/tests/integration/test_deep_mode_chat_loop.py`
- `backend/tests/services/test_workspace_service.py`
- `frontend/src/components/chat/{PlanPanel,WorkspacePanel,SubAgentPanel,MessageView,AgentBadge,CodeExecutionPanel.test}.tsx`
- `frontend/src/hooks/useChatState.ts`
- `frontend/src/i18n/translations.ts`

**Files scanned:** 40+
**Pattern extraction date:** 2026-05-03

---

*End of PATTERNS.md. Consumed by `gsd-planner` to write per-plan PLAN.md files (19-01 through 19-10 per CONTEXT.md D-31).*
