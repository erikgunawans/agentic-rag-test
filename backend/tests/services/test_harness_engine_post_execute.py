"""Phase 22 / DOCX-08 / D-22-15 / REVIEW #7 + #8 — Tests for post_execute hook.

7 tests locking the post_execute contract added in plan 22-03:
1.  test_post_execute_none_is_noop
2.  test_post_execute_success_yielded_as_artifact_event
3.  test_post_execute_error_dict_logged_no_status_change
4.  test_post_execute_exception_caught_no_status_change
5.  test_post_execute_runs_after_last_phase_before_engine_complete
6.  test_post_execute_emits_workspace_updated_when_wrote_binary  (REVIEW #7)
7.  test_harness_artifact_event_carries_correlation_fields        (REVIEW #8)
"""
from __future__ import annotations

import asyncio
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
    EVT_PHASE_COMPLETE,
    EVT_PHASE_START,
    run_harness_engine,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_prereqs() -> HarnessPrerequisites:
    return HarnessPrerequisites(harness_intro="test harness")


async def _collect(gen) -> list[dict]:
    """Drain an async generator into a list."""
    events = []
    async for ev in gen:
        events.append(ev)
    return events


def _make_programmatic_phase(name: str = "echo", post_execute=None) -> PhaseDefinition:
    async def _executor(inputs, token, thread_id, harness_run_id):
        return {"result": "ok", "text": "echo done"}

    return PhaseDefinition(
        name=name,
        phase_type=PhaseType.PROGRAMMATIC,
        executor=_executor,
        timeout_seconds=60,
        post_execute=post_execute,
    )


def _patch_workspace():
    """Return a mock WorkspaceService instance."""
    ws_instance = MagicMock()
    ws_instance.write_text_file = AsyncMock(return_value={"ok": True})
    ws_instance.read_file = AsyncMock(
        return_value={"ok": True, "content": "# Harness Progress\n"}
    )
    return ws_instance


def _make_harness(name: str = "contract-review", phases=None) -> HarnessDefinition:
    return HarnessDefinition(
        name=name,
        display_name="Contract Review",
        prerequisites=_make_prereqs(),
        phases=phases or [_make_programmatic_phase()],
    )


def _make_run_kwargs(harness, harness_run_id: str = "run-test"):
    return dict(
        harness=harness,
        harness_run_id=harness_run_id,
        thread_id="thread-1",
        user_id="user-1",
        user_email="u@test.com",
        token="tok",
        registry=None,
        cancellation_event=asyncio.Event(),
    )


def _base_patches():
    return {
        "app.services.harness_engine.agent_todos_service.write_todos": AsyncMock(return_value=None),
        "app.services.harness_engine.harness_runs_service.advance_phase": AsyncMock(return_value=True),
        "app.services.harness_engine.harness_runs_service.complete": AsyncMock(return_value=True),
        "app.services.harness_engine.harness_runs_service.fail": AsyncMock(return_value=True),
        "app.services.harness_engine.harness_runs_service.cancel": AsyncMock(return_value=True),
        "app.services.harness_engine.harness_runs_service.get_run_by_id": AsyncMock(
            return_value={"status": "running"}
        ),
    }


# ---------------------------------------------------------------------------
# Test 1: post_execute=None is a noop — smoke_echo byte-identical (D-16)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_post_execute_none_is_noop():
    """When post_execute=None the engine runs byte-identical to pre-Phase-22.

    No harness_artifact event should appear. The standard phase_start/phase_complete/
    harness_complete sequence must be preserved exactly.
    """
    harness = _make_harness(phases=[_make_programmatic_phase(post_execute=None)])
    ws_mock = _patch_workspace()

    patches = _base_patches()
    with (
        patch("app.services.harness_engine.agent_todos_service.write_todos", patches["app.services.harness_engine.agent_todos_service.write_todos"]),
        patch("app.services.harness_engine.harness_runs_service.advance_phase", patches["app.services.harness_engine.harness_runs_service.advance_phase"]),
        patch("app.services.harness_engine.harness_runs_service.complete", patches["app.services.harness_engine.harness_runs_service.complete"]),
        patch("app.services.harness_engine.harness_runs_service.fail", patches["app.services.harness_engine.harness_runs_service.fail"]),
        patch("app.services.harness_engine.harness_runs_service.cancel", patches["app.services.harness_engine.harness_runs_service.cancel"]),
        patch("app.services.harness_engine.harness_runs_service.get_run_by_id", patches["app.services.harness_engine.harness_runs_service.get_run_by_id"]),
        patch("app.services.harness_engine.WorkspaceService", return_value=ws_mock),
    ):
        events = await _collect(run_harness_engine(**_make_run_kwargs(harness)))

    event_types = [e.get("type") for e in events]

    assert "harness_artifact" not in event_types, "No harness_artifact event when post_execute=None"
    assert "workspace_updated" not in event_types, "No workspace_updated when post_execute=None"
    assert EVT_PHASE_START in event_types
    assert EVT_PHASE_COMPLETE in event_types
    assert EVT_COMPLETE in event_types

    complete_ev = next(e for e in events if e.get("type") == EVT_COMPLETE)
    assert complete_ev["status"] == "completed"


# ---------------------------------------------------------------------------
# Test 2: post_execute success → harness_artifact event with correct shape
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_post_execute_success_yielded_as_artifact_event():
    """post_execute returning ok=True dict yields harness_artifact with ok=True
    and includes harness_run_id + harness_mode (REVIEW #8)."""
    post_execute_mock = AsyncMock(return_value={
        "ok": True,
        "docx_path": "review.docx",
        "signed_url": "https://example.com/review.docx",
    })
    phase = _make_programmatic_phase(post_execute=post_execute_mock)
    harness = _make_harness(name="contract-review", phases=[phase])
    ws_mock = _patch_workspace()

    patches = _base_patches()
    with (
        patch("app.services.harness_engine.agent_todos_service.write_todos", patches["app.services.harness_engine.agent_todos_service.write_todos"]),
        patch("app.services.harness_engine.harness_runs_service.advance_phase", patches["app.services.harness_engine.harness_runs_service.advance_phase"]),
        patch("app.services.harness_engine.harness_runs_service.complete", patches["app.services.harness_engine.harness_runs_service.complete"]),
        patch("app.services.harness_engine.harness_runs_service.fail", patches["app.services.harness_engine.harness_runs_service.fail"]),
        patch("app.services.harness_engine.harness_runs_service.cancel", patches["app.services.harness_engine.harness_runs_service.cancel"]),
        patch("app.services.harness_engine.harness_runs_service.get_run_by_id", patches["app.services.harness_engine.harness_runs_service.get_run_by_id"]),
        patch("app.services.harness_engine.WorkspaceService", return_value=ws_mock),
    ):
        events = await _collect(run_harness_engine(**_make_run_kwargs(harness, "run-42")))

    artifact_events = [e for e in events if e.get("type") == "harness_artifact"]
    assert len(artifact_events) == 1, "Expected exactly one harness_artifact event"

    artifact = artifact_events[0]
    assert artifact["ok"] is True
    assert artifact["docx_path"] == "review.docx"
    assert artifact["signed_url"] == "https://example.com/review.docx"
    assert artifact["harness_run_id"] == "run-42"
    assert artifact["harness_mode"] == "contract-review"

    # harness still completes successfully (D-22-15)
    complete_ev = next(e for e in events if e.get("type") == EVT_COMPLETE)
    assert complete_ev["status"] == "completed"


# ---------------------------------------------------------------------------
# Test 3: post_execute error dict → harness_artifact ok=False; status stays 'completed'
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_post_execute_error_dict_logged_no_status_change():
    """When post_execute returns an error dict the engine yields harness_artifact ok=False
    but harness_runs.status stays 'completed' (D-22-15 non-fatal fallback invariant)."""
    post_execute_mock = AsyncMock(return_value={
        "error": "docx_build_failed",
        "code": "DOCX_BUILD_ERROR",
        "detail": "python-docx crashed",
        "fallback_message": "DOCX generation failed — see chat for markdown summary.",
    })
    phase = _make_programmatic_phase(post_execute=post_execute_mock)
    harness = _make_harness(phases=[phase])
    ws_mock = _patch_workspace()

    complete_mock = AsyncMock(return_value=True)
    patches = _base_patches()
    patches["app.services.harness_engine.harness_runs_service.complete"] = complete_mock

    with (
        patch("app.services.harness_engine.agent_todos_service.write_todos", patches["app.services.harness_engine.agent_todos_service.write_todos"]),
        patch("app.services.harness_engine.harness_runs_service.advance_phase", patches["app.services.harness_engine.harness_runs_service.advance_phase"]),
        patch("app.services.harness_engine.harness_runs_service.complete", complete_mock),
        patch("app.services.harness_engine.harness_runs_service.fail", patches["app.services.harness_engine.harness_runs_service.fail"]),
        patch("app.services.harness_engine.harness_runs_service.cancel", patches["app.services.harness_engine.harness_runs_service.cancel"]),
        patch("app.services.harness_engine.harness_runs_service.get_run_by_id", patches["app.services.harness_engine.harness_runs_service.get_run_by_id"]),
        patch("app.services.harness_engine.WorkspaceService", return_value=ws_mock),
    ):
        events = await _collect(run_harness_engine(**_make_run_kwargs(harness)))

    # harness_artifact yielded with ok=False
    artifact_events = [e for e in events if e.get("type") == "harness_artifact"]
    assert len(artifact_events) == 1
    assert artifact_events[0]["ok"] is False
    assert artifact_events[0]["code"] == "DOCX_BUILD_ERROR"

    # harness_runs.complete() was still called (not fail())
    complete_mock.assert_called_once()
    fail_mock = patches["app.services.harness_engine.harness_runs_service.fail"]
    fail_mock.assert_not_called()

    # status is 'completed' in final event
    complete_ev = next(e for e in events if e.get("type") == EVT_COMPLETE)
    assert complete_ev["status"] == "completed"


# ---------------------------------------------------------------------------
# Test 4: post_execute raises exception → caught, logged, status stays 'completed'
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_post_execute_exception_caught_no_status_change():
    """If post_execute raises, engine catches it, yields harness_artifact ok=False with
    code=POST_EXEC_EXC, and harness_runs.status stays 'completed' (D-22-15)."""
    post_execute_mock = AsyncMock(side_effect=RuntimeError("DOCX engine exploded"))
    phase = _make_programmatic_phase(post_execute=post_execute_mock)
    harness = _make_harness(phases=[phase])
    ws_mock = _patch_workspace()

    fail_mock = AsyncMock(return_value=True)
    complete_mock = AsyncMock(return_value=True)
    patches = _base_patches()

    with (
        patch("app.services.harness_engine.agent_todos_service.write_todos", patches["app.services.harness_engine.agent_todos_service.write_todos"]),
        patch("app.services.harness_engine.harness_runs_service.advance_phase", patches["app.services.harness_engine.harness_runs_service.advance_phase"]),
        patch("app.services.harness_engine.harness_runs_service.complete", complete_mock),
        patch("app.services.harness_engine.harness_runs_service.fail", fail_mock),
        patch("app.services.harness_engine.harness_runs_service.cancel", patches["app.services.harness_engine.harness_runs_service.cancel"]),
        patch("app.services.harness_engine.harness_runs_service.get_run_by_id", patches["app.services.harness_engine.harness_runs_service.get_run_by_id"]),
        patch("app.services.harness_engine.WorkspaceService", return_value=ws_mock),
    ):
        events = await _collect(run_harness_engine(**_make_run_kwargs(harness)))

    artifact_events = [e for e in events if e.get("type") == "harness_artifact"]
    assert len(artifact_events) == 1
    artifact = artifact_events[0]
    assert artifact["ok"] is False
    assert artifact["code"] == "POST_EXEC_EXC"
    assert "DOCX engine exploded" in artifact["detail"]

    # fail() must NOT be called (D-22-15)
    fail_mock.assert_not_called()
    complete_mock.assert_called_once()

    complete_ev = next(e for e in events if e.get("type") == EVT_COMPLETE)
    assert complete_ev["status"] == "completed"


# ---------------------------------------------------------------------------
# Test 5: yield ordering — phase_complete → harness_artifact → workspace_updated → progress → harness_complete
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_post_execute_runs_after_last_phase_before_engine_complete():
    """Event order must be: phase_complete → harness_artifact → workspace_updated
    (if wrote_binary) → _append_progress → harness_complete.

    We verify: phase_complete appears before harness_artifact, which appears
    before harness_complete (workspace_updated between those two).
    """
    post_execute_mock = AsyncMock(return_value={
        "ok": True,
        "docx_path": "order-test.docx",
        "wrote_binary": True,
        "size_bytes": 1234,
    })
    phase = _make_programmatic_phase(post_execute=post_execute_mock)
    harness = _make_harness(phases=[phase])
    ws_mock = _patch_workspace()

    patches = _base_patches()
    with (
        patch("app.services.harness_engine.agent_todos_service.write_todos", patches["app.services.harness_engine.agent_todos_service.write_todos"]),
        patch("app.services.harness_engine.harness_runs_service.advance_phase", patches["app.services.harness_engine.harness_runs_service.advance_phase"]),
        patch("app.services.harness_engine.harness_runs_service.complete", patches["app.services.harness_engine.harness_runs_service.complete"]),
        patch("app.services.harness_engine.harness_runs_service.fail", patches["app.services.harness_engine.harness_runs_service.fail"]),
        patch("app.services.harness_engine.harness_runs_service.cancel", patches["app.services.harness_engine.harness_runs_service.cancel"]),
        patch("app.services.harness_engine.harness_runs_service.get_run_by_id", patches["app.services.harness_engine.harness_runs_service.get_run_by_id"]),
        patch("app.services.harness_engine.WorkspaceService", return_value=ws_mock),
    ):
        events = await _collect(run_harness_engine(**_make_run_kwargs(harness)))

    event_types = [e.get("type") for e in events]

    phase_complete_idx = next(i for i, t in enumerate(event_types) if t == EVT_PHASE_COMPLETE)
    artifact_idx = next(i for i, t in enumerate(event_types) if t == "harness_artifact")
    ws_updated_idx = next(i for i, t in enumerate(event_types) if t == "workspace_updated")
    harness_complete_idx = next(i for i, t in enumerate(event_types) if t == EVT_COMPLETE)

    assert phase_complete_idx < artifact_idx, "phase_complete must precede harness_artifact"
    assert artifact_idx < ws_updated_idx, "harness_artifact must precede workspace_updated"
    assert ws_updated_idx < harness_complete_idx, "workspace_updated must precede harness_complete"


# ---------------------------------------------------------------------------
# Test 6 (REVIEW #7): workspace_updated emitted when wrote_binary=True
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_post_execute_emits_workspace_updated_when_wrote_binary():
    """REVIEW #7: post_execute that wrote a binary file MUST trigger a workspace_updated
    event so the Workspace Panel re-renders (mirrors chat.py:1004 sandbox write pattern)."""
    post_execute_mock = AsyncMock(return_value={
        "ok": True,
        "docx_path": "contract-review-abc12345.docx",
        "signed_url": "https://example.com/x.docx",
        "wrote_binary": True,
        "size_bytes": 9876,
    })
    phase = _make_programmatic_phase(post_execute=post_execute_mock)
    harness = _make_harness(phases=[phase])
    ws_mock = _patch_workspace()

    patches = _base_patches()
    with (
        patch("app.services.harness_engine.agent_todos_service.write_todos", patches["app.services.harness_engine.agent_todos_service.write_todos"]),
        patch("app.services.harness_engine.harness_runs_service.advance_phase", patches["app.services.harness_engine.harness_runs_service.advance_phase"]),
        patch("app.services.harness_engine.harness_runs_service.complete", patches["app.services.harness_engine.harness_runs_service.complete"]),
        patch("app.services.harness_engine.harness_runs_service.fail", patches["app.services.harness_engine.harness_runs_service.fail"]),
        patch("app.services.harness_engine.harness_runs_service.cancel", patches["app.services.harness_engine.harness_runs_service.cancel"]),
        patch("app.services.harness_engine.harness_runs_service.get_run_by_id", patches["app.services.harness_engine.harness_runs_service.get_run_by_id"]),
        patch("app.services.harness_engine.WorkspaceService", return_value=ws_mock),
    ):
        events = await _collect(run_harness_engine(**_make_run_kwargs(harness)))

    artifact_events = [e for e in events if e.get("type") == "harness_artifact"]
    ws_updated_events = [e for e in events if e.get("type") == "workspace_updated"]

    assert len(artifact_events) == 1, "Should have one harness_artifact event"
    assert len(ws_updated_events) == 1, "REVIEW #7: Should have one workspace_updated event"

    # Ordering: artifact before workspace_updated
    artifact_idx = next(i for i, e in enumerate(events) if e.get("type") == "harness_artifact")
    ws_idx = next(i for i, e in enumerate(events) if e.get("type") == "workspace_updated")
    assert artifact_idx < ws_idx, "workspace_updated must follow harness_artifact"

    ws_ev = ws_updated_events[0]
    assert ws_ev["file_path"] == "contract-review-abc12345.docx"
    assert ws_ev["source"] == "harness"
    assert ws_ev["size_bytes"] == 9876
    assert ws_ev["operation"] == "create"


# ---------------------------------------------------------------------------
# Test 7 (REVIEW #8): harness_artifact event carries correlation fields
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_harness_artifact_event_carries_correlation_fields():
    """REVIEW #8: harness_artifact event must include harness_run_id AND harness_mode
    (the harness name) so the frontend reducer can correlate without heuristics."""
    post_execute_mock = AsyncMock(return_value={"ok": True, "docx_path": "x.docx"})
    phase = _make_programmatic_phase(post_execute=post_execute_mock)
    harness = _make_harness(name="contract-review", phases=[phase])
    ws_mock = _patch_workspace()

    patches = _base_patches()
    with (
        patch("app.services.harness_engine.agent_todos_service.write_todos", patches["app.services.harness_engine.agent_todos_service.write_todos"]),
        patch("app.services.harness_engine.harness_runs_service.advance_phase", patches["app.services.harness_engine.harness_runs_service.advance_phase"]),
        patch("app.services.harness_engine.harness_runs_service.complete", patches["app.services.harness_engine.harness_runs_service.complete"]),
        patch("app.services.harness_engine.harness_runs_service.fail", patches["app.services.harness_engine.harness_runs_service.fail"]),
        patch("app.services.harness_engine.harness_runs_service.cancel", patches["app.services.harness_engine.harness_runs_service.cancel"]),
        patch("app.services.harness_engine.harness_runs_service.get_run_by_id", patches["app.services.harness_engine.harness_runs_service.get_run_by_id"]),
        patch("app.services.harness_engine.WorkspaceService", return_value=ws_mock),
    ):
        events = await _collect(run_harness_engine(**_make_run_kwargs(harness, "run-42")))

    artifact = next(e for e in events if e.get("type") == "harness_artifact")
    assert artifact["harness_run_id"] == "run-42"
    assert artifact["harness_mode"] == "contract-review"
