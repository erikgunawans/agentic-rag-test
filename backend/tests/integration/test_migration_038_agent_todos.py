"""Integration tests for migration 038: agent_todos table + messages.deep_mode column.

These tests verify:
  - Schema: agent_todos columns, constraints (6 defined tests per plan spec)
  - RLS: SEC-01 regression — User A cannot SELECT/INSERT/UPDATE/DELETE User B's todos
  - Trigger: handle_updated_at fires on agent_todos UPDATE

All 6 tests FAIL before migration 038 is applied (TDD RED gate).
After `supabase db push`, all 6 should PASS (TDD GREEN gate).

NOTE: Tests 1–4 use functional assertions (SELECT/INSERT) rather than querying
information_schema or pg_indexes directly — Supabase PostgREST only exposes the
public schema, not system catalog tables.

Requirements covered: TODO-01, MIG-01, MIG-04, SEC-01

Run (pre-migration — expect 6 errors):
    cd backend && source venv/bin/activate && \\
      pytest tests/integration/test_migration_038_agent_todos.py -v

Run (post-migration — expect 6 passed):
    cd backend && source venv/bin/activate && \\
      TEST_EMAIL="test@test.com" TEST_PASSWORD='!*-3-3?3uZ?b$v&' \\
      TEST_EMAIL_2="test-2@test.com" TEST_PASSWORD_2='fK4$Wd?HGKmb#A2' \\
      pytest tests/integration/test_migration_038_agent_todos.py -v
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
# Helpers
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


def _create_thread_svc(user_id: str) -> str:
    """Create a thread row via service-role and return its ID."""
    svc = get_supabase_client()
    thread_id = str(uuid.uuid4())
    svc.table("threads").insert({
        "id": thread_id,
        "user_id": user_id,
        "title": f"test-migration-038-{thread_id[:8]}",
    }).execute()
    return thread_id


def _delete_thread_svc(thread_id: str) -> None:
    """Delete a thread row via service-role (cascades to agent_todos)."""
    svc = get_supabase_client()
    try:
        svc.table("threads").delete().eq("id", thread_id).execute()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Test 1: Schema columns present on agent_todos
# ---------------------------------------------------------------------------


def test_schema_columns_present():
    """agent_todos table has all 8 required columns.

    Uses a SELECT with all column names explicitly — PostgREST raises PGRST204
    if any column is missing, and the INSERT round-trip validates types.
    Fails with relation-not-found before migration 038 is applied (RED).
    """
    user_a_id = _get_user_id(TEST_EMAIL, TEST_PASSWORD)
    svc = get_supabase_client()
    thread_id = _create_thread_svc(user_a_id)
    todo_id = str(uuid.uuid4())
    try:
        # INSERT with all 8 required columns — fails if any is absent or wrong type
        insert_result = svc.table("agent_todos").insert({
            "id": todo_id,
            "thread_id": thread_id,
            "user_id": user_a_id,
            "content": "schema verification row",
            "status": "pending",
            "position": 0,
        }).execute()
        assert insert_result.data, "INSERT returned no data — table may not exist"

        # SELECT back with all 8 columns explicitly named
        row = (
            svc.table("agent_todos")
            .select("id,thread_id,user_id,content,status,position,created_at,updated_at")
            .eq("id", todo_id)
            .single()
            .execute()
        )
        data = row.data
        assert data is not None, "SELECT returned no row"
        for col in ("id", "thread_id", "user_id", "content", "status", "position",
                    "created_at", "updated_at"):
            assert col in data, f"Column '{col}' missing from agent_todos"

        # Spot-check types: position must be int, content must be str
        assert isinstance(data["position"], int), (
            f"position must be integer, got {type(data['position'])}"
        )
        assert isinstance(data["content"], str), (
            f"content must be text, got {type(data['content'])}"
        )
    finally:
        svc.table("agent_todos").delete().eq("id", todo_id).execute()
        _delete_thread_svc(thread_id)


# ---------------------------------------------------------------------------
# Test 2: Check constraint on status column
# ---------------------------------------------------------------------------


def test_schema_check_constraint():
    """status CHECK constraint accepts valid values and rejects 'foo'.

    Inserts rows with each valid status (should succeed) and then inserts
    with status='foo' (should raise an exception from PostgreSQL CHECK).
    Fails before migration 038 is applied (table does not exist — RED).
    """
    user_a_id = _get_user_id(TEST_EMAIL, TEST_PASSWORD)
    svc = get_supabase_client()
    thread_id = _create_thread_svc(user_a_id)
    created_ids: list[str] = []
    try:
        # Valid statuses must succeed
        for pos, status in enumerate(("pending", "in_progress", "completed")):
            row_id = str(uuid.uuid4())
            res = svc.table("agent_todos").insert({
                "id": row_id,
                "thread_id": thread_id,
                "user_id": user_a_id,
                "content": f"valid status test ({status})",
                "status": status,
                "position": pos,
            }).execute()
            assert res.data, f"INSERT with valid status='{status}' returned no data"
            created_ids.append(row_id)

        # Invalid status must raise — PostgreSQL CHECK violation
        with pytest.raises(Exception) as exc_info:
            svc.table("agent_todos").insert({
                "id": str(uuid.uuid4()),
                "thread_id": thread_id,
                "user_id": user_a_id,
                "content": "bad status row",
                "status": "foo",
                "position": 99,
            }).execute()

        err = str(exc_info.value).lower()
        assert any(kw in err for kw in ("check", "constraint", "violates", "invalid", "23514")), (
            f"Expected CHECK constraint violation for status='foo', got: {exc_info.value}"
        )
    finally:
        for row_id in created_ids:
            svc.table("agent_todos").delete().eq("id", row_id).execute()
        _delete_thread_svc(thread_id)


# ---------------------------------------------------------------------------
# Test 3: Indexes present on agent_todos (functional verification)
# ---------------------------------------------------------------------------


def test_schema_indexes_present():
    """Verify indexed access patterns work on agent_todos.

    pg_indexes is not exposed via PostgREST, so we verify functionally:
    - Queries ordered by (thread_id, position) work without error (idx_agent_todos_thread)
    - Queries filtered + ordered by (user_id, created_at DESC) work (idx_agent_todos_user)

    Fails before migration 038 is applied (table does not exist — RED).
    """
    user_a_id = _get_user_id(TEST_EMAIL, TEST_PASSWORD)
    svc = get_supabase_client()
    thread_id = _create_thread_svc(user_a_id)
    todo_ids: list[str] = []
    try:
        # Insert two rows so ORDER BY has something to work with
        for pos in range(2):
            row_id = str(uuid.uuid4())
            svc.table("agent_todos").insert({
                "id": row_id,
                "thread_id": thread_id,
                "user_id": user_a_id,
                "content": f"index test row {pos}",
                "status": "pending",
                "position": pos,
            }).execute()
            todo_ids.append(row_id)

        # idx_agent_todos_thread: filter by thread_id, ORDER BY position
        r1 = (
            svc.table("agent_todos")
            .select("id,position")
            .eq("thread_id", thread_id)
            .order("position")
            .execute()
        )
        assert r1.data is not None, "Query on (thread_id, position) failed"
        assert len(r1.data) == 2, f"Expected 2 rows, got {len(r1.data)}"
        assert r1.data[0]["position"] <= r1.data[1]["position"], "Rows not ordered by position"

        # idx_agent_todos_user: filter by user_id, ORDER BY created_at DESC
        r2 = (
            svc.table("agent_todos")
            .select("id,created_at")
            .eq("user_id", user_a_id)
            .order("created_at", desc=True)
            .limit(10)
            .execute()
        )
        assert r2.data is not None, "Query on (user_id, created_at DESC) failed"
    finally:
        for row_id in todo_ids:
            svc.table("agent_todos").delete().eq("id", row_id).execute()
        _delete_thread_svc(thread_id)


# ---------------------------------------------------------------------------
# Test 4: messages.deep_mode column exists with correct type and default
# ---------------------------------------------------------------------------


def test_schema_messages_deep_mode_column():
    """messages.deep_mode column exists, is boolean, and defaults to false.

    Inserts a message WITHOUT specifying deep_mode, then SELECTs it back
    including the deep_mode column — verifies existence and default value.
    Fails before migration 038 is applied (column does not exist — RED).
    """
    user_a_id = _get_user_id(TEST_EMAIL, TEST_PASSWORD)
    svc = get_supabase_client()
    thread_id = _create_thread_svc(user_a_id)
    msg_id = str(uuid.uuid4())
    try:
        # Insert without specifying deep_mode — default should apply
        insert_result = svc.table("messages").insert({
            "id": msg_id,
            "thread_id": thread_id,
            "user_id": user_a_id,
            "role": "user",
            "content": "migration 038 deep_mode column test",
        }).execute()
        assert insert_result.data, "Message INSERT returned no data"

        # SELECT back with deep_mode explicitly in the column list
        row = (
            svc.table("messages")
            .select("id,deep_mode")
            .eq("id", msg_id)
            .single()
            .execute()
        )
        assert row.data is not None, "Message not found after INSERT"
        assert "deep_mode" in row.data, (
            "deep_mode column missing from messages — "
            "ALTER TABLE messages ADD COLUMN deep_mode not applied (migration 038 missing)"
        )
        assert row.data["deep_mode"] is False, (
            f"messages.deep_mode should default to false, got: {row.data['deep_mode']}"
        )

        # Also verify that explicitly setting deep_mode=True works (column accepts booleans)
        svc.table("messages").update({"deep_mode": True}).eq("id", msg_id).execute()
        row2 = (
            svc.table("messages")
            .select("deep_mode")
            .eq("id", msg_id)
            .single()
            .execute()
        )
        assert row2.data["deep_mode"] is True, (
            "messages.deep_mode should accept True after UPDATE"
        )
    finally:
        svc.table("messages").delete().eq("id", msg_id).execute()
        _delete_thread_svc(thread_id)


# ---------------------------------------------------------------------------
# Test 5: RLS — User A cannot access User B's agent_todos (SEC-01)
# ---------------------------------------------------------------------------


def test_rls_user_a_cannot_access_user_b_todos():
    """SEC-01: User A cannot SELECT, INSERT, UPDATE, or DELETE User B's todos.

    User B creates a thread + agent_todos row via service-role.
    User A's JWT-scoped client attempts:
      - SELECT → returns 0 rows (RLS filters)
      - INSERT into User B's thread_id → raises exception (RLS WITH CHECK)
      - UPDATE User B's row → 0 rows affected (RLS USING blocks)
      - DELETE User B's row → 0 rows affected (RLS USING blocks)

    Mirrors the v1.0 entity_registry RLS test pattern.
    Fails before migration 038 is applied (RED).
    """
    # Resolve user IDs
    user_a_id = _get_user_id(TEST_EMAIL, TEST_PASSWORD)
    user_b_id = _get_user_id(TEST_EMAIL_2, TEST_PASSWORD_2)

    # User A's JWT-scoped client
    token_a = _login(TEST_EMAIL, TEST_PASSWORD)
    client_a = get_supabase_authed_client(token_a)

    # Service-role client to set up User B's data
    svc = get_supabase_client()

    # Create User B's thread via service-role
    b_thread_id = _create_thread_svc(user_b_id)
    b_todo_id = None

    try:
        # Insert User B's agent_todos row via service-role (bypasses RLS)
        b_todo_id = str(uuid.uuid4())
        svc.table("agent_todos").insert({
            "id": b_todo_id,
            "thread_id": b_thread_id,
            "user_id": user_b_id,
            "content": "User B's secret todo",
            "status": "pending",
            "position": 0,
        }).execute()

        # ── RLS SELECT: User A must see 0 rows for User B's todo ──
        select_result = (
            client_a.table("agent_todos")
            .select("id")
            .eq("id", b_todo_id)
            .execute()
        )
        assert select_result.data == [], (
            f"RLS SELECT failed: User A should see 0 rows for User B's todo, "
            f"got: {select_result.data}"
        )

        # ── RLS INSERT: User A cannot insert into User B's thread ──
        insert_raised = False
        try:
            client_a.table("agent_todos").insert({
                "thread_id": b_thread_id,
                "user_id": user_a_id,
                "content": "Attacker todo in User B thread",
                "status": "pending",
                "position": 1,
            }).execute()
        except Exception:
            insert_raised = True

        if not insert_raised:
            # PostgREST may return 0 rows affected rather than raising; check result
            # The INSERT WITH CHECK on threads.user_id must block this
            verify = (
                svc.table("agent_todos")
                .select("id")
                .eq("thread_id", b_thread_id)
                .eq("user_id", user_a_id)
                .execute()
            )
            assert verify.data == [], (
                f"RLS INSERT failed: User A should not be able to insert into "
                f"User B's thread. Found rows: {verify.data}"
            )

        # ── RLS UPDATE: User A cannot update User B's todo ──
        update_result = (
            client_a.table("agent_todos")
            .update({"content": "Tampered by User A"})
            .eq("id", b_todo_id)
            .execute()
        )
        # Verify the row was NOT actually updated (RLS filters the target rows)
        verify_update = (
            svc.table("agent_todos")
            .select("content")
            .eq("id", b_todo_id)
            .execute()
        )
        if verify_update.data:
            assert verify_update.data[0]["content"] == "User B's secret todo", (
                f"RLS UPDATE failed: User A tampered with User B's todo. "
                f"Content is now: {verify_update.data[0]['content']}"
            )

        # ── RLS DELETE: User A cannot delete User B's todo ──
        client_a.table("agent_todos").delete().eq("id", b_todo_id).execute()
        # Verify the row still exists
        verify_delete = (
            svc.table("agent_todos")
            .select("id")
            .eq("id", b_todo_id)
            .execute()
        )
        assert len(verify_delete.data) == 1, (
            f"RLS DELETE failed: User A deleted User B's todo (id={b_todo_id}). "
            "RLS DELETE policy not enforced."
        )

    finally:
        # Cleanup: service-role deletes (cascade handles agent_todos via thread deletion)
        if b_todo_id:
            try:
                svc.table("agent_todos").delete().eq("id", b_todo_id).execute()
            except Exception:
                pass
        _delete_thread_svc(b_thread_id)


# ---------------------------------------------------------------------------
# Test 6: handle_updated_at trigger fires on agent_todos UPDATE
# ---------------------------------------------------------------------------


def test_handle_updated_at_trigger_fires():
    """handle_updated_at trigger (from migration 001) fires on agent_todos UPDATE.

    Insert a row, capture updated_at, wait 50ms, UPDATE content,
    assert updated_at advanced.

    Fails before migration 038 is applied (table does not exist — RED).
    """
    user_a_id = _get_user_id(TEST_EMAIL, TEST_PASSWORD)
    svc = get_supabase_client()

    thread_id = _create_thread_svc(user_a_id)
    todo_id = None

    try:
        # Insert row via service-role
        todo_id = str(uuid.uuid4())
        insert_result = svc.table("agent_todos").insert({
            "id": todo_id,
            "thread_id": thread_id,
            "user_id": user_a_id,
            "content": "Initial content",
            "status": "pending",
            "position": 0,
        }).execute()

        assert insert_result.data, (
            "INSERT into agent_todos returned no data — table may not exist."
        )

        # Capture initial updated_at
        row_before = (
            svc.table("agent_todos")
            .select("updated_at")
            .eq("id", todo_id)
            .single()
            .execute()
        )
        initial_updated_at = row_before.data["updated_at"]

        # Wait 50ms to ensure timestamp difference is detectable
        time.sleep(0.1)  # 100ms for reliability

        # UPDATE the content — trigger should advance updated_at
        svc.table("agent_todos").update({"content": "Updated content"}).eq("id", todo_id).execute()

        # Fetch updated row
        row_after = (
            svc.table("agent_todos")
            .select("updated_at")
            .eq("id", todo_id)
            .single()
            .execute()
        )
        new_updated_at = row_after.data["updated_at"]

        assert new_updated_at != initial_updated_at, (
            f"handle_updated_at trigger did NOT fire: updated_at unchanged "
            f"(before={initial_updated_at}, after={new_updated_at}). "
            "Check trigger registration in migration 038."
        )
        # New timestamp must be strictly after the initial one
        assert new_updated_at > initial_updated_at, (
            f"updated_at went backwards: before={initial_updated_at}, after={new_updated_at}"
        )

    finally:
        if todo_id:
            try:
                svc.table("agent_todos").delete().eq("id", todo_id).execute()
            except Exception:
                pass
        _delete_thread_svc(thread_id)
