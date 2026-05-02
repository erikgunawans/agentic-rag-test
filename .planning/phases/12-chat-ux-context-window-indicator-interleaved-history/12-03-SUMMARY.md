---
phase: 12-chat-ux-context-window-indicator-interleaved-history
plan: 03
status: complete
requirements: [CTX-01]
tests_added: 8
tests_passing: 8
regression: 8/8 chat_sandbox_streaming tests still pass
---

# Plan 12-03 Summary: Usage Capture in OpenRouterService

## What Was Built

1. **`_extract_usage` helper** (module-level): Defensively converts an OpenAI `CompletionUsage` object (or anything duck-compatible) into a `{prompt_tokens, completion_tokens, total_tokens}` dict, returning `None` on any extraction failure or when all fields are None.

2. **`stream_response` plumbed**: Always passes `stream_options={"include_usage": True}` to `client.chat.completions.create`. Captures usage from chunks where `choices` is empty (the canonical OpenAI usage chunk shape) AND from the last regular chunk if the provider attaches it there. Terminal yield is now `{"delta": "", "done": True, "usage": <dict | None>}`.

3. **`complete_with_tools` plumbed**: Returns a 5th key `"usage"` on the result dict alongside existing `role`, `content`, `tool_calls`, `finish_reason`. None when provider does not emit usage data.

4. **Graceful CTX-06 no-op**: When the provider does NOT emit a usage chunk, both methods log a single DEBUG line and surface `usage=None`. Service does NOT raise.

5. **Tests**: Created `backend/tests/services/test_openrouter_usage.py` with 8 tests using mocked AsyncOpenAI client.

## Key Decisions Honored

- **D-P12-02**: Single source of truth — every chat path through OpenRouterService benefits without per-call wiring.
- **D-P12-03 / CTX-06**: Graceful no-op when provider does not emit usage. No exception, only DEBUG log.
- **Backwards compat**: Existing consumer pattern `async for c in stream_response(): text += c["delta"]` continues to work — the new `usage` key is optional and only on terminal chunk.

## Files Changed

- `backend/app/services/openrouter_service.py` — full rewrite (~125 lines, was 67)
- `backend/tests/services/test_openrouter_usage.py` — NEW; 8 tests

## Verification

```
pytest tests/services/test_openrouter_usage.py -v   → 8 passed
pytest tests/routers/test_chat_sandbox_streaming.py -v   → 8 passed (regression)
python -c "from app.main import app; print('OK')"   → OK
```

## Test Coverage

1. `test_stream_response_passes_stream_options` — kwarg verified on `create()` call
2. `test_stream_response_terminal_chunk_carries_usage` — full positive path
3. `test_stream_response_no_usage_chunk_yields_none` — CTX-06 graceful fallback
4. `test_stream_response_partial_usage_object_safe` — partial usage object tolerated
5. `test_complete_with_tools_returns_usage` — non-stream usage extraction
6. `test_complete_with_tools_no_usage_returns_none` — non-stream None fallback
7. `test_complete_with_tools_preserves_tool_calls_shape` — existing tool_calls structure intact
8. `test_stream_response_existing_consumer_pattern_works` — chat.py consumer unaffected

## Self-Check: PASSED

All must_haves verified, key_links present, no regression on existing chat-streaming path.
