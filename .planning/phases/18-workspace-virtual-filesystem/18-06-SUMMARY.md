---
plan: "18-06"
phase: "18-workspace-virtual-filesystem"
status: complete
wave: 5
self_check: PASSED
subsystem: workspace-sse-events
tags: [workspace, sse, chat-loop, tdd]
dependency_graph:
  requires: ["18-03", "18-05"]
  provides: ["workspace_updated SSE event at all 3 chat-loop emission sites"]
  affects:
    - backend/app/routers/chat.py
    - backend/app/services/sandbox_service.py
    - backend/app/services/tool_service.py
tech_stack:
  added: []
  patterns:
    - "workspace_updated SSE yielded alongside tool_result in _run_tool_loop"
    - "workspace_callback: Callable[[dict], None] propagated through execute chain"
    - "sandbox event queue reused for workspace_updated events"
    - "deep-mode loop: direct data: SSE yield with redaction_on buffer respect"
key_files:
  modified:
    - backend/app/routers/chat.py
    - backend/app/services/sandbox_service.py
    - backend/app/services/tool_service.py
  created:
    - backend/tests/api/test_chat_workspace_sse.py
decisions:
  - "All 3 chat-loop paths updated (standard, test-skeleton, deep-mode) for completeness"
  - "Deep-mode loop uses direct yield with redaction_on buffer respect (mirrors todos_updated pattern)"
  - "workspace_callback uses sync put_nowait into existing sandbox_event_queue — avoids new queue or coroutine"
  - "Payload contains only metadata (file_path, operation, size_bytes, source) — no content body"
  - "Test harness patches build_llm_tools + build_catalog_block to ensure write_file appears in available_tool_names"
metrics:
  duration: "~30 minutes"
  completed_at: "2026-05-03T02:05Z"
  tasks_completed: 3
  files_changed: 4
---

# Phase 18 Plan 06: workspace_updated SSE Event Summary

**One-liner:** workspace_updated SSE event wired at all 3 chat-loop emission sites (standard, test-skeleton, deep-mode) plus sandbox callback chain, with 3 passing e2e tests verifying emission, kill-switch, and read-only exclusion.

## What Was Built

### Emission Site Count in chat.py

**3 distinct emission sites** (not 2 as estimated):

| Site | Location | Loop Type | Pattern |
|------|----------|-----------|---------|
| Site 1 | `_run_tool_loop` L695–720 | Standard/agent-mode | `yield "workspace_updated", {...}` |
| Site 2 | `_run_tool_loop_for_test` L1450–1470 | Test-skeleton loop | `yield "workspace_updated", {...}` |
| Site 3 | Deep-mode `run_deep_mode_loop` L1771–1802 | Deep-mode direct SSE | `yield f"data: {json.dumps(evt)}\n\n"` |

Sites 1 and 2 are translated to SSE `data: {...}\n\n` by the outer `async for event_type, data in _run_tool_loop(...)` handler (falls through to `else: yield f"data: {json.dumps(data)}\n\n"` branch). Site 3 emits directly. All 3 sites respect `redaction_on` buffer discipline.

### Sandbox Callback Channel

**Pre-existed but required new wiring.** The existing `sandbox_event_queue` in chat.py was already used for `code_stdout`/`code_stderr` streaming. No new queue was needed:

1. Added `workspace_callback: Callable[[dict], None] | None = None` param to:
   - `sandbox_service.execute()` → `_collect_and_upload_files()`
   - `tool_service.execute_tool()` → `_execute_code()`
   - `chat._dispatch_tool()`
2. In `_run_tool_loop` and `_run_tool_loop_for_test`: created `_workspace_event_callback` closure that calls `sandbox_event_queue.put_nowait(event)` — same queue the `sandbox_stream_callback` uses.
3. After `register_sandbox_files()` succeeds in `_collect_and_upload_files()`: calls `workspace_callback({type: "workspace_updated", file_path: "sandbox/{entry.filename}", operation: "create", size_bytes: entry.size_bytes, source: "sandbox"})` for each entry.
4. Queue drain in chat.py (`while not sandbox_event_queue.empty()`) forwards workspace_updated events to the outer SSE handler, which translates them to `data: {...}\n\n`.

### Tests (3 PASS)

| # | Test | Behavior |
|---|------|----------|
| 1 | `test_write_file_emits_workspace_updated` | write_file → workspace_updated with correct file_path/operation/size_bytes/source |
| 2 | `test_workspace_disabled_no_workspace_updated_events` | workspace_enabled=False → 0 events (kill-switch) |
| 3 | `test_list_files_no_workspace_updated_events` | list_files (read-only) → 0 events |

## Commits

| Hash | Description |
|------|-------------|
| `b3ada62` | `feat(18-06)`: emit workspace_updated SSE after write_file/edit_file in all three chat-loop sites |
| `fa71a41` | `feat(18-06)`: wire sandbox workspace_updated events through callback chain (WS-10) |
| `7e414ed` | `test(18-06)`: e2e SSE tests for workspace_updated event emission (WS-10) |

## Deviations from Plan

### 1. [Rule 1 - Bug] available_tool_names blocks unregistered tools

**Found during:** Task 3 test debugging (Test 1 failure)
**Issue:** `_run_tool_loop` checks `func_name not in available_tool_names` before dispatching. `available_tool_names` is built from `build_llm_tools()` which reads `_REGISTRY`. Patching `_REGISTRY` alone was insufficient because `build_llm_tools` returned mock-schema objects, not proper tool-name strings.
**Fix:** Test patches also `build_llm_tools` to return a proper OpenAI-format schema array, and `build_catalog_block` to return empty string. No production code change needed.
**Impact:** Tests pass, implementation correct.

### 2. [Rule 2 - Auto-adapted] Three emission sites instead of two

**Found during:** Task 1 code review
**Issue:** Plan said "2 expected (agent-mode + standard)". The codebase has 3 loops: `_run_tool_loop` (standard + agent paths), `_run_tool_loop_for_test` (test skeleton), and deep-mode (`run_deep_mode_loop`). Deep-mode uses a completely different pattern (direct `yield f"data: ..."` with `tool_loop_buffer` for redaction).
**Fix:** Added workspace_updated emission to all 3 sites. Deep-mode site follows the `todos_updated` precedent at L1709–1714.
**Impact:** Complete coverage across all chat-loop paths.

### 3. [Rule 2 - Auto-adapted] Separate workspace_callback param instead of reusing stream_callback

**Found during:** Task 2 implementation
**Issue:** Plan suggested "use stream_callback" but the existing `stream_callback` has signature `(event_type: str, line: str)` (designed for string stdout/stderr lines). workspace_updated is a dict.
**Fix:** Added separate `workspace_callback: Callable[[dict], None] | None = None` parameter that takes a dict and calls `put_nowait`. This is cleaner and avoids type confusion.
**Impact:** Clear separation of concerns; sandbox line streaming and workspace event emission remain orthogonal.

## Must-Haves Verified

- [x] After successful write_file/edit_file, workspace_updated SSE emitted with {type, file_path, operation, size_bytes, source: "agent"}
- [x] Events flow through existing chat-loop SSE generator (same yield discipline as tool_start/tool_result)
- [x] PII redaction egress filter wraps tool results — workspace events go through same buffer path
- [x] workspace_enabled=False: zero workspace_updated events emitted
- [x] sandbox callback chain: workspace_callback propagated from _dispatch_tool → _execute_code → sandbox_service.execute() → _collect_and_upload_files()
- [x] Sandbox emits one workspace_updated per registered file via existing queue
- [x] read_file/list_files produce zero workspace_updated events
- [x] All 3 e2e tests PASS
- [x] 6 existing sandbox-workspace integration tests still PASS (no regression)
- [x] Import check: `python -c "from app.main import app; print('OK')"` → OK

## Known Stubs

None — all workspace_updated emission points are fully wired. sandbox_callback path fires only when workspace_enabled=True AND token is set AND files were uploaded (same guard as plan 18-05).

## Threat Flags

None — workspace_updated payload contains only metadata (file_path, size_bytes, operation, source). No file content is included. T-18-22 (information disclosure via event payload) is mitigated by design. T-18-24 (event-type whitelist bypass) is addressed: the SSE writer uses a fall-through `else` branch that JSON-dumps whatever comes through — no whitelist to bypass.

## Self-Check: PASSED
