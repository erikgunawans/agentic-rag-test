---
phase: 10-code-execution-sandbox-backend
plan: 05
subsystem: chat-sse-streaming
tags: [sse, streaming, chat, tool-loop, redaction, sandbox, asyncio]
dependency_graph:
  requires: [10-04]
  provides: [SANDBOX-03]
  affects: [backend/app/routers/chat.py, backend/tests/routers/]
tech_stack:
  added: [asyncio.Queue, asyncio.create_task, asyncio.wait_for]
  patterns:
    - queue-adapter for async-generator callback impedance
    - per-line anonymization for SSE-streamed code output
    - module-level async-generator test helper for inner function testing
key_files:
  modified:
    - backend/app/routers/chat.py
  created:
    - backend/tests/routers/__init__.py
    - backend/tests/routers/test_chat_sandbox_streaming.py
decisions:
  - "Queue-adapter pattern over generator-yielded-streaming refactor (planner alert #1)"
  - "Per-line anonymize_tool_output (option b) over skeleton-emit for code_stdout/code_stderr (planner alert #2)"
  - "Module-level _run_tool_loop_for_test helper to unit-test inner async generator"
metrics:
  duration: "~25 minutes"
  completed: "2026-05-01"
  tasks_completed: 1
  tasks_total: 1
  files_modified: 1
  files_created: 2
  tests_added: 8
  tests_regression: 315
---

# Phase 10 Plan 05: chat.py SSE Sandbox Streaming Summary

**One-liner:** Queue-adapter streams code_stdout/code_stderr SSE events line-by-line from execute_code with per-line PII anonymization and tool_call_id tagging.

## What Was Built

Modified `backend/app/routers/chat.py` to thread the sandbox `stream_callback` through `_run_tool_loop`, enabling real-time stdout/stderr SSE events during `execute_code` tool invocations (SANDBOX-03).

## Lines Modified in chat.py

| Change | Old Lines | New Lines | Description |
|--------|-----------|-----------|-------------|
| asyncio import | 1 | 1 | Added `import asyncio` (explicit, required for Queue/create_task/wait_for) |
| tool_context thread_id | 172–178 | 172–179 | Added `"thread_id": body.thread_id` to tool_context dict (D-P10-04) |
| Queue adapter setup | before line 245 | 252–288 | sandbox_event_queue + sandbox_stream_callback closure (alert #1 resolution) |
| redaction-ON execute_tool | 271–275 | 318–342 | Wrapped in create_task + queue drain; passes stream_callback=sandbox_callback |
| redaction-OFF execute_tool | 299–302 | 373–396 | Wrapped in create_task + queue drain; passes stream_callback=sandbox_callback |
| Branch A special-case | 566–571 | 566–577 | elif code_stdout/code_stderr → yield live (bypass redaction buffer) |
| Branch B special-case | 632–637 | 639–650 | elif code_stdout/code_stderr → yield live (bypass redaction buffer) |
| _run_tool_loop_for_test | (new) | 794–943 | Module-level test helper mirroring _run_tool_loop without closure deps |

## Queue-Adapter Pattern (Final Form)

```python
# Setup — BEFORE execute_tool, inside per-tool-call branch:
sandbox_event_queue: asyncio.Queue | None = None
sandbox_callback = None
if func_name == "execute_code":
    sandbox_event_queue = asyncio.Queue()

    async def sandbox_stream_callback(event_type: str, line: str):
        # Per-line anonymization when redaction_on=True (alert #2 resolution)
        emit_line = line
        if redaction_on and registry is not None:
            try:
                anon = await anonymize_tool_output({"line": line}, registry, redaction_service)
                if isinstance(anon, dict):
                    emit_line = anon.get("line", line)
            except Exception as _exc:
                logger.warning("sandbox stream anon failed — emitting skeleton")
                emit_line = ""  # skeleton fallback (D-89 safe default)
        await sandbox_event_queue.put({
            "type": event_type,
            "line": emit_line,
            "tool_call_id": tc["id"],
        })

    sandbox_callback = sandbox_stream_callback

# Execution — wraps execute_tool in a Task; drains queue while it runs:
if sandbox_event_queue is not None:
    tool_output_task = asyncio.create_task(
        tool_service.execute_tool(..., stream_callback=sandbox_callback)
    )
    # Drain while running
    while not tool_output_task.done():
        try:
            evt = await asyncio.wait_for(sandbox_event_queue.get(), timeout=0.1)
            yield evt["type"], evt
        except asyncio.TimeoutError:
            continue
    # Drain remainder
    while not sandbox_event_queue.empty():
        evt = sandbox_event_queue.get_nowait()
        yield evt["type"], evt
    tool_output = await tool_output_task
else:
    tool_output = await tool_service.execute_tool(..., stream_callback=None)
```

## Anonymization Decision Rationale (Alert #2 — Option (b) Chosen)

The planner flagged two options for handling PII in sandbox stdout/stderr:

- **(a) Skeleton-emit only** (`{type: code_stdout}` with no `line`): Maximally safe but defeats SANDBOX-03's streaming UX — the user sees no output during execution.
- **(b) Per-line anonymize before emit**: Each line is passed through `anonymize_tool_output({"line": ...}, registry, redaction_service)` inside the callback. The anonymized `emit_line` is what gets enqueued and ultimately SSE-emitted.

**Option (b) was chosen** because SANDBOX-03 is fundamentally about the user seeing code output. Surrogate values (Faker-generated names/numbers) preserve the semantic meaning while satisfying the D-89 privacy invariant. The skeleton-emit fallback (`emit_line = ""`) is used only when anonymization itself raises an exception, ensuring the pipeline never fails hard.

## Branch A/B Special-Case Rationale

Branches A (multi-agent path, line 568) and B (single-agent path, line 639) in `event_generator()` handle `_run_tool_loop` yields. The existing logic buffers ALL events when `redaction_on=True` to prevent partial-turn PII exposure if a later egress filter trips.

For `code_stdout`/`code_stderr` events, buffering-until-end-of-loop would defeat SANDBOX-03 (no real-time output). The special case bypasses the buffer because:
1. Lines are already anonymized inside `sandbox_stream_callback` before they're enqueued.
2. By the time branches A/B see these events, the `line` field contains surrogates (or an empty skeleton), never real PII.
3. SANDBOX-03's streaming UX requires live emit.

## Test Pass Count

| Category | Count |
|----------|-------|
| New tests (Phase 10 Plan 05) | 8 |
| Existing unit + service tests | 315 |
| **Total passing** | **323** |
| Failures | 0 |

## Acceptance Criteria Verification

- [x] `tool_context` dict in chat.py contains `thread_id` key sourced from `body.thread_id` (line 165)
- [x] `_run_tool_loop` contains an `asyncio.Queue` instantiation guarded by `if func_name == "execute_code"` (line 252)
- [x] `sandbox_stream_callback` closure exists and `.put()`s into the queue (lines 257–287)
- [x] When `redaction_on=True`, `anonymize_tool_output` is called on the line before enqueue (lines 269–281)
- [x] Two `execute_tool` call sites both pass `stream_callback=sandbox_callback` (lines 324, 378)
- [x] Branches A and B contain `elif event_type in ("code_stdout", "code_stderr"):` (lines 568, 639)
- [x] SSE payload shape: `{type, line, tool_call_id}` (D-P10-06)
- [x] All 8 new unit tests pass
- [x] 315 existing tests unaffected (no regressions)
- [x] Backend imports cleanly: `python -c "from app.main import app; print('OK')"`
- [x] Test 8 (byte-identical invariant for non-execute_code) passes

## Deviations from Plan

None — plan executed exactly as written. The `_run_tool_loop_for_test` module-level helper was planned and specified in the plan's `<action>` section.

## Known Stubs

None — the implementation is complete and wires real logic.

## Threat Flags

No new security-relevant surface beyond what the threat model in the plan describes.

## Self-Check: PASSED

Files created/modified:
- `/Users/erikgunawansupriatna/claude-code-agentic-rag-masterclass-1/backend/app/routers/chat.py` — FOUND
- `/Users/erikgunawansupriatna/claude-code-agentic-rag-masterclass-1/backend/tests/routers/__init__.py` — FOUND
- `/Users/erikgunawansupriatna/claude-code-agentic-rag-masterclass-1/backend/tests/routers/test_chat_sandbox_streaming.py` — FOUND

Commits:
- `eb0e15b` test(10-05): add failing tests — FOUND
- `b29ed54` feat(10-05): thread sandbox stream_callback — FOUND
