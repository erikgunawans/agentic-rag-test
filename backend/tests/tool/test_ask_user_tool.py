"""Phase 19 / 19-05: Integration tests for the ask_user tool end-to-end wiring.

Tests cover (D-29, D-30, ASK-01..04, D-01, D-04, D-15, D-23, D-P13-01):
1. test_ask_user_registered_when_flags_on: dual-flag registration gating
2. test_ask_user_schema_matches_d29: schema verbatim from D-29
3. test_ask_user_pause_emits_sse: pause flow emits agent_status + ask_user + done
4. test_ask_user_dispatch_persists_audit_log: D-23 audit log with action="ask_user"
5. test_ask_user_pause_does_not_persist_messages_row: D-15 — persisted state is agent_runs, not messages row
6. test_ask_user_not_in_legacy_TOOL_DEFINITIONS: D-P13-01 adapter-wrap invariant

Until plan 19-05 Task 3 lands, all 6 tests fail (RED gate).
"""
from __future__ import annotations

import asyncio
import json
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


async def _collect_sse_events(
    mock_settings,
    mock_openrouter,
    extra_patches=None,
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
    ] + (extra_patches or [])

    events = []
    # Use dynamic context manager expansion for variable-length patches
    import contextlib

    async def _run():
        with contextlib.ExitStack() as stack:
            for p in all_patches:
                stack.enter_context(p)
            gen = run_deep_mode_loop(
                messages=[],
                user_message="what should I do?",
                user_id=user["id"],
                user_email=user["email"],
                token=user["token"],
                tool_context=tool_context,
                thread_id=thread_id,
                user_msg_id=user_msg_id,
                client=mock_supabase,
                sys_settings={"pii_redaction_enabled": False, "llm_model": "test-model"},
                web_search_effective=False,
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


def _build_mock_openrouter_ask_user(question="confirm?"):
    """Build a mock openrouter that returns one ask_user tool call."""
    ask_user_tool_call = {
        "id": "call-ask-user-1",
        "type": "function",
        "function": {
            "name": "ask_user",
            "arguments": json.dumps({"question": question}),
        },
    }
    first_response = {"tool_calls": [ask_user_tool_call], "content": None, "usage": {}}
    mock_openrouter = MagicMock()
    # Only one response — loop should return after ask_user pause
    mock_openrouter.complete_with_tools = AsyncMock(return_value=first_response)

    async def _stream():
        yield {"delta": "", "done": True, "usage": {}}

    mock_openrouter.stream_response = AsyncMock(return_value=_stream())
    return mock_openrouter


# ---------------------------------------------------------------------------
# Test 1: Dual-flag registration gating (ASK-01)
# ---------------------------------------------------------------------------

def test_ask_user_registered_when_flags_on():
    """With tool_registry_enabled=True AND sub_agent_enabled=True, ask_user is in registry;
    with either flag off, ask_user is NOT in registry."""
    import app.services.tool_registry as tr
    import app.services.tool_service as ts

    # --- Both flags on: ask_user MUST be registered ---
    mock_settings_on = _make_settings(tool_registry_enabled=True, sub_agent_enabled=True)
    tr._REGISTRY.clear()
    with patch("app.services.tool_service.settings", mock_settings_on):
        ts._register_sub_agent_tools()
    assert "ask_user" in tr._REGISTRY, (
        "ask_user must be in _REGISTRY when tool_registry_enabled=True AND sub_agent_enabled=True"
    )

    # --- sub_agent_enabled=False: ask_user must NOT be registered ---
    mock_settings_no_sub = _make_settings(tool_registry_enabled=True, sub_agent_enabled=False)
    tr._REGISTRY.clear()
    with patch("app.services.tool_service.settings", mock_settings_no_sub):
        ts._register_sub_agent_tools()
    assert "ask_user" not in tr._REGISTRY, (
        "ask_user must NOT be in _REGISTRY when sub_agent_enabled=False"
    )

    # --- tool_registry_enabled=False: ask_user must NOT be registered ---
    mock_settings_no_reg = _make_settings(tool_registry_enabled=False, sub_agent_enabled=True)
    tr._REGISTRY.clear()
    with patch("app.services.tool_service.settings", mock_settings_no_reg):
        ts._register_sub_agent_tools()
    assert "ask_user" not in tr._REGISTRY, (
        "ask_user must NOT be in _REGISTRY when tool_registry_enabled=False"
    )


# ---------------------------------------------------------------------------
# Test 2: Schema matches D-29 verbatim
# ---------------------------------------------------------------------------

def test_ask_user_schema_matches_d29():
    """Registered schema parameters exactly match CONTEXT.md D-29."""
    import app.services.tool_registry as tr
    import app.services.tool_service as ts

    mock_settings = _make_settings(tool_registry_enabled=True, sub_agent_enabled=True)
    tr._REGISTRY.clear()
    with patch("app.services.tool_service.settings", mock_settings):
        ts._register_sub_agent_tools()

    entry = tr._REGISTRY.get("ask_user")
    assert entry is not None, "ask_user must be in _REGISTRY to verify schema"

    schema = entry.schema
    assert schema["type"] == "function"
    fn = schema["function"]
    assert fn["name"] == "ask_user"

    params = fn["parameters"]
    props = params["properties"]

    # question param: required string
    assert "question" in props, "schema must have 'question' parameter"
    assert props["question"]["type"] == "string"
    assert "question" in params["required"], "'question' must be in required list"

    # Only 'question' in parameters (no extra fields per D-29)
    assert len(props) == 1, f"D-29 schema has exactly 1 parameter, got: {list(props.keys())}"


# ---------------------------------------------------------------------------
# Test 3: Pause flow emits agent_status + ask_user + done (ASK-02, D-01, D-16)
# ---------------------------------------------------------------------------

def test_ask_user_pause_emits_sse():
    """Stub LLM returns one ask_user tool call; loop emits:
      agent_status{status:'waiting_for_user', detail:'confirm?'}
      ask_user{question:'confirm?'}
      delta{done:true}
    then returns (generator closes). agent_runs row persists with
    status='waiting_for_user', pending_question='confirm?'."""
    import app.services.tool_registry as tr
    import app.services.tool_service as ts

    mock_settings = _make_settings(tool_registry_enabled=True, sub_agent_enabled=True)
    tr._REGISTRY.clear()
    with patch("app.services.tool_service.settings", mock_settings):
        ts._register_sub_agent_tools()

    mock_openrouter = _build_mock_openrouter_ask_user("confirm?")

    # Mock agent_runs_service methods
    mock_active_run = {
        "id": "run-uuid",
        "thread_id": "thread-test-uuid",
        "status": "waiting_for_user",
        "pending_question": "confirm?",
        "last_round_index": 0,
        "error_detail": None,
    }
    mock_start_run = AsyncMock(return_value={
        "id": "run-uuid",
        "thread_id": "thread-test-uuid",
        "status": "working",
        "pending_question": None,
        "last_round_index": 0,
        "error_detail": None,
    })
    mock_get_active_run = AsyncMock(return_value=None)  # No prior run at loop start
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

    # Must emit agent_status with waiting_for_user
    agent_status_events = [e for e in events if e.get("type") == "agent_status"]
    waiting_events = [e for e in agent_status_events if e.get("status") == "waiting_for_user"]
    assert len(waiting_events) >= 1, (
        f"Expected agent_status{{status:'waiting_for_user'}} SSE; got event_types: {event_types}"
    )
    waiting_evt = waiting_events[0]
    assert waiting_evt.get("detail") == "confirm?", (
        f"agent_status.detail must be the question 'confirm?'; got: {waiting_evt.get('detail')}"
    )

    # Must emit ask_user event
    ask_user_events = [e for e in events if e.get("type") == "ask_user"]
    assert len(ask_user_events) >= 1, (
        f"Expected ask_user SSE event; got event_types: {event_types}"
    )
    assert ask_user_events[0].get("question") == "confirm?", (
        f"ask_user.question must be 'confirm?'; got: {ask_user_events[0].get('question')}"
    )

    # Must emit done=True
    done_events = [e for e in events if e.get("done") is True]
    assert len(done_events) >= 1, f"Expected delta{{done:True}} SSE; got event_types: {event_types}"

    # set_pending_question must have been called (persists waiting_for_user state)
    assert mock_set_pending.called, "agent_runs_service.set_pending_question must be called on ask_user pause"
    call_kwargs = mock_set_pending.call_args
    # Check question was passed
    question_arg = call_kwargs.kwargs.get("question") or (call_kwargs.args[1] if len(call_kwargs.args) > 1 else None)
    assert question_arg == "confirm?", f"set_pending_question called with question={question_arg!r}, expected 'confirm?'"


# ---------------------------------------------------------------------------
# Test 4: Audit log written (D-23)
# ---------------------------------------------------------------------------

def test_ask_user_dispatch_persists_audit_log():
    """After ask_user dispatch, log_action is called with
    action='ask_user', resource_type='agent_runs'."""
    import app.services.tool_registry as tr
    import app.services.tool_service as ts

    mock_settings = _make_settings(tool_registry_enabled=True, sub_agent_enabled=True)
    tr._REGISTRY.clear()
    with patch("app.services.tool_service.settings", mock_settings):
        ts._register_sub_agent_tools()

    mock_openrouter = _build_mock_openrouter_ask_user("audit test question")
    mock_log_action = MagicMock()

    mock_start_run = AsyncMock(return_value={
        "id": "run-uuid", "thread_id": "thread-test-uuid",
        "status": "working", "pending_question": None,
        "last_round_index": 0, "error_detail": None,
    })
    mock_get_active_run = AsyncMock(return_value=None)
    mock_set_pending = AsyncMock(return_value=None)

    extra_patches = [
        patch("app.routers.chat.log_action", mock_log_action),
        patch("app.routers.chat.agent_runs_service.start_run", mock_start_run),
        patch("app.routers.chat.agent_runs_service.get_active_run", mock_get_active_run),
        patch("app.routers.chat.agent_runs_service.set_pending_question", mock_set_pending),
    ]

    asyncio.run(_collect_sse_events(
        mock_settings=mock_settings,
        mock_openrouter=mock_openrouter,
        extra_patches=extra_patches,
    ))

    calls = mock_log_action.call_args_list
    ask_user_audit_calls = [
        c for c in calls
        if (c.kwargs.get("action") == "ask_user")
        or (len(c.args) >= 3 and c.args[2] == "ask_user")
    ]
    assert len(ask_user_audit_calls) >= 1, (
        f"log_action must be called with action='ask_user'; "
        f"all calls were: {[str(c) for c in calls]}"
    )
    call = ask_user_audit_calls[0]
    resource_type = call.kwargs.get("resource_type") or (
        call.args[3] if len(call.args) > 3 else None
    )
    assert resource_type == "agent_runs", (
        f"resource_type must be 'agent_runs', got: {resource_type}"
    )


# ---------------------------------------------------------------------------
# Test 5: ask_user pause does NOT persist a tool_result messages row (D-15)
# ---------------------------------------------------------------------------

def test_ask_user_pause_does_not_persist_messages_row():
    """D-15: persisted state for ask_user pause is agent_runs.last_round_index,
    NOT a tool_result messages row. _persist_round_message is called for the
    assistant round (with the ask_user tool_call), but NOT with a tool_result
    for the ask_user call (the user reply will fill it on resume).

    Specifically: the loop must RETURN (generator exhausted) immediately after
    emitting ask_user SSE, before calling _persist_round_message with the
    ask_user tool_result. The only _persist_round_message call allowed is for
    the assistant message row that contains the tool_call itself."""
    import app.services.tool_registry as tr
    import app.services.tool_service as ts

    mock_settings = _make_settings(tool_registry_enabled=True, sub_agent_enabled=True)
    tr._REGISTRY.clear()
    with patch("app.services.tool_service.settings", mock_settings):
        ts._register_sub_agent_tools()

    mock_openrouter = _build_mock_openrouter_ask_user("pause check?")
    mock_persist = MagicMock(return_value="new-parent-id")

    mock_start_run = AsyncMock(return_value={
        "id": "run-uuid", "thread_id": "thread-test-uuid",
        "status": "working", "pending_question": None,
        "last_round_index": 0, "error_detail": None,
    })
    mock_get_active_run = AsyncMock(return_value=None)
    mock_set_pending = AsyncMock(return_value=None)

    extra_patches = [
        patch("app.routers.chat._persist_round_message", mock_persist),
        patch("app.routers.chat.agent_runs_service.start_run", mock_start_run),
        patch("app.routers.chat.agent_runs_service.get_active_run", mock_get_active_run),
        patch("app.routers.chat.agent_runs_service.set_pending_question", mock_set_pending),
    ]

    asyncio.run(_collect_sse_events(
        mock_settings=mock_settings,
        mock_openrouter=mock_openrouter,
        # Note: must NOT patch _persist_round_message via all_patches (it's already in base patches)
        # so we override it via extra_patches
        extra_patches=extra_patches,
    ))

    # The ask_user dispatch handler must RETURN before _persist_round_message is
    # called with a tool_result for the ask_user call.
    # Accept: 0 calls (return before persist) OR 1 call (assistant row only, no tool_result row)
    # Reject: any call that looks like it's persisting a tool_result for ask_user
    for call in mock_persist.call_args_list:
        tool_records = call.kwargs.get("tool_records") or (
            call.args[5] if len(call.args) > 5 else []
        )
        if tool_records:
            for rec in tool_records:
                tool_name = getattr(rec, "tool", None) or (rec.get("tool") if isinstance(rec, dict) else None)
                assert tool_name != "ask_user", (
                    "D-15 violation: _persist_round_message called with ask_user tool_result. "
                    "The ask_user pause must return before persisting the tool_result row."
                )


# ---------------------------------------------------------------------------
# Test 6: ask_user NOT in legacy TOOL_DEFINITIONS (D-P13-01 invariant)
# ---------------------------------------------------------------------------

def test_ask_user_not_in_legacy_TOOL_DEFINITIONS():
    """ask_user must NOT appear in tool_service.TOOL_DEFINITIONS.
    It registers exclusively via adapter-wrap in _register_sub_agent_tools() (D-P13-01)."""
    from app.services.tool_service import TOOL_DEFINITIONS
    tool_names = [t["function"]["name"] for t in TOOL_DEFINITIONS]
    assert "ask_user" not in tool_names, (
        "ask_user must NOT be in TOOL_DEFINITIONS — registered exclusively via "
        "_register_sub_agent_tools() adapter-wrap (D-P13-01 invariant)"
    )
