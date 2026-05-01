"""Tests for Phase 10 SANDBOX-03: sandbox stdout/stderr SSE streaming.

Tests the _run_tool_loop behavior via a module-level test helper
(_run_tool_loop_for_test) that must be added to chat.py as part of the
Phase 10 implementation (GREEN phase).

Tests 1-8 cover:
  1. Non-execute_code tools get stream_callback=None
  2. execute_code gets a non-None callable stream_callback
  3. Callback fires 3 stdout lines → 3 ("code_stdout", payload) tuples
  4. Callback fires 1 stderr line → ("code_stderr", payload) with correct shape
  5. tool_context passed to execute_tool contains thread_id from body.thread_id
  6. When redaction_on=True, lines are anonymized via anonymize_tool_output
  7. Event sequence: tool_start → N code_stdout/code_stderr → tool_result
  8. Regression: no stray code_stdout/code_stderr for non-execute_code tools

All tests use pytest.mark.asyncio and unittest.mock.AsyncMock.
"""
from __future__ import annotations

import asyncio
import json
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

FAKE_TC_ID = "tc-test-aaa"
FAKE_THREAD_ID = "thread-test-555"
FAKE_USER_ID = "user-test-111"


def _make_openrouter_response(func_name: str, func_args: dict, tc_id: str = FAKE_TC_ID):
    """Minimal OpenRouter complete_with_tools response with one tool call."""
    return {
        "tool_calls": [
            {
                "id": tc_id,
                "function": {
                    "name": func_name,
                    "arguments": json.dumps(func_args),
                },
            }
        ]
    }


def _no_tool_calls():
    return {"tool_calls": []}


async def _collect(gen: AsyncGenerator) -> list:
    """Drain an async generator into a list."""
    return [item async for item in gen]


# ---------------------------------------------------------------------------
# Core test harness
# ---------------------------------------------------------------------------

async def _invoke_run_tool_loop(
    *,
    fake_execute_tool,
    func_name: str,
    func_args: dict,
    tc_id: str = FAKE_TC_ID,
    thread_id: str = FAKE_THREAD_ID,
    redaction_on: bool = False,
    registry=None,
    redaction_service=None,
) -> list:
    """Invoke chat.py's _run_tool_loop_for_test with controlled mocks.

    chat.py must expose a module-level ``_run_tool_loop_for_test`` async
    generator function (added in Phase 10 GREEN). If it doesn't exist yet,
    the test will fail with AttributeError — which is the expected RED state.
    """
    # Build a minimal tool_context with thread_id (Phase 10 requirement)
    tool_context = {
        "top_k": 5,
        "threshold": 0.7,
        "embedding_model": "text-embedding-3-small",
        "llm_model": "openai/gpt-4o-mini",
        "thread_id": thread_id,
    }

    tools = [{"type": "function", "function": {"name": func_name}}]

    # Patch at module level — these are the singletons chat.py uses
    mock_openrouter = AsyncMock()
    mock_openrouter.complete_with_tools = AsyncMock(side_effect=[
        _make_openrouter_response(func_name, func_args, tc_id),
        _no_tool_calls(),
    ])

    mock_ts = MagicMock()
    mock_ts.execute_tool = fake_execute_tool

    egress_mock = MagicMock()
    egress_mock.tripped = False

    with (
        patch("app.routers.chat.openrouter_service", mock_openrouter),
        patch("app.routers.chat.tool_service", mock_ts),
        patch("app.routers.chat.egress_filter", return_value=egress_mock),
    ):
        import app.routers.chat as chat_mod

        # This will raise AttributeError if _run_tool_loop_for_test doesn't exist yet.
        # That's the expected RED failure.
        gen = chat_mod._run_tool_loop_for_test(
            messages=[{"role": "user", "content": "test"}],
            tools=tools,
            max_iterations=3,
            user_id=FAKE_USER_ID,
            tool_context=tool_context,
            registry=registry,
            redaction_service=redaction_service,
            redaction_on=redaction_on,
            available_tool_names=[func_name],
            token="test-token",
        )

        return await _collect(gen)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestChatSandboxStreaming:
    """Phase 10 SANDBOX-03 — _run_tool_loop sandbox streaming tests."""

    @pytest.mark.asyncio
    async def test_1_non_execute_code_gets_none_callback(self):
        """Test 1: Non-execute_code tool is called with stream_callback=None."""
        captured_kwargs = {}

        async def fake_execute_tool(name, args, user_id, context, **kwargs):
            captured_kwargs.update(kwargs)
            return {"results": []}

        await _invoke_run_tool_loop(
            fake_execute_tool=fake_execute_tool,
            func_name="search_documents",
            func_args={"query": "test"},
        )

        assert "stream_callback" in captured_kwargs, (
            "execute_tool should receive stream_callback kwarg"
        )
        assert captured_kwargs["stream_callback"] is None, (
            "Non-execute_code tools should receive stream_callback=None"
        )

    @pytest.mark.asyncio
    async def test_2_execute_code_gets_callable_callback(self):
        """Test 2: execute_code is called with a non-None callable stream_callback."""
        captured_kwargs = {}

        async def fake_execute_tool(name, args, user_id, context, **kwargs):
            captured_kwargs.update(kwargs)
            return {"stdout": "", "stderr": "", "exit_code": 0}

        await _invoke_run_tool_loop(
            fake_execute_tool=fake_execute_tool,
            func_name="execute_code",
            func_args={"code": "print('hi')"},
        )

        assert "stream_callback" in captured_kwargs, (
            "execute_tool should receive stream_callback kwarg for execute_code"
        )
        assert captured_kwargs["stream_callback"] is not None, (
            "execute_code should receive a non-None stream_callback"
        )
        assert callable(captured_kwargs["stream_callback"]), (
            "stream_callback should be callable"
        )

    @pytest.mark.asyncio
    async def test_3_stdout_lines_yield_code_stdout_tuples(self):
        """Test 3: 3 stdout callbacks produce 3 ('code_stdout', payload) tuples with tool_call_id."""
        async def fake_execute_tool(name, args, user_id, context, **kwargs):
            cb = kwargs.get("stream_callback")
            if cb is not None:
                await cb("code_stdout", "a\n")
                await cb("code_stdout", "b\n")
                await cb("code_stdout", "c\n")
            return {"stdout": "a\nb\nc\n", "stderr": "", "exit_code": 0}

        events = await _invoke_run_tool_loop(
            fake_execute_tool=fake_execute_tool,
            func_name="execute_code",
            func_args={"code": "print('a')\nprint('b')\nprint('c')"},
            tc_id=FAKE_TC_ID,
        )

        stdout_events = [e for e in events if e[0] == "code_stdout"]
        assert len(stdout_events) == 3, f"Expected 3 code_stdout events, got {len(stdout_events)}"

        lines = [e[1]["line"] for e in stdout_events]
        assert lines == ["a\n", "b\n", "c\n"], f"Unexpected lines: {lines}"

        for ev_type, payload in stdout_events:
            assert "tool_call_id" in payload, "code_stdout payload must contain tool_call_id"
            assert payload["tool_call_id"] == FAKE_TC_ID, (
                f"tool_call_id should be {FAKE_TC_ID!r}, got {payload['tool_call_id']!r}"
            )

    @pytest.mark.asyncio
    async def test_4_stderr_line_yields_code_stderr_tuple(self):
        """Test 4: stderr callback produces ('code_stderr', payload) with correct D-P10-06 shape."""
        async def fake_execute_tool(name, args, user_id, context, **kwargs):
            cb = kwargs.get("stream_callback")
            if cb is not None:
                await cb("code_stderr", "err\n")
            return {"stdout": "", "stderr": "err\n", "exit_code": 1}

        events = await _invoke_run_tool_loop(
            fake_execute_tool=fake_execute_tool,
            func_name="execute_code",
            func_args={"code": "raise Exception('err')"},
            tc_id=FAKE_TC_ID,
        )

        stderr_events = [e for e in events if e[0] == "code_stderr"]
        assert len(stderr_events) == 1, f"Expected 1 code_stderr event, got {len(stderr_events)}"

        ev_type, payload = stderr_events[0]
        assert ev_type == "code_stderr"
        assert payload["type"] == "code_stderr"
        assert payload["line"] == "err\n"
        assert payload["tool_call_id"] == FAKE_TC_ID, (
            f"Expected tool_call_id={FAKE_TC_ID!r}, got {payload.get('tool_call_id')!r}"
        )

    @pytest.mark.asyncio
    async def test_5_tool_context_includes_thread_id(self):
        """Test 5: tool_context passed to execute_tool contains thread_id matching the thread."""
        captured_context = {}

        async def fake_execute_tool(name, args, user_id, context, **kwargs):
            if context:
                captured_context.update(context)
            return {"results": []}

        await _invoke_run_tool_loop(
            fake_execute_tool=fake_execute_tool,
            func_name="search_documents",
            func_args={"query": "test"},
            thread_id="thread-SPECIFIC-999",
        )

        assert "thread_id" in captured_context, (
            "tool_context must include thread_id (Phase 10 D-P10-04)"
        )
        assert captured_context["thread_id"] == "thread-SPECIFIC-999", (
            f"thread_id should match the request thread_id, got {captured_context['thread_id']!r}"
        )

    @pytest.mark.asyncio
    async def test_6_redaction_on_anonymizes_lines(self):
        """Test 6: When redaction_on=True, each code_stdout/stderr line is anonymized."""
        anon_call_args = []

        async def fake_anonymize(output, registry, redaction_service):
            anon_call_args.append(output)
            if isinstance(output, dict) and "line" in output:
                return {"line": "REDACTED"}
            return output

        async def fake_execute_tool(name, args, user_id, context, **kwargs):
            cb = kwargs.get("stream_callback")
            if cb is not None:
                await cb("code_stdout", "real-pii-data\n")
            return {"stdout": "real-pii-data\n", "stderr": "", "exit_code": 0}

        mock_registry = MagicMock()
        mock_redaction_svc = MagicMock()

        with patch("app.routers.chat.anonymize_tool_output", side_effect=fake_anonymize):
            events = await _invoke_run_tool_loop(
                fake_execute_tool=fake_execute_tool,
                func_name="execute_code",
                func_args={"code": "print('real-pii-data')"},
                redaction_on=True,
                registry=mock_registry,
                redaction_service=mock_redaction_svc,
            )

        stdout_events = [e for e in events if e[0] == "code_stdout"]
        assert len(stdout_events) == 1, f"Expected 1 code_stdout event, got {len(stdout_events)}"
        assert stdout_events[0][1]["line"] == "REDACTED", (
            "When redaction_on=True, line must be anonymized before yielding "
            f"(got: {stdout_events[0][1]['line']!r})"
        )

        # anonymize_tool_output must be called with a {"line": ...} dict
        line_dicts = [c for c in anon_call_args if isinstance(c, dict) and "line" in c]
        assert len(line_dicts) >= 1, (
            "anonymize_tool_output must be called with {'line': ...} for each sandbox line"
        )

    @pytest.mark.asyncio
    async def test_7_event_sequence_tool_start_stdout_tool_result(self):
        """Test 7: Exactly one tool_start, 2 code_stdout, then one tool_result — in order."""
        async def fake_execute_tool(name, args, user_id, context, **kwargs):
            cb = kwargs.get("stream_callback")
            if cb is not None:
                await cb("code_stdout", "line1\n")
                await cb("code_stdout", "line2\n")
            return {"stdout": "line1\nline2\n", "stderr": "", "exit_code": 0}

        events = await _invoke_run_tool_loop(
            fake_execute_tool=fake_execute_tool,
            func_name="execute_code",
            func_args={"code": "print('line1')\nprint('line2')"},
        )

        # Exclude the final 'records' sentinel
        non_records = [(t, d) for t, d in events if t != "records"]
        types_seq = [t for t, _ in non_records]

        assert types_seq.count("tool_start") == 1, f"Expected 1 tool_start, got {types_seq}"
        assert types_seq.count("tool_result") == 1, f"Expected 1 tool_result, got {types_seq}"
        assert types_seq.count("code_stdout") == 2, f"Expected 2 code_stdout, got {types_seq}"

        ts_i = types_seq.index("tool_start")
        tr_i = types_seq.index("tool_result")
        cs_indices = [i for i, t in enumerate(types_seq) if t == "code_stdout"]

        assert all(ts_i < i for i in cs_indices), (
            f"tool_start must come before all code_stdout events. Sequence: {types_seq}"
        )
        assert all(i < tr_i for i in cs_indices), (
            f"All code_stdout events must come before tool_result. Sequence: {types_seq}"
        )

    @pytest.mark.asyncio
    async def test_8_sandbox_disabled_no_stray_events(self):
        """Test 8 (regression): Non-execute_code calls produce no stray code_stdout/code_stderr events.

        This is the SC#5-style invariant: when sandbox_enabled=False and no execute_code
        is invoked, event output is identical to the pre-Phase-10 baseline.
        """
        captured_kwargs = {}

        async def fake_execute_tool(name, args, user_id, context, **kwargs):
            captured_kwargs.update(kwargs)
            return {"results": ["doc1"]}

        events = await _invoke_run_tool_loop(
            fake_execute_tool=fake_execute_tool,
            func_name="search_documents",
            func_args={"query": "contract terms"},
        )

        # No stray sandbox events
        stray = [e for e in events if e[0] in ("code_stdout", "code_stderr")]
        assert len(stray) == 0, (
            f"No code_stdout/code_stderr events for non-execute_code tools: {stray}"
        )

        # stream_callback must be None for non-execute_code
        assert captured_kwargs.get("stream_callback") is None, (
            "stream_callback must be None for non-execute_code tools"
        )

        # Baseline event types must still be present
        event_types = {e[0] for e in events}
        assert "tool_start" in event_types, "tool_start must still be present (no regression)"
        assert "tool_result" in event_types, "tool_result must still be present (no regression)"
        assert "records" in event_types, "records sentinel must still be present"
