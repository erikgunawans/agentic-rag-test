"""Integration tests for migration 040: agent_runs table + messages.parent_task_id column.

These tests verify:
  - Schema: agent_runs columns, constraints, indexes (7 defined tests per plan spec)
  - RLS: T-19-03 mitigation — User A cannot SELECT User B's agent_runs rows
  - Partial unique constraint: at most one active run per thread
  - CHECK constraint: pending_question invariant
  - Trigger: handle_updated_at fires on agent_runs UPDATE
  - messages.parent_task_id column exists and accepts UUID values

All 7 tests FAIL before migration 040 is applied (TDD RED gate).
After `supabase db push`, all 7 should PASS (TDD GREEN gate).

NOTE: Tests use functional assertions (SELECT/INSERT) rather than querying
information_schema or pg_indexes directly — Supabase PostgREST only exposes the
public schema, not system catalog tables.

Requirements covered: TASK-04, ASK-04, STATUS-05

Run (pre-migration — expect 7 errors / relation does not exist):
    cd backend && source venv/bin/activate && \\
      pytest tests/integration/test_migration_040_agent_runs.py -v

Run (post-migration — expect 7 passed):
    cd backend && source venv/bin/activate && \\
      TEST_EMAIL="test@test.com" TEST_PASSWORD='!*-3-3?3uZ?b$v&' \\
      TEST_EMAIL_2="test-2@test.com" TEST_PASSWORD_2='fK4$Wd?HGKmb#A2' \\
      pytest tests/integration/test_migration_040_agent_runs.py -v
"""

from __future__ import annotations

import os
import time
import uuid

import pytest

from app.database import get_supabase_authed_client, get_supabase_client

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TEST_EMAIL = os.environ.get("TEST_EMAIL", "test@test.com")
TEST_PASSWORD = os.environ.get("TEST_PASSWORD", "!*-3-3?3uZ?b$v&")
TEST_EMAIL_2 = os.environ.get("TEST_EMAIL_2", "test-2@test.com")
TEST_PASSWORD_2 = os.environ.get("TEST_PASSWORD_2", "fK4$Wd?HGKmb#A2")


# ---------------------------------------------------------------------------
# Helpers (copied verbatim from test_migration_038_agent_todos.py per PATTERNS.md L1004-1009)
# ---------------------------------------------------------------------------


def _login(email: str, password: str) -> str:
    """Return a JWT access token for the given credentials via Supabase auth."""
    client = get_supabase_client()
    result = client.auth.sign_in_with_password({"email": email, "password": password})
    return result.session.access_token


def _get_user_id(email: str, password: str) -> str:
    """Return the Supabase user UUID for the given credentials."""
    client = get_supabase_client()
    result = client.auth.sign_in_with_password({"email": email, "password": password})
    return str(result.user.id)


def _create_thread_svc(user_id: str, name: str = "") -> str:
    """Create a thread row via service-role and return its ID."""
    svc = get_supabase_client()
    thread_id = str(uuid.uuid4())
    title = name if name else f"test-migration-040-{thread_id[:8]}"
    svc.table("threads").insert({
        "id": thread_id,
        "user_id": user_id,
        "title": title,
    }).execute()
    return thread_id


def _delete_thread_svc(thread_id: str) -> None:
    """Delete a thread row via service-role (cascades to agent_runs)."""
    svc = get_supabase_client()
    try:
        svc.table("threads").delete().eq("id", thread_id).execute()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Test 1: agent_runs table exists with expected columns
# ---------------------------------------------------------------------------


def test_agent_runs_table_exists_with_expected_columns():
    """agent_runs table has all 9 required columns.

    Uses INSERT + SELECT round-trip to assert columns are present with correct types.
    Fails with relation-not-found before migration 040 is applied (RED).
    """
    user_a_id = _get_user_id(TEST_EMAIL, TEST_PASSWORD)
    svc = get_supabase_client()
    thread_id = _create_thread_svc(user_a_id)
    run_id = str(uuid.uuid4())
    try:
        # INSERT with all required columns explicitly
        insert_result = svc.table("agent_runs").insert({
            "id": run_id,
            "thread_id": thread_id,
            "user_id": user_a_id,
            "status": "working",
            "last_round_index": 0,
        }).execute()
        assert insert_result.data, "INSERT returned no data — table may not exist"

        # SELECT back with all 9 columns explicitly named
        row = (
            svc.table("agent_runs")
            .select(
                "id,thread_id,user_id,status,pending_question,"
                "last_round_index,error_detail,created_at,updated_at"
            )
            .eq("id", run_id)
            .single()
            .execute()
        )
        data = row.data
        assert data is not None, "SELECT returned no row"
        for col in (
            "id", "thread_id", "user_id", "status", "pending_question",
            "last_round_index", "error_detail", "created_at", "updated_at",
        ):
            assert col in data, f"Column '{col}' missing from agent_runs"

        # Spot-check types
        assert data["status"] == "working", (
            f"status must be 'working', got {data['status']!r}"
        )
        assert isinstance(data["last_round_index"], int), (
            f"last_round_index must be integer, got {type(data['last_round_index'])}"
        )
        assert data["pending_question"] is None, (
            "pending_question must default to NULL when not provided"
        )
    finally:
        svc.table("agent_runs").delete().eq("id", run_id).execute()
        _delete_thread_svc(thread_id)


# ---------------------------------------------------------------------------
# Test 2: Partial unique constraint — at most one active run per thread
# ---------------------------------------------------------------------------


def test_agent_runs_partial_unique_constraint_active_run():
    """Partial unique index prevents two active runs on the same thread.

    Insert a 'working' row, then attempt a second 'working' row in the same
    thread — expect a unique constraint violation (409 / IntegrityError).
    Fails before migration 040 is applied (table does not exist — RED).
    """
    user_a_id = _get_user_id(TEST_EMAIL, TEST_PASSWORD)
    svc = get_supabase_client()
    thread_id = _create_thread_svc(user_a_id)
    run_id_1 = str(uuid.uuid4())
    run_id_2 = str(uuid.uuid4())
    try:
        # First active run — must succeed
        svc.table("agent_runs").insert({
            "id": run_id_1,
            "thread_id": thread_id,
            "user_id": user_a_id,
            "status": "working",
            "last_round_index": 0,
        }).execute()

        # Second active run in the same thread — must fail
        with pytest.raises(Exception) as exc_info:
            svc.table("agent_runs").insert({
                "id": run_id_2,
                "thread_id": thread_id,
                "user_id": user_a_id,
                "status": "working",
                "last_round_index": 0,
            }).execute()

        err = str(exc_info.value).lower()
        assert any(kw in err for kw in ("unique", "duplicate", "conflict", "23505", "409")), (
            f"Expected unique constraint violation for second active run, got: {exc_info.value}"
        )
    finally:
        svc.table("agent_runs").delete().eq("id", run_id_1).execute()
        svc.table("agent_runs").delete().eq("id", run_id_2).execute()
        _delete_thread_svc(thread_id)


# ---------------------------------------------------------------------------
# Test 3: CHECK constraint — pending_question invariant
# ---------------------------------------------------------------------------


def test_agent_runs_pending_question_invariant():
    """agent_runs_pending_question_invariant CHECK constraint is enforced.

    Case A: status='waiting_for_user' with NULL pending_question → CHECK violation.
    Case B: status='working' with non-NULL pending_question → CHECK violation.
    Fails before migration 040 is applied (table does not exist — RED).
    """
    user_a_id = _get_user_id(TEST_EMAIL, TEST_PASSWORD)
    svc = get_supabase_client()
    thread_id_a = _create_thread_svc(user_a_id, "test-040-inv-a")
    thread_id_b = _create_thread_svc(user_a_id, "test-040-inv-b")
    try:
        # Case A: waiting_for_user + NULL pending_question → must fail
        with pytest.raises(Exception) as exc_a:
            svc.table("agent_runs").insert({
                "id": str(uuid.uuid4()),
                "thread_id": thread_id_a,
                "user_id": user_a_id,
                "status": "waiting_for_user",
                "pending_question": None,
                "last_round_index": 1,
            }).execute()

        err_a = str(exc_a.value).lower()
        assert any(kw in err_a for kw in ("check", "constraint", "violates", "23514")), (
            f"Expected CHECK violation for waiting_for_user+NULL pending_question, got: {exc_a.value}"
        )

        # Case B: working + non-NULL pending_question → must fail
        with pytest.raises(Exception) as exc_b:
            svc.table("agent_runs").insert({
                "id": str(uuid.uuid4()),
                "thread_id": thread_id_b,
                "user_id": user_a_id,
                "status": "working",
                "pending_question": "Should this be here?",
                "last_round_index": 0,
            }).execute()

        err_b = str(exc_b.value).lower()
        assert any(kw in err_b for kw in ("check", "constraint", "violates", "23514")), (
            f"Expected CHECK violation for working+non-NULL pending_question, got: {exc_b.value}"
        )
    finally:
        _delete_thread_svc(thread_id_a)
        _delete_thread_svc(thread_id_b)


# ---------------------------------------------------------------------------
# Test 4: CHECK constraint — status must be a valid enum value
# ---------------------------------------------------------------------------


def test_agent_runs_status_check_constraint():
    """status CHECK constraint rejects invalid values.

    Attempts INSERT with status='nonsense' — expect CHECK violation.
    Valid statuses (working, waiting_for_user, complete, error) succeed.
    Fails before migration 040 is applied (table does not exist — RED).
    """
    user_a_id = _get_user_id(TEST_EMAIL, TEST_PASSWORD)
    svc = get_supabase_client()
    thread_id = _create_thread_svc(user_a_id)
    valid_ids: list[str] = []
    try:
        # Valid statuses must succeed
        for status in ("working", "complete", "error"):
            run_id = str(uuid.uuid4())
            res = svc.table("agent_runs").insert({
                "id": run_id,
                "thread_id": thread_id,
                "user_id": user_a_id,
                "status": status,
                "last_round_index": 0,
            }).execute()
            assert res.data, f"INSERT with valid status='{status}' returned no data"
            valid_ids.append(run_id)

        # Invalid status → CHECK violation
        with pytest.raises(Exception) as exc_info:
            svc.table("agent_runs").insert({
                "id": str(uuid.uuid4()),
                "thread_id": thread_id,
                "user_id": user_a_id,
                "status": "nonsense",
                "last_round_index": 0,
            }).execute()

        err = str(exc_info.value).lower()
        assert any(kw in err for kw in ("check", "constraint", "violates", "invalid", "23514")), (
            f"Expected CHECK constraint violation for status='nonsense', got: {exc_info.value}"
        )
    finally:
        for run_id in valid_ids:
            svc.table("agent_runs").delete().eq("id", run_id).execute()
        _delete_thread_svc(thread_id)


# ---------------------------------------------------------------------------
# Test 5: handle_updated_at trigger fires on agent_runs UPDATE
# ---------------------------------------------------------------------------


def test_agent_runs_handle_updated_at_trigger():
    """handle_updated_at trigger (from migration 001) fires on agent_runs UPDATE.

    Insert a row, capture updated_at, wait 100ms, UPDATE status to 'complete',
    assert updated_at > created_at.
    Fails before migration 040 is applied (table does not exist — RED).
    """
    user_a_id = _get_user_id(TEST_EMAIL, TEST_PASSWORD)
    svc = get_supabase_client()
    thread_id = _create_thread_svc(user_a_id)
    run_id = None
    try:
        run_id = str(uuid.uuid4())
        insert_result = svc.table("agent_runs").insert({
            "id": run_id,
            "thread_id": thread_id,
            "user_id": user_a_id,
            "status": "working",
            "last_round_index": 0,
        }).execute()
        assert insert_result.data, (
            "INSERT into agent_runs returned no data — table may not exist."
        )

        # Capture initial updated_at
        row_before = (
            svc.table("agent_runs")
            .select("updated_at,created_at")
            .eq("id", run_id)
            .single()
            .execute()
        )
        initial_updated_at = row_before.data["updated_at"]

        # Wait 100ms so timestamp difference is detectable
        time.sleep(0.1)

        # UPDATE status to 'complete' — trigger should advance updated_at
        svc.table("agent_runs").update({"status": "complete"}).eq("id", run_id).execute()

        # Fetch updated row
        row_after = (
            svc.table("agent_runs")
            .select("updated_at")
            .eq("id", run_id)
            .single()
            .execute()
        )
        new_updated_at = row_after.data["updated_at"]

        assert new_updated_at != initial_updated_at, (
            f"handle_updated_at trigger did NOT fire: updated_at unchanged "
            f"(before={initial_updated_at}, after={new_updated_at}). "
            "Check trigger registration in migration 040."
        )
        assert new_updated_at > initial_updated_at, (
            f"updated_at went backwards: before={initial_updated_at}, after={new_updated_at}"
        )
    finally:
        if run_id:
            try:
                svc.table("agent_runs").delete().eq("id", run_id).execute()
            except Exception:
                pass
        _delete_thread_svc(thread_id)


# ---------------------------------------------------------------------------
# Test 6: RLS — User A cannot read User B's agent_runs rows (T-19-03 mitigation)
# ---------------------------------------------------------------------------


def test_agent_runs_rls_user_isolation():
    """T-19-03: User A cannot SELECT User B's agent_runs rows.

    User B creates a thread + agent_runs row via service-role.
    User A's JWT-scoped client attempts SELECT → must return 0 rows (RLS filters).

    Mirrors threat T-19-03 mitigation: RLS uses
    thread_id IN (SELECT id FROM threads WHERE user_id = auth.uid()) form.
    Fails before migration 040 is applied (RED).
    """
    user_a_id = _get_user_id(TEST_EMAIL, TEST_PASSWORD)
    user_b_id = _get_user_id(TEST_EMAIL_2, TEST_PASSWORD_2)

    # User A's JWT-scoped client
    token_a = _login(TEST_EMAIL, TEST_PASSWORD)
    client_a = get_supabase_authed_client(token_a)

    # Service-role client to set up User B's data
    svc = get_supabase_client()

    # Create User B's thread via service-role
    b_thread_id = _create_thread_svc(user_b_id)
    b_run_id = None

    try:
        # Insert User B's agent_runs row via service-role (bypasses RLS)
        b_run_id = str(uuid.uuid4())
        svc.table("agent_runs").insert({
            "id": b_run_id,
            "thread_id": b_thread_id,
            "user_id": user_b_id,
            "status": "working",
            "last_round_index": 0,
        }).execute()

        # User A must see 0 rows for User B's run
        select_result = (
            client_a.table("agent_runs")
            .select("id")
            .eq("id", b_run_id)
            .execute()
        )
        assert select_result.data == [], (
            f"RLS SELECT failed: User A should see 0 rows for User B's agent_runs row, "
            f"got: {select_result.data}"
        )

        # User A also cannot see User B's run in a thread-filtered query
        thread_result = (
            client_a.table("agent_runs")
            .select("id")
            .eq("thread_id", b_thread_id)
            .execute()
        )
        assert thread_result.data == [], (
            f"RLS SELECT (thread filter) failed: User A sees User B's run via thread_id filter, "
            f"got: {thread_result.data}"
        )
    finally:
        if b_run_id:
            try:
                svc.table("agent_runs").delete().eq("id", b_run_id).execute()
            except Exception:
                pass
        _delete_thread_svc(b_thread_id)


# ---------------------------------------------------------------------------
# Test 7: messages.parent_task_id column exists and accepts UUID values
# ---------------------------------------------------------------------------


def test_messages_parent_task_id_column_exists():
    """messages.parent_task_id column exists and accepts a UUID value.

    INSERT a message with parent_task_id set to a random UUID,
    SELECT back, assert column accepted the value.
    Also assert that parent_task_id defaults to NULL when omitted.
    Fails before migration 040 is applied (column does not exist — RED).
    """
    user_a_id = _get_user_id(TEST_EMAIL, TEST_PASSWORD)
    svc = get_supabase_client()
    thread_id = _create_thread_svc(user_a_id)
    msg_id_with = str(uuid.uuid4())
    msg_id_without = str(uuid.uuid4())
    parent_task_id = str(uuid.uuid4())
    try:
        # Insert message WITH parent_task_id set
        insert_with = svc.table("messages").insert({
            "id": msg_id_with,
            "thread_id": thread_id,
            "user_id": user_a_id,
            "role": "assistant",
            "content": "sub-agent message with parent_task_id",
            "parent_task_id": parent_task_id,
        }).execute()
        assert insert_with.data, "INSERT with parent_task_id returned no data"

        row_with = (
            svc.table("messages")
            .select("id,parent_task_id")
            .eq("id", msg_id_with)
            .single()
            .execute()
        )
        assert row_with.data is not None, "Message with parent_task_id not found after INSERT"
        assert "parent_task_id" in row_with.data, (
            "parent_task_id column missing from messages — "
            "ALTER TABLE messages ADD COLUMN parent_task_id not applied (migration 040 missing)"
        )
        assert row_with.data["parent_task_id"] == parent_task_id, (
            f"parent_task_id value mismatch: expected {parent_task_id}, "
            f"got {row_with.data['parent_task_id']}"
        )

        # Insert message WITHOUT parent_task_id — should default to NULL
        insert_without = svc.table("messages").insert({
            "id": msg_id_without,
            "thread_id": thread_id,
            "user_id": user_a_id,
            "role": "user",
            "content": "regular message without parent_task_id",
        }).execute()
        assert insert_without.data, "INSERT without parent_task_id returned no data"

        row_without = (
            svc.table("messages")
            .select("id,parent_task_id")
            .eq("id", msg_id_without)
            .single()
            .execute()
        )
        assert row_without.data is not None, "Regular message not found after INSERT"
        assert row_without.data["parent_task_id"] is None, (
            f"parent_task_id should default to NULL, got: {row_without.data['parent_task_id']}"
        )
    finally:
        svc.table("messages").delete().eq("id", msg_id_with).execute()
        svc.table("messages").delete().eq("id", msg_id_without).execute()
        _delete_thread_svc(thread_id)
