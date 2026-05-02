---
phase: 17-deep-mode-foundation-planning-todos-plan-panel
plan: "04"
subsystem: api
tags: [python, fastapi, deep-mode, tool-calling, sse, tdd, pii-redaction, todos]

# Dependency graph
requires:
  - phase: 17-deep-mode-foundation-planning-todos-plan-panel/17-02
    provides: "max_deep_rounds=50, max_tool_rounds=25, deep_mode_enabled=False in Pydantic Settings"
  - phase: 17-deep-mode-foundation-planning-todos-plan-panel/17-03
    provides: "write_todos + read_todos registered in tool_registry; agent_todos_service implemented"

provides:
  - "run_deep_mode_loop() async generator in chat.py — full deep-mode agent loop with extended prompt, todos tools, todos_updated SSE, exhaustion fallback, deep_mode persistence, egress coverage"
  - "build_deep_mode_system_prompt() in deep_mode_prompt.py — deterministic KV-cache-friendly 4-section prompt builder"
  - "SendMessageRequest.deep_mode: bool = False — payload field for per-message deep mode toggle"
  - "Feature gate: DEEP_MODE_ENABLED=false rejects deep_mode=true with HTTP 400"
  - "_persist_round_message() extended with deep_mode: bool = False kwarg"
  - "D-15 migration: standard single-agent loop uses settings.max_tool_rounds"
  - "31 integration tests (23 deep-mode + 8 byte-identical fallback)"

affects:
  - 17-05-rest-endpoint-todos (consumes deep_mode_enabled gate)
  - 17-06-plan-panel-ui (consumes todos_updated SSE, deep_mode column on messages)
  - 17-07-rls-regression (tests deep_mode persistence)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "run_deep_mode_loop: module-level async generator (mirrors _run_tool_loop_for_test pattern) so it can be tested and referenced without closure deps"
    - "_dispatch_tool_deep: module-level registry-first dispatcher (mirrors _dispatch_tool closure)"
    - "D-17/D-18: todos_updated SSE emitted AFTER DB write commits (write_todos awaited), BEFORE tool_result"
    - "DEEP-06: current_tools swapped to [] + summary system message injected at iteration max_iterations - 1"
    - "DEEP-04: _persist_round_message called with deep_mode=True in deep loop; defaults False in standard loop"
    - "D-15: max_tool_rounds replaces tools_max_iterations in standard single-agent path"

key-files:
  created:
    - backend/app/services/deep_mode_prompt.py
    - backend/tests/integration/test_deep_mode_chat_loop.py
    - backend/tests/integration/test_deep_mode_byte_identical_fallback.py
  modified:
    - backend/app/routers/chat.py

key-decisions:
  - "run_deep_mode_loop is module-level (not a closure like event_generator) — allows source-inspection tests and future direct test invocation without mock complexity"
  - "_dispatch_tool_deep is a separate module-level function rather than re-using the _dispatch_tool closure — necessary since the closure captures body/user/sys_settings from stream_chat scope"
  - "anon_history reconstruction uses enumerate(m for m in messages if m.get('content')) — preserves only content-bearing rows to avoid index drift with tool-result messages that have no content"
  - "todos_updated SSE always emitted outside the redaction_on buffer (emitted directly to stream) — the todo list snapshot is already post-anonymization data; no PII risk in the SSE event"
  - "D-15 migration applied only to single-agent path (line ~991); multi-agent path uses agent_def.max_iterations which was always a separate field"

patterns-established:
  - "Deep-mode SSE event: data: {type: todos_updated, todos: [...]} — emitted after write_todos OR read_todos (full snapshot, D-17)"
  - "DEEP-03 invariant: SYSTEM_PROMPT constant unchanged; _run_tool_loop unchanged; event_generator unchanged — all deep-mode logic lives in run_deep_mode_loop"
  - "SC#5 preserved: deep_mode=False path produces byte-identical output to v1.2"

requirements-completed: [DEEP-01, DEEP-02, DEEP-03, DEEP-04, DEEP-05, DEEP-06, DEEP-07, TODO-03, TODO-04]

# Metrics
duration: 65min
completed: "2026-05-02"
---

# Phase 17 Plan 04: Deep Mode Chat Loop Branch Summary

**run_deep_mode_loop() wired into chat.py — full deep-mode agent loop with MAX_DEEP_ROUNDS=50, deterministic extended prompt, write_todos/read_todos tools, todos_updated SSE events, exhaustion fallback, deep_mode row persistence, and egress filter coverage; 31 integration tests pass**

## Performance

- **Duration:** ~65 min
- **Started:** 2026-05-02T21:30:00Z
- **Completed:** 2026-05-02T22:37:18Z
- **Tasks:** 2 (TDD RED + GREEN)
- **Files modified:** 4 (1 new service, 1 modified router, 2 new test files)

## Accomplishments

- Created `backend/app/services/deep_mode_prompt.py`:
  - `build_deep_mode_system_prompt(base_prompt) -> str` — appends 4 deterministic sections (Planning, Recitation Pattern, Sub-Agent Delegation stub, Asking-User stub)
  - Deterministic: identical bytes on each call with same input (KV-cache stable per DEEP-05/D-09)
  - No timestamps, no volatile data — todo state flows through tools, not this prompt

- Extended `backend/app/routers/chat.py` (498 lines added, 1 modified):
  - `SendMessageRequest.deep_mode: bool = False` — per-message deep mode payload field (DEEP-01)
  - Front-gate in `stream_chat`: checks `settings.deep_mode_enabled`, raises HTTP 400 `"deep mode disabled"` when flag off and `deep_mode=true` requested (T-17-09)
  - `run_deep_mode_loop()` module-level async generator — the deep-mode agent loop (DEEP-02):
    - `max_iterations = settings.max_deep_rounds` (50 per CONF-01)
    - Extended system prompt via `build_deep_mode_system_prompt()` (DEEP-05, TODO-04)
    - Tools list built from registry — includes `write_todos` and `read_todos` (loading="immediate", D-10)
    - `todos_updated` SSE event emitted after every `write_todos` / `read_todos` dispatch — full snapshot (D-17, D-18, TODO-03)
    - DEEP-06: on iteration `max_iterations - 1`, injects "summarize and deliver" system message and swaps `current_tools = []` to force terminal text round
    - DEEP-04: `_persist_round_message()` called with `deep_mode=True` for all rounds
    - D-32 / T-17-10: `egress_filter()` applied before every LLM call
    - DEEP-07 mid-loop safety: `write_todos` awaited (DB committed) before `todos_updated` SSE emit
    - Redaction ON/OFF paths mirrored from `event_generator`
    - Auto-title generation mirrors standard path
  - `_dispatch_tool_deep()` module-level registry-first dispatcher (same logic as `_dispatch_tool` closure)
  - `_persist_round_message()` extended with `deep_mode: bool = False` kwarg (DEEP-04, MIG-04 consumer)
  - D-15 migration: standard single-agent loop now uses `settings.max_tool_rounds` (25) instead of `settings.tools_max_iterations` (5 legacy default)

- Created 31 integration tests:
  - `test_deep_mode_chat_loop.py` (23 tests): prompt sections, field + defaults, feature gate, `run_deep_mode_loop` existence + async generator type, `todos_updated` SSE events, MAX_DEEP_ROUNDS exhaustion, `deep_mode` column persistence, egress filter coverage, D-15 migration
  - `test_deep_mode_byte_identical_fallback.py` (8 tests): DEEP-03 invariant — `SYSTEM_PROMPT` unchanged, no Deep Mode in standard loop, no `todos_updated` in `_run_tool_loop`, no `agent_todos_service` in standard path, dispatch front-gated, `_persist_round_message` signature backward-compatible

## Task Commits

1. **Task 1: TDD RED — deep_mode_prompt.py + failing tests** - `55ee123` (test)
2. **Task 2: TDD GREEN — run_deep_mode_loop + payload field + gate + SSE + persistence** - `e354bb7` (feat)

## Files Created/Modified

| File | Change | Lines |
|------|--------|-------|
| `backend/app/services/deep_mode_prompt.py` | Created | 52 |
| `backend/app/routers/chat.py` | Modified | +499, -1 |
| `backend/tests/integration/test_deep_mode_chat_loop.py` | Created | 357 |
| `backend/tests/integration/test_deep_mode_byte_identical_fallback.py` | Created | 152 |

## Decisions Made

- `run_deep_mode_loop` is module-level (not a closure inside `stream_chat`). This enables source-inspection tests, avoids closure variable capture issues, and keeps the function directly testable. The function receives all needed values as parameters.
- `_dispatch_tool_deep` is a separate module-level function rather than re-using the `_dispatch_tool` closure, because `_dispatch_tool` captures `user`, `body`, and `sys_settings` from the `stream_chat` scope.
- `todos_updated` SSE is emitted outside the `tool_loop_buffer` (not buffered when `redaction_on=True`) because the todo list snapshot contains post-anonymization data — no PII leaks via this event.
- D-15 migration applied only to the single-agent path (`settings.max_tool_rounds`); the multi-agent path uses `agent_def.max_iterations` which is a separate per-agent field and was never `tools_max_iterations`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical functionality] anon_history reconstruction uses filtered generator**
- **Found during:** Task 2 implementation
- **Issue:** History messages include both `role: assistant` rows (with content) and `role: tool` rows (with `tool_call_id` but no `content`). Zipping `messages` with `anonymized_strings` using a flat index would skip non-content rows and cause index drift.
- **Fix:** Used `enumerate(m for m in messages if m.get('content'))` to only zip content-bearing messages with their anonymized counterparts.
- **Files modified:** `backend/app/routers/chat.py` (run_deep_mode_loop anon_history construction)
- **Verification:** Syntactically correct; mirrors the implicit filter in event_generator which only passes content-bearing messages to `redact_text_batch`.

None beyond the above — plan executed as specified.

## Known Stubs

- **Sub-agent stub in prompt** (`## Deep Mode — Sub-Agent Delegation`): placeholder text per D-09. The actual `task` tool ships in Phase 19. Intentional — tracked in CONTEXT.md deferred items.
- **Ask-user stub in prompt** (`## Deep Mode — Asking the User`): placeholder text per D-09. Ships in Phase 19.

## Threat Surface Scan

| Flag | File | Description |
|------|------|-------------|
| T-17-09 (mitigated) | backend/app/routers/chat.py | deep_mode=true front-gate: checks settings.deep_mode_enabled, raises 400 when off |
| T-17-10 (mitigated) | backend/app/routers/chat.py | run_deep_mode_loop calls egress_filter before every LLM invocation (D-32) |
| T-17-11 (mitigated) | backend/app/routers/chat.py | DEEP-06 hard cap: tools=[] + summary message injected at iteration max_deep_rounds - 1 |

No new unmitigated threat surface. Privacy invariant preserved (D-32): all deep-mode LLM payloads route through egress_filter.

## Self-Check

### Files Created/Modified Exist

- `backend/app/services/deep_mode_prompt.py` - FOUND (52 lines)
- `backend/app/routers/chat.py` - FOUND (modified: +499 lines)
- `backend/tests/integration/test_deep_mode_chat_loop.py` - FOUND (357 lines)
- `backend/tests/integration/test_deep_mode_byte_identical_fallback.py` - FOUND (152 lines)

### Commits Exist

- `55ee123` - FOUND (test: TDD RED — deep_mode_prompt + failing tests)
- `e354bb7` - FOUND (feat: TDD GREEN — run_deep_mode_loop implementation)

### Verification

- `python3 -m py_compile app/routers/chat.py` → Syntax OK
- `python3 -m py_compile app/services/deep_mode_prompt.py` → Syntax OK
- `from app.main import app; print('OK')` → OK
- `pytest tests/integration/test_deep_mode_chat_loop.py tests/integration/test_deep_mode_byte_identical_fallback.py -v` → 31 passed
- `build_deep_mode_system_prompt('Base.') == build_deep_mode_system_prompt('Base.')` → True (deterministic)
- SYSTEM_PROMPT constant contains no `## Deep Mode` sections (DEEP-03 preserved)
- `_run_tool_loop_for_test` contains no `todos_updated` (DEEP-03 preserved)

## Self-Check: PASSED

---
*Phase: 17-deep-mode-foundation-planning-todos-plan-panel*
*Completed: 2026-05-02*
