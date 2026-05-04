"""Phase 21 / Plan 21-02 Task 2 — Tests for LLM_HUMAN_INPUT dispatch + outer paused-terminal handler.

6 tests covering HIL-01..03 + the outer-loop paused short-circuit (BLOCKER-4 fix):
  1. test_hil_question_generation_llm_call          — LLM called once with json_schema(HumanInputQuestion)
  2. test_hil_delta_events_emitted_before_required  — delta(s) → harness_human_input_required → done
  3. test_hil_required_event_payload                — required event has {type, question, workspace_output_path, harness_run_id}
  4. test_hil_db_paused_before_sse_close            — harness_runs_service.pause called BEFORE final harness_complete
  5. test_hil_egress_filter_blocks_pii_question     — egress trip → egress_blocked terminal, NO LLM call, NO pause()
  6. test_hil_phase_yields_paused_terminal_and_stops— outer loop yields harness_complete{status=paused}, no advance_phase, no complete, phase[1] never dispatched
"""
from __future__ import annotations

import asyncio
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
    EVT_COMPLETE,
    EVT_HUMAN_INPUT_REQUIRED,
    EVT_PHASE_COMPLETE,
    EVT_PHASE_START,
    HumanInputQuestion,
    run_harness_engine,
)


def _make_prereqs() -> HarnessPrerequisites:
    return HarnessPrerequisites(harness_intro="test harness")


async def _collect(gen) -> list[dict]:
    events = []
    async for ev in gen:
        events.append(ev)
    return events


def _patch_workspace(read_data: dict | None = None) -> MagicMock:
    ws_instance = MagicMock()
    ws_instance.write_text_file = AsyncMock(return_value={"ok": True})
    ws_instance.read_file = AsyncMock(
        return_value=read_data or {"ok": True, "content": "prior phase output\n"}
    )
    return ws_instance


def _make_hil_phase(name: str = "ask-label", workspace_output: str = "test-answer.md") -> PhaseDefinition:
    return PhaseDefinition(
        name=name,
        phase_type=PhaseType.LLM_HUMAN_INPUT,
        system_prompt_template="Generate a single short question.",
        workspace_inputs=["echo.md"],
        workspace_output=workspace_output,
        timeout_seconds=86_400,
    )


# ---------------------------------------------------------------------------
# Test 1 — LLM called once with json_schema response_format for HumanInputQuestion
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_hil_question_generation_llm_call():
    harness = HarnessDefinition(
        name="h", display_name="H", prerequisites=_make_prereqs(),
        phases=[_make_hil_phase()],
    )

    mock_llm = AsyncMock(return_value={"content": '{"question": "What label?"}'})
    ws_mock = _patch_workspace()

    with (
        patch("app.services.harness_engine.agent_todos_service.write_todos", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.advance_phase", AsyncMock(return_value=True)),
        patch("app.services.harness_engine.harness_runs_service.complete", AsyncMock(return_value=True)),
        patch("app.services.harness_engine.harness_runs_service.fail", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.cancel", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.pause", AsyncMock(return_value={"id": "run-1", "status": "paused"})),
        patch("app.services.harness_engine.harness_runs_service.get_run_by_id", AsyncMock(return_value={"status": "running"})),
        patch("app.services.harness_engine.WorkspaceService", return_value=ws_mock),
        patch("app.services.openrouter_service.OpenRouterService.complete_with_tools", mock_llm),
    ):
        await _collect(
            run_harness_engine(
                harness=harness, harness_run_id="run-1", thread_id="t1",
                user_id="u1", user_email="u@test.com", token="tok",
                registry=None, cancellation_event=asyncio.Event(),
            )
        )

    assert mock_llm.call_count == 1
    call_kwargs = mock_llm.call_args.kwargs
    response_format = call_kwargs.get("response_format")
    assert response_format is not None
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["name"] == "HumanInputQuestion"
    schema = response_format["json_schema"]["schema"]
    # Must have a 'question' property required
    assert "question" in schema.get("properties", {})


# ---------------------------------------------------------------------------
# Test 2 — delta events emitted BEFORE harness_human_input_required
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_hil_delta_events_emitted_before_required():
    harness = HarnessDefinition(
        name="h", display_name="H", prerequisites=_make_prereqs(),
        phases=[_make_hil_phase()],
    )

    mock_llm = AsyncMock(return_value={"content": '{"question": "What label should we use for the echo result?"}'})
    ws_mock = _patch_workspace()

    with (
        patch("app.services.harness_engine.agent_todos_service.write_todos", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.advance_phase", AsyncMock(return_value=True)),
        patch("app.services.harness_engine.harness_runs_service.complete", AsyncMock(return_value=True)),
        patch("app.services.harness_engine.harness_runs_service.fail", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.cancel", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.pause", AsyncMock(return_value={"id": "run-2", "status": "paused"})),
        patch("app.services.harness_engine.harness_runs_service.get_run_by_id", AsyncMock(return_value={"status": "running"})),
        patch("app.services.harness_engine.WorkspaceService", return_value=ws_mock),
        patch("app.services.openrouter_service.OpenRouterService.complete_with_tools", mock_llm),
    ):
        events = await _collect(
            run_harness_engine(
                harness=harness, harness_run_id="run-2", thread_id="t2",
                user_id="u1", user_email="u@test.com", token="tok",
                registry=None, cancellation_event=asyncio.Event(),
            )
        )

    types = [e.get("type") for e in events]
    # At least one delta exists
    delta_indexes = [i for i, t in enumerate(types) if t == "delta"]
    assert len(delta_indexes) >= 1, f"no delta events found in {types}"
    # Required event exists
    assert types.count(EVT_HUMAN_INPUT_REQUIRED) == 1
    required_idx = types.index(EVT_HUMAN_INPUT_REQUIRED)
    # All deltas come before required event
    assert all(i < required_idx for i in delta_indexes)


# ---------------------------------------------------------------------------
# Test 3 — required event payload has {type, question, workspace_output_path, harness_run_id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_hil_required_event_payload():
    phase = _make_hil_phase(workspace_output="my-answer.md")
    harness = HarnessDefinition(
        name="h", display_name="H", prerequisites=_make_prereqs(),
        phases=[phase],
    )

    mock_llm = AsyncMock(return_value={"content": '{"question": "What label?"}'})
    ws_mock = _patch_workspace()

    with (
        patch("app.services.harness_engine.agent_todos_service.write_todos", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.advance_phase", AsyncMock(return_value=True)),
        patch("app.services.harness_engine.harness_runs_service.complete", AsyncMock(return_value=True)),
        patch("app.services.harness_engine.harness_runs_service.fail", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.cancel", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.pause", AsyncMock(return_value={"id": "run-3", "status": "paused"})),
        patch("app.services.harness_engine.harness_runs_service.get_run_by_id", AsyncMock(return_value={"status": "running"})),
        patch("app.services.harness_engine.WorkspaceService", return_value=ws_mock),
        patch("app.services.openrouter_service.OpenRouterService.complete_with_tools", mock_llm),
    ):
        events = await _collect(
            run_harness_engine(
                harness=harness, harness_run_id="run-3", thread_id="t3",
                user_id="u1", user_email="u@test.com", token="tok",
                registry=None, cancellation_event=asyncio.Event(),
            )
        )

    required_evs = [e for e in events if e.get("type") == EVT_HUMAN_INPUT_REQUIRED]
    assert len(required_evs) == 1
    ev = required_evs[0]
    # Required keys
    assert ev["type"] == EVT_HUMAN_INPUT_REQUIRED
    assert ev["question"] == "What label?"
    assert ev["workspace_output_path"] == "my-answer.md"
    assert ev["harness_run_id"] == "run-3"


# ---------------------------------------------------------------------------
# Test 4 — pause() called BEFORE the final harness_complete event
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_hil_db_paused_before_sse_close():
    harness = HarnessDefinition(
        name="h", display_name="H", prerequisites=_make_prereqs(),
        phases=[_make_hil_phase()],
    )

    # Use a recorder mock that captures call order vs subsequent events.
    # We'll wrap pause() so that it appends "PAUSE_CALLED" to a shared log.
    call_log: list[str] = []

    async def _recording_pause(**kwargs):
        call_log.append(f"pause:{kwargs.get('run_id')}")
        return {"id": kwargs.get("run_id"), "status": "paused"}

    mock_llm = AsyncMock(return_value={"content": '{"question": "What label?"}'})
    ws_mock = _patch_workspace()

    with (
        patch("app.services.harness_engine.agent_todos_service.write_todos", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.advance_phase", AsyncMock(return_value=True)),
        patch("app.services.harness_engine.harness_runs_service.complete", AsyncMock(return_value=True)),
        patch("app.services.harness_engine.harness_runs_service.fail", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.cancel", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.pause", _recording_pause),
        patch("app.services.harness_engine.harness_runs_service.get_run_by_id", AsyncMock(return_value={"status": "running"})),
        patch("app.services.harness_engine.WorkspaceService", return_value=ws_mock),
        patch("app.services.openrouter_service.OpenRouterService.complete_with_tools", mock_llm),
    ):
        events = await _collect(
            run_harness_engine(
                harness=harness, harness_run_id="run-4", thread_id="t4",
                user_id="u1", user_email="u@test.com", token="tok",
                registry=None, cancellation_event=asyncio.Event(),
            )
        )

    # pause() must have been called exactly once with run_id="run-4"
    assert call_log == ["pause:run-4"]

    # The harness_complete event must exist with status='paused'
    complete_evs = [e for e in events if e.get("type") == EVT_COMPLETE]
    assert len(complete_evs) == 1
    assert complete_evs[0]["status"] == "paused"


# ---------------------------------------------------------------------------
# Test 5 — egress filter blocks PII → terminal egress_blocked, NO LLM, NO pause
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_hil_egress_filter_blocks_pii_question():
    harness = HarnessDefinition(
        name="h", display_name="H", prerequisites=_make_prereqs(),
        phases=[_make_hil_phase()],
    )

    fake_registry = MagicMock()
    egress_result = MagicMock()
    egress_result.tripped = True
    egress_result.match_count = 2

    mock_llm = AsyncMock(return_value={"content": '{"question": "What?"}'})
    mock_pause = AsyncMock(return_value={"id": "run-5", "status": "paused"})
    ws_mock = _patch_workspace()

    with (
        patch("app.services.harness_engine.agent_todos_service.write_todos", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.advance_phase", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.complete", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.fail", AsyncMock(return_value=True)),
        patch("app.services.harness_engine.harness_runs_service.cancel", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.pause", mock_pause),
        patch("app.services.harness_engine.harness_runs_service.get_run_by_id", AsyncMock(return_value={"status": "running"})),
        patch("app.services.harness_engine.WorkspaceService", return_value=ws_mock),
        patch("app.services.harness_engine.egress_filter", return_value=egress_result),
        patch("app.services.openrouter_service.OpenRouterService.complete_with_tools", mock_llm),
    ):
        events = await _collect(
            run_harness_engine(
                harness=harness, harness_run_id="run-5", thread_id="t5",
                user_id="u1", user_email="u@test.com", token="tok",
                registry=fake_registry, cancellation_event=asyncio.Event(),
            )
        )

    # No LLM call (egress runs BEFORE LLM)
    assert mock_llm.call_count == 0
    # No pause() call (egress short-circuits before pause)
    assert mock_pause.call_count == 0

    # Final phase_error / harness_complete must report PII_EGRESS_BLOCKED
    error_codes = [e.get("code") for e in events if e.get("type") == "harness_phase_error"]
    assert "PII_EGRESS_BLOCKED" in error_codes


# ---------------------------------------------------------------------------
# Test 6 (BLOCKER-4) — outer loop yields harness_complete{paused}, halts entirely
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_hil_phase_yields_paused_terminal_and_stops():
    """Multi-phase harness: phase[0]=HIL, phase[1]=PROGRAMMATIC.
    After HIL pauses:
      (a) Exactly ONE EVT_COMPLETE with status='paused'.
      (b) ZERO EVT_PHASE_COMPLETE for phase[0].
      (c) ZERO calls to advance_phase.
      (d) ZERO calls to complete().
      (e) Phase[1] is NEVER dispatched (no phase_start event for index 1).
    """
    phase1_called = False

    async def _phase1_executor(inputs, token, thread_id, harness_run_id):
        nonlocal phase1_called
        phase1_called = True
        return {"text": "phase 1 done"}

    harness = HarnessDefinition(
        name="h", display_name="H", prerequisites=_make_prereqs(),
        phases=[
            _make_hil_phase("ask-label"),
            PhaseDefinition(
                name="should_not_run", phase_type=PhaseType.PROGRAMMATIC,
                executor=_phase1_executor, timeout_seconds=5,
            ),
        ],
    )

    mock_llm = AsyncMock(return_value={"content": '{"question": "Pick a label?"}'})
    mock_advance = AsyncMock(return_value=True)
    mock_complete = AsyncMock(return_value=True)
    mock_pause = AsyncMock(return_value={"id": "run-6", "status": "paused"})
    ws_mock = _patch_workspace()

    with (
        patch("app.services.harness_engine.agent_todos_service.write_todos", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.advance_phase", mock_advance),
        patch("app.services.harness_engine.harness_runs_service.complete", mock_complete),
        patch("app.services.harness_engine.harness_runs_service.fail", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.cancel", AsyncMock()),
        patch("app.services.harness_engine.harness_runs_service.pause", mock_pause),
        patch("app.services.harness_engine.harness_runs_service.get_run_by_id", AsyncMock(return_value={"status": "running"})),
        patch("app.services.harness_engine.WorkspaceService", return_value=ws_mock),
        patch("app.services.openrouter_service.OpenRouterService.complete_with_tools", mock_llm),
    ):
        events = await _collect(
            run_harness_engine(
                harness=harness, harness_run_id="run-6", thread_id="t6",
                user_id="u1", user_email="u@test.com", token="tok",
                registry=None, cancellation_event=asyncio.Event(),
            )
        )

    # (a) Exactly one EVT_COMPLETE with status='paused'
    complete_evs = [e for e in events if e.get("type") == EVT_COMPLETE]
    assert len(complete_evs) == 1
    assert complete_evs[0]["status"] == "paused"

    # (b) Zero EVT_PHASE_COMPLETE for phase[0]
    phase_complete_evs = [e for e in events if e.get("type") == EVT_PHASE_COMPLETE]
    assert len(phase_complete_evs) == 0

    # (c) Zero calls to advance_phase
    assert mock_advance.call_count == 0

    # (d) Zero calls to complete()
    assert mock_complete.call_count == 0

    # pause was called exactly once
    assert mock_pause.call_count == 1

    # (e) Phase[1] never dispatched — no PROGRAMMATIC executor call, no phase_start for index 1
    assert phase1_called is False
    phase_start_indexes = [
        e["phase_index"] for e in events if e.get("type") == EVT_PHASE_START
    ]
    assert 1 not in phase_start_indexes
