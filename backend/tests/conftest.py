"""Shared pytest fixtures for the LexCore backend test suite.

Phase 1 (milestone v1.0) adds:
- `seeded_faker`: per-test Faker seed for reproducible surrogate generation
  (D-20: production never sets a seed).
- `redaction_service`: session-scoped to verify @lru_cache singleton behaviour
  (PERF-01 / SC#5).

Phase 2 (milestone v1.0) adds:
- `test_user_id`: session-scoped — resolves the TEST_EMAIL super_admin's
  auth.users.id via `client.auth.admin.list_users()` (B-4 — canonical
  project pattern from `backend/scripts/set_admin_role.py` L26).
- `fresh_thread_id`: per-test fresh `threads` row (D-44) — yields a UUID;
  cleanup deletes the threads row, which cascades to entity_registry rows
  via the `ON DELETE CASCADE` FK on `entity_registry.thread_id` (D-22).
- `empty_registry`: per-test empty ConversationRegistry bound to a fresh
  thread (D-44).
- `_reset_thread_locks`: autouse fixture that clears
  `redaction_service._thread_locks` AND rebinds `_thread_locks_master` to
  the current event loop (W-4 — eliminates "Lock is bound to a different
  event loop" cross-test contamination).
"""

from __future__ import annotations

import uuid as _uuid

import pytest
import pytest_asyncio


@pytest.fixture
def seeded_faker():
    """Per-test deterministic seed for the redaction Faker (D-20).

    Returns the seeded Faker instance. Tests that compare exact surrogate
    values request this fixture; tests that only check structural properties
    (gender, presence/absence of tokens) can skip it.
    """
    from app.services.redaction.anonymization import get_faker

    faker = get_faker()
    faker.seed_instance(42)  # arbitrary fixed seed
    yield faker
    # No teardown - the next test that requests seeded_faker re-seeds.


@pytest.fixture(scope="session")
def redaction_service():
    """Session-scoped RedactionService.

    The fixture is session-scoped because get_redaction_service() is itself
    @lru_cache'd; using the same instance across all tests verifies the
    singleton stays intact (PERF-01 / SC#5).
    """
    from app.services.redaction_service import get_redaction_service

    return get_redaction_service()


# ---------- Phase 2 fixtures ----------------------------------------------


@pytest.fixture(scope="session")
def test_user_id():
    """Returns a stable user_id owned by the TEST_EMAIL super_admin.

    Uses client.auth.admin.list_users() — the canonical project pattern
    from backend/scripts/set_admin_role.py L26 — because the user_profiles
    table has NO email column (verified against migration 016 schema).

    auth.users is the source of truth for emails; user_profiles.user_id
    references auth.users.id, which equals threads.user_id (the FK target).
    """
    import os

    from app.database import get_supabase_client

    client = get_supabase_client()
    test_email = os.environ.get("TEST_EMAIL", "test@test.com")
    # Service-role can call auth.admin endpoints. list_users() returns up to
    # 50 users by default — TEST_EMAIL super_admin will be in page 1.
    users = client.auth.admin.list_users()
    test_user = next((u for u in users if u.email == test_email), None)
    if test_user is None:
        pytest.fail(
            f"Test user {test_email!r} not found in auth.users. "
            f'Set up the user account first (see CLAUDE.md "Testing" section).'
        )
    return test_user.id  # auth.users.id matches the threads.user_id FK target


@pytest_asyncio.fixture
async def fresh_thread_id(test_user_id):
    """D-44: a fresh thread_id per test — avoids cross-test registry pollution.

    ON DELETE CASCADE on entity_registry.thread_id ensures cleanup is
    automatic when the thread row is deleted in the teardown.

    Threads table NOT NULL columns without defaults: ONLY `user_id`
    (verified across migrations 001-028 on 2026-04-26 via
    `grep -i "ALTER TABLE.*threads.*ADD COLUMN" supabase/migrations/*.sql`
    → NONE). If a future migration adds a NOT-NULL-without-default column,
    the defensive `except` block below surfaces the column name fast.
    """
    from app.database import get_supabase_client

    client = get_supabase_client()
    tid = str(_uuid.uuid4())
    payload = {
        "id": tid,
        "user_id": test_user_id,
        "title": "phase2-test",
    }
    try:
        client.table("threads").insert(payload).execute()
    except Exception as e:
        msg = str(e)
        if "null value in column" in msg.lower() and "violates not-null" in msg.lower():
            # Surface the offending column so the developer can update both
            # this fixture and the W-3 audit comment in one diff.
            pytest.fail(
                f"fresh_thread_id fixture is stale: a NOT-NULL-without-default "
                f"column has been added to public.threads since the 2026-04-26 "
                f"audit. Original supabase error: {msg}"
            )
        raise
    yield tid
    # Cascade-deletes any entity_registry rows for this thread (D-22 ON DELETE CASCADE).
    client.table("threads").delete().eq("id", tid).execute()


@pytest_asyncio.fixture
async def empty_registry(fresh_thread_id):
    """D-44: empty ConversationRegistry bound to a fresh thread."""
    from app.services.redaction.registry import ConversationRegistry

    return await ConversationRegistry.load(fresh_thread_id)


@pytest.fixture(autouse=True)
def _reset_thread_locks():
    """Clear redaction_service._thread_locks AND rebind _thread_locks_master.

    Each pytest-asyncio test creates a fresh event loop. asyncio.Lock instances
    are bound to the loop they were created on; a Lock instantiated under a
    previous test's (now-dead) loop raises 'Lock is bound to a different event
    loop' on the next test's first acquire.

    W-4 fix: the previous version of this fixture cleared `_thread_locks` (the
    per-thread dict) but NOT `_thread_locks_master`. The master lock is
    instantiated at module load time (under whatever loop ran first) and is
    used in EVERY redact_text(registry=...) call to make get-or-create atomic
    — so a stale master lock from test N would crash test N+1's first acquire.

    Rebinding `_thread_locks_master` to a fresh `asyncio.Lock()` inside this
    fixture ensures the master lock is bound to the CURRENT test's event loop.
    """
    import asyncio

    from app.services import redaction_service as _rs

    _rs._thread_locks.clear()
    _rs._thread_locks_master = asyncio.Lock()  # Re-bind to current test's event loop
    yield
    _rs._thread_locks.clear()
    # Note: we do NOT rebind _thread_locks_master on teardown — the next test's
    # autouse setup will rebind to its loop. Rebinding on teardown would bind
    # to the loop that's about to be torn down, which is pointless.
