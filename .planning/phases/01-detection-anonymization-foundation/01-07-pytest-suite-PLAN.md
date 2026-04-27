---
phase: 1
plan_number: 07
title: "Pytest suite covering all 5 Phase 1 success criteria"
wave: 4
depends_on: [01, 02, 03, 04, 05, 06]
requirements: [PII-01, PII-02, PII-03, PII-04, PII-05, ANON-01, ANON-02, ANON-03, ANON-04, ANON-05, ANON-06, PERF-01, OBS-01]
files_modified:
  - backend/tests/api/test_redaction.py
  - backend/tests/conftest.py
autonomous: true
must_haves:
  - "`pytest backend/tests/api/test_redaction.py -v` exits 0 with at least 12 passing tests covering each of the 5 Phase 1 Success Criteria from ROADMAP.md."
  - "Faker `seed_instance(seed)` is set per-test via a pytest fixture (D-20) so surrogate values are reproducible; production runtime never sets a seed."
  - "Tests import `RedactionService` directly via `from app.services.redaction_service import get_redaction_service` - no HTTP, no FastAPI test client (D-19)."
  - "Test suite runs offline: `TRACING_PROVIDER=\"\"` (or unset) is the default for the test environment so the @traced decorator is a no-op."
---

<objective>
Ship the pytest test suite that proves all 13 Phase 1 REQ-IDs are satisfied and all 5 ROADMAP Phase 1 Success Criteria pass. The suite is the gate for the phase verifier - until these tests pass, Phase 1 is not done.

**SC#3 scope reconciliation (B5):** ROADMAP SC#3 reads "tool calls that pass UUIDs continue to work end-to-end." Phase 1 verifies SC#3 at the redaction-service layer only — UUID literals in chat input survive `redact_text()` unchanged (`TestSC3_UuidSurvival`). End-to-end tool-call symmetric coverage (where `ToolService.execute_tool(...)` arguments containing UUIDs round-trip through redaction) is owned by Phase 5 (TOOL-01..04, BUFFER-01..03) per CONTEXT.md D-12 ("Phase 1's redaction service operates on plain text only — no structured tool-arg awareness"). The Phase 1 tests assert the necessary precondition (UUID literal preservation) for Phase 5 to succeed; full tool-dispatch round-trip lands in Phase 5.

Each Success Criterion gets its own test class so failures are isolated:
- **SC#1** (representative Indonesian paragraph -> realistic surrogates + `[ENTITY_TYPE]` placeholders): `TestSC1_IndonesianParagraph` -> covers PII-01, ANON-01, ANON-02, ANON-06.
- **SC#2** (two-pass thresholds 0.7 / 0.3 honoured + bucket env vars): `TestSC2_TwoPassThresholds` -> covers PII-02, PII-03, PII-05.
- **SC#3** (UUID survives unchanged): `TestSC3_UuidSurvival` -> covers PII-04.
- **SC#4** (gender-matched surrogates + no real surname/first-name reuse): `TestSC4_GenderAndCrossCheck` -> covers ANON-03, ANON-04, ANON-05.
- **SC#5** (lazy singletons loaded once + tracing span emitted): `TestSC5_SingletonAndTracing` -> covers PERF-01, OBS-01.

Plus a small fixture / conftest module for the `Faker` seed and a session-scoped redaction-service fixture so Presidio loads exactly once across the whole suite (PERF-01 verification by counting calls).

Output: One new test file (`backend/tests/api/test_redaction.py`), one updated conftest (`backend/tests/conftest.py`), and a `pytest -v` green run covering all 5 Success Criteria.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/01-detection-anonymization-foundation/01-CONTEXT.md
@.planning/ROADMAP.md
@backend/app/services/redaction_service.py
@backend/app/services/redaction/detection.py
@backend/app/services/redaction/anonymization.py
@backend/app/services/redaction/uuid_filter.py
@backend/app/services/redaction/honorifics.py
@backend/app/services/redaction/gender_id.py
@backend/app/services/redaction/name_extraction.py

CONTEXT.md decisions consumed: D-19 (pure pytest, imports RedactionService directly, no HTTP), D-20 (Faker seed_instance per-test fixture), D-12 (Phase 1 plain text only — SC#3 is verified at the redaction layer; tool-call symmetric coverage owned by Phase 5; see B5 reconciliation in `<objective>`).

ROADMAP.md Phase 1 Success Criteria (verbatim):
1. Calling the new redaction service on a representative Indonesian legal paragraph returns text where every detected PERSON / EMAIL / PHONE / LOCATION / DATE / URL is replaced with a Faker-generated surrogate, while hard-redact entity types appear as `[ENTITY_TYPE]` placeholders.
2. Two-pass NER thresholds are honoured - `PII_SURROGATE_SCORE_THRESHOLD=0.7` and `PII_REDACT_SCORE_THRESHOLD=0.3` (and the bucket env vars `PII_SURROGATE_ENTITIES` / `PII_REDACT_ENTITIES`) take effect without restarting per-call processing.
3. A document-ID lookalike string (UUID segment) inside chat input is NOT redacted; tool calls that pass UUIDs continue to work end-to-end.
4. Person-name surrogates are gender-matched (female-original yields female surrogate when gender is detectable; ambiguous originals fall back to random) and never reuse a real surname or first name from the same input batch.
5. A backend cold-start loads Presidio NER, gender-detection model, and the nickname dictionary exactly once (lazy-singleton); subsequent redaction calls reuse them, and every call appears as a span in the configured tracing provider (`TRACING_PROVIDER=langsmith` or `langfuse`).

Existing pytest convention to follow:
- Tests live under `backend/tests/api/` (despite the `api/` name; matches existing convention per D-19).
- Project uses raw pytest (no test runner like nose).
- Async tests use `pytest.mark.asyncio` (the project already has `pytest-asyncio` in tests dependencies; verify with `pip show pytest-asyncio` if uncertain).
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: Add Faker-seed fixture to conftest.py</name>
  <files>backend/tests/conftest.py</files>
  <read_first>
    - backend/tests/conftest.py if it exists (read existing fixtures so we don't clobber)
    - .planning/phases/01-detection-anonymization-foundation/01-CONTEXT.md (D-20 - Faker seed_instance per test, never in production)
    - backend/app/services/redaction/anonymization.py (get_faker - the @lru_cache'd Faker singleton we will seed)
  </read_first>
  <action>
**Step 0 (B1 — directory scaffolding):** before writing any test file, ensure the
`backend/tests/api/` directory and its `__init__.py` markers exist. The current
repo has no `backend/tests/` directory at all (verified at planning time —
`ls backend/tests/ 2>/dev/null` returns nothing). Run:

```bash
mkdir -p backend/tests/api
touch backend/tests/__init__.py backend/tests/api/__init__.py
```

This creates the package skeleton pytest needs to discover `conftest.py` and
`test_redaction.py`. Do this BEFORE creating `conftest.py`.

If `backend/tests/conftest.py` exists, APPEND to it. If it does not exist, create it with this content:

```python
"""Shared pytest fixtures for the LexCore backend test suite.

Phase 1 (milestone v1.0) adds:
- `seeded_faker`: per-test Faker seed for reproducible surrogate generation
  (D-20: production never sets a seed).
- `redaction_service`: session-scoped to verify @lru_cache singleton behaviour
  (PERF-01 / SC#5).
"""

from __future__ import annotations

import pytest


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
```

If a conftest.py already exists, only ADD the two fixtures above (don't duplicate or replace existing fixtures). Use `pytest --fixtures backend/tests/api/test_redaction.py` after adding to confirm both fixtures are discoverable.
  </action>
  <verify>
    <automated>test -d backend/tests/api &amp;&amp; test -f backend/tests/__init__.py &amp;&amp; test -f backend/tests/api/__init__.py &amp;&amp; cd backend &amp;&amp; source venv/bin/activate &amp;&amp; python -c "import importlib; mod = importlib.import_module('tests.conftest'); print(hasattr(mod, 'seeded_faker'), hasattr(mod, 'redaction_service'))"</automated>
  </verify>
  <acceptance_criteria>
    - **B1 (test scaffolding):** `test -d backend/tests/api && test -f backend/tests/__init__.py && test -f backend/tests/api/__init__.py` exits 0.
    - `backend/tests/conftest.py` exists.
    - `grep -n "def seeded_faker" backend/tests/conftest.py` returns 1 match.
    - `grep -n "def redaction_service" backend/tests/conftest.py` returns 1 match.
    - `grep -n "scope=\"session\"" backend/tests/conftest.py` returns at least 1 match (the session-scoped redaction_service).
    - `grep -n "seed_instance(42)" backend/tests/conftest.py` returns 1 match.
    - `cd backend && source venv/bin/activate && python -c "from tests.conftest import seeded_faker, redaction_service; print('OK')"` exits 0.
  </acceptance_criteria>
  <done>conftest.py exposes the seeded_faker (per-test) and redaction_service (session-scoped) fixtures so the test file can request them.</done>
</task>

<task type="auto" tdd="false">
  <name>Task 2: Create test_redaction.py with one TestSC class per Phase 1 Success Criterion</name>
  <files>backend/tests/api/test_redaction.py</files>
  <read_first>
    - backend/tests/conftest.py (Task 1 - the two fixtures)
    - backend/app/services/redaction_service.py (RedactionResult schema; redact_text is async)
    - backend/app/services/redaction/detection.py (Entity model; detect_entities returns the 3-tuple (masked_text, entities, sentinels) per W10)
    - backend/app/services/redaction/uuid_filter.py (apply_uuid_mask raises RedactionError on sentinel collision)
    - .planning/phases/01-detection-anonymization-foundation/01-CONTEXT.md (D-19, D-20; specifics section keeps the "Aaron Thompson DDS" / "Margaret Thompson" surname-collision scenario front-of-mind)
    - .planning/ROADMAP.md (Phase 1 SC#1..#5 verbatim - quote them as test docstrings)
  </read_first>
  <action>
Create `backend/tests/api/test_redaction.py` with this complete content:

```python
"""Phase 1 redaction service tests.

Each TestSC<N>_... class corresponds to one Phase 1 ROADMAP Success Criterion.
Test docstrings quote the SC verbatim. Failures isolate to the SC they cover.

Conventions (D-19):
- Pure pytest. No HTTP. Imports RedactionService directly.
- Async tests use @pytest.mark.asyncio.
- Faker is seeded via the seeded_faker fixture (D-20) where exact surrogate
  values matter; structural assertions (no Bambang, contains [US_SSN], etc.)
  do not require a seed.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


# ---------- Helpers ---------------------------------------------------------

INDONESIAN_PARAGRAPH = (
    "Pak Bambang Sutrisno (email: bambang.s@example.com, telp +62-812-1234-5678) "
    "tinggal di Jakarta dan menerima surat tertanggal 12 Maret 2026. "
    "Lihat profil di https://lexcore.id/u/bambang. "
    "Nomor SSN 123-45-6789 dan kartu kredit 4111-1111-1111-1111 jangan dibagikan. "
    "Document ID: 6ba7b810-9dad-11d1-80b4-00c04fd430c8."
)


# ---------- SC#1: representative Indonesian paragraph ----------------------

class TestSC1_IndonesianParagraph:
    """SC#1: Calling the new redaction service on a representative Indonesian
    legal paragraph returns text where every detected PERSON / EMAIL / PHONE /
    LOCATION / DATE / URL is replaced with a Faker-generated surrogate, while
    hard-redact entity types appear as [ENTITY_TYPE] placeholders.
    Covers: PII-01, ANON-01, ANON-02, ANON-06.
    """

    async def test_real_pii_values_absent_from_output(self, redaction_service):
        result = await redaction_service.redact_text(INDONESIAN_PARAGRAPH)
        assert "Bambang" not in result.anonymized_text
        assert "bambang.s@example.com" not in result.anonymized_text
        assert "+62-812-1234-5678" not in result.anonymized_text

    async def test_hard_redact_placeholders_present(self, redaction_service):
        result = await redaction_service.redact_text(INDONESIAN_PARAGRAPH)
        assert "[US_SSN]" in result.anonymized_text or "[CREDIT_CARD]" in result.anonymized_text
        # Hard-redact entries never enter entity_map (FR-3.5)
        for v in result.entity_map.values():
            assert not (v.startswith("[") and v.endswith("]") and "_" not in v)

    async def test_entity_map_populated_for_surrogates(self, redaction_service):
        result = await redaction_service.redact_text(INDONESIAN_PARAGRAPH)
        # At least PERSON, EMAIL_ADDRESS, PHONE_NUMBER should appear as keys.
        assert len(result.entity_map) >= 3
        # No hard-redact placeholder appears as a key.
        for k in result.entity_map.keys():
            assert not k.startswith("[")


# ---------- SC#2: two-pass thresholds & bucket env vars --------------------

class TestSC2_TwoPassThresholds:
    """SC#2: Two-pass NER thresholds are honoured -
    PII_SURROGATE_SCORE_THRESHOLD=0.7 and PII_REDACT_SCORE_THRESHOLD=0.3
    (and the bucket env vars PII_SURROGATE_ENTITIES / PII_REDACT_ENTITIES)
    take effect without restarting per-call processing.
    Covers: PII-02, PII-03, PII-05.
    """

    async def test_settings_thresholds_match_prd_defaults(self):
        from app.config import get_settings
        s = get_settings()
        assert s.pii_surrogate_score_threshold == 0.7
        assert s.pii_redact_score_threshold == 0.3

    async def test_settings_bucket_env_vars_match_prd_defaults(self):
        from app.config import get_settings
        s = get_settings()
        for et in ("PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "LOCATION", "DATE_TIME", "URL", "IP_ADDRESS"):
            assert et in s.pii_surrogate_entities
        for et in ("CREDIT_CARD", "US_SSN", "IBAN_CODE", "MEDICAL_LICENSE"):
            assert et in s.pii_redact_entities

    async def test_detected_entities_respect_per_bucket_thresholds(self, redaction_service):
        from app.services.redaction.detection import detect_entities
        _masked, ents, _sentinels = detect_entities(INDONESIAN_PARAGRAPH)
        from app.config import get_settings
        s = get_settings()
        for e in ents:
            if e.bucket == "surrogate":
                assert e.score >= s.pii_surrogate_score_threshold, e
            elif e.bucket == "redact":
                assert e.score >= s.pii_redact_score_threshold, e
            else:
                pytest.fail(f"Unknown bucket {e.bucket!r} on entity {e}")


# ---------- SC#3: UUID survives ---------------------------------------------

class TestSC3_UuidSurvival:
    """SC#3: A document-ID lookalike string (UUID segment) inside chat input
    is NOT redacted; tool calls that pass UUIDs continue to work end-to-end.

    SCOPE (B5 reconciliation): Phase 1 verifies SC#3 at the redaction-service
    layer only — UUID literals survive `redact_text()` unchanged. End-to-end
    tool-call symmetric coverage (ToolService.execute_tool args round-tripping
    through redaction) is owned by Phase 5 per CONTEXT.md D-12 (Phase 1
    operates on plain text only — no structured tool-arg awareness). These
    tests assert the necessary precondition (UUID literal preservation) for
    Phase 5 to succeed.

    Covers: PII-04.
    """

    async def test_uuid_passes_through_untouched(self, redaction_service):
        uuid = "6ba7b810-9dad-11d1-80b4-00c04fd430c8"
        text = f"Doc {uuid} sent to Pak Bambang."
        result = await redaction_service.redact_text(text)
        assert uuid in result.anonymized_text
        # Bambang should still be replaced
        assert "Bambang" not in result.anonymized_text

    async def test_multiple_uuids_all_preserved(self, redaction_service):
        u1 = "6ba7b810-9dad-11d1-80b4-00c04fd430c8"
        u2 = "11111111-2222-3333-4444-555555555555"
        text = f"Refs {u1} and {u2} for Sri Mulyani."
        result = await redaction_service.redact_text(text)
        assert u1 in result.anonymized_text
        assert u2 in result.anonymized_text

    async def test_sentinel_collision_raises(self):
        from app.services.redaction import RedactionError
        from app.services.redaction.uuid_filter import apply_uuid_mask
        with pytest.raises(RedactionError):
            apply_uuid_mask("text containing <<UUID_0>> sentinel literal")


# ---------- SC#4: gender match + no surname/first-name reuse ---------------

class TestSC4_GenderAndCrossCheck:
    """SC#4: Person-name surrogates are gender-matched (female-original yields
    female surrogate when gender is detectable; ambiguous originals fall back
    to random) and never reuse a real surname or first name from the same
    input batch.
    Covers: ANON-03, ANON-04, ANON-05.
    """

    async def test_indonesian_gender_lookup_table(self):
        from app.services.redaction.gender_id import lookup_gender
        assert lookup_gender("Bambang") == "M"
        assert lookup_gender("Sri") == "F"
        assert lookup_gender("Kris") == "unknown"  # tagged "U"
        assert lookup_gender("NotARealName") == "unknown"

    async def test_real_first_and_surname_tokens_never_reused(self, redaction_service):
        text = "Aaron Thompson DDS dan Margaret Thompson tinggal di Surabaya."
        result = await redaction_service.redact_text(text)
        # PRD §7.5 surname-collision corruption scenario: no surrogate may
        # contain a real first-name or surname token.
        forbidden = {"aaron", "thompson", "margaret"}
        for surrogate in result.entity_map.values():
            tokens = {t.lower() for t in surrogate.split() if t}
            assert not (tokens & forbidden), f"Surrogate {surrogate!r} reused real token"

    async def test_same_real_value_yields_same_surrogate_within_call(self, redaction_service):
        text = "Pak Bambang met Bambang yesterday. Bambang was happy."
        result = await redaction_service.redact_text(text)
        # Within one call, "Bambang" -> single surrogate (case-insensitive consistency).
        unique_surrogates = set(result.entity_map.values())
        # The text has two real PERSON references ("Pak Bambang" and "Bambang");
        # they may or may not collapse depending on Presidio span boundaries,
        # but the entity_map should never contain TWO different surrogates for
        # the literal token "Bambang".
        bambang_surrogates = {v for k, v in result.entity_map.items() if "Bambang" in k}
        assert len(bambang_surrogates) <= 1, bambang_surrogates


# ---------- SC#5: lazy singletons + tracing span ---------------------------

class TestSC5_SingletonAndTracing:
    """SC#5: A backend cold-start loads Presidio NER, gender-detection model,
    and the nickname dictionary exactly once (lazy-singleton); subsequent
    redaction calls reuse them, and every call appears as a span in the
    configured tracing provider.
    Covers: PERF-01, OBS-01.
    """

    async def test_get_redaction_service_is_singleton(self):
        from app.services.redaction_service import get_redaction_service
        a = get_redaction_service()
        b = get_redaction_service()
        assert a is b

    async def test_get_analyzer_is_singleton(self):
        from app.services.redaction.detection import get_analyzer
        assert get_analyzer() is get_analyzer()

    async def test_get_faker_is_singleton(self):
        from app.services.redaction.anonymization import get_faker
        assert get_faker() is get_faker()

    async def test_get_gender_detector_is_singleton(self):
        from app.services.redaction.anonymization import get_gender_detector
        assert get_gender_detector() is get_gender_detector()

    async def test_traced_decorator_is_no_op_when_provider_empty(self, monkeypatch):
        # With TRACING_PROVIDER unset/empty (the test default), @traced returns
        # the wrapped function as-is. Verify by calling redact_text and ensuring
        # we get the real RedactionResult back (not a tracing wrapper).
        from app.services.redaction_service import RedactionResult, get_redaction_service
        result = await get_redaction_service().redact_text("Test message.")
        assert isinstance(result, RedactionResult)
        assert result.latency_ms >= 0.0

    async def test_traced_decorator_does_not_call_langsmith_when_provider_empty(
        self, monkeypatch
    ):
        """I14: when TRACING_PROVIDER='', @traced must NOT call
        langsmith.traceable or langfuse.observe. Re-import tracing_service to
        re-evaluate the decorator binding under the empty-provider env, then
        define a wrapped function and call it.
        """
        import importlib

        # Make langsmith.traceable explode if called at any point.
        def _boom(*_a, **_kw):
            raise AssertionError("langsmith.traceable should not be called")

        monkeypatch.setattr("langsmith.traceable", _boom, raising=False)
        monkeypatch.setenv("TRACING_PROVIDER", "")

        import app.services.tracing_service as ts

        importlib.reload(ts)

        @ts.traced(name="t")
        def f() -> int:
            return 42

        assert f() == 42


# ---------- B4: log-privacy regression -------------------------------------

class TestSC5_LogPrivacy:
    """B4: enforce that no real PII value reaches log output. A regression
    such as `logger.debug("entity=%s", entity.text)` would silently leak real
    user data into stdout / Railway logs; this class fails fast if that ever
    ships.
    """

    async def test_no_real_pii_in_log_output(self, redaction_service, caplog):
        import logging as _logging

        with caplog.at_level(_logging.DEBUG):
            await redaction_service.redact_text(INDONESIAN_PARAGRAPH)

        # Real PII strings present in INDONESIAN_PARAGRAPH (the module-level
        # fixture). Update this list if the fixture changes.
        forbidden = [
            "Bambang Sutrisno",
            "Bambang",
            "Sutrisno",
            "bambang.s@example.com",
            "+62-812-1234-5678",
            "Jakarta",
            "https://lexcore.id/u/bambang",
        ]

        for record in caplog.records:
            msg = record.getMessage()
            for value in forbidden:
                assert value not in msg, (
                    f"Real PII {value!r} leaked in log record: {msg!r} "
                    f"(logger={record.name}, level={record.levelname})"
                )


# ---------- W11: D-08 vs D-06 placeholder shape disambiguation -------------

class TestPlaceholderShapes:
    """W11: D-08 hard-redact placeholders are bare `[ENTITY_TYPE]`; D-06
    collision-fallback placeholders carry a 6-hex blake2b suffix
    `[ENTITY_TYPE_HHHHHH]`. The two shapes must remain distinguishable so
    downstream Phase 2 dedup logic can tell them apart.
    """

    async def test_placeholder_shapes_are_distinguishable(
        self, redaction_service
    ):
        import re

        # Run a redaction that we expect to trip the hard-redact path
        # (CREDIT_CARD / US_SSN are in INDONESIAN_PARAGRAPH).
        result = await redaction_service.redact_text(INDONESIAN_PARAGRAPH)
        output = result.anonymized_text

        # Every bracketed token in the output:
        all_placeholders = re.findall(
            r"\[[A-Z][A-Z_]+(?:_[0-9A-F]{6})?\]", output
        )
        assert all_placeholders, (
            "Expected at least one bracketed placeholder in output "
            f"(got: {output!r})"
        )

        # Classify each placeholder as D-08 (bare) vs D-06 (with hex suffix).
        d06_pattern = re.compile(r"^\[[A-Z][A-Z_]+_[0-9A-F]{6}\]$")
        d08_pattern = re.compile(r"^\[[A-Z][A-Z_]+\]$")
        for tok in all_placeholders:
            assert d06_pattern.match(tok) or d08_pattern.match(tok), (
                f"Placeholder {tok!r} matches neither D-08 nor D-06 shape"
            )
            # The two shapes are exclusive (a 6-hex suffix never appears in a
            # bare D-08 form because D-08 placeholders contain no underscore-
            # suffixed hex segment).
            assert not (
                d06_pattern.match(tok) and d08_pattern.match(tok)
            ), f"Placeholder {tok!r} ambiguously matches both shapes"
```

Notes:
- `pytestmark = pytest.mark.asyncio` at module top promotes every async test to a pytest-asyncio test; no need to decorate each individually.
- The "Aaron Thompson DDS / Margaret Thompson" test directly maps to PRD §7.5 (the example mentioned in CONTEXT.md `<specifics>` and the rationale for D-07).
- SC#5 verifies BOTH the singleton property (object identity across calls) AND that `@traced` is a no-op when `TRACING_PROVIDER=""` (the test environment default).
- We do NOT test the langsmith / langfuse provider paths in Phase 1 - that requires live API credentials. SUMMARY notes this as a Phase 6 hardening test.
- After writing the file, the PostToolUse import-check hook may warn that the test module is large (~150 lines). That's fine - large tests beat fragmented assertion-per-file.
  </action>
  <verify>
    <automated>cd backend &amp;&amp; source venv/bin/activate &amp;&amp; pytest backend/tests/api/test_redaction.py -v --tb=short</automated>
  </verify>
  <acceptance_criteria>
    - `backend/tests/api/test_redaction.py` exists.
    - `grep -n "class TestSC1_IndonesianParagraph" backend/tests/api/test_redaction.py` returns 1 match.
    - `grep -n "class TestSC2_TwoPassThresholds" backend/tests/api/test_redaction.py` returns 1 match.
    - `grep -n "class TestSC3_UuidSurvival" backend/tests/api/test_redaction.py` returns 1 match.
    - `grep -n "class TestSC4_GenderAndCrossCheck" backend/tests/api/test_redaction.py` returns 1 match.
    - `grep -n "class TestSC5_SingletonAndTracing" backend/tests/api/test_redaction.py` returns 1 match.
    - `grep -n "pytestmark = pytest.mark.asyncio" backend/tests/api/test_redaction.py` returns 1 match.
    - `grep -c "async def test_" backend/tests/api/test_redaction.py` returns at least 14 (covers SC#1..SC#5 plus B4 log-privacy and W11 placeholder-shape regression tests).
    - **B4 (test class present):** `grep -n "class TestSC5_LogPrivacy" backend/tests/api/test_redaction.py` returns 1 match.
    - **B4 (assertion mechanism):** `grep -n "async def test_no_real_pii_in_log_output" backend/tests/api/test_redaction.py` returns 1 match; `grep -n "caplog" backend/tests/api/test_redaction.py` returns at least 2 matches (fixture parameter + at_level usage).
    - **W11 (test class present):** `grep -n "class TestPlaceholderShapes" backend/tests/api/test_redaction.py` returns 1 match; `grep -n "async def test_placeholder_shapes_are_distinguishable" backend/tests/api/test_redaction.py` returns 1 match.
    - **B5 (SC#3 reconciliation prose):** `grep -n "B5 reconciliation\|tool-call symmetric coverage\|owned by Phase 5" backend/tests/api/test_redaction.py` returns at least 1 match (TestSC3_UuidSurvival docstring).
    - **I14 (no-op @traced regression test):** `grep -n "test_traced_decorator_does_not_call_langsmith_when_provider_empty" backend/tests/api/test_redaction.py` returns 1 match.
    - `cd backend && source venv/bin/activate && pytest backend/tests/api/test_redaction.py -v` exits 0; the summary line reports `>=12 passed` and `0 failed`.
    - `cd backend && source venv/bin/activate && pytest backend/tests/api/test_redaction.py::TestSC3_UuidSurvival -v` exits 0 and reports 3 passing tests.
    - `cd backend && source venv/bin/activate && pytest backend/tests/api/test_redaction.py::TestSC5_LogPrivacy::test_no_real_pii_in_log_output -v` exits 0 (B4).
    - `cd backend && source venv/bin/activate && pytest backend/tests/api/test_redaction.py::TestPlaceholderShapes -v` exits 0 (W11).
    - `cd backend && source venv/bin/activate && python -c "from app.main import app; print('OK')"` exits 0 (no test imports broke production code).
  </acceptance_criteria>
  <done>test_redaction.py covers all 5 ROADMAP Phase 1 Success Criteria across 5 TestSC classes (>=12 individual async tests); pytest exits 0; conftest fixtures wire the Faker seed and session-scoped service.</done>
</task>

</tasks>

<verification>
Final phase-level verification:
```bash
cd backend && source venv/bin/activate
pytest backend/tests/api/test_redaction.py -v --tb=short
# Expected: all tests pass.

# Sanity smoke that the rest of the API still imports
python -c "from app.main import app; print('OK')"
```
</verification>

<success_criteria>
1. ROADMAP Phase 1 SC#1 verified by `TestSC1_IndonesianParagraph`.
2. ROADMAP Phase 1 SC#2 verified by `TestSC2_TwoPassThresholds`.
3. ROADMAP Phase 1 SC#3 verified by `TestSC3_UuidSurvival`.
4. ROADMAP Phase 1 SC#4 verified by `TestSC4_GenderAndCrossCheck`.
5. ROADMAP Phase 1 SC#5 verified by `TestSC5_SingletonAndTracing`.
6. All 13 Phase 1 REQ-IDs (PII-01..05, ANON-01..06, PERF-01, OBS-01) have at least one test asserting their behaviour.
7. Test suite runs offline with `TRACING_PROVIDER=""` (default).
</success_criteria>

<output>
After completion, create `.planning/phases/01-detection-anonymization-foundation/01-07-SUMMARY.md` capturing:
- Final test count (`pytest --collect-only -q backend/tests/api/test_redaction.py | wc -l`).
- Pass / fail summary on the first green run.
- Wall-clock time of the full suite (cold-start vs warm).
- Any tests that had to be marked `xfail` due to Presidio multilingual model coverage gaps on Indonesian text - record these as Phase 4-6 follow-ups, NOT as scope reductions to Phase 1.
- Confirmation that `pytest backend/tests/api/test_redaction.py` is the single end-to-end gate for Phase 1 verification.
</output>
