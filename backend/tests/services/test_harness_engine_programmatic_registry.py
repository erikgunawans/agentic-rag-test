"""Phase 22 / REVIEW #4 — Tests for PROGRAMMATIC executor receiving registry kwargs.

REVIEW #4 finding: CR-05's internal LLM calls would BYPASS the SEC-04 egress-filter
path because the engine did not pass `registry` to programmatic executors.

These tests lock the fix:
1. test_engine_passes_registry_to_programmatic_executor — REVIEW #4 core invariant
2. test_engine_backward_compat_legacy_executor_without_registry_kwargs — legacy executors that don't accept new kwargs still work

These are RED tests — they will fail until Task 1 GREEN implementation is done.
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
from app.services.harness_engine import run_harness_engine


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


def _make_harness_with_executor(executor, name: str = "test-harness") -> HarnessDefinition:
    return HarnessDefinition(
        name=name,
        display_name="Test Harness",
        prerequisites=_make_prereqs(),
        phases=[
            PhaseDefinition(
                name="test-phase",
                phase_type=PhaseType.PROGRAMMATIC,
                executor=executor,
                timeout_seconds=60,
            ),
        ],
    )


def _patch_workspace():
    ws_instance = MagicMock()
    ws_instance.write_text_file = AsyncMock(return_value={"ok": True})
    ws_instance.read_file = AsyncMock(
        return_value={"ok": True, "content": "# Harness Progress\n"}
    )
    return ws_instance


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
# Test 1 (REVIEW #4): engine passes registry + system_settings + user_id + user_email
# to PROGRAMMATIC executors so they can wrap internal LLM calls in egress_filter.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_engine_passes_registry_to_programmatic_executor():
    """REVIEW #4: privacy invariant — engine MUST pass registry to programmatic
    executors so they can wrap any internal LLM call in egress_filter.

    The B4 single-registry invariant (chat.py:1851) flows from the chat router
    down through run_harness_engine → _dispatch_phase → executor. Without this
    path, CR-05's per-chunk LLM calls would bypass the SEC-04 egress filter.
    """
    captured_kwargs: dict = {}

    async def sentinel_executor(**kwargs):
        captured_kwargs.update(kwargs)
        return {"content": "ok"}

    harness = _make_harness_with_executor(sentinel_executor)
    mock_registry = MagicMock()
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
        events = await _collect(run_harness_engine(
            harness=harness,
            harness_run_id="run-r4-test",
            thread_id="thread-1",
            user_id="user-uuid-1",
            user_email="user@test.com",
            token="tok",
            registry=mock_registry,
            cancellation_event=asyncio.Event(),
        ))

    # REVIEW #4 core assertion: registry kwarg must reach the executor
    assert "registry" in captured_kwargs, (
        "REVIEW #4: registry kwarg missing from programmatic executor call. "
        "Fix: _dispatch_phase PROGRAMMATIC block must pass registry=registry to phase.executor()."
    )
    assert captured_kwargs["registry"] is mock_registry, (
        "REVIEW #4: executor received a different registry instance. "
        "Must be the same object — B4 single-registry invariant."
    )
    assert "user_id" in captured_kwargs, "user_id kwarg missing from executor call"
    assert captured_kwargs["user_id"] == "user-uuid-1"
    assert "user_email" in captured_kwargs, "user_email kwarg missing from executor call"
    assert captured_kwargs["user_email"] == "user@test.com"

    # Engine should still complete successfully
    complete_ev = next((e for e in events if e.get("type") == "harness_complete"), None)
    assert complete_ev is not None, "Engine must complete after programmatic phase"
    assert complete_ev["status"] == "completed"


# ---------------------------------------------------------------------------
# Test 2 (backward-compat): legacy executor that does NOT accept new kwargs
# is still invoked successfully — engine catches TypeError and retries with
# the old 4-kwarg signature so smoke_echo and pre-Phase-22 harnesses keep working.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_engine_backward_compat_legacy_executor_without_registry_kwargs():
    """Backward-compat: a legacy executor (only accepts inputs/token/thread_id/harness_run_id)
    must NOT crash the engine. The engine must catch TypeError on the new-signature call
    and retry with the legacy signature.

    This preserves smoke_echo._phase1_echo behavior for pre-Phase-22 harnesses that
    have not yet been updated to accept **_. smoke_echo itself is updated in plan 22-08
    with **_, but any external harness not under our control must also keep working.
    """
    call_log: list[str] = []

    async def legacy_executor(*, inputs: dict, token: str, thread_id: str, harness_run_id: str):
        """Strict 4-kwarg signature — no **_. Simulates a pre-Phase-22 executor."""
        call_log.append("legacy_called")
        return {"content": "legacy ok"}

    harness = _make_harness_with_executor(legacy_executor)
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
        events = await _collect(run_harness_engine(
            harness=harness,
            harness_run_id="run-legacy",
            thread_id="thread-2",
            user_id="user-2",
            user_email="legacy@test.com",
            token="tok2",
            registry=MagicMock(),
            cancellation_event=asyncio.Event(),
        ))

    # Legacy executor must have been called (via the fallback retry path)
    assert "legacy_called" in call_log, (
        "Legacy executor must be invoked via backward-compat retry. "
        "Engine must catch TypeError and retry without the new kwargs."
    )

    # Engine must still complete (not fail) — legacy executor works fine
    complete_ev = next((e for e in events if e.get("type") == "harness_complete"), None)
    assert complete_ev is not None
    assert complete_ev["status"] == "completed", (
        f"Legacy executor harness must complete, got: {complete_ev}"
    )
