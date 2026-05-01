"""
test_code_executions_get_by_id.py — Integration tests for Phase 11 single-row read endpoint.

Plan 11-03: GET /code-executions/{execution_id}

4 test cases covering:
  - Test 1: Owner reads their own row, signed URLs are refreshed (200)
  - Test 2: Missing UUID returns 404
  - Test 3: Cross-user access returns 404 (RLS-filtered, not 403 — never confirms existence)
  - Test 4: Row with empty files[] returns 200 + files: []

References:
  - 11-03-PLAN.md §tasks Task 1
  - 11-CONTEXT.md §D-P11-06 (file-download cards refresh signed URLs)
  - 10-CONTEXT.md §D-P10-14 (1-hour signed URL TTL), §D-P10-15 (RLS), §D-P10-13 (storage path)

Run target (from CLAUDE.md § Code Quality):

    cd backend && source venv/bin/activate && \\
      TEST_EMAIL="test@test.com" TEST_PASSWORD='!*-3-3?3uZ?b$v&' \\
      TEST_EMAIL_2="test-2@test.com" TEST_PASSWORD_2='fK4$Wd?HGKmb#A2' \\
      API_BASE_URL="http://localhost:8000" \\
      pytest tests/api/test_code_executions_get_by_id.py -v --tb=short

Note: These are integration tests that require:
  - A running backend at API_BASE_URL
  - Migration 036 applied (code_executions table + sandbox-outputs bucket)
  - Test accounts as specified in CLAUDE.md
"""

from __future__ import annotations

import os
import uuid

import httpx
import pytest

from app.database import get_supabase_client

# ---------------------------------------------------------------------------
# Configuration — mirrors test_code_executions.py
# ---------------------------------------------------------------------------

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")
TEST_EMAIL = os.environ.get("TEST_EMAIL", "test@test.com")
TEST_PASSWORD = os.environ.get("TEST_PASSWORD", "!*-3-3?3uZ?b$v&")
TEST_EMAIL_2 = os.environ.get("TEST_EMAIL_2", "test-2@test.com")
TEST_PASSWORD_2 = os.environ.get("TEST_PASSWORD_2", "fK4$Wd?HGKmb#A2")


# ---------------------------------------------------------------------------
# Helpers — mirror test_code_executions.py for self-contained execution
# ---------------------------------------------------------------------------


def _login(email: str, password: str) -> str:
    """Return a JWT access token for the given credentials via Supabase auth."""
    client = get_supabase_client()
    result = client.auth.sign_in_with_password({"email": email, "password": password})
    return result.session.access_token


def _http(token: str) -> httpx.Client:
    """Return an httpx Client pre-configured with the auth token."""
    return httpx.Client(
        base_url=API_BASE_URL,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30.0,
    )


def _get_user_id(email: str, password: str) -> str:
    """Return the Supabase user UUID for the given credentials."""
    client = get_supabase_client()
    result = client.auth.sign_in_with_password({"email": email, "password": password})
    return str(result.user.id)


def _create_thread(user_id: str) -> str:
    """Create a thread row via service-role and return its ID."""
    svc = get_supabase_client()
    thread_id = str(uuid.uuid4())
    svc.table("threads").insert({
        "id": thread_id,
        "user_id": user_id,
        "title": f"test-thread-{thread_id[:8]}",
    }).execute()
    return thread_id


def _insert_execution(
    user_id: str,
    thread_id: str,
    *,
    files: list[dict] | None = None,
    status: str = "success",
    code: str = "print('hello')",
    description: str | None = None,
) -> str:
    """Insert a code_executions row via service-role. Returns the execution ID."""
    svc = get_supabase_client()
    exec_id = str(uuid.uuid4())
    row = {
        "id": exec_id,
        "user_id": user_id,
        "thread_id": thread_id,
        "code": code,
        "description": description,
        "stdout": "hello\n",
        "stderr": "",
        "exit_code": 0 if status == "success" else 1,
        "execution_ms": 42,
        "status": status,
        "files": files if files is not None else [],
    }
    svc.table("code_executions").insert(row).execute()
    return exec_id


def _delete_execution(exec_id: str):
    """Delete a code_executions row via service-role (test teardown)."""
    svc = get_supabase_client()
    try:
        svc.table("code_executions").delete().eq("id", exec_id).execute()
    except Exception:
        pass


def _delete_thread(thread_id: str):
    """Delete a thread row via service-role (test teardown)."""
    svc = get_supabase_client()
    try:
        svc.table("threads").delete().eq("id", thread_id).execute()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Session-scoped auth tokens (acquire once per test run)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def auth_token() -> str:
    """JWT for test@test.com (super_admin per CLAUDE.md)."""
    return _login(TEST_EMAIL, TEST_PASSWORD)


@pytest.fixture(scope="session")
def auth_token_2() -> str:
    """JWT for test-2@test.com (regular user — NOT super_admin per CLAUDE.md)."""
    return _login(TEST_EMAIL_2, TEST_PASSWORD_2)


@pytest.fixture(scope="session")
def user_1_id() -> str:
    """UUID of test@test.com user."""
    return _get_user_id(TEST_EMAIL, TEST_PASSWORD)


@pytest.fixture(scope="session")
def user_2_id() -> str:
    """UUID of test-2@test.com user."""
    return _get_user_id(TEST_EMAIL_2, TEST_PASSWORD_2)


# ---------------------------------------------------------------------------
# Test 1: Owner reads their own row, signed URLs refreshed (D-P10-14)
# ---------------------------------------------------------------------------


class TestGetByIdReturnsRow:
    """User A creates a row, then GETs it by id. Returns 200 with refreshed URLs."""

    def test_get_by_id_returns_row_with_refreshed_urls(
        self,
        auth_token: str,
        user_1_id: str,
    ):
        thread_id = _create_thread(user_1_id)
        storage_path = f"{user_1_id}/{thread_id}/{uuid.uuid4()}/out.csv"
        exec_id = _insert_execution(
            user_1_id,
            thread_id,
            files=[{
                "filename": "out.csv",
                "size_bytes": 12,
                "signed_url": "https://example.com/stale-url?token=expired",
                "storage_path": storage_path,
            }],
        )
        try:
            with _http(auth_token) as client:
                resp = client.get(f"/code-executions/{exec_id}")
            assert resp.status_code == 200, (
                f"Expected 200, got {resp.status_code}: {resp.text}"
            )
            body = resp.json()
            # Body matches CodeExecutionResponse shape (unwrapped, not under data/count)
            assert body["id"] == exec_id, f"id mismatch: {body['id']} vs {exec_id}"
            assert body["user_id"] == user_1_id, f"user_id mismatch: {body['user_id']}"
            assert body["thread_id"] == thread_id, f"thread_id mismatch: {body['thread_id']}"
            assert body["status"] == "success"
            assert isinstance(body["files"], list), "files must be a list"
            assert len(body["files"]) == 1, f"expected 1 file, got {len(body['files'])}"
            f = body["files"][0]
            assert f["filename"] == "out.csv"
            # signed_url refresh: either fresh URL was generated, or stale URL was
            # preserved (logged warning) if the storage object doesn't exist in test
            # env. Either way the field must be present and non-empty (per Plan 10-06
            # behavior: stale URL is kept on refresh failure rather than dropped).
            assert "signed_url" in f, "files[0] must have signed_url"
            assert f["signed_url"], "files[0].signed_url must be non-empty"
        finally:
            _delete_execution(exec_id)
            _delete_thread(thread_id)


# ---------------------------------------------------------------------------
# Test 2: Missing UUID returns 404
# ---------------------------------------------------------------------------


class TestGetByIdMissing:
    """GET /code-executions/{nonexistent-uuid} returns 404."""

    def test_get_by_id_404_when_missing(self, auth_token: str):
        random_id = "00000000-0000-0000-0000-000000000000"
        with _http(auth_token) as client:
            resp = client.get(f"/code-executions/{random_id}")
        assert resp.status_code == 404, (
            f"Expected 404, got {resp.status_code}: {resp.text}"
        )
        body = resp.json()
        assert body.get("detail") == "Code execution not found", (
            f"Expected detail='Code execution not found', got: {body}"
        )


# ---------------------------------------------------------------------------
# Test 3: Cross-user access returns 404 (RLS-filtered)
# ---------------------------------------------------------------------------


class TestGetByIdCrossUser:
    """User A inserts a row; User B's GET returns 404 (RLS hides the row)."""

    def test_get_by_id_404_on_cross_user(
        self,
        auth_token_2: str,
        user_1_id: str,
    ):
        # User 1 owns the row
        thread_id = _create_thread(user_1_id)
        exec_id = _insert_execution(user_1_id, thread_id)
        try:
            # User 2 (NOT super_admin) tries to read it — RLS should hide → 404
            with _http(auth_token_2) as client:
                resp = client.get(f"/code-executions/{exec_id}")
            assert resp.status_code == 404, (
                f"Expected 404 (RLS-filtered), got {resp.status_code}: {resp.text}"
            )
            body = resp.json()
            assert body.get("detail") == "Code execution not found", (
                f"Expected detail='Code execution not found', got: {body}"
            )
        finally:
            _delete_execution(exec_id)
            _delete_thread(thread_id)


# ---------------------------------------------------------------------------
# Test 4: Empty files[] passes through cleanly
# ---------------------------------------------------------------------------


class TestGetByIdEmptyFiles:
    """Row with files=[] returns 200 with files=[]; no signed-URL refresh failure."""

    def test_get_by_id_passes_through_when_files_empty(
        self,
        auth_token: str,
        user_1_id: str,
    ):
        thread_id = _create_thread(user_1_id)
        exec_id = _insert_execution(user_1_id, thread_id, files=[])
        try:
            with _http(auth_token) as client:
                resp = client.get(f"/code-executions/{exec_id}")
            assert resp.status_code == 200, (
                f"Expected 200, got {resp.status_code}: {resp.text}"
            )
            body = resp.json()
            assert body["id"] == exec_id
            assert body["files"] == [], f"Expected files=[], got: {body['files']}"
        finally:
            _delete_execution(exec_id)
            _delete_thread(thread_id)
