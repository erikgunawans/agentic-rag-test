---
phase: 21-batched-parallel-sub-agents-human-in-the-loop
plan: 03
type: execute
wave: 3
depends_on: [01, 02]
files_modified:
  - backend/app/services/harness_engine.py
  - backend/app/services/sub_agent_loop.py
  - backend/tests/services/test_harness_engine_batch.py
autonomous: true
requirements:
  - BATCH-01  # Parses items from workspace input file
  - BATCH-02  # Chunks into batches of batch_size, runs concurrently via asyncio.gather pattern
  - BATCH-03  # batch_size from PhaseDefinition (default 5)
  - BATCH-04  # Real-time SSE streaming via asyncio.Queue (not delayed)
  - BATCH-05  # Results accumulate into JSONL workspace output file (per item)
  - BATCH-06  # Each sub-agent reads only what it needs from workspace + emits item-level SSE
  - BATCH-07  # Mid-batch resume — JSONL state dictates remaining items
must_haves:
  truths:
    - "PhaseType.LLM_BATCH_AGENTS branch in _dispatch_phase REPLACES the residual PHASE21_PENDING runtime stub from Plan 21-02."
    - "Dispatcher reads phase.workspace_inputs[0] (the items file) — JSON array of item objects. If unparseable, yields _terminal_phase_result with error='batch_input_invalid'."
    - "Dispatcher computes JSONL path = `<stem>.jsonl` and final-merge path = `<stem>.json` from phase.workspace_output stem (e.g. 'risk-analysis.json' → 'risk-analysis.jsonl' + 'risk-analysis.json'). Both paths pass validate_workspace_path."
    - "Resume logic: read `<stem>.jsonl` via WorkspaceService.read_file. If it exists, parse newline-delimited JSON, build done_set = {row['item_index'] for row}, filter all_items to only items whose index is NOT in done_set. Failed items (status='failed') are also in done_set — NEVER retried (D-12, STATUS-03)."
    - "Re-chunk remaining_items into batches of phase.batch_size (default 5)."
    - "Per batch: emit harness_batch_start event with {type, harness_run_id, phase_index, phase_name, batch_size, batch_index, items_total}; spawn N concurrent asyncio.create_task coroutines; each coroutine puts events into a shared asyncio.Queue; main generator drains the queue while batch tasks run."
    - "Per item: server-generated UUID task_id (via uuid.uuid4()); coroutine yields harness_batch_item_start, then bridges to run_sub_agent_loop, forwarding nested events with item's task_id; on terminal sub-agent result, atomically appends `{item_index, status, result|error}` JSON line to <stem>.jsonl via WorkspaceService.append_line; yields harness_batch_item_complete."
    - "Tool curation (BLOCKER-6 fix): dispatcher computes `curated_tools = [t for t in (phase.tools or []) if t not in PANEL_LOCKED_EXCLUDED_TOOLS]` ONCE per phase (mirroring the LLM_AGENT pattern at harness_engine.py:594). The curated list is forwarded into each sub-agent invocation via `parent_tool_context['phase_tools']` so batch sub-agents inherit the same tool curation Phase 22 CR-06 (RAG tools) requires. The signature `run_sub_agent_loop(parent_tool_context=...)` is the verified inheritance channel — see sub_agent_loop.py:142,256 (parent_tool_context dict is passed through to tool_context). NOTE: sub_agent_loop.py:212-225 currently builds tools from the registry independent of any per-phase override; if the executor confirms during Task 1 that `parent_tool_context['phase_tools']` is not yet honored downstream, the executor MUST add a small hook in sub_agent_loop.py to filter `sub_tools` against `phase_tools` when present (treat as a sub-task within the same atomic commit). Either way, the BATCH dispatcher's responsibility to PASS the curated list is non-negotiable."
    - "Sub-agent failure isolation: if run_sub_agent_loop raises or yields a terminal error, the dispatcher writes `{item_index, status: 'failed', error: {...}}` to JSONL and continues batch (D-11, STATUS-04)."
    - "After all batches complete: read <stem>.jsonl, parse all rows, sort by item_index ascending, build sorted JSON array, call WorkspaceService.write_text_file(<stem>.json, json.dumps(sorted)) — this is the downstream artifact (D-06)."
    - "Final harness_batch_complete event includes {failed_count: N}; harness_phase_complete event includes {partial: True} when failed_count > 0 (additive — existing consumers ignore unknown fields)."
    - "Egress filter is applied INSIDE run_sub_agent_loop already (Phase 19 D-21) — dispatcher does NOT need a duplicate egress check. Confirmed in PATTERNS.md."
    - "No automatic retries — failed items stay failed. STATUS-03 invariant preserved."
    - "item_index is globally unique across all batches — uses original parsed-array index (e.g. 7 items at batch_size=3 → batches [0,1,2], [3,4,5], [6])."
  artifacts:
    - path: "backend/app/services/harness_engine.py"
      provides: "LLM_BATCH_AGENTS dispatch branch with asyncio.Queue fan-in + JSONL append + merge pass + resume logic + phase.tools curation propagation"
      contains: "LLM_BATCH_AGENTS"
    - path: "backend/tests/services/test_harness_engine_batch.py"
      provides: "8 test cases: concurrent dispatch, JSONL append per item, resume skip ok, resume skip failed, failure marker continues, merge sorted, item_index globally unique, phase.tools curation inheritance"
      contains: "test_batch_concurrent_dispatch"
  key_links:
    - from: "_dispatch_phase LLM_BATCH_AGENTS"
      to: "asyncio.Queue"
      via: "fan-in multiplexer for concurrent sub-agents"
      pattern: "asyncio\\.Queue\\(\\)"
    - from: "_dispatch_phase LLM_BATCH_AGENTS per-item terminal"
      to: "WorkspaceService.append_line"
      via: "atomic JSONL line write per completed item (Plan 21-01)"
      pattern: "append_line"
    - from: "_dispatch_phase LLM_BATCH_AGENTS post-batch"
      to: "WorkspaceService.write_text_file"
      via: "merge pass writing sorted <stem>.json"
      pattern: "write_text_file"
    - from: "_dispatch_phase LLM_BATCH_AGENTS"
      to: "run_sub_agent_loop"
      via: "per-item sub-agent invocation with curated phase.tools via parent_tool_context['phase_tools']"
      pattern: "run_sub_agent_loop"
    - from: "_dispatch_phase LLM_BATCH_AGENTS"
      to: "PANEL_LOCKED_EXCLUDED_TOOLS filter"
      via: "tool curation mirroring LLM_AGENT at line 594"
      pattern: "PANEL_LOCKED_EXCLUDED_TOOLS"
---

<objective>
Implement the `LLM_BATCH_AGENTS` phase dispatch in `harness_engine.py` — the second and final Phase 21 phase type. This is the largest single piece of Phase 21 work: concurrent sub-agent fan-out via `asyncio.Queue`, JSONL atomic append per item, mid-batch resume, post-batch merge, item-level SSE event emission, AND propagation of `phase.tools` curation so batch sub-agents inherit the same tool restrictions LLM_AGENT phases enjoy.

**On WARNING-1 (split decision):** This task implements 5 closely-coupled subsystems (input parse, resume detection, fan-in, JSONL append, merge) that share state (`done_set`, `failed_count`, `queue`, `tasks` list) and data flow within a single dispatch branch. Splitting into 21-03a/21-03b would force the resume-detection helper and the queue-fan-in to share a fragile interface across plan boundaries — the executor would have to mock the resume helper inside the fan-in tests. We keep the task atomic, with 8 unit tests budgeting context tightly. If the executor finds context exhaustion during execution, they may extract `_merge_jsonl_to_json` and `_stem_paths` to a separate commit within the same plan; structural splitting is not required.

Purpose: Turns the harness engine from sequential into a fan-out workflow platform. Phase 22 Contract Review will register two `llm_batch_agents` phases (risk analysis at batch_size=5, redlines at batch_size=5) that depend on this dispatcher AND on the curated-tools inheritance for RAG tool access (CR-06).
Output: Engine modifications + 8 unit tests covering BATCH-01..07 plus tool-curation inheritance.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/STATE.md
@.planning/phases/21-batched-parallel-sub-agents-human-in-the-loop/21-CONTEXT.md
@.planning/phases/21-batched-parallel-sub-agents-human-in-the-loop/21-PATTERNS.md
@.planning/phases/21-batched-parallel-sub-agents-human-in-the-loop/21-01-workspace-jsonl-append-helper-PLAN.md
@.planning/phases/21-batched-parallel-sub-agents-human-in-the-loop/21-02-hil-dispatcher-and-engine-signature-PLAN.md
@CLAUDE.md
@backend/app/services/harness_engine.py
@backend/app/services/sub_agent_loop.py
@backend/app/services/workspace_service.py
@backend/app/harnesses/types.py
@backend/tests/services/test_harness_engine.py

<interfaces>
<!-- Patterns extracted from existing code (verified during planning). -->

From backend/app/services/sub_agent_loop.py:
```python
# Line 412 — REUSED VERBATIM by each batch item. Note: NO `tools` parameter.
async def run_sub_agent_loop(
    *,
    description: str,
    context_files: list[str],
    parent_user_id: str,
    parent_user_email: str,
    parent_token: str,
    parent_tool_context: dict,    # <-- the inheritance channel for phase.tools curation (BLOCKER-6 fix)
    parent_thread_id: str,
    parent_user_msg_id: str,    # SSE correlation id; pass per-item task_id here
    client,                     # OpenRouter client
    sys_settings: dict,
    web_search_effective: bool,
    task_id: str,               # per-item UUID for nested event tagging (D-10)
    parent_redaction_registry,
) -> AsyncIterator[dict]:
    """Yields SSE-shaped events. Last event is `_terminal_result` dict.

    Tool curation: line 256 propagates parent_tool_context into the per-call
    `tool_context = {**parent_tool_context, "user_email": ..., "token": ...}`.
    Batch dispatcher passes `parent_tool_context={"phase_tools": curated_tools, ...}`;
    if downstream consumers don't yet honor `phase_tools`, the executor adds a
    small filter at sub_agent_loop.py:223 (`sub_tools = [t for t in sub_tools if
    not phase_tools or t["function"]["name"] in phase_tools]`).
    """
```

From backend/app/services/harness_engine.py LLM_AGENT block (line 594 — the curation analog to mirror):
```python
# Line 594 — VERIFIED:
curated_tools = [t for t in phase.tools if t not in PANEL_LOCKED_EXCLUDED_TOOLS]
```

From backend/app/services/workspace_service.py (post Plan 21-01):
```python
class WorkspaceService:
    async def read_file(thread_id, file_path) -> dict          # {content, ...} | {error: 'file_not_found', ...}
    async def write_text_file(thread_id, file_path, content, source) -> dict
    async def append_line(thread_id, file_path, line) -> dict  # added by Plan 21-01
```

From backend/app/services/harness_engine.py (post Plan 21-02):
```python
EVT_BATCH_START = "harness_batch_start"            # already declared (Phase 20)
EVT_BATCH_COMPLETE = "harness_batch_complete"      # already declared (Phase 20)
EVT_BATCH_ITEM_START = "harness_batch_item_start"  # added by Plan 21-02
EVT_BATCH_ITEM_COMPLETE = "harness_batch_item_complete"  # added by Plan 21-02
PANEL_LOCKED_EXCLUDED_TOOLS  # already imported at line 54 — REUSE for batch curation
```

From backend/app/harnesses/types.py:
```python
@dataclass(frozen=True, slots=True)
class PhaseDefinition:
    workspace_inputs: list[str]   # batch reads workspace_inputs[0] = items file
    workspace_output: str         # batch interprets stem; writes <stem>.jsonl + <stem>.json
    batch_size: int = 5           # default chunk size (BATCH-03)
    tools: list[str] = field(default_factory=list)  # phase-level tool whitelist (CR-06)
```

asyncio.Queue fan-in pattern (chat.py:646-741):
```python
queue = asyncio.Queue()
async def producer(item): ...     # creates events, await queue.put({...})
tasks = [asyncio.create_task(producer(i)) for i in batch]
done_count = 0
while done_count < len(tasks):
    try:
        evt = await asyncio.wait_for(queue.get(), timeout=0.1)
        if evt.get("_done"): done_count += 1
        else: yield evt
    except asyncio.TimeoutError:
        if all(t.done() for t in tasks):
            break
# drain remainder
while not queue.empty():
    evt = queue.get_nowait()
    if not evt.get("_done"): yield evt
await asyncio.gather(*tasks, return_exceptions=True)
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Implement LLM_BATCH_AGENTS dispatch — input parse, resume detection, asyncio.Queue fan-in, JSONL append, merge pass, item-level SSE, and phase.tools curation propagation (RED → GREEN with 8 tests)</name>
  <files>backend/app/services/harness_engine.py, backend/tests/services/test_harness_engine_batch.py</files>
  <read_first>
    - backend/app/services/harness_engine.py — full file. Critical lines: 84-86 + (post 21-02) EVT_BATCH_ITEM_START/COMPLETE constants; 54 (PANEL_LOCKED_EXCLUDED_TOOLS import); 592-690 LLM_AGENT dispatcher block — line 594 has the verified `curated_tools = [t for t in phase.tools if t not in PANEL_LOCKED_EXCLUDED_TOOLS]` pattern to mirror; 692+ residual PHASE21_PENDING runtime stub now scoped to LLM_BATCH_AGENTS only after Plan 21-02 (line 697 `"code": "PHASE21_PENDING"` literal — this is the ONLY runtime occurrence remaining).
    - backend/app/services/sub_agent_loop.py around line 412 (signature), line 142 (parent_tool_context type hint), line 256 (the `tool_context = {**parent_tool_context, ...}` propagation site), lines 212-225 (where sub_tools are built — the executor inspects this region to determine if a `phase_tools` honor hook is already present or needs to be added in this commit).
    - backend/app/routers/chat.py lines 632-741 — the canonical asyncio.Queue fan-in pattern that Phase 21 mirrors. Read this verbatim.
    - backend/app/services/workspace_service.py — confirm `append_line` signature from Plan 21-01.
    - .planning/phases/21-batched-parallel-sub-agents-human-in-the-loop/21-PATTERNS.md — sections "harness_engine.py — replace lines 692-698 PHASE21_PENDING stubs" (lines 33-145) and "harness_engine.py — asyncio.Queue fan-in for `LLM_BATCH_AGENTS`" (lines 181-223).
    - .planning/phases/21-batched-parallel-sub-agents-human-in-the-loop/21-CONTEXT.md — D-05 (JSONL line shape), D-06 (merge pass after all batches), D-07 (resume logic), D-08 (item-level SSE events), D-10 (per-item task_id UUID), D-11 (failure marker), D-12 (resume skips both ok and failed).
    - backend/tests/services/test_harness_engine.py — full file. Mock pattern + `_collect` helper + MOCK_BASES dict pattern.
  </read_first>
  <behavior>
    Tests in `backend/tests/services/test_harness_engine_batch.py`:

    - Test 1 `test_batch_concurrent_dispatch`: 6 items at batch_size=3 → 2 batches; mock `run_sub_agent_loop` to yield `_terminal_result` per call. Collect events; assert event sequence contains EVT_BATCH_START twice (one per batch), EVT_BATCH_ITEM_START 6 times, EVT_BATCH_ITEM_COMPLETE 6 times, EVT_BATCH_COMPLETE twice; assert per-item events from concurrent items can interleave (sort assertion: not guaranteed strict order within a batch but item_index range correct).
    - Test 2 `test_batch_jsonl_append_per_item`: 3 items; mock WorkspaceService.append_line as a recording AsyncMock; assert called exactly 3 times; assert each call payload includes both `item_index` and `status: "ok"` (or "failed"); assert path is `<stem>.jsonl`.
    - Test 3 `test_batch_resume_skips_done_items`: pre-seed `read_file('<stem>.jsonl')` mock to return content with rows for item_index 0 and 2 (status=ok). 4-item input. Assert run_sub_agent_loop is invoked exactly 2 times (items 1 and 3 only). Assert append_line is called only for items 1 and 3.
    - Test 4 `test_batch_resume_skips_failed_items`: pre-seed JSONL with item_index 0 status=failed. 2-item input. Assert run_sub_agent_loop is invoked exactly 1 time (item 1 only) — failed items NOT re-queued (D-12).
    - Test 5 `test_batch_failure_marker_continues`: 3 items; mock run_sub_agent_loop to raise Exception for item 1, succeed for items 0 and 2. Assert append_line called 3 times — item 1's call payload has `status: "failed"` and `error: {...}`. Assert all 3 items processed (batch did NOT abort on item 1's failure). Assert final harness_batch_complete event has `failed_count: 1`. Assert harness_phase_complete event has `partial: True`.
    - Test 6 `test_batch_merge_pass_sorted`: 4 items; mock JSONL state at end-of-batch to contain rows in order [3, 0, 2, 1]. Assert WorkspaceService.write_text_file called once with path `<stem>.json` and content that, when parsed as JSON, is a list sorted by item_index ascending [item_0, item_1, item_2, item_3].
    - Test 7 `test_batch_item_index_globally_unique`: 7 items at batch_size=3 → 3 batches. Capture all EVT_BATCH_ITEM_START events; assert item_index values are exactly {0,1,2,3,4,5,6} with no per-batch reset to 0.
    - Test 8 `test_batch_sub_agent_inherits_phase_tools_curation` (BLOCKER-6 regression): construct a phase with `phase.tools=["search_documents", "query_database", "task"]` (where `task` is in PANEL_LOCKED_EXCLUDED_TOOLS). Patch `app.services.harness_engine.run_sub_agent_loop` as a recording AsyncMock async-generator. Dispatch a 2-item batch. For each `run_sub_agent_loop` call, capture `kwargs["parent_tool_context"]` and assert it contains key `"phase_tools"` with the curated list `["search_documents", "query_database"]` (PANEL_LOCKED tools removed). Assert the curated list is IDENTICAL across both calls (computed once per phase, not per item).
  </behavior>
  <action>
    Edit `backend/app/services/harness_engine.py`. Replace the residual `PHASE21_PENDING` runtime stub for LLM_BATCH_AGENTS with the full dispatcher.

    Add at top of file (with other imports):
    ```python
    import uuid
    from pathlib import PurePosixPath
    ```
    (`PANEL_LOCKED_EXCLUDED_TOOLS` is already imported at line 54 — do NOT re-import.)

    Add a small helper near `_summarize_output`:
    ```python
    def _stem_paths(workspace_output: str) -> tuple[str, str]:
        """For 'risk-analysis.json' → ('risk-analysis.jsonl', 'risk-analysis.json').
        For 'risk-analysis' → ('risk-analysis.jsonl', 'risk-analysis.json').
        """
        p = PurePosixPath(workspace_output)
        stem = p.stem if p.suffix else p.name
        parent = str(p.parent) if str(p.parent) not in (".", "") else ""
        jsonl_name = f"{stem}.jsonl"
        json_name = f"{stem}.json"
        if parent:
            return f"{parent}/{jsonl_name}", f"{parent}/{json_name}"
        return jsonl_name, json_name
    ```

    Replace the LLM_BATCH_AGENTS branch (the surviving PHASE21_PENDING block from Plan 21-02). Insert above the residual stub:

    ```python
    # Phase 21 / BATCH-01..07: LLM_BATCH_AGENTS dispatch.
    if phase.phase_type == PhaseType.LLM_BATCH_AGENTS:
        ws = WorkspaceService(token=token)

        # 0. BLOCKER-6 fix: curate phase.tools ONCE per phase, mirroring LLM_AGENT
        #    pattern at harness_engine.py:594. The curated list is propagated to
        #    every batch sub-agent via parent_tool_context['phase_tools'] so Phase 22
        #    CR-06 (RAG tools) inherit correctly.
        curated_tools = [t for t in (phase.tools or []) if t not in PANEL_LOCKED_EXCLUDED_TOOLS]

        # 1. BATCH-01: parse items from workspace_inputs[0]
        if not phase.workspace_inputs:
            yield {"_terminal_phase_result": {
                "error": "batch_no_input", "code": "BATCH_NO_INPUT",
                "detail": "phase.workspace_inputs is empty",
            }}
            return
        items_path = phase.workspace_inputs[0]
        items_read = await ws.read_file(thread_id, items_path)
        if "error" in items_read:
            yield {"_terminal_phase_result": {
                "error": "batch_input_unreadable", "code": "BATCH_INPUT_UNREADABLE",
                "detail": items_read.get("detail", "read failed"),
            }}
            return
        try:
            all_items = json.loads(items_read.get("content", "[]"))
            if not isinstance(all_items, list):
                raise ValueError("items file must be a JSON array")
        except Exception as exc:
            yield {"_terminal_phase_result": {
                "error": "batch_input_invalid", "code": "BATCH_INPUT_INVALID",
                "detail": str(exc)[:500],
            }}
            return

        # 2. BATCH-07: resume detection — read <stem>.jsonl, build done_set
        jsonl_path, merged_path = _stem_paths(phase.workspace_output)
        done_set: set[int] = set()
        existing_jsonl = await ws.read_file(thread_id, jsonl_path)
        if "error" not in existing_jsonl:
            for line in (existing_jsonl.get("content", "") or "").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                    if "item_index" in row:
                        done_set.add(int(row["item_index"]))
                except Exception:
                    continue   # skip malformed lines

        # 3. Compute remaining_items as (original_index, item) tuples — globally unique index
        remaining = [(i, it) for i, it in enumerate(all_items) if i not in done_set]
        items_total = len(all_items)
        if not remaining:
            # Already complete — go straight to merge pass
            await _merge_jsonl_to_json(ws, thread_id, jsonl_path, merged_path)
            yield {"_terminal_phase_result": {"text": f"All {items_total} items previously completed"}}
            return

        # 4. BATCH-02/BATCH-03: chunk remaining into batches of phase.batch_size
        bs = max(1, phase.batch_size or 5)
        batches = [remaining[i:i + bs] for i in range(0, len(remaining), bs)]

        # 5. Per-batch concurrent dispatch via asyncio.Queue fan-in
        failed_count = 0
        for batch_idx, batch_chunk in enumerate(batches):
            yield {
                "type": EVT_BATCH_START,
                "harness_run_id": harness_run_id,
                "phase_index": phase_index,
                "phase_name": phase.name,
                "batch_index": batch_idx,
                "batch_size": len(batch_chunk),
                "items_total": items_total,
            }

            queue: asyncio.Queue = asyncio.Queue()

            async def _run_one(global_idx: int, item: dict):
                """Producer: dispatch one sub-agent, append result to JSONL, mark done."""
                task_id = str(uuid.uuid4())
                await queue.put({
                    "type": EVT_BATCH_ITEM_START,
                    "harness_run_id": harness_run_id,
                    "phase_index": phase_index,
                    "phase_name": phase.name,
                    "item_index": global_idx,
                    "items_total": items_total,
                    "task_id": task_id,
                    "batch_index": batch_idx,
                })
                sub_status = "ok"
                sub_result: dict = {}
                description = phase.system_prompt_template + f"\n\nItem to process: {json.dumps(item, ensure_ascii=False)}"
                try:
                    collected_text: list[str] = []
                    async for ev in run_sub_agent_loop(
                        description=description,
                        context_files=phase.workspace_inputs,
                        parent_user_id=user_id,
                        parent_user_email=user_email,
                        parent_token=token,
                        # BLOCKER-6 fix: propagate curated tools via the verified
                        # parent_tool_context channel (sub_agent_loop.py:142,256).
                        parent_tool_context={"phase_tools": curated_tools},
                        parent_thread_id=thread_id,
                        parent_user_msg_id=harness_run_id,
                        client=or_svc.client,
                        sys_settings=sys_settings,
                        web_search_effective=False,
                        task_id=task_id,
                        parent_redaction_registry=registry,
                    ):
                        if "_terminal_result" in ev:
                            term = ev["_terminal_result"]
                            if isinstance(term, dict) and term.get("error"):
                                sub_status = "failed"
                                sub_result = {"error": term.get("error"),
                                              "code": term.get("code", "TASK_FAILED"),
                                              "detail": term.get("detail", "")[:500]}
                            else:
                                sub_result = {"text": "\n".join(collected_text), "terminal": term}
                            break
                        if isinstance(ev, dict) and ev.get("type") == "delta":
                            collected_text.append(ev.get("content", ""))
                        # Forward nested SSE events with task_id correlation
                        await queue.put({**ev, "task_id": task_id, "batch_index": batch_idx})
                except Exception as exc:
                    logger.error(
                        "_dispatch_phase: batch sub_agent crash phase=%s item=%s: %s",
                        phase.name, global_idx, exc, exc_info=True,
                    )
                    sub_status = "failed"
                    sub_result = {
                        "error": "sub_agent_crashed",
                        "code": "TASK_LOOP_CRASH",
                        "detail": str(exc)[:500],
                    }

                # Append to JSONL — uses Plan 21-01's atomic append_line
                line_payload: dict = {"item_index": global_idx, "status": sub_status}
                if sub_status == "failed":
                    line_payload["error"] = sub_result
                else:
                    line_payload["result"] = sub_result
                try:
                    await ws.append_line(
                        thread_id, jsonl_path, json.dumps(line_payload, ensure_ascii=False)
                    )
                except Exception as exc:
                    logger.warning(
                        "_dispatch_phase: append_line failed phase=%s item=%s: %s",
                        phase.name, global_idx, exc,
                    )

                await queue.put({
                    "type": EVT_BATCH_ITEM_COMPLETE,
                    "harness_run_id": harness_run_id,
                    "phase_index": phase_index,
                    "phase_name": phase.name,
                    "item_index": global_idx,
                    "items_total": items_total,
                    "task_id": task_id,
                    "status": sub_status,
                    "batch_index": batch_idx,
                })
                await queue.put({"_done": True, "_failed": sub_status == "failed"})

            # Spawn producers and drain queue
            tasks = [asyncio.create_task(_run_one(gi, it)) for gi, it in batch_chunk]
            done_count = 0
            target = len(tasks)
            while done_count < target:
                try:
                    evt = await asyncio.wait_for(queue.get(), timeout=0.1)
                    if evt.get("_done"):
                        done_count += 1
                        if evt.get("_failed"):
                            failed_count += 1
                        continue
                    yield evt
                except asyncio.TimeoutError:
                    if all(t.done() for t in tasks):
                        break
            # Drain remainder
            while not queue.empty():
                evt = queue.get_nowait()
                if evt.get("_done"):
                    done_count += 1
                    if evt.get("_failed"):
                        failed_count += 1
                    continue
                yield evt
            await asyncio.gather(*tasks, return_exceptions=True)

            yield {
                "type": EVT_BATCH_COMPLETE,
                "harness_run_id": harness_run_id,
                "phase_index": phase_index,
                "phase_name": phase.name,
                "batch_index": batch_idx,
                "failed_count": failed_count,
            }

        # 6. BATCH-05/D-06: merge pass — read JSONL, sort by item_index, write final JSON
        await _merge_jsonl_to_json(ws, thread_id, jsonl_path, merged_path)

        # 7. Terminal — surface partial-completion via additive field on phase_complete
        terminal_output: dict = {"text": f"Processed {items_total} items ({failed_count} failed)"}
        if failed_count > 0:
            terminal_output["partial"] = True
            terminal_output["failed_count"] = failed_count
        yield {"_terminal_phase_result": terminal_output}
        return
    ```

    Add the merge helper at module scope:
    ```python
    async def _merge_jsonl_to_json(
        ws: WorkspaceService, thread_id: str, jsonl_path: str, json_path: str
    ) -> None:
        """D-06: read JSONL, sort by item_index, write sorted JSON array."""
        existing = await ws.read_file(thread_id, jsonl_path)
        if "error" in existing:
            return
        rows: list[dict] = []
        for line in (existing.get("content", "") or "").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
        rows.sort(key=lambda r: r.get("item_index", 0))
        try:
            await ws.write_text_file(
                thread_id, json_path, json.dumps(rows, ensure_ascii=False, indent=2),
                source="harness",
            )
        except Exception as exc:
            logger.warning("_merge_jsonl_to_json: write failed: %s", exc)
    ```

    **sub_agent_loop.py phase_tools honor (conditional sub-edit):** during execution, `read_first` requires inspecting `sub_agent_loop.py:212-225` (the sub_tools build region). If a `phase_tools` honor hook is NOT yet present, add it in the SAME atomic commit:

    ```python
    # Inside run_sub_agent_loop, after sub_tools is initially computed (line ~223):
    phase_tools = parent_tool_context.get("phase_tools") if parent_tool_context else None
    if phase_tools is not None:  # explicit allow-list; empty list means "no tools"
        sub_tools = [t for t in sub_tools if t["function"]["name"] in phase_tools]
    ```

    **Outer phase-result event extension (additive):** find where `EVT_PHASE_COMPLETE` is yielded after a successful phase. Extend the payload conditionally: if the phase was LLM_BATCH_AGENTS AND the terminal output had `partial: True`, append `partial: True` and `failed_count: N` to the phase_complete event payload. Keep this purely additive — existing consumers ignore unknown fields.

    Remove the residual `PHASE21_PENDING` runtime stub for LLM_BATCH_AGENTS (it is now fully implemented). After this edit, the only `PHASE21_PENDING` mention left in the file is the docstring at line 26 (which is unaffected).

    **Tests** — `backend/tests/services/test_harness_engine_batch.py`. Mirror imports + MOCK_BASES dict + `_collect` helper from `test_harness_engine.py` and `test_harness_engine_human_input.py`. Use `AsyncMock` for `WorkspaceService.read_file` (to seed JSONL state for resume tests), `AsyncMock` for `WorkspaceService.append_line`, `AsyncMock` for `WorkspaceService.write_text_file`, and `AsyncMock` patching `app.services.harness_engine.run_sub_agent_loop` — make it an async generator that yields the per-item terminal AND records its kwargs for Test 8.

    For the concurrent test, build a stateful append_line mock that records `(call_index, payload)` tuples; assert the call_index sequence does NOT have to match item_index sequence (proving concurrent execution is happening in test).

    For Test 8 specifically: capture all `kwargs["parent_tool_context"]` values across calls; assert each contains `phase_tools=["search_documents", "query_database"]`. Assert `len(set(id(c["phase_tools"]) for c in captured))` confirms either the same list object reused OR equal lists (computed once per phase).

    Run order:
    1. RED: write all 8 tests; run `cd backend && source venv/bin/activate && pytest tests/services/test_harness_engine_batch.py -x`. ALL must fail.
    2. GREEN: implement the dispatcher (and the sub_agent_loop honor hook if needed). Rerun. ALL must pass.
    3. Confirm no regression: `pytest backend/tests/services/test_harness_engine.py backend/tests/services/test_harness_engine_human_input.py` exits 0.
    4. Atomic commit: `gsd-sdk query commit "feat(21-03): implement LLM_BATCH_AGENTS dispatcher with asyncio.Queue fan-in + JSONL resume + phase.tools curation" --files backend/app/services/harness_engine.py backend/tests/services/test_harness_engine_batch.py backend/app/services/sub_agent_loop.py`.
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pytest tests/services/test_harness_engine_batch.py tests/services/test_harness_engine.py tests/services/test_harness_engine_human_input.py -v --tb=short</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "if phase.phase_type == PhaseType.LLM_BATCH_AGENTS" backend/app/services/harness_engine.py` returns 1.
    - `grep -c "asyncio.Queue" backend/app/services/harness_engine.py` returns >= 1.
    - `grep -c "asyncio.create_task" backend/app/services/harness_engine.py` returns >= 1 (in batch dispatcher).
    - `grep -c "ws.append_line" backend/app/services/harness_engine.py` returns >= 1.
    - `grep -c "_merge_jsonl_to_json" backend/app/services/harness_engine.py` returns >= 2 (definition + call).
    - `grep -c "EVT_BATCH_ITEM_START\|EVT_BATCH_ITEM_COMPLETE" backend/app/services/harness_engine.py` returns >= 4 (2 declarations + 2 emit sites).
    - `grep -c '"code": "PHASE21_PENDING"' backend/app/services/harness_engine.py` returns 0 (BLOCKER-3 fix: both runtime stubs removed; the docstring at line 26 does NOT match this exact literal).
    - `grep -c "_stem_paths" backend/app/services/harness_engine.py` returns >= 2 (definition + call site).
    - `grep -c "curated_tools" backend/app/services/harness_engine.py` returns >= 2 (BLOCKER-6 fix: declaration in BATCH dispatcher + usage in _run_one parent_tool_context — note this counts the LLM_AGENT pattern at line 594 as a 3rd occurrence, but the minimum of 2 from the BATCH branch alone is the binding floor; existing LLM_AGENT match is bonus).
    - `grep -c "PANEL_LOCKED_EXCLUDED_TOOLS" backend/app/services/harness_engine.py` returns >= 2 (existing LLM_AGENT use at line 594 + new BATCH use; the import at line 54 is a 3rd match — all acceptable).
    - `grep -c '"phase_tools"' backend/app/services/harness_engine.py` returns >= 1 (parent_tool_context key).
    - `pytest backend/tests/services/test_harness_engine_batch.py` exits 0 with all 8 tests passing.
    - `pytest backend/tests/services/test_harness_engine.py backend/tests/services/test_harness_engine_human_input.py` exits 0 (no regression).
    - `cd backend && python -c "from app.main import app; print('OK')"` prints `OK`.
  </acceptance_criteria>
  <done>
    LLM_BATCH_AGENTS dispatcher fully implemented with concurrent fan-in, JSONL atomic append, mid-batch resume, sorted merge pass, item-level SSE events, partial-completion marker, AND phase.tools curation propagated to every batch sub-agent via parent_tool_context['phase_tools']. All 8 tests green. No PHASE21_PENDING runtime stubs remain. No regression.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| dispatcher → N concurrent run_sub_agent_loop calls | each sub-agent inherits parent JWT (SEC-02); per-item failure isolation already in run_sub_agent_loop (Phase 19 D-12); curated tool list inherited via parent_tool_context |
| each sub-agent → cloud OpenRouter | egress filter applied INSIDE run_sub_agent_loop (Phase 19 D-21) — dispatcher does NOT add a duplicate filter |
| append_line → workspace_files row | RLS-scoped DB write under user JWT; per-(thread,path) lock (Plan 21-01) |
| dispatcher input parser → all_items JSON | data origin is workspace file; could be malformed |
| phase.tools curation → batch sub-agent | curation is single-source per phase; no per-item drift possible |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-21-03-01 | Denial-of-Service | unbounded item count → unbounded asyncio.create_task spawn | mitigate | Concurrency is bounded by phase.batch_size (default 5) per batch — never more than batch_size in flight at once. Total items also implicitly bounded by 1 MB workspace input file cap (WS-03). |
| T-21-03-02 | Denial-of-Service | infinite recursion if a batch sub-agent triggers another batch | mitigate | Phase 19 D-02 already strips `task` tool from sub-agent context (recursive sub-agents disabled, .planning/STATE.md invariant). Batch sub-agent inherits same restriction; additionally PANEL_LOCKED_EXCLUDED_TOOLS curation removes `task` from phase.tools as a defense-in-depth. |
| T-21-03-03 | Tampering | malformed items file (non-JSON, non-array, oversize) | mitigate | json.loads in try/except yields batch_input_invalid terminal; isinstance check rejects non-array; 1 MB workspace cap bounds size. |
| T-21-03-04 | Race / data corruption | concurrent append_line from N sub-agents | mitigate | Plan 21-01's per-(thread, file_path) asyncio.Lock serializes appends within a single worker. Cross-process upgrade carried as v1.0 D-31 deferred. |
| T-21-03-05 | Information Disclosure | workspace_inputs paths leak via path-traversal in JSONL/merged path | mitigate | _stem_paths only manipulates the stem of phase.workspace_output (developer-defined harness config); validate_workspace_path is called by ws.append_line and ws.write_text_file (defense in depth). |
| T-21-03-06 | Information Disclosure | per-item PII leaks to cloud LLM | mitigate | Egress filter is enforced inside run_sub_agent_loop (Phase 19 SEC-04). Privacy invariant preserved unchanged. |
| T-21-03-07 | Repudiation | which sub-agent failed why? | mitigate | JSONL line for failed items contains structured error {error, code, detail} — full audit trail in workspace, mirrors STATUS-02 append-only error contract. |
| T-21-03-08 | Tampering | resume reads forged JSONL to skip items | accept | JSONL is RLS-scoped under user's own thread; only the same user can write it. No cross-user attack surface. |
| T-21-03-09 | Elevation | batch sub-agent calls a tool outside phase.tools allow-list | mitigate | curated_tools propagated via parent_tool_context['phase_tools']; sub_agent_loop honors the filter when present. PANEL_LOCKED_EXCLUDED_TOOLS removed unconditionally. Phase 22 CR-06 RAG access works because phase.tools=['search_documents', ...] explicitly allow-lists those tools. |
</threat_model>

<verification>
- 8 batch tests pass.
- 6 HIL tests still pass (Plan 21-02 unaffected).
- 5 pause/resume regression tests still pass (Plan 21-02 Task 0).
- 15 existing harness_engine tests still pass.
- `from app.main import app` imports clean.
- No `PHASE21_PENDING` runtime literal remains (only the docstring at line 26).
- Atomic commit `feat(21-03): implement LLM_BATCH_AGENTS dispatcher` landed.
</verification>

<success_criteria>
LLM_BATCH_AGENTS phase type fully dispatchable: parses items, resumes from JSONL, fans out via asyncio.Queue with curated tools inherited from phase.tools, atomically appends per item, isolates failures, merges sorted JSON output, surfaces partial completion. All 8 tests green. Phase 21 engine work is COMPLETE after this plan.
</success_criteria>

<output>
After completion, create `.planning/phases/21-batched-parallel-sub-agents-human-in-the-loop/21-03-SUMMARY.md`
</output>
</content>
</invoke>