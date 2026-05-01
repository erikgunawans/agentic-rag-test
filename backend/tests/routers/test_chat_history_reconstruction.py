"""Phase 11 Plan 11-04 — chat.py history reconstruction tests.

Covers:
  - `_expand_history_row(row)`: emits OpenAI triplet for modern rows where
    every `tool_calls.calls[]` carries `tool_call_id`, falls back to
    `[{role, content}]` for legacy rows (D-P11-03 / D-P11-07).
  - `_derive_tool_status(tool_name, tool_output, *, exception_caught=False)`:
    derives ToolCallRecord.status per D-P11-08 (success / error / timeout
    for execute_code; success / error otherwise).

Both helpers are MODULE-LEVEL in `app.routers.chat` (extracted out of the
per-request handler scope so they can be unit-tested without booting the
FastAPI app, mirroring the `_run_tool_loop_for_test` pattern from Plan 10-05).

Tests are unit tests — they import the helpers directly and never construct
a request, so they do not require Supabase env vars. (`conftest.py` may still
trigger Settings init at collect-time when other tests in the suite import the
redaction service; that is an environmental concern handled at runner level.)
"""
from __future__ import annotations

import json

import pytest


# ---------------------------------------------------------------------------
# `_expand_history_row` — modern rows
# ---------------------------------------------------------------------------


def test_expand_modern_row_with_two_calls():
    """Modern row with 2 tool calls expands to 4 items: assistant{tool_calls}
    + 2 tool messages + trailing assistant{content}."""
    from app.routers.chat import _expand_history_row

    row = {
        "role": "assistant",
        "content": "final assistant text",
        "tool_calls": {
            "calls": [
                {
                    "tool": "x",
                    "input": {},
                    "output": {"stdout": "abc"},
                    "tool_call_id": "call_1",
                    "status": "success",
                },
                {
                    "tool": "y",
                    "input": {},
                    "output": "plain str",
                    "tool_call_id": "call_2",
                    "status": "success",
                },
            ]
        },
    }
    items = _expand_history_row(row)
    assert len(items) == 4

    # (a) assistant with tool_calls list
    assert items[0]["role"] == "assistant"
    assert items[0]["content"] == ""
    assert isinstance(items[0]["tool_calls"], list)
    assert items[0]["tool_calls"][0]["id"] == "call_1"
    assert items[0]["tool_calls"][0]["type"] == "function"
    assert items[0]["tool_calls"][0]["function"]["name"] == "x"
    assert items[0]["tool_calls"][0]["function"]["arguments"] == "{}"
    assert items[0]["tool_calls"][1]["id"] == "call_2"
    assert items[0]["tool_calls"][1]["function"]["name"] == "y"

    # (b) first tool message (dict output → JSON-encoded)
    assert items[1]["role"] == "tool"
    assert items[1]["tool_call_id"] == "call_1"
    assert items[1]["content"] == json.dumps({"stdout": "abc"}, ensure_ascii=False)

    # (c) second tool message (str output → verbatim, NOT double-encoded)
    assert items[2]["role"] == "tool"
    assert items[2]["tool_call_id"] == "call_2"
    assert items[2]["content"] == "plain str"

    # (d) trailing assistant text
    assert items[3]["role"] == "assistant"
    assert items[3]["content"] == "final assistant text"


def test_expand_modern_row_empty_assistant_text():
    """Modern row with empty content omits the trailing assistant text item."""
    from app.routers.chat import _expand_history_row

    row = {
        "role": "assistant",
        "content": "",
        "tool_calls": {
            "calls": [
                {
                    "tool": "x",
                    "input": {},
                    "output": {"stdout": "abc"},
                    "tool_call_id": "call_1",
                    "status": "success",
                },
                {
                    "tool": "y",
                    "input": {},
                    "output": "plain str",
                    "tool_call_id": "call_2",
                    "status": "success",
                },
            ]
        },
    }
    items = _expand_history_row(row)
    assert len(items) == 3
    assert items[0]["role"] == "assistant"
    assert items[1]["role"] == "tool"
    assert items[2]["role"] == "tool"


def test_expand_legacy_row_no_tool_call_id():
    """Legacy row (single call missing tool_call_id) falls back to flat."""
    from app.routers.chat import _expand_history_row

    row = {
        "role": "assistant",
        "content": "legacy text",
        "tool_calls": {
            "calls": [
                {
                    "tool": "x",
                    "input": {},
                    "output": {},
                    "tool_call_id": None,
                }
            ]
        },
    }
    items = _expand_history_row(row)
    assert items == [{"role": "assistant", "content": "legacy text"}]


def test_expand_row_no_tool_calls_at_all():
    """Row with tool_calls=None returns flat fallback."""
    from app.routers.chat import _expand_history_row

    row = {"role": "user", "content": "hello", "tool_calls": None}
    items = _expand_history_row(row)
    assert items == [{"role": "user", "content": "hello"}]


def test_expand_partial_legacy_calls_falls_back():
    """When ONE call has tool_call_id and another lacks it, helper falls back
    entirely (per-row cutoff per D-P11-03 — no cherry-picking)."""
    from app.routers.chat import _expand_history_row

    row = {
        "role": "assistant",
        "content": "mixed",
        "tool_calls": {
            "calls": [
                {"tool": "x", "input": {}, "output": {}, "tool_call_id": "call_1"},
                {"tool": "y", "input": {}, "output": {}, "tool_call_id": None},
            ]
        },
    }
    items = _expand_history_row(row)
    assert items == [{"role": "assistant", "content": "mixed"}]


def test_str_output_in_tool_message_no_double_encoding():
    """When call.output is already a string (post-Plan-11-01 truncation), the
    tool message's content is the string itself — NOT json.dumps(string)."""
    from app.routers.chat import _expand_history_row

    truncated = "huge stdout\n…[truncated, 12345 more bytes]\n"
    row = {
        "role": "assistant",
        "content": "",
        "tool_calls": {
            "calls": [
                {
                    "tool": "execute_code",
                    "input": {},
                    "output": truncated,
                    "tool_call_id": "call_1",
                }
            ]
        },
    }
    items = _expand_history_row(row)
    # Find the tool message
    tool_msg = next(i for i in items if i["role"] == "tool")
    assert tool_msg["content"] == truncated
    # Negative: it should NOT be json.dumps(truncated) (which would wrap quotes)
    assert tool_msg["content"] != json.dumps(truncated, ensure_ascii=False)


def test_redaction_batch_compatibility():
    """All expanded items have a 'content' key — redaction batch
    `[m['content'] for m in expanded]` does not raise KeyError."""
    from app.routers.chat import _expand_history_row

    row = {
        "role": "assistant",
        "content": "tail",
        "tool_calls": {
            "calls": [
                {"tool": "x", "input": {}, "output": {"a": 1}, "tool_call_id": "c1"},
                {"tool": "y", "input": {}, "output": "z", "tool_call_id": "c2"},
            ]
        },
    }
    items = _expand_history_row(row)
    # Should not raise
    contents = [m["content"] for m in items]
    assert all(isinstance(c, str) for c in contents)


def test_every_expanded_item_has_content_key():
    """Test 13 (per plan §6d / Splice F): assistant rows with tool_calls MUST
    set content="" (not omit it) so the redaction batch index alignment is
    preserved (D-P11-10)."""
    from app.routers.chat import _expand_history_row

    row = {
        "role": "assistant",
        "content": "final",
        "tool_calls": {
            "calls": [
                {"tool": "x", "input": {}, "output": {}, "tool_call_id": "c1"}
            ]
        },
    }
    items = _expand_history_row(row)
    for item in items:
        assert "content" in item, f"missing content key on item: {item}"


# ---------------------------------------------------------------------------
# `_derive_tool_status` — sandbox + non-sandbox + exception
# ---------------------------------------------------------------------------


def test_status_derive_for_execute_code_success():
    from app.routers.chat import _derive_tool_status

    status = _derive_tool_status(
        "execute_code",
        {"stdout": "x", "exit_code": 0, "error_type": None},
    )
    assert status == "success"


def test_status_derive_for_execute_code_timeout():
    from app.routers.chat import _derive_tool_status

    status = _derive_tool_status(
        "execute_code",
        {"error_type": "timeout", "exit_code": -1},
    )
    assert status == "timeout"


def test_status_derive_for_execute_code_error():
    from app.routers.chat import _derive_tool_status

    status = _derive_tool_status(
        "execute_code",
        {"error_type": "runtime_error", "exit_code": 1},
    )
    assert status == "error"


def test_status_derive_for_non_sandbox_success():
    from app.routers.chat import _derive_tool_status

    status = _derive_tool_status("search_documents", {"results": []})
    assert status == "success"


def test_status_derive_for_exception_path():
    from app.routers.chat import _derive_tool_status

    status = _derive_tool_status("anything", None, exception_caught=True)
    assert status == "error"
