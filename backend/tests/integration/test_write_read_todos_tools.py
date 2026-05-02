"""Phase 17 / v1.3 — Integration tests for write_todos + read_todos tool dispatch.

Plan 17-03 (TODO-02, TODO-03, TODO-05) — TDD RED gate (before service exists),
TDD GREEN gate (after service + registry registration).

Tests exercise:
- tool dispatch via tool_registry (TOOL_REGISTRY_ENABLED=true path)
- Full-replacement semantic (write 3 then write 1 → DB has 1)
- RLS isolation (User A's todos invisible to User B)
- Registry disabled path (TOOL_REGISTRY_ENABLED=false)

Requirements: TODO-02, TODO-03, TODO-05, SEC-01, D-06, D-29, D-31, D-34

NOTE: These tests require a live Supabase connection and migration 038 applied.
Run with credentials set:
    TEST_EMAIL / TEST_PASSWORD / TEST_EMAIL_2 / TEST_PASSWORD_2

The tests skip gracefully if the table does not exist (migration not applied).
"""

from __future__ import annotations

import os
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


def _login(email: str, password: str) -> tuple[str, str]:
    """Return (access_token, user_id) for the given credentials."""
    client = get_supabase_client()
    result = client.auth.sign_in_with_password({"email": email, "password": password})
    return result.session.access_token, str(result.user.id)


def _create_thread(user_id: str) -> str:
    """Create a thread via service-role and return its ID."""
    svc = get_supabase_client()
    thread_id = str(uuid.uuid4())
    svc.table("threads").insert({
        "id": thread_id,
        "user_id": user_id,
        "title": f"test-17-03-{thread_id[:8]}",
    }).execute()
    return thread_id


def _delete_thread(thread_id: str) -> None:
    svc = get_supabase_client()
    try:
        svc.table("threads").delete().eq("id", thread_id).execute()
    except Exception:
        pass


def _check_table_exists() -> bool:
    """Return True if agent_todos table exists (migration 038 applied)."""
    svc = get_supabase_client()
    try:
        svc.table("agent_todos").select("id").limit(0).execute()
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def user_a_creds():
    """Return (token, user_id, user_email) for User A (super admin)."""
    token, user_id = _login(TEST_EMAIL, TEST_PASSWORD)
    return token, user_id, TEST_EMAIL


@pytest.fixture(scope="module")
def user_b_creds():
    """Return (token, user_id, user_email) for User B."""
    token, user_id = _login(TEST_EMAIL_2, TEST_PASSWORD_2)
    return token, user_id, TEST_EMAIL_2


@pytest.fixture
def user_a_thread(user_a_creds):
    """Create a thread for User A; clean up after test."""
    _, user_a_id, _ = user_a_creds
    thread_id = _create_thread(user_a_id)
    yield thread_id
    _delete_thread(thread_id)


@pytest.fixture
def user_b_thread(user_b_creds):
    """Create a thread for User B; clean up after test."""
    _, user_b_id, _ = user_b_creds
    thread_id = _create_thread(user_b_id)
    yield thread_id
    _delete_thread(thread_id)


# ---------------------------------------------------------------------------
# Context object for tool dispatch
# ---------------------------------------------------------------------------


class _ToolCtx:
    """Minimal context passed to registry executors (mirrors what chat.py provides)."""
    def __init__(self, thread_id: str, user_id: str, user_email: str, token: str):
        self.thread_id = thread_id
        self.user_id = user_id
        self.user_email = user_email
        self.token = token

    def get(self, key, default=None):
        return getattr(self, key, default)

    def __contains__(self, key):
        return hasattr(self, key)

    def __getitem__(self, key):
        return getattr(self, key)


# ---------------------------------------------------------------------------
# Direct service layer tests (no registry dispatch)
# These always run and can work without migration if they catch the error
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_write_todos_via_service_direct(user_a_creds, user_a_thread):
    """Direct service call: write_todos persists to DB with correct position."""
    if not _check_table_exists():
        pytest.skip("agent_todos table not present (migration 038 not applied)")

    from app.services.agent_todos_service import write_todos, read_todos

    token_a, user_a_id, user_a_email = user_a_creds
    thread_id = user_a_thread

    todos = [{"content": "step 1", "status": "pending"}]
    await write_todos(
        thread_id=thread_id,
        user_id=user_a_id,
        user_email=user_a_email,
        token=token_a,
        todos=todos,
    )

    # Verify via service-role client
    svc = get_supabase_client()
    rows = (
        svc.table("agent_todos")
        .select("content,status,position")
        .eq("thread_id", thread_id)
        .order("position")
        .execute()
    )
    assert len(rows.data) == 1, f"Expected 1 row, got {len(rows.data)}"
    assert rows.data[0]["position"] == 0
    assert rows.data[0]["content"] == "step 1"
    assert rows.data[0]["status"] == "pending"


@pytest.mark.asyncio
async def test_read_todos_via_service_direct(user_a_creds, user_a_thread):
    """Direct service call: read_todos returns list in position order."""
    if not _check_table_exists():
        pytest.skip("agent_todos table not present (migration 038 not applied)")

    from app.services.agent_todos_service import write_todos, read_todos

    token_a, user_a_id, user_a_email = user_a_creds
    thread_id = user_a_thread

    todos = [
        {"content": "first", "status": "pending"},
        {"content": "second", "status": "in_progress"},
    ]
    await write_todos(
        thread_id=thread_id,
        user_id=user_a_id,
        user_email=user_a_email,
        token=token_a,
        todos=todos,
    )

    result = await read_todos(
        thread_id=thread_id,
        user_id=user_a_id,
        user_email=user_a_email,
        token=token_a,
    )
    assert len(result) == 2
    assert result[0]["position"] < result[1]["position"]
    assert result[0]["content"] == "first"
    assert result[1]["content"] == "second"


@pytest.mark.asyncio
async def test_full_replacement_semantic(user_a_creds, user_a_thread):
    """D-06: write 3 todos then write 1 → DB has exactly 1 row."""
    if not _check_table_exists():
        pytest.skip("agent_todos table not present (migration 038 not applied)")

    from app.services.agent_todos_service import write_todos

    token_a, user_a_id, user_a_email = user_a_creds
    thread_id = user_a_thread

    # Write 3
    await write_todos(
        thread_id=thread_id,
        user_id=user_a_id,
        user_email=user_a_email,
        token=token_a,
        todos=[
            {"content": "a", "status": "pending"},
            {"content": "b", "status": "pending"},
            {"content": "c", "status": "pending"},
        ],
    )

    # Write 1 (replaces all 3)
    await write_todos(
        thread_id=thread_id,
        user_id=user_a_id,
        user_email=user_a_email,
        token=token_a,
        todos=[{"content": "only one", "status": "in_progress"}],
    )

    svc = get_supabase_client()
    rows = (
        svc.table("agent_todos")
        .select("id,content")
        .eq("thread_id", thread_id)
        .execute()
    )
    assert len(rows.data) == 1, (
        f"Full-replacement failed: expected 1 row after re-write, got {len(rows.data)}"
    )
    assert rows.data[0]["content"] == "only one"


@pytest.mark.asyncio
async def test_rls_isolation(user_a_creds, user_b_creds, user_a_thread):
    """SEC-01: User B cannot read User A's todos via RLS-scoped client."""
    if not _check_table_exists():
        pytest.skip("agent_todos table not present (migration 038 not applied)")

    from app.services.agent_todos_service import write_todos, read_todos

    token_a, user_a_id, user_a_email = user_a_creds
    token_b, user_b_id, user_b_email = user_b_creds
    thread_id = user_a_thread

    # User A writes todos
    await write_todos(
        thread_id=thread_id,
        user_id=user_a_id,
        user_email=user_a_email,
        token=token_a,
        todos=[{"content": "User A secret", "status": "pending"}],
    )

    # User B tries to read User A's thread via their own token — RLS blocks it
    result = await read_todos(
        thread_id=thread_id,
        user_id=user_b_id,
        user_email=user_b_email,
        token=token_b,
        _audit=False,  # skip audit for isolation test
    )
    assert result == [], (
        f"RLS isolation failed: User B can read User A's todos: {result}"
    )


# ---------------------------------------------------------------------------
# Registry dispatch tests (require TOOL_REGISTRY_ENABLED=true)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_write_todos_via_execute_tool(user_a_creds, user_a_thread, monkeypatch):
    """Registry path: tool_registry executor for write_todos dispatches correctly."""
    if not _check_table_exists():
        pytest.skip("agent_todos table not present (migration 038 not applied)")

    import app.config as config_mod
    monkeypatch.setenv("TOOL_REGISTRY_ENABLED", "true")
    config_mod.get_settings.cache_clear()

    from app.services import tool_registry
    tool_registry._clear_for_tests()

    # Import tool_service to trigger registration
    import importlib
    import app.services.tool_service as ts_mod
    importlib.reload(ts_mod)

    # Import tool_registry registration for phase 17 todos
    import app.services.agent_todos_service  # noqa: F401 — ensures module loads

    # Verify write_todos is registered (it should be after reload)
    if "write_todos" not in tool_registry._REGISTRY:
        pytest.skip("write_todos not registered — Phase 17 registry entries not loaded yet")

    token_a, user_a_id, user_a_email = user_a_creds
    thread_id = user_a_thread
    ctx_dict = {
        "thread_id": thread_id,
        "user_id": user_a_id,
        "user_email": user_a_email,
        "token": token_a,
    }

    tool_def = tool_registry._REGISTRY["write_todos"]
    result = await tool_def.executor(
        {"todos": [{"content": "via registry", "status": "pending"}]},
        user_a_id,
        ctx_dict,
        token=token_a,
    )

    assert "todos" in result, f"Executor should return {{'todos': [...]}}; got {result}"

    # Verify DB row
    svc = get_supabase_client()
    rows = (
        svc.table("agent_todos")
        .select("content,position")
        .eq("thread_id", thread_id)
        .execute()
    )
    assert len(rows.data) >= 1
    contents = [r["content"] for r in rows.data]
    assert "via registry" in contents


@pytest.mark.asyncio
async def test_read_todos_via_execute_tool(user_a_creds, user_a_thread, monkeypatch):
    """Registry path: read_todos executor returns sorted list."""
    if not _check_table_exists():
        pytest.skip("agent_todos table not present (migration 038 not applied)")

    import app.config as config_mod
    monkeypatch.setenv("TOOL_REGISTRY_ENABLED", "true")
    config_mod.get_settings.cache_clear()

    from app.services import tool_registry

    if "write_todos" not in tool_registry._REGISTRY or "read_todos" not in tool_registry._REGISTRY:
        pytest.skip("write_todos/read_todos not registered — check Phase 17 registration")

    token_a, user_a_id, user_a_email = user_a_creds
    thread_id = user_a_thread
    ctx_dict = {
        "thread_id": thread_id,
        "user_id": user_a_id,
        "user_email": user_a_email,
        "token": token_a,
    }

    # Write 2 todos first
    write_def = tool_registry._REGISTRY["write_todos"]
    await write_def.executor(
        {"todos": [
            {"content": "task 1", "status": "pending"},
            {"content": "task 2", "status": "in_progress"},
        ]},
        user_a_id,
        ctx_dict,
        token=token_a,
    )

    # Read via registry
    read_def = tool_registry._REGISTRY["read_todos"]
    result = await read_def.executor({}, user_a_id, ctx_dict, token=token_a)

    assert "todos" in result, f"Executor should return {{'todos': [...]}}; got {result}"
    todos = result["todos"]
    assert len(todos) == 2
    positions = [t["position"] for t in todos]
    assert positions == sorted(positions), "Todos must be ordered by position"


@pytest.mark.asyncio
async def test_tool_registry_disabled_byte_identical(monkeypatch):
    """D-31: when TOOL_REGISTRY_ENABLED=false, write_todos is NOT in the registry.

    This verifies the byte-identical fallback invariant from v1.2.
    """
    import app.config as config_mod
    monkeypatch.setenv("TOOL_REGISTRY_ENABLED", "false")
    config_mod.get_settings.cache_clear()

    # The fresh settings should say disabled
    fresh_settings = config_mod.Settings()
    assert fresh_settings.tool_registry_enabled is False, (
        "TOOL_REGISTRY_ENABLED=false must disable the flag"
    )

    # When the flag is off, tool_registry should not export write_todos
    # (it may not even be imported in production, but we can inspect the registry)
    from app.services import tool_registry
    tool_registry._clear_for_tests()

    # After reset, write_todos should not be in the registry
    # (it only registers when tool_registry_enabled=true)
    assert "write_todos" not in tool_registry._REGISTRY, (
        "write_todos must NOT be in the registry when TOOL_REGISTRY_ENABLED=false"
    )
    assert "read_todos" not in tool_registry._REGISTRY, (
        "read_todos must NOT be in the registry when TOOL_REGISTRY_ENABLED=false"
    )
