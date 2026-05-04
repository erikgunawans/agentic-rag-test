"""Phase 21 / Plan 21-03 — Tests for LLM_BATCH_AGENTS dispatch.

8 tests covering BATCH-01..07 + tool-curation inheritance (BLOCKER-6 fix):
  1. test_batch_concurrent_dispatch          — N items at batch_size=N → 2 batches; per-item events
  2. test_batch_jsonl_append_per_item        — append_line called once per item with item_index + status
  3. test_batch_resume_skips_done_items      — JSONL pre-seed with status=ok rows; only remaining items dispatched
  4. test_batch_resume_skips_failed_items    — JSONL pre-seed with status=failed; failed items NOT retried
  5. test_batch_failure_marker_continues     — one item raises; failure marker written, batch continues
  6. test_batch_merge_pass_sorted            — out-of-order JSONL → sorted final JSON array
  7. test_batch_item_index_globally_unique   — 7 items at batch_size=3; item_index spans 0..6 (no per-batch reset)
  8. test_batch_sub_agent_inherits_phase_tools_curation — BLOCKER-6 regression: curated tools pass via parent_tool_context
"""
from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.harnesses.types import (
    HarnessDefinition,
    HarnessPrerequisites,
    PhaseDefinition,
    PhaseType,
)
from app.services.harness_engine import (
    EVT_BATCH_COMPLETE,
    EVT_BATCH_ITEM_COMPLETE,
    EVT_BATCH_ITEM_START,
    EVT_BATCH_START,
    EVT_COMPLETE,
    EVT_PHASE_COMPLETE,
    EVT_PHASE_START,
    run_harness_engine,
)


def _make_prereqs() -> HarnessPrerequisites:
    return HarnessPrerequisites(harness_intro="test harness")


async def _collect(gen) -> list[dict]:
    events = []
    async for ev in gen:
        events.append(ev)
    return events


def _make_batch_phase(
    *,
    name: str = "batch-process",
    workspace_inputs: list[str] | None = None,
    workspace_output: str = "results.json",
    batch_size: int = 5,
    tools: list[str] | None = None,
    timeout_seconds: int = 600,
) -> PhaseDefinition:
    return PhaseDefinition(
        name=name,
        phase_type=PhaseType.LLM_BATCH_AGENTS,
        system_prompt_template="Process this item.",
        tools=tools or [],
        workspace_inputs=workspace_inputs or ["items.json"],
        workspace_output=workspace_output,
        batch_size=batch_size,
        timeout_seconds=timeout_seconds,
    )


def _build_ws_mock(*, items: list, jsonl_state: dict[str, str] | None = None):
    """Create a mock WorkspaceService instance.

    items: list of items to be returned when reading the workspace_inputs[0] file
    jsonl_state: optional dict mapping jsonl_path -> existing content (for resume)

    The mock is stateful: append_line updates a tracking dict that subsequent
    read_file calls reflect.
    """
    ws_instance = MagicMock()
    state: dict[str, str] = dict(jsonl_state or {})
    items_content = json.dumps(items)

    async def _read_file(thread_id, file_path):
        # workspace_inputs[0] = items file
        if file_path.endswith(".json") and file_path not in state and "items" in file_path:
            return {"ok": True, "content": items_content}
        # Pre-seeded JSONL
        if file_path in state:
            return {"ok": True, "content": state[file_path]}
        # Default fallback (e.g., progress.md, missing JSONL)
        if file_path.endswith(".jsonl"):
            return {"error": "file_not_found", "file_path": file_path}
        return {"ok": True, "content": ""}

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

    ws_instance.read_file = AsyncMock(side_effect=_read_file)
    ws_instance.write_text_file = AsyncMock(side_effect=_write_text_file)
    ws_instance.append_line = AsyncMock(side_effect=_append_line)
    ws_instance._state = state  # exposed for test assertions
    return ws_instance


def _make_sub_agent_mock(
    *,
    succeed_indexes: set | None = None,
    fail_indexes: set | None = None,
    raise_indexes: set | None = None,
    captured_calls: list | None = None,
):
    """Build an async generator mock for run_sub_agent_loop.

    Yields one terminal event per call. Behavior keyed by which call number:
    we determine the item_index from the description's "Item to process" suffix.

    Defaults: every call succeeds.
    """
    succeed_indexes = succeed_indexes if succeed_indexes is not None else None
    fail_indexes = fail_indexes or set()
    raise_indexes = raise_indexes or set()

    async def _mock(**kwargs) -> AsyncIterator[dict]:
        if captured_calls is not None:
            captured_calls.append(kwargs)
        desc = kwargs.get("description", "")
        # Parse out item index from description's "Item to process: ..." suffix.
        # The dispatcher embeds JSON of the item; we look for "index" in that.
        idx = None
        marker = "Item to process: "
        if marker in desc:
            try:
                tail = desc.split(marker, 1)[1].strip()
                obj = json.loads(tail)
                if isinstance(obj, dict) and "index" in obj:
                    idx = int(obj["index"])
            except Exception:
                idx = None

        if idx is not None and idx in raise_indexes:
            raise RuntimeError(f"sub_agent_failure_{idx}")

        if idx is not None and idx in fail_indexes:
            yield {"_terminal_result": {
                "error": "sub_agent_failed",
                "code": "SUB_AGENT_FAIL",
                "detail": f"item {idx} failed",
            }}
            return

        yield {"_terminal_result": {"text": f"item-{idx}-result"}}

    return _mock


def _patch_engine(ws_mock, sub_agent_mock):
    """Build the patch context manager set used by every batch test."""
    return [
        patch("app.services.harness_engine.agent_todos_service.write_todos", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.advance_phase", AsyncMock(return_value=True)),
        patch("app.services.harness_engine.harness_runs_service.complete", AsyncMock(return_value=True)),
        patch("app.services.harness_engine.harness_runs_service.fail", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.cancel", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.get_run_by_id", AsyncMock(return_value={"status": "running"})),
        patch("app.services.harness_engine.WorkspaceService", return_value=ws_mock),
        patch("app.services.harness_engine.run_sub_agent_loop", sub_agent_mock),
    ]


def _enter_all(patches):
    return [p.__enter__() for p in patches]


def _exit_all(patches):
    for p in reversed(patches):
        p.__exit__(None, None, None)


# ---------------------------------------------------------------------------
# Test 1 — concurrent dispatch
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_batch_concurrent_dispatch():
    items = [{"index": i} for i in range(6)]
    phase = _make_batch_phase(
        workspace_inputs=["items.json"],
        workspace_output="results.json",
        batch_size=3,
    )
    harness = HarnessDefinition(
        name="h", display_name="H", prerequisites=_make_prereqs(),
        phases=[phase],
    )

    ws_mock = _build_ws_mock(items=items)
    sub_agent_mock = _make_sub_agent_mock()
    patches = _patch_engine(ws_mock, sub_agent_mock)

    _enter_all(patches)
    try:
        events = await _collect(
            run_harness_engine(
                harness=harness, harness_run_id="run-1", thread_id="t1",
                user_id="u1", user_email="u@test.com", token="tok",
                registry=None, cancellation_event=asyncio.Event(),
            )
        )
    finally:
        _exit_all(patches)

    types = [e.get("type") for e in events if isinstance(e, dict)]
    # 2 batches, 6 items
    assert types.count(EVT_BATCH_START) == 2
    assert types.count(EVT_BATCH_ITEM_START) == 6
    assert types.count(EVT_BATCH_ITEM_COMPLETE) == 6
    assert types.count(EVT_BATCH_COMPLETE) == 2


# ---------------------------------------------------------------------------
# Test 2 — JSONL append per item
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_batch_jsonl_append_per_item():
    items = [{"index": i} for i in range(3)]
    phase = _make_batch_phase(workspace_output="results.json", batch_size=3)
    harness = HarnessDefinition(
        name="h", display_name="H", prerequisites=_make_prereqs(),
        phases=[phase],
    )

    ws_mock = _build_ws_mock(items=items)
    sub_agent_mock = _make_sub_agent_mock()
    patches = _patch_engine(ws_mock, sub_agent_mock)

    _enter_all(patches)
    try:
        await _collect(
            run_harness_engine(
                harness=harness, harness_run_id="run-2", thread_id="t2",
                user_id="u1", user_email="u@test.com", token="tok",
                registry=None, cancellation_event=asyncio.Event(),
            )
        )
    finally:
        _exit_all(patches)

    # Exactly 3 append_line calls
    assert ws_mock.append_line.call_count == 3
    # Verify each call payload contains item_index + status, path == .jsonl
    for call in ws_mock.append_line.call_args_list:
        args = call.args
        kwargs = call.kwargs
        path = args[1] if len(args) > 1 else kwargs.get("file_path")
        line = args[2] if len(args) > 2 else kwargs.get("line")
        assert path.endswith(".jsonl"), f"path is not .jsonl: {path}"
        payload = json.loads(line)
        assert "item_index" in payload
        assert payload["status"] in ("ok", "failed")


# ---------------------------------------------------------------------------
# Test 3 — resume skips done (status=ok) items
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_batch_resume_skips_done_items():
    items = [{"index": i} for i in range(4)]
    # Pre-seed JSONL: items 0 and 2 already done (ok)
    seeded_jsonl = (
        json.dumps({"item_index": 0, "status": "ok", "result": {"text": "old"}}) + "\n"
        + json.dumps({"item_index": 2, "status": "ok", "result": {"text": "old"}}) + "\n"
    )

    phase = _make_batch_phase(workspace_output="results.json", batch_size=4)
    harness = HarnessDefinition(
        name="h", display_name="H", prerequisites=_make_prereqs(),
        phases=[phase],
    )

    ws_mock = _build_ws_mock(items=items, jsonl_state={"results.jsonl": seeded_jsonl})
    captured_calls: list = []
    sub_agent_mock = _make_sub_agent_mock(captured_calls=captured_calls)
    patches = _patch_engine(ws_mock, sub_agent_mock)

    _enter_all(patches)
    try:
        await _collect(
            run_harness_engine(
                harness=harness, harness_run_id="run-3", thread_id="t3",
                user_id="u1", user_email="u@test.com", token="tok",
                registry=None, cancellation_event=asyncio.Event(),
            )
        )
    finally:
        _exit_all(patches)

    # Sub-agent invoked exactly 2 times (items 1 and 3)
    assert len(captured_calls) == 2
    # append_line called only for items 1 and 3
    assert ws_mock.append_line.call_count == 2
    appended_indexes = set()
    for call in ws_mock.append_line.call_args_list:
        args = call.args
        line = args[2] if len(args) > 2 else call.kwargs.get("line")
        appended_indexes.add(json.loads(line)["item_index"])
    assert appended_indexes == {1, 3}


# ---------------------------------------------------------------------------
# Test 4 — resume skips failed items (D-12: failed items NOT retried)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_batch_resume_skips_failed_items():
    items = [{"index": i} for i in range(2)]
    # Pre-seed: item 0 is failed; item 1 is fresh
    seeded_jsonl = (
        json.dumps({"item_index": 0, "status": "failed", "error": {"error": "x", "code": "Y"}}) + "\n"
    )

    phase = _make_batch_phase(workspace_output="results.json", batch_size=2)
    harness = HarnessDefinition(
        name="h", display_name="H", prerequisites=_make_prereqs(),
        phases=[phase],
    )

    ws_mock = _build_ws_mock(items=items, jsonl_state={"results.jsonl": seeded_jsonl})
    captured_calls: list = []
    sub_agent_mock = _make_sub_agent_mock(captured_calls=captured_calls)
    patches = _patch_engine(ws_mock, sub_agent_mock)

    _enter_all(patches)
    try:
        await _collect(
            run_harness_engine(
                harness=harness, harness_run_id="run-4", thread_id="t4",
                user_id="u1", user_email="u@test.com", token="tok",
                registry=None, cancellation_event=asyncio.Event(),
            )
        )
    finally:
        _exit_all(patches)

    # Sub-agent invoked exactly 1 time (only item 1)
    assert len(captured_calls) == 1
    # Verify it was item 1
    desc = captured_calls[0]["description"]
    assert '"index": 1' in desc or '"index":1' in desc


# ---------------------------------------------------------------------------
# Test 5 — failure marker continues batch (D-11)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_batch_failure_marker_continues():
    items = [{"index": i} for i in range(3)]

    phase = _make_batch_phase(workspace_output="results.json", batch_size=3)
    harness = HarnessDefinition(
        name="h", display_name="H", prerequisites=_make_prereqs(),
        phases=[phase],
    )

    ws_mock = _build_ws_mock(items=items)
    # Item 1 raises; items 0 and 2 succeed
    sub_agent_mock = _make_sub_agent_mock(raise_indexes={1})
    patches = _patch_engine(ws_mock, sub_agent_mock)

    _enter_all(patches)
    try:
        events = await _collect(
            run_harness_engine(
                harness=harness, harness_run_id="run-5", thread_id="t5",
                user_id="u1", user_email="u@test.com", token="tok",
                registry=None, cancellation_event=asyncio.Event(),
            )
        )
    finally:
        _exit_all(patches)

    # All 3 items appended
    assert ws_mock.append_line.call_count == 3
    payloads = []
    for call in ws_mock.append_line.call_args_list:
        line = call.args[2] if len(call.args) > 2 else call.kwargs.get("line")
        payloads.append(json.loads(line))

    by_index = {p["item_index"]: p for p in payloads}
    assert by_index[1]["status"] == "failed"
    assert "error" in by_index[1]
    assert by_index[0]["status"] == "ok"
    assert by_index[2]["status"] == "ok"

    # harness_batch_complete event includes failed_count: 1 (final batch event)
    batch_complete_evs = [e for e in events if isinstance(e, dict) and e.get("type") == EVT_BATCH_COMPLETE]
    assert any(e.get("failed_count") == 1 for e in batch_complete_evs)


# ---------------------------------------------------------------------------
# Test 6 — merge pass sorted
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_batch_merge_pass_sorted():
    items = [{"index": i} for i in range(4)]

    phase = _make_batch_phase(workspace_output="results.json", batch_size=4)
    harness = HarnessDefinition(
        name="h", display_name="H", prerequisites=_make_prereqs(),
        phases=[phase],
    )

    ws_mock = _build_ws_mock(items=items)
    sub_agent_mock = _make_sub_agent_mock()
    patches = _patch_engine(ws_mock, sub_agent_mock)

    _enter_all(patches)
    try:
        await _collect(
            run_harness_engine(
                harness=harness, harness_run_id="run-6", thread_id="t6",
                user_id="u1", user_email="u@test.com", token="tok",
                registry=None, cancellation_event=asyncio.Event(),
            )
        )
    finally:
        _exit_all(patches)

    # Final merged JSON should exist at results.json — verify write_text_file
    # was called with sorted results.
    json_writes = [
        call for call in ws_mock.write_text_file.call_args_list
        if (call.args[1] if len(call.args) > 1 else call.kwargs.get("file_path")) == "results.json"
    ]
    assert len(json_writes) >= 1, "merge write_text_file to results.json missing"
    # Last call to results.json is the merge pass
    merge_call = json_writes[-1]
    content = merge_call.args[2] if len(merge_call.args) > 2 else merge_call.kwargs.get("content")
    parsed = json.loads(content)
    assert isinstance(parsed, list)
    assert len(parsed) == 4
    indexes = [r["item_index"] for r in parsed]
    assert indexes == [0, 1, 2, 3]


# ---------------------------------------------------------------------------
# Test 7 — item_index globally unique across batches
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_batch_item_index_globally_unique():
    items = [{"index": i} for i in range(7)]

    phase = _make_batch_phase(workspace_output="results.json", batch_size=3)
    harness = HarnessDefinition(
        name="h", display_name="H", prerequisites=_make_prereqs(),
        phases=[phase],
    )

    ws_mock = _build_ws_mock(items=items)
    sub_agent_mock = _make_sub_agent_mock()
    patches = _patch_engine(ws_mock, sub_agent_mock)

    _enter_all(patches)
    try:
        events = await _collect(
            run_harness_engine(
                harness=harness, harness_run_id="run-7", thread_id="t7",
                user_id="u1", user_email="u@test.com", token="tok",
                registry=None, cancellation_event=asyncio.Event(),
            )
        )
    finally:
        _exit_all(patches)

    item_starts = [
        e for e in events
        if isinstance(e, dict) and e.get("type") == EVT_BATCH_ITEM_START
    ]
    indexes = sorted(e["item_index"] for e in item_starts)
    assert indexes == [0, 1, 2, 3, 4, 5, 6], f"got {indexes}"


# ---------------------------------------------------------------------------
# Test 8 — sub-agent inherits phase.tools curation (BLOCKER-6)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_batch_sub_agent_inherits_phase_tools_curation():
    items = [{"index": i} for i in range(2)]

    # phase.tools includes "write_todos" which IS in PANEL_LOCKED_EXCLUDED_TOOLS
    # — it MUST be filtered out. The other two tools must remain.
    phase = _make_batch_phase(
        workspace_output="results.json",
        batch_size=2,
        tools=["search_documents", "query_database", "write_todos"],
    )
    harness = HarnessDefinition(
        name="h", display_name="H", prerequisites=_make_prereqs(),
        phases=[phase],
    )

    ws_mock = _build_ws_mock(items=items)
    captured_calls: list = []
    sub_agent_mock = _make_sub_agent_mock(captured_calls=captured_calls)
    patches = _patch_engine(ws_mock, sub_agent_mock)

    _enter_all(patches)
    try:
        await _collect(
            run_harness_engine(
                harness=harness, harness_run_id="run-8", thread_id="t8",
                user_id="u1", user_email="u@test.com", token="tok",
                registry=None, cancellation_event=asyncio.Event(),
            )
        )
    finally:
        _exit_all(patches)

    # Both items dispatched
    assert len(captured_calls) == 2

    # Each call's parent_tool_context must contain phase_tools with curated list
    for call in captured_calls:
        ctx = call.get("parent_tool_context")
        assert ctx is not None, "parent_tool_context missing"
        assert "phase_tools" in ctx, f"phase_tools missing from {ctx}"
        curated = ctx["phase_tools"]
        # write_todos must be removed; others retained
        assert "write_todos" not in curated
        assert "search_documents" in curated
        assert "query_database" in curated
        assert curated == ["search_documents", "query_database"]

    # Curated list IDENTICAL across calls (computed once per phase)
    all_lists = [tuple(c["parent_tool_context"]["phase_tools"]) for c in captured_calls]
    assert len(set(all_lists)) == 1, "curated list differs across batch items"
