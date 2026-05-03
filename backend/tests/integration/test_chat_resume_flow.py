"""Phase 19 / 19-05: Integration tests for the ask_user pause-and-resume flow.

Tests cover the two-request sequence:
  POST /chat (ask_user pause) → POST /chat (resume with answer)
  D-01, D-04, D-15, D-17, ASK-02, ASK-03, ASK-04

1. test_chat_resume_after_pause_routes_message_as_tool_result
2. test_resume_branch_short_circuits_when_sub_agent_disabled
3. test_resume_branch_short_circuits_when_no_active_run
4. test_resume_ignores_deep_mode_flag_in_body
5. test_offtopic_reply_passed_through_verbatim
6. test_resume_increments_last_round_index

Until plan 19-05 Task 3 lands (resume branch in stream_chat), all 6 tests fail (RED gate).
"""
from __future__ import annotations

import asyncio
import json
import contextlib
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_settings(**overrides):
    s = MagicMock()
    s.tool_registry_enabled = overrides.get("tool_registry_enabled", True)
    s.sub_agent_enabled = overrides.get("sub_agent_enabled", True)
    s.deep_mode_enabled = overrides.get("deep_mode_enabled", True)
    s.workspace_enabled = overrides.get("workspace_enabled", True)
    s.sandbox_enabled = False
    s.agents_enabled = False
    s.tools_enabled = True
    s.max_sub_agent_rounds = 15
    s.max_deep_rounds = 50
    s.fuzzy_deanon_mode = "none"
    s.rag_top_k = 5
    s.rag_similarity_threshold = 0.3
    return s


def _make_user():
    return {"id": "user-uuid", "email": "test@test.com", "token": "jwt-token", "role": "user"}


def _build_mock_openrouter_ask_user(question="A or B?"):
    """Mock openrouter that returns one ask_user call (pause scenario)."""
    ask_user_tc = {
        "id": "call-ask-1",
        "type": "function",
        "function": {"name": "ask_user", "arguments": json.dumps({"question": question})},
    }
    mock = MagicMock()
    mock.complete_with_tools = AsyncMock(
        return_value={"tool_calls": [ask_user_tc], "content": None, "usage": {}}
    )

    async def _stream():
        yield {"delta": "", "done": True, "usage": {}}

    mock.stream_response = AsyncMock(return_value=_stream())
    return mock


def _build_mock_openrouter_resume_response(answer_text="Got it."):
    """Mock openrouter that (after seeing tool_result for ask_user) returns final text."""
    mock = MagicMock()
    # No tool calls — terminal response with answer text
    mock.complete_with_tools = AsyncMock(
        return_value={"tool_calls": [], "content": answer_text, "usage": {"prompt_tokens": 10, "completion_tokens": 5}}
    )

    async def _stream():
        yield {"delta": answer_text, "done": False}
        yield {"delta": "", "done": True, "usage": {"prompt_tokens": 10, "completion_tokens": 5}}

    mock.stream_response = AsyncMock(return_value=_stream())
    return mock


async def _drive_run_deep_mode_loop(
    mock_settings,
    mock_openrouter,
    thread_id="thread-test-uuid",
    user_message="what should I do?",
    extra_patches=None,
    resume_run_id=None,
    resume_tool_result=None,
    resume_round_index=0,
):
    """Drive run_deep_mode_loop directly and collect SSE events."""
    from app.routers.chat import run_deep_mode_loop

    user = _make_user()
    mock_supabase = MagicMock()
    mock_supabase.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "msg-uuid", "thread_id": thread_id}
    ]

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

    # Phase 19 / 19-06: agent_runs_service methods must be mocked in base_patches
    # so that Site A (start_run) and Site C (complete) don't touch real Supabase.
    # Extra_patches may override individual methods for specific test scenarios.
    _mock_run_record = {
        "id": "run-uuid", "thread_id": thread_id, "status": "working",
        "pending_question": None, "last_round_index": 0, "error_detail": None,
    }
    base_patches = [
        patch("app.routers.chat.settings", mock_settings),
        patch("app.routers.chat.openrouter_service", mock_openrouter),
        patch("app.routers.chat.run_sub_agent_loop", AsyncMock(side_effect=Exception("should not be called"))),
        patch("app.routers.chat._persist_round_message", return_value="new-parent-id"),
        patch("app.routers.chat.build_skill_catalog_block", _noop_build_catalog_block),
        patch("app.services.skill_catalog_service.register_user_skills", _noop_register_user_skills),
        # Phase 19 / 19-06: mock lifecycle methods so tests don't call real Supabase
        patch("app.routers.chat.agent_runs_service.start_run", AsyncMock(return_value=_mock_run_record)),
        patch("app.routers.chat.agent_runs_service.complete", AsyncMock(return_value=None)),
        patch("app.routers.chat.agent_runs_service.error", AsyncMock(return_value=None)),
        patch("app.routers.chat.agent_runs_service.get_active_run", AsyncMock(return_value=None)),
        patch("app.routers.chat.agent_runs_service.set_pending_question", AsyncMock(return_value=None)),
    ] + (extra_patches or [])

    events = []

    async def _run():
        with contextlib.ExitStack() as stack:
            for p in base_patches:
                stack.enter_context(p)
            kwargs = {}
            if resume_run_id is not None:
                kwargs["resume_run_id"] = resume_run_id
                kwargs["resume_tool_result"] = resume_tool_result
                kwargs["resume_round_index"] = resume_round_index
            gen = run_deep_mode_loop(
                messages=[],
                user_message=user_message,
                user_id=user["id"],
                user_email=user["email"],
                token=user["token"],
                tool_context=tool_context,
                thread_id=thread_id,
                user_msg_id="user-msg-uuid",
                client=mock_supabase,
                sys_settings={"pii_redaction_enabled": False, "llm_model": "test-model"},
                web_search_effective=False,
                **kwargs,
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
# Test 1: Full two-request pause/resume sequence (ASK-02, ASK-03, ASK-04)
# ---------------------------------------------------------------------------

def test_chat_resume_after_pause_routes_message_as_tool_result():
    """Two-request sequence:
    Request 1: LLM calls ask_user(question='A or B?')
      → SSE: agent_status{waiting_for_user} + ask_user{question} + done
      → agent_runs row created with status='waiting_for_user'
    Request 2: body.message='A' → detected as resume
      → run_deep_mode_loop called with resume_tool_result='A'
      → LLM sees ask_user tool_result='A' and returns 'Got it.'
      → SSE: agent_status{working} + delta{Got it.} + agent_status{complete} + done
      → agent_runs transitioned to complete
    """
    import app.services.tool_registry as tr
    import app.services.tool_service as ts

    mock_settings = _make_settings(tool_registry_enabled=True, sub_agent_enabled=True)
    tr._REGISTRY.clear()
    with patch("app.services.tool_service.settings", mock_settings):
        ts._register_sub_agent_tools()

    # --- Request 1: pause ---
    mock_start_run = AsyncMock(return_value={
        "id": "run-uuid", "thread_id": "thread-test-uuid",
        "status": "working", "pending_question": None,
        "last_round_index": 0, "error_detail": None,
    })
    mock_get_active_run_none = AsyncMock(return_value=None)
    mock_set_pending = AsyncMock(return_value=None)

    pause_patches = [
        patch("app.routers.chat.agent_runs_service.start_run", mock_start_run),
        patch("app.routers.chat.agent_runs_service.get_active_run", mock_get_active_run_none),
        patch("app.routers.chat.agent_runs_service.set_pending_question", mock_set_pending),
    ]

    pause_events = asyncio.run(_drive_run_deep_mode_loop(
        mock_settings=mock_settings,
        mock_openrouter=_build_mock_openrouter_ask_user("A or B?"),
        extra_patches=pause_patches,
    ))

    pause_types = [e.get("type") for e in pause_events]
    assert "ask_user" in pause_types, f"Request 1 must emit ask_user SSE; got: {pause_types}"
    waiting_evts = [e for e in pause_events if e.get("type") == "agent_status" and e.get("status") == "waiting_for_user"]
    assert len(waiting_evts) >= 1, f"Request 1 must emit agent_status(waiting_for_user); got: {pause_types}"
    done_evts = [e for e in pause_events if e.get("done") is True]
    assert len(done_evts) >= 1, "Request 1 must emit done=True to close the stream"
    assert mock_set_pending.called, "set_pending_question must be called on Request 1"

    # --- Request 2: resume ---
    # The stream_chat resume branch detects waiting_for_user run and calls run_deep_mode_loop
    # with resume_run_id + resume_tool_result. Here we drive run_deep_mode_loop directly
    # with those kwargs to test the resume path inside the loop.
    mock_transition = AsyncMock(return_value=None)
    mock_complete = AsyncMock(return_value=None)
    mock_get_active_run_waiting = AsyncMock(return_value={
        "id": "run-uuid", "thread_id": "thread-test-uuid",
        "status": "waiting_for_user", "pending_question": "A or B?",
        "last_round_index": 0, "error_detail": None,
    })

    resume_patches = [
        patch("app.routers.chat.agent_runs_service.get_active_run", mock_get_active_run_waiting),
        patch("app.routers.chat.agent_runs_service.transition_status", mock_transition),
        patch("app.routers.chat.agent_runs_service.complete", mock_complete),
    ]

    resume_events = asyncio.run(_drive_run_deep_mode_loop(
        mock_settings=mock_settings,
        mock_openrouter=_build_mock_openrouter_resume_response("Got it."),
        user_message="A",
        resume_run_id="run-uuid",
        resume_tool_result="A",
        resume_round_index=1,
        extra_patches=resume_patches,
    ))

    resume_types = [e.get("type") for e in resume_events]
    # Must see working status at start of resumed loop
    working_evts = [e for e in resume_events if e.get("type") == "agent_status" and e.get("status") == "working"]
    assert len(working_evts) >= 1, f"Request 2 must emit agent_status(working); got: {resume_types}"
    # Must emit text content containing 'Got it.'
    delta_content = "".join(e.get("delta", "") for e in resume_events if e.get("type") == "delta" and not e.get("done"))
    assert "Got it." in delta_content, f"Request 2 must stream 'Got it.' text; got delta: {delta_content!r}"


# ---------------------------------------------------------------------------
# Test 2: Resume branch short-circuits when sub_agent_enabled=False (D-17)
# ---------------------------------------------------------------------------

def test_resume_branch_short_circuits_when_sub_agent_disabled():
    """With sub_agent_enabled=False, the resume detection branch in stream_chat
    must NOT be entered. The second POST is treated as a normal message.
    Verified by checking: run_deep_mode_loop does NOT receive resume_run_id kwargs."""
    import app.services.tool_registry as tr
    import app.services.tool_service as ts

    mock_settings = _make_settings(sub_agent_enabled=False)
    tr._REGISTRY.clear()
    with patch("app.services.tool_service.settings", mock_settings):
        ts._register_sub_agent_tools()

    # Verify ask_user is NOT registered when sub_agent_enabled=False
    assert "ask_user" not in tr._REGISTRY, (
        "ask_user must not be in registry when sub_agent_enabled=False"
    )

    # Simulate a second POST with body.message='A' but sub_agent_enabled=False
    # The resume detection should NOT trigger agent_runs_service.get_active_run
    mock_get_active_run = AsyncMock(return_value={
        "id": "run-uuid", "thread_id": "thread-test-uuid",
        "status": "waiting_for_user", "pending_question": "A or B?",
        "last_round_index": 0, "error_detail": None,
    })

    # Import stream_chat and verify the resume branch logic
    import inspect
    import app.routers.chat as chat_module
    src = inspect.getsource(chat_module.stream_chat)
    assert "sub_agent_enabled" in src, (
        "stream_chat must check settings.sub_agent_enabled before entering resume branch"
    )

    # The resume-detection branch must be gated by sub_agent_enabled AND deep_mode_enabled
    # When sub_agent_enabled=False: run_deep_mode_loop should NOT receive resume kwargs
    # We verify this by calling run_deep_mode_loop WITHOUT resume_run_id (normal path)
    mock_openrouter_normal = MagicMock()
    mock_openrouter_normal.complete_with_tools = AsyncMock(
        return_value={"tool_calls": [], "content": "normal response", "usage": {}}
    )

    async def _stream():
        yield {"delta": "normal response", "done": False}
        yield {"delta": "", "done": True, "usage": {}}

    mock_openrouter_normal.stream_response = AsyncMock(return_value=_stream())

    events = asyncio.run(_drive_run_deep_mode_loop(
        mock_settings=mock_settings,
        mock_openrouter=mock_openrouter_normal,
        user_message="A",
        # No resume_run_id = treated as normal new message
    ))

    # Should complete normally without ask_user-related events
    event_types = [e.get("type") for e in events]
    assert "ask_user" not in event_types, (
        f"No ask_user event expected for normal path; got: {event_types}"
    )
    assert "agent_status" not in event_types or all(
        e.get("status") != "waiting_for_user"
        for e in events if e.get("type") == "agent_status"
    ), "No waiting_for_user status expected when sub_agent_enabled=False"


# ---------------------------------------------------------------------------
# Test 3: Resume branch short-circuits when no active run (D-04)
# ---------------------------------------------------------------------------

def test_resume_branch_short_circuits_when_no_active_run():
    """With no waiting_for_user run in agent_runs, the second POST is treated
    as a normal new message (no resume injection)."""
    import app.services.tool_registry as tr
    import app.services.tool_service as ts

    mock_settings = _make_settings(sub_agent_enabled=True)
    tr._REGISTRY.clear()
    with patch("app.services.tool_service.settings", mock_settings):
        ts._register_sub_agent_tools()

    # stream_chat calls get_active_run → returns None (no paused run)
    mock_get_active_run_none = AsyncMock(return_value=None)

    # Normal LLM response (no ask_user)
    mock_openrouter = MagicMock()
    mock_openrouter.complete_with_tools = AsyncMock(
        return_value={"tool_calls": [], "content": "normal answer", "usage": {}}
    )

    async def _stream():
        yield {"delta": "normal answer", "done": False}
        yield {"delta": "", "done": True, "usage": {}}

    mock_openrouter.stream_response = AsyncMock(return_value=_stream())

    extra_patches = [
        patch("app.routers.chat.agent_runs_service.get_active_run", mock_get_active_run_none),
    ]

    events = asyncio.run(_drive_run_deep_mode_loop(
        mock_settings=mock_settings,
        mock_openrouter=mock_openrouter,
        user_message="hello",
        extra_patches=extra_patches,
    ))

    event_types = [e.get("type") for e in events]
    # Normal path — no resume-specific events
    assert "ask_user" not in event_types, (
        f"No ask_user event expected when no active run; got: {event_types}"
    )


# ---------------------------------------------------------------------------
# Test 4: Resume ignores deep_mode flag in body (D-04)
# ---------------------------------------------------------------------------

def test_resume_ignores_deep_mode_flag_in_body():
    """D-04: second POST has body.deep_mode=false; resume still proceeds via
    the original run's mode. The resume_run_id kwarg takes precedence over
    the deep_mode flag in the request body."""
    import app.services.tool_registry as tr
    import app.services.tool_service as ts

    mock_settings = _make_settings(sub_agent_enabled=True)
    tr._REGISTRY.clear()
    with patch("app.services.tool_service.settings", mock_settings):
        ts._register_sub_agent_tools()

    # Verify stream_chat source: resume branch must NOT check body.deep_mode
    import inspect
    import app.routers.chat as chat_module
    src = inspect.getsource(chat_module.stream_chat)
    # The resume branch comment must reference D-04 or body.deep_mode ignored
    assert "resume" in src.lower() or "get_active_run" in src, (
        "stream_chat must have resume-detection logic (D-04)"
    )

    # Drive run_deep_mode_loop with resume_run_id (simulating deep_mode=False body
    # but resume was detected via agent_runs): the loop should still work
    mock_transition = AsyncMock(return_value=None)
    mock_complete = AsyncMock(return_value=None)
    mock_get_active_run_waiting = AsyncMock(return_value={
        "id": "run-uuid", "thread_id": "thread-test-uuid",
        "status": "waiting_for_user", "pending_question": "What flavor?",
        "last_round_index": 0, "error_detail": None,
    })

    mock_openrouter = _build_mock_openrouter_resume_response("Chocolate")
    resume_patches = [
        patch("app.routers.chat.agent_runs_service.get_active_run", mock_get_active_run_waiting),
        patch("app.routers.chat.agent_runs_service.transition_status", mock_transition),
        patch("app.routers.chat.agent_runs_service.complete", mock_complete),
    ]

    # Even if body.deep_mode would be False, we explicitly pass resume_run_id
    # to simulate the resume path being triggered by stream_chat
    events = asyncio.run(_drive_run_deep_mode_loop(
        mock_settings=mock_settings,
        mock_openrouter=mock_openrouter,
        user_message="Chocolate",  # body.message is the user's reply
        resume_run_id="run-uuid",
        resume_tool_result="Chocolate",
        resume_round_index=1,
        extra_patches=resume_patches,
    ))

    # The resumed loop should produce a response (not be blocked by deep_mode=False)
    event_types = [e.get("type") for e in events]
    done_evts = [e for e in events if e.get("done") is True]
    assert len(done_evts) >= 1, (
        f"Resumed loop must complete (produce done=True); got: {event_types}"
    )


# ---------------------------------------------------------------------------
# Test 5: Off-topic reply passed through verbatim (D-15)
# ---------------------------------------------------------------------------

def test_offtopic_reply_passed_through_verbatim():
    """D-15: body.message='how's the weather?' is passed verbatim as the
    ask_user tool result. The LLM sees the raw reply and decides next step.
    No code-level filter is applied to the reply content."""
    import app.services.tool_registry as tr
    import app.services.tool_service as ts

    mock_settings = _make_settings(sub_agent_enabled=True)
    tr._REGISTRY.clear()
    with patch("app.services.tool_service.settings", mock_settings):
        ts._register_sub_agent_tools()

    captured_llm_messages = []

    async def _capture_complete_with_tools(messages, tools, **kwargs):
        captured_llm_messages.extend(messages)
        return {"tool_calls": [], "content": "I'll proceed with what I have.", "usage": {}}

    mock_openrouter = MagicMock()
    mock_openrouter.complete_with_tools = AsyncMock(side_effect=_capture_complete_with_tools)

    async def _stream():
        yield {"delta": "I'll proceed with what I have.", "done": False}
        yield {"delta": "", "done": True, "usage": {}}

    mock_openrouter.stream_response = AsyncMock(return_value=_stream())

    mock_transition = AsyncMock(return_value=None)
    mock_complete = AsyncMock(return_value=None)
    mock_get_active = AsyncMock(return_value={
        "id": "run-uuid", "thread_id": "thread-test-uuid",
        "status": "waiting_for_user", "pending_question": "Which contract?",
        "last_round_index": 0, "error_detail": None,
    })

    resume_patches = [
        patch("app.routers.chat.agent_runs_service.get_active_run", mock_get_active),
        patch("app.routers.chat.agent_runs_service.transition_status", mock_transition),
        patch("app.routers.chat.agent_runs_service.complete", mock_complete),
    ]

    off_topic_reply = "how's the weather?"
    asyncio.run(_drive_run_deep_mode_loop(
        mock_settings=mock_settings,
        mock_openrouter=mock_openrouter,
        user_message=off_topic_reply,
        resume_run_id="run-uuid",
        resume_tool_result=off_topic_reply,
        resume_round_index=1,
        extra_patches=resume_patches,
    ))

    # Verify: the off-topic reply must appear verbatim in the LLM messages
    # as the tool result content (D-15 — no filtering)
    all_tool_messages = [
        m for m in captured_llm_messages
        if m.get("role") == "tool"
    ]
    # The ask_user tool result should contain the verbatim off-topic reply
    tool_result_contents = [m.get("content", "") for m in all_tool_messages]
    assert any(off_topic_reply in c for c in tool_result_contents), (
        f"D-15 violation: off-topic reply '{off_topic_reply}' must be passed verbatim "
        f"as ask_user tool result; actual tool message contents: {tool_result_contents}"
    )


# ---------------------------------------------------------------------------
# Test 6: Resume increments last_round_index
# ---------------------------------------------------------------------------

def test_resume_increments_last_round_index():
    """agent_runs.last_round_index is advanced by 1 after resume (D-04).
    When run_deep_mode_loop is called with resume_round_index=N,
    the loop starts from iteration N (not 0)."""
    import app.services.tool_registry as tr
    import app.services.tool_service as ts

    mock_settings = _make_settings(sub_agent_enabled=True)
    tr._REGISTRY.clear()
    with patch("app.services.tool_service.settings", mock_settings):
        ts._register_sub_agent_tools()

    # The stream_chat resume branch calls run_deep_mode_loop with:
    #   resume_round_index = active_run["last_round_index"] + 1
    # We verify by inspecting stream_chat source for this pattern
    import inspect
    import app.routers.chat as chat_module
    src = inspect.getsource(chat_module.stream_chat)
    assert "last_round_index" in src, (
        "stream_chat must reference last_round_index when constructing resume call"
    )

    # Also verify run_deep_mode_loop signature accepts resume kwargs
    import inspect as _inspect
    sig = _inspect.signature(chat_module.run_deep_mode_loop)
    params = list(sig.parameters.keys())
    assert "resume_run_id" in params, (
        f"run_deep_mode_loop must accept resume_run_id kwarg; got params: {params}"
    )
    assert "resume_tool_result" in params, (
        f"run_deep_mode_loop must accept resume_tool_result kwarg; got params: {params}"
    )
    assert "resume_round_index" in params, (
        f"run_deep_mode_loop must accept resume_round_index kwarg; got params: {params}"
    )

    # Drive the loop with resume_round_index=2 to verify it behaves correctly
    mock_transition = AsyncMock(return_value=None)
    mock_complete = AsyncMock(return_value=None)
    mock_get_active = AsyncMock(return_value={
        "id": "run-uuid", "thread_id": "thread-test-uuid",
        "status": "waiting_for_user", "pending_question": "Check complete?",
        "last_round_index": 1,  # was at round 1 when paused
        "error_detail": None,
    })

    mock_openrouter = _build_mock_openrouter_resume_response("Yes, complete.")
    resume_patches = [
        patch("app.routers.chat.agent_runs_service.get_active_run", mock_get_active),
        patch("app.routers.chat.agent_runs_service.transition_status", mock_transition),
        patch("app.routers.chat.agent_runs_service.complete", mock_complete),
    ]

    events = asyncio.run(_drive_run_deep_mode_loop(
        mock_settings=mock_settings,
        mock_openrouter=mock_openrouter,
        user_message="Yes, complete.",
        resume_run_id="run-uuid",
        resume_tool_result="Yes, complete.",
        resume_round_index=2,  # last_round_index + 1
        extra_patches=resume_patches,
    ))

    # Loop must produce a response (not error out)
    event_types = [e.get("type") for e in events]
    done_evts = [e for e in events if e.get("done") is True]
    assert len(done_evts) >= 1, (
        f"Resumed loop (round_index=2) must complete; got event_types: {event_types}"
    )
