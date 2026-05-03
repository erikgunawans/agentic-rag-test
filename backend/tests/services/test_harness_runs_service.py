"""Unit tests for harness_runs_service — Phase 20 Plan 20-02 (TDD RED → GREEN).

Tests cover the full public API of harness_runs_service using unittest.mock:
  1.  start_run inserts row with status='pending', current_phase=0, returns run_id
  2.  start_run calls audit_service.log_action with action='harness_run_started'
  3.  get_active_run returns None when no rows exist for thread
  4.  get_active_run returns single row when status IN (pending/running/paused)
  5.  get_latest_for_thread returns most-recently-created row regardless of status
  6.  advance_phase updates current_phase + merges phase_results (transactional guard
      rejects when row already terminal → returns False + logs WARNING)
  7.  complete sets status='completed', audit-logs harness_run_completed
  8.  fail sets status='failed', truncates error_detail, audit-logs harness_run_failed
  9.  cancel sets status='cancelled', audit-logs harness_run_cancelled
  10. error_detail longer than 500 chars is truncated to 500 before DB write
  11. RunStatus Literal type contains exactly 6 values

These tests are UNIT tests — all DB and audit calls are mocked via
unittest.mock.MagicMock / AsyncMock. No real Supabase connection required.

Run:
    cd backend && source venv/bin/activate && \\
        pytest tests/services/test_harness_runs_service.py -v
"""

from __future__ import annotations

import typing
import logging
import pytest
from unittest.mock import MagicMock, patch, call


# ---------------------------------------------------------------------------
# Helper: build a mock Supabase client with fluent query-builder chain
# ---------------------------------------------------------------------------

def _make_supabase_mock(return_data: list | None = None) -> MagicMock:
    """Return a MagicMock that mimics the Supabase Python client query builder.

    The builder chain is:
        client.table(name)
              .insert(payload).execute()
              .select(cols).eq(k, v).in_(k, vs).order(col, desc=True).limit(n).execute()
              .update(payload).eq(k, v).in_(k, vs).execute()
    All methods return `self` so chaining works; `.execute()` returns an object
    with `data` attribute.
    """
    mock = MagicMock()
    execute_result = MagicMock()
    execute_result.data = return_data if return_data is not None else []

    builder = MagicMock()
    builder.execute.return_value = execute_result
    # Make every builder method return itself for chaining
    for method in ("insert", "select", "update", "eq", "in_", "order", "limit"):
        getattr(builder, method).return_value = builder

    mock.table.return_value = builder
    return mock, builder, execute_result


# ===========================================================================
# Test 1 — start_run inserts row with status='pending', returns run_id
# ===========================================================================

@pytest.mark.asyncio
async def test_start_run_inserts_pending_row():
    """start_run should INSERT a row with status='pending', current_phase=0,
    and return the new row's 'id' as a string (UUID)."""
    from app.services import harness_runs_service

    fake_run_id = "aaaaaaaa-0000-0000-0000-000000000001"
    mock_client, builder, execute_result = _make_supabase_mock(
        return_data=[{
            "id": fake_run_id,
            "thread_id": "t1",
            "user_id": "u1",
            "harness_type": "smoke-echo",
            "status": "pending",
            "current_phase": 0,
            "phase_results": {},
            "input_file_ids": [],
            "error_detail": None,
            "created_at": "2026-05-03T00:00:00Z",
            "updated_at": "2026-05-03T00:00:00Z",
        }]
    )

    with (
        patch("app.services.harness_runs_service.get_supabase_authed_client", return_value=mock_client),
        patch("app.services.harness_runs_service.audit_service.log_action"),
    ):
        result = await harness_runs_service.start_run(
            thread_id="t1",
            user_id="u1",
            user_email="u@test.com",
            harness_type="smoke-echo",
            input_file_ids=None,
            token="tok",
        )

    assert result == fake_run_id

    # Verify INSERT payload contained correct fields
    insert_payload = builder.insert.call_args[0][0]
    assert insert_payload["status"] == "pending"
    assert insert_payload["current_phase"] == 0
    assert insert_payload["harness_type"] == "smoke-echo"
    assert "phase_results" in insert_payload
    assert insert_payload.get("input_file_ids", []) == []


# ===========================================================================
# Test 2 — start_run calls audit_service.log_action with harness_run_started
# ===========================================================================

@pytest.mark.asyncio
async def test_start_run_emits_audit_log():
    """start_run must call audit_service.log_action with action='harness_run_started',
    resource_type='harness_runs', and resource_id equal to the new run's id."""
    from app.services import harness_runs_service

    fake_run_id = "aaaaaaaa-0000-0000-0000-000000000002"
    mock_client, _, _ = _make_supabase_mock(
        return_data=[{"id": fake_run_id, "status": "pending", "current_phase": 0}]
    )

    with (
        patch("app.services.harness_runs_service.get_supabase_authed_client", return_value=mock_client),
        patch("app.services.harness_runs_service.audit_service.log_action") as mock_audit,
    ):
        await harness_runs_service.start_run(
            thread_id="t2",
            user_id="u2",
            user_email="u2@test.com",
            harness_type="smoke-echo",
            input_file_ids=None,
            token="tok",
        )

    mock_audit.assert_called_once()
    kwargs = mock_audit.call_args.kwargs
    assert kwargs.get("action") == "harness_run_started"
    assert kwargs.get("resource_type") == "harness_runs"
    assert kwargs.get("resource_id") == fake_run_id


# ===========================================================================
# Test 3 — get_active_run returns None when no rows exist
# ===========================================================================

@pytest.mark.asyncio
async def test_get_active_run_returns_none_when_no_rows():
    """get_active_run should return None when the SELECT returns an empty list."""
    from app.services import harness_runs_service

    mock_client, _, _ = _make_supabase_mock(return_data=[])

    with patch("app.services.harness_runs_service.get_supabase_authed_client", return_value=mock_client):
        result = await harness_runs_service.get_active_run(thread_id="t3", token="tok")

    assert result is None


# ===========================================================================
# Test 4 — get_active_run returns row for active statuses
# ===========================================================================

@pytest.mark.asyncio
async def test_get_active_run_returns_row_for_active_status():
    """get_active_run returns the single row when status IN (pending/running/paused);
    terminal rows (completed/failed/cancelled) must not be returned."""
    from app.services import harness_runs_service

    active_row = {
        "id": "run-active",
        "thread_id": "t4",
        "status": "running",
        "current_phase": 1,
    }
    mock_client, builder, _ = _make_supabase_mock(return_data=[active_row])

    with patch("app.services.harness_runs_service.get_supabase_authed_client", return_value=mock_client):
        result = await harness_runs_service.get_active_run(thread_id="t4", token="tok")

    assert result == active_row

    # Verify the query used .in_() to filter by active statuses
    in_call_args = builder.in_.call_args
    assert in_call_args is not None
    statuses_arg = in_call_args[0][1]  # second positional arg to .in_()
    assert set(statuses_arg) == {"pending", "running", "paused"}


# ===========================================================================
# Test 5 — get_latest_for_thread returns most-recent row regardless of status
# ===========================================================================

@pytest.mark.asyncio
async def test_get_latest_for_thread_returns_most_recent_row():
    """get_latest_for_thread returns the most-recently created row for the thread,
    regardless of status (used by D-05 gatekeeper eligibility)."""
    from app.services import harness_runs_service

    latest_row = {
        "id": "run-latest",
        "thread_id": "t5",
        "status": "completed",
        "current_phase": 3,
    }
    mock_client, _, _ = _make_supabase_mock(return_data=[latest_row])

    with patch("app.services.harness_runs_service.get_supabase_authed_client", return_value=mock_client):
        result = await harness_runs_service.get_latest_for_thread(thread_id="t5", token="tok")

    assert result == latest_row


# ===========================================================================
# Test 6 — advance_phase transactional guard: 0-row update when terminal
# ===========================================================================

@pytest.mark.asyncio
async def test_advance_phase_guard_logs_warning_on_zero_rows(caplog):
    """advance_phase must return False and log a WARNING when the transactional guard
    finds no matching rows (i.e., row is already terminal)."""
    from app.services import harness_runs_service

    # Simulate 0 rows returned — row is already in terminal state
    mock_client, _, _ = _make_supabase_mock(return_data=[])

    with (
        patch("app.services.harness_runs_service.get_supabase_authed_client", return_value=mock_client),
        caplog.at_level(logging.WARNING, logger="app.services.harness_runs_service"),
    ):
        result = await harness_runs_service.advance_phase(
            run_id="run-terminal",
            new_phase_index=2,
            phase_results_patch={"phase_2": {"status": "ok"}},
            token="tok",
        )

    assert result is False
    assert any("advance_phase" in r.message or "0 rows" in r.message for r in caplog.records)


# ===========================================================================
# Test 7 — complete sets status='completed', audit-logs harness_run_completed
# ===========================================================================

@pytest.mark.asyncio
async def test_complete_sets_completed_and_audit_logs():
    """complete() must UPDATE status='completed' with the guard .eq('status','running'),
    and call audit_service.log_action with action='harness_run_completed'."""
    from app.services import harness_runs_service

    mock_client, builder, execute_result = _make_supabase_mock(
        return_data=[{"id": "run-c", "status": "completed"}]
    )

    with (
        patch("app.services.harness_runs_service.get_supabase_authed_client", return_value=mock_client),
        patch("app.services.harness_runs_service.audit_service.log_action") as mock_audit,
    ):
        result = await harness_runs_service.complete(
            run_id="run-c",
            user_id="u7",
            user_email="u7@test.com",
            token="tok",
        )

    assert result is True
    mock_audit.assert_called_once()
    kwargs = mock_audit.call_args.kwargs
    assert kwargs.get("action") == "harness_run_completed"
    assert kwargs.get("resource_type") == "harness_runs"


# ===========================================================================
# Test 8 — fail sets status='failed', truncates error_detail, audit-logs
# ===========================================================================

@pytest.mark.asyncio
async def test_fail_sets_failed_and_audit_logs():
    """fail() must UPDATE status='failed', persist truncated error_detail, and
    call audit_service.log_action with action='harness_run_failed'."""
    from app.services import harness_runs_service

    mock_client, builder, _ = _make_supabase_mock(
        return_data=[{"id": "run-f", "status": "failed"}]
    )

    error_msg = "something went wrong"
    with (
        patch("app.services.harness_runs_service.get_supabase_authed_client", return_value=mock_client),
        patch("app.services.harness_runs_service.audit_service.log_action") as mock_audit,
    ):
        result = await harness_runs_service.fail(
            run_id="run-f",
            user_id="u8",
            user_email="u8@test.com",
            error_detail=error_msg,
            token="tok",
        )

    assert result is True
    mock_audit.assert_called_once()
    kwargs = mock_audit.call_args.kwargs
    assert kwargs.get("action") == "harness_run_failed"

    # Verify the UPDATE payload contains truncated error_detail
    update_payload = builder.update.call_args[0][0]
    assert update_payload.get("status") == "failed"
    assert update_payload.get("error_detail") == error_msg  # short — no truncation needed


# ===========================================================================
# Test 9 — cancel sets status='cancelled', audit-logs harness_run_cancelled
# ===========================================================================

@pytest.mark.asyncio
async def test_cancel_sets_cancelled_and_audit_logs():
    """cancel() must UPDATE status='cancelled' with guard .in_('status', ACTIVE_STATUSES),
    and call audit_service.log_action with action='harness_run_cancelled'."""
    from app.services import harness_runs_service

    mock_client, _, _ = _make_supabase_mock(
        return_data=[{"id": "run-x", "status": "cancelled"}]
    )

    with (
        patch("app.services.harness_runs_service.get_supabase_authed_client", return_value=mock_client),
        patch("app.services.harness_runs_service.audit_service.log_action") as mock_audit,
    ):
        result = await harness_runs_service.cancel(
            run_id="run-x",
            user_id="u9",
            user_email="u9@test.com",
            token="tok",
        )

    assert result is True
    mock_audit.assert_called_once()
    kwargs = mock_audit.call_args.kwargs
    assert kwargs.get("action") == "harness_run_cancelled"
    assert kwargs.get("resource_type") == "harness_runs"


# ===========================================================================
# Test 10 — error_detail longer than 500 chars is truncated before DB write
# ===========================================================================

@pytest.mark.asyncio
async def test_error_detail_truncated_to_500_chars():
    """fail() must truncate error_detail to exactly 500 chars before persisting.
    A 600-char string must arrive in the DB as 500 chars."""
    from app.services import harness_runs_service

    long_error = "E" * 600  # 600 chars — must be truncated to 500

    mock_client, builder, _ = _make_supabase_mock(
        return_data=[{"id": "run-trunc", "status": "failed"}]
    )

    with (
        patch("app.services.harness_runs_service.get_supabase_authed_client", return_value=mock_client),
        patch("app.services.harness_runs_service.audit_service.log_action"),
    ):
        await harness_runs_service.fail(
            run_id="run-trunc",
            user_id="u10",
            user_email="u10@test.com",
            error_detail=long_error,
            token="tok",
        )

    update_payload = builder.update.call_args[0][0]
    persisted_detail = update_payload.get("error_detail", "")
    assert len(persisted_detail) == 500, f"Expected 500, got {len(persisted_detail)}"
    assert persisted_detail == "E" * 500


# ===========================================================================
# Test 11 — RunStatus Literal type contains exactly 6 values
# ===========================================================================

def test_run_status_literal_has_six_values():
    """RunStatus must be a Literal with exactly 6 values:
    pending, running, paused, completed, failed, cancelled."""
    from app.services.harness_runs_service import RunStatus

    values = set(typing.get_args(RunStatus))
    assert values == {"pending", "running", "paused", "completed", "failed", "cancelled"}, (
        f"RunStatus has unexpected values: {values}"
    )


# ===========================================================================
# Test (bonus): active_run_partial_unique — name from plan acceptance_criteria
# ===========================================================================

@pytest.mark.asyncio
async def test_active_run_partial_unique():
    """Ensures that get_active_run queries with the correct partial-unique active
    statuses (pending/running/paused) — not old agent_runs statuses."""
    from app.services import harness_runs_service

    mock_client, builder, _ = _make_supabase_mock(return_data=[])

    with patch("app.services.harness_runs_service.get_supabase_authed_client", return_value=mock_client):
        await harness_runs_service.get_active_run(thread_id="t-pu", token="tok")

    in_call_args = builder.in_.call_args
    assert in_call_args is not None
    statuses_arg = in_call_args[0][1]
    # Must NOT contain agent_runs statuses like "working" or "waiting_for_user"
    assert "working" not in statuses_arg
    assert "waiting_for_user" not in statuses_arg
    # Must contain harness-specific active statuses
    assert set(statuses_arg) == {"pending", "running", "paused"}
