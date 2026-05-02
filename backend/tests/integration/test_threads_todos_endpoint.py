"""Integration tests for GET /threads/{thread_id}/todos endpoint.

Plan 17-05 / TODO-07 — Thread-reload hydration endpoint for the Plan Panel.

Covers:
  - Ordered todo list returned for authenticated user (position ASC).
  - Empty thread returns {"todos": []}.
  - Missing Authorization header → 401.
  - RLS isolation: User B sees [] for User A's thread (not a 403 — matches v1.0 behavior).
  - Unknown thread_id → 200 OK with {"todos": []} (matches /messages behavior).
  - Response shape: each item has exactly {id, content, status, position} — no leakage.

All tests FAIL at RED (endpoint does not exist — 404).
After Task 2 (endpoint added to threads.py), all 6 should PASS (GREEN).

Requirements covered: TODO-07, D-27, D-28, T-17-12, T-17-13

Run (TDD RED — expect 6 failures):
    cd backend && source venv/bin/activate && \\
      pytest tests/integration/test_threads_todos_endpoint.py -v

Run (TDD GREEN — expect 6 passed):
    cd backend && source venv/bin/activate && \\
      TEST_EMAIL="test@test.com" TEST_PASSWORD='!*-3-3?3uZ?b$v&' \\
      TEST_EMAIL_2="test-2@test.com" TEST_PASSWORD_2='fK4$Wd?HGKmb#A2' \\
      pytest tests/integration/test_threads_todos_endpoint.py -v
"""

from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient

from app.database import get_supabase_authed_client, get_supabase_client
from app.main import app

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TEST_EMAIL = os.environ.get("TEST_EMAIL", "test@test.com")
TEST_PASSWORD = os.environ.get("TEST_PASSWORD", "!*-3-3?3uZ?b$v&")
TEST_EMAIL_2 = os.environ.get("TEST_EMAIL_2", "test-2@test.com")
TEST_PASSWORD_2 = os.environ.get("TEST_PASSWORD_2", "fK4$Wd?HGKmb#A2")

client = TestClient(app)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _login(email: str, password: str) -> str:
    """Return a JWT access token for the given credentials via Supabase auth."""
    svc = get_supabase_client()
    result = svc.auth.sign_in_with_password({"email": email, "password": password})
    return result.session.access_token


def _get_user_id(email: str, password: str) -> str:
    """Return the Supabase user UUID for the given credentials."""
    svc = get_supabase_client()
    result = svc.auth.sign_in_with_password({"email": email, "password": password})
    return str(result.user.id)


def _create_thread_svc(user_id: str) -> str:
    """Create a thread row via service-role and return its ID."""
    svc = get_supabase_client()
    thread_id = str(uuid.uuid4())
    svc.table("threads").insert({
        "id": thread_id,
        "user_id": user_id,
        "title": f"test-17-05-{thread_id[:8]}",
    }).execute()
    return thread_id


def _insert_todos_svc(thread_id: str, user_id: str, todos: list[dict]) -> list[str]:
    """Insert agent_todos rows via service-role (bypasses RLS). Returns list of IDs."""
    svc = get_supabase_client()
    ids: list[str] = []
    for todo in todos:
        todo_id = str(uuid.uuid4())
        svc.table("agent_todos").insert({
            "id": todo_id,
            "thread_id": thread_id,
            "user_id": user_id,
            "content": todo["content"],
            "status": todo.get("status", "pending"),
            "position": todo["position"],
        }).execute()
        ids.append(todo_id)
    return ids


def _delete_thread_svc(thread_id: str) -> None:
    """Delete a thread row via service-role (cascades to agent_todos)."""
    svc = get_supabase_client()
    try:
        svc.table("threads").delete().eq("id", thread_id).execute()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Test 1: GET /threads/{id}/todos returns ordered list
# ---------------------------------------------------------------------------


def test_get_todos_returns_ordered_list():
    """User A creates thread + 3 todos; GET returns them ordered by position ASC.

    Verifies: 200 OK, body {"todos": [...]}, 3 items in position order (0, 1, 2).
    Fails before endpoint is added (404 — RED).
    """
    user_a_id = _get_user_id(TEST_EMAIL, TEST_PASSWORD)
    token_a = _login(TEST_EMAIL, TEST_PASSWORD)
    thread_id = _create_thread_svc(user_a_id)

    try:
        # Insert 3 todos with positions out of insertion order to verify ordering
        _insert_todos_svc(thread_id, user_a_id, [
            {"content": "Third task", "status": "pending", "position": 2},
            {"content": "First task", "status": "in_progress", "position": 0},
            {"content": "Second task", "status": "completed", "position": 1},
        ])

        response = client.get(
            f"/threads/{thread_id}/todos",
            headers={"Authorization": f"Bearer {token_a}"},
        )

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )
        body = response.json()
        assert "todos" in body, f"Response missing 'todos' key: {body}"

        todos = body["todos"]
        assert len(todos) == 3, f"Expected 3 todos, got {len(todos)}: {todos}"

        # Verify ordering by position ASC
        positions = [t["position"] for t in todos]
        assert positions == sorted(positions), (
            f"Todos not ordered by position ASC: {positions}"
        )
        assert positions == [0, 1, 2], f"Expected positions [0,1,2], got {positions}"

        # Verify content matches position order
        assert todos[0]["content"] == "First task"
        assert todos[1]["content"] == "Second task"
        assert todos[2]["content"] == "Third task"

    finally:
        _delete_thread_svc(thread_id)


# ---------------------------------------------------------------------------
# Test 2: Empty thread returns {"todos": []}
# ---------------------------------------------------------------------------


def test_get_todos_empty_thread():
    """User A creates thread with no todos; GET returns {"todos": []}.

    Fails before endpoint is added (404 — RED).
    """
    user_a_id = _get_user_id(TEST_EMAIL, TEST_PASSWORD)
    token_a = _login(TEST_EMAIL, TEST_PASSWORD)
    thread_id = _create_thread_svc(user_a_id)

    try:
        response = client.get(
            f"/threads/{thread_id}/todos",
            headers={"Authorization": f"Bearer {token_a}"},
        )

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )
        body = response.json()
        assert body == {"todos": []}, (
            f"Expected {{\"todos\": []}}, got {body}"
        )

    finally:
        _delete_thread_svc(thread_id)


# ---------------------------------------------------------------------------
# Test 3: Missing Authorization → 401
# ---------------------------------------------------------------------------


def test_get_todos_unauthorized_no_token():
    """GET /threads/{id}/todos without Authorization header → 403.

    Note: The existing get_current_user dependency returns 403 "Not authenticated"
    (not 401) — this matches project convention (see test_admin_settings_auth.py).
    """
    # Use a random UUID — we expect 403 before any DB access
    fake_thread_id = str(uuid.uuid4())

    response = client.get(f"/threads/{fake_thread_id}/todos")

    assert response.status_code == 403, (
        f"Expected 403 when no token provided, got {response.status_code}: {response.text}"
    )


# ---------------------------------------------------------------------------
# Test 4: RLS isolation — User B sees [] for User A's thread
# ---------------------------------------------------------------------------


def test_get_todos_rls_isolation_returns_empty():
    """User B's JWT scoped to their own data; User A's thread todos are invisible.

    User A creates thread + todos (via service-role).
    User B calls GET /threads/{user_a_thread_id}/todos with User B's JWT.
    Expected: 200 OK with {"todos": []} — RLS filters the rows, not a 403.

    This matches v1.0 behavior: RLS returns empty set, not an authorization error.
    Verifies T-17-12 mitigation.

    Fails before endpoint is added (404 — RED).
    """
    user_a_id = _get_user_id(TEST_EMAIL, TEST_PASSWORD)
    token_b = _login(TEST_EMAIL_2, TEST_PASSWORD_2)

    thread_id = _create_thread_svc(user_a_id)

    try:
        # Insert User A's todos via service-role
        _insert_todos_svc(thread_id, user_a_id, [
            {"content": "User A's private todo", "status": "pending", "position": 0},
        ])

        # User B calls the endpoint with their own JWT
        response = client.get(
            f"/threads/{thread_id}/todos",
            headers={"Authorization": f"Bearer {token_b}"},
        )

        assert response.status_code == 200, (
            f"Expected 200 (RLS empty set), got {response.status_code}: {response.text}"
        )
        body = response.json()
        assert body == {"todos": []}, (
            f"RLS isolation failed: User B should see {{\"todos\": []}}, got {body}"
        )

    finally:
        _delete_thread_svc(thread_id)


# ---------------------------------------------------------------------------
# Test 5: Unknown thread_id → 200 OK with {"todos": []}
# ---------------------------------------------------------------------------


def test_get_todos_unknown_thread():
    """GET /threads/{nonexistent_uuid}/todos with valid JWT → 200 OK with {"todos": []}.

    Matches existing /messages behavior: returns empty list rather than 404.
    RLS simply filters the non-existent rows to an empty set.

    Fails before endpoint is added (404 — RED).
    """
    token_a = _login(TEST_EMAIL, TEST_PASSWORD)
    nonexistent_thread_id = str(uuid.uuid4())

    response = client.get(
        f"/threads/{nonexistent_thread_id}/todos",
        headers={"Authorization": f"Bearer {token_a}"},
    )

    assert response.status_code == 200, (
        f"Expected 200 for unknown thread (RLS empty set), got {response.status_code}: {response.text}"
    )
    body = response.json()
    assert body == {"todos": []}, (
        f"Expected {{\"todos\": []}}, got {body}"
    )


# ---------------------------------------------------------------------------
# Test 6: Response shape — exactly {id, content, status, position}
# ---------------------------------------------------------------------------


def test_get_todos_response_shape():
    """Each todo item has exactly {id, content, status, position} — no extra field leakage.

    Verifies that user_id, thread_id, created_at, updated_at are NOT included
    in the response (minimal projection per plan spec and D-17 SSE shape).

    Fails before endpoint is added (404 — RED).
    """
    user_a_id = _get_user_id(TEST_EMAIL, TEST_PASSWORD)
    token_a = _login(TEST_EMAIL, TEST_PASSWORD)
    thread_id = _create_thread_svc(user_a_id)

    try:
        _insert_todos_svc(thread_id, user_a_id, [
            {"content": "Shape test todo", "status": "in_progress", "position": 0},
        ])

        response = client.get(
            f"/threads/{thread_id}/todos",
            headers={"Authorization": f"Bearer {token_a}"},
        )

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )
        body = response.json()
        todos = body["todos"]
        assert len(todos) == 1, f"Expected 1 todo, got {len(todos)}"

        item = todos[0]
        expected_keys = {"id", "content", "status", "position"}
        actual_keys = set(item.keys())

        assert actual_keys == expected_keys, (
            f"Response shape mismatch. "
            f"Expected keys: {expected_keys}. "
            f"Actual keys: {actual_keys}. "
            f"Extra keys: {actual_keys - expected_keys}. "
            f"Missing keys: {expected_keys - actual_keys}."
        )

        # Spot-check types
        assert isinstance(item["id"], str), f"id must be a string, got {type(item['id'])}"
        assert isinstance(item["content"], str), f"content must be str, got {type(item['content'])}"
        assert item["status"] in ("pending", "in_progress", "completed"), (
            f"status must be one of pending/in_progress/completed, got {item['status']!r}"
        )
        assert isinstance(item["position"], int), f"position must be int, got {type(item['position'])}"

    finally:
        _delete_thread_svc(thread_id)
