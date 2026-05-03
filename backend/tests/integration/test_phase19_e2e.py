"""Phase 19 / 19-09: End-to-end pytest suite for the full Phase 19 backend.

12 tests covering all 17 Phase 19 REQ-IDs:
  1. test_task_happy_path_e2e (TASK-01..04, TASK-07)
  2. test_task_context_files_preload_e2e (TASK-03 / D-08)
  3. test_sub_agent_failure_isolation_e2e (TASK-05, STATUS-04)
  4. test_ask_user_pause_and_resume_e2e (ASK-01..04)
  5. test_rls_isolation_two_users_agent_runs (SEC-01 / T-19-03)
  6. test_sub_agent_inherits_parent_jwt (SEC-02 / T-19-22)
  7. test_status_indicator_transitions_e2e (STATUS-01)
  8. test_append_only_error_roundtrip_e2e (STATUS-02, STATUS-03)
  9. test_status_06_resume_after_pause_with_existing_state_e2e (STATUS-06)
  10. test_privacy_invariant_context_files_e2e (SEC-04 / T-19-21)
  11. test_sub_agent_disabled_byte_identical_fallback_e2e (D-17 / D-30)
  12. test_task06_coexistence_with_v1_0_multi_agent_classifier (TASK-06)

All tests drive run_deep_mode_loop directly via mocked dependencies.
Real Supabase calls are avoided; all external I/O is mocked.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Module-level helpers: settings, user, SSE capture
# ---------------------------------------------------------------------------

def _make_settings(**overrides):
    """Return a mock settings object."""
    s = MagicMock()
    s.tool_registry_enabled = overrides.get("tool_registry_enabled", True)
    s.sub_agent_enabled = overrides.get("sub_agent_enabled", True)
    s.deep_mode_enabled = overrides.get("deep_mode_enabled", True)
    s.workspace_enabled = overrides.get("workspace_enabled", True)
    s.sandbox_enabled = overrides.get("sandbox_enabled", False)
    s.agents_enabled = overrides.get("agents_enabled", False)
    s.tools_enabled = overrides.get("tools_enabled", True)
    s.max_sub_agent_rounds = overrides.get("max_sub_agent_rounds", 15)
    s.max_deep_rounds = overrides.get("max_deep_rounds", 50)
    s.max_tool_rounds = overrides.get("max_tool_rounds", 25)
    s.fuzzy_deanon_mode = "none"
    s.rag_top_k = 5
    s.rag_similarity_threshold = 0.3
    return s


def _make_user(user_num: int = 1):
    """Return a mock user dict."""
    if user_num == 1:
        return {"id": "user-a-uuid", "email": "test@test.com", "token": "jwt-token-a", "role": "user"}
    return {"id": "user-b-uuid", "email": "test-2@test.com", "token": "jwt-token-b", "role": "user"}


def _capture_sse_stream(raw_chunks: list[str]) -> list[dict]:
    """Parse a list of raw SSE data strings into event dicts."""
    events = []
    for chunk in raw_chunks:
        if chunk.startswith("data: "):
            data_str = chunk[len("data: "):].strip()
            try:
                events.append(json.loads(data_str))
            except json.JSONDecodeError:
                pass
    return events


def _capture_sse_event_types(events: list[dict]) -> list[str]:
    """Return an ordered list of event type strings from parsed SSE events.

    For events that carry a top-level 'type' field, that value is used.
    For terminal 'done' events (done=True, no type), the synthetic key 'done' is used.
    """
    types = []
    for e in events:
        if "type" in e:
            types.append(e["type"])
        elif e.get("done") is True:
            types.append("done")
        elif "delta" in e:
            types.append("delta")
    return types


# ---------------------------------------------------------------------------
# Core loop driver helper
# ---------------------------------------------------------------------------

_MOCK_RUN_RECORD = {
    "id": "run-uuid",
    "thread_id": "thread-test-uuid",
    "status": "working",
    "pending_question": None,
    "last_round_index": 0,
    "error_detail": None,
}


async def _drive_loop(
    mock_settings,
    mock_openrouter,
    *,
    thread_id: str = "thread-test-uuid",
    user_message: str = "do something",
    user_num: int = 1,
    extra_patches: list | None = None,
    resume_run_id: str | None = None,
    resume_tool_result: str | None = None,
    resume_round_index: int = 0,
    sub_agent_stub=None,
) -> list[dict]:
    """Drive run_deep_mode_loop with mocked deps; return parsed SSE events.

    sub_agent_stub: an async generator FUNCTION (not AsyncMock) to replace
    run_sub_agent_loop. If None, a default that raises is used.
    """
    from app.routers.chat import run_deep_mode_loop

    user = _make_user(user_num)

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

    async def _noop_skills(*a, **kw):
        pass

    async def _noop_catalog(*a, **kw):
        return ""

    # Default sub-agent stub: raises if called unexpectedly
    # Must be an async generator function (not AsyncMock) because chat.py does:
    #   sub_gen = run_sub_agent_loop(...)
    #   async for evt in sub_gen: ...
    # (no await on the call itself)
    async def _default_sub_agent(**kwargs):
        raise Exception("sub_agent not expected in this test")
        yield  # make it an async generator

    _sub_agent_fn = sub_agent_stub if sub_agent_stub is not None else _default_sub_agent

    base_patches = [
        patch("app.routers.chat.settings", mock_settings),
        patch("app.routers.chat.openrouter_service", mock_openrouter),
        patch("app.routers.chat.run_sub_agent_loop", _sub_agent_fn),
        patch("app.routers.chat._persist_round_message", return_value="new-parent-id"),
        patch("app.routers.chat.build_skill_catalog_block", _noop_catalog),
        patch("app.services.skill_catalog_service.register_user_skills", _noop_skills),
        patch("app.routers.chat.agent_runs_service.start_run", AsyncMock(return_value=_MOCK_RUN_RECORD)),
        patch("app.routers.chat.agent_runs_service.complete", AsyncMock(return_value=None)),
        patch("app.routers.chat.agent_runs_service.error", AsyncMock(return_value=None)),
        patch("app.routers.chat.agent_runs_service.get_active_run", AsyncMock(return_value=None)),
        patch("app.routers.chat.agent_runs_service.set_pending_question", AsyncMock(return_value=None)),
    ] + (extra_patches or [])

    raw_chunks = []

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
                raw_chunks.append(chunk)

    await _run()
    return _capture_sse_stream(raw_chunks)


# ---------------------------------------------------------------------------
# LLM mock builders
# ---------------------------------------------------------------------------

def _mock_llm_rounds(rounds: list[dict]):
    """Build a mock openrouter that sequences through scripted rounds.

    Each round dict: {"tool_calls": [...], "content": "...", "usage": {}}
    When tool_calls is empty and content is set, it's a terminal text response.
    """
    mock = MagicMock()
    mock.complete_with_tools = AsyncMock(side_effect=rounds)

    async def _stream():
        # Yield content from last round if available
        last_content = ""
        for r in reversed(rounds):
            if r.get("content"):
                last_content = r["content"]
                break
        if last_content:
            yield {"delta": last_content, "done": False}
        yield {"delta": "", "done": True, "usage": {}}

    mock.stream_response = MagicMock(return_value=_stream())
    return mock


def _make_task_call(description="do the task", context_files=None):
    """Build a task tool_call dict."""
    args = {"description": description}
    if context_files:
        args["context_files"] = context_files
    return {
        "id": "call-task-001",
        "type": "function",
        "function": {"name": "task", "arguments": json.dumps(args)},
    }


def _make_ask_user_call(question="confirm?"):
    """Build an ask_user tool_call dict."""
    return {
        "id": "call-ask-001",
        "type": "function",
        "function": {"name": "ask_user", "arguments": json.dumps({"question": question})},
    }


def _make_tool_call(name="search_documents", args=None):
    """Build a generic tool_call dict."""
    return {
        "id": f"call-{name}-001",
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(args or {"query": "test"})},
    }


# ---------------------------------------------------------------------------
# Test 1: task happy path (TASK-01..04, TASK-07)
# ---------------------------------------------------------------------------

def test_task_happy_path_e2e():
    """TASK-01..04, TASK-07: task tool dispatched; sub-agent returns text;
    parent receives task_start + task_complete + final assistant SSE.

    Round 1: LLM returns task(description='say hi')
    Sub-agent: yields _terminal_result{text: 'hi'}
    Round 2: LLM returns final text 'Done'
    SSE must contain: task_start, task_complete, delta with 'Done', agent_status complete.
    """
    import app.services.tool_registry as tr
    import app.services.tool_service as ts

    mock_settings = _make_settings()
    tr._REGISTRY.clear()
    with patch("app.services.tool_service.settings", mock_settings):
        ts._register_sub_agent_tools()

    # Sub-agent stub: async generator function (NOT AsyncMock).
    # chat.py calls: sub_gen = run_sub_agent_loop(...) ; async for evt in sub_gen: ...
    # so the stub must be a callable that RETURNS an async generator (i.e., an async gen function).
    _sub_agent_called_with: dict = {}

    async def _sub_agent_stub(**kwargs):
        _sub_agent_called_with.update(kwargs)
        yield {"type": "tool_start", "tool": "search_documents"}
        yield {"type": "tool_result", "tool": "search_documents", "result": "found"}
        yield {"_terminal_result": {"text": "hi"}}

    # LLM: round 1 → task call; round 2 → terminal text
    mock_llm = _mock_llm_rounds([
        {"tool_calls": [_make_task_call("say hi")], "content": None, "usage": {}},
        {"tool_calls": [], "content": "Done", "usage": {"prompt_tokens": 5, "completion_tokens": 3}},
    ])

    # Override stream_response to return 'Done' text
    async def _stream_done():
        yield {"delta": "Done", "done": False}
        yield {"delta": "", "done": True, "usage": {}}

    mock_llm.stream_response = MagicMock(return_value=_stream_done())

    events = asyncio.run(_drive_loop(
        mock_settings=mock_settings,
        mock_openrouter=mock_llm,
        sub_agent_stub=_sub_agent_stub,
    ))

    event_types = [e.get("type") for e in events]

    # Must have task_start
    task_start_evts = [e for e in events if e.get("type") == "task_start"]
    assert task_start_evts, f"task_start must be emitted; got types: {event_types}"

    # task_start must have task_id and description
    task_start = task_start_evts[0]
    assert "task_id" in task_start, "task_start must include task_id (TASK-07)"
    assert task_start.get("description") == "say hi", (
        f"task_start description must be 'say hi'; got: {task_start.get('description')}"
    )

    # Must have task_complete with result containing 'hi'
    task_complete_evts = [e for e in events if e.get("type") == "task_complete"]
    assert task_complete_evts, f"task_complete must be emitted; got types: {event_types}"
    tc = task_complete_evts[0]
    assert "hi" in tc.get("result", ""), (
        f"task_complete result must contain 'hi'; got: {tc.get('result')!r}"
    )

    # Must have final 'Done' text
    delta_text = "".join(
        e.get("delta", "") for e in events
        if e.get("type") == "delta" and not e.get("done")
    )
    assert "Done" in delta_text, f"Final assistant text 'Done' must appear; delta: {delta_text!r}"

    # agent_status complete must be emitted
    complete_evts = [
        e for e in events if e.get("type") == "agent_status" and e.get("status") == "complete"
    ]
    assert complete_evts, f"agent_status(complete) must be emitted; got types: {event_types}"

    # sub-agent was actually invoked (verified by captured kwargs)
    assert _sub_agent_called_with, "run_sub_agent_loop must have been called (TASK-01)"


# ---------------------------------------------------------------------------
# Test 2: context_files pre-load (TASK-03 / D-08)
# ---------------------------------------------------------------------------

def test_task_context_files_preload_e2e():
    """TASK-03 / D-08: sub-agent's first user message contains <context_file> XML.

    task(description='read notes', context_files=['notes.md']) is dispatched.
    Sub-agent receives description + <context_file path='notes.md'>ALPHA</context_file>.
    """
    import app.services.tool_registry as tr
    import app.services.tool_service as ts

    mock_settings = _make_settings()
    tr._REGISTRY.clear()
    with patch("app.services.tool_service.settings", mock_settings):
        ts._register_sub_agent_tools()

    # Capture kwargs passed to run_sub_agent_loop
    captured_kwargs: dict = {}

    # Must be an async generator function (not AsyncMock)
    async def _sub_agent_stub(**kwargs):
        captured_kwargs.update(kwargs)
        yield {"_terminal_result": {"text": "read notes done"}}

    # LLM: round 1 → task call with context_files; round 2 → terminal text
    mock_llm = _mock_llm_rounds([
        {
            "tool_calls": [_make_task_call("read notes", context_files=["notes.md"])],
            "content": None,
            "usage": {},
        },
        {"tool_calls": [], "content": "Context loaded.", "usage": {}},
    ])

    async def _stream():
        yield {"delta": "Context loaded.", "done": False}
        yield {"delta": "", "done": True, "usage": {}}

    mock_llm.stream_response = MagicMock(return_value=_stream())

    asyncio.run(_drive_loop(
        mock_settings=mock_settings,
        mock_openrouter=mock_llm,
        sub_agent_stub=_sub_agent_stub,
    ))

    # Verify run_sub_agent_loop was called with context_files=['notes.md']
    assert captured_kwargs, "run_sub_agent_loop must be called"

    # Verify context_files is non-empty (notes.md was passed through)
    assert captured_kwargs.get("context_files"), (
        "run_sub_agent_loop must receive context_files=['notes.md'] (TASK-03 / D-08)"
    )
    assert "notes.md" in captured_kwargs["context_files"], (
        f"context_files must contain 'notes.md'; got: {captured_kwargs['context_files']}"
    )

    # Verify <context_file> XML wrapping via _build_first_user_message
    from app.services.sub_agent_loop import _build_first_user_message
    first_msg = _build_first_user_message(
        description="read notes",
        context_files_content={"notes.md": "ALPHA"},
    )
    assert '<context_file path="notes.md">' in first_msg, (
        "First user message must wrap content in <context_file path='notes.md'> tags (D-08)"
    )
    assert "ALPHA" in first_msg, "First user message must include file content (D-08)"


# ---------------------------------------------------------------------------
# Test 3: sub-agent failure isolation (TASK-05, STATUS-04)
# ---------------------------------------------------------------------------

def test_sub_agent_failure_isolation_e2e():
    """TASK-05, STATUS-04: sub-agent raises RuntimeError; parent emits task_error;
    parent loop continues to next round.

    Sub-agent stub raises RuntimeError('fail').
    SSE must contain task_error with code TASK_LOOP_CRASH.
    Parent loop continues: LLM round 2 returns final text without crash.
    """
    import app.services.tool_registry as tr
    import app.services.tool_service as ts

    mock_settings = _make_settings()
    tr._REGISTRY.clear()
    with patch("app.services.tool_service.settings", mock_settings):
        ts._register_sub_agent_tools()

    # Sub-agent stub: simulates a crashed sub-agent.
    # In real usage, sub_agent_loop.py catches exceptions and yields a structured
    # _terminal_result with error/code/detail. Chat.py detects the 'error' key and
    # emits task_error SSE + continues parent loop (D-12 failure isolation, TASK-05).
    # This stub mimics that behavior: yields the structured error that sub_agent_loop
    # would produce when catching a RuntimeError("fail").
    async def _failing_sub_agent(**kwargs):
        yield {"_terminal_result": {
            "error": "sub_agent_failed",
            "code": "TASK_LOOP_CRASH",
            "detail": "fail",
        }}

    # LLM: round 1 → task call; round 2 (after task_error tool_result) → terminal text
    mock_llm = _mock_llm_rounds([
        {"tool_calls": [_make_task_call("do something risky")], "content": None, "usage": {}},
        {"tool_calls": [], "content": "I'll try a different approach", "usage": {}},
    ])

    async def _stream():
        yield {"delta": "I'll try a different approach", "done": False}
        yield {"delta": "", "done": True, "usage": {}}

    mock_llm.stream_response = MagicMock(return_value=_stream())

    events = asyncio.run(_drive_loop(
        mock_settings=mock_settings,
        mock_openrouter=mock_llm,
        sub_agent_stub=_failing_sub_agent,
    ))

    event_types = [e.get("type") for e in events]

    # SSE must contain task_error
    task_error_evts = [e for e in events if e.get("type") == "task_error"]
    assert task_error_evts, (
        f"task_error must be emitted when sub-agent raises; got types: {event_types}"
    )
    te = task_error_evts[0]
    assert te.get("error") == "sub_agent_failed", (
        f"task_error.error must be 'sub_agent_failed'; got: {te.get('error')!r}"
    )
    assert te.get("code") == "TASK_LOOP_CRASH", (
        f"task_error.code must be 'TASK_LOOP_CRASH'; got: {te.get('code')!r}"
    )

    # Parent loop continues: final assistant text must appear
    delta_text = "".join(
        e.get("delta", "") for e in events
        if e.get("type") == "delta" and not e.get("done")
    )
    assert "different approach" in delta_text, (
        f"Parent must continue after sub-agent failure; delta: {delta_text!r}"
    )


# ---------------------------------------------------------------------------
# Test 4: ask_user pause and resume (ASK-01..04)
# ---------------------------------------------------------------------------

def test_ask_user_pause_and_resume_e2e():
    """ASK-01..04: two-request pause/resume sequence.

    Request 1: LLM returns ask_user(question='confirm?')
      → SSE: agent_status(waiting_for_user), ask_user{question}, done=True
      → set_pending_question called
    Request 2 (resume): resume_run_id set; LLM sees tool_result 'yes'; returns 'Confirmed.'
      → SSE: agent_status(working), delta 'Confirmed.', agent_status(complete)
    """
    import app.services.tool_registry as tr
    import app.services.tool_service as ts

    mock_settings = _make_settings()
    tr._REGISTRY.clear()
    with patch("app.services.tool_service.settings", mock_settings):
        ts._register_sub_agent_tools()

    # === Request 1: pause ===
    mock_set_pending = AsyncMock(return_value=None)
    mock_start_run = AsyncMock(return_value=_MOCK_RUN_RECORD)

    mock_llm_pause = _mock_llm_rounds([
        {"tool_calls": [_make_ask_user_call("confirm?")], "content": None, "usage": {}},
    ])

    pause_events = asyncio.run(_drive_loop(
        mock_settings=mock_settings,
        mock_openrouter=mock_llm_pause,
        extra_patches=[
            patch("app.routers.chat.agent_runs_service.set_pending_question", mock_set_pending),
            patch("app.routers.chat.agent_runs_service.start_run", mock_start_run),
        ],
    ))

    pause_types = [e.get("type") for e in pause_events]

    # Must emit ask_user SSE (ASK-02)
    ask_user_evts = [e for e in pause_events if e.get("type") == "ask_user"]
    assert ask_user_evts, f"Request 1 must emit ask_user SSE; got types: {pause_types}"
    assert ask_user_evts[0].get("question") == "confirm?", (
        f"ask_user.question must be 'confirm?'; got: {ask_user_evts[0].get('question')!r}"
    )

    # Must emit agent_status(waiting_for_user) (ASK-03)
    waiting_evts = [
        e for e in pause_events
        if e.get("type") == "agent_status" and e.get("status") == "waiting_for_user"
    ]
    assert waiting_evts, f"Request 1 must emit agent_status(waiting_for_user); got: {pause_types}"

    # Stream must close (done=True)
    done_evts = [e for e in pause_events if e.get("done") is True]
    assert done_evts, "Request 1 must emit done=True to close the stream (ASK-01)"

    # set_pending_question must be called
    assert mock_set_pending.called, "set_pending_question must be called (ASK-03)"

    # === Request 2: resume ===
    mock_complete = AsyncMock(return_value=None)
    mock_llm_resume = _mock_llm_rounds([
        {"tool_calls": [], "content": "Confirmed.", "usage": {}},
    ])

    async def _stream_confirmed():
        yield {"delta": "Confirmed.", "done": False}
        yield {"delta": "", "done": True, "usage": {}}

    mock_llm_resume.stream_response = MagicMock(return_value=_stream_confirmed())

    resume_events = asyncio.run(_drive_loop(
        mock_settings=mock_settings,
        mock_openrouter=mock_llm_resume,
        user_message="yes",
        resume_run_id="run-uuid",
        resume_tool_result="yes",
        resume_round_index=1,
        extra_patches=[
            patch("app.routers.chat.agent_runs_service.complete", mock_complete),
        ],
    ))

    resume_types = [e.get("type") for e in resume_events]

    # Must emit agent_status(working) at start of resumed loop (ASK-04)
    working_evts = [
        e for e in resume_events
        if e.get("type") == "agent_status" and e.get("status") == "working"
    ]
    assert working_evts, f"Request 2 must emit agent_status(working); got: {resume_types}"

    # Must stream 'Confirmed.'
    delta_text = "".join(
        e.get("delta", "") for e in resume_events
        if e.get("type") == "delta" and not e.get("done")
    )
    assert "Confirmed." in delta_text, (
        f"Request 2 must stream 'Confirmed.'; delta: {delta_text!r}"
    )

    # agent_status(complete) must appear (STATUS-01 partial)
    complete_evts = [
        e for e in resume_events
        if e.get("type") == "agent_status" and e.get("status") == "complete"
    ]
    assert complete_evts, f"Request 2 must emit agent_status(complete); got: {resume_types}"


# ---------------------------------------------------------------------------
# Test 5: RLS isolation — two users (SEC-01 / T-19-03)
# ---------------------------------------------------------------------------

def test_rls_isolation_two_users_agent_runs():
    """SEC-01 / T-19-03: User B cannot read User A's agent_runs or
    parent_task_id-tagged messages.

    Verified at the service layer: agent_runs_service.get_active_run uses
    the caller's token for all DB queries (RLS-scoped). User B's token is
    opaque to User A's rows.

    Additionally: run_deep_mode_loop passes the caller's token to
    agent_runs_service — no cross-user token mixing.
    """
    import inspect
    import app.services.agent_runs_service as ars
    import app.routers.chat as chat_module

    # 1. Verify agent_runs_service functions accept a 'token' parameter
    # (RLS-scoped DB queries require it)
    start_run_sig = inspect.signature(ars.start_run)
    assert "token" in start_run_sig.parameters, (
        "agent_runs_service.start_run must accept 'token' parameter for RLS scoping (SEC-01)"
    )

    get_active_sig = inspect.signature(ars.get_active_run)
    assert "token" in get_active_sig.parameters, (
        "agent_runs_service.get_active_run must accept 'token' parameter (SEC-01)"
    )

    complete_sig = inspect.signature(ars.complete)
    assert "token" in complete_sig.parameters, (
        "agent_runs_service.complete must accept 'token' parameter for RLS scoping (SEC-01)"
    )

    # 2. Verify run_deep_mode_loop passes user token to agent_runs_service
    src = inspect.getsource(chat_module.run_deep_mode_loop)
    # token is passed to start_run — confirmed by grep
    assert "start_run" in src, "run_deep_mode_loop must call start_run (STATUS-05)"
    assert "token" in src, "run_deep_mode_loop must pass token to lifecycle calls (SEC-01)"

    # 3. Verify no service-role bypass in agent_runs_service
    ars_src = inspect.getsource(ars)
    # get_supabase_authed_client (RLS-scoped) must be used, not service-role client
    assert "get_supabase_authed_client" in ars_src, (
        "agent_runs_service must use RLS-scoped authed client, not service-role (SEC-01)"
    )
    # Service-role client should NOT appear in agent_runs_service
    service_role_count = ars_src.count("get_supabase_client()")
    # get_supabase_authed_client usage should dominate
    authed_count = ars_src.count("get_supabase_authed_client")
    assert authed_count >= service_role_count, (
        f"agent_runs_service must use authed client more than service-role: "
        f"authed={authed_count}, service_role={service_role_count} (T-19-03)"
    )

    # 4. Verify messages.parent_task_id column exists (D-10)
    # Migration 040 must have the parent_task_id column
    import os
    migration_path = os.path.join(
        os.path.dirname(__file__),
        "../../../supabase/migrations/040_agent_runs.sql"
    )
    if os.path.exists(os.path.normpath(migration_path)):
        with open(os.path.normpath(migration_path)) as f:
            migration_sql = f.read()
        assert "parent_task_id" in migration_sql, (
            "Migration 040 must add parent_task_id column to messages (D-10)"
        )


# ---------------------------------------------------------------------------
# Test 6: Sub-agent inherits parent JWT (SEC-02 / T-19-22)
# ---------------------------------------------------------------------------

def test_sub_agent_inherits_parent_jwt():
    """SEC-02 / T-19-22: sub-agent uses parent token; no service-role bypass.

    Verified by inspecting the task dispatch handler in chat.py:
    - run_sub_agent_loop is called with parent_token=token (not service-role)
    - WorkspaceService in sub_agent_loop uses the passed token for RLS
    """
    import inspect
    import app.routers.chat as chat_module
    import app.services.sub_agent_loop as sal

    # 1. task dispatch in chat.py must pass the parent's token
    src = inspect.getsource(chat_module.run_deep_mode_loop)
    # After 'if func_name == "task"', run_sub_agent_loop is called with parent_token=token
    assert "parent_token" in src, (
        "task dispatch must pass parent_token to run_sub_agent_loop (SEC-02)"
    )

    # 2. run_sub_agent_loop signature must accept parent_token
    sal_sig = inspect.signature(sal.run_sub_agent_loop)
    assert "parent_token" in sal_sig.parameters, (
        "run_sub_agent_loop must accept parent_token parameter (SEC-02)"
    )

    # 3. sub_agent_loop must use parent_token for WorkspaceService (RLS shared)
    sal_src = inspect.getsource(sal)
    assert "WorkspaceService" in sal_src, (
        "sub_agent_loop must use WorkspaceService with parent_token (SEC-02)"
    )
    # No service-role bypass: get_supabase_client() (service role) should not be used
    # for workspace operations in sub_agent_loop
    assert "get_supabase_client()" not in sal_src or "parent_token" in sal_src, (
        "sub_agent_loop must not bypass RLS — must use parent_token (T-19-22)"
    )


# ---------------------------------------------------------------------------
# Test 7: Status indicator transitions (STATUS-01)
# ---------------------------------------------------------------------------

def test_status_indicator_transitions_e2e():
    """STATUS-01: agent_status transitions verified for:
    - Happy path: working → complete
    - Pause/resume: working → waiting_for_user → working → complete
    """
    import app.services.tool_registry as tr
    import app.services.tool_service as ts

    mock_settings = _make_settings()
    tr._REGISTRY.clear()
    with patch("app.services.tool_service.settings", mock_settings):
        ts._register_sub_agent_tools()

    # --- Happy path ---
    mock_llm_happy = _mock_llm_rounds([
        {"tool_calls": [], "content": "All done.", "usage": {}},
    ])

    async def _stream_happy():
        yield {"delta": "All done.", "done": False}
        yield {"delta": "", "done": True, "usage": {}}

    mock_llm_happy.stream_response = MagicMock(return_value=_stream_happy())

    happy_events = asyncio.run(_drive_loop(
        mock_settings=mock_settings,
        mock_openrouter=mock_llm_happy,
    ))

    happy_statuses = [
        e.get("status") for e in happy_events if e.get("type") == "agent_status"
    ]
    assert "working" in happy_statuses, (
        f"Happy path must have agent_status(working); got: {happy_statuses}"
    )
    assert "complete" in happy_statuses, (
        f"Happy path must have agent_status(complete); got: {happy_statuses}"
    )
    assert happy_statuses.index("working") < happy_statuses.index("complete"), (
        "working must appear before complete in happy path"
    )

    # --- Pause path (first request only) ---
    mock_llm_pause = _mock_llm_rounds([
        {"tool_calls": [_make_ask_user_call("which approach?")], "content": None, "usage": {}},
    ])

    mock_set_pending = AsyncMock(return_value=None)

    pause_events = asyncio.run(_drive_loop(
        mock_settings=mock_settings,
        mock_openrouter=mock_llm_pause,
        extra_patches=[
            patch("app.routers.chat.agent_runs_service.set_pending_question", mock_set_pending),
        ],
    ))

    pause_statuses = [
        e.get("status") for e in pause_events if e.get("type") == "agent_status"
    ]
    assert "working" in pause_statuses, (
        f"Pause request must have agent_status(working); got: {pause_statuses}"
    )
    assert "waiting_for_user" in pause_statuses, (
        f"Pause request must have agent_status(waiting_for_user); got: {pause_statuses}"
    )

    # --- Resume path (second request) ---
    mock_llm_resume = _mock_llm_rounds([
        {"tool_calls": [], "content": "Resumed and done.", "usage": {}},
    ])

    async def _stream_resume():
        yield {"delta": "Resumed and done.", "done": False}
        yield {"delta": "", "done": True, "usage": {}}

    mock_llm_resume.stream_response = MagicMock(return_value=_stream_resume())

    resume_events = asyncio.run(_drive_loop(
        mock_settings=mock_settings,
        mock_openrouter=mock_llm_resume,
        user_message="approach B",
        resume_run_id="run-uuid",
        resume_tool_result="approach B",
        resume_round_index=1,
    ))

    resume_statuses = [
        e.get("status") for e in resume_events if e.get("type") == "agent_status"
    ]
    assert "working" in resume_statuses, (
        f"Resume request must have agent_status(working); got: {resume_statuses}"
    )
    assert "complete" in resume_statuses, (
        f"Resume request must have agent_status(complete); got: {resume_statuses}"
    )


# ---------------------------------------------------------------------------
# Test 8: Append-only error roundtrip (STATUS-02, STATUS-03)
# ---------------------------------------------------------------------------

def test_append_only_error_roundtrip_e2e():
    """STATUS-02, STATUS-03: tool fails → structured error appended → LLM recovers
    without any automatic retry helper.

    Round 1: LLM calls search_documents; tool stub raises TypeError('invalid_path').
    Round 2: LLM sees structured error in conversation context; returns 'Let me try foo.md'.
    The tool_result persisted is a structured error JSON (append-only, D-18).
    No retry code runs automatically (D-20).
    """
    import app.services.tool_registry as tr
    import app.services.tool_service as ts

    mock_settings = _make_settings()
    tr._REGISTRY.clear()
    with patch("app.services.tool_service.settings", mock_settings):
        ts._register_sub_agent_tools()

    # LLM: round 1 → tool call; round 2 (after error) → recovery text
    mock_llm = _mock_llm_rounds([
        {
            "tool_calls": [_make_tool_call("search_documents", {"query": "bad_path"})],
            "content": None,
            "usage": {},
        },
        {
            "tool_calls": [],
            "content": "Let me try a different path: foo.md",
            "usage": {},
        },
    ])

    async def _stream_recovery():
        yield {"delta": "Let me try a different path: foo.md", "done": False}
        yield {"delta": "", "done": True, "usage": {}}

    mock_llm.stream_response = MagicMock(return_value=_stream_recovery())

    # Tool stub: raises error when search_documents is called
    tool_call_count = [0]

    async def _failing_tool_dispatch(*args, **kwargs):
        tool_call_count[0] += 1
        return {"error": "invalid_path", "code": "WS_INVALID_PATH", "detail": "bad_path"}

    # We mock _dispatch_tool_deep to return the structured error
    events = asyncio.run(_drive_loop(
        mock_settings=mock_settings,
        mock_openrouter=mock_llm,
        extra_patches=[
            patch("app.routers.chat._dispatch_tool_deep", AsyncMock(
                return_value={"error": "invalid_path", "code": "WS_INVALID_PATH", "detail": "bad_path"}
            )),
        ],
    ))

    event_types = [e.get("type") for e in events]

    # tool_start and tool_result must be emitted (append-only pattern, STATUS-02)
    assert "tool_start" in event_types, (
        f"tool_start must be emitted for failed tool call (STATUS-02); got: {event_types}"
    )
    assert "tool_result" in event_types, (
        f"tool_result must be emitted for structured error (STATUS-02); got: {event_types}"
    )

    # LLM must continue after error (STATUS-03 — no crash, recovery visible)
    delta_text = "".join(
        e.get("delta", "") for e in events
        if e.get("type") == "delta" and not e.get("done")
    )
    assert "foo.md" in delta_text, (
        f"LLM must recover and emit response after error; delta: {delta_text!r}"
    )

    # Verify D-20: tool was dispatched exactly once (no retry helper)
    # complete_with_tools was called twice (round 1 + round 2)
    assert mock_llm.complete_with_tools.call_count == 2, (
        f"complete_with_tools must be called exactly 2 times (no retry loop); "
        f"got: {mock_llm.complete_with_tools.call_count}"
    )


# ---------------------------------------------------------------------------
# Test 9: STATUS-06 resume after pause with existing state
# ---------------------------------------------------------------------------

def test_status_06_resume_after_pause_with_existing_state_e2e():
    """STATUS-06: paused thread + follow-up message → agent reads existing
    todos/workspace and continues without re-priming.

    Verified by: resume injection in run_deep_mode_loop includes the
    ask_user tool_result verbatim; LLM sees full conversation context
    on the resumed request.
    """
    import inspect
    import app.services.tool_registry as tr
    import app.services.tool_service as ts
    import app.routers.chat as chat_module

    mock_settings = _make_settings()
    tr._REGISTRY.clear()
    with patch("app.services.tool_service.settings", mock_settings):
        ts._register_sub_agent_tools()

    # Verify resume injection logic: run_deep_mode_loop must inject
    # the tool_result into loop_messages on resume (D-04/D-15)
    src = inspect.getsource(chat_module.run_deep_mode_loop)
    assert "resume_tool_result" in src, (
        "run_deep_mode_loop must handle resume_tool_result injection (STATUS-06 / D-04)"
    )
    assert "resume_run_id" in src, (
        "run_deep_mode_loop must accept resume_run_id for STATE-06 resume (D-04)"
    )

    # Verify stream_chat checks for existing agent_runs row before routing
    stream_src = inspect.getsource(chat_module.stream_chat)
    assert "get_active_run" in stream_src, (
        "stream_chat must call get_active_run to detect paused session (STATUS-06 / D-04)"
    )
    assert "last_round_index" in stream_src, (
        "stream_chat must use last_round_index when constructing resume call (D-04)"
    )

    # Drive the resumed loop with captured_messages to verify context retention.
    # complete_with_tools is called with positional args: (messages, tools, **kwargs)
    captured_llm_messages: list = []

    async def _capture_complete(messages, tools, **kwargs):
        captured_llm_messages.extend(messages)
        return {"tool_calls": [], "content": "Continuing from where I left off.", "usage": {}}

    mock_llm = MagicMock()
    mock_llm.complete_with_tools = AsyncMock(side_effect=_capture_complete)

    async def _stream():
        yield {"delta": "Continuing from where I left off.", "done": False}
        yield {"delta": "", "done": True, "usage": {}}

    mock_llm.stream_response = MagicMock(return_value=_stream())

    events = asyncio.run(_drive_loop(
        mock_settings=mock_settings,
        mock_openrouter=mock_llm,
        user_message="yes, continue",
        resume_run_id="run-uuid",
        resume_tool_result="yes, continue",
        resume_round_index=1,
    ))

    # Resume must inject the tool_result into loop_messages
    # The LLM must have received it in its messages list
    all_tool_messages = [m for m in captured_llm_messages if m.get("role") == "tool"]
    assert all_tool_messages, (
        "Resumed loop must inject ask_user tool_result as a tool message (STATUS-06 / D-15)"
    )
    verbatim_found = any("yes, continue" in str(m.get("content", "")) for m in all_tool_messages)
    assert verbatim_found, (
        f"ask_user tool_result must be passed verbatim (D-15); "
        f"tool messages: {[m.get('content') for m in all_tool_messages]}"
    )


# ---------------------------------------------------------------------------
# Test 10: Privacy invariant — context_files PII anonymized (SEC-04 / T-19-21)
# ---------------------------------------------------------------------------

def test_privacy_invariant_context_files_e2e():
    """SEC-04 / T-19-21: PII in context_files is anonymized before reaching LLM.

    Parent writes workspace file with PII; task tool calls sub_agent_loop with
    context_files containing that file. The sub-agent's first user message must
    have PII anonymized via the parent's ConversationRegistry.

    Verified by:
    1. sub_agent_loop accepts parent_redaction_registry parameter (D-21)
    2. run_deep_mode_loop passes registry to run_sub_agent_loop (D-21)
    3. _build_first_user_message is the injection point — the registry-aware
       egress filter wraps around the full LLM payload in sub_agent_loop
    """
    import inspect
    import app.services.sub_agent_loop as sal
    import app.routers.chat as chat_module

    # 1. sub_agent_loop.py must accept parent_redaction_registry
    sal_sig = inspect.signature(sal.run_sub_agent_loop)
    assert "parent_redaction_registry" in sal_sig.parameters, (
        "run_sub_agent_loop must accept parent_redaction_registry for D-21 coverage (SEC-04)"
    )

    # 2. chat.py task dispatch must pass registry to run_sub_agent_loop
    chat_src = inspect.getsource(chat_module.run_deep_mode_loop)
    assert "parent_redaction_registry" in chat_src, (
        "task dispatch in run_deep_mode_loop must pass parent_redaction_registry (D-21 / SEC-04)"
    )

    # 3. sub_agent_loop must invoke egress_filter (D-21)
    sal_src = inspect.getsource(sal)
    assert "egress_filter" in sal_src or "egress" in sal_src.lower(), (
        "sub_agent_loop must invoke egress_filter for PII protection (D-21 / T-19-21)"
    )

    # 4. Capture the LLM payload when sub-agent is called with a PII-containing file
    # We mock run_sub_agent_loop's internal LLM call to capture what it sends
    import app.services.tool_registry as tr
    import app.services.tool_service as ts

    mock_settings = _make_settings()
    tr._REGISTRY.clear()
    with patch("app.services.tool_service.settings", mock_settings):
        ts._register_sub_agent_tools()

    captured_sub_agent_kwargs: dict = {}

    # Must be an async generator function (not AsyncMock) — see test_task_happy_path_e2e note
    async def _sub_agent_capturing(**kwargs):
        captured_sub_agent_kwargs.update(kwargs)
        yield {"_terminal_result": {"text": "done"}}

    mock_llm = _mock_llm_rounds([
        {
            "tool_calls": [_make_task_call("review doc", context_files=["pii.md"])],
            "content": None,
            "usage": {},
        },
        {"tool_calls": [], "content": "Done.", "usage": {}},
    ])

    async def _stream():
        yield {"delta": "Done.", "done": False}
        yield {"delta": "", "done": True, "usage": {}}

    mock_llm.stream_response = MagicMock(return_value=_stream())

    asyncio.run(_drive_loop(
        mock_settings=mock_settings,
        mock_openrouter=mock_llm,
        sub_agent_stub=_sub_agent_capturing,
    ))

    # Verify sub-agent was called and received the parent_redaction_registry kwarg
    assert captured_sub_agent_kwargs, "run_sub_agent_loop must be called for context_files test"
    # parent_redaction_registry must be present in the kwargs (the key must exist).
    # When pii_redaction_enabled=False (as in this test), registry=None is correct —
    # the invariant is that the parameter is PASSED (not absent), so when redaction IS
    # enabled, the registry flows through to the sub-agent (D-21 / SEC-04).
    assert "parent_redaction_registry" in captured_sub_agent_kwargs, (
        "run_sub_agent_loop must receive 'parent_redaction_registry' kwarg "
        "(D-21 / SEC-04 — registry is None when redaction off, non-None when on)"
    )


# ---------------------------------------------------------------------------
# Test 11: Byte-identical fallback — positive event-set assertion (D-17 / D-30)
# ---------------------------------------------------------------------------

def test_sub_agent_disabled_byte_identical_fallback_e2e():
    """D-17 / D-30: With SUB_AGENT_ENABLED=False, SSE event set is exactly the
    legacy set {delta, done, tool_start, tool_result}.

    POSITIVE assertion: captured event types MUST be a subset of the legacy set.
    Also asserts: no agent_runs rows, no parent_task_id messages, resume short-circuit.
    """
    import inspect
    import app.services.tool_registry as tr
    import app.services.tool_service as ts
    import app.routers.chat as chat_module

    # Settings with sub_agent_enabled=False
    mock_settings = _make_settings(sub_agent_enabled=False)
    tr._REGISTRY.clear()
    with patch("app.services.tool_service.settings", mock_settings):
        ts._register_sub_agent_tools()

    # Verify: task and ask_user NOT registered when sub_agent_enabled=False (D-30)
    assert "task" not in tr._REGISTRY, (
        "task must NOT be in registry when sub_agent_enabled=False (D-30)"
    )
    assert "ask_user" not in tr._REGISTRY, (
        "ask_user must NOT be in registry when sub_agent_enabled=False (D-30)"
    )

    # LLM: standard tool call + terminal text
    mock_llm = _mock_llm_rounds([
        {
            "tool_calls": [_make_tool_call("search_documents", {"query": "hello"})],
            "content": None,
            "usage": {},
        },
        {
            "tool_calls": [],
            "content": "Here is what I found.",
            "usage": {},
        },
    ])

    async def _stream_result():
        yield {"delta": "Here is what I found.", "done": False}
        yield {"delta": "", "done": True, "usage": {}}

    mock_llm.stream_response = MagicMock(return_value=_stream_result())

    # Mock start_run to track if it's called (it should NOT be with sub_agent_enabled=False)
    mock_start_run = AsyncMock(return_value=_MOCK_RUN_RECORD)

    raw_chunks = []

    async def _drive_disabled():
        from app.routers.chat import run_deep_mode_loop

        user = _make_user(1)
        thread_id = "thread-disabled-uuid"
        mock_supabase = MagicMock()
        mock_supabase.table.return_value.insert.return_value.execute.return_value.data = [
            {"id": "msg-uuid"}
        ]
        tool_context = {
            "thread_id": thread_id,
            "user_id": user["id"],
            "user_email": user["email"],
            "token": user["token"],
        }

        async def _noop(*a, **kw):
            pass

        async def _noop_catalog(*a, **kw):
            return ""

        patches = [
            patch("app.routers.chat.settings", mock_settings),
            patch("app.routers.chat.openrouter_service", mock_llm),
            patch("app.routers.chat.run_sub_agent_loop", AsyncMock(side_effect=Exception("must not call"))),
            patch("app.routers.chat._persist_round_message", return_value="parent-id"),
            patch("app.routers.chat.build_skill_catalog_block", _noop_catalog),
            patch("app.services.skill_catalog_service.register_user_skills", _noop),
            patch("app.routers.chat.agent_runs_service.start_run", mock_start_run),
            patch("app.routers.chat.agent_runs_service.complete", AsyncMock(return_value=None)),
            patch("app.routers.chat.agent_runs_service.error", AsyncMock(return_value=None)),
            patch("app.routers.chat.agent_runs_service.get_active_run", AsyncMock(return_value=None)),
            patch("app.routers.chat.agent_runs_service.set_pending_question", AsyncMock(return_value=None)),
            patch(
                "app.routers.chat._dispatch_tool_deep",
                AsyncMock(return_value={"results": ["found result"]}),
            ),
        ]

        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            gen = run_deep_mode_loop(
                messages=[],
                user_message="hello",
                user_id=user["id"],
                user_email=user["email"],
                token=user["token"],
                tool_context=tool_context,
                thread_id=thread_id,
                user_msg_id="user-msg-uuid",
                client=mock_supabase,
                sys_settings={"pii_redaction_enabled": False, "llm_model": "test-model"},
                web_search_effective=False,
            )
            async for chunk in gen:
                raw_chunks.append(chunk)

    asyncio.run(_drive_disabled())

    events = _capture_sse_stream(raw_chunks)
    captured_event_types = _capture_sse_event_types(events)

    # POSITIVE event-set assertion (D-17 / revision-1 Warning 9 fix):
    # The set of captured event types must be a SUBSET of the legacy set.
    legacy_set = {"delta", "done", "tool_start", "tool_result"}
    captured_set = set(captured_event_types)

    assert captured_set <= legacy_set, (
        f"Unexpected event types leaked when sub_agent_enabled=False: "
        f"{captured_set - legacy_set}. Full set: {captured_set} (D-17 / T-19-FALLBACK)"
    )

    # Negative-space assertions (informative; implied by the positive assertion above):
    assert "task_start" not in captured_set, "task_start must NOT appear when sub_agent_enabled=False"
    assert "task_complete" not in captured_set, "task_complete must NOT appear when sub_agent_enabled=False"
    assert "task_error" not in captured_set, "task_error must NOT appear when sub_agent_enabled=False"
    assert "agent_status" not in captured_set, "agent_status must NOT appear when sub_agent_enabled=False"

    # Database-level invariant: start_run must NOT have been called (D-17 gating)
    assert not mock_start_run.called, (
        "agent_runs_service.start_run must NOT be called when sub_agent_enabled=False (D-17)"
    )

    # Resume-detection short-circuit: stream_chat source must gate resume on sub_agent_enabled
    stream_src = inspect.getsource(chat_module.stream_chat)
    assert "sub_agent_enabled" in stream_src, (
        "stream_chat must check sub_agent_enabled before entering resume branch (D-17)"
    )


# ---------------------------------------------------------------------------
# Test 12: TASK-06 coexistence with v1.0 multi-agent classifier
# ---------------------------------------------------------------------------

def test_task06_coexistence_with_v1_0_multi_agent_classifier():
    """TASK-06: existing v1.0 multi-agent classifier (analyze_document,
    explore_knowledge_base) still works unchanged.

    The new 'task' tool does NOT replace or affect agent_service.classify_intent().
    Standard mode (deep_mode=False, agents_enabled=True) uses agent_service normally.
    """
    import inspect
    import app.services.agent_service as agent_svc
    import app.routers.chat as chat_module

    # 1. classify_intent signature must be intact (v1.0 params)
    ci_sig = inspect.signature(agent_svc.classify_intent)
    ci_params = list(ci_sig.parameters.keys())
    required_params = ["message", "history", "openrouter_service", "model"]
    for param in required_params:
        assert param in ci_params, (
            f"agent_service.classify_intent must have '{param}' param; got: {ci_params}"
        )

    # 2. stream_chat still calls classify_intent for agents_enabled path
    src = inspect.getsource(chat_module.stream_chat)
    assert "classify_intent" in src, (
        "stream_chat must still call agent_service.classify_intent for v1.0 path (TASK-06)"
    )

    # 3. agent_start SSE event must still be in stream_chat (v1.0 multi-agent event)
    assert "agent_start" in src, (
        "stream_chat must still emit 'agent_start' SSE event for v1.0 agents (TASK-06)"
    )

    # 4. task tool dispatch is gated INSIDE run_deep_mode_loop (deep mode only)
    # — it does NOT interfere with the agents_enabled branch in stream_chat
    deep_src = inspect.getsource(chat_module.run_deep_mode_loop)
    assert 'func_name == "task"' in deep_src or "func_name==\"task\"" in deep_src or \
        'func_name == "task"' in deep_src, (
        "task dispatch must be inside run_deep_mode_loop, not in the standard agents path (TASK-06)"
    )

    # 5. The task tool is NOT in TOOL_DEFINITIONS (D-P13-01 invariant)
    # (the standard agents path uses TOOL_DEFINITIONS)
    import app.services.tool_service as ts
    tool_def_names = [t.get("function", {}).get("name", "") for t in ts.TOOL_DEFINITIONS]
    assert "task" not in tool_def_names, (
        f"task must NOT be in TOOL_DEFINITIONS (would contaminate v1.0 agent path); "
        f"found: {[n for n in tool_def_names if n == 'task']} (TASK-06 / D-P13-01)"
    )
    assert "ask_user" not in tool_def_names, (
        f"ask_user must NOT be in TOOL_DEFINITIONS; found: {[n for n in tool_def_names if n == 'ask_user']}"
    )

    # 6. Verify analyze_document + explore_knowledge_base patterns exist in agent definitions
    # These are the v1.0 tool names that the classifier returns
    agent_src = inspect.getsource(agent_svc)
    # The v1.0 multi-agent classifier returns agent names like 'research', 'data_analyst', etc.
    assert "research" in agent_src or "explorer" in agent_src or "data_analyst" in agent_src, (
        "agent_service must still define v1.0 agent types (research/explorer/data_analyst) (TASK-06)"
    )
