"""Phase 21 / Plan 21-02 Task 0 — Tests for harness_runs_service.pause + resume_from_pause.

5 tests covering the new helpers added for the HIL flow:
  1. test_pause_running_row_succeeds         — guard accepts running, returns updated row
  2. test_pause_pending_row_is_no_op         — guard rejects (pending != running) → None
  3. test_pause_paused_row_is_no_op          — guard rejects (already paused) → None
  4. test_resume_from_pause_paused_row_succeeds — guard accepts paused, merges phase_results
  5. test_resume_from_pause_running_row_is_no_op — guard rejects (not paused) → None

All tests UNIT — Supabase client mocked via MagicMock chain.
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helper: Supabase mock with optional separate select+update return data
# ---------------------------------------------------------------------------

def _make_supabase_mock(
    update_data: list | None = None,
    select_data: list | None = None,
) -> tuple[MagicMock, MagicMock, MagicMock]:
    """Build a MagicMock supabase client.

    For resume_from_pause the service does select(phase_results) FIRST, then update.
    Both calls go through the same chained builder; .execute() returns different .data
    depending on whether select or update was the last action.

    To make this simple: we return the SELECT data on the first .execute() call
    (the phase_results fetch), and UPDATE data on the second.
    """
    mock = MagicMock()

    select_result = MagicMock()
    select_result.data = select_data if select_data is not None else []
    update_result = MagicMock()
    update_result.data = update_data if update_data is not None else []

    builder = MagicMock()
    # First execute() returns select_result, all subsequent return update_result.
    builder.execute.side_effect = [select_result, update_result, update_result]

    for method in ("insert", "select", "update", "eq", "in_", "order", "limit"):
        getattr(builder, method).return_value = builder

    mock.table.return_value = builder
    return mock, builder, update_result


# ===========================================================================
# Test 1 — pause(running) → returns updated row, status=paused
# ===========================================================================

@pytest.mark.asyncio
async def test_pause_running_row_succeeds():
    from app.services import harness_runs_service

    paused_row = {
        "id": "run-x",
        "thread_id": "t1",
        "user_id": "u1",
        "harness_type": "smoke-echo",
        "status": "paused",
        "current_phase": 2,
        "phase_results": {},
        "input_file_ids": [],
        "error_detail": None,
        "created_at": "2026-05-04T00:00:00Z",
        "updated_at": "2026-05-04T00:00:01Z",
    }
    # pause uses ONE execute() call (single update)
    mock_client = MagicMock()
    execute_result = MagicMock()
    execute_result.data = [paused_row]
    builder = MagicMock()
    builder.execute.return_value = execute_result
    for method in ("insert", "select", "update", "eq", "in_", "order", "limit"):
        getattr(builder, method).return_value = builder
    mock_client.table.return_value = builder

    with (
        patch("app.services.harness_runs_service.get_supabase_authed_client", return_value=mock_client),
        patch("app.services.harness_runs_service.audit_service.log_action") as mock_audit,
    ):
        result = await harness_runs_service.pause(
            run_id="run-x",
            user_id="u1",
            user_email="u1@test.com",
            token="tok",
        )

    assert result is not None
    assert result["status"] == "paused"

    # Verify .update({"status": "paused"}) was called
    update_payload = builder.update.call_args[0][0]
    assert update_payload == {"status": "paused"}

    # Verify the chained .in_("status", ["running"]) guard was applied
    in_call = builder.in_.call_args
    assert in_call is not None
    assert in_call[0][0] == "status"
    assert in_call[0][1] == ["running"]

    # Audit log emitted with action='harness_run_paused'
    mock_audit.assert_called_once()
    kwargs = mock_audit.call_args.kwargs
    assert kwargs["action"] == "harness_run_paused"
    assert kwargs["resource_type"] == "harness_runs"
    assert kwargs["resource_id"] == "run-x"


# ===========================================================================
# Test 2 — pause(pending) returns None (guard rejects, no audit)
# ===========================================================================

@pytest.mark.asyncio
async def test_pause_pending_row_is_no_op():
    from app.services import harness_runs_service

    # Guard rejects → empty data
    mock_client = MagicMock()
    execute_result = MagicMock()
    execute_result.data = []
    builder = MagicMock()
    builder.execute.return_value = execute_result
    for method in ("insert", "select", "update", "eq", "in_", "order", "limit"):
        getattr(builder, method).return_value = builder
    mock_client.table.return_value = builder

    with (
        patch("app.services.harness_runs_service.get_supabase_authed_client", return_value=mock_client),
        patch("app.services.harness_runs_service.audit_service.log_action") as mock_audit,
    ):
        result = await harness_runs_service.pause(
            run_id="run-pending",
            user_id="u1",
            user_email="u1@test.com",
            token="tok",
        )

    assert result is None
    # Audit log NOT called — guard rejected silently
    mock_audit.assert_not_called()


# ===========================================================================
# Test 3 — pause(paused) returns None (guard rejects, no audit)
# ===========================================================================

@pytest.mark.asyncio
async def test_pause_paused_row_is_no_op():
    from app.services import harness_runs_service

    # Guard rejects (status='paused', guard requires 'running') → empty data
    mock_client = MagicMock()
    execute_result = MagicMock()
    execute_result.data = []
    builder = MagicMock()
    builder.execute.return_value = execute_result
    for method in ("insert", "select", "update", "eq", "in_", "order", "limit"):
        getattr(builder, method).return_value = builder
    mock_client.table.return_value = builder

    with (
        patch("app.services.harness_runs_service.get_supabase_authed_client", return_value=mock_client),
        patch("app.services.harness_runs_service.audit_service.log_action") as mock_audit,
    ):
        result = await harness_runs_service.pause(
            run_id="run-already-paused",
            user_id="u1",
            user_email="u1@test.com",
            token="tok",
        )

    assert result is None
    mock_audit.assert_not_called()


# ===========================================================================
# Test 4 — resume_from_pause(paused) succeeds, merges phase_results
# ===========================================================================

@pytest.mark.asyncio
async def test_resume_from_pause_paused_row_succeeds():
    from app.services import harness_runs_service

    # 1st execute: SELECT phase_results — returns existing dict
    # 2nd execute: UPDATE — returns updated row
    select_data = [{"phase_results": {"2": {"phase_name": "ask", "output": {}}}}]
    update_data = [{
        "id": "run-x",
        "thread_id": "t1",
        "user_id": "u1",
        "harness_type": "smoke-echo",
        "status": "running",
        "current_phase": 3,
        "phase_results": {
            "2": {"phase_name": "ask", "output": {"answer": "the reply"}},
        },
        "input_file_ids": [],
        "error_detail": None,
        "created_at": "2026-05-04T00:00:00Z",
        "updated_at": "2026-05-04T00:00:02Z",
    }]

    mock_client, builder, _ = _make_supabase_mock(
        select_data=select_data,
        update_data=update_data,
    )

    with (
        patch("app.services.harness_runs_service.get_supabase_authed_client", return_value=mock_client),
        patch("app.services.harness_runs_service.audit_service.log_action") as mock_audit,
    ):
        result = await harness_runs_service.resume_from_pause(
            run_id="run-x",
            new_phase_index=3,
            phase_results_patch={"2": {"phase_name": "ask", "output": {"answer": "the reply"}}},
            user_id="u1",
            user_email="u1@test.com",
            token="tok",
        )

    assert result is not None
    assert result["status"] == "running"
    assert result["current_phase"] == 3

    # Verify update payload merged the patch into existing phase_results
    update_payload = builder.update.call_args[0][0]
    assert update_payload["status"] == "running"
    assert update_payload["current_phase"] == 3
    # The merged phase_results must contain the patch value
    assert update_payload["phase_results"]["2"]["output"]["answer"] == "the reply"

    # Verify the chained .in_("status", ["paused"]) guard was applied
    # (.in_ is also called by other operations in this file; check at least once)
    in_calls = [c for c in builder.in_.call_args_list]
    paused_guard_calls = [c for c in in_calls if c[0][1] == ["paused"]]
    assert len(paused_guard_calls) >= 1

    # Audit log emitted with action='harness_run_resumed'
    mock_audit.assert_called_once()
    kwargs = mock_audit.call_args.kwargs
    assert kwargs["action"] == "harness_run_resumed"
    assert kwargs["resource_type"] == "harness_runs"
    assert kwargs["resource_id"] == "run-x"


# ===========================================================================
# Test 5 — resume_from_pause(running) returns None (guard rejects)
# ===========================================================================

@pytest.mark.asyncio
async def test_resume_from_pause_running_row_is_no_op():
    from app.services import harness_runs_service

    # 1st execute: SELECT phase_results — empty (or any) row
    # 2nd execute: UPDATE — guard rejected → empty data
    mock_client, builder, _ = _make_supabase_mock(
        select_data=[{"phase_results": {}}],
        update_data=[],
    )

    with (
        patch("app.services.harness_runs_service.get_supabase_authed_client", return_value=mock_client),
        patch("app.services.harness_runs_service.audit_service.log_action") as mock_audit,
    ):
        result = await harness_runs_service.resume_from_pause(
            run_id="run-not-paused",
            new_phase_index=1,
            phase_results_patch={"0": {"answer": "x"}},
            user_id="u1",
            user_email="u1@test.com",
            token="tok",
        )

    assert result is None
    mock_audit.assert_not_called()
