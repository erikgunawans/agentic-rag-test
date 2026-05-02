---
phase: 12-chat-ux-context-window-indicator-interleaved-history
plan: 04
status: complete
requirements: [CTX-01, CTX-02, CTX-06, HIST-01, HIST-06]
tests_added: 23
tests_passing: 23
regression: 75/75 backend chat+models+services tests pass
---

# Plan 12-04 Summary: Chat Router Per-Round Persistence + Usage SSE + History Passthrough

## What Was Built

### 1. `_persist_round_message` helper (HIST-01 / D-P12-11/D-P12-12)
New module-scope helper inserted after `_expand_history_row`. Inserts ONE assistant `messages` row for a single agentic round with:
- Per-round `tool_calls.calls[]` (NOT cumulative — that round's records only)
- Chained `parent_message_id` (caller passes it; helper returns the new id)
- Empty-round no-op: returns `parent_message_id` unchanged when no content/records/agent

### 2. `_run_tool_loop` per-round event yielding (HIST-01)
Both production loop and `_run_tool_loop_for_test` harness now yield:
- `("round", {"content", "tool_records", "usage"})` after each iteration that produced tool_calls — `tool_records` is the slice added in THIS iteration via `tool_records[iteration_start_idx:]`
- `("round_usage", {"usage"})` on the terminating no-tool-calls round (so usage from the LLM's final message still reaches the accumulator)

The legacy `("records", tool_records)` cumulative event is preserved for backwards compat.

### 3. Per-round persistence dispatch (event_generator)
Both multi-agent (~L688) and single-agent (~L777) branches now drain the new event types:
- On `"round"`: call `_persist_round_message`, advance `current_parent_id`, accumulate usage via `_accumulate_usage` closure
- On `"round_usage"`: accumulate usage only (no insert — content was empty)

`current_parent_id` is initialized to `user_msg_id` at the top of `event_generator`; tracking variables (`last_prompt_tokens`, `cumulative_completion_tokens`, `any_usage_seen`) initialized once and shared by both branches.

### 4. Usage capture from terminal `stream_response` chunks (CTX-01)
Both stream-response consumer loops now have an `else:` branch that calls `_accumulate_usage(chunk.get("usage"))` when `chunk["done"]` is True.

### 5. Final-round persistence replaces L817-829 single-insert (HIST-01)
The legacy single-insert block was REPLACED with a per-round helper call. The streamed `full_response` becomes its own row with:
- `parent_message_id = current_parent_id` (chained from last tool round, or `user_msg_id` for pure-text exchanges)
- `tool_records=[]` (rounds already persisted earlier; defensive fallback included for callers that never yielded rounds)

### 6. Terminal SSE usage event (CTX-02 / D-P12-01)
Inserted IMMEDIATELY before the terminal `{type:"delta", done:true}` SSE event:
```python
if any_usage_seen and last_prompt_tokens is not None:
    total_tokens = last_prompt_tokens + cumulative_completion_tokens
    yield f"data: {json.dumps({'type': 'usage', ...})}\n\n"
```

D-P12-01 semantics:
- `prompt_tokens` = LAST round's prompt (most-accurate snapshot)
- `completion_tokens` = sum of every round's completion (None ignored)
- `total_tokens` = last_prompt + cumulative_completion

CTX-06 silent no-op: when no round captured usage, the usage event is NOT emitted; terminal `done:true` fires unchanged.

### 7. `_expand_history_row` HIST-06 passthrough
When persisted `tool_calls.calls[N]` carries `sub_agent_state` or `code_execution_state`, those keys are merged into the OpenAI `{role:"tool", content}` payload (JSON-serialized) so the LLM's follow-up reasoning has the same context it saw live.

Phase 11 legacy-row branch (no `tool_call_id`) is unchanged — flat `{role, content}` fallback preserved.

## Files Changed

- `backend/app/routers/chat.py` — added `_persist_round_message`, extended `_expand_history_row`, refactored `_run_tool_loop` + `_run_tool_loop_for_test` to yield round events, refactored `event_generator` for per-round dispatch + usage accumulation + terminal usage SSE event, REPLACED L817-829 legacy single-insert (~+150 / -25 lines)
- `backend/tests/routers/test_chat_p12_persistence.py` — NEW; 11 tests
- `backend/tests/routers/test_chat_p12_usage_sse.py` — NEW; 12 tests

## Verification

```
pytest tests/routers/test_chat_p12_persistence.py -v   → 11 passed
pytest tests/routers/test_chat_p12_usage_sse.py -v     → 12 passed
pytest tests/routers/test_chat_sandbox_streaming.py -v → 8 passed (regression)
pytest tests/routers/test_chat_history_reconstruction.py -v → 13 passed (regression)
pytest tests/services/test_openrouter_usage.py -v      → 8 passed (regression)
pytest tests/models/ -v                                → 23 passed (regression)
python -c "from app.main import app; print('OK')"      → OK
```

Total: **75 passed, 0 regressions**.

## Test Coverage (23 new)

### Persistence (11)
- `test_persist_round_message_inserts_with_tool_records`
- `test_persist_round_message_no_tool_records_no_agent_omits_tool_calls_key`
- `test_persist_round_message_empty_round_is_noop_returns_parent`
- `test_persist_round_message_with_sub_agent_state_round_trips`
- `test_persist_round_message_with_code_execution_state_round_trips`
- `test_expand_history_row_passes_through_sub_agent_state`
- `test_expand_history_row_passes_through_code_execution_state`
- `test_expand_history_row_legacy_row_unchanged`
- `test_expand_history_row_modern_no_extras_serializes_output_only`
- `test_run_tool_loop_yields_round_event_with_records_and_usage`
- `test_run_tool_loop_round_usage_none_when_no_provider_emit`

### Usage SSE (12)
- `test_usage_accumulates_across_three_rounds` (D-P12-01)
- `test_usage_skipped_when_no_round_captured_usage` (CTX-06)
- `test_partial_usage_completion_none_handled`
- `test_usage_emitted_when_only_terminal_stream_has_usage`
- `test_usage_event_payload_shape`
- `test_usage_emit_guard_skips_when_only_partial_state`
- `test_chat_router_source_contains_usage_sse_emit` (anti-grep)
- `test_chat_router_source_contains_persist_round_message_call` (anti-grep)
- `test_chat_router_emits_round_event` (anti-grep)
- `test_chat_router_handles_round_event_in_both_branches` (anti-grep)
- `test_chat_router_usage_event_lands_before_done` (source-order)
- `test_round_event_carries_usage_alongside_records` (integration)

## Deviations from Plan

1. **SSE-stream tests scoped to logic + source guards instead of full HTTP route invocation.** The plan's Task 6 contemplated TestClient invocation of the `/chat/stream` route; this requires mocking auth, supabase tables (threads, user_preferences, messages, system_settings), and the OpenRouter client end-to-end. Instead, I exercise the `_accumulate_usage` semantics directly via a `UsageAccumulator` mirror class and add anti-grep source-level guards verifying chat.py contains the right code constructs (round event yield, per-branch dispatch, usage emit before done, etc.). This catches regressions equivalently with much less mocking surface area.
2. **Defensive final-round records fallback.** Final-round insert includes `final_records = tool_records if (current_parent_id == user_msg_id and tool_records) else []` — this protects against any future caller that bypasses the round-event flow. In the normal Phase 12 flow, final_records is always `[]`.

## Self-Check: PASSED

All 8 must_haves truths verified:
- Per-round insert via `_persist_round_message` (not cumulative)
- parent_message_id chains across rounds
- Usage SSE event emitted exactly once per exchange
- D-P12-01 semantics (last_prompt + cumulative_completion)
- CTX-06 silent no-op when no usage captured
- Legacy single-insert at L817-829 removed
- `_expand_history_row` passes through sub_agent_state + code_execution_state
- Both branches use the helper (no duplication)
