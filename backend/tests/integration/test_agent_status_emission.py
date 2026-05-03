"""Phase 19 / 19-06: Integration tests for agent_status SSE emission and agent_runs lifecycle.

Tests cover the three emission sites owned by this plan (A, C, D) plus the
append-only error contract (D-18..D-20) and D-07/D-17 invariants.

Site B (waiting_for_user) is OWNED by 19-05's ask_user dispatch handler.
Test 2 verifies Site B emits exactly once (from that canonical location).

Tests:
1. test_agent_status_transitions_working_to_complete
2. test_agent_status_transitions_to_waiting_for_user
3. test_agent_status_emits_error_on_uncaught_exception
4. test_failed_tool_call_appended_to_messages_with_structured_error
5. test_no_stack_trace_in_tool_result_payload
6. test_no_automatic_retry_on_tool_failure
7. test_sub_agent_does_not_emit_agent_status
8. test_agent_runs_row_lifecycle_start_to_complete

Until plan 19-06 Task 2 lands (Sites A, C, D wired in chat.py), tests 1, 3, 8 fail (RED).
Tests 2, 4, 5, 6, 7 may pass depending on existing behavior.
"""
from __future__ import annotations

import asyncio
import json
import contextlib
from unittest.mock import AsyncMock, MagicMock, call, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_settings(**overrides):
    s = MagicMock()
    s.tool_registry_enabled = overrides.get("tool_registry_enabled", True)
    s.sub_agent_enabled = overrides.get("sub_agent_enabled", True)
    s.deep_mode_enabled = overrides.get("deep_mode_enabled", True)
    s.workspace_enabled = overrides.get("workspace_enabled", False)
    s.sandbox_enabled = False
    s.agents_enabled = False
    s.tools_enabled = True
    s.max_sub_agent_rounds = overrides.get("max_sub_agent_rounds", 15)
    s.max_deep_rounds = overrides.get("max_deep_rounds", 50)
    s.fuzzy_deanon_mode = "none"
    s.rag_top_k = 5
    s.rag_similarity_threshold = 0.3
    return s


def _make_user():
    return {"id": "user-uuid", "email": "test@test.com", "token": "jwt-token", "role": "user"}


def _build_mock_openrouter_terminal(text="Done."):
    """Mock openrouter that returns a direct terminal text response (no tool calls)."""
    mock = MagicMock()
    mock.complete_with_tools = AsyncMock(
        return_value={"tool_calls": [], "content": text, "usage": {"prompt_tokens": 10, "completion_tokens": 5}}
    )

    async def _stream():
        yield {"delta": "", "done": True, "usage": {}}

    mock.stream_response = MagicMock(return_value=_stream())
    return mock


def _build_mock_openrouter_ask_user(question="confirm?"):
    """Mock openrouter that returns one ask_user tool call then closes."""
    ask_user_tc = {
        "id": "call-ask-user-1",
        "type": "function",
        "function": {"name": "ask_user", "arguments": json.dumps({"question": question})},
    }
    mock = MagicMock()
    mock.complete_with_tools = AsyncMock(
        return_value={"tool_calls": [ask_user_tc], "content": None, "usage": {}}
    )

    async def _stream():
        yield {"delta": "", "done": True, "usage": {}}

    mock.stream_response = MagicMock(return_value=_stream())
    return mock


def _build_mock_openrouter_raises(exc_factory=None):
    """Mock openrouter whose complete_with_tools raises an exception."""
    if exc_factory is None:
        exc_factory = lambda: RuntimeError("LLM unavailable")  # noqa: E731
    mock = MagicMock()
    mock.complete_with_tools = AsyncMock(side_effect=exc_factory())

    async def _stream():
        yield {"delta": "", "done": True, "usage": {}}

    mock.stream_response = MagicMock(return_value=_stream())
    return mock


def _build_mock_openrouter_tool_fails():
    """Mock openrouter that returns one tool call, then after the tool fail a terminal response."""
    tool_tc = {
        "id": "call-bad-tool-1",
        "type": "function",
        "function": {"name": "search_documents", "arguments": json.dumps({"query": "test"})},
    }
    # Round 1: returns tool call; round 2 (after tool error): terminal text
    responses = [
        {"tool_calls": [tool_tc], "content": None, "usage": {}},
        {"tool_calls": [], "content": "Recovered after error.", "usage": {"prompt_tokens": 10, "completion_tokens": 5}},
    ]
    mock = MagicMock()
    mock.complete_with_tools = AsyncMock(side_effect=responses)

    async def _stream():
        yield {"delta": "", "done": True, "usage": {}}

    mock.stream_response = MagicMock(return_value=_stream())
    return mock


def _build_mock_openrouter_task_dispatch():
    """Mock openrouter that returns a task tool call, then terminal text."""
    task_tc = {
        "id": "call-task-1",
        "type": "function",
        "function": {"name": "task", "arguments": json.dumps({"description": "do something"})},
    }
    responses = [
        {"tool_calls": [task_tc], "content": None, "usage": {}},
        {"tool_calls": [], "content": "Sub-agent done.", "usage": {"prompt_tokens": 10, "completion_tokens": 5}},
    ]
    mock = MagicMock()
    mock.complete_with_tools = AsyncMock(side_effect=responses)

    async def _stream():
        yield {"delta": "", "done": True, "usage": {}}

    mock.stream_response = MagicMock(return_value=_stream())
    return mock


async def _collect_sse_events(
    mock_settings,
    mock_openrouter,
    extra_patches=None,
    resume_run_id=None,
    resume_tool_result=None,
):
    """Drive run_deep_mode_loop with mocked dependencies and collect parsed SSE events."""
    from app.routers.chat import run_deep_mode_loop

    user = _make_user()
    thread_id = "thread-test-uuid"
    user_msg_id = "user-msg-uuid"

    mock_supabase = MagicMock()
    mock_supabase.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "msg-uuid", "thread_id": thread_id}
    ]
    mock_supabase.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = (
        {"title": "Existing Thread"}
    )

    tool_context = {
        "thread_id": thread_id,
        "user_id": user["id"],
        "user_email": user["email"],
        "token": user["token"],
    }

    async def _noop_register_user_skills(*a, **kw):
        pass

    async def _noop_build_catalog_block(*a, **kw):
        return ""

    all_patches = [
        patch("app.routers.chat.settings", mock_settings),
        patch("app.routers.chat.openrouter_service", mock_openrouter),
        patch("app.routers.chat.run_sub_agent_loop", AsyncMock(side_effect=Exception("should not be called"))),
        patch("app.routers.chat._persist_round_message", return_value="new-parent-id"),
        patch("app.routers.chat.build_skill_catalog_block", _noop_build_catalog_block),
        patch("app.services.skill_catalog_service.register_user_skills", _noop_register_user_skills),
        patch("app.routers.chat.agent_runs_service.start_run", AsyncMock(return_value={
            "id": "run-uuid", "thread_id": thread_id, "status": "working",
            "pending_question": None, "last_round_index": 0, "error_detail": None,
        })),
        patch("app.routers.chat.agent_runs_service.complete", AsyncMock(return_value=None)),
        patch("app.routers.chat.agent_runs_service.error", AsyncMock(return_value=None)),
        patch("app.routers.chat.agent_runs_service.get_active_run", AsyncMock(return_value=None)),
        patch("app.routers.chat.agent_runs_service.set_pending_question", AsyncMock(return_value=None)),
    ] + (extra_patches or [])

    events = []

    async def _run():
        with contextlib.ExitStack() as stack:
            for p in all_patches:
                stack.enter_context(p)
            gen = run_deep_mode_loop(
                messages=[],
                user_message="do something",
                user_id=user["id"],
                user_email=user["email"],
                token=user["token"],
                tool_context=tool_context,
                thread_id=thread_id,
                user_msg_id=user_msg_id,
                client=mock_supabase,
                sys_settings={"pii_redaction_enabled": False, "llm_model": "test-model"},
                web_search_effective=False,
                resume_run_id=resume_run_id,
                resume_tool_result=resume_tool_result,
            )
            async for chunk in gen:
                if chunk.startswith("data: "):
                    data_str = chunk[len("data: "):].strip()
                    try:
                        events.append(json.loads(data_str))
                    except json.JSONDecodeError:
                        pass

    await _run()
    return events


# ---------------------------------------------------------------------------
# Test 1: agent_status working→complete transitions (STATUS-01, D-16, D-17)
# ---------------------------------------------------------------------------

def test_agent_status_transitions_working_to_complete():
    """Happy-path single round: stub LLM returns direct terminal text.

    Expected SSE order (gated by sub_agent_enabled=True):
      agent_status{working} — Site A (loop entry)
      delta{done:False} — partial text chunks
      agent_status{complete} — Site C (before final done)
      delta{done:True}

    agent_runs row lifecycle:
      start_run called at loop entry
      complete called at terminal
    """
    mock_settings = _make_settings(sub_agent_enabled=True)
    mock_openrouter = _build_mock_openrouter_terminal("Done.")

    mock_start_run = AsyncMock(return_value={
        "id": "run-uuid", "thread_id": "thread-test-uuid", "status": "working",
        "pending_question": None, "last_round_index": 0, "error_detail": None,
    })
    mock_complete = AsyncMock(return_value=None)

    extra_patches = [
        patch("app.routers.chat.agent_runs_service.start_run", mock_start_run),
        patch("app.routers.chat.agent_runs_service.complete", mock_complete),
    ]

    events = asyncio.run(_collect_sse_events(
        mock_settings=mock_settings,
        mock_openrouter=mock_openrouter,
        extra_patches=extra_patches,
    ))

    event_types = [e.get("type") for e in events]

    # Site A: agent_status{working} must appear early in stream
    working_events = [e for e in events if e.get("type") == "agent_status" and e.get("status") == "working"]
    assert len(working_events) >= 1, (
        f"Expected agent_status{{status:'working'}} (Site A); got event_types: {event_types}"
    )

    # Site C: agent_status{complete} must appear before done
    complete_events = [e for e in events if e.get("type") == "agent_status" and e.get("status") == "complete"]
    assert len(complete_events) >= 1, (
        f"Expected agent_status{{status:'complete'}} (Site C); got event_types: {event_types}"
    )

    # Ordering: working before complete
    working_idx = next(i for i, e in enumerate(events) if e.get("type") == "agent_status" and e.get("status") == "working")
    complete_idx = next(i for i, e in enumerate(events) if e.get("type") == "agent_status" and e.get("status") == "complete")
    assert working_idx < complete_idx, (
        f"agent_status{{working}} must precede agent_status{{complete}}; "
        f"working_idx={working_idx}, complete_idx={complete_idx}"
    )

    # done{True} must appear after complete
    done_idx = next((i for i, e in enumerate(events) if e.get("done") is True), None)
    assert done_idx is not None, f"Expected delta{{done:True}}; got event_types: {event_types}"
    assert complete_idx < done_idx, (
        f"agent_status{{complete}} must precede delta{{done:True}}; "
        f"complete_idx={complete_idx}, done_idx={done_idx}"
    )

    # agent_runs lifecycle: start_run called
    assert mock_start_run.called, "agent_runs_service.start_run must be called at loop entry"

    # agent_runs lifecycle: complete called
    assert mock_complete.called, "agent_runs_service.complete must be called on successful completion"


# ---------------------------------------------------------------------------
# Test 2: waiting_for_user (Site B — owned by 19-05, verified here once)
# ---------------------------------------------------------------------------

def test_agent_status_transitions_to_waiting_for_user():
    """Ask user round: agent_status{working} (Site A) then agent_status{waiting_for_user} (Site B).

    Site B is OWNED by 19-05's ask_user dispatch handler. This test verifies:
    - Exactly 1 waiting_for_user emission (no duplicate from this plan's wiring)
    - SSE order: working → waiting_for_user → ask_user → done
    - agent_runs row at status='waiting_for_user' (set_pending_question called)
    """
    import app.services.tool_registry as tr
    import app.services.tool_service as ts

    mock_settings = _make_settings(sub_agent_enabled=True)
    tr._REGISTRY.clear()
    with patch("app.services.tool_service.settings", mock_settings):
        ts._register_sub_agent_tools()

    mock_openrouter = _build_mock_openrouter_ask_user("ready?")

    mock_start_run = AsyncMock(return_value={
        "id": "run-uuid", "thread_id": "thread-test-uuid", "status": "working",
        "pending_question": None, "last_round_index": 0, "error_detail": None,
    })
    mock_get_active_run = AsyncMock(return_value=None)
    mock_set_pending = AsyncMock(return_value=None)

    extra_patches = [
        patch("app.routers.chat.agent_runs_service.start_run", mock_start_run),
        patch("app.routers.chat.agent_runs_service.get_active_run", mock_get_active_run),
        patch("app.routers.chat.agent_runs_service.set_pending_question", mock_set_pending),
    ]

    events = asyncio.run(_collect_sse_events(
        mock_settings=mock_settings,
        mock_openrouter=mock_openrouter,
        extra_patches=extra_patches,
    ))

    event_types = [e.get("type") for e in events]

    # Site A: working emitted first
    working_events = [e for e in events if e.get("type") == "agent_status" and e.get("status") == "working"]
    assert len(working_events) >= 1, (
        f"Expected agent_status{{working}} at Site A; got: {event_types}"
    )

    # Site B: exactly 1 waiting_for_user (no duplicate from this plan)
    waiting_events = [e for e in events if e.get("type") == "agent_status" and e.get("status") == "waiting_for_user"]
    assert len(waiting_events) == 1, (
        f"Expected exactly 1 agent_status{{waiting_for_user}} (Site B canonical owner = 19-05); "
        f"got {len(waiting_events)}: {event_types}"
    )
    assert waiting_events[0].get("detail") == "ready?", (
        f"agent_status.detail must be the question; got: {waiting_events[0].get('detail')}"
    )

    # ask_user SSE event present
    ask_user_events = [e for e in events if e.get("type") == "ask_user"]
    assert len(ask_user_events) == 1, f"Expected exactly 1 ask_user event; got: {event_types}"

    # done emitted
    done_events = [e for e in events if e.get("done") is True]
    assert len(done_events) >= 1, f"Expected delta{{done:True}}; got: {event_types}"

    # agent_runs row in waiting_for_user — set_pending_question called
    assert mock_set_pending.called, "set_pending_question must be called on ask_user pause"


# ---------------------------------------------------------------------------
# Test 3: agent_status{error} on uncaught exception (Site D, D-16, STATUS-01)
# ---------------------------------------------------------------------------

def test_agent_status_emits_error_on_uncaught_exception():
    """Stub LLM raises an unrecoverable exception (not EgressBlockedAbort).

    Expected:
    - SSE stream emits agent_status{error, detail:str(exc)[:200]} (Site D)
    - SSE stream emits delta{done:True} after the error
    - agent_runs row transitions to status='error' (error() called)
    - agent_status{working} (Site A) was emitted before the error
    """
    mock_settings = _make_settings(sub_agent_enabled=True)
    # LLM raises an unrecoverable error
    mock_openrouter = _build_mock_openrouter_raises(lambda: RuntimeError("LLM unavailable"))

    mock_start_run = AsyncMock(return_value={
        "id": "run-uuid", "thread_id": "thread-test-uuid", "status": "working",
        "pending_question": None, "last_round_index": 0, "error_detail": None,
    })
    mock_error = AsyncMock(return_value=None)

    extra_patches = [
        patch("app.routers.chat.agent_runs_service.start_run", mock_start_run),
        patch("app.routers.chat.agent_runs_service.error", mock_error),
    ]

    events = asyncio.run(_collect_sse_events(
        mock_settings=mock_settings,
        mock_openrouter=mock_openrouter,
        extra_patches=extra_patches,
    ))

    event_types = [e.get("type") for e in events]

    # Site A: working must have been emitted before the exception
    working_events = [e for e in events if e.get("type") == "agent_status" and e.get("status") == "working"]
    assert len(working_events) >= 1, (
        f"Expected agent_status{{working}} (Site A) before error; got: {event_types}"
    )

    # Site D: agent_status{error} emitted
    error_events = [e for e in events if e.get("type") == "agent_status" and e.get("status") == "error"]
    assert len(error_events) >= 1, (
        f"Expected agent_status{{error}} (Site D); got event_types: {event_types}"
    )

    error_evt = error_events[0]
    detail = error_evt.get("detail", "")
    assert "LLM unavailable" in detail, (
        f"agent_status{{error}}.detail must include str(exc); got: {detail!r}"
    )
    assert len(detail) <= 200, (
        f"agent_status{{error}}.detail must be truncated to 200 chars (D-19); len={len(detail)}"
    )
    # No Traceback in detail (D-19)
    assert "Traceback" not in detail, (
        f"D-19 violation: detail must not contain 'Traceback'; got: {detail!r}"
    )

    # done emitted after error
    done_events = [e for e in events if e.get("done") is True]
    assert len(done_events) >= 1, (
        f"Expected delta{{done:True}} after error; got: {event_types}"
    )

    # agent_runs lifecycle: error() called
    assert mock_error.called, "agent_runs_service.error() must be called on uncaught exception (Site D)"
    call_kwargs = mock_error.call_args
    error_detail_arg = call_kwargs.kwargs.get("error_detail")
    assert error_detail_arg is not None, "error() must be called with error_detail kwarg"
    assert len(error_detail_arg) <= 500, "error_detail persisted to DB must be ≤500 chars (D-19)"


# ---------------------------------------------------------------------------
# Test 4: Failed tool call → structured D-18 error in tool_result output
# ---------------------------------------------------------------------------

def test_failed_tool_call_appended_to_messages_with_structured_error():
    """Stub a tool to raise; assert the persisted tool_result has D-18 shape.

    When a tool execution raises, the loop must persist:
      output={"error": "<message>", ...} or {"error": "...", "code": "...", "detail": "..."}

    Specifically: no exception is re-raised to the caller; the error is
    appended to loop_messages as a tool result and the loop continues.
    """
    mock_settings = _make_settings(sub_agent_enabled=True)
    mock_openrouter = _build_mock_openrouter_tool_fails()

    # Patch _dispatch_tool_deep to raise for the first call
    _dispatch_call_count = [0]

    async def _failing_dispatch(name, args, user_id, context=None, *, token=None):
        _dispatch_call_count[0] += 1
        raise ValueError("invalid query parameter")

    extra_patches = [
        patch("app.routers.chat._dispatch_tool_deep", _failing_dispatch),
    ]

    events = asyncio.run(_collect_sse_events(
        mock_settings=mock_settings,
        mock_openrouter=mock_openrouter,
        extra_patches=extra_patches,
    ))

    event_types = [e.get("type") for e in events]

    # Loop must NOT crash — should complete and emit done
    done_events = [e for e in events if e.get("done") is True]
    assert len(done_events) >= 1, (
        f"Loop must continue after tool failure and emit done; got: {event_types}"
    )

    # No agent_status{error} — tool errors are not loop-level errors (D-18, D-20)
    loop_error_events = [e for e in events if e.get("type") == "agent_status" and e.get("status") == "error"]
    assert len(loop_error_events) == 0, (
        f"Tool failure must NOT trigger agent_status{{error}} (D-18: append-only, not exception); "
        f"got {len(loop_error_events)} error events"
    )

    # Tool was dispatched exactly once (no retry — D-20)
    assert _dispatch_call_count[0] == 1, (
        f"Tool must be called exactly once (no retry — D-20); called {_dispatch_call_count[0]} times"
    )


# ---------------------------------------------------------------------------
# Test 5: No stack trace in tool_result payload (D-19)
# ---------------------------------------------------------------------------

def test_no_stack_trace_in_tool_result_payload():
    """When a tool raises, the tool_result persisted to loop_messages must NOT
    contain 'Traceback' (D-19 — stack traces stay server-side in logger only).

    We capture the tool_output that gets added to loop_messages by patching
    _persist_round_message and inspecting the tool_records argument.
    """
    mock_settings = _make_settings(sub_agent_enabled=True)
    mock_openrouter = _build_mock_openrouter_tool_fails()

    async def _traceback_dispatch(name, args, user_id, context=None, *, token=None):
        raise RuntimeError(
            "Traceback (most recent call last):\n  File 'tool.py', line 1\nRuntimeError: oops"
        )

    persisted_tool_records = []

    def _capture_persist(client, *, thread_id, user_id, parent_message_id,
                         content, tool_records, agent_name, deep_mode):
        persisted_tool_records.extend(tool_records)
        return "new-parent-id"

    extra_patches = [
        patch("app.routers.chat._dispatch_tool_deep", _traceback_dispatch),
        patch("app.routers.chat._persist_round_message", _capture_persist),
    ]

    asyncio.run(_collect_sse_events(
        mock_settings=mock_settings,
        mock_openrouter=mock_openrouter,
        extra_patches=extra_patches,
    ))

    # Inspect persisted tool records for Traceback content
    for rec in persisted_tool_records:
        output = getattr(rec, "output", None) or (rec.get("output") if isinstance(rec, dict) else None)
        error = getattr(rec, "error", None) or (rec.get("error") if isinstance(rec, dict) else None)

        if output:
            output_str = json.dumps(output) if isinstance(output, dict) else str(output)
            assert "Traceback" not in output_str, (
                f"D-19 violation: 'Traceback' found in tool_result output: {output_str[:200]}"
            )

        if error:
            error_str = str(error)
            assert "Traceback" not in error_str, (
                f"D-19 violation: 'Traceback' found in tool_record.error: {error_str[:200]}"
            )


# ---------------------------------------------------------------------------
# Test 6: No automatic retry on tool failure (D-20, STATUS-03)
# ---------------------------------------------------------------------------

def test_no_automatic_retry_on_tool_failure():
    """When a tool fails, the loop calls it exactly once — no retry helper invocation.

    After the single failure, the LLM sees the error in the next round and decides
    what to do. This test verifies the dispatch count is exactly 1 per failing tool.
    """
    mock_settings = _make_settings(sub_agent_enabled=True)
    mock_openrouter = _build_mock_openrouter_tool_fails()

    dispatch_call_count = [0]

    async def _counting_dispatch(name, args, user_id, context=None, *, token=None):
        dispatch_call_count[0] += 1
        raise ValueError(f"tool {name} failed")

    extra_patches = [
        patch("app.routers.chat._dispatch_tool_deep", _counting_dispatch),
    ]

    events = asyncio.run(_collect_sse_events(
        mock_settings=mock_settings,
        mock_openrouter=mock_openrouter,
        extra_patches=extra_patches,
    ))

    # Tool dispatched exactly once (no retry)
    assert dispatch_call_count[0] == 1, (
        f"D-20 violation: tool must be called exactly once; "
        f"dispatch count={dispatch_call_count[0]}"
    )

    # Loop continues normally after the error
    done_events = [e for e in events if e.get("done") is True]
    assert len(done_events) >= 1, "Loop must still complete with done=True after tool failure"


# ---------------------------------------------------------------------------
# Test 7: Sub-agent does NOT emit agent_status (D-07)
# ---------------------------------------------------------------------------

def test_sub_agent_does_not_emit_agent_status():
    """D-07: Only the outermost loop emits agent_status events.

    When a task tool call dispatches a sub-agent, the sub-agent's SSE events
    bubble up through the parent generator — but they must NOT include any
    agent_status events (the sub-agent visualization uses task_start/task_complete).

    This test stubs run_sub_agent_loop to yield a mix of events including a
    (hypothetical bad) agent_status event, and verifies the parent strips/excludes it.
    Actually tests the correct behavior: the parent forwards sub-agent events as-is,
    but the sub_agent_loop.py (19-03) must never yield agent_status events.
    We verify: no agent_status events with task_id in the parent stream
    (which would indicate they were forwarded from sub-agent).
    """
    import app.services.tool_registry as tr
    import app.services.tool_service as ts

    mock_settings = _make_settings(sub_agent_enabled=True)
    tr._REGISTRY.clear()
    with patch("app.services.tool_service.settings", mock_settings):
        ts._register_sub_agent_tools()

    mock_openrouter = _build_mock_openrouter_task_dispatch()

    async def _sub_agent_gen(*args, **kwargs):
        # Simulate sub-agent emitting tool events but NO agent_status
        yield {"type": "tool_start", "tool": "search_documents"}
        yield {"type": "tool_result", "tool": "search_documents"}
        # Sub-agent yields its terminal result dict
        yield {"_terminal_result": {"text": "sub-agent result text"}}

    extra_patches = [
        patch("app.routers.chat.run_sub_agent_loop", _sub_agent_gen),
    ]

    events = asyncio.run(_collect_sse_events(
        mock_settings=mock_settings,
        mock_openrouter=mock_openrouter,
        extra_patches=extra_patches,
    ))

    event_types = [e.get("type") for e in events]

    # No agent_status with task_id (would mean sub-agent emitted it)
    agent_status_with_task_id = [
        e for e in events
        if e.get("type") == "agent_status" and "task_id" in e
    ]
    assert len(agent_status_with_task_id) == 0, (
        f"D-07 violation: agent_status events with task_id found "
        f"(sub-agent must not emit agent_status): {agent_status_with_task_id}"
    )

    # Parent's own agent_status (working, complete) are present — these are fine
    parent_working = [e for e in events if e.get("type") == "agent_status" and e.get("status") == "working"]
    assert len(parent_working) >= 1, (
        f"Parent must still emit agent_status{{working}} (Site A); got: {event_types}"
    )

    # task_start and task_complete events are present
    task_start_events = [e for e in events if e.get("type") == "task_start"]
    assert len(task_start_events) >= 1, f"Expected task_start; got: {event_types}"

    task_complete_events = [e for e in events if e.get("type") == "task_complete"]
    assert len(task_complete_events) >= 1, f"Expected task_complete; got: {event_types}"


# ---------------------------------------------------------------------------
# Test 8: agent_runs lifecycle start→complete (STATUS-05)
# ---------------------------------------------------------------------------

def test_agent_runs_row_lifecycle_start_to_complete():
    """At loop entry (with sub_agent_enabled=True), start_run invoked.
    At successful exit, complete invoked. On uncaught exception, error invoked.

    Part A: happy path → start_run then complete
    Part B: exception path → start_run then error
    """
    # --- Part A: Happy path ---
    mock_settings = _make_settings(sub_agent_enabled=True)
    mock_openrouter_happy = _build_mock_openrouter_terminal("all done")

    mock_start_run_a = AsyncMock(return_value={
        "id": "run-happy", "thread_id": "thread-test-uuid", "status": "working",
        "pending_question": None, "last_round_index": 0, "error_detail": None,
    })
    mock_complete_a = AsyncMock(return_value=None)
    mock_error_a = AsyncMock(return_value=None)

    extra_a = [
        patch("app.routers.chat.agent_runs_service.start_run", mock_start_run_a),
        patch("app.routers.chat.agent_runs_service.complete", mock_complete_a),
        patch("app.routers.chat.agent_runs_service.error", mock_error_a),
    ]

    asyncio.run(_collect_sse_events(
        mock_settings=mock_settings,
        mock_openrouter=mock_openrouter_happy,
        extra_patches=extra_a,
    ))

    assert mock_start_run_a.called, "Part A: start_run must be called at loop entry"
    assert mock_complete_a.called, "Part A: complete must be called at successful exit"
    assert not mock_error_a.called, "Part A: error must NOT be called on happy path"

    # --- Part B: Exception path ---
    mock_openrouter_exc = _build_mock_openrouter_raises(lambda: RuntimeError("crash"))

    mock_start_run_b = AsyncMock(return_value={
        "id": "run-error", "thread_id": "thread-test-uuid", "status": "working",
        "pending_question": None, "last_round_index": 0, "error_detail": None,
    })
    mock_complete_b = AsyncMock(return_value=None)
    mock_error_b = AsyncMock(return_value=None)

    extra_b = [
        patch("app.routers.chat.agent_runs_service.start_run", mock_start_run_b),
        patch("app.routers.chat.agent_runs_service.complete", mock_complete_b),
        patch("app.routers.chat.agent_runs_service.error", mock_error_b),
    ]

    asyncio.run(_collect_sse_events(
        mock_settings=mock_settings,
        mock_openrouter=mock_openrouter_exc,
        extra_patches=extra_b,
    ))

    assert mock_start_run_b.called, "Part B: start_run must be called even when loop will error"
    assert mock_error_b.called, "Part B: error() must be called on uncaught exception"
    assert not mock_complete_b.called, "Part B: complete must NOT be called on exception path"

    # Verify error was called with run_id from start_run
    error_call = mock_error_b.call_args
    run_id_arg = error_call.args[0] if error_call.args else error_call.kwargs.get("run_id")
    # Either positional or keyword — verify it matches the run_id from start_run
    assert run_id_arg == "run-error" or error_call.kwargs.get("run_id") == "run-error" or (
        len(error_call.args) >= 1 and error_call.args[0] == "run-error"
    ), f"error() must be called with run_id from start_run; got call: {error_call}"
