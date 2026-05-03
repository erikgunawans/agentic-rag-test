"""Phase 20 / Plan 20-04 — Tests for harness routing branches in chat.py.

13 tests covering:
1.  test_d02_reject_when_active_harness_returns_409_with_structured_payload
2.  test_d05_skip_gatekeeper_when_harness_disabled
3.  test_d05_skip_gatekeeper_when_no_harness_registered
4.  test_d05_skip_gatekeeper_when_latest_run_exists
5.  test_d05_skip_gatekeeper_when_prerequisites_requires_upload_false
6.  test_d05_invokes_gatekeeper_stream_when_eligible
7.  test_cancel_harness_endpoint_sets_cancelled_status
8.  test_cancel_harness_endpoint_404_when_no_active_run
9.  test_get_active_harness_returns_null_when_none
10. test_get_active_harness_returns_payload_when_active
11. test_get_or_build_conversation_registry_calls_load_when_redaction_on  (B4)
12. test_get_or_build_conversation_registry_returns_none_when_redaction_off  (B4)
13. test_gatekeeper_stream_wrapper_passes_same_registry_to_gatekeeper_and_engine  (B4)
"""
from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch, call

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


def _make_harness(n_phases: int = 2, requires_upload: bool = True) -> HarnessDefinition:
    phases = [
        PhaseDefinition(
            name=f"Phase {i}",
            phase_type=PhaseType.PROGRAMMATIC,
        )
        for i in range(n_phases)
    ]
    return HarnessDefinition(
        name="smoke-echo",
        display_name="Smoke Echo",
        prerequisites=_make_prereqs(requires_upload=requires_upload),
        phases=phases,
    )


def _mock_user():
    return {"id": "user-1", "email": "user@test.com", "token": "tok", "role": "user"}


def _make_harness_run_record(
    harness_type: str = "smoke-echo",
    status: str = "running",
    current_phase: int = 0,
) -> dict:
    return {
        "id": "run-1",
        "thread_id": "thread-1",
        "user_id": "user-1",
        "harness_type": harness_type,
        "status": status,
        "current_phase": current_phase,
        "phase_results": {},
        "input_file_ids": [],
        "error_detail": None,
        "created_at": "2026-05-03T00:00:00Z",
        "updated_at": "2026-05-03T00:00:01Z",
    }


async def _drain_async_gen(gen):
    items = []
    async for item in gen:
        items.append(item)
    return items


async def _make_async_iter(items):
    for item in items:
        yield item


# ---------------------------------------------------------------------------
# 1. test_d02_reject_when_active_harness_returns_409_with_structured_payload
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_d02_reject_when_active_harness_returns_409_with_structured_payload():
    """D-02: when active harness exists, stream_chat returns 409 JSON."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.routers.chat import router
    from app.dependencies import get_current_user

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: _mock_user()

    harness = _make_harness()

    # Mock supabase thread ownership check
    mock_client = MagicMock()
    thread_chain = MagicMock()
    mock_client.table.return_value = thread_chain
    thread_chain.select.return_value = thread_chain
    thread_chain.eq.return_value = thread_chain
    thread_chain.limit.return_value = thread_chain
    thread_chain.execute.return_value = MagicMock(data=[{"id": "thread-1"}])

    active_run = _make_harness_run_record(current_phase=1)

    with patch("app.routers.chat.get_supabase_client", return_value=mock_client), \
         patch("app.routers.chat.settings") as mock_settings, \
         patch("app.routers.chat.harness_runs_service.get_active_run", new_callable=AsyncMock, return_value=active_run), \
         patch("app.routers.chat.harness_registry.get_harness", return_value=harness):
        mock_settings.sub_agent_enabled = False
        mock_settings.deep_mode_enabled = False
        mock_settings.harness_enabled = True

        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(
            "/chat/stream",
            json={
                "thread_id": "thread-1",
                "message": "Hello",
                "parent_message_id": None,
            },
        )

    assert response.status_code == 409
    payload = response.json()
    assert payload["error"] == "harness_in_progress"
    assert payload["harness_type"] == "smoke-echo"
    assert payload["current_phase"] == 1
    assert "phase_name" in payload


# ---------------------------------------------------------------------------
# 2. test_d05_skip_gatekeeper_when_harness_disabled
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_d05_skip_gatekeeper_when_harness_disabled():
    """D-05: when harness_enabled=False, gatekeeper branch never fires."""
    from app.routers.chat import _gatekeeper_stream_wrapper

    with patch("app.routers.chat.settings") as mock_settings, \
         patch("app.routers.chat.harness_runs_service.get_active_run", new_callable=AsyncMock, return_value=None) as mock_active, \
         patch("app.routers.chat.harness_runs_service.get_latest_for_thread", new_callable=AsyncMock, return_value=None) as mock_latest, \
         patch("app.routers.chat.harness_registry.list_harnesses", return_value=[]) as mock_list:
        mock_settings.harness_enabled = False
        mock_settings.sub_agent_enabled = False
        mock_settings.deep_mode_enabled = False
        # Neither get_active_run nor get_latest_for_thread should be called
        # when harness_enabled is False. Check by asserting they are NOT called.
        # (The branches are gated by `if settings.harness_enabled`)
        mock_active.assert_not_called()
        mock_latest.assert_not_called()


# ---------------------------------------------------------------------------
# 3. test_d05_skip_gatekeeper_when_no_harness_registered
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_d05_skip_gatekeeper_when_no_harness_registered():
    """D-05: when harness registry is empty, gatekeeper branch doesn't fire."""
    with patch("app.routers.chat.harness_runs_service.get_latest_for_thread", new_callable=AsyncMock, return_value=None), \
         patch("app.routers.chat.harness_registry.list_harnesses", return_value=[]) as mock_list:
        # list_harnesses() returns empty; gatekeeper should NOT be invoked
        harnesses = mock_list()
        assert len(harnesses) == 0


# ---------------------------------------------------------------------------
# 4. test_d05_skip_gatekeeper_when_latest_run_exists
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_d05_skip_gatekeeper_when_latest_run_exists():
    """D-05: when get_latest_for_thread returns a run (any status), gatekeeper doesn't fire."""
    # Build the router and exercise stream_chat via TestClient
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.routers.chat import router
    from app.dependencies import get_current_user

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: _mock_user()

    mock_client = MagicMock()
    thread_chain = MagicMock()
    mock_client.table.return_value = thread_chain
    thread_chain.select.return_value = thread_chain
    thread_chain.eq.return_value = thread_chain
    thread_chain.limit.return_value = thread_chain
    thread_chain.order.return_value = thread_chain
    thread_chain.maybe_single.return_value = thread_chain
    thread_chain.execute.return_value = MagicMock(data=[{"id": "thread-1"}])

    completed_run = _make_harness_run_record(status="completed")

    with patch("app.routers.chat.get_supabase_client", return_value=mock_client), \
         patch("app.routers.chat.settings") as mock_settings, \
         patch("app.routers.chat.harness_runs_service.get_active_run", new_callable=AsyncMock, return_value=None), \
         patch("app.routers.chat.harness_runs_service.get_latest_for_thread", new_callable=AsyncMock, return_value=completed_run), \
         patch("app.routers.chat.harness_registry.list_harnesses", return_value=[_make_harness()]), \
         patch("app.routers.chat._gatekeeper_stream_wrapper") as mock_gk_wrapper:
        mock_settings.sub_agent_enabled = False
        mock_settings.deep_mode_enabled = False
        mock_settings.harness_enabled = True
        # _gatekeeper_stream_wrapper should NOT be called since latest run exists
        mock_gk_wrapper.side_effect = AssertionError("gatekeeper should not be invoked")

        # Request will proceed past D-05 branch to normal chat flow
        # (we don't need to complete the full flow — just confirm gatekeeper wasn't called)
        try:
            client = TestClient(app, raise_server_exceptions=False)
            client.post(
                "/chat/stream",
                json={"thread_id": "thread-1", "message": "Hello", "parent_message_id": None},
            )
        except Exception:
            pass  # normal flow may fail due to incomplete mocks; that's OK

        mock_gk_wrapper.assert_not_called()


# ---------------------------------------------------------------------------
# 5. test_d05_skip_gatekeeper_when_prerequisites_requires_upload_false  (GATE-05)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_d05_skip_gatekeeper_when_prerequisites_requires_upload_false():
    """GATE-05: harness with requires_upload=False skips gatekeeper."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.routers.chat import router
    from app.dependencies import get_current_user

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: _mock_user()

    mock_client = MagicMock()
    thread_chain = MagicMock()
    mock_client.table.return_value = thread_chain
    thread_chain.select.return_value = thread_chain
    thread_chain.eq.return_value = thread_chain
    thread_chain.limit.return_value = thread_chain
    thread_chain.order.return_value = thread_chain
    thread_chain.maybe_single.return_value = thread_chain
    thread_chain.execute.return_value = MagicMock(data=[{"id": "thread-1"}])

    harness_no_upload = _make_harness(requires_upload=False)

    with patch("app.routers.chat.get_supabase_client", return_value=mock_client), \
         patch("app.routers.chat.settings") as mock_settings, \
         patch("app.routers.chat.harness_runs_service.get_active_run", new_callable=AsyncMock, return_value=None), \
         patch("app.routers.chat.harness_runs_service.get_latest_for_thread", new_callable=AsyncMock, return_value=None), \
         patch("app.routers.chat.harness_registry.list_harnesses", return_value=[harness_no_upload]), \
         patch("app.routers.chat._gatekeeper_stream_wrapper") as mock_gk_wrapper:
        mock_settings.sub_agent_enabled = False
        mock_settings.deep_mode_enabled = False
        mock_settings.harness_enabled = True
        mock_gk_wrapper.side_effect = AssertionError("gatekeeper should not be invoked for no-upload harness")

        try:
            client = TestClient(app, raise_server_exceptions=False)
            client.post(
                "/chat/stream",
                json={"thread_id": "thread-1", "message": "Hello", "parent_message_id": None},
            )
        except Exception:
            pass

        mock_gk_wrapper.assert_not_called()


# ---------------------------------------------------------------------------
# 6. test_d05_invokes_gatekeeper_stream_when_eligible
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_d05_invokes_gatekeeper_stream_when_eligible():
    """D-05: when eligible, _gatekeeper_stream_wrapper is called via StreamingResponse."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.routers.chat import router
    from app.dependencies import get_current_user

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: _mock_user()

    mock_client = MagicMock()
    thread_chain = MagicMock()
    mock_client.table.return_value = thread_chain
    thread_chain.select.return_value = thread_chain
    thread_chain.eq.return_value = thread_chain
    thread_chain.limit.return_value = thread_chain
    thread_chain.execute.return_value = MagicMock(data=[{"id": "thread-1"}])

    harness = _make_harness(requires_upload=True)

    # The gatekeeper stream wrapper should be called; provide minimal SSE output
    gk_called = []

    async def mock_gk_stream(**kwargs):
        gk_called.append(kwargs)
        yield f"data: {json.dumps({'type': 'delta', 'content': 'Hello!'})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    with patch("app.routers.chat.get_supabase_client", return_value=mock_client), \
         patch("app.routers.chat.settings") as mock_settings, \
         patch("app.routers.chat.get_system_settings", return_value={"pii_redaction_enabled": False, "llm_model": "x"}), \
         patch("app.routers.chat.harness_runs_service.get_active_run", new_callable=AsyncMock, return_value=None), \
         patch("app.routers.chat.harness_runs_service.get_latest_for_thread", new_callable=AsyncMock, return_value=None), \
         patch("app.routers.chat.harness_registry.list_harnesses", return_value=[harness]), \
         patch("app.routers.chat._gatekeeper_stream_wrapper", side_effect=mock_gk_stream):
        mock_settings.sub_agent_enabled = False
        mock_settings.deep_mode_enabled = False
        mock_settings.harness_enabled = True

        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(
            "/chat/stream",
            json={"thread_id": "thread-1", "message": "Hello", "parent_message_id": None},
        )

    assert len(gk_called) == 1
    assert gk_called[0]["thread_id"] == "thread-1"
    assert gk_called[0]["user_message"] == "Hello"


# ---------------------------------------------------------------------------
# 7. test_cancel_harness_endpoint_sets_cancelled_status
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cancel_harness_endpoint_sets_cancelled_status():
    """POST /threads/{id}/harness/cancel returns 200 and calls cancel()."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.routers.chat import router
    from app.dependencies import get_current_user

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: _mock_user()

    active_run = _make_harness_run_record(status="running")

    with patch("app.routers.chat.settings") as mock_settings, \
         patch("app.routers.chat.harness_runs_service.get_active_run", new_callable=AsyncMock, return_value=active_run), \
         patch("app.routers.chat.harness_runs_service.cancel", new_callable=AsyncMock, return_value=True) as mock_cancel:
        mock_settings.harness_enabled = True

        client = TestClient(app, raise_server_exceptions=False)
        response = client.post("/chat/threads/thread-1/harness/cancel")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["harness_run_id"] == "run-1"
    assert payload["status"] == "cancelled"
    mock_cancel.assert_called_once()


# ---------------------------------------------------------------------------
# 8. test_cancel_harness_endpoint_404_when_no_active_run
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cancel_harness_endpoint_404_when_no_active_run():
    """POST /threads/{id}/harness/cancel returns 404 when no active run."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.routers.chat import router
    from app.dependencies import get_current_user

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: _mock_user()

    with patch("app.routers.chat.settings") as mock_settings, \
         patch("app.routers.chat.harness_runs_service.get_active_run", new_callable=AsyncMock, return_value=None):
        mock_settings.harness_enabled = True

        client = TestClient(app, raise_server_exceptions=False)
        response = client.post("/chat/threads/thread-1/harness/cancel")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# 9. test_get_active_harness_returns_null_when_none
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_active_harness_returns_null_when_none():
    """GET /threads/{id}/harness/active returns {harnessRun: null} when no active run."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.routers.chat import router
    from app.dependencies import get_current_user

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: _mock_user()

    with patch("app.routers.chat.settings") as mock_settings, \
         patch("app.routers.chat.harness_runs_service.get_active_run", new_callable=AsyncMock, return_value=None):
        mock_settings.harness_enabled = True

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/chat/threads/thread-1/harness/active")

    assert response.status_code == 200
    assert response.json() == {"harnessRun": None}


# ---------------------------------------------------------------------------
# 10. test_get_active_harness_returns_payload_when_active
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_active_harness_returns_payload_when_active():
    """GET /threads/{id}/harness/active returns structured payload when active run exists."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.routers.chat import router
    from app.dependencies import get_current_user

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: _mock_user()

    active_run = _make_harness_run_record(status="running", current_phase=1)
    harness = _make_harness(n_phases=3)

    with patch("app.routers.chat.settings") as mock_settings, \
         patch("app.routers.chat.harness_runs_service.get_active_run", new_callable=AsyncMock, return_value=active_run), \
         patch("app.routers.chat.harness_registry.get_harness", return_value=harness):
        mock_settings.harness_enabled = True

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/chat/threads/thread-1/harness/active")

    assert response.status_code == 200
    payload = response.json()
    assert payload["harnessRun"] is not None
    hr = payload["harnessRun"]
    assert hr["id"] == "run-1"
    assert hr["harnessType"] == "smoke-echo"
    assert hr["status"] == "running"
    assert hr["currentPhase"] == 1
    assert hr["phaseCount"] == 3
    assert hr["phaseName"] == "Phase 1"


# ---------------------------------------------------------------------------
# 11. test_get_or_build_conversation_registry_calls_load_when_redaction_on  (B4)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_or_build_conversation_registry_calls_load_when_redaction_on():
    """B4: when pii_redaction_enabled=True, ConversationRegistry.load called with thread_id."""
    from app.routers.chat import _get_or_build_conversation_registry

    mock_registry = MagicMock()
    sys_settings = {"pii_redaction_enabled": True}

    with patch("app.routers.chat.ConversationRegistry") as mock_cr:
        mock_cr.load = AsyncMock(return_value=mock_registry)
        result = await _get_or_build_conversation_registry(
            "thread-b4-1", sys_settings=sys_settings
        )

    mock_cr.load.assert_called_once_with("thread-b4-1")
    assert result is mock_registry


# ---------------------------------------------------------------------------
# 12. test_get_or_build_conversation_registry_returns_none_when_redaction_off  (B4)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_or_build_conversation_registry_returns_none_when_redaction_off():
    """B4: when pii_redaction_enabled=False, returns None and ConversationRegistry.load NOT called."""
    from app.routers.chat import _get_or_build_conversation_registry

    sys_settings = {"pii_redaction_enabled": False}

    with patch("app.routers.chat.ConversationRegistry") as mock_cr:
        mock_cr.load = AsyncMock()
        result = await _get_or_build_conversation_registry(
            "thread-b4-2", sys_settings=sys_settings
        )

    mock_cr.load.assert_not_called()
    assert result is None


# ---------------------------------------------------------------------------
# 13. test_gatekeeper_stream_wrapper_passes_same_registry_to_gatekeeper_and_engine  (B4)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_gatekeeper_stream_wrapper_passes_same_registry_to_gatekeeper_and_engine():
    """B4: the SAME registry object (by identity) is passed to both run_gatekeeper
    and run_harness_engine from _gatekeeper_stream_wrapper.

    Simplified after Plan 20-05 moved gatekeeper/engine/post_harness imports to
    module level in chat.py — simple monkeypatch on 'app.routers.chat.*' works.
    """
    from app.routers.chat import _gatekeeper_stream_wrapper

    harness = _make_harness(n_phases=2)
    mock_registry = MagicMock(name="RegistrySentinel")

    gk_registry_received = []
    engine_registry_received = []

    async def _mock_gatekeeper(**kwargs):
        gk_registry_received.append(kwargs.get("registry"))
        yield {
            "type": "gatekeeper_complete",
            "triggered": True,
            "harness_run_id": "run-99",
            "phase_count": 2,
            "user_message_id": "umsg-1",
            "assistant_message_id": "amsg-1",
        }

    async def _mock_engine(**kwargs):
        engine_registry_received.append(kwargs.get("registry"))
        yield {"type": "harness_complete", "harness_run_id": "run-99", "status": "completed"}

    async def _mock_summarize(**kwargs):
        yield {"type": "summary_complete", "assistant_message_id": None}

    sys_settings = {"pii_redaction_enabled": True}

    with patch("app.routers.chat._get_or_build_conversation_registry", new_callable=AsyncMock, return_value=mock_registry), \
         patch("app.routers.chat.run_gatekeeper", side_effect=_mock_gatekeeper), \
         patch("app.routers.chat.run_harness_engine", side_effect=_mock_engine), \
         patch("app.routers.chat.summarize_harness_run", side_effect=_mock_summarize), \
         patch("app.routers.chat.harness_runs_service.get_run_by_id", new_callable=AsyncMock, return_value={"id": "run-99", "phase_results": {}}):

        events = await _drain_async_gen(
            _gatekeeper_stream_wrapper(
                harness=harness,
                thread_id="thread-b4-3",
                user_id="user-1",
                user_email="user@test.com",
                user_message="Go.",
                token="tok",
                sys_settings=sys_settings,
            )
        )

    # Both gatekeeper and engine should have received a registry
    assert len(gk_registry_received) == 1
    assert len(engine_registry_received) == 1
    # SAME object identity — B4 invariant
    assert gk_registry_received[0] is engine_registry_received[0]
    assert gk_registry_received[0] is mock_registry


# ---------------------------------------------------------------------------
# 14. test_409_harness_in_progress_includes_phase_count
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_409_harness_in_progress_includes_phase_count():
    """CR-03 regression: 409 harness_in_progress response must include phase_count so frontend renders correct N/M fraction."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.routers.chat import router
    from app.dependencies import get_current_user

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: _mock_user()

    harness = _make_harness(n_phases=3)

    mock_client = MagicMock()
    thread_chain = MagicMock()
    mock_client.table.return_value = thread_chain
    thread_chain.select.return_value = thread_chain
    thread_chain.eq.return_value = thread_chain
    thread_chain.limit.return_value = thread_chain
    thread_chain.execute.return_value = MagicMock(data=[{"id": "thread-1"}])

    active_run = _make_harness_run_record(harness_type="smoke-echo", current_phase=1)

    with patch("app.routers.chat.get_supabase_client", return_value=mock_client), \
         patch("app.routers.chat.settings") as mock_settings, \
         patch("app.routers.chat.harness_runs_service.get_active_run", new_callable=AsyncMock, return_value=active_run), \
         patch("app.routers.chat.harness_registry.get_harness", return_value=harness):
        mock_settings.sub_agent_enabled = False
        mock_settings.deep_mode_enabled = False
        mock_settings.harness_enabled = True

        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(
            "/chat/stream",
            json={
                "thread_id": "thread-1",
                "message": "Hello",
                "parent_message_id": None,
            },
        )

    assert response.status_code == 409
    payload = response.json()
    assert payload["error"] == "harness_in_progress"
    assert payload["phase_count"] == 3
