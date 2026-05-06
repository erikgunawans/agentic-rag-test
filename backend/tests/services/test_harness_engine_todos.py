"""Phase 22 / UAT Gap 2 — regression test for write_todos signature propagation.

Catches the bug discovered in live UAT 2026-05-06 where harness_engine.py called
write_todos(thread_id, todos, token) — 3 args in wrong order — but the real
signature is (thread_id, user_id, user_email, token, todos). The error handler
itself crashed with the same TypeError, so harness failure was silent.

This test must NOT mock write_todos at the call boundary with a no-op AsyncMock
(the existing tests do that, which is why signature drift was invisible).
Instead it captures positional args and asserts the order matches the real
signature.
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
from app.services.harness_engine import _run_harness_engine_inner


# Canonical executor signature (matches test_harness_engine.py:67):
#   async def _executor(inputs, token, thread_id, harness_run_id) -> dict: ...
async def _ok_executor(inputs, token, thread_id, harness_run_id):
    return {"result": "ok", "text": "echo done"}


async def _crashing_executor(inputs, token, thread_id, harness_run_id):
    # Returning an error dict drives the engine through the error branch
    # (matches the failure-event contract used by other harness tests).
    raise RuntimeError("intentional failure for error-path coverage")


def _make_harness(executor) -> HarnessDefinition:
    """Build a one-phase programmatic harness with the canonical executor pattern."""
    return HarnessDefinition(
        name="smoke-echo",
        display_name="Smoke Echo",
        prerequisites=HarnessPrerequisites(harness_intro="x"),
        phases=[
            PhaseDefinition(
                name="echo",
                phase_type=PhaseType.PROGRAMMATIC,
                executor=executor,
                timeout_seconds=5,
            ),
        ],
    )


@pytest.mark.asyncio
async def test_write_todos_signature_propagation():
    """Engine must call write_todos with (thread_id, user_id, user_email, token, todos).

    Failure mode pre-fix: TypeError: write_todos() missing 2 required positional
    arguments: 'token' and 'todos'.
    """
    captured: list[tuple] = []

    async def capturing_write_todos(thread_id, user_id, user_email, token, todos):
        # Mirror real signature; capture in order.
        captured.append((thread_id, user_id, user_email, token, list(todos)))
        return []

    harness = _make_harness(_ok_executor)

    with patch(
        "app.services.harness_engine.agent_todos_service.write_todos",
        side_effect=capturing_write_todos,
    ), patch(
        "app.services.harness_engine.WorkspaceService"
    ) as mock_ws_cls, patch(
        "app.services.harness_engine.harness_runs_service.get_run_by_id",
        new_callable=AsyncMock,
        return_value={"status": "running"},
    ), patch(
        "app.services.harness_engine.harness_runs_service.advance_phase",
        new_callable=AsyncMock,
        return_value=True,
    ), patch(
        "app.services.harness_engine.harness_runs_service.complete",
        new_callable=AsyncMock,
        return_value=True,
    ):
        mock_ws = MagicMock()
        mock_ws.write_text_file = AsyncMock(return_value={"ok": True})
        mock_ws.read_file = AsyncMock(return_value={"ok": True, "content": "# Harness Progress\n"})
        mock_ws_cls.return_value = mock_ws

        events = []
        async for ev in _run_harness_engine_inner(
            harness=harness,
            harness_run_id="run-1",
            thread_id="thread-1",
            user_id="user-1",
            user_email="user@test.com",
            token="tok",
            registry=None,
            cancellation_event=asyncio.Event(),
            start_phase_index=0,
        ):
            events.append(ev)

    # At minimum: init + in_progress + completed = 3 write_todos calls per
    # successful programmatic phase. The error path (call site 4) is exercised
    # in the companion failure test below.
    assert len(captured) >= 3, (
        f"Expected >=3 write_todos calls (init/in_progress/completed); "
        f"got {len(captured)}"
    )

    for idx, args in enumerate(captured):
        assert args[0] == "thread-1", f"call {idx}: arg 0 (thread_id) wrong: {args[0]!r}"
        assert args[1] == "user-1", f"call {idx}: arg 1 (user_id) wrong: {args[1]!r}"
        assert args[2] == "user@test.com", f"call {idx}: arg 2 (user_email) wrong: {args[2]!r}"
        assert args[3] == "tok", f"call {idx}: arg 3 (token) wrong: {args[3]!r}"
        todos = args[4]
        assert isinstance(todos, list), f"call {idx}: arg 4 (todos) not list"
        for t in todos:
            assert "content" in t and "status" in t and "position" in t, (
                f"call {idx}: todo missing required keys: {t!r}"
            )


@pytest.mark.asyncio
async def test_write_todos_signature_propagation_error_path():
    """The error-path call site (line ~361 pre-fix) must also use the right signature.

    Drives a phase whose executor raises, which routes the engine through the
    'error' branch where write_todos is called once more.
    """
    captured: list[tuple] = []

    async def capturing_write_todos(thread_id, user_id, user_email, token, todos):
        captured.append((thread_id, user_id, user_email, token, list(todos)))
        return []

    harness = _make_harness(_crashing_executor)

    with patch(
        "app.services.harness_engine.agent_todos_service.write_todos",
        side_effect=capturing_write_todos,
    ), patch(
        "app.services.harness_engine.WorkspaceService"
    ) as mock_ws_cls, patch(
        "app.services.harness_engine.harness_runs_service.get_run_by_id",
        new_callable=AsyncMock,
        return_value={"status": "running"},
    ), patch(
        "app.services.harness_engine.harness_runs_service.fail",
        new_callable=AsyncMock,
        return_value=True,
    ), patch(
        "app.services.harness_engine.harness_runs_service.advance_phase",
        new_callable=AsyncMock,
        return_value=True,
    ):
        mock_ws = MagicMock()
        mock_ws.write_text_file = AsyncMock(return_value={"ok": True})
        mock_ws.read_file = AsyncMock(return_value={"ok": True, "content": "# Harness Progress\n"})
        mock_ws_cls.return_value = mock_ws

        async for _ in _run_harness_engine_inner(
            harness=harness,
            harness_run_id="run-2",
            thread_id="thread-2",
            user_id="user-2",
            user_email="u2@test.com",
            token="tok2",
            registry=None,
            cancellation_event=asyncio.Event(),
            start_phase_index=0,
        ):
            pass

    # init + in_progress + error = 3 calls minimum on failure path.
    assert len(captured) >= 3, f"Expected >=3 write_todos calls on error path; got {len(captured)}"
    for args in captured:
        assert args[0] == "thread-2"
        assert args[1] == "user-2"
        assert args[2] == "u2@test.com"
        assert args[3] == "tok2"
        assert isinstance(args[4], list)
