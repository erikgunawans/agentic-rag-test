"""Phase 21 / Plan 21-04 — Tests for HIL resume branch in chat.py.

7 tests covering:
1.  test_hil_resume_detects_paused_status — paused row triggers SSE (200), not 409.
2.  test_hil_resume_writes_answer_to_workspace — body.message → phase.workspace_output.
3.  test_hil_resume_calls_resume_from_pause_with_next_index — resume_from_pause(new_phase_index=current+1)
    AND advance_phase NOT called (BLOCKER-2 regression).
4.  test_hil_resume_calls_run_harness_engine_with_start_phase_index — start_phase_index=current+1.
5.  test_hil_resume_persists_user_message_with_harness_mode — messages insert tagged with
    harness_mode=harness_type.
6.  test_409_only_blocks_pending_running — parametrized (pending → 409, running → 409,
    paused → 200 SSE, None → 200 normal flow).
7.  test_hil_resume_returns_500_when_resume_from_pause_returns_none — stale-state guard surfaces 500.
"""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.harnesses.types import (
    HarnessDefinition,
    HarnessPrerequisites,
    PhaseDefinition,
    PhaseType,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _make_prereqs(requires_upload: bool = True) -> HarnessPrerequisites:
    return HarnessPrerequisites(
        requires_upload=requires_upload,
        upload_description="your contract DOCX or PDF",
        accepted_mime_types=["application/pdf"],
        min_files=1,
        max_files=1,
        harness_intro="This harness reviews your contract.",
    )


def _make_harness_with_hil_phase() -> HarnessDefinition:
    """4-phase harness with HIL phase at index 2 (workspace_output='test-answer.md')."""
    phases = [
        PhaseDefinition(name="phase-0", phase_type=PhaseType.PROGRAMMATIC),
        PhaseDefinition(name="phase-1", phase_type=PhaseType.PROGRAMMATIC),
        PhaseDefinition(
            name="ask-label",
            phase_type=PhaseType.LLM_HUMAN_INPUT,
            system_prompt_template="What label?",
            workspace_inputs=[],
            workspace_output="test-answer.md",
        ),
        PhaseDefinition(name="phase-3", phase_type=PhaseType.PROGRAMMATIC),
    ]
    return HarnessDefinition(
        name="smoke-echo",
        display_name="Smoke Echo",
        prerequisites=_make_prereqs(requires_upload=True),
        phases=phases,
    )


def _mock_user():
    return {"id": "user-1", "email": "user@test.com", "token": "tok", "role": "user"}


def _make_paused_run(current_phase: int = 2) -> dict:
    return {
        "id": "run-1",
        "thread_id": "thread-1",
        "user_id": "user-1",
        "harness_type": "smoke-echo",
        "status": "paused",
        "current_phase": current_phase,
        "phase_results": {},
        "input_file_ids": [],
        "error_detail": None,
        "created_at": "2026-05-04T00:00:00Z",
        "updated_at": "2026-05-04T00:00:01Z",
    }


def _make_active_run(status: str = "running", current_phase: int = 1) -> dict:
    return {
        "id": "run-2",
        "thread_id": "thread-1",
        "user_id": "user-1",
        "harness_type": "smoke-echo",
        "status": status,
        "current_phase": current_phase,
        "phase_results": {},
        "input_file_ids": [],
        "error_detail": None,
        "created_at": "2026-05-04T00:00:00Z",
        "updated_at": "2026-05-04T00:00:01Z",
    }


def _make_thread_owner_client() -> MagicMock:
    """Mock supabase client returning the owned thread for the ownership check."""
    mock_client = MagicMock()
    chain = MagicMock()
    mock_client.table.return_value = chain
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.limit.return_value = chain
    chain.order.return_value = chain
    chain.maybe_single.return_value = chain
    chain.insert.return_value = chain
    chain.update.return_value = chain
    chain.execute.return_value = MagicMock(data=[{"id": "thread-1"}])
    return mock_client


async def _empty_harness_engine_gen(*args, **kwargs):
    """Test stub for run_harness_engine — yields a single completion event then ends."""
    yield {"type": "harness_complete", "status": "completed", "harness_run_id": "run-1"}


def _patch_run_engine_returning_empty():
    """Patch run_harness_engine with an async-generator that yields one event."""
    return patch(
        "app.routers.chat.run_harness_engine",
        side_effect=_empty_harness_engine_gen,
    )


# ---------------------------------------------------------------------------
# 1. test_hil_resume_detects_paused_status
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_hil_resume_detects_paused_status():
    """HIL resume: paused row triggers SSE (200), not 409."""
    from app.routers.chat import router
    from app.dependencies import get_current_user

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: _mock_user()

    harness = _make_harness_with_hil_phase()
    paused_run = _make_paused_run(current_phase=2)
    mock_client = _make_thread_owner_client()

    mock_ws_instance = MagicMock()
    mock_ws_instance.write_text_file = AsyncMock(return_value={"ok": True, "operation": "create"})

    with patch("app.routers.chat.get_supabase_client", return_value=mock_client), \
         patch("app.routers.chat.settings") as mock_settings, \
         patch("app.routers.chat.harness_runs_service.get_active_run", new_callable=AsyncMock, return_value=paused_run), \
         patch("app.routers.chat.harness_runs_service.resume_from_pause", new_callable=AsyncMock, return_value=paused_run) as mock_resume, \
         patch("app.routers.chat.harness_runs_service.advance_phase", new_callable=AsyncMock) as mock_advance, \
         patch("app.routers.chat.harness_registry.get_harness", return_value=harness), \
         patch("app.routers.chat.WorkspaceService", return_value=mock_ws_instance), \
         patch("app.routers.chat.get_supabase_authed_client", return_value=mock_client), \
         _patch_run_engine_returning_empty():
        mock_settings.harness_enabled = True
        mock_settings.sub_agent_enabled = False
        mock_settings.deep_mode_enabled = False

        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(
            "/chat/stream",
            json={"thread_id": "thread-1", "message": "Test answer 123", "parent_message_id": None},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    mock_resume.assert_awaited_once()
    mock_advance.assert_not_called()  # BLOCKER-2: never use advance_phase on paused rows


# ---------------------------------------------------------------------------
# 2. test_hil_resume_writes_answer_to_workspace
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_hil_resume_writes_answer_to_workspace():
    """HIL resume: body.message → phase.workspace_output via WorkspaceService.write_text_file."""
    from app.routers.chat import router
    from app.dependencies import get_current_user

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: _mock_user()

    harness = _make_harness_with_hil_phase()
    paused_run = _make_paused_run(current_phase=2)
    mock_client = _make_thread_owner_client()

    mock_ws_instance = MagicMock()
    mock_ws_instance.write_text_file = AsyncMock(return_value={"ok": True, "operation": "create"})

    with patch("app.routers.chat.get_supabase_client", return_value=mock_client), \
         patch("app.routers.chat.settings") as mock_settings, \
         patch("app.routers.chat.harness_runs_service.get_active_run", new_callable=AsyncMock, return_value=paused_run), \
         patch("app.routers.chat.harness_runs_service.resume_from_pause", new_callable=AsyncMock, return_value=paused_run), \
         patch("app.routers.chat.harness_runs_service.advance_phase", new_callable=AsyncMock), \
         patch("app.routers.chat.harness_registry.get_harness", return_value=harness), \
         patch("app.routers.chat.WorkspaceService", return_value=mock_ws_instance) as mock_ws_cls, \
         patch("app.routers.chat.get_supabase_authed_client", return_value=mock_client), \
         _patch_run_engine_returning_empty():
        mock_settings.harness_enabled = True
        mock_settings.sub_agent_enabled = False
        mock_settings.deep_mode_enabled = False

        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(
            "/chat/stream",
            json={"thread_id": "thread-1", "message": "Test answer 123", "parent_message_id": None},
        )

    assert response.status_code == 200
    mock_ws_cls.assert_called_once_with(token="tok")
    mock_ws_instance.write_text_file.assert_awaited_once()
    call_args = mock_ws_instance.write_text_file.await_args
    # write_text_file(thread_id, file_path, content, source="harness")
    args, kwargs = call_args.args, call_args.kwargs
    # Accept positional or keyword argument shapes
    if args:
        assert args[0] == "thread-1"
        assert args[1] == "test-answer.md"
        assert args[2] == "Test answer 123"
    else:
        assert kwargs.get("thread_id") == "thread-1"
        assert kwargs.get("file_path") == "test-answer.md"
        assert kwargs.get("content") == "Test answer 123"
    assert kwargs.get("source") == "harness"


# ---------------------------------------------------------------------------
# 3. test_hil_resume_calls_resume_from_pause_with_next_index
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_hil_resume_calls_resume_from_pause_with_next_index():
    """HIL resume: resume_from_pause invoked with new_phase_index=current+1 + phase_results_patch.
    BLOCKER-2 regression: advance_phase MUST NOT be called on paused rows."""
    from app.routers.chat import router
    from app.dependencies import get_current_user

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: _mock_user()

    harness = _make_harness_with_hil_phase()
    paused_run = _make_paused_run(current_phase=2)
    mock_client = _make_thread_owner_client()

    mock_ws_instance = MagicMock()
    mock_ws_instance.write_text_file = AsyncMock(return_value={"ok": True, "operation": "create"})

    with patch("app.routers.chat.get_supabase_client", return_value=mock_client), \
         patch("app.routers.chat.settings") as mock_settings, \
         patch("app.routers.chat.harness_runs_service.get_active_run", new_callable=AsyncMock, return_value=paused_run), \
         patch("app.routers.chat.harness_runs_service.resume_from_pause", new_callable=AsyncMock, return_value=paused_run) as mock_resume, \
         patch("app.routers.chat.harness_runs_service.advance_phase", new_callable=AsyncMock) as mock_advance, \
         patch("app.routers.chat.harness_registry.get_harness", return_value=harness), \
         patch("app.routers.chat.WorkspaceService", return_value=mock_ws_instance), \
         patch("app.routers.chat.get_supabase_authed_client", return_value=mock_client), \
         _patch_run_engine_returning_empty():
        mock_settings.harness_enabled = True
        mock_settings.sub_agent_enabled = False
        mock_settings.deep_mode_enabled = False

        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(
            "/chat/stream",
            json={"thread_id": "thread-1", "message": "Test answer 123", "parent_message_id": None},
        )

    assert response.status_code == 200
    mock_resume.assert_awaited_once()
    kwargs = mock_resume.await_args.kwargs
    assert kwargs["run_id"] == "run-1"
    assert kwargs["new_phase_index"] == 3  # current_phase 2 + 1
    assert "2" in kwargs["phase_results_patch"]
    patch_dict = kwargs["phase_results_patch"]["2"]
    assert patch_dict["phase_name"] == "ask-label"
    assert patch_dict["output"]["answer"] == "Test answer 123"
    # BLOCKER-2: advance_phase MUST NOT be called for paused rows.
    mock_advance.assert_not_called()


# ---------------------------------------------------------------------------
# 4. test_hil_resume_calls_run_harness_engine_with_start_phase_index
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_hil_resume_calls_run_harness_engine_with_start_phase_index():
    """HIL resume: run_harness_engine awaited with start_phase_index=current+1."""
    from app.routers.chat import router
    from app.dependencies import get_current_user

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: _mock_user()

    harness = _make_harness_with_hil_phase()
    paused_run = _make_paused_run(current_phase=2)
    mock_client = _make_thread_owner_client()

    mock_ws_instance = MagicMock()
    mock_ws_instance.write_text_file = AsyncMock(return_value={"ok": True, "operation": "create"})

    captured_kwargs: dict = {}

    async def _capture_engine(*args, **kwargs):
        captured_kwargs.update(kwargs)
        yield {"type": "harness_complete", "status": "completed", "harness_run_id": "run-1"}

    with patch("app.routers.chat.get_supabase_client", return_value=mock_client), \
         patch("app.routers.chat.settings") as mock_settings, \
         patch("app.routers.chat.harness_runs_service.get_active_run", new_callable=AsyncMock, return_value=paused_run), \
         patch("app.routers.chat.harness_runs_service.resume_from_pause", new_callable=AsyncMock, return_value=paused_run), \
         patch("app.routers.chat.harness_runs_service.advance_phase", new_callable=AsyncMock), \
         patch("app.routers.chat.harness_registry.get_harness", return_value=harness), \
         patch("app.routers.chat.WorkspaceService", return_value=mock_ws_instance), \
         patch("app.routers.chat.get_supabase_authed_client", return_value=mock_client), \
         patch("app.routers.chat.run_harness_engine", side_effect=_capture_engine):
        mock_settings.harness_enabled = True
        mock_settings.sub_agent_enabled = False
        mock_settings.deep_mode_enabled = False

        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(
            "/chat/stream",
            json={"thread_id": "thread-1", "message": "Test answer 123", "parent_message_id": None},
        )
        # Drain SSE stream to ensure run_harness_engine is invoked.
        _body = response.read()

    assert response.status_code == 200
    assert captured_kwargs.get("start_phase_index") == 3  # current_phase 2 + 1
    assert captured_kwargs.get("harness_run_id") == "run-1"
    assert captured_kwargs.get("thread_id") == "thread-1"


# ---------------------------------------------------------------------------
# 5. test_hil_resume_persists_user_message_with_harness_mode
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_hil_resume_persists_user_message_with_harness_mode():
    """HIL resume: user message persisted with harness_mode=harness_type."""
    from app.routers.chat import router
    from app.dependencies import get_current_user

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: _mock_user()

    harness = _make_harness_with_hil_phase()
    paused_run = _make_paused_run(current_phase=2)

    # Capture insert calls
    captured_inserts: list[dict] = []

    class _InsertCapture:
        def __init__(self):
            self.data = [{"id": "msg-1"}]

        def execute(self):
            return MagicMock(data=[{"id": "msg-1"}])

    class _Chain:
        def __init__(self):
            pass

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
            return _InsertCapture()

        def update(self, *a, **kw):
            return self

        def execute(self):
            return MagicMock(data=[{"id": "thread-1"}])

    mock_client = MagicMock()
    mock_client.table = lambda *a, **kw: _Chain()

    mock_ws_instance = MagicMock()
    mock_ws_instance.write_text_file = AsyncMock(return_value={"ok": True, "operation": "create"})

    with patch("app.routers.chat.get_supabase_client", return_value=mock_client), \
         patch("app.routers.chat.settings") as mock_settings, \
         patch("app.routers.chat.harness_runs_service.get_active_run", new_callable=AsyncMock, return_value=paused_run), \
         patch("app.routers.chat.harness_runs_service.resume_from_pause", new_callable=AsyncMock, return_value=paused_run), \
         patch("app.routers.chat.harness_runs_service.advance_phase", new_callable=AsyncMock), \
         patch("app.routers.chat.harness_registry.get_harness", return_value=harness), \
         patch("app.routers.chat.WorkspaceService", return_value=mock_ws_instance), \
         patch("app.routers.chat.get_supabase_authed_client", return_value=mock_client), \
         _patch_run_engine_returning_empty():
        mock_settings.harness_enabled = True
        mock_settings.sub_agent_enabled = False
        mock_settings.deep_mode_enabled = False

        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(
            "/chat/stream",
            json={"thread_id": "thread-1", "message": "Test answer 123", "parent_message_id": None},
        )

    assert response.status_code == 200
    # At least one captured insert payload should match HIL message tagging.
    matches = [
        p for p in captured_inserts
        if p.get("role") == "user"
        and p.get("content") == "Test answer 123"
        and p.get("harness_mode") == "smoke-echo"
    ]
    assert len(matches) >= 1, f"expected harness-tagged user insert; got {captured_inserts}"


# ---------------------------------------------------------------------------
# 6. test_409_only_blocks_pending_running
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "status,expected_code",
    [("pending", 409), ("running", 409), ("paused", 200), (None, 200)],
)
@pytest.mark.asyncio
async def test_409_only_blocks_pending_running(status, expected_code):
    """409 narrowed: only pending/running. paused → SSE; None → normal flow (200)."""
    from app.routers.chat import router
    from app.dependencies import get_current_user

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: _mock_user()

    harness = _make_harness_with_hil_phase()
    if status is None:
        active_run = None
    elif status == "paused":
        active_run = _make_paused_run(current_phase=2)
    else:
        active_run = _make_active_run(status=status, current_phase=1)

    mock_client = _make_thread_owner_client()

    mock_ws_instance = MagicMock()
    mock_ws_instance.write_text_file = AsyncMock(return_value={"ok": True, "operation": "create"})

    with patch("app.routers.chat.get_supabase_client", return_value=mock_client), \
         patch("app.routers.chat.settings") as mock_settings, \
         patch("app.routers.chat.harness_runs_service.get_active_run", new_callable=AsyncMock, return_value=active_run), \
         patch("app.routers.chat.harness_runs_service.get_latest_for_thread", new_callable=AsyncMock, return_value=None), \
         patch("app.routers.chat.harness_runs_service.resume_from_pause", new_callable=AsyncMock, return_value=active_run if status == "paused" else None), \
         patch("app.routers.chat.harness_runs_service.advance_phase", new_callable=AsyncMock), \
         patch("app.routers.chat.harness_registry.get_harness", return_value=harness), \
         patch("app.routers.chat.harness_registry.list_harnesses", return_value=[]), \
         patch("app.routers.chat.WorkspaceService", return_value=mock_ws_instance), \
         patch("app.routers.chat.get_supabase_authed_client", return_value=mock_client), \
         patch("app.routers.chat._gatekeeper_stream_wrapper") as mock_gk, \
         _patch_run_engine_returning_empty():
        mock_settings.harness_enabled = True
        mock_settings.sub_agent_enabled = False
        mock_settings.deep_mode_enabled = False
        # Prevent gatekeeper from being awaited in normal-flow case
        mock_gk.return_value = iter([])

        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(
            "/chat/stream",
            json={"thread_id": "thread-1", "message": "Hello", "parent_message_id": None},
        )

    if expected_code == 409:
        assert response.status_code == 409, f"status={status} expected 409 got {response.status_code}"
        payload = response.json()
        assert payload["error"] == "harness_in_progress"
    else:
        # Either paused (200 SSE) or no active (200 normal). Both must NOT be 409.
        assert response.status_code != 409, (
            f"status={status} unexpectedly returned 409 (body={response.text})"
        )


# ---------------------------------------------------------------------------
# 7. test_hil_resume_returns_500_when_resume_from_pause_returns_none
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_hil_resume_returns_500_when_resume_from_pause_returns_none():
    """BLOCKER-2 regression: stale-state guard surfaces 500 with hil_resume_state_invalid.
    run_harness_engine MUST NOT be invoked."""
    from app.routers.chat import router
    from app.dependencies import get_current_user

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: _mock_user()

    harness = _make_harness_with_hil_phase()
    paused_run = _make_paused_run(current_phase=2)
    mock_client = _make_thread_owner_client()

    mock_ws_instance = MagicMock()
    mock_ws_instance.write_text_file = AsyncMock(return_value={"ok": True, "operation": "create"})

    engine_invoked = {"called": False}

    async def _engine_should_not_be_called(*args, **kwargs):
        engine_invoked["called"] = True
        if False:
            yield {}

    with patch("app.routers.chat.get_supabase_client", return_value=mock_client), \
         patch("app.routers.chat.settings") as mock_settings, \
         patch("app.routers.chat.harness_runs_service.get_active_run", new_callable=AsyncMock, return_value=paused_run), \
         patch("app.routers.chat.harness_runs_service.resume_from_pause", new_callable=AsyncMock, return_value=None), \
         patch("app.routers.chat.harness_runs_service.advance_phase", new_callable=AsyncMock), \
         patch("app.routers.chat.harness_registry.get_harness", return_value=harness), \
         patch("app.routers.chat.WorkspaceService", return_value=mock_ws_instance), \
         patch("app.routers.chat.get_supabase_authed_client", return_value=mock_client), \
         patch("app.routers.chat.run_harness_engine", side_effect=_engine_should_not_be_called):
        mock_settings.harness_enabled = True
        mock_settings.sub_agent_enabled = False
        mock_settings.deep_mode_enabled = False

        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(
            "/chat/stream",
            json={"thread_id": "thread-1", "message": "Test answer 123", "parent_message_id": None},
        )

    assert response.status_code == 500
    payload = response.json()
    assert payload["error"] == "hil_resume_state_invalid"
    assert engine_invoked["called"] is False
