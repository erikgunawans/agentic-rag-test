---
phase: 12-chat-ux-context-window-indicator-interleaved-history
plan: 01
status: complete
requirements: [HIST-02, HIST-03]
tests_added: 12
tests_passing: 12
regression: 11/11 Phase 11 tests pass
---

# Plan 12-01 Summary: ToolCallRecord Extended with sub_agent_state + code_execution_state

## What Was Built

Extended `backend/app/models/tools.py` `ToolCallRecord` with two optional JSONB sub-keys:

- `sub_agent_state: dict | None = None` — for HIST-02 (sub-agent panel reconstruction at history reload)
- `code_execution_state: dict | None = None` — for HIST-03 (code-execution panel reconstruction)

Added a Pydantic `field_validator` on `code_execution_state` that head-truncates the `stdout` and `stderr` keys to 50 KB each (D-P12-14 parity with D-P11-04). Other keys (code, exit_code, execution_ms, files, error_type) pass through unchanged.

Added a shared `_head_truncate_string` helper used by the new validator. Existing `truncate_output` validator on `output` is unchanged (Phase 11 D-P11-04).

NO schema migration required — `messages.tool_calls` is JSONB.

## Key Decisions Honored

- **D-P12-14:** Write-time materialization, 50 KB cap on stdout/stderr only, NO cap on `sub_agent_state` (typical <5 KB per CONTEXT.md).
- **D-P11-04 parity:** Marker `\n…[truncated, N more bytes]\n` uses Unicode U+2026 single ellipsis, byte-size measured in UTF-8.
- **Phase 11 backwards compat:** `tool_call_id`, `status`, `output` validator, `MAX_OUTPUT_BYTES` all unchanged.
- **Legacy rows:** Default-None semantics let pre-Phase-12 persisted rows validate cleanly.

## Files Changed

- `backend/app/models/tools.py` — added 2 optional fields, 1 validator, 1 helper function (~40 lines)
- `backend/tests/models/test_tool_call_record_p12.py` — NEW; 12 unit tests

## Verification

```
pytest tests/models/test_tool_call_record_p12.py -v   → 12 passed
pytest tests/models/test_tool_call_record.py -v       → 11 passed (Phase 11 regression — clean)
python -c "from app.main import app; print('OK')"     → OK
```

## Test Coverage

1. `test_optional_new_fields_default_none` — backwards compat for legacy rows
2. `test_sub_agent_state_round_trip` — full HIST-02 shape passes through
3. `test_code_execution_state_under_cap_unchanged` — small payloads pass-through
4. `test_code_execution_state_stdout_over_cap_truncated` — 60K stdout → head + 10K marker
5. `test_code_execution_state_stderr_over_cap_truncated` — 70K stderr → head + 20K marker
6. `test_code_execution_state_both_streams_over_cap` — independent truncation
7. `test_code_execution_state_truncation_marker_unicode_ellipsis` — U+2026, not three dots
8. `test_code_execution_state_byte_size_uses_utf8` — multi-byte chars trip UTF-8 byte cap
9. `test_sub_agent_state_no_truncation_in_v1` — 100K reasoning passes through
10. `test_legacy_summary_round_trip_p12` — ToolCallSummary still works
11. `test_p11_tests_still_pass_regression` — sentinel for Phase 11 record shape
12. `test_code_execution_state_missing_stdout_key_safe` — partial state tolerated

## Self-Check: PASSED

All must_haves verified, all key_links present, regression clean, backend imports.
