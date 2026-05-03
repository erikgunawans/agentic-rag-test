"""Phase 18 / WS-09 — API tests for workspace endpoints.

Tests the two REST endpoints:
  GET /threads/{thread_id}/files          → JSON array
  GET /threads/{thread_id}/files/{path}  → text body or 307 to signed URL

Test matrix:
  Test 1: No auth returns 403
  Test 2: Empty thread returns []
  Test 3: Write text file via service, list returns it, read returns body
  Test 4: Missing file returns 404
  Test 5: Invalid path (traversal attempt) returns 400 or 404
  Test 6: Cross-user RLS isolation — User B cannot see User A's files
  Test 7: WORKSPACE_ENABLED=False gate smoke-check (skipped — process-isolated reload)

Runs against live Supabase test DB (credentials from CLAUDE.md § Testing):
    cd backend && source venv/bin/activate && \\
      WORKSPACE_ENABLED=true \\
      TEST_EMAIL="test@test.com" TEST_PASSWORD='!*-3-3?3uZ?b$v&' \\
      TEST_EMAIL_2="test-2@test.com" TEST_PASSWORD_2='fK4$Wd?HGKmb#A2' \\
      API_BASE_URL="http://localhost:8000" \\
      pytest tests/api/test_workspace_endpoints.py -v --tb=short

Requirements:
  - Backend running with WORKSPACE_ENABLED=true
  - Migration 039 applied (workspace_files table + RLS)
  - Test accounts as per CLAUDE.md
"""

from __future__ import annotations

import asyncio
import os
import uuid

import httpx
import pytest

from app.database import get_supabase_client
from app.services.workspace_service import WorkspaceService

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")
TEST_EMAIL = os.environ.get("TEST_EMAIL", "test@test.com")
TEST_PASSWORD = os.environ.get("TEST_PASSWORD", "!*-3-3?3uZ?b$v&")
TEST_EMAIL_2 = os.environ.get("TEST_EMAIL_2", "test-2@test.com")
TEST_PASSWORD_2 = os.environ.get("TEST_PASSWORD_2", "fK4$Wd?HGKmb#A2")


# ---------------------------------------------------------------------------
# Helpers / Fixtures
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


def _http(token: str) -> httpx.Client:
    """Return an httpx Client pre-configured with the auth token."""
    return httpx.Client(
        base_url=API_BASE_URL,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30.0,
        follow_redirects=False,  # We test 307 redirects explicitly
    )


def _create_thread(user_id: str) -> str:
    """Create a thread row via service-role and return its ID."""
    svc = get_supabase_client()
    thread_id = str(uuid.uuid4())
    svc.table("threads").insert({
        "id": thread_id,
        "user_id": user_id,
        "title": f"ws-test-{thread_id[:8]}",
    }).execute()
    return thread_id


def _delete_thread(thread_id: str) -> None:
    """Delete a thread and its workspace_files via service-role (teardown)."""
    svc = get_supabase_client()
    try:
        svc.table("workspace_files").delete().eq("thread_id", thread_id).execute()
    except Exception:
        pass
    try:
        svc.table("threads").delete().eq("id", thread_id).execute()
    except Exception:
        pass


def _run(coro):
    """Run an async coroutine in tests (simple asyncio.run wrapper)."""
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Session-scoped auth tokens (acquire once per test run)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def auth_token() -> str:
    """JWT for test@test.com (super_admin per CLAUDE.md)."""
    return _login(TEST_EMAIL, TEST_PASSWORD)


@pytest.fixture(scope="session")
def auth_token_2() -> str:
    """JWT for test-2@test.com (regular user)."""
    return _login(TEST_EMAIL_2, TEST_PASSWORD_2)


@pytest.fixture(scope="session")
def user_1_id() -> str:
    """UUID of test@test.com."""
    return _get_user_id(TEST_EMAIL, TEST_PASSWORD)


@pytest.fixture(scope="session")
def user_2_id() -> str:
    """UUID of test-2@test.com."""
    return _get_user_id(TEST_EMAIL_2, TEST_PASSWORD_2)


@pytest.fixture(scope="module")
def thread_1(user_1_id: str):
    """A fresh thread owned by User 1. Cleaned up after the module."""
    tid = _create_thread(user_1_id)
    yield tid
    _delete_thread(tid)


# ---------------------------------------------------------------------------
# Test 1: Auth gate — 403 without Authorization header
# ---------------------------------------------------------------------------


class TestAuthGate:
    """Both endpoints reject requests without an Authorization header."""

    def test_list_no_auth_returns_403(self):
        tid = str(uuid.uuid4())
        with httpx.Client(base_url=API_BASE_URL, timeout=10.0) as client:
            resp = client.get(f"/threads/{tid}/files")
        assert resp.status_code == 403, (
            f"Expected 403 (no auth on list), got {resp.status_code}: {resp.text}"
        )

    def test_read_no_auth_returns_403(self):
        tid = str(uuid.uuid4())
        with httpx.Client(base_url=API_BASE_URL, timeout=10.0) as client:
            resp = client.get(f"/threads/{tid}/files/readme.md")
        assert resp.status_code == 403, (
            f"Expected 403 (no auth on read), got {resp.status_code}: {resp.text}"
        )


# ---------------------------------------------------------------------------
# Test 2: Empty thread returns []
# ---------------------------------------------------------------------------


class TestEmptyList:
    """Fresh thread with no workspace files returns an empty JSON array."""

    def test_list_empty_thread(self, auth_token: str, user_1_id: str):
        # Create a dedicated thread so we know it's empty
        tid = _create_thread(user_1_id)
        try:
            with _http(auth_token) as client:
                resp = client.get(f"/threads/{tid}/files")
            assert resp.status_code == 200, (
                f"Expected 200 on empty list, got {resp.status_code}: {resp.text}"
            )
            assert resp.json() == [], (
                f"Expected [] for empty thread, got {resp.json()}"
            )
        finally:
            _delete_thread(tid)


# ---------------------------------------------------------------------------
# Test 3: Write via service → list shows file → read returns body
# ---------------------------------------------------------------------------


class TestWriteListRead:
    """Write a text file via WorkspaceService; verify list and read endpoints."""

    def test_write_then_list_then_read_text(self, auth_token: str, thread_1: str):
        token = auth_token
        tid = thread_1
        ws = WorkspaceService(token=token)

        # Write a markdown file via service layer
        write_result = _run(ws.write_text_file(tid, "notes/hello.md", "# Hello\n\nworld"))
        assert "error" not in write_result, f"write_text_file failed: {write_result}"

        # List endpoint should now return the file
        with _http(token) as client:
            resp = client.get(f"/threads/{tid}/files")
        assert resp.status_code == 200, f"list status={resp.status_code}: {resp.text}"
        files = resp.json()
        paths = [f["file_path"] for f in files]
        assert "notes/hello.md" in paths, (
            f"Expected 'notes/hello.md' in list, got paths={paths}"
        )

        # Read endpoint should return the content inline
        with _http(token) as client:
            resp = client.get(f"/threads/{tid}/files/notes/hello.md")
        assert resp.status_code == 200, f"read status={resp.status_code}: {resp.text}"
        assert "Hello" in resp.text, f"Expected content in body, got: {resp.text[:200]}"
        ct = resp.headers.get("content-type", "")
        assert ct.startswith("text/"), f"Expected text/* content-type, got: {ct}"


# ---------------------------------------------------------------------------
# Test 4: Missing file returns 404
# ---------------------------------------------------------------------------


class TestMissingFile:
    """Reading a file that does not exist returns 404."""

    def test_read_missing_file_404(self, auth_token: str, thread_1: str):
        missing_path = f"does/not/exist-{uuid.uuid4().hex}.md"
        with _http(auth_token) as client:
            resp = client.get(f"/threads/{thread_1}/files/{missing_path}")
        assert resp.status_code == 404, (
            f"Expected 404 for missing file, got {resp.status_code}: {resp.text}"
        )


# ---------------------------------------------------------------------------
# Test 5: Invalid path (traversal) returns 400 or 404
# ---------------------------------------------------------------------------


class TestInvalidPath:
    """Traversal attempts and invalid paths are rejected."""

    def test_dotdot_traversal_rejected(self, auth_token: str, thread_1: str):
        # URL-encoded ".." — FastAPI's :path converter passes through but the service
        # validator should catch ".." segments (T-18-16 mitigation).
        with _http(auth_token) as client:
            resp = client.get(f"/threads/{thread_1}/files/foo/../etc/passwd")
        # Accept 400 (service validator caught it) or 404 (RLS / path normalization)
        assert resp.status_code in (400, 404), (
            f"Expected 400 or 404 for traversal path, got {resp.status_code}: {resp.text}"
        )


# ---------------------------------------------------------------------------
# Test 6: Cross-user RLS isolation — User B cannot read User A's thread
# ---------------------------------------------------------------------------


class TestRLSIsolation:
    """User B cannot see files in User A's thread."""

    def test_cross_thread_list_isolation(
        self, auth_token_2: str, thread_1: str, auth_token: str
    ):
        # First ensure User A has at least one file so the list is non-empty for A
        ws = WorkspaceService(token=auth_token)
        _run(ws.write_text_file(thread_1, "secret.md", "top secret"))

        # User B queries User A's thread
        with _http(auth_token_2) as client:
            resp = client.get(f"/threads/{thread_1}/files")

        # RLS returns empty list (200) — User B sees nothing, no error leaked
        # OR backend returns 404 if RLS causes the thread itself to appear missing
        if resp.status_code == 200:
            files = resp.json()
            paths = [f["file_path"] for f in files]
            assert "secret.md" not in paths, (
                f"SECURITY: User B can see User A's file! paths={paths}"
            )
        else:
            assert resp.status_code in (403, 404), (
                f"Expected 200-empty, 403, or 404 for cross-user access, got {resp.status_code}"
            )

    def test_cross_thread_read_isolation(
        self, auth_token_2: str, thread_1: str
    ):
        # User B tries to read a known file path from User A's thread
        with _http(auth_token_2) as client:
            resp = client.get(f"/threads/{thread_1}/files/secret.md")
        # Must not return 200 with content
        assert resp.status_code in (403, 404), (
            f"SECURITY: User B can read User A's file! status={resp.status_code}, body={resp.text[:200]}"
        )


# ---------------------------------------------------------------------------
# Test 7: WORKSPACE_ENABLED=False gate (process-isolated, skipped here)
# ---------------------------------------------------------------------------


class TestWorkspaceDisabledGate:
    """When WORKSPACE_ENABLED=False the routes should not be registered.

    This requires a process-isolated FastAPI test client that can reload the app
    with a different env var. Skipped here in favour of the unit-level import check
    (verified in Task 1 of plan 18-04 via python -c assertion).
    """

    def test_disabled_gate_smoke(self):
        pytest.skip(
            "Requires process-isolated reload (WORKSPACE_ENABLED=False). "
            "Covered by Task 1 import assertion: routes absent when flag=False."
        )
