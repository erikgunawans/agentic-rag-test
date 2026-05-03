"""Phase 19 / 19-04: Integration tests for the task tool end-to-end wiring.

Tests cover (D-28, D-30, TASK-01..05, TASK-07, STATUS-04, D-P13-01):
1. test_task_tool_registered_when_flags_on: dual-flag registration gating
2. test_task_tool_schema_matches_d28: schema verbatim from D-28
3. test_task_dispatch_emits_task_start_complete: SSE event sequence
4. test_task_dispatch_forwards_nested_events_with_task_id: D-06 tagging
5. test_task_dispatch_returns_structured_error_on_failure: TASK-05/STATUS-04
6. test_task_dispatch_persists_audit_log: D-23 audit log
7. test_task_dispatch_generates_server_side_uuid: server-side task_id
8. test_task_not_registered_in_legacy_TOOL_DEFINITIONS: D-P13-01 invariant

Until plan 19-04 Tasks 2+3 land, all 8 tests fail (RED gate).
"""
from __future__ import annotations

import asyncio
import json
import uuid
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
    s.fuzzy_deanon_mode = "none"
    s.rag_top_k = 5
    s.rag_similarity_threshold = 0.3
    return s


def _make_user():
    return {"id": "user-uuid", "email": "test@test.com", "token": "jwt-token", "role": "user"}


async def _aiter_chunks(items):
    """Return items as an async iterable."""
    for item in items:
        yield item


async def _collect_sse_events(
    mock_settings,
    mock_openrouter,
    stub_sub_gen,
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

    # Stub skill registration and catalog (hit during run_deep_mode_loop setup)
    # register_user_skills is imported lazily inside run_deep_mode_loop, so patch at module level
    async def _noop_register_user_skills(*a, **kw):
        pass

    async def _noop_build_catalog_block(*a, **kw):
        return ""

    all_patches = [
        patch("app.routers.chat.settings", mock_settings),
        patch("app.routers.chat.openrouter_service", mock_openrouter),
        # run_sub_agent_loop is imported at module level in chat.py — patch the name there
        patch("app.routers.chat.run_sub_agent_loop", stub_sub_gen),
        patch("app.routers.chat._persist_round_message", return_value="new-parent-id"),
        patch("app.routers.chat.build_skill_catalog_block", _noop_build_catalog_block),
        patch("app.services.skill_catalog_service.register_user_skills", _noop_register_user_skills),
    ] + (extra_patches or [])

    events = []
    with (
        all_patches[0],
        all_patches[1],
        all_patches[2],
        all_patches[3],
        all_patches[4],
        all_patches[5],
    ):
        # run_deep_mode_loop(messages, user_message, user_id, user_email, token,
        #                    tool_context, thread_id, user_msg_id, client,
        #                    sys_settings, web_search_effective)
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
        )
        async for chunk in gen:
            if chunk.startswith("data: "):
                data_str = chunk[len("data: "):].strip()
                try:
                    events.append(json.loads(data_str))
                except json.JSONDecodeError:
                    pass

    return events


def _build_mock_openrouter(task_description="hello"):
    """Build a mock openrouter that returns one task call then terminal text."""
    task_tool_call = {
        "id": "call-task-1",
        "type": "function",
        "function": {
            "name": "task",
            "arguments": json.dumps({"description": task_description}),
        },
    }
    first_response = {"tool_calls": [task_tool_call], "content": None, "usage": {}}
    second_response = {"tool_calls": [], "content": "All done!", "usage": {}}
    mock_openrouter = MagicMock()
    mock_openrouter.complete_with_tools = AsyncMock(
        side_effect=[first_response, second_response]
    )

    async def _stream():
        yield {"delta": "All done!", "done": False}
        yield {"delta": "", "done": True, "usage": {}}

    mock_openrouter.stream_response = AsyncMock(return_value=_stream())
    return mock_openrouter


# ---------------------------------------------------------------------------
# Test 1: Dual-flag registration gating
# ---------------------------------------------------------------------------

def test_task_tool_registered_when_flags_on():
    """With tool_registry_enabled=True AND sub_agent_enabled=True, task is in registry;
    with either flag off, task is NOT in registry."""
    import app.services.tool_registry as tr
    import app.services.tool_service as ts

    # --- Both flags on: task MUST be registered ---
    mock_settings_on = _make_settings(tool_registry_enabled=True, sub_agent_enabled=True)
    tr._REGISTRY.clear()
    with patch("app.services.tool_service.settings", mock_settings_on):
        ts._register_sub_agent_tools()
    assert "task" in tr._REGISTRY, (
        "task must be in _REGISTRY when tool_registry_enabled=True AND sub_agent_enabled=True"
    )

    # --- sub_agent_enabled=False: task must NOT be registered ---
    mock_settings_no_sub = _make_settings(tool_registry_enabled=True, sub_agent_enabled=False)
    tr._REGISTRY.clear()
    with patch("app.services.tool_service.settings", mock_settings_no_sub):
        ts._register_sub_agent_tools()
    assert "task" not in tr._REGISTRY, (
        "task must NOT be in _REGISTRY when sub_agent_enabled=False"
    )

    # --- tool_registry_enabled=False: task must NOT be registered ---
    mock_settings_no_reg = _make_settings(tool_registry_enabled=False, sub_agent_enabled=True)
    tr._REGISTRY.clear()
    with patch("app.services.tool_service.settings", mock_settings_no_reg):
        ts._register_sub_agent_tools()
    assert "task" not in tr._REGISTRY, (
        "task must NOT be in _REGISTRY when tool_registry_enabled=False"
    )


# ---------------------------------------------------------------------------
# Test 2: Schema matches D-28 verbatim
# ---------------------------------------------------------------------------

def test_task_tool_schema_matches_d28():
    """Registered schema parameters exactly match CONTEXT.md D-28."""
    import app.services.tool_registry as tr
    import app.services.tool_service as ts

    mock_settings = _make_settings(tool_registry_enabled=True, sub_agent_enabled=True)
    tr._REGISTRY.clear()
    with patch("app.services.tool_service.settings", mock_settings):
        ts._register_sub_agent_tools()

    entry = tr._REGISTRY.get("task")
    assert entry is not None, "task must be in _REGISTRY to verify schema"

    # ToolDefinition stores schema as a dict attribute
    schema = entry.schema
    assert schema["type"] == "function"
    fn = schema["function"]
    assert fn["name"] == "task"

    params = fn["parameters"]
    props = params["properties"]

    # description param: required string
    assert "description" in props, "schema must have 'description' parameter"
    assert props["description"]["type"] == "string"
    assert "description" in params["required"], "'description' must be in required list"

    # context_files param: optional array of strings
    assert "context_files" in props, "schema must have 'context_files' parameter"
    cf = props["context_files"]
    assert cf["type"] == "array", "context_files must be array type"
    assert cf["items"]["type"] == "string", "context_files items must be string type"

    # context_files is optional (not in required)
    assert "context_files" not in params.get("required", []), (
        "context_files must be optional (not in required)"
    )


# ---------------------------------------------------------------------------
# Test 3: SSE event sequence: task_start -> task_complete
# ---------------------------------------------------------------------------

def test_task_dispatch_emits_task_start_complete():
    """Stub LLM returns task tool_call; sub-agent returns text 'done';
    parent SSE stream emits task_start{task_id, description} -> task_complete{task_id, result='done'}."""
    import app.services.tool_registry as tr
    import app.services.tool_service as ts

    mock_settings = _make_settings(tool_registry_enabled=True, sub_agent_enabled=True)
    tr._REGISTRY.clear()
    with patch("app.services.tool_service.settings", mock_settings):
        ts._register_sub_agent_tools()

    async def _stub_sub_gen(**kwargs):
        yield {"_terminal_result": {"text": "done"}}

    mock_openrouter = _build_mock_openrouter("hello")

    events = asyncio.run(_collect_sse_events(
        mock_settings=mock_settings,
        mock_openrouter=mock_openrouter,
        stub_sub_gen=_stub_sub_gen,
    ))

    event_types = [e["type"] for e in events if "type" in e]
    assert "task_start" in event_types, f"task_start not in {event_types}"
    assert "task_complete" in event_types, f"task_complete not in {event_types}"

    task_start = next(e for e in events if e.get("type") == "task_start")
    assert task_start["description"] == "hello", (
        f"task_start.description must be 'hello', got: {task_start.get('description')}"
    )
    assert "task_id" in task_start, "task_start must include task_id"
    uuid.UUID(task_start["task_id"])  # must be valid UUID

    task_complete = next(e for e in events if e.get("type") == "task_complete")
    assert task_complete["result"] == "done", (
        f"task_complete.result must be 'done', got: {task_complete.get('result')}"
    )
    assert task_complete["task_id"] == task_start["task_id"], (
        "task_complete.task_id must match task_start.task_id"
    )


# ---------------------------------------------------------------------------
# Test 4: Nested events are tagged with task_id (D-06)
# ---------------------------------------------------------------------------

def test_task_dispatch_forwards_nested_events_with_task_id():
    """Sub-agent yields tool_start event; parent SSE contains the same tool_start
    with task_id field added (D-06 — tagging at wrapper boundary)."""
    import app.services.tool_registry as tr
    import app.services.tool_service as ts

    mock_settings = _make_settings(tool_registry_enabled=True, sub_agent_enabled=True)
    tr._REGISTRY.clear()
    with patch("app.services.tool_service.settings", mock_settings):
        ts._register_sub_agent_tools()

    async def _stub_sub_gen(**kwargs):
        # Sub-agent yields a nested tool_start event, then terminal result
        yield {"type": "tool_start", "tool": "read_file"}
        yield {"_terminal_result": {"text": "nested done"}}

    task_tool_call = {
        "id": "call-task-nested",
        "type": "function",
        "function": {
            "name": "task",
            "arguments": json.dumps({"description": "nested test"}),
        },
    }
    first_response = {"tool_calls": [task_tool_call], "content": None, "usage": {}}
    second_response = {"tool_calls": [], "content": "ok", "usage": {}}
    mock_openrouter = MagicMock()
    mock_openrouter.complete_with_tools = AsyncMock(
        side_effect=[first_response, second_response]
    )

    async def _stream():
        yield {"delta": "ok", "done": False}
        yield {"delta": "", "done": True, "usage": {}}

    mock_openrouter.stream_response = AsyncMock(return_value=_stream())

    events = asyncio.run(_collect_sse_events(
        mock_settings=mock_settings,
        mock_openrouter=mock_openrouter,
        stub_sub_gen=_stub_sub_gen,
    ))

    # Find forwarded tool_start from sub-agent (must have task_id tag)
    tagged_tool_starts = [
        e for e in events
        if e.get("type") == "tool_start"
        and e.get("tool") == "read_file"
        and "task_id" in e
    ]
    assert len(tagged_tool_starts) >= 1, (
        f"Expected forwarded tool_start with task_id; got events: {events}"
    )
    uuid.UUID(tagged_tool_starts[0]["task_id"])  # must be valid UUID


# ---------------------------------------------------------------------------
# Test 5: Failure isolation returns structured error (TASK-05 / STATUS-04)
# ---------------------------------------------------------------------------

def test_task_dispatch_returns_structured_error_on_failure():
    """Sub-agent yields _terminal_result with 'error' key;
    parent emits task_error SSE; parent's tool_result carries the structured error."""
    import app.services.tool_registry as tr
    import app.services.tool_service as ts

    mock_settings = _make_settings(tool_registry_enabled=True, sub_agent_enabled=True)
    tr._REGISTRY.clear()
    with patch("app.services.tool_service.settings", mock_settings):
        ts._register_sub_agent_tools()

    async def _stub_sub_gen(**kwargs):
        yield {"_terminal_result": {
            "error": "sub_agent_failed",
            "code": "TASK_LOOP_CRASH",
            "detail": "something went wrong",
        }}

    task_tool_call = {
        "id": "call-task-err",
        "type": "function",
        "function": {
            "name": "task",
            "arguments": json.dumps({"description": "fail test"}),
        },
    }
    first_response = {"tool_calls": [task_tool_call], "content": None, "usage": {}}
    second_response = {"tool_calls": [], "content": "recovered", "usage": {}}
    mock_openrouter = MagicMock()
    mock_openrouter.complete_with_tools = AsyncMock(
        side_effect=[first_response, second_response]
    )

    async def _stream():
        yield {"delta": "recovered", "done": False}
        yield {"delta": "", "done": True, "usage": {}}

    mock_openrouter.stream_response = AsyncMock(return_value=_stream())

    events = asyncio.run(_collect_sse_events(
        mock_settings=mock_settings,
        mock_openrouter=mock_openrouter,
        stub_sub_gen=_stub_sub_gen,
    ))

    event_types = [e["type"] for e in events if "type" in e]
    assert "task_error" in event_types, f"task_error not in event_types: {event_types}"
    assert "task_start" in event_types, "task_start must precede task_error"

    task_error = next(e for e in events if e.get("type") == "task_error")
    assert task_error.get("error") == "sub_agent_failed", (
        f"task_error.error must be 'sub_agent_failed', got: {task_error.get('error')}"
    )
    assert "task_id" in task_error, "task_error must include task_id"
    uuid.UUID(task_error["task_id"])  # must be valid UUID


# ---------------------------------------------------------------------------
# Test 6: Audit log written on dispatch (D-23)
# ---------------------------------------------------------------------------

def test_task_dispatch_persists_audit_log():
    """After task dispatch, audit_service.log_action is called with
    action='task', resource_type='agent_runs', resource_id=thread_id."""
    import app.services.tool_registry as tr
    import app.services.tool_service as ts

    mock_settings = _make_settings(tool_registry_enabled=True, sub_agent_enabled=True)
    tr._REGISTRY.clear()
    with patch("app.services.tool_service.settings", mock_settings):
        ts._register_sub_agent_tools()

    async def _stub_sub_gen(**kwargs):
        yield {"_terminal_result": {"text": "audit test done"}}

    mock_openrouter = _build_mock_openrouter("audit check")
    mock_log_action = MagicMock()

    # log_action is imported directly in chat.py: `from app.services.audit_service import log_action`
    with patch("app.routers.chat.log_action", mock_log_action):
        asyncio.run(_collect_sse_events(
            mock_settings=mock_settings,
            mock_openrouter=mock_openrouter,
            stub_sub_gen=_stub_sub_gen,
        ))

    # Verify log_action was called with action="task" and resource_type="agent_runs"
    calls = mock_log_action.call_args_list
    task_audit_calls = [
        c for c in calls
        if (c.kwargs.get("action") == "task")
        or (len(c.args) >= 3 and c.args[2] == "task")
    ]
    assert len(task_audit_calls) >= 1, (
        f"log_action must be called with action='task'; "
        f"all calls were: {[str(c) for c in calls]}"
    )
    # Verify resource_type is agent_runs
    call = task_audit_calls[0]
    resource_type = call.kwargs.get("resource_type") or (
        call.args[3] if len(call.args) > 3 else None
    )
    assert resource_type == "agent_runs", (
        f"resource_type must be 'agent_runs', got: {resource_type}"
    )


# ---------------------------------------------------------------------------
# Test 7: task_id is server-generated UUID (not LLM-controlled)
# ---------------------------------------------------------------------------

def test_task_dispatch_generates_server_side_uuid():
    """task_id in SSE events is a valid UUID string generated server-side.
    The LLM does not pass task_id — it comes from the dispatcher (Discretion default)."""
    import app.services.tool_registry as tr
    import app.services.tool_service as ts

    mock_settings = _make_settings(tool_registry_enabled=True, sub_agent_enabled=True)
    tr._REGISTRY.clear()
    with patch("app.services.tool_service.settings", mock_settings):
        ts._register_sub_agent_tools()

    async def _stub_sub_gen(**kwargs):
        yield {"_terminal_result": {"text": "uuid test"}}

    mock_openrouter = _build_mock_openrouter("uuid server test")

    events = asyncio.run(_collect_sse_events(
        mock_settings=mock_settings,
        mock_openrouter=mock_openrouter,
        stub_sub_gen=_stub_sub_gen,
    ))

    task_start_events = [e for e in events if e.get("type") == "task_start"]
    assert len(task_start_events) >= 1, "task_start event must be emitted"

    task_id = task_start_events[0]["task_id"]
    # Must be a valid UUID string
    parsed = uuid.UUID(task_id)
    assert str(parsed) == task_id, f"task_id '{task_id}' must be a valid UUID string"
    # Must NOT be the LLM's tool call id (which would mean LLM controlled it)
    assert task_id != "call-task-1", "task_id must not equal the LLM tool call id"


# ---------------------------------------------------------------------------
# Test 8: task NOT in legacy TOOL_DEFINITIONS (D-P13-01 invariant)
# ---------------------------------------------------------------------------

def test_task_not_registered_in_legacy_TOOL_DEFINITIONS():
    """task must NOT appear in tool_service.TOOL_DEFINITIONS.
    It registers exclusively via adapter-wrap in _register_sub_agent_tools() (D-P13-01)."""
    from app.services.tool_service import TOOL_DEFINITIONS
    tool_names = [t["function"]["name"] for t in TOOL_DEFINITIONS]
    assert "task" not in tool_names, (
        "task must NOT be in TOOL_DEFINITIONS — registered exclusively via "
        "_register_sub_agent_tools() adapter-wrap (D-P13-01 invariant)"
    )
