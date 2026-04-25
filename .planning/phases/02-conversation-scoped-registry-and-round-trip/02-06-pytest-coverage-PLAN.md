---
phase: 02-conversation-scoped-registry-and-round-trip
plan: 06
type: execute
wave: 5
depends_on: [03, 04, 05]
files_modified:
  - backend/tests/conftest.py
  - backend/tests/api/test_redaction_registry.py
  - backend/tests/unit/__init__.py
  - backend/tests/unit/test_conversation_registry.py
autonomous: true
requirements: [REG-01, REG-02, REG-03, REG-04, REG-05, DEANON-01, DEANON-02, PERF-03]
must_haves:
  truths:
    - "All 5 Phase 2 ROADMAP success criteria have at least one test class each"
    - "SC#5 (concurrent race) hits the REAL Supabase DB — not a mock"
    - "Cross-turn surname collision test (PRD §7.5 / D-37) passes"
    - "Hard-redact survival test (D-35 / SC#4) passes"
    - "Phase 1's 20 existing tests still pass alongside the new Phase 2 tests"
    - "No real PII appears in caplog output during any Phase 2 test (B4 / D-18 invariant)"
  artifacts:
    - path: "backend/tests/conftest.py"
      provides: "fresh_thread_id + empty_registry + reset_thread_locks fixtures"
    - path: "backend/tests/api/test_redaction_registry.py"
      provides: "Integration test classes TestSC1..TestSC5 covering all 5 SCs against real DB"
      contains: "asyncio.gather"
      min_lines: 200
    - path: "backend/tests/unit/__init__.py"
      provides: "Tests subpackage marker"
    - path: "backend/tests/unit/test_conversation_registry.py"
      provides: "Pure-unit (no DB) tests for registry primitives"
      min_lines: 30
  key_links:
    - from: "backend/tests/api/test_redaction_registry.py"
      to: "live entity_registry table"
      via: "service-role insert via redact_text + verification SELECT"
      pattern: "client\\.table\\(['\"]entity_registry['\"]\\)"
    - from: "backend/tests/api/test_redaction_registry.py"
      to: "asyncio.gather race"
      via: "TestSC5_RegistryRace.test_concurrent_introduction_of_same_entity"
      pattern: "asyncio\\.gather"
---

<objective>
Cover all 5 Phase 2 ROADMAP Success Criteria with pytest. Each SC gets at least one test class; SC#5 (the race condition) MUST hit the real DB to exercise the unique constraint at the actual serialisation point. Add a unit-only test file for `ConversationRegistry` primitives that don't need a DB.

Purpose: Closes the Phase 2 verification loop. The race-condition test in particular is non-negotiable per CONTEXT.md "specifics" — it is the only test that proves PERF-03 + the cross-process safety net (D-23 unique constraint) are correctly composed.

Output: Four new/modified test files. Roughly 200 lines for the integration suite, 30 lines for unit, plus 3 new fixtures in conftest.py. All Phase 2 tests pass; Phase 1's 20 tests still pass.

**Wave-5 dependency note (B-1 cascade):** Plan 05 moves to Wave 4 because it requires Plan 04's DB methods (`load`, `upsert_delta`). Plan 06's tests exercise the full Phase-2 surface (load + redact_text(registry=) + upsert_delta + de_anonymize_text), so it must run AFTER Plan 03 (live DB), Plan 04 (DB methods), AND Plan 05 (service wiring). New wave: 5.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/02-conversation-scoped-registry-and-round-trip/02-CONTEXT.md
@.planning/phases/02-conversation-scoped-registry-and-round-trip/02-PATTERNS.md
@CLAUDE.md
@backend/tests/conftest.py
@backend/tests/api/test_redaction.py
@backend/app/services/redaction_service.py
@backend/app/services/redaction/registry.py
@backend/app/database.py

<interfaces>
<!-- Existing primitives this plan calls. Read once; no codebase exploration needed. -->

From backend/tests/conftest.py L15-41 (Phase 1 fixtures — DO NOT MODIFY; only ADD new ones):
```python
@pytest.fixture
def seeded_faker():
    """Per-test deterministic seed for the redaction Faker (D-20)."""
    from app.services.redaction.anonymization import get_faker
    faker = get_faker()
    faker.seed_instance(42)
    yield faker

@pytest.fixture(scope="session")
def redaction_service():
    """Session-scoped RedactionService."""
    from app.services.redaction_service import get_redaction_service
    return get_redaction_service()
```

From backend/tests/api/test_redaction.py L1-18 (file header convention):
```python
"""Phase 1 redaction service tests.

Each TestSC<N>_... class corresponds to one Phase 1 ROADMAP Success Criterion.
Test docstrings quote the SC verbatim. Failures isolate to the SC they cover.
"""
from __future__ import annotations
import pytest
pytestmark = pytest.mark.asyncio
```

From CLAUDE.md "Testing" section — test credentials:
- TEST_EMAIL=test@test.com / TEST_PASSWORD=!*-3-3?3uZ?b$v&
- These are super_admin; service-role client doesn't need them but if a fixture must create a thread row owned by a real user, use this account's id.

From backend/app/database.py L1-8: `get_supabase_client()` returns the service-role client used by the test fixtures and assertions.

From supabase/migrations/001_initial_schema.sql L7-15 + audit of migrations 002-028 (W-3 verification, dated 2026-04-26):
```sql
create table public.threads (
  id uuid primary key default gen_random_uuid(),     -- HAS DEFAULT
  user_id uuid not null references auth.users(id) on delete cascade,  -- NOT NULL, NO DEFAULT (FK to test user)
  title text not null default 'New Thread',          -- HAS DEFAULT
  openai_thread_id text,                              -- nullable
  last_response_id text,                              -- nullable
  created_at timestamptz not null default now(),     -- HAS DEFAULT
  updated_at timestamptz not null default now()      -- HAS DEFAULT
);
```
**Threads table NOT NULL columns without defaults: only `user_id` (verified across migrations 001-028 on 2026-04-26 — `grep -i "ALTER TABLE.*threads.*ADD COLUMN" supabase/migrations/*.sql` returns NONE).** The fresh-thread fixture supplies `id` (explicit UUID for downstream assertions), `user_id` (via `test_user_id` fixture), and `title` (explicit override of default). The defensive try/except below surfaces any future column additions early.

ROADMAP Phase 2 Success Criteria (verbatim from ROADMAP.md L42-47):
- SC#1: Within a single thread, mentioning the same real person, email, or phone number twice (in different casings) yields the same surrogate both times; the registry exposes case-insensitive lookups.
- SC#2: Closing a thread, restarting the backend, and resuming the thread produces identical surrogates for previously-seen entities.
- SC#3: Surrogates emitted by the LLM in any letter-case round-trip back to the original real values before user-facing display.
- SC#4: Hard-redacted placeholders ([CREDIT_CARD], [US_SSN], …) never appear as keys in the registry — they are intentionally one-way.
- SC#5: Two simultaneous chat requests on the same thread that introduce the same new entity produce a single registry row (no duplicate surrogates, no race).
</interfaces>
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: Add Phase 2 fixtures to conftest.py — fresh_thread_id, empty_registry, reset_thread_locks</name>
  <files>backend/tests/conftest.py</files>
  <read_first>
    - backend/tests/conftest.py (current — preserve Phase 1 fixtures verbatim; only ADD new fixtures at the bottom)
    - .planning/phases/02-conversation-scoped-registry-and-round-trip/02-PATTERNS.md §"Pattern B — `seeded_faker` + `redaction_service` fixtures" (the explicit "What to ADD for Phase 2" section)
    - .planning/phases/02-conversation-scoped-registry-and-round-trip/02-CONTEXT.md decisions D-43, D-44
    - CLAUDE.md "Testing" section (test credentials)
    - supabase/migrations/001_initial_schema.sql L7-15 (W-3: threads NOT NULL audit)
  </read_first>
  <action>
EDIT `backend/tests/conftest.py`. Add THREE new fixtures at the bottom of the file (do not modify existing Phase 1 fixtures).

(A) New imports at the top of the imports block:
```python
import uuid as _uuid
import pytest_asyncio
```

If `pytest_asyncio` is already imported (Phase 1 uses `pytest.mark.asyncio` but may not import the package directly), confirm it is in `requirements.txt` — `grep "pytest-asyncio" backend/requirements.txt`. If absent, surface immediately to the orchestrator before continuing — DO NOT silently add a dependency.

(B) Helper to obtain a real user_id for thread ownership. Add as a session-scoped fixture (the test user is created at test time only if missing — Phase 1 conftest doesn't already supply one):

```python
@pytest.fixture(scope="session")
def test_user_id():
    """Returns a stable user_id owned by the TEST_EMAIL super_admin.

    Service-role client looks up the user; we don't need to authenticate.
    The threads table FK requires a real auth.users row, so we resolve
    test@test.com once per test session.
    """
    import os
    from app.database import get_supabase_client
    client = get_supabase_client()
    # auth.admin.list_users is paged — TEST_EMAIL is the super_admin so it's in page 1.
    # Conservative: query the user_profiles table which Phase 1 conftest knows exists.
    test_email = os.environ.get("TEST_EMAIL", "test@test.com")
    res = client.table("user_profiles").select("id").eq("email", test_email).single().execute()
    if not res.data:
        pytest.fail(f"Test user {test_email!r} not found in user_profiles — set up via /set_admin_role")
    return res.data["id"]
```

(C) Per-test fresh thread fixture (D-44).

**W-3 — `threads` NOT NULL audit:** As of migration 028 (2026-04-26), the threads table has the columns shown in the `<interfaces>` block above. NOT NULL columns without defaults: ONLY `user_id` (verified across migrations 001-028 — `grep -i "ALTER TABLE.*threads.*ADD COLUMN" supabase/migrations/*.sql` returns NONE). The fixture supplies `id` (explicit so cleanup can target it), `user_id` (from `test_user_id`), and `title` (explicit override). All other columns rely on defaults. The defensive `try/except` surfaces the exact column name if a future migration adds a NOT-NULL-without-default column.

```python
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
```

(D) Empty registry fixture (D-44):

```python
@pytest_asyncio.fixture
async def empty_registry(fresh_thread_id):
    """D-44: empty ConversationRegistry bound to a fresh thread."""
    from app.services.redaction.registry import ConversationRegistry
    return await ConversationRegistry.load(fresh_thread_id)
```

(E) Reset module-level lock state between tests (W-4 — must rebind both the dict AND the master lock to the per-test event loop):

```python
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
```

`autouse=True` runs this for EVERY test — Phase 1 tests too. The clear-clear pattern is harmless for Phase 1 (registry=None paths never touch `_thread_locks`).

After editing, run a quick sanity check:
```bash
cd backend && source venv/bin/activate && pytest tests/api/test_redaction.py -q --collect-only 2>&1 | tail -5
```
The Phase 1 tests should still be collected (the autouse fixture doesn't affect collection).
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && grep -q "def fresh_thread_id" tests/conftest.py && grep -q "def empty_registry" tests/conftest.py && grep -q "def _reset_thread_locks" tests/conftest.py && grep -q "def test_user_id" tests/conftest.py && grep -q "_thread_locks_master = asyncio.Lock()" tests/conftest.py && grep -q "violates not-null" tests/conftest.py && echo "OK"</automated>
  </verify>
  <acceptance_criteria>
    - `backend/tests/conftest.py` contains `def fresh_thread_id` (pytest_asyncio fixture).
    - `backend/tests/conftest.py` contains `def empty_registry`.
    - `backend/tests/conftest.py` contains `def _reset_thread_locks` with `autouse=True`.
    - `backend/tests/conftest.py` contains `def test_user_id` (session-scoped).
    - `backend/tests/conftest.py` contains literal `_rs._thread_locks_master = asyncio.Lock()` inside `_reset_thread_locks` (W-4 — master lock rebind).
    - `backend/tests/conftest.py` contains literal `violates not-null` substring inside `fresh_thread_id` (W-3 — defensive try/except diagnostic).
    - **W-4 acceptance criterion**: After autouse fixture runs, `_rs._thread_locks_master._loop` matches the current event loop (or is None if not yet bound). Practical test: a smoke pytest run with two tests that both use `empty_registry` must NOT raise `RuntimeError: Lock is bound to a different event loop` from the second test.
    - Phase 1 fixtures (`seeded_faker`, `redaction_service`) are unchanged: `git diff conftest.py` shows ZERO modifications to lines L1-50.
    - Phase 1 tests still collect: `pytest tests/api/test_redaction.py -q --collect-only` exits 0.
  </acceptance_criteria>
  <done>Conftest is Phase 2-ready. Plan 06 Tasks 2 and 3 can now use the fixtures without cross-test event-loop contamination (W-4) or stale-schema column surprises (W-3).</done>
</task>

<task type="auto" tdd="false">
  <name>Task 2: Create integration test suite covering all 5 Phase 2 SCs (real DB)</name>
  <files>backend/tests/api/test_redaction_registry.py</files>
  <read_first>
    - backend/tests/api/test_redaction.py L1-296 (Phase 1 test file — analog for class shape, fixture usage, log-privacy assertion)
    - backend/tests/conftest.py (Task 1 output — confirms fresh_thread_id / empty_registry / test_user_id fixtures exist)
    - backend/app/services/redaction_service.py (Plan 05 — confirms `redact_text(text, registry=)` signature and `de_anonymize_text` method are present)
    - backend/app/services/redaction/registry.py (Plan 02 + 04 — confirms `ConversationRegistry.load`, `lookup`, `entries` API)
    - .planning/phases/02-conversation-scoped-registry-and-round-trip/02-PATTERNS.md §"backend/tests/api/test_redaction_registry.py (NEW)" — Patterns A-G with full sketches per SC class
    - .planning/phases/02-conversation-scoped-registry-and-round-trip/02-CONTEXT.md decisions D-42, D-43
  </read_first>
  <action>
Create `backend/tests/api/test_redaction_registry.py` with 6 test classes (5 SCs + 1 cross-turn collision case for PRD §7.5 / D-37). The file MUST exercise the real Supabase DB — NO mocks for the SC#5 race test. Total target ~200 lines.

File header (verbatim convention from Phase 1 test_redaction.py):
```python
"""Phase 2 conversation-scoped registry & round-trip tests.

Each TestSC<N>_... class corresponds to one Phase 2 ROADMAP Success Criterion.
Test docstrings quote the SC verbatim. The race-condition test (TestSC5_*) MUST
hit the real Supabase DB to exercise the unique-constraint serialisation path
(D-23 / D-43) — do NOT mock the supabase client there.

Coverage:
  - SC#1 → TestSC1_CaseInsensitiveConsistency  (REG-01, REG-03, REG-04)
  - SC#2 → TestSC2_ResumeAcrossRestart         (REG-02)
  - SC#3 → TestSC3_DeAnonRoundTripCaseSensitive (DEANON-01, DEANON-02)
  - SC#4 → TestSC4_HardRedactNotInRegistry      (REG-05, D-35)
  - SC#5 → TestSC5_RegistryRace                 (PERF-03, D-23, D-29, D-30)
  - PRD §7.5 / D-37 → TestSC5b_CrossTurnSurnameCollision

Forbidden in caplog (B4 / D-18 / D-41 invariant): real PII MUST NOT appear
in any log message produced by these tests. Each class with caplog usage
asserts the no-real-PII invariant.
"""

from __future__ import annotations

import asyncio

import pytest

pytestmark = pytest.mark.asyncio
```

Then the six classes. Use the exact patterns from PATTERNS.md §"backend/tests/api/test_redaction_registry.py (NEW)" — copy them in and adjust for the live fixtures from Task 1.

(A) `TestSC1_CaseInsensitiveConsistency` — within one turn, two redact_text calls on the same registry with different-cased mentions of the same real entity yield the same surrogate.

```python
class TestSC1_CaseInsensitiveConsistency:
    """SC#1: Within a single thread, mentioning the same real person, email,
    or phone number twice (in different casings) yields the same surrogate
    both times; the registry exposes case-insensitive lookups.
    Covers: REG-01, REG-03, REG-04.
    """

    async def test_same_real_value_different_case_same_surrogate(
        self, redaction_service, empty_registry, seeded_faker,
    ):
        text1 = "Pak Bambang Sutrisno tinggal di Jakarta."
        text2 = "BAMBANG SUTRISNO menelpon hari ini."  # all-caps mention
        r1 = await redaction_service.redact_text(text1, registry=empty_registry)
        r2 = await redaction_service.redact_text(text2, registry=empty_registry)

        # Find the surrogate produced for "Bambang Sutrisno" in each result.
        # Phase 1 entity_map keys preserve the matched substring; we look up
        # via registry.lookup() which is the canonical case-insensitive path.
        s1 = empty_registry.lookup("Bambang Sutrisno")
        s2 = empty_registry.lookup("BAMBANG SUTRISNO")
        assert s1 is not None, "registry must have entry for Bambang Sutrisno"
        assert s1 == s2, f"Case-insensitive lookup must return same surrogate; got {s1!r} vs {s2!r}"
```

(B) `TestSC2_ResumeAcrossRestart` — write registry, drop in-memory instance, re-load, surrogate is identical.

```python
class TestSC2_ResumeAcrossRestart:
    """SC#2: Closing a thread, restarting the backend, and resuming produces
    identical surrogates (registry persisted to DB and reloaded on resume).
    Covers: REG-02.
    """

    async def test_load_after_drop_returns_same_mappings(
        self, redaction_service, fresh_thread_id, seeded_faker,
    ):
        from app.services.redaction.registry import ConversationRegistry

        reg1 = await ConversationRegistry.load(fresh_thread_id)
        await redaction_service.redact_text("Pak Bambang tinggal di Jakarta.", registry=reg1)
        s1 = reg1.lookup("Bambang")
        del reg1  # simulate restart

        reg2 = await ConversationRegistry.load(fresh_thread_id)
        s2 = reg2.lookup("Bambang")
        assert s1 is not None and s2 is not None
        assert s1 == s2, f"Restart-reloaded surrogate diverged: {s1!r} vs {s2!r}"
```

(C) `TestSC3_DeAnonRoundTripCaseSensitive` — feed the surrogate back in different casing; de-anon resolves to the original real value.

```python
class TestSC3_DeAnonRoundTripCaseSensitive:
    """SC#3: Surrogates emitted by the LLM in any letter-case round-trip back
    to original real values before user-facing display.
    Covers: DEANON-01, DEANON-02.
    """

    async def test_uppercased_surrogate_resolves_to_original_real(
        self, redaction_service, empty_registry, seeded_faker,
    ):
        await redaction_service.redact_text(
            "Email Pak Bambang adalah bambang.s@example.com.",
            registry=empty_registry,
        )
        # Find the surrogate the registry assigned to the email.
        email_surrogate = empty_registry.lookup("bambang.s@example.com")
        assert email_surrogate is not None

        # Simulate LLM emitting the surrogate uppercased.
        llm_output = f"The email {email_surrogate.upper()} was used."
        roundtrip = await redaction_service.de_anonymize_text(llm_output, empty_registry)
        assert "bambang.s@example.com" in roundtrip, (
            f"De-anon failed to restore original casing email; got: {roundtrip!r}"
        )
```

(D) `TestSC4_HardRedactNotInRegistry` — credit-card-like input gets `[CREDIT_CARD]` in anonymized output AND there is zero registry row for CREDIT_CARD AND the placeholder survives a de-anon round-trip.

```python
class TestSC4_HardRedactNotInRegistry:
    """SC#4: Hard-redacted placeholders never appear as keys in the registry
    AND survive a de-anonymization round-trip unchanged.
    Covers: REG-05, D-24, D-35.
    """

    async def test_credit_card_not_persisted(
        self, redaction_service, empty_registry, seeded_faker,
    ):
        from app.database import get_supabase_client

        text = "Card 4111-1111-1111-1111 belongs to Pak Bambang."
        result = await redaction_service.redact_text(text, registry=empty_registry)
        assert "[CREDIT_CARD]" in result.anonymized_text

        client = get_supabase_client()
        rows = (
            client.table("entity_registry")
            .select("entity_type")
            .eq("thread_id", empty_registry.thread_id)
            .execute()
            .data
        )
        types = {r["entity_type"] for r in rows}
        assert "CREDIT_CARD" not in types, "Hard-redact leaked into registry"

    async def test_credit_card_placeholder_survives_de_anon(
        self, redaction_service, empty_registry, seeded_faker,
    ):
        from app.services.redaction.registry import ConversationRegistry
        text_in = "Card 4111-1111-1111-1111 belongs to Pak Bambang."
        result = await redaction_service.redact_text(text_in, registry=empty_registry)
        # Re-load fresh registry to simulate per-turn lifecycle.
        reg2 = await ConversationRegistry.load(empty_registry.thread_id)
        roundtrip = await redaction_service.de_anonymize_text(result.anonymized_text, reg2)
        assert "[CREDIT_CARD]" in roundtrip
```

(E) `TestSC5_RegistryRace` — asyncio.gather of two redact_text calls introducing the same entity → exactly ONE row, identical surrogates returned. MUST hit real DB.

```python
class TestSC5_RegistryRace:
    """SC#5: Two simultaneous chat requests on the same thread that introduce
    the same new entity produce a single registry row (no duplicate surrogates,
    no race). Verifies PERF-03 (per-thread asyncio.Lock) AND the unique-
    constraint serialisation safety net (D-23). MUST hit the real DB.
    Covers: PERF-03, D-23, D-29, D-30.
    """

    async def test_concurrent_introduction_of_same_entity(
        self, redaction_service, empty_registry, seeded_faker,
    ):
        from app.database import get_supabase_client

        text_a = "Pak Bambang Sutrisno tinggal di Jakarta."
        text_b = "Bambang Sutrisno menelpon hari ini."

        await asyncio.gather(
            redaction_service.redact_text(text_a, registry=empty_registry),
            redaction_service.redact_text(text_b, registry=empty_registry),
        )

        sa = empty_registry.lookup("Bambang Sutrisno")
        sb = empty_registry.lookup("bambang sutrisno")
        assert sa is not None
        assert sa == sb, f"Race produced divergent surrogates: {sa!r} vs {sb!r}"

        client = get_supabase_client()
        rows = (
            client.table("entity_registry")
            .select("id")
            .eq("thread_id", empty_registry.thread_id)
            .eq("real_value_lower", "bambang sutrisno")
            .execute()
            .data
        )
        assert len(rows) == 1, f"Expected exactly one registry row, got {len(rows)}"
```

(F) `TestSC5b_CrossTurnSurnameCollision` — D-37 / PRD §7.5 case. Turn 1 introduces "Maria Santos"; turn 3 introduces "Margaret Thompson". Maria's surrogate must not contain "Margaret"/"Thompson" and Margaret's surrogate must not contain "Maria"/"Santos".

```python
class TestSC5b_CrossTurnSurnameCollision:
    """D-37 / PRD §7.5: A surrogate generated in turn 1 must not have its
    surname token clash with a real PERSON introduced in turn 3. The cross-
    turn forbidden-token set (registry.forbidden_tokens()) prevents this.
    """

    async def test_turn3_real_does_not_collide_with_turn1_surrogate(
        self, redaction_service, empty_registry, seeded_faker,
    ):
        await redaction_service.redact_text(
            "Maria Santos works here.", registry=empty_registry,
        )
        s1 = empty_registry.lookup("Maria Santos")
        assert s1 is not None
        sur1_tokens = {t.casefold() for t in s1.split()}

        await redaction_service.redact_text(
            "Margaret Thompson called.", registry=empty_registry,
        )
        s2 = empty_registry.lookup("Margaret Thompson")
        assert s2 is not None
        sur2_tokens = {t.casefold() for t in s2.split()}

        # Phase 2 invariant: turn-3 surrogate avoids real tokens already in
        # registry (maria, santos) AND turn-3 reals (margaret, thompson).
        for forbidden in {"maria", "santos", "margaret", "thompson"}:
            assert forbidden not in sur2_tokens, (
                f"Cross-turn collision: surrogate {s2!r} contains forbidden token {forbidden!r}"
            )
```

Hard rules — verify after writing:

- File MUST start with the verbatim header docstring including the SC→class mapping.
- `pytestmark = pytest.mark.asyncio` at module level.
- 6 classes total (5 SCs + 1 cross-turn collision); class names use the EXACT pattern `TestSC<N>_<descriptor>` from Phase 1.
- TestSC5_RegistryRace MUST contain `asyncio.gather(` AND a `client.table("entity_registry")` SELECT — proves DB is hit.
- TestSC5_RegistryRace MUST assert `len(rows) == 1` — the unique-constraint enforcement check.
- All test methods accept `seeded_faker` as a fixture (per-test deterministic surrogate output) — this is critical for the cross-turn collision test which depends on Faker being seeded so the surrogate token set is stable.
- Use `empty_registry.lookup(...)` for assertions (canonical case-insensitive path) instead of poking `_by_lower` directly.

Run the suite after writing:
```bash
cd backend && source venv/bin/activate && pytest tests/api/test_redaction_registry.py -v --tb=short
```
Expected: 6 tests passed (or 7 if the executor split a class into multiple methods).
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pytest tests/api/test_redaction_registry.py -v --tb=short 2>&1 | tail -20</automated>
  </verify>
  <acceptance_criteria>
    - File `backend/tests/api/test_redaction_registry.py` exists.
    - File contains 6 test classes whose names match `TestSC[1-5]` or `TestSC5b_` patterns.
    - File contains `asyncio.gather` (race test present).
    - File contains literal `client.table("entity_registry")` (proves real DB usage in SC#4 and SC#5).
    - File contains `len(rows) == 1` assertion (unique-constraint check in SC#5).
    - All tests pass: pytest exits 0 with 6+ passed and 0 failed.
    - Phase 1 tests still pass: `pytest tests/api/test_redaction.py -q` exits 0 with 20 passed.
    - Combined: `pytest tests/api/test_redaction.py tests/api/test_redaction_registry.py -q` exits 0 with 26+ passed.
  </acceptance_criteria>
  <done>All 5 Phase 2 SCs verified against the live DB. The race test is the binding proof that PERF-03 and D-23 compose correctly.</done>
</task>

<task type="auto" tdd="false">
  <name>Task 3: Create unit test scaffold for ConversationRegistry primitives (no DB)</name>
  <files>backend/tests/unit/__init__.py, backend/tests/unit/test_conversation_registry.py</files>
  <read_first>
    - backend/app/services/redaction/registry.py (Plan 02 + 04 — confirms in-memory API: __init__, lookup, entries, forbidden_tokens, thread_id property)
    - .planning/phases/02-conversation-scoped-registry-and-round-trip/02-PATTERNS.md §"backend/tests/unit/test_conversation_registry.py (NEW, optional)"
    - .planning/phases/02-conversation-scoped-registry-and-round-trip/02-CONTEXT.md decisions D-36, D-37, D-38
  </read_first>
  <action>
The `backend/tests/unit/` directory does not exist yet. Two files to create:

(A) `backend/tests/unit/__init__.py` — empty file (just a marker so pytest discovers the package). Single line:
```python
```
(Actually empty; do not put a docstring.)

(B) `backend/tests/unit/test_conversation_registry.py` — pure-unit coverage that does NOT touch the DB. Constructs `ConversationRegistry` directly with `rows=[...]` and exercises in-memory primitives.

```python
"""Phase 2 ConversationRegistry pure-unit tests (no DB).

Exercises the in-memory primitives — lookup case-insensitivity, entries()
copy semantics, forbidden_tokens() per-PERSON filter (D-38). For DB-backed
behaviour (load, upsert_delta, race), see tests/api/test_redaction_registry.py.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


class TestConversationRegistryUnit:
    """Pure-unit coverage for ConversationRegistry — no DB access."""

    async def test_lookup_is_casefold_correct(self):
        from app.services.redaction.registry import ConversationRegistry, EntityMapping
        reg = ConversationRegistry(thread_id="t-1", rows=[
            EntityMapping(
                real_value="Bambang Sutrisno",
                real_value_lower="bambang sutrisno",
                surrogate_value="Andi Pratama",
                entity_type="PERSON",
            ),
        ])
        assert reg.lookup("bambang sutrisno") == "Andi Pratama"
        assert reg.lookup("BAMBANG SUTRISNO") == "Andi Pratama"
        assert reg.lookup("Bambang Sutrisno") == "Andi Pratama"
        assert reg.lookup("Margaret Thompson") is None

    async def test_entries_returns_a_copy(self):
        from app.services.redaction.registry import ConversationRegistry, EntityMapping
        m = EntityMapping(
            real_value="x", real_value_lower="x",
            surrogate_value="y", entity_type="PERSON",
        )
        reg = ConversationRegistry(thread_id="t-1", rows=[m])
        entries = reg.entries()
        entries.append(m)  # mutate caller's copy
        assert len(reg.entries()) == 1, "entries() must return a copy, not the internal list"

    async def test_forbidden_tokens_only_persons(self):
        """D-38: per-PERSON only. Email / phone / URL contributions excluded."""
        from app.services.redaction.registry import ConversationRegistry, EntityMapping
        rows = [
            EntityMapping(
                real_value="Bambang Sutrisno",
                real_value_lower="bambang sutrisno",
                surrogate_value="Andi Pratama",
                entity_type="PERSON",
            ),
            EntityMapping(
                real_value="bambang.s@example.com",
                real_value_lower="bambang.s@example.com",
                surrogate_value="someone@elsewhere.com",
                entity_type="EMAIL_ADDRESS",
            ),
        ]
        reg = ConversationRegistry(thread_id="t-1", rows=rows)
        tokens = reg.forbidden_tokens()
        assert "bambang" in tokens
        assert "sutrisno" in tokens
        # Email parts MUST NOT contribute (D-38).
        assert "example.com" not in tokens
        assert "bambang.s@example.com" not in tokens

    async def test_thread_id_property_immutable(self):
        from app.services.redaction.registry import ConversationRegistry
        reg = ConversationRegistry(thread_id="t-abc", rows=[])
        assert reg.thread_id == "t-abc"
        # property is read-only — assignment must raise
        with pytest.raises(AttributeError):
            reg.thread_id = "t-xyz"  # type: ignore
```

After writing both files, run them:
```bash
cd backend && source venv/bin/activate && pytest tests/unit/test_conversation_registry.py -v --tb=short
```
Expected: 4 tests passed.

Confirm pytest discovers the new dir without breaking Phase 1 / Phase 2 integration test discovery:
```bash
cd backend && source venv/bin/activate && pytest tests/ -q --collect-only 2>&1 | tail -10
```
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pytest tests/unit/test_conversation_registry.py -v --tb=short 2>&1 | tail -10</automated>
  </verify>
  <acceptance_criteria>
    - File `backend/tests/unit/__init__.py` exists (empty).
    - File `backend/tests/unit/test_conversation_registry.py` exists.
    - File contains 4 test methods named per the patterns above.
    - File contains `pytestmark = pytest.mark.asyncio` at module level.
    - File does NOT import `app.database` or `get_supabase_client` (pure-unit invariant — no DB).
    - All 4 tests pass: pytest exits 0 with 4 passed.
    - Combined regression: `pytest tests/ -q` exits 0 with 30+ tests passed (20 Phase 1 + 6 Phase 2 integration + 4 unit = 30; could be higher if executor adds extra cases).
  </acceptance_criteria>
  <done>Phase 2 unit-level coverage in place. The full pytest invocation `pytest tests/ -q` runs all of Phase 1, Phase 2 integration, and Phase 2 unit suites green.</done>
</task>

</tasks>

<verification>
- All Phase 2 ROADMAP SCs (1-5) have at least one test class — quick check:
  ```bash
  grep -c "class TestSC" backend/tests/api/test_redaction_registry.py
  ```
  Returns >= 5.
- Race test exercises real DB:
  ```bash
  grep "client.table" backend/tests/api/test_redaction_registry.py
  ```
  Returns at least 2 occurrences (SC#4 and SC#5).
- W-4 master-lock rebind in place:
  ```bash
  grep "_thread_locks_master = asyncio.Lock()" backend/tests/conftest.py
  ```
  Returns >= 1.
- W-3 defensive try/except in fresh_thread_id:
  ```bash
  grep "violates not-null" backend/tests/conftest.py
  ```
  Returns >= 1.
- Combined regression PASSES:
  ```bash
  cd backend && source venv/bin/activate && \
    TEST_EMAIL="test@test.com" TEST_PASSWORD='!*-3-3?3uZ?b$v&' \
    pytest tests/ -q --tb=short
  ```
  Exits 0 with all tests passed.
- No real PII in caplog from any Phase 2 test (B4 / D-18 invariant): if executor adds caplog assertions, run with `--log-level=DEBUG` and grep the captured output for known real strings ("Bambang", "bambang.s@example.com", "Maria Santos", etc.) — none should appear.
- Phase 1 still 20/20: `pytest tests/api/test_redaction.py -q` exits 0 with 20 passed.
</verification>

<success_criteria>
- All 5 Phase 2 ROADMAP SCs verified by tests against the live Supabase DB.
- D-37 (cross-turn surname collision avoidance per PRD §7.5) verified.
- D-23 unique-constraint serialisation explicitly tested in SC#5.
- D-35 (hard-redact survives de-anon) verified.
- B4 / D-18 / D-41 (no real PII in logs) preserved.
- Phase 1's 20 tests still pass.
- W-3: fresh_thread_id fixture is stale-schema-aware (defensive try/except surfaces NOT-NULL-without-default column additions).
- W-4: _thread_locks_master rebind in autouse fixture eliminates cross-test "Lock is bound to a different event loop" failures.
</success_criteria>

<output>
Create `.planning/phases/02-conversation-scoped-registry-and-round-trip/02-06-SUMMARY.md` with:
- Test counts: integration (6+ tests / 6 classes), unit (4 tests / 1 class), Phase 1 regression (20 tests).
- Combined pytest output (last 10 lines of the full run).
- Confirm SC#5 hit the live DB (cite the SELECT row count assertion).
- Confirm Phase 1 regression: 20/20 pass.
- Confirm W-3 + W-4 fixtures present (master lock rebind, defensive try/except).
- Note any executor decisions (e.g. extra edge-case tests added).
</output>
</content>
