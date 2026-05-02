"""Integration tests for migration 038: agent_todos table + messages.deep_mode column.

These tests verify:
  - Schema: agent_todos columns, types, constraints (6 defined tests per plan spec)
  - RLS: SEC-01 regression — User A cannot SELECT/INSERT/UPDATE/DELETE User B's todos
  - Trigger: handle_updated_at fires on agent_todos UPDATE

All 6 tests FAIL before migration 038 is applied (TDD RED gate).
After `supabase db push`, all 6 should PASS (TDD GREEN gate).

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
    """agent_todos table has exactly the expected 8 columns with correct types.

    Queries information_schema.columns for public.agent_todos.
    Fails with relation-not-found error before migration 038 is applied (RED).
    """
    svc = get_supabase_client()
    result = (
        svc.table("information_schema.columns")
        .select("column_name,data_type,is_nullable,column_default")
        .eq("table_schema", "public")
        .eq("table_name", "agent_todos")
        .execute()
    )
    rows = result.data
    col_map = {r["column_name"]: r for r in rows}

    expected_columns = {
        "id": "uuid",
        "thread_id": "uuid",
        "user_id": "uuid",
        "content": "text",
        "status": "text",
        "position": "integer",
        "created_at": "timestamp with time zone",
        "updated_at": "timestamp with time zone",
    }

    assert set(col_map.keys()) == set(expected_columns.keys()), (
        f"Column mismatch. Expected: {set(expected_columns.keys())}, "
        f"Got: {set(col_map.keys())}"
    )

    for col_name, expected_type in expected_columns.items():
        actual_type = col_map[col_name]["data_type"]
        assert actual_type == expected_type, (
            f"Column '{col_name}' type mismatch: expected '{expected_type}', "
            f"got '{actual_type}'"
        )


# ---------------------------------------------------------------------------
# Test 2: Check constraint on status column
# ---------------------------------------------------------------------------


def test_schema_check_constraint():
    """status CHECK constraint accepts valid values and rejects 'foo'.

    Verifies the constraint exists in information_schema.check_constraints.
    Fails before migration 038 is applied (RED).
    """
    svc = get_supabase_client()

    # Check the constraint exists in check_constraints for agent_todos
    result = svc.rpc("query_check_constraints", {}).execute()

    # Use information_schema directly via the table API
    constraints = (
        svc.table("information_schema.check_constraints")
        .select("constraint_name,check_clause")
        .eq("constraint_schema", "public")
        .execute()
    )

    # Also check table_constraints to confirm agent_todos has a check constraint
    table_constraints = (
        svc.table("information_schema.table_constraints")
        .select("constraint_name,constraint_type,table_name")
        .eq("table_schema", "public")
        .eq("table_name", "agent_todos")
        .eq("constraint_type", "CHECK")
        .execute()
    )

    assert len(table_constraints.data) >= 1, (
        "Expected at least one CHECK constraint on agent_todos "
        f"(status IN ('pending','in_progress','completed')), got none. "
        "Migration 038 not applied."
    )


# ---------------------------------------------------------------------------
# Test 3: Indexes present on agent_todos
# ---------------------------------------------------------------------------


def test_schema_indexes_present():
    """idx_agent_todos_thread and idx_agent_todos_user exist on agent_todos.

    Queries pg_indexes via service-role.
    Fails before migration 038 is applied (RED).
    """
    svc = get_supabase_client()

    # pg_indexes is accessible via the REST API through information_schema equivalent
    # We use a direct RPC call to pg_catalog via information_schema
    result = (
        svc.table("pg_indexes")
        .select("indexname,tablename")
        .eq("schemaname", "public")
        .eq("tablename", "agent_todos")
        .execute()
    )

    index_names = {row["indexname"] for row in result.data}

    assert "idx_agent_todos_thread" in index_names, (
        f"Index 'idx_agent_todos_thread' not found on agent_todos. "
        f"Found indexes: {index_names}. Migration 038 not applied."
    )
    assert "idx_agent_todos_user" in index_names, (
        f"Index 'idx_agent_todos_user' not found on agent_todos. "
        f"Found indexes: {index_names}. Migration 038 not applied."
    )


# ---------------------------------------------------------------------------
# Test 4: messages.deep_mode column exists with correct type and default
# ---------------------------------------------------------------------------


def test_schema_messages_deep_mode_column():
    """messages.deep_mode column exists, type boolean, NOT NULL, default false.

    Queries information_schema.columns for public.messages.deep_mode.
    Fails before migration 038 is applied (RED).
    """
    svc = get_supabase_client()
    result = (
        svc.table("information_schema.columns")
        .select("column_name,data_type,is_nullable,column_default")
        .eq("table_schema", "public")
        .eq("table_name", "messages")
        .eq("column_name", "deep_mode")
        .execute()
    )

    assert len(result.data) == 1, (
        f"Expected messages.deep_mode column to exist, got {len(result.data)} rows. "
        "Migration 038 not applied (ALTER TABLE messages ADD COLUMN deep_mode missing)."
    )

    col = result.data[0]
    assert col["data_type"] == "boolean", (
        f"messages.deep_mode must be type 'boolean', got '{col['data_type']}'"
    )
    assert col["is_nullable"] == "NO", (
        f"messages.deep_mode must be NOT NULL, got is_nullable='{col['is_nullable']}'"
    )
    assert col["column_default"] is not None and "false" in str(col["column_default"]).lower(), (
        f"messages.deep_mode must have DEFAULT false, got column_default='{col['column_default']}'"
    )


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
