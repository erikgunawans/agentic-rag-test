# Phase 21: Batched Parallel Sub-Agents + Human-in-the-Loop — Pattern Map

**Mapped:** 2026-05-04
**Files analyzed:** 11 (3 backend modify, 1 backend new helper candidate, 1 backend harness extend, 3 backend tests, 2 frontend modify, 1 frontend i18n, 3 frontend tests)
**Analogs found:** 11 / 11

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `backend/app/services/harness_engine.py` (modify, replace 692-698) | service / dispatcher | async-generator SSE event stream | Same file, `LLM_AGENT` block (lines 592-690) | exact (same dispatcher) |
| `backend/app/services/harness_engine.py` (modify, add `start_phase_index`) | service / public entry | request-response (function signature) | Same file, `run_harness_engine` (lines 93-148) | exact (extend in place) |
| `backend/app/routers/chat.py` (modify, HIL resume branch) | router / SSE entry | request-response → SSE | Same file, Phase 19 ask_user resume branch (lines 283-360) | exact (same shape) |
| `backend/app/routers/chat.py` (modify, 409 condition) | router / guard | request-response | Same file, lines 362-388 | exact (in-place edit) |
| `backend/app/services/workspace_service.py` (verify / maybe add `append_line`) | service / DB I/O | DB write | Same file, `write_text_file` (lines 193-261) | exact (same class) |
| `backend/app/harnesses/smoke_echo.py` (extend 2→4 phases) | harness definition | static config | Same file, existing 2-phase harness (lines 78-126) | exact (extend in place) |
| `frontend/src/hooks/useChatState.ts` (modify, add `batchProgress` slice) | hook / reducer | SSE event-driven state | Same file, `harnessRun` slice (lines 24-32, 582-623) | exact (mirror pattern) |
| `frontend/src/components/chat/HarnessBanner.tsx` (modify, batch + paused) | component | render | Same file, existing render (lines 67-115) | exact (extend in place) |
| `frontend/src/i18n/translations.ts` (modify) | i18n | static strings | Same file, `harness.banner.*` keys (lines 725-735, 1466-1477) | exact (same namespace) |
| `backend/tests/services/test_harness_engine_batch.py` (new) | backend test | unit / async-gen drain | `test_harness_engine.py` (lines 1-90+) | role-match (same module under test) |
| `backend/tests/services/test_harness_engine_human_input.py` (new) | backend test | unit / async-gen drain | `test_harness_engine.py` | role-match |
| `backend/tests/routers/test_chat_hil_resume.py` (new) | backend test | router / FastAPI TestClient | `test_chat_harness_routing.py` (lines 1-60+) | exact (same router under test) |
| `frontend/src/components/chat/__tests__/HarnessBanner.batchProgress.test.tsx` (new) | frontend test | Vitest component | `PlanPanel.test.tsx` (lines 30-121) | role-match (panel-style test) |
| `frontend/src/components/chat/__tests__/HarnessBanner.paused.test.tsx` (new) | frontend test | Vitest component | `PlanPanel.test.tsx` | role-match |
| `frontend/src/hooks/__tests__/useChatState.batchProgress.test.ts` (new) | frontend test | Vitest hook | `usePublicSettings.test.ts` (in `/hooks/`) | role-match |

---

## Pattern Assignments

### `harness_engine.py` — replace lines 692-698 PHASE21_PENDING stubs

**Analog:** Same file, `LLM_AGENT` dispatcher block (lines 592-690).

**Tool curation pattern** (lines 592-595) — mirror this for batch sub-agents (NO `tools` param on `run_sub_agent_loop`; curation is pre-call):
```python
if phase.phase_type == PhaseType.LLM_AGENT:
    # PANEL-03 LLM-side defense: strip excluded tools from this phase's list
    curated_tools = [t for t in phase.tools if t not in PANEL_LOCKED_EXCLUDED_TOOLS]
    description = phase.system_prompt_template or phase.description or phase.name
```

**`run_sub_agent_loop` invocation** (lines 622-636) — REUSED VERBATIM by each batch item; do NOT pass a `tools` kwarg:
```python
async for ev in run_sub_agent_loop(
    description=description,
    context_files=phase.workspace_inputs,
    parent_user_id=user_id,
    parent_user_email=user_email,
    parent_token=token,
    parent_tool_context={},
    parent_thread_id=thread_id,
    parent_user_msg_id=harness_run_id,   # SSE correlation — use run_id
    client=or_svc.client,
    sys_settings=sys_settings,
    web_search_effective=False,
    task_id=harness_run_id,               # batch: pass per-item UUID instead
    parent_redaction_registry=registry,
):
    if "_terminal_result" in ev:
        ...
        break
    yield ev
```

**Workspace write after sub-agent terminal** (lines 678-689) — mirror for HIL answer write + JSONL append + final merge:
```python
output: dict = {"text": "\n".join(collected_text)}
if phase.workspace_output:
    try:
        ws = WorkspaceService(token=token)
        await ws.write_text_file(
            thread_id, phase.workspace_output, output["text"], source="harness"
        )
    except Exception as exc:
        logger.warning(
            "_dispatch_phase: workspace write failed phase=%s: %s", phase.name, exc
        )

yield {"_terminal_phase_result": output}
return
```

**Phase 21 SSE constants — already declared** (lines 84-86):
```python
EVT_BATCH_START = "harness_batch_start"                 # [Phase 21 - deferred]
EVT_BATCH_COMPLETE = "harness_batch_complete"           # [Phase 21 - deferred]
EVT_HUMAN_INPUT_REQUIRED = "harness_human_input_required"  # [Phase 21 - deferred]
```
**Add new** item-level constants for D-08:
```python
EVT_BATCH_ITEM_START = "harness_batch_item_start"
EVT_BATCH_ITEM_COMPLETE = "harness_batch_item_complete"
```

**Failure isolation envelope pattern** (lines 648-657, 673-675) — every batch item wraps `run_sub_agent_loop` in the same try/except, writing a `{status: "failed", error: {...}}` line to JSONL instead of breaking the batch:
```python
except Exception as exc:
    logger.error(
        "_dispatch_phase: sub_agent_loop crash phase=%s: %s", phase.name, exc, exc_info=True
    )
    sub_status = "failed"
    sub_result = {
        "error": "sub_agent_crashed",
        "code": "TASK_LOOP_CRASH",
        "detail": str(exc)[:500],
    }
```

**Egress filter** (`LLM_SINGLE` lines 503-514) — apply at HIL question-generation LLM call:
```python
if registry is not None:
    payload = json.dumps(messages, ensure_ascii=False)
    er = egress_filter(payload, registry, None)
    if er.tripped:
        yield {
            "_terminal_phase_result": {
                "error": "egress_blocked",
                "code": "PII_EGRESS_BLOCKED",
                "detail": "PII detected in llm_single payload",
            }
        }
        return
```

**Pydantic structured output pattern** (lines 516-558) — HIL question generation uses `response_format=json_schema` + `model_validate_json` against a `class HumanInputQuestion(BaseModel): question: str` schema:
```python
schema = phase.output_schema.model_json_schema()
llm_result = await or_svc.complete_with_tools(
    messages=messages,
    tools=None,
    model=None,
    response_format={
        "type": "json_schema",
        "json_schema": {
            "name": phase.output_schema.__name__,
            "schema": schema,
            "strict": True,
        },
    },
)
parsed = phase.output_schema.model_validate_json(llm_result.get("content", ""))
```

---

### `harness_engine.py` — `run_harness_engine` signature extension (D-03)

**Analog:** Same file, current signature (lines 93-103) and inner phase loop (line 201).

Current signature pattern (extend with `start_phase_index: int = 0` keyword-only):
```python
async def run_harness_engine(
    *,
    harness: HarnessDefinition,
    harness_run_id: str,
    thread_id: str,
    user_id: str,
    user_email: str,
    token: str,
    registry,
    cancellation_event: asyncio.Event,
    # NEW for Phase 21:
    start_phase_index: int = 0,
) -> AsyncIterator[dict]:
```

Phase loop (line 201) — must skip phases below `start_phase_index`:
```python
for phase_index, phase in enumerate(harness.phases):
    if phase_index < start_phase_index:
        continue   # already recorded in phase_results from prior run
    # ... existing logic
```

**Constraint:** Default `0` preserves byte-identical behavior for all existing callers. Pass `current_phase + 1` from HIL resume in chat.py.

---

### `harness_engine.py` — asyncio.Queue fan-in for `LLM_BATCH_AGENTS`

**Analog:** `chat.py` lines 632-741 (sandbox SSE event queue) — the canonical fan-in pattern.

**Queue construction + producer fan-out + consumer drain** (chat.py 646-741, condensed):
```python
sandbox_event_queue = asyncio.Queue()

# Producer side: callback enqueues events as they arrive
async def sandbox_stream_callback(event_type: str, line: str):
    await sandbox_event_queue.put({
        "type": event_type,
        "line": emit_line,
        "tool_call_id": tc["id"],
    })

# Consumer side: spawn the worker, drain the queue while it runs
tool_output_task = asyncio.create_task(
    _dispatch_tool(func_name, real_args, ...)
)
while not tool_output_task.done():
    try:
        evt = await asyncio.wait_for(
            sandbox_event_queue.get(), timeout=0.1,
        )
        yield evt["type"], evt
    except asyncio.TimeoutError:
        continue
# Drain any remaining queued events after task completes
while not sandbox_event_queue.empty():
    evt = sandbox_event_queue.get_nowait()
    yield evt["type"], evt
tool_output = await tool_output_task
```

**Phase 21 adaptation:** N concurrent producers (one `asyncio.create_task` per item in current batch chunk), one shared queue, one consumer drain loop on the dispatcher generator. Each item's producer puts every nested SSE event from `run_sub_agent_loop` into the shared queue; the dispatcher yields them in arrival order. Track completion with a counter (`done_count == chunk_size`) rather than `task.done()` per task.

**Constraints (do-not-deviate):**
- Use `await queue.put(...)` from async producers; `put_nowait(...)` only from sync callbacks (workspace_event_callback at chat.py:684-685 is the precedent).
- Drain remaining queue contents after all producers finish — same pattern as line 738-740.
- Re-chunk strategy: items 0..N-1 → batches of `phase.batch_size`; for resume, re-chunk only `remaining_items` (D-07).

---

### `chat.py` — D-01 / D-02 HIL resume branch (NEW, before 409 block)

**Analog:** Same file, Phase 19 ask_user resume branch (lines 283-360).

**Detection + DB transition + history reload + StreamingResponse** (condensed from lines 287-360):
```python
# Phase 19 / D-04: resume-detection branch (gated by SUB_AGENT_ENABLED AND DEEP_MODE_ENABLED).
if settings.sub_agent_enabled and settings.deep_mode_enabled:
    active_run = await agent_runs_service.get_active_run(body.thread_id, user["token"])
    if active_run and active_run["status"] == "waiting_for_user":
        # Transition before re-entering the loop — race-mitigation guard is inside service.
        await agent_runs_service.transition_status(
            run_id=active_run["id"],
            new_status="working",
            token=user["token"],
            user_id=user["id"],
            user_email=user.get("email", ""),
        )
        # Reload history for the resumed loop (same as normal path below)
        flat_rows_resume = (
            client.table("messages").select("role, content, tool_calls")
            .eq("thread_id", body.thread_id).eq("user_id", user["id"])
            .order("created_at").execute()
        ).data or []
        # ... build _history_resume, _sys_settings_resume, _web_search_resume ...
        _user_msg_resume = client.table("messages").insert({
            "thread_id": body.thread_id,
            "user_id": user["id"],
            "role": "user",
            "content": body.message,
            "parent_message_id": body.parent_message_id,
        }).execute()
        _user_msg_id_resume = _user_msg_resume.data[0]["id"]
        return StreamingResponse(
            run_deep_mode_loop(
                messages=_history_resume,
                user_message=body.message,
                # ... resume kwargs ...
                resume_run_id=active_run["id"],
                resume_tool_result=body.message,
                resume_round_index=active_run["last_round_index"] + 1,
            ),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
```

**Phase 21 HIL resume adaptation** — same shape, different service + write target:
```python
# Phase 21 / D-01, D-02: HIL resume detection (BEFORE the 409 block at line 366).
if settings.harness_enabled:
    paused_run = await harness_runs_service.get_active_run(
        thread_id=body.thread_id, token=user["token"]
    )
    if paused_run is not None and paused_run["status"] == "paused":
        # 1. Write user's answer to current phase's workspace_output
        h = harness_registry.get_harness(paused_run["harness_type"])
        current_phase_idx = paused_run["current_phase"]
        current_phase = h.phases[current_phase_idx]
        ws = WorkspaceService(token=user["token"])
        await ws.write_text_file(
            body.thread_id, current_phase.workspace_output, body.message, source="harness"
        )
        # 2. Persist user's message with harness_mode tag (mirror post_harness:150-155)
        client.table("messages").insert({
            "thread_id": body.thread_id,
            "user_id": user["id"],
            "role": "user",
            "content": body.message,
            "harness_mode": h.name,
            "parent_message_id": body.parent_message_id,
        }).execute()
        # 3. Mark current phase complete via advance_phase
        await harness_runs_service.advance_phase(
            run_id=paused_run["id"],
            new_phase_index=current_phase_idx + 1,
            phase_results_patch={
                str(current_phase_idx): {
                    "phase_name": current_phase.name,
                    "output": {"answer": body.message[:500]},
                }
            },
            token=user["token"],
        )
        # 4. Resume the engine from the next phase
        return StreamingResponse(
            run_harness_engine(
                harness=h,
                harness_run_id=paused_run["id"],
                thread_id=body.thread_id,
                user_id=user["id"],
                user_email=user.get("email", ""),
                token=user["token"],
                registry=...,                  # B4 single-registry helper
                cancellation_event=asyncio.Event(),
                start_phase_index=current_phase_idx + 1,
            ),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
```

---

### `chat.py` — D-01 409 block change (lines 362-388)

**Analog:** Existing 409 block — surgical edit only.

**Current** (lines 366-388):
```python
if settings.harness_enabled:
    active_harness = await harness_runs_service.get_active_run(
        thread_id=body.thread_id, token=user["token"]
    )
    if active_harness is not None:
        # ... build phase_name ...
        return JSONResponse(status_code=409, content={...})
```

**Phase 21 D-01 change** — only block when status is `pending` or `running`, NOT `paused`:
```python
if active_harness is not None and active_harness.get("status") in ("pending", "running"):
    # 409 path unchanged
    return JSONResponse(status_code=409, ...)
```

**Constraint:** The HIL resume branch above MUST run BEFORE this 409 block, so `paused` falls through to resume rather than triggering a stale 409.

---

### `workspace_service.py` — JSONL append (verify or add `append_line`)

**Analog:** Same file, `write_text_file` (lines 193-261) and `read_file` (lines 267-324).

**Existing `write_text_file` upsert** (lines 238-251):
```python
self._client.table("workspace_files").upsert(
    {
        "thread_id": thread_id,
        "file_path": file_path,
        "content": content,
        ...
    },
    on_conflict="thread_id,file_path",
).execute()
```

**JSONL append decision (Phase 21 plan-time):**
- **Option A (preferred — no new helper):** Read existing content via `read_file`, concat new line + `\n`, call `write_text_file`. Plan must serialize appends per-batch under an `asyncio.Lock` since the upsert is read-then-write (not atomic).
- **Option B (new helper):** Add `WorkspaceService.append_line(thread_id, path, line)` that does a single SQL `UPDATE ... SET content = content || $newline` to make appends DB-atomic.

**Recommended for plan:** Option B (atomic append). Validation rules from `validate_workspace_path` (lines 64-129) apply identically. Match the structured-error return convention (lines 209, 234, 254):
```python
return {"ok": True, "operation": "append", "size_bytes": N, "file_path": file_path}
# or
return {"error": "db_error", "detail": str(exc), "file_path": file_path}
```

**Constraint:** Per-line max length must be checked against `MAX_TEXT_CONTENT_BYTES = 1024 * 1024` (line 38) cumulative — final file size after append must stay under cap. Plan-phase confirms.

---

### `harnesses/smoke_echo.py` — extend 2 → 4 phases

**Analog:** Same file (lines 78-126) — register pattern + Pydantic schema + executor pattern.

**Existing Phase 1 PROGRAMMATIC** (lines 39-74) — mirror to write a 3-item synthetic `test-items.md` for batch input:
```python
async def _phase1_echo(
    *, inputs: dict[str, str], token: str, thread_id: str, harness_run_id: str
) -> dict:
    ws = WorkspaceService(token=token)
    files = await ws.list_files(thread_id)
    # ... build content ...
    return {"content": echo_content, ...}
```

**Existing Phase 2 LLM_SINGLE pattern** (lines 107-124) — mirror for HIL Phase 3 (system_prompt_template that asks one short question):
```python
PhaseDefinition(
    name="summarize",
    description="Read echo.md and produce a JSON summary via Pydantic schema (HARN-05).",
    phase_type=PhaseType.LLM_SINGLE,
    system_prompt_template=("..."),
    tools=[],
    workspace_inputs=["echo.md"],
    workspace_output="summary.json",
    output_schema=EchoSummary,
    timeout_seconds=120,
),
```

**Phase 21 additions to `SMOKE_ECHO.phases` list:**
```python
PhaseDefinition(  # Phase 3: HIL
    name="ask-label",
    phase_type=PhaseType.LLM_HUMAN_INPUT,
    system_prompt_template="Generate one short clarifying question: 'What label should we put on the echo result?'",
    workspace_inputs=["echo.md"],
    workspace_output="test-answer.md",
    timeout_seconds=86_400,
),
PhaseDefinition(  # Phase 4: BATCH
    name="batch-process",
    phase_type=PhaseType.LLM_BATCH_AGENTS,
    system_prompt_template="Process this single item. Return the item's label echoed back.",
    tools=[],
    workspace_inputs=["test-items.md"],   # Phase 1 must write a synthetic 3-item JSON array here
    workspace_output="test-batch.json",   # final merge target; engine also writes test-batch.jsonl
    batch_size=2,                          # 3 items at batch_size=2 → 2 batches (items 0+1, then item 2)
    timeout_seconds=600,
),
```

**Constraint:** `Phase 1 _phase1_echo` must also write `test-items.md` to workspace (a 3-item JSON array string) so Phase 4 has input. The smoke harness is gated by `settings.harness_smoke_enabled` (line 130) — no new flag.

---

### `useChatState.ts` — `batchProgress` slice (NEW, mirror `harnessRun`)

**Analog:** Same file, `harnessRun` slice and reducer arms.

**Type declaration pattern** (lines 24-32):
```typescript
export type HarnessRunSlice = null | {
  id: string
  harnessType: string
  status: 'pending' | 'running' | 'paused' | 'completed' | 'cancelled' | 'failed'
  currentPhase: number
  phaseCount: number
  phaseName: string
  errorDetail: string | null
}
```

**Phase 21 mirror — add to same file:**
```typescript
// Phase 21 / D-09: per-item progress for llm_batch_agents phases.
// Driven by harness_batch_item_start / harness_batch_item_complete SSE events;
// cleared by harness_phase_complete (when the batch phase ends).
export type BatchProgressSlice = null | {
  completed: number
  total: number
}
```

**State + setter** (lines 132, 788-789):
```typescript
const [harnessRun, setHarnessRun] = useState<HarnessRunSlice>(null)
// ... return { harnessRun, setHarnessRun, ... }
```

**Reducer arm pattern for harness_phase_start/complete** (lines 582-598) — mirror exactly:
```typescript
} else if (event.type === 'harness_phase_start') {
  setHarnessRun((prev) => ({
    id: event.harness_run_id as string,
    harnessType: (prev?.harnessType) ?? '',
    status: 'running',
    currentPhase: event.phase_index as number,
    phaseCount: (prev?.phaseCount) ?? 0,
    phaseName: event.phase_name as string,
    errorDetail: null,
  }))
} else if (event.type === 'harness_phase_complete') {
  setHarnessRun((prev) => prev ? { ...prev, currentPhase: prev.currentPhase + 1 } : prev)
}
```

**Phase 21 reducer arms — append in same SSE switch:**
```typescript
} else if (event.type === 'harness_batch_item_start') {
  setBatchProgress((prev) => ({
    completed: prev?.completed ?? 0,
    total: event.items_total as number,
  }))
} else if (event.type === 'harness_batch_item_complete') {
  setBatchProgress((prev) =>
    prev ? { ...prev, completed: prev.completed + 1 } : { completed: 1, total: event.items_total as number }
  )
}
```

**Clear-on-phase-complete** — extend the existing `harness_phase_complete` arm:
```typescript
} else if (event.type === 'harness_phase_complete') {
  setHarnessRun((prev) => prev ? { ...prev, currentPhase: prev.currentPhase + 1 } : prev)
  setBatchProgress(null)   // Phase 21 D-09: clear batch progress at phase boundary
}
```

**Thread-switch reset** (lines 233-249) — also reset `batchProgress`:
```typescript
setHarnessRun(null)
setBatchProgress(null)   // Phase 21 — mirror harness slice reset
```

**ChatContext auto-flow:** The ChatContext re-exports `useChatState`'s return via `ReturnType<typeof useChatState>` — no manual context type edits needed (memory ID 9472).

---

### `HarnessBanner.tsx` — extend with batch progress + paused state

**Analog:** Same file, existing `titleText` builder (lines 67-82).

**Existing title text branches** (lines 67-82):
```typescript
const titleText = isActive
  ? t('harness.banner.running', {
      harnessType: harnessLabel,
      n: String(harnessRun.currentPhase + 1),
      m: String(harnessRun.phaseCount || '?'),
      phaseName: harnessRun.phaseName,
    })
  : isCancelled
  ? t('harness.banner.cancelled', { harnessType: harnessLabel })
  : isFailed
  ? t('harness.banner.failed', {...})
  : ''
```

**Phase 21 addition — read `batchProgress` from context** (line 33 reads from useChatContext; just add):
```typescript
const { harnessRun, batchProgress, activeThreadId } = useChatContext()
```

**Build modifier suffix and append to active title text:**
```typescript
const isPaused = harnessRun?.status === 'paused'

const baseTitle = isActive
  ? (isPaused
      ? t('harness.banner.paused', { harnessType: harnessLabel })
      : t('harness.banner.running', { ... }))
  : isCancelled ? t('harness.banner.cancelled', { harnessType: harnessLabel })
  : isFailed ? t('harness.banner.failed', {...})
  : ''

const batchSuffix = batchProgress
  ? ' — ' + t('harness.banner.batchProgress', {
      completed: String(batchProgress.completed),
      total: String(batchProgress.total),
    })
  : ''

const titleText = baseTitle + batchSuffix
```

**Constraint:** `paused` is part of the existing `ACTIVE_STATUSES` (line 29). Cancel button stays visible (already gated on `isActive`). No new component, no new test-id changes — extend `data-testid="harness-banner"` only.

---

### `i18n/translations.ts` — add 3 new keys (ID + EN)

**Analog:** Same file, existing `harness.banner.*` keys (lines 725-735 ID, 1466-1477 EN).

**Existing pattern (ID, line 725):**
```typescript
'harness.banner.running': '{harnessType} berjalan — fase {n} dari {m} ({phaseName})',
'harness.banner.cancelled': '{harnessType} dibatalkan',
'harness.banner.failed': '{harnessType} gagal — {detail}',
```

**Phase 21 additions (ID block, near line 727):**
```typescript
'harness.banner.batchProgress': 'Menganalisis klausula {completed}/{total}',
'harness.banner.paused': 'Menunggu respons Anda — {harnessType}',
```

**Phase 21 additions (EN block, near line 1468):**
```typescript
'harness.banner.batchProgress': 'Analyzing clause {completed}/{total}',
'harness.banner.paused': 'Awaiting your response — {harnessType}',
```

**Constraint:** ID is the default locale (CLAUDE.md). Both locales must ship in the same commit.

---

### `test_harness_engine_batch.py` — backend tests (NEW)

**Analog:** `test_harness_engine.py` (existing file, lines 1-90 imports + helpers + mocks).

**Imports + helper pattern** (lines 20-47):
```python
from __future__ import annotations
import asyncio, json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from pydantic import BaseModel

from app.harnesses.types import (
    HarnessDefinition, HarnessPrerequisites, PhaseDefinition, PhaseType,
)
from app.services.harness_engine import (
    EVT_BATCH_COMPLETE, EVT_BATCH_START, EVT_PHASE_COMPLETE, run_harness_engine,
)

async def _collect(gen) -> list[dict]:
    events = []
    async for ev in gen:
        events.append(ev)
    return events
```

**Shared MOCK_BASES dict pattern** (lines 82-90) — REUSED for batch tests; add `run_sub_agent_loop` AsyncMock that yields per-item terminal results to drive concurrent dispatch:
```python
MOCK_BASES = {
    "app.services.harness_engine.agent_todos_service.write_todos": AsyncMock(return_value=None),
    "app.services.harness_engine.harness_runs_service.advance_phase": AsyncMock(return_value=True),
    "app.services.harness_engine.harness_runs_service.complete": AsyncMock(return_value=True),
    "app.services.harness_engine.harness_runs_service.get_run_by_id": AsyncMock(
        return_value={"status": "running"}
    ),
    "app.services.harness_engine.WorkspaceService": MagicMock(),
}
```

**Required test cases (from CONTEXT spec):**
1. `test_batch_concurrent_dispatch` — N items at batch_size=N triggers `asyncio.gather` style fan-in (use `_collect` to drain async-gen; assert per-item events appear interleaved).
2. `test_batch_jsonl_append_per_item` — assert `WorkspaceService.write_text_file` (or `append_line`) called once per item with monotonically growing content.
3. `test_batch_resume_skips_done_items` — pre-seed JSONL workspace file with `{"item_index": 0, "status": "ok", ...}`; assert only items 1..N-1 dispatched.
4. `test_batch_resume_skips_failed_items` — JSONL has `{"status": "failed"}`; assert NOT re-queued (D-12 + STATUS-03).
5. `test_batch_failure_marker_continues` — one item raises; assert JSONL has `{status: "failed", error: ...}` line AND remaining items still complete.
6. `test_batch_merge_pass_sorted` — JSONL written out-of-order (3, 0, 1, 2); assert final `.json` is `[item_0, item_1, item_2, item_3]` sorted by `item_index`.
7. `test_batch_item_index_globally_unique` — 7 items at batch_size=3 → 3 batches; `item_index` in events spans 0..6 with no per-batch reset.

---

### `test_harness_engine_human_input.py` — backend tests (NEW)

**Analog:** Same `test_harness_engine.py` mock dictionary pattern + `_collect` helper.

**Required test cases:**
1. `test_hil_question_generation_llm_call` — `complete_with_tools` invoked once with `response_format=json_schema`; mock returns `{"question": "What label?"}`.
2. `test_hil_delta_events_emitted_before_required` — events list ends with `delta`* sequence followed by single `harness_human_input_required` then `done` (or harness_complete with paused — TBD plan).
3. `test_hil_required_event_payload` — assert event has keys `type`, `question`, `workspace_output_path`, `harness_run_id`.
4. `test_hil_db_paused_before_sse_close` — patch `harness_runs_service.transition_status` (or whichever sets `paused`); assert called BEFORE final yield.
5. `test_hil_egress_filter_blocks_pii_question` — registry mock with `egress_filter` returning `tripped=True`; assert `_terminal_phase_result` is `egress_blocked` error dict (mirrors LLM_SINGLE pattern lines 503-514).

---

### `test_chat_hil_resume.py` — router tests (NEW)

**Analog:** `test_chat_harness_routing.py` (lines 1-60 imports + fixtures, full file ~13 tests).

**Imports + fixture pattern** (lines 17-49):
```python
from __future__ import annotations
import asyncio, json
from unittest.mock import AsyncMock, MagicMock, patch, call
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.harnesses.types import (
    HarnessDefinition, HarnessPrerequisites, PhaseDefinition, PhaseType,
)

def _make_prereqs(requires_upload: bool = True) -> HarnessPrerequisites:
    return HarnessPrerequisites(
        requires_upload=requires_upload,
        upload_description="...",
        accepted_mime_types=["application/pdf"],
        min_files=1, max_files=1,
        harness_intro="...",
    )
```

**Required test cases:**
1. `test_hil_resume_detects_paused_status` — mock `harness_runs_service.get_active_run` returns `{status: "paused"}`; assert HIL branch entered (not 409).
2. `test_hil_resume_writes_answer_to_workspace` — assert `WorkspaceService.write_text_file` called with phase's `workspace_output` and `body.message`.
3. `test_hil_resume_calls_advance_phase` — assert `harness_runs_service.advance_phase` invoked with `new_phase_index = current_phase + 1`.
4. `test_hil_resume_calls_run_harness_engine_with_start_phase_index` — assert `run_harness_engine` invoked with `start_phase_index=current_phase + 1`.
5. `test_hil_resume_persists_user_message_with_harness_mode` — assert `messages` insert includes `harness_mode=harness.name` (mirror `post_harness.py:150-155`).
6. `test_409_only_blocks_pending_running` — `status="paused"` falls through; `status="pending"` returns 409; `status="running"` returns 409.

---

### `HarnessBanner.batchProgress.test.tsx` — frontend test (NEW)

**Analog:** `PlanPanel.test.tsx` (lines 30-121 — describes mock pattern for ChatContext).

**Mock pattern** (lines 41-50):
```typescript
const mockChatContext = {
  todos: [] as Todo[],
  isCurrentMessageDeepMode: false,
  harnessRun: null as HarnessRunSlice,
  activeThreadId: 'thread-test-123' as string | null,
}

vi.mock('@/contexts/ChatContext', () => ({
  useChatContext: () => mockChatContext,
}))
```

**Render helper** (lines 106-111):
```typescript
function renderPanel() {
  return render(
    <I18nProvider>
      <PlanPanel />
    </I18nProvider>,
  )
}
```

**Phase 21 adaptation — extend mock with `batchProgress`:**
```typescript
const mockChatContext = {
  harnessRun: { id: 'run-1', harnessType: 'smoke-echo', status: 'running',
                currentPhase: 0, phaseCount: 4, phaseName: 'batch-process',
                errorDetail: null } as HarnessRunSlice,
  batchProgress: null as { completed: number; total: number } | null,
  activeThreadId: 'thread-test-123' as string | null,
}
```

**Required test cases:**
1. `test_batch_progress_null_renders_no_suffix` — banner text equals base running text only.
2. `test_batch_progress_renders_indonesian_default` — `batchProgress = {completed: 3, total: 15}`; banner text contains "Menganalisis klausula 3/15".
3. `test_batch_progress_renders_english_when_locale_en` — wrap with `<I18nProvider initialLocale="en">` (or test util); assert "Analyzing clause 3/15".

---

### `HarnessBanner.paused.test.tsx` — frontend test (NEW)

Same mock + render helper as `batchProgress.test.tsx`.

**Required test cases:**
1. `test_paused_banner_indonesian_default` — `harnessRun.status='paused'`; assert banner text "Menunggu respons Anda — Smoke Echo".
2. `test_paused_banner_english` — locale en; assert "Awaiting your response — Smoke Echo".
3. `test_paused_banner_keeps_cancel_button` — `paused` is in `ACTIVE_STATUSES` (line 29); `harness-banner-cancel` testid present.

---

### `useChatState.batchProgress.test.ts` — hook test (NEW)

**Analog:** `usePublicSettings.test.ts` (in `frontend/src/hooks/`) — Vitest hook test pattern.

**Required test cases (drive the reducer directly via SSE event injection):**
1. `test_harness_batch_item_start_seeds_total` — dispatch event `{type: "harness_batch_item_start", item_index: 0, items_total: 5}`; assert `batchProgress.total === 5`, `completed === 0`.
2. `test_harness_batch_item_complete_increments_completed` — start event then complete event; assert `completed === 1`.
3. `test_harness_phase_complete_clears_batch_progress` — seed `batchProgress`, dispatch `harness_phase_complete`; assert `batchProgress === null`.
4. `test_thread_switch_resets_batch_progress` — change `activeThreadId`; assert `batchProgress === null` (mirror line 240).

---

## Shared Patterns

### Pattern: `harness_mode` message tagging
**Source:** `backend/app/services/post_harness.py:150-155`
**Apply to:** HIL resume branch in `chat.py` (user answer message), HIL question generation (assistant message persisted before SSE close)
```python
client.table("messages").insert({
    "thread_id": thread_id,
    "role": "assistant",   # or "user" for HIL answer
    "content": content,
    "harness_mode": harness_name,
}).execute()
```

### Pattern: SSE event format with `harness_run_id` correlation
**Source:** `backend/app/services/harness_engine.py:260-266` and `chat.py:645`
**Apply to:** All Phase 21 new events (batch_item_start/complete, human_input_required)
```python
yield {
    "type": EVT_PHASE_START,                    # or EVT_BATCH_ITEM_START etc.
    "harness_run_id": harness_run_id,           # mandatory for frontend correlation
    "phase_index": phase_index,
    "phase_name": phase.name,
    "phase_type": phase.phase_type.value,
}
```
SSE wire format (frontend consumer):
```python
yield f"data: {json.dumps({'type': '...', ...})}\n\n"
```

### Pattern: `task_id` event tagging (Phase 19 D-06)
**Source:** `backend/app/services/sub_agent_loop.py:320-345`
**Apply to:** Each batch item's sub-agent — pass a per-item server-generated UUID (NOT the harness_run_id) so frontend `tasks` Map correlates each clause to its own TaskPanel card. Add `batch_index: item_index` to the `task_start` payload.
```python
yield {
    "type": "tool_start",
    "tool": func_name,
    "task_id": task_id,           # per-item UUID
}
```

### Pattern: Egress filter pre-LLM-call (SEC-04)
**Source:** `backend/app/services/harness_engine.py:503-514` (LLM_SINGLE block)
**Apply to:** HIL question generation LLM call (D-21 / SEC-04 invariant — registry-known PII never reaches cloud)
```python
if registry is not None:
    payload = json.dumps(messages, ensure_ascii=False)
    er = egress_filter(payload, registry, None)
    if er.tripped:
        yield {"_terminal_phase_result": {
            "error": "egress_blocked", "code": "PII_EGRESS_BLOCKED",
            "detail": "PII detected in llm_human_input payload",
        }}
        return
```

### Pattern: STATUS-03 no-retry rule
**Source:** `.planning/STATE.md` v1.3 contract; Phase 19 D-20
**Apply to:** Batch failure handling (D-11, D-12) — write failure marker to JSONL, continue batch, NEVER auto-retry. User cancels + re-triggers if retries needed.

### Pattern: Pydantic structured LLM output
**Source:** `backend/app/services/harness_engine.py:516-558` and CLAUDE.md "Use Pydantic for structured LLM outputs (`json_object` response format)"
**Apply to:** HIL question generation. Define a tiny Pydantic class:
```python
class HumanInputQuestion(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)
```

### Pattern: Workspace path validation
**Source:** `backend/app/services/workspace_service.py:64-129`
**Apply to:** JSONL path (`{stem}.jsonl`) and merged path (`{stem}.json`) computed at dispatch time. Both must pass `validate_workspace_path` — no `..`, no leading `/`, no backslash.

### Pattern: B4 single-registry helper
**Source:** `backend/app/routers/chat.py:1723` (`_gatekeeper_stream_wrapper`) — memory ID 9305
**Apply to:** HIL resume branch — registry passed to `run_harness_engine` MUST be the same `ConversationRegistry` instance loaded for the parent SSE; do NOT mint a fresh one (egress invariant).

---

## No Analog Found

None — all 11 new/modified files have an in-repo analog from Phase 17/18/19/20.

---

## Metadata

**Analog search scope:**
- `backend/app/services/{harness_engine,harness_runs_service,sub_agent_loop,workspace_service,post_harness,gatekeeper}.py`
- `backend/app/routers/chat.py`
- `backend/app/harnesses/{smoke_echo,types}.py`
- `backend/tests/services/{test_harness_engine,test_chat_harness_routing}.py`
- `frontend/src/hooks/useChatState.ts`
- `frontend/src/components/chat/{HarnessBanner.tsx,__tests__/PlanPanel.test.tsx}`
- `frontend/src/i18n/translations.ts`

**Files scanned:** 13
**Pattern extraction date:** 2026-05-04
