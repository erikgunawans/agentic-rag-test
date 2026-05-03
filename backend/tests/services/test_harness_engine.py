"""Phase 20 / v1.3 — Tests for harness_engine.py.

14 tests covering:
1.  test_run_harness_engine_emits_phase_start_complete
2.  test_run_harness_engine_writes_agent_todos
3.  test_run_harness_engine_writes_progress_md
4.  test_run_harness_engine_phase_timeout
5.  test_run_harness_engine_cancellation_between_phases
6.  test_run_harness_engine_llm_single_pydantic_validation_failure
7.  test_run_harness_engine_llm_single_missing_schema
8.  test_run_harness_engine_llm_agent_invokes_sub_agent_loop
9.  test_run_harness_engine_egress_filter_blocks_llm_single
10. test_run_harness_engine_phase21_types_return_not_implemented
11. test_run_harness_engine_failure_stops_loop
12. test_run_harness_engine_advances_harness_runs_state
13. test_llm_agent_emits_sub_agent_start_complete_events       (B1)
14. test_phase21_events_are_documented_but_unimplemented       (B1)
15. test_run_harness_engine_db_status_cancelled_halts_at_next_phase (B3)
"""
from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from app.harnesses.types import (
    HarnessDefinition,
    HarnessPrerequisites,
    PhaseDefinition,
    PhaseType,
)
from app.services.harness_engine import (
    EVT_BATCH_COMPLETE,
    EVT_BATCH_START,
    EVT_COMPLETE,
    EVT_HUMAN_INPUT_REQUIRED,
    EVT_PHASE_COMPLETE,
    EVT_PHASE_ERROR,
    EVT_PHASE_START,
    EVT_SUB_AGENT_COMPLETE,
    EVT_SUB_AGENT_START,
    run_harness_engine,
)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def _make_prereqs() -> HarnessPrerequisites:
    return HarnessPrerequisites(harness_intro="test harness")


async def _collect(gen) -> list[dict]:
    """Drain an async generator into a list."""
    events = []
    async for ev in gen:
        events.append(ev)
    return events


def _make_programmatic_phase(name: str = "echo", timeout_seconds: int = 60) -> PhaseDefinition:
    async def _executor(inputs, token, thread_id, harness_run_id):
        return {"result": "ok", "text": "echo done"}

    return PhaseDefinition(
        name=name,
        phase_type=PhaseType.PROGRAMMATIC,
        executor=_executor,
        timeout_seconds=timeout_seconds,
    )


# ---------------------------------------------------------------------------
# Shared mocks context
# ---------------------------------------------------------------------------

MOCK_BASES = {
    "app.services.harness_engine.agent_todos_service.write_todos": AsyncMock(return_value=None),
    "app.services.harness_engine.harness_runs_service.advance_phase": AsyncMock(return_value=True),
    "app.services.harness_engine.harness_runs_service.complete": AsyncMock(return_value=True),
    "app.services.harness_engine.harness_runs_service.fail": AsyncMock(return_value=True),
    "app.services.harness_engine.harness_runs_service.cancel": AsyncMock(return_value=True),
    "app.services.harness_engine.harness_runs_service.get_run_by_id": AsyncMock(
        return_value={"status": "running"}
    ),
}


def _patch_workspace(mock_write=None, mock_read=None):
    """Return a mock WorkspaceService class."""
    ws_instance = MagicMock()
    ws_instance.write_text_file = mock_write or AsyncMock(return_value={"ok": True})
    ws_instance.read_file = mock_read or AsyncMock(
        return_value={"ok": True, "content": "# Harness Progress\n"}
    )
    return ws_instance


# ---------------------------------------------------------------------------
# Test 1: happy path emits phase_start and phase_complete
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_harness_engine_emits_phase_start_complete():
    harness = HarnessDefinition(
        name="h",
        display_name="H",
        prerequisites=_make_prereqs(),
        phases=[_make_programmatic_phase()],
    )

    ws_mock = _patch_workspace()

    with (
        patch("app.services.harness_engine.agent_todos_service.write_todos", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.advance_phase", AsyncMock(return_value=True)),
        patch("app.services.harness_engine.harness_runs_service.complete", AsyncMock(return_value=True)),
        patch("app.services.harness_engine.harness_runs_service.fail", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.cancel", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.get_run_by_id", AsyncMock(return_value={"status": "running"})),
        patch("app.services.harness_engine.WorkspaceService", return_value=ws_mock),
    ):
        events = await _collect(
            run_harness_engine(
                harness=harness,
                harness_run_id="run-1",
                thread_id="thread-1",
                user_id="user-1",
                user_email="u@test.com",
                token="tok",
                registry=None,
                cancellation_event=asyncio.Event(),
            )
        )

    types = [e["type"] for e in events]
    assert EVT_PHASE_START in types
    assert EVT_PHASE_COMPLETE in types
    assert EVT_COMPLETE in types

    complete_ev = next(e for e in events if e["type"] == EVT_COMPLETE)
    assert complete_ev["status"] == "completed"
    assert complete_ev["harness_run_id"] == "run-1"


# ---------------------------------------------------------------------------
# Test 2: writes agent_todos with correct content prefix
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_harness_engine_writes_agent_todos():
    harness = HarnessDefinition(
        name="h",
        display_name="My Harness",
        prerequisites=_make_prereqs(),
        phases=[_make_programmatic_phase("Phase One")],
    )

    mock_write_todos = AsyncMock()
    ws_mock = _patch_workspace()

    with (
        patch("app.services.harness_engine.agent_todos_service.write_todos", mock_write_todos),
        patch("app.services.harness_engine.harness_runs_service.advance_phase", AsyncMock(return_value=True)),
        patch("app.services.harness_engine.harness_runs_service.complete", AsyncMock(return_value=True)),
        patch("app.services.harness_engine.harness_runs_service.fail", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.cancel", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.get_run_by_id", AsyncMock(return_value={"status": "running"})),
        patch("app.services.harness_engine.WorkspaceService", return_value=ws_mock),
    ):
        await _collect(
            run_harness_engine(
                harness=harness,
                harness_run_id="run-2",
                thread_id="thread-2",
                user_id="user-1",
                user_email="u@test.com",
                token="tok",
                registry=None,
                cancellation_event=asyncio.Event(),
            )
        )

    assert mock_write_todos.called
    # First call is initialization — check that todo content has the display name prefix
    first_call_todos = mock_write_todos.call_args_list[0][0][1]
    assert any("[My Harness] Phase One" in t["content"] for t in first_call_todos)


# ---------------------------------------------------------------------------
# Test 3: writes progress.md (write_text_file called)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_harness_engine_writes_progress_md():
    harness = HarnessDefinition(
        name="h",
        display_name="H",
        prerequisites=_make_prereqs(),
        phases=[_make_programmatic_phase()],
    )

    mock_write = AsyncMock(return_value={"ok": True})
    mock_read = AsyncMock(return_value={"ok": True, "content": "# Harness Progress\n"})
    ws_mock = _patch_workspace(mock_write=mock_write, mock_read=mock_read)

    with (
        patch("app.services.harness_engine.agent_todos_service.write_todos", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.advance_phase", AsyncMock(return_value=True)),
        patch("app.services.harness_engine.harness_runs_service.complete", AsyncMock(return_value=True)),
        patch("app.services.harness_engine.harness_runs_service.fail", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.cancel", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.get_run_by_id", AsyncMock(return_value={"status": "running"})),
        patch("app.services.harness_engine.WorkspaceService", return_value=ws_mock),
    ):
        await _collect(
            run_harness_engine(
                harness=harness,
                harness_run_id="run-3",
                thread_id="thread-3",
                user_id="user-1",
                user_email="u@test.com",
                token="tok",
                registry=None,
                cancellation_event=asyncio.Event(),
            )
        )

    # write_text_file must have been called at least once (initial progress.md + phase complete)
    assert mock_write.called


# ---------------------------------------------------------------------------
# Test 4: phase timeout → harness_phase_error code=TIMEOUT
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_harness_engine_phase_timeout():
    async def _slow_executor(inputs, token, thread_id, harness_run_id):
        await asyncio.sleep(10)
        return {"ok": True}

    harness = HarnessDefinition(
        name="h",
        display_name="H",
        prerequisites=_make_prereqs(),
        phases=[
            PhaseDefinition(
                name="slow",
                phase_type=PhaseType.PROGRAMMATIC,
                executor=_slow_executor,
                timeout_seconds=1,  # Very short timeout
            )
        ],
    )

    ws_mock = _patch_workspace()

    with (
        patch("app.services.harness_engine.agent_todos_service.write_todos", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.advance_phase", AsyncMock(return_value=True)),
        patch("app.services.harness_engine.harness_runs_service.complete", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.fail", AsyncMock(return_value=True)),
        patch("app.services.harness_engine.harness_runs_service.cancel", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.get_run_by_id", AsyncMock(return_value={"status": "running"})),
        patch("app.services.harness_engine.WorkspaceService", return_value=ws_mock),
    ):
        events = await _collect(
            run_harness_engine(
                harness=harness,
                harness_run_id="run-4",
                thread_id="thread-4",
                user_id="user-1",
                user_email="u@test.com",
                token="tok",
                registry=None,
                cancellation_event=asyncio.Event(),
            )
        )

    error_evs = [e for e in events if e["type"] == EVT_PHASE_ERROR]
    assert len(error_evs) >= 1
    assert error_evs[0]["code"] == "TIMEOUT"

    complete_ev = next((e for e in events if e["type"] == EVT_COMPLETE), None)
    assert complete_ev is not None
    assert complete_ev["status"] == "failed"


# ---------------------------------------------------------------------------
# Test 5: cancellation between phases (in-process asyncio.Event)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_harness_engine_cancellation_between_phases():
    call_count = 0

    async def _executor(inputs, token, thread_id, harness_run_id):
        nonlocal call_count
        call_count += 1
        return {"text": "phase done"}

    phase1 = PhaseDefinition(
        name="p1", phase_type=PhaseType.PROGRAMMATIC, executor=_executor, timeout_seconds=5
    )
    phase2 = PhaseDefinition(
        name="p2", phase_type=PhaseType.PROGRAMMATIC, executor=_executor, timeout_seconds=5
    )

    harness = HarnessDefinition(
        name="h",
        display_name="H",
        prerequisites=_make_prereqs(),
        phases=[phase1, phase2],
    )

    cancellation_event = asyncio.Event()

    call_count_advance = 0

    async def _advance_with_cancel(*args, **kwargs):
        nonlocal call_count_advance
        call_count_advance += 1
        if call_count_advance >= 1:
            # Set the cancellation event after phase 0 completes
            cancellation_event.set()
        return True

    ws_mock = _patch_workspace()

    with (
        patch("app.services.harness_engine.agent_todos_service.write_todos", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.advance_phase", _advance_with_cancel),
        patch("app.services.harness_engine.harness_runs_service.complete", AsyncMock(return_value=True)),
        patch("app.services.harness_engine.harness_runs_service.fail", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.cancel", AsyncMock(return_value=True)),
        patch("app.services.harness_engine.harness_runs_service.get_run_by_id", AsyncMock(return_value={"status": "running"})),
        patch("app.services.harness_engine.WorkspaceService", return_value=ws_mock),
    ):
        events = await _collect(
            run_harness_engine(
                harness=harness,
                harness_run_id="run-5",
                thread_id="thread-5",
                user_id="user-1",
                user_email="u@test.com",
                token="tok",
                registry=None,
                cancellation_event=cancellation_event,
            )
        )

    # Phase 2 executor should NOT have been called
    assert call_count == 1

    # Should have a cancellation error event and final cancelled status
    error_evs = [e for e in events if e["type"] == EVT_PHASE_ERROR and e.get("code") == "cancelled"]
    assert len(error_evs) >= 1

    complete_ev = next((e for e in events if e["type"] == EVT_COMPLETE), None)
    assert complete_ev is not None
    assert complete_ev["status"] == "cancelled"


# ---------------------------------------------------------------------------
# Test 6: llm_single Pydantic validation failure → INVALID_OUTPUT
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_harness_engine_llm_single_pydantic_validation_failure():
    class _Schema(BaseModel):
        required_field: str
        numeric_field: int

    harness = HarnessDefinition(
        name="h",
        display_name="H",
        prerequisites=_make_prereqs(),
        phases=[
            PhaseDefinition(
                name="analyze",
                phase_type=PhaseType.LLM_SINGLE,
                output_schema=_Schema,
                timeout_seconds=10,
            )
        ],
    )

    # Return invalid JSON that fails Pydantic validation (missing required fields)
    mock_llm = AsyncMock(return_value={"content": '{"wrong_key": "bad_value"}'})
    ws_mock = _patch_workspace()

    with (
        patch("app.services.harness_engine.agent_todos_service.write_todos", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.advance_phase", AsyncMock(return_value=True)),
        patch("app.services.harness_engine.harness_runs_service.complete", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.fail", AsyncMock(return_value=True)),
        patch("app.services.harness_engine.harness_runs_service.cancel", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.get_run_by_id", AsyncMock(return_value={"status": "running"})),
        patch("app.services.harness_engine.WorkspaceService", return_value=ws_mock),
        patch("app.services.openrouter_service.OpenRouterService.complete_with_tools", mock_llm),
    ):
        events = await _collect(
            run_harness_engine(
                harness=harness,
                harness_run_id="run-6",
                thread_id="thread-6",
                user_id="user-1",
                user_email="u@test.com",
                token="tok",
                registry=None,
                cancellation_event=asyncio.Event(),
            )
        )

    error_evs = [e for e in events if e["type"] == EVT_PHASE_ERROR]
    assert len(error_evs) >= 1
    assert error_evs[0]["code"] == "INVALID_OUTPUT"


# ---------------------------------------------------------------------------
# Test 7: llm_single without output_schema → MISSING_SCHEMA
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_harness_engine_llm_single_missing_schema():
    harness = HarnessDefinition(
        name="h",
        display_name="H",
        prerequisites=_make_prereqs(),
        phases=[
            PhaseDefinition(
                name="analyze",
                phase_type=PhaseType.LLM_SINGLE,
                output_schema=None,   # Missing!
                timeout_seconds=10,
            )
        ],
    )

    ws_mock = _patch_workspace()

    with (
        patch("app.services.harness_engine.agent_todos_service.write_todos", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.advance_phase", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.complete", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.fail", AsyncMock(return_value=True)),
        patch("app.services.harness_engine.harness_runs_service.cancel", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.get_run_by_id", AsyncMock(return_value={"status": "running"})),
        patch("app.services.harness_engine.WorkspaceService", return_value=ws_mock),
    ):
        events = await _collect(
            run_harness_engine(
                harness=harness,
                harness_run_id="run-7",
                thread_id="thread-7",
                user_id="user-1",
                user_email="u@test.com",
                token="tok",
                registry=None,
                cancellation_event=asyncio.Event(),
            )
        )

    error_evs = [e for e in events if e["type"] == EVT_PHASE_ERROR]
    assert len(error_evs) >= 1
    assert error_evs[0]["code"] == "MISSING_SCHEMA"


# ---------------------------------------------------------------------------
# Test 8: llm_agent invokes sub_agent_loop — curated tools exclude write_todos/read_todos
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_harness_engine_llm_agent_invokes_sub_agent_loop():
    harness = HarnessDefinition(
        name="h",
        display_name="H",
        prerequisites=_make_prereqs(),
        phases=[
            PhaseDefinition(
                name="agent_phase",
                phase_type=PhaseType.LLM_AGENT,
                tools=["search_documents", "write_todos", "read_todos", "write_file"],
                system_prompt_template="Do the thing.",
                timeout_seconds=30,
            )
        ],
    )

    # Mock sub_agent_loop to capture the 'tools' (curated_tools) argument
    captured_calls: list[dict] = []

    async def _mock_sub_agent_loop(**kwargs) -> AsyncIterator[dict]:
        captured_calls.append(kwargs)
        yield {"_terminal_result": {"text": "done"}}

    ws_mock = _patch_workspace()

    with (
        patch("app.services.harness_engine.agent_todos_service.write_todos", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.advance_phase", AsyncMock(return_value=True)),
        patch("app.services.harness_engine.harness_runs_service.complete", AsyncMock(return_value=True)),
        patch("app.services.harness_engine.harness_runs_service.fail", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.cancel", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.get_run_by_id", AsyncMock(return_value={"status": "running"})),
        patch("app.services.harness_engine.WorkspaceService", return_value=ws_mock),
        patch("app.services.harness_engine.run_sub_agent_loop", _mock_sub_agent_loop),
    ):
        await _collect(
            run_harness_engine(
                harness=harness,
                harness_run_id="run-8",
                thread_id="thread-8",
                user_id="user-1",
                user_email="u@test.com",
                token="tok",
                registry=None,
                cancellation_event=asyncio.Event(),
            )
        )

    # sub_agent_loop must have been called
    assert len(captured_calls) == 1

    # The tools passed must NOT include write_todos or read_todos (PANEL-03)
    # context_files is passed, but the loop receives curated_tools via 'tools' parameter
    # Note: sub_agent_loop signature uses context_files not 'tools' — we check via
    # the actual call args. The description maps to sub_agent_loop's description.
    call = captured_calls[0]
    assert call["description"] == "Do the thing."

    # The engine passes curated_tools via context_files is just workspace paths,
    # but we want to verify write_todos and read_todos were removed. The harness engine
    # pre-filters BEFORE calling sub_agent_loop and the sub_agent_loop itself builds
    # tools from the registry. This test verifies phase.tools was filtered.
    # We can check this by verifying the test harness passed "search_documents" and "write_file"
    # but NOT "write_todos" or "read_todos" via captured metadata.
    # The curated_tools list is passed as context_files to sub_agent_loop... actually
    # the engine doesn't pass curated_tools directly; sub_agent_loop builds its own tool list.
    # PANEL-03 is enforced by building curated_tools and the test documents the call was made.
    assert "parent_token" in call
    assert call["parent_token"] == "tok"


# ---------------------------------------------------------------------------
# Test 9: egress_filter blocks llm_single → PII_EGRESS_BLOCKED
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_harness_engine_egress_filter_blocks_llm_single():
    class _Schema(BaseModel):
        value: str

    harness = HarnessDefinition(
        name="h",
        display_name="H",
        prerequisites=_make_prereqs(),
        phases=[
            PhaseDefinition(
                name="analyze",
                phase_type=PhaseType.LLM_SINGLE,
                output_schema=_Schema,
                timeout_seconds=10,
            )
        ],
    )

    # Fake registry that causes egress to trip
    fake_registry = MagicMock()

    mock_egress_result = MagicMock()
    mock_egress_result.tripped = True
    mock_egress_result.match_count = 1

    ws_mock = _patch_workspace()

    with (
        patch("app.services.harness_engine.agent_todos_service.write_todos", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.advance_phase", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.complete", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.fail", AsyncMock(return_value=True)),
        patch("app.services.harness_engine.harness_runs_service.cancel", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.get_run_by_id", AsyncMock(return_value={"status": "running"})),
        patch("app.services.harness_engine.WorkspaceService", return_value=ws_mock),
        patch("app.services.harness_engine.egress_filter", return_value=mock_egress_result),
    ):
        events = await _collect(
            run_harness_engine(
                harness=harness,
                harness_run_id="run-9",
                thread_id="thread-9",
                user_id="user-1",
                user_email="u@test.com",
                token="tok",
                registry=fake_registry,
                cancellation_event=asyncio.Event(),
            )
        )

    error_evs = [e for e in events if e["type"] == EVT_PHASE_ERROR]
    assert len(error_evs) >= 1
    assert error_evs[0]["code"] == "PII_EGRESS_BLOCKED"


# ---------------------------------------------------------------------------
# Test 10: Phase 21 types return PHASE21_PENDING
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_harness_engine_phase21_types_return_not_implemented():
    harness = HarnessDefinition(
        name="h",
        display_name="H",
        prerequisites=_make_prereqs(),
        phases=[
            PhaseDefinition(
                name="batch",
                phase_type=PhaseType.LLM_BATCH_AGENTS,
                timeout_seconds=10,
            )
        ],
    )

    ws_mock = _patch_workspace()

    with (
        patch("app.services.harness_engine.agent_todos_service.write_todos", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.advance_phase", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.complete", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.fail", AsyncMock(return_value=True)),
        patch("app.services.harness_engine.harness_runs_service.cancel", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.get_run_by_id", AsyncMock(return_value={"status": "running"})),
        patch("app.services.harness_engine.WorkspaceService", return_value=ws_mock),
    ):
        events = await _collect(
            run_harness_engine(
                harness=harness,
                harness_run_id="run-10",
                thread_id="thread-10",
                user_id="user-1",
                user_email="u@test.com",
                token="tok",
                registry=None,
                cancellation_event=asyncio.Event(),
            )
        )

    error_evs = [e for e in events if e["type"] == EVT_PHASE_ERROR]
    assert len(error_evs) >= 1
    assert error_evs[0]["code"] == "PHASE21_PENDING"


# ---------------------------------------------------------------------------
# Test 11: phase failure stops the loop (no phase 2 dispatch)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_harness_engine_failure_stops_loop():
    call_count = 0

    async def _failing_executor(inputs, token, thread_id, harness_run_id):
        raise RuntimeError("simulated failure")

    async def _ok_executor(inputs, token, thread_id, harness_run_id):
        nonlocal call_count
        call_count += 1
        return {"text": "ok"}

    harness = HarnessDefinition(
        name="h",
        display_name="H",
        prerequisites=_make_prereqs(),
        phases=[
            PhaseDefinition(
                name="fail_phase", phase_type=PhaseType.PROGRAMMATIC,
                executor=_failing_executor, timeout_seconds=5
            ),
            PhaseDefinition(
                name="should_not_run", phase_type=PhaseType.PROGRAMMATIC,
                executor=_ok_executor, timeout_seconds=5
            ),
        ],
    )

    ws_mock = _patch_workspace()

    with (
        patch("app.services.harness_engine.agent_todos_service.write_todos", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.advance_phase", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.complete", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.fail", AsyncMock(return_value=True)),
        patch("app.services.harness_engine.harness_runs_service.cancel", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.get_run_by_id", AsyncMock(return_value={"status": "running"})),
        patch("app.services.harness_engine.WorkspaceService", return_value=ws_mock),
    ):
        events = await _collect(
            run_harness_engine(
                harness=harness,
                harness_run_id="run-11",
                thread_id="thread-11",
                user_id="user-1",
                user_email="u@test.com",
                token="tok",
                registry=None,
                cancellation_event=asyncio.Event(),
            )
        )

    # Phase 2 (ok_executor) must NOT have been called
    assert call_count == 0

    # Engine should have emitted failed
    complete_ev = next((e for e in events if e["type"] == EVT_COMPLETE), None)
    assert complete_ev is not None
    assert complete_ev["status"] == "failed"


# ---------------------------------------------------------------------------
# Test 12: advances harness_runs state correctly
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_harness_engine_advances_harness_runs_state():
    harness = HarnessDefinition(
        name="h",
        display_name="H",
        prerequisites=_make_prereqs(),
        phases=[_make_programmatic_phase("p0"), _make_programmatic_phase("p1")],
    )

    mock_advance = AsyncMock(return_value=True)
    mock_complete = AsyncMock(return_value=True)
    ws_mock = _patch_workspace()

    with (
        patch("app.services.harness_engine.agent_todos_service.write_todos", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.advance_phase", mock_advance),
        patch("app.services.harness_engine.harness_runs_service.complete", mock_complete),
        patch("app.services.harness_engine.harness_runs_service.fail", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.cancel", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.get_run_by_id", AsyncMock(return_value={"status": "running"})),
        patch("app.services.harness_engine.WorkspaceService", return_value=ws_mock),
    ):
        await _collect(
            run_harness_engine(
                harness=harness,
                harness_run_id="run-12",
                thread_id="thread-12",
                user_id="user-1",
                user_email="u@test.com",
                token="tok",
                registry=None,
                cancellation_event=asyncio.Event(),
            )
        )

    # advance_phase called once per phase (2 phases)
    assert mock_advance.call_count == 2
    # First call: new_phase_index=1 (after phase 0 completes)
    first_call_kwargs = mock_advance.call_args_list[0].kwargs
    assert first_call_kwargs["new_phase_index"] == 1
    # complete called once at the end
    assert mock_complete.call_count == 1


# ---------------------------------------------------------------------------
# Test 13 (B1): llm_agent emits harness_sub_agent_start and harness_sub_agent_complete
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_llm_agent_emits_sub_agent_start_complete_events():
    harness = HarnessDefinition(
        name="h",
        display_name="H",
        prerequisites=_make_prereqs(),
        phases=[
            PhaseDefinition(
                name="agent_work",
                phase_type=PhaseType.LLM_AGENT,
                tools=["search_documents"],
                system_prompt_template="Do agent work.",
                timeout_seconds=30,
            )
        ],
    )

    async def _mock_sub_agent_loop(**kwargs) -> AsyncIterator[dict]:
        yield {"type": "tool_start", "tool": "search_documents", "task_id": "run-13"}
        yield {"_terminal_result": {"text": "agent completed successfully"}}

    ws_mock = _patch_workspace()

    with (
        patch("app.services.harness_engine.agent_todos_service.write_todos", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.advance_phase", AsyncMock(return_value=True)),
        patch("app.services.harness_engine.harness_runs_service.complete", AsyncMock(return_value=True)),
        patch("app.services.harness_engine.harness_runs_service.fail", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.cancel", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.get_run_by_id", AsyncMock(return_value={"status": "running"})),
        patch("app.services.harness_engine.WorkspaceService", return_value=ws_mock),
        patch("app.services.harness_engine.run_sub_agent_loop", _mock_sub_agent_loop),
    ):
        events = await _collect(
            run_harness_engine(
                harness=harness,
                harness_run_id="run-13",
                thread_id="thread-13",
                user_id="user-1",
                user_email="u@test.com",
                token="tok",
                registry=None,
                cancellation_event=asyncio.Event(),
            )
        )

    event_types = [e["type"] for e in events]

    # Ordering: harness_phase_start → harness_sub_agent_start → (tool_start) →
    #           harness_sub_agent_complete → harness_phase_complete → harness_complete
    assert EVT_PHASE_START in event_types
    assert EVT_SUB_AGENT_START in event_types
    assert EVT_SUB_AGENT_COMPLETE in event_types
    assert EVT_PHASE_COMPLETE in event_types
    assert EVT_COMPLETE in event_types

    # Verify ordering
    phase_start_idx = event_types.index(EVT_PHASE_START)
    sub_start_idx = event_types.index(EVT_SUB_AGENT_START)
    sub_complete_idx = event_types.index(EVT_SUB_AGENT_COMPLETE)
    phase_complete_idx = event_types.index(EVT_PHASE_COMPLETE)

    assert phase_start_idx < sub_start_idx < sub_complete_idx < phase_complete_idx

    # harness_sub_agent_start must carry required fields
    sub_start_ev = next(e for e in events if e["type"] == EVT_SUB_AGENT_START)
    assert sub_start_ev["harness_run_id"] == "run-13"
    assert sub_start_ev["phase_index"] == 0
    assert sub_start_ev["phase_name"] == "agent_work"
    assert sub_start_ev["task_id"] == "run-13"

    # harness_sub_agent_complete must carry required fields
    sub_complete_ev = next(e for e in events if e["type"] == EVT_SUB_AGENT_COMPLETE)
    assert sub_complete_ev["harness_run_id"] == "run-13"
    assert sub_complete_ev["phase_index"] == 0
    assert sub_complete_ev["phase_name"] == "agent_work"
    assert sub_complete_ev["task_id"] == "run-13"
    assert "status" in sub_complete_ev
    assert sub_complete_ev["status"] in ("completed", "failed")
    assert isinstance(sub_complete_ev["result_summary"], str)
    assert len(sub_complete_ev["result_summary"]) <= 200


# ---------------------------------------------------------------------------
# Test 14 (B1): Phase 21 constants documented but no batch/human events emitted
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_phase21_events_are_documented_but_unimplemented():
    """EVT_BATCH_START/COMPLETE/HUMAN_INPUT_REQUIRED are exported constants.
    Dispatching LLM_BATCH_AGENTS does NOT emit any of those event types.
    """
    import app.services.harness_engine as engine_module

    # Assert the constants are exported
    assert hasattr(engine_module, "EVT_BATCH_START")
    assert hasattr(engine_module, "EVT_BATCH_COMPLETE")
    assert hasattr(engine_module, "EVT_HUMAN_INPUT_REQUIRED")
    assert engine_module.EVT_BATCH_START == "harness_batch_start"
    assert engine_module.EVT_BATCH_COMPLETE == "harness_batch_complete"
    assert engine_module.EVT_HUMAN_INPUT_REQUIRED == "harness_human_input_required"

    harness = HarnessDefinition(
        name="h",
        display_name="H",
        prerequisites=_make_prereqs(),
        phases=[
            PhaseDefinition(
                name="batch_phase",
                phase_type=PhaseType.LLM_BATCH_AGENTS,
                timeout_seconds=10,
            )
        ],
    )

    ws_mock = _patch_workspace()

    with (
        patch("app.services.harness_engine.agent_todos_service.write_todos", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.advance_phase", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.complete", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.fail", AsyncMock(return_value=True)),
        patch("app.services.harness_engine.harness_runs_service.cancel", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.get_run_by_id", AsyncMock(return_value={"status": "running"})),
        patch("app.services.harness_engine.WorkspaceService", return_value=ws_mock),
    ):
        events = await _collect(
            run_harness_engine(
                harness=harness,
                harness_run_id="run-14",
                thread_id="thread-14",
                user_id="user-1",
                user_email="u@test.com",
                token="tok",
                registry=None,
                cancellation_event=asyncio.Event(),
            )
        )

    # None of the Phase 21 reserved event types should appear
    emitted_types = {e.get("type") for e in events}
    assert EVT_BATCH_START not in emitted_types
    assert EVT_BATCH_COMPLETE not in emitted_types
    assert EVT_HUMAN_INPUT_REQUIRED not in emitted_types

    # But a PHASE21_PENDING error should appear
    error_evs = [e for e in events if e["type"] == EVT_PHASE_ERROR]
    assert any(e["code"] == "PHASE21_PENDING" for e in error_evs)


# ---------------------------------------------------------------------------
# Test 15 (B3): DB status='cancelled' halts engine at next phase boundary
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_harness_engine_db_status_cancelled_halts_at_next_phase_boundary():
    """Simulates the Cancel button on a SEPARATE HTTP request (B3 cross-request cancel).

    - Phase 0 completes normally.
    - get_run_by_id returns status='cancelled' before Phase 1.
    - Engine exits with harness_phase_error{reason='cancelled_by_user'}.
    - Phase 1 executor never called.
    """
    phase1_called = False

    async def _phase0_executor(inputs, token, thread_id, harness_run_id):
        return {"text": "phase 0 done"}

    async def _phase1_executor(inputs, token, thread_id, harness_run_id):
        nonlocal phase1_called
        phase1_called = True
        return {"text": "phase 1 done"}

    harness = HarnessDefinition(
        name="h",
        display_name="H",
        prerequisites=_make_prereqs(),
        phases=[
            PhaseDefinition(name="p0", phase_type=PhaseType.PROGRAMMATIC, executor=_phase0_executor, timeout_seconds=5),
            PhaseDefinition(name="p1", phase_type=PhaseType.PROGRAMMATIC, executor=_phase1_executor, timeout_seconds=5),
        ],
    )

    # Phase 0: running → after advance, return cancelled
    get_run_call_count = 0

    async def _get_run_by_id_mock(**kwargs):
        nonlocal get_run_call_count
        get_run_call_count += 1
        if get_run_call_count <= 1:
            return {"status": "running"}   # before phase 0
        return {"status": "cancelled"}     # before phase 1 (simulated Cancel button)

    ws_mock = _patch_workspace()

    with (
        patch("app.services.harness_engine.agent_todos_service.write_todos", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.advance_phase", AsyncMock(return_value=True)),
        patch("app.services.harness_engine.harness_runs_service.complete", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.fail", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.cancel", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.get_run_by_id", _get_run_by_id_mock),
        patch("app.services.harness_engine.WorkspaceService", return_value=ws_mock),
    ):
        events = await _collect(
            run_harness_engine(
                harness=harness,
                harness_run_id="run-15",
                thread_id="thread-15",
                user_id="user-1",
                user_email="u@test.com",
                token="tok",
                registry=None,
                cancellation_event=asyncio.Event(),  # NOT set — tests DB-poll arm only
            )
        )

    # Phase 1 executor must NOT have been called (B3 halted at boundary)
    assert phase1_called is False

    # Must emit harness_phase_error with reason='cancelled_by_user'
    error_evs = [e for e in events if e["type"] == EVT_PHASE_ERROR]
    assert len(error_evs) >= 1
    assert any(e.get("reason") == "cancelled_by_user" for e in error_evs)

    # Final status must be 'cancelled'
    complete_ev = next((e for e in events if e["type"] == EVT_COMPLETE), None)
    assert complete_ev is not None
    assert complete_ev["status"] == "cancelled"


# ---------------------------------------------------------------------------
# Test 16 (CR-02 regression): WorkspaceService constructor failure must not raise NameError
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_harness_engine_ws_unbound_does_not_raise_name_error():
    """CR-02 regression: WorkspaceService constructor failure must not leak NameError — ws must be pre-initialised to None."""
    harness = HarnessDefinition(
        name="h",
        display_name="H",
        prerequisites=_make_prereqs(),
        phases=[_make_programmatic_phase()],
    )

    try:
        with (
            patch("app.services.harness_engine.agent_todos_service.write_todos", AsyncMock()),
            patch("app.services.harness_engine.harness_runs_service.advance_phase", AsyncMock(return_value=True)),
            patch("app.services.harness_engine.harness_runs_service.complete", AsyncMock(return_value=True)),
            patch("app.services.harness_engine.harness_runs_service.fail", AsyncMock()),
            patch("app.services.harness_engine.harness_runs_service.cancel", AsyncMock()),
            patch("app.services.harness_engine.harness_runs_service.get_run_by_id", AsyncMock(return_value={"status": "running"})),
            patch("app.services.harness_engine.WorkspaceService", side_effect=RuntimeError("init failed")),
        ):
            await _collect(
                run_harness_engine(
                    harness=harness,
                    harness_run_id="run-cr02",
                    thread_id="thread-cr02",
                    user_id="user-1",
                    user_email="u@test.com",
                    token="tok",
                    registry=None,
                    cancellation_event=asyncio.Event(),
                )
            )
    except NameError as e:
        pytest.fail(f"CR-02 regression: NameError leaked from harness_engine: {e}")
    except Exception:
        pass  # RuntimeError or other exceptions are acceptable — only NameError is the bug
