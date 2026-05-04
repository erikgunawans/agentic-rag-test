"""Phase 21 / Plan 21-06 — End-to-end Phase 21 smoke harness tests.

Drives the full 4-phase smoke harness pipeline and verifies that the
HIL pause-resume-batch flow works through both the engine directly and the
chat.py HIL resume branch (Plan 21-04). Covers all 11 Phase 21 requirements
(BATCH-01..07 + HIL-01..04) end-to-end.

9 tests:
1. test_smoke_harness_has_4_phases — definition shape (4 phases, types match).
2. test_phase1_echo_writes_synthetic_items_file — Phase 1 dual write (echo.md + test-items.md).
3. test_smoke_e2e_runs_through_phase_3_and_pauses — phases 0..2 then EVT_HUMAN_INPUT_REQUIRED + EVT_COMPLETE{paused}.
4. test_smoke_e2e_resume_writes_answer — start_phase_index=3 skips phases 0..2.
5. test_smoke_e2e_batch_phase_emits_2_batches — 3 items at batch_size=2 → 2 EVT_BATCH_START + 3 item start/complete.
6. test_smoke_e2e_batch_appends_3_jsonl_lines — 3 append_line calls against test-batch.jsonl.
7. test_smoke_e2e_batch_writes_merged_json — sorted 3-element list at test-batch.json.
8. test_smoke_e2e_full_hil_resume_then_batch — combined invocation: pause → resume → completed.
9. test_router_pipeline_hil_resume_into_batch — WARNING-7 router-level TestClient pipeline test.
"""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.harnesses.types import HarnessDefinition, PhaseDefinition, PhaseType
from app.services.harness_engine import (
    EVT_BATCH_COMPLETE,
    EVT_BATCH_ITEM_COMPLETE,
    EVT_BATCH_ITEM_START,
    EVT_BATCH_START,
    EVT_COMPLETE,
    EVT_HUMAN_INPUT_REQUIRED,
    EVT_PHASE_COMPLETE,
    EVT_PHASE_START,
    run_harness_engine,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _collect(gen) -> list[dict]:
    events: list[dict] = []
    async for ev in gen:
        events.append(ev)
    return events


def _build_smoke_ws_mock(*, items_content: str | None = None, answer_present: bool = False):
    """Stateful WorkspaceService mock that mirrors the real read/write/append
    cycle the smoke harness needs.

    items_content: if provided, returned when test-items.md is read. Default = a
                   3-item JSON array matching SYNTHETIC_BATCH_ITEMS.
    answer_present: if True, test-answer.md is pre-seeded (simulates HIL resume).
    """
    state: dict[str, str] = {}
    state["echo.md"] = "# Smoke Echo — Workspace Snapshot\n\nTotal uploaded files: 0\n"
    state["test-items.md"] = items_content or json.dumps([
        {"index": 0, "label": "alpha"},
        {"index": 1, "label": "beta"},
        {"index": 2, "label": "gamma"},
    ])
    if answer_present:
        state["test-answer.md"] = "Testing label"

    ws_instance = MagicMock()

    async def _read_file(thread_id, file_path):
        if file_path in state:
            return {"ok": True, "content": state[file_path]}
        return {"error": "file_not_found", "file_path": file_path}

    async def _write_text_file(thread_id, file_path, content, source="agent"):
        state[file_path] = content
        return {"ok": True, "operation": "write", "size_bytes": len(content), "file_path": file_path}

    async def _append_line(thread_id, file_path, line):
        existing = state.get(file_path, "")
        new_segment = line if line.endswith("\n") else line + "\n"
        state[file_path] = existing + new_segment
        return {
            "ok": True,
            "operation": "append",
            "size_bytes": len(state[file_path]),
            "file_path": file_path,
        }

    async def _list_files(thread_id):
        return []

    ws_instance.read_file = AsyncMock(side_effect=_read_file)
    ws_instance.write_text_file = AsyncMock(side_effect=_write_text_file)
    ws_instance.append_line = AsyncMock(side_effect=_append_line)
    ws_instance.list_files = AsyncMock(side_effect=_list_files)
    ws_instance._state = state
    return ws_instance


def _patch_engine_basics(ws_mock):
    """Common engine dependency patches.

    NOTE: WorkspaceService is patched at BOTH binding sites — the engine module
    AND the smoke_echo module — because Phase 1's _phase1_echo executor
    instantiates WorkspaceService via its OWN import binding (not the engine's).
    """
    return [
        patch("app.services.harness_engine.agent_todos_service.write_todos", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.advance_phase", AsyncMock(return_value=True)),
        patch("app.services.harness_engine.harness_runs_service.complete", AsyncMock(return_value=True)),
        patch("app.services.harness_engine.harness_runs_service.fail", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.cancel", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.pause", AsyncMock(return_value={"id": "run-1", "status": "paused"})),
        patch("app.services.harness_engine.harness_runs_service.get_run_by_id", AsyncMock(return_value={"status": "running"})),
        patch("app.services.harness_engine.WorkspaceService", return_value=ws_mock),
        patch("app.harnesses.smoke_echo.WorkspaceService", return_value=ws_mock),
    ]


def _enter_all(patches):
    return [p.__enter__() for p in patches]


def _exit_all(patches):
    for p in reversed(patches):
        p.__exit__(None, None, None)


def _make_label_sub_agent_mock():
    """Sub-agent stub that yields one terminal_result containing the item label."""

    async def _mock(**kwargs):
        # Extract item from description
        desc = kwargs.get("description", "")
        marker = "Item to process: "
        label = "echoed"
        if marker in desc:
            try:
                tail = desc.split(marker, 1)[1].strip()
                obj = json.loads(tail)
                if isinstance(obj, dict):
                    label = obj.get("label", "echoed")
            except Exception:
                pass
        yield {"_terminal_result": {"text": label}}

    return _mock


# ---------------------------------------------------------------------------
# Test 1 — definition shape
# ---------------------------------------------------------------------------

def test_smoke_harness_has_4_phases():
    """SMOKE_ECHO must expose 4 phases of types [PROGRAMMATIC, LLM_SINGLE, LLM_HUMAN_INPUT, LLM_BATCH_AGENTS]."""
    from app.harnesses.smoke_echo import SMOKE_ECHO

    assert len(SMOKE_ECHO.phases) == 4
    types = [p.phase_type for p in SMOKE_ECHO.phases]
    assert types == [
        PhaseType.PROGRAMMATIC,
        PhaseType.LLM_SINGLE,
        PhaseType.LLM_HUMAN_INPUT,
        PhaseType.LLM_BATCH_AGENTS,
    ]
    # Phase 3 must target test-answer.md; Phase 4 must target test-batch.json with batch_size=2
    assert SMOKE_ECHO.phases[2].name == "ask-label"
    assert SMOKE_ECHO.phases[2].workspace_output == "test-answer.md"
    assert SMOKE_ECHO.phases[3].name == "batch-process"
    assert SMOKE_ECHO.phases[3].workspace_output == "test-batch.json"
    assert SMOKE_ECHO.phases[3].batch_size == 2
    assert SMOKE_ECHO.phases[3].workspace_inputs == ["test-items.md"]


# ---------------------------------------------------------------------------
# Test 2 — Phase 1 writes test-items.md alongside echo.md
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_phase1_echo_writes_synthetic_items_file():
    """Phase 1 executor must write a 3-element JSON array to test-items.md
    (so Phase 4 batch-process has input). Existing echo.md write is preserved."""
    from app.harnesses.smoke_echo import _phase1_echo

    mock_ws = MagicMock()
    mock_ws.list_files = AsyncMock(return_value=[])
    mock_ws.write_text_file = AsyncMock(return_value={"ok": True})

    with patch("app.harnesses.smoke_echo.WorkspaceService", return_value=mock_ws):
        result = await _phase1_echo(
            inputs={}, token="tok", thread_id="t1", harness_run_id="r1",
        )

    # Executor must have invoked write_text_file at least twice — once for
    # echo.md (engine writes via output["content"]) is OK, but for test-items.md
    # the executor must write it directly.
    write_calls = mock_ws.write_text_file.await_args_list
    paths_written = []
    for call in write_calls:
        args, kwargs = call.args, call.kwargs
        path = args[1] if len(args) > 1 else kwargs.get("file_path")
        paths_written.append(path)
    assert "test-items.md" in paths_written, (
        f"test-items.md not written; saw {paths_written}"
    )

    # Find the test-items.md content and verify it parses as a 3-element JSON array
    items_call = None
    for call in write_calls:
        args, kwargs = call.args, call.kwargs
        path = args[1] if len(args) > 1 else kwargs.get("file_path")
        if path == "test-items.md":
            items_call = call
            break
    assert items_call is not None
    args, kwargs = items_call.args, items_call.kwargs
    content = args[2] if len(args) > 2 else kwargs.get("content")
    parsed = json.loads(content)
    assert isinstance(parsed, list)
    assert len(parsed) == 3
    # Each item must have an index + label so the batch sub-agent can parse
    for i, item in enumerate(parsed):
        assert item.get("index") == i
        assert isinstance(item.get("label"), str)

    # Result should still indicate echo content for the engine to write echo.md
    assert "content" in result


# ---------------------------------------------------------------------------
# Test 3 — drive engine through phases 0..2, expect HIL pause
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_smoke_e2e_runs_through_phase_3_and_pauses():
    from app.harnesses.smoke_echo import SMOKE_ECHO

    # Pre-seeded items match what Phase 1 would write
    ws_mock = _build_smoke_ws_mock()

    # LLM_SINGLE phase 2 returns a parseable EchoSummary
    # LLM_HUMAN_INPUT phase 3 returns a question
    llm_responses = [
        {"content": json.dumps({"echo_count": 0, "summary": "Empty workspace"})},
        {"content": json.dumps({"question": "What label?"})},
    ]
    call_count = {"n": 0}

    async def _llm_side_effect(**kwargs):
        idx = call_count["n"]
        call_count["n"] += 1
        return llm_responses[min(idx, len(llm_responses) - 1)]

    pause_calls = []

    async def _recording_pause(**kwargs):
        pause_calls.append(kwargs)
        return {"id": kwargs.get("run_id"), "status": "paused"}

    patches = _patch_engine_basics(ws_mock)
    patches.append(
        patch("app.services.openrouter_service.OpenRouterService.complete_with_tools", side_effect=_llm_side_effect)
    )
    patches.append(
        patch("app.services.harness_engine.harness_runs_service.pause", _recording_pause)
    )

    _enter_all(patches)
    try:
        events = await _collect(
            run_harness_engine(
                harness=SMOKE_ECHO, harness_run_id="run-3a", thread_id="t-3a",
                user_id="u1", user_email="u@test.com", token="tok",
                registry=None, cancellation_event=asyncio.Event(),
            )
        )
    finally:
        _exit_all(patches)

    types = [e.get("type") for e in events if isinstance(e, dict)]

    # Phase starts: 0, 1, 2 (NOT 3 — paused before reaching batch)
    phase_start_indexes = [
        e["phase_index"] for e in events
        if isinstance(e, dict) and e.get("type") == EVT_PHASE_START
    ]
    assert phase_start_indexes == [0, 1, 2], f"got {phase_start_indexes}"

    # Phase complete: only 0 and 1 (Phase 2 paused — no phase_complete)
    phase_complete_indexes = [
        e["phase_index"] for e in events
        if isinstance(e, dict) and e.get("type") == EVT_PHASE_COMPLETE
    ]
    assert phase_complete_indexes == [0, 1], f"got {phase_complete_indexes}"

    # Exactly one EVT_HUMAN_INPUT_REQUIRED
    assert types.count(EVT_HUMAN_INPUT_REQUIRED) == 1
    # Final EVT_COMPLETE has status='paused'
    complete_evs = [e for e in events if isinstance(e, dict) and e.get("type") == EVT_COMPLETE]
    assert len(complete_evs) == 1
    assert complete_evs[0]["status"] == "paused"

    # pause() called once
    assert len(pause_calls) == 1


# ---------------------------------------------------------------------------
# Test 4 — start_phase_index=3 skips phases 0..2
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_smoke_e2e_resume_writes_answer():
    """Calling run_harness_engine with start_phase_index=3 must skip phases 0..2
    and dispatch only the batch phase."""
    from app.harnesses.smoke_echo import SMOKE_ECHO

    ws_mock = _build_smoke_ws_mock(answer_present=True)

    sub_agent_mock = _make_label_sub_agent_mock()
    patches = _patch_engine_basics(ws_mock)
    patches.append(
        patch("app.services.harness_engine.run_sub_agent_loop", sub_agent_mock)
    )

    _enter_all(patches)
    try:
        events = await _collect(
            run_harness_engine(
                harness=SMOKE_ECHO, harness_run_id="run-4a", thread_id="t-4a",
                user_id="u1", user_email="u@test.com", token="tok",
                registry=None, cancellation_event=asyncio.Event(),
                start_phase_index=3,
            )
        )
    finally:
        _exit_all(patches)

    phase_start_indexes = [
        e["phase_index"] for e in events
        if isinstance(e, dict) and e.get("type") == EVT_PHASE_START
    ]
    # Only phase 3 dispatched
    assert phase_start_indexes == [3], f"got {phase_start_indexes}"

    # Final harness_complete with status='completed'
    complete_evs = [e for e in events if isinstance(e, dict) and e.get("type") == EVT_COMPLETE]
    assert len(complete_evs) == 1
    assert complete_evs[0]["status"] == "completed"


# ---------------------------------------------------------------------------
# Test 5 — batch phase emits 2 EVT_BATCH_START + 3 item start/complete
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_smoke_e2e_batch_phase_emits_2_batches():
    from app.harnesses.smoke_echo import SMOKE_ECHO

    ws_mock = _build_smoke_ws_mock(answer_present=True)

    sub_agent_mock = _make_label_sub_agent_mock()
    patches = _patch_engine_basics(ws_mock)
    patches.append(
        patch("app.services.harness_engine.run_sub_agent_loop", sub_agent_mock)
    )

    _enter_all(patches)
    try:
        events = await _collect(
            run_harness_engine(
                harness=SMOKE_ECHO, harness_run_id="run-5a", thread_id="t-5a",
                user_id="u1", user_email="u@test.com", token="tok",
                registry=None, cancellation_event=asyncio.Event(),
                start_phase_index=3,
            )
        )
    finally:
        _exit_all(patches)

    types = [e.get("type") for e in events if isinstance(e, dict)]
    # 3 items at batch_size=2 → 2 batches: [items 0,1] then [item 2]
    assert types.count(EVT_BATCH_START) == 2
    assert types.count(EVT_BATCH_COMPLETE) == 2
    assert types.count(EVT_BATCH_ITEM_START) == 3
    assert types.count(EVT_BATCH_ITEM_COMPLETE) == 3


# ---------------------------------------------------------------------------
# Test 6 — JSONL append called 3 times against test-batch.jsonl
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_smoke_e2e_batch_appends_3_jsonl_lines():
    from app.harnesses.smoke_echo import SMOKE_ECHO

    ws_mock = _build_smoke_ws_mock(answer_present=True)

    sub_agent_mock = _make_label_sub_agent_mock()
    patches = _patch_engine_basics(ws_mock)
    patches.append(
        patch("app.services.harness_engine.run_sub_agent_loop", sub_agent_mock)
    )

    _enter_all(patches)
    try:
        await _collect(
            run_harness_engine(
                harness=SMOKE_ECHO, harness_run_id="run-6a", thread_id="t-6a",
                user_id="u1", user_email="u@test.com", token="tok",
                registry=None, cancellation_event=asyncio.Event(),
                start_phase_index=3,
            )
        )
    finally:
        _exit_all(patches)

    assert ws_mock.append_line.await_count == 3
    appended_paths = []
    for call in ws_mock.append_line.await_args_list:
        args, kwargs = call.args, call.kwargs
        path = args[1] if len(args) > 1 else kwargs.get("file_path")
        appended_paths.append(path)
    # All against the same JSONL file (stem of test-batch.json → test-batch.jsonl)
    assert appended_paths == ["test-batch.jsonl"] * 3


# ---------------------------------------------------------------------------
# Test 7 — write merged JSON sorted by item_index
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_smoke_e2e_batch_writes_merged_json():
    from app.harnesses.smoke_echo import SMOKE_ECHO

    ws_mock = _build_smoke_ws_mock(answer_present=True)

    sub_agent_mock = _make_label_sub_agent_mock()
    patches = _patch_engine_basics(ws_mock)
    patches.append(
        patch("app.services.harness_engine.run_sub_agent_loop", sub_agent_mock)
    )

    _enter_all(patches)
    try:
        await _collect(
            run_harness_engine(
                harness=SMOKE_ECHO, harness_run_id="run-7a", thread_id="t-7a",
                user_id="u1", user_email="u@test.com", token="tok",
                registry=None, cancellation_event=asyncio.Event(),
                start_phase_index=3,
            )
        )
    finally:
        _exit_all(patches)

    # Find the test-batch.json write (merge pass)
    json_writes = []
    for call in ws_mock.write_text_file.await_args_list:
        args, kwargs = call.args, call.kwargs
        path = args[1] if len(args) > 1 else kwargs.get("file_path")
        if path == "test-batch.json":
            json_writes.append(call)

    assert len(json_writes) >= 1, (
        f"merge write to test-batch.json missing; "
        f"saw paths {[c.args[1] if len(c.args) > 1 else c.kwargs.get('file_path') for c in ws_mock.write_text_file.await_args_list]}"
    )
    merge_call = json_writes[-1]
    args, kwargs = merge_call.args, merge_call.kwargs
    content = args[2] if len(args) > 2 else kwargs.get("content")
    parsed = json.loads(content)
    assert isinstance(parsed, list)
    assert len(parsed) == 3
    # Sorted by item_index
    indexes = [r["item_index"] for r in parsed]
    assert indexes == [0, 1, 2]


# ---------------------------------------------------------------------------
# Test 8 — full pipeline: pause then resume to completion
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_smoke_e2e_full_hil_resume_then_batch():
    """Drive the engine in two passes (pause then resume) and verify the
    combined event log contains the full pipeline observations."""
    from app.harnesses.smoke_echo import SMOKE_ECHO

    ws_mock = _build_smoke_ws_mock()

    # LLM responses for both LLM_SINGLE (phase 1) and LLM_HUMAN_INPUT (phase 2)
    llm_responses = [
        {"content": json.dumps({"echo_count": 0, "summary": "Empty workspace"})},
        {"content": json.dumps({"question": "What label?"})},
    ]
    call_idx = {"n": 0}

    async def _llm_side_effect(**kwargs):
        idx = call_idx["n"]
        call_idx["n"] += 1
        return llm_responses[min(idx, len(llm_responses) - 1)]

    sub_agent_mock = _make_label_sub_agent_mock()

    patches = _patch_engine_basics(ws_mock)
    patches.append(
        patch("app.services.openrouter_service.OpenRouterService.complete_with_tools", side_effect=_llm_side_effect)
    )
    patches.append(
        patch("app.services.harness_engine.run_sub_agent_loop", sub_agent_mock)
    )

    _enter_all(patches)
    try:
        # First pass — phases 0..2, ends paused
        first_events = await _collect(
            run_harness_engine(
                harness=SMOKE_ECHO, harness_run_id="run-8", thread_id="t-8",
                user_id="u1", user_email="u@test.com", token="tok",
                registry=None, cancellation_event=asyncio.Event(),
            )
        )

        # Simulate the HIL resume branch (Plan 21-04): write the answer to workspace
        await ws_mock.write_text_file("t-8", "test-answer.md", "Final label", source="harness")

        # Second pass — start from phase 3 (resume)
        second_events = await _collect(
            run_harness_engine(
                harness=SMOKE_ECHO, harness_run_id="run-8", thread_id="t-8",
                user_id="u1", user_email="u@test.com", token="tok",
                registry=None, cancellation_event=asyncio.Event(),
                start_phase_index=3,
            )
        )
    finally:
        _exit_all(patches)

    all_events = first_events + second_events
    types = [e.get("type") for e in all_events if isinstance(e, dict)]

    # Phase start indexes across both passes: 0, 1, 2 in first pass; 3 only in second
    phase_starts = [
        e["phase_index"] for e in all_events
        if isinstance(e, dict) and e.get("type") == EVT_PHASE_START
    ]
    assert phase_starts == [0, 1, 2, 3], f"got {phase_starts}"

    # Phase complete: 0, 1 (first pass) + 3 (second) = 3 total. Phase 2 paused → no complete event.
    phase_completes = [
        e["phase_index"] for e in all_events
        if isinstance(e, dict) and e.get("type") == EVT_PHASE_COMPLETE
    ]
    assert phase_completes == [0, 1, 3], f"got {phase_completes}"

    # Exactly one EVT_HUMAN_INPUT_REQUIRED (phase 2)
    assert types.count(EVT_HUMAN_INPUT_REQUIRED) == 1
    # 2 EVT_BATCH_START (phase 3)
    assert types.count(EVT_BATCH_START) == 2
    assert types.count(EVT_BATCH_ITEM_START) == 3
    assert types.count(EVT_BATCH_ITEM_COMPLETE) == 3

    # First pass ends paused
    first_completes = [e for e in first_events if isinstance(e, dict) and e.get("type") == EVT_COMPLETE]
    assert len(first_completes) == 1
    assert first_completes[0]["status"] == "paused"

    # Second pass ends completed
    second_completes = [e for e in second_events if isinstance(e, dict) and e.get("type") == EVT_COMPLETE]
    assert len(second_completes) == 1
    assert second_completes[0]["status"] == "completed"


# ---------------------------------------------------------------------------
# Test 9 — Router-level pipeline (WARNING-7 regression)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_router_pipeline_hil_resume_into_batch():
    """Drive the chat router's HIL resume branch via FastAPI TestClient.

    This test exercises chat.py:stream_chat HIL resume branch +
    _resume_harness_engine_sse helper from Plan 21-04 VERBATIM. Only the outer
    boundaries (LLM client, sub_agent_loop, supabase) are mocked.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.routers.chat import router
    from app.dependencies import get_current_user
    from app.harnesses.smoke_echo import SMOKE_ECHO

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "u-1", "email": "u@test.com", "token": "tok-1", "role": "user",
    }

    paused_run = {
        "id": "h-1",
        "thread_id": "t-1",
        "user_id": "u-1",
        "harness_type": "smoke-echo",
        "status": "paused",
        "current_phase": 2,  # ask-label HIL phase
        "phase_results": {},
        "input_file_ids": [],
        "error_detail": None,
        "created_at": "2026-05-04T00:00:00Z",
        "updated_at": "2026-05-04T00:00:01Z",
    }
    resumed_run = dict(paused_run)
    resumed_run["status"] = "running"
    resumed_run["current_phase"] = 3

    ws_mock = _build_smoke_ws_mock(answer_present=False)

    # Capture supabase chain calls (insert messages, thread ownership check)
    captured_inserts: list[dict] = []

    class _Chain:
        def select(self, *a, **kw):
            return self

        def eq(self, *a, **kw):
            return self

        def limit(self, *a, **kw):
            return self

        def order(self, *a, **kw):
            return self

        def maybe_single(self):
            return self

        def insert(self, payload):
            captured_inserts.append(payload)
            return self

        def update(self, *a, **kw):
            return self

        def execute(self):
            return MagicMock(data=[{"id": "thread-1"}])

    mock_client = MagicMock()
    mock_client.table = lambda *a, **kw: _Chain()

    sub_agent_mock = _make_label_sub_agent_mock()

    resume_mock = AsyncMock(return_value=resumed_run)
    advance_mock = AsyncMock()

    with patch("app.routers.chat.get_supabase_client", return_value=mock_client), \
         patch("app.routers.chat.get_supabase_authed_client", return_value=mock_client), \
         patch("app.routers.chat.settings") as mock_settings, \
         patch("app.routers.chat.harness_runs_service.get_active_run", new_callable=AsyncMock, return_value=paused_run), \
         patch("app.routers.chat.harness_runs_service.resume_from_pause", resume_mock), \
         patch("app.routers.chat.harness_runs_service.advance_phase", advance_mock), \
         patch("app.routers.chat.harness_registry.get_harness", return_value=SMOKE_ECHO), \
         patch("app.routers.chat.WorkspaceService", return_value=ws_mock), \
         patch("app.routers.chat._get_or_build_conversation_registry", new_callable=AsyncMock, return_value=None), \
         patch("app.services.harness_engine.WorkspaceService", return_value=ws_mock), \
         patch("app.services.harness_engine.agent_todos_service.write_todos", new_callable=AsyncMock), \
         patch("app.services.harness_engine.harness_runs_service.advance_phase", new_callable=AsyncMock, return_value=True), \
         patch("app.services.harness_engine.harness_runs_service.complete", new_callable=AsyncMock, return_value=True), \
         patch("app.services.harness_engine.harness_runs_service.fail", new_callable=AsyncMock), \
         patch("app.services.harness_engine.harness_runs_service.cancel", new_callable=AsyncMock), \
         patch("app.services.harness_engine.harness_runs_service.pause", new_callable=AsyncMock, return_value={"id": "h-1", "status": "paused"}), \
         patch("app.services.harness_engine.harness_runs_service.get_run_by_id", new_callable=AsyncMock, return_value={"status": "running"}), \
         patch("app.services.harness_engine.run_sub_agent_loop", sub_agent_mock):
        mock_settings.harness_enabled = True
        mock_settings.sub_agent_enabled = False
        mock_settings.deep_mode_enabled = False

        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(
            "/chat/stream",
            json={"thread_id": "t-1", "message": "Test answer 123", "parent_message_id": None},
        )
        body = response.text

    # 7. Asserts
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    # WorkspaceService.write_text_file invoked with HIL answer
    write_calls = ws_mock.write_text_file.await_args_list
    answer_writes = []
    for call in write_calls:
        args, kwargs = call.args, call.kwargs
        path = args[1] if len(args) > 1 else kwargs.get("file_path")
        content = args[2] if len(args) > 2 else kwargs.get("content")
        if path == "test-answer.md":
            answer_writes.append((path, content))
    assert any(c == "Test answer 123" for _, c in answer_writes), (
        f"HIL answer write missing; saw paths {[a[0] for a in answer_writes]}"
    )

    # resume_from_pause awaited once with new_phase_index=3
    resume_mock.assert_awaited_once()
    rp_kwargs = resume_mock.await_args.kwargs
    assert rp_kwargs["new_phase_index"] == 3

    # advance_phase NEVER called (BLOCKER-2 invariant)
    advance_mock.assert_not_awaited()

    # User reply persisted with harness_mode tag
    matches = [
        p for p in captured_inserts
        if p.get("role") == "user"
        and p.get("content") == "Test answer 123"
        and p.get("harness_mode") == "smoke-echo"
    ]
    assert len(matches) >= 1, f"HIL message tagging missing; saw {captured_inserts}"

    # SSE body contains batch events and final completed marker
    assert "harness_batch_start" in body
    assert body.count("harness_batch_item_complete") >= 3
    assert "harness_complete" in body
    assert '"status": "completed"' in body
