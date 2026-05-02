"""Phase 12 Plan 12-04 integration tests for per-round persistence (HIST-01).

Tests cover:
- _persist_round_message helper insert + chaining return value
- Empty-round no-op
- _expand_history_row sub_agent_state + code_execution_state passthrough (HIST-06)
- _run_tool_loop_for_test yields "round" events with content + tool_records + usage
- Phase 11 legacy-row fallback unchanged

Strategy: target the helpers and the Phase 12 test-harness extension directly.
Full SSE-stream tests (route invocation) live in test_chat_p12_usage_sse.py.
"""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.tools import ToolCallRecord


# ---------------------------------------------------------------------------
# _persist_round_message helper — direct unit tests
# ---------------------------------------------------------------------------

def _make_mock_supabase_client(captured: list):
    """Returns a mock supabase client whose .table('messages').insert(d).execute()
    appends d to `captured` and returns a result with auto-id."""
    client = MagicMock()
    table_mock = MagicMock()

    def _insert(insert_data):
        captured.append(insert_data)
        execute_mock = MagicMock()
        new_id = f"msg-{len(captured)}"
        execute_mock.execute.return_value = MagicMock(
            data=[{**insert_data, "id": new_id}]
        )
        return execute_mock

    table_mock.insert.side_effect = _insert
    client.table.return_value = table_mock
    return client


def test_persist_round_message_inserts_with_tool_records():
    from app.routers.chat import _persist_round_message

    captured: list = []
    client = _make_mock_supabase_client(captured)
    records = [
        ToolCallRecord(
            tool="search_documents",
            input={"q": "x"},
            output={"hits": []},
            tool_call_id="call_1",
            status="success",
        )
    ]
    new_id = _persist_round_message(
        client,
        thread_id="t1",
        user_id="u1",
        parent_message_id="parent-0",
        content="round 1 text",
        tool_records=records,
        agent_name="research",
    )
    assert len(captured) == 1
    row = captured[0]
    assert row["thread_id"] == "t1"
    assert row["user_id"] == "u1"
    assert row["role"] == "assistant"
    assert row["content"] == "round 1 text"
    assert row["parent_message_id"] == "parent-0"
    # Per-round payload — only this round's calls
    assert row["tool_calls"]["agent"] == "research"
    assert len(row["tool_calls"]["calls"]) == 1
    assert row["tool_calls"]["calls"][0]["tool"] == "search_documents"
    # Returned id chains forward
    assert new_id == "msg-1"


def test_persist_round_message_no_tool_records_no_agent_omits_tool_calls_key():
    from app.routers.chat import _persist_round_message

    captured: list = []
    client = _make_mock_supabase_client(captured)
    new_id = _persist_round_message(
        client,
        thread_id="t1",
        user_id="u1",
        parent_message_id="parent-0",
        content="terminal text",
        tool_records=[],
        agent_name=None,
    )
    assert len(captured) == 1
    row = captured[0]
    assert row["content"] == "terminal text"
    assert "tool_calls" not in row
    assert new_id == "msg-1"


def test_persist_round_message_empty_round_is_noop_returns_parent():
    from app.routers.chat import _persist_round_message

    captured: list = []
    client = _make_mock_supabase_client(captured)
    new_id = _persist_round_message(
        client,
        thread_id="t1",
        user_id="u1",
        parent_message_id="parent-0",
        content="",
        tool_records=[],
        agent_name=None,
    )
    # No insert performed
    assert len(captured) == 0
    # parent_message_id passes through unchanged
    assert new_id == "parent-0"


def test_persist_round_message_with_sub_agent_state_round_trips():
    from app.routers.chat import _persist_round_message

    captured: list = []
    client = _make_mock_supabase_client(captured)
    sub_state = {
        "mode": "explorer",
        "document_id": None,
        "reasoning": "looking at clauses",
        "explorer_tool_calls": [],
    }
    records = [
        ToolCallRecord(
            tool="run_research_agent",
            input={"query": "indemnity"},
            output={"answer": "ok"},
            tool_call_id="call_research_1",
            status="success",
            sub_agent_state=sub_state,
        )
    ]
    _persist_round_message(
        client,
        thread_id="t1",
        user_id="u1",
        parent_message_id="parent-0",
        content="",
        tool_records=records,
        agent_name=None,
    )
    persisted = captured[0]["tool_calls"]["calls"][0]
    assert persisted["sub_agent_state"] == sub_state


def test_persist_round_message_with_code_execution_state_round_trips():
    from app.routers.chat import _persist_round_message

    captured: list = []
    client = _make_mock_supabase_client(captured)
    code_state = {
        "code": "print(1)",
        "stdout": "1\n",
        "stderr": "",
        "exit_code": 0,
        "execution_ms": 12,
        "files": [],
        "error_type": None,
    }
    records = [
        ToolCallRecord(
            tool="execute_code",
            input={"code": "print(1)"},
            output={"stdout": "1\n", "exit_code": 0},
            tool_call_id="call_exec_1",
            status="success",
            code_execution_state=code_state,
        )
    ]
    _persist_round_message(
        client,
        thread_id="t1",
        user_id="u1",
        parent_message_id="parent-0",
        content="",
        tool_records=records,
        agent_name=None,
    )
    persisted = captured[0]["tool_calls"]["calls"][0]
    assert persisted["code_execution_state"] == code_state


# ---------------------------------------------------------------------------
# _expand_history_row sub_agent_state + code_execution_state passthrough
# ---------------------------------------------------------------------------

def test_expand_history_row_passes_through_sub_agent_state():
    from app.routers.chat import _expand_history_row

    sub_state = {
        "mode": "explorer",
        "document_id": "doc-1",
        "reasoning": "r",
        "explorer_tool_calls": [],
    }
    row = {
        "id": "m1",
        "role": "assistant",
        "content": "answer",
        "tool_calls": {
            "agent": "research",
            "calls": [
                {
                    "tool": "run_research_agent",
                    "input": {"query": "q"},
                    "output": {"answer": "a"},
                    "tool_call_id": "call_1",
                    "status": "success",
                    "sub_agent_state": sub_state,
                }
            ],
        },
    }
    items = _expand_history_row(row)
    # First item: assistant tool_calls envelope
    assert items[0]["role"] == "assistant"
    assert items[0]["tool_calls"][0]["function"]["name"] == "run_research_agent"
    # Second item: tool message — must include sub_agent_state in JSON content
    tool_msg = items[1]
    assert tool_msg["role"] == "tool"
    assert tool_msg["tool_call_id"] == "call_1"
    parsed = json.loads(tool_msg["content"])
    assert parsed["sub_agent_state"] == sub_state
    assert parsed["answer"] == "a"


def test_expand_history_row_passes_through_code_execution_state():
    from app.routers.chat import _expand_history_row

    code_state = {
        "code": "print(2)",
        "stdout": "2\n",
        "stderr": "",
        "exit_code": 0,
        "execution_ms": 7,
        "files": [],
        "error_type": None,
    }
    row = {
        "id": "m1",
        "role": "assistant",
        "content": "ran code",
        "tool_calls": {
            "agent": None,
            "calls": [
                {
                    "tool": "execute_code",
                    "input": {"code": "print(2)"},
                    "output": {"stdout": "2\n", "exit_code": 0},
                    "tool_call_id": "call_exec_1",
                    "status": "success",
                    "code_execution_state": code_state,
                }
            ],
        },
    }
    items = _expand_history_row(row)
    tool_msg = items[1]
    parsed = json.loads(tool_msg["content"])
    assert parsed["code_execution_state"] == code_state


def test_expand_history_row_legacy_row_unchanged():
    """Phase 11 legacy-row branch (no tool_call_id) still emits flat shape."""
    from app.routers.chat import _expand_history_row

    row = {
        "id": "m_legacy",
        "role": "assistant",
        "content": "old answer",
        "tool_calls": None,
    }
    items = _expand_history_row(row)
    assert items == [{"role": "assistant", "content": "old answer"}]


def test_expand_history_row_modern_no_extras_serializes_output_only():
    """When neither sub_agent_state nor code_execution_state is set,
    the tool-message content is the existing Phase 11 serialization."""
    from app.routers.chat import _expand_history_row

    row = {
        "role": "assistant",
        "content": "answer",
        "tool_calls": {
            "agent": None,
            "calls": [
                {
                    "tool": "search_documents",
                    "input": {"q": "x"},
                    "output": {"hits": ["a"]},
                    "tool_call_id": "call_1",
                    "status": "success",
                }
            ],
        },
    }
    items = _expand_history_row(row)
    parsed = json.loads(items[1]["content"])
    assert parsed == {"hits": ["a"]}
    assert "sub_agent_state" not in parsed
    assert "code_execution_state" not in parsed


# ---------------------------------------------------------------------------
# _run_tool_loop_for_test yields "round" events (Phase 12 harness extension)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_tool_loop_yields_round_event_with_records_and_usage():
    """_run_tool_loop_for_test yields a 'round' event after each iteration."""
    from app.routers import chat as chat_module

    # Mock complete_with_tools: round 1 = tool call (search), round 2 = no tool
    call_count = {"n": 0}

    async def fake_complete_with_tools(messages, tools, model=None, response_format=None):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return {
                "role": "assistant",
                "content": "intermediate",
                "tool_calls": [
                    {
                        "id": "call_search_1",
                        "type": "function",
                        "function": {
                            "name": "search_documents",
                            "arguments": json.dumps({"q": "x"}),
                        },
                    }
                ],
                "finish_reason": "tool_calls",
                "usage": {"prompt_tokens": 100, "completion_tokens": 30, "total_tokens": 130},
            }
        return {
            "role": "assistant",
            "content": "done",
            "tool_calls": None,
            "finish_reason": "stop",
            "usage": {"prompt_tokens": 130, "completion_tokens": 10, "total_tokens": 140},
        }

    chat_module.openrouter_service.complete_with_tools = fake_complete_with_tools
    chat_module.tool_service.execute_tool = AsyncMock(return_value={"hits": []})

    events = []
    async for ev_type, data in chat_module._run_tool_loop_for_test(
        messages=[{"role": "user", "content": "hi"}],
        tools=[{"type": "function", "function": {"name": "search_documents"}}],
        max_iterations=5,
        user_id="u1",
        tool_context={"top_k": 5, "threshold": 0.3, "embedding_model": "x", "llm_model": "x", "thread_id": "t1"},
        available_tool_names=["search_documents"],
    ):
        events.append((ev_type, data))

    round_events = [e for e in events if e[0] == "round"]
    round_usage_events = [e for e in events if e[0] == "round_usage"]

    # Round 1: tool was called → "round" event with that round's records
    assert len(round_events) == 1
    round1 = round_events[0][1]
    assert round1["content"] == "intermediate"
    assert len(round1["tool_records"]) == 1
    assert round1["tool_records"][0].tool == "search_documents"
    assert round1["usage"]["prompt_tokens"] == 100

    # Round 2: no tool calls → "round_usage" event only
    assert len(round_usage_events) == 1
    assert round_usage_events[0][1]["usage"]["prompt_tokens"] == 130


@pytest.mark.asyncio
async def test_run_tool_loop_round_usage_none_when_no_provider_emit():
    """CTX-06: when provider returns usage=None on the terminal round, the
    round_usage event still fires with usage=None — caller skips emit."""
    from app.routers import chat as chat_module

    async def fake_complete_with_tools(messages, tools, model=None, response_format=None):
        return {
            "role": "assistant",
            "content": "done",
            "tool_calls": None,
            "finish_reason": "stop",
            "usage": None,
        }

    chat_module.openrouter_service.complete_with_tools = fake_complete_with_tools

    events = []
    async for ev_type, data in chat_module._run_tool_loop_for_test(
        messages=[{"role": "user", "content": "hi"}],
        tools=[{"type": "function", "function": {"name": "search_documents"}}],
        max_iterations=5,
        user_id="u1",
        tool_context={"thread_id": "t1"},
        available_tool_names=["search_documents"],
    ):
        events.append((ev_type, data))

    round_usage_events = [e for e in events if e[0] == "round_usage"]
    assert len(round_usage_events) == 1
    assert round_usage_events[0][1]["usage"] is None
