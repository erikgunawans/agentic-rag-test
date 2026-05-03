"""Unit tests for agent_runs_service — Phase 19 Plan 19-02 (TDD RED).

Tests cover the full public API of agent_runs_service:
  1. start_run creates a working row
  2. set_pending_question transitions status to waiting_for_user
  3. transition_status completes a run
  4. error() sets status='error' and error_detail
  5. get_active_run returns a waiting_for_user row
  6. get_active_run returns None when only completed rows exist
  7. start_run fails when an active run already exists (partial unique constraint)

These tests run against the REAL Supabase test project.
Requires env vars: TEST_EMAIL, TEST_PASSWORD, TEST_EMAIL_2, TEST_PASSWORD_2

Run:
    cd backend && source venv/bin/activate && \\
        TEST_EMAIL="test@test.com" TEST_PASSWORD='!*-3-3?3uZ?b$v&' \\
        TEST_EMAIL_2="test-2@test.com" TEST_PASSWORD_2='fK4$Wd?HGKmb#A2' \\
        API_BASE_URL="https://api-production-cde1.up.railway.app" \\
        pytest tests/services/test_agent_runs_service.py -v --tb=short
"""

from __future__ import annotations

import os
import uuid
import pytest

from app.database import get_supabase_client, get_supabase_authed_client
from app.services.agent_runs_service import (
    start_run,
    set_pending_question,
    transition_status,
    complete,
    error,
    get_active_run,
)

# ---------------------------------------------------------------------------
# Skip guard — missing env vars
# ---------------------------------------------------------------------------

TEST_EMAIL = os.environ.get("TEST_EMAIL", "")
TEST_PASSWORD = os.environ.get("TEST_PASSWORD", "")
TEST_EMAIL_2 = os.environ.get("TEST_EMAIL_2", "")
TEST_PASSWORD_2 = os.environ.get("TEST_PASSWORD_2", "")

pytestmark = pytest.mark.skipif(
    not TEST_EMAIL or not TEST_PASSWORD,
    reason="TEST_EMAIL / TEST_PASSWORD env vars not set",
)


# ---------------------------------------------------------------------------
# Module-level helpers (mirror test_workspace_service.py shape)
# ---------------------------------------------------------------------------

def _login(email: str, password: str) -> str:
    """Return a JWT access token for the given test account."""
    client = get_supabase_client()
    result = client.auth.sign_in_with_password({"email": email, "password": password})
    return result.session.access_token


def _get_user_id(token: str) -> str:
    """Return the auth.uid() for the given token."""
    client = get_supabase_authed_client(token)
    result = client.auth.get_user(token)
    return result.user.id


def _create_thread_svc(user_id: str) -> str:
    """Insert a minimal thread using service-role client; return thread_id."""
    client = get_supabase_client()
    result = (
        client.table("threads")
        .insert({"user_id": user_id, "title": "test-agent-runs"})
        .execute()
    )
    return result.data[0]["id"]


def _delete_thread_svc(thread_id: str) -> None:
    """Delete thread via service-role client (cascades agent_runs)."""
    client = get_supabase_client()
    client.table("threads").delete().eq("id", thread_id).execute()


# ---------------------------------------------------------------------------
# 1. start_run creates a working row
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_start_run_creates_working_row():
    """After start_run, get_active_run returns a row with status='working'
    and last_round_index=0."""
    token = _login(TEST_EMAIL, TEST_PASSWORD)
    user_id = _get_user_id(token)
    thread_id = _create_thread_svc(user_id)
    try:
        record = await start_run(thread_id, user_id, TEST_EMAIL, token)
        assert record["status"] == "working"
        assert record["last_round_index"] == 0
        assert record["thread_id"] == thread_id

        active = await get_active_run(thread_id, token)
        assert active is not None
        assert active["status"] == "working"
        assert active["last_round_index"] == 0
    finally:
        _delete_thread_svc(thread_id)


# ---------------------------------------------------------------------------
# 2. set_pending_question transitions to waiting_for_user
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_set_pending_question_transitions_to_waiting_for_user():
    """After start_run + set_pending_question, row has status='waiting_for_user'
    and pending_question set to the provided value."""
    token = _login(TEST_EMAIL, TEST_PASSWORD)
    user_id = _get_user_id(token)
    thread_id = _create_thread_svc(user_id)
    try:
        record = await start_run(thread_id, user_id, TEST_EMAIL, token)
        run_id = record["id"]

        await set_pending_question(run_id, "What is the deadline?", 3, token)

        active = await get_active_run(thread_id, token)
        assert active is not None
        assert active["status"] == "waiting_for_user"
        assert active["pending_question"] == "What is the deadline?"
        assert active["last_round_index"] == 3
    finally:
        _delete_thread_svc(thread_id)


# ---------------------------------------------------------------------------
# 3. transition_status completes a run
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_transition_status_completes_run():
    """After start_run + transition_status('complete'), get_active_run returns None
    (completed rows are excluded from the active lookup)."""
    token = _login(TEST_EMAIL, TEST_PASSWORD)
    user_id = _get_user_id(token)
    thread_id = _create_thread_svc(user_id)
    try:
        record = await start_run(thread_id, user_id, TEST_EMAIL, token)
        run_id = record["id"]

        await transition_status(run_id, "complete", token)

        active = await get_active_run(thread_id, token)
        assert active is None
    finally:
        _delete_thread_svc(thread_id)


# ---------------------------------------------------------------------------
# 4. error() records error_detail
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_error_run_records_error_detail():
    """error() sets status='error' and stores error_detail.
    After calling error(), get_active_run returns None (error rows are inactive)."""
    token = _login(TEST_EMAIL, TEST_PASSWORD)
    user_id = _get_user_id(token)
    thread_id = _create_thread_svc(user_id)
    try:
        record = await start_run(thread_id, user_id, TEST_EMAIL, token)
        run_id = record["id"]

        await error(run_id, token, user_id, TEST_EMAIL, error_detail="LLM timeout after 30s")

        active = await get_active_run(thread_id, token)
        assert active is None  # error rows not returned as active

        # Verify error_detail stored via direct service-role lookup
        svc_client = get_supabase_client()
        result = svc_client.table("agent_runs").select("status, error_detail").eq("id", run_id).execute()
        assert result.data[0]["status"] == "error"
        assert result.data[0]["error_detail"] == "LLM timeout after 30s"
    finally:
        _delete_thread_svc(thread_id)


# ---------------------------------------------------------------------------
# 5. get_active_run returns waiting_for_user row
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_active_run_returns_waiting_row():
    """get_active_run includes both 'working' and 'waiting_for_user' statuses.
    A row in 'waiting_for_user' state is returned."""
    token = _login(TEST_EMAIL, TEST_PASSWORD)
    user_id = _get_user_id(token)
    thread_id = _create_thread_svc(user_id)
    try:
        record = await start_run(thread_id, user_id, TEST_EMAIL, token)
        run_id = record["id"]

        await set_pending_question(run_id, "Clarify scope?", 1, token)

        active = await get_active_run(thread_id, token)
        assert active is not None
        assert active["status"] == "waiting_for_user"
        assert active["id"] == run_id
    finally:
        _delete_thread_svc(thread_id)


# ---------------------------------------------------------------------------
# 6. get_active_run returns None when only completed rows exist
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_active_run_returns_none_when_only_completed_rows_exist():
    """Completed rows do not appear in get_active_run — it only returns
    rows with status IN ('working', 'waiting_for_user')."""
    token = _login(TEST_EMAIL, TEST_PASSWORD)
    user_id = _get_user_id(token)
    thread_id = _create_thread_svc(user_id)
    try:
        record = await start_run(thread_id, user_id, TEST_EMAIL, token)
        run_id = record["id"]

        await complete(run_id, token, user_id, TEST_EMAIL)

        active = await get_active_run(thread_id, token)
        assert active is None
    finally:
        _delete_thread_svc(thread_id)


# ---------------------------------------------------------------------------
# 7. start_run fails when active run already exists
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_start_run_fails_when_active_run_already_exists():
    """The partial unique constraint on (thread_id) WHERE status IN ('working',
    'waiting_for_user') prevents a second active run in the same thread.
    A second start_run call raises (PostgreSQL unique violation surfaced
    by Supabase client)."""
    token = _login(TEST_EMAIL, TEST_PASSWORD)
    user_id = _get_user_id(token)
    thread_id = _create_thread_svc(user_id)
    try:
        # First run succeeds
        await start_run(thread_id, user_id, TEST_EMAIL, token)

        # Second run must fail — unique constraint violation
        with pytest.raises(Exception):
            await start_run(thread_id, user_id, TEST_EMAIL, token)
    finally:
        _delete_thread_svc(thread_id)
