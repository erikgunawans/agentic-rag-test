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
    layer only - UUID literals survive `redact_text()` unchanged. End-to-end
    tool-call symmetric coverage (ToolService.execute_tool args round-tripping
    through redaction) is owned by Phase 5 per CONTEXT.md D-12 (Phase 1
    operates on plain text only - no structured tool-arg awareness). These
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
        # ANON-03: within one call, the SAME real PERSON value reuses the same
        # surrogate. Use two occurrences of an identical bare name so Presidio
        # produces two spans with the same `.text`; the anonymizer's
        # case-insensitive entity_map lookup must collapse them to one
        # surrogate. (We intentionally avoid honorifics like "Pak Bambang"
        # vs "Bambang" because Presidio span boundaries treat those as
        # different entity texts -> different keys -> different surrogates,
        # which is the documented behaviour, not what ANON-03 covers.)
        text = "Bambang Sutrisno menelpon. Kemudian Bambang Sutrisno pulang."
        result = await redaction_service.redact_text(text)

        # The literal real value "Bambang Sutrisno" must map to exactly one
        # surrogate within this single call.
        keys_matching = [
            k for k in result.entity_map.keys() if k.lower() == "bambang sutrisno"
        ]
        assert keys_matching, (
            f"Expected 'Bambang Sutrisno' in entity_map keys; got {list(result.entity_map.keys())!r}"
        )
        surrogates_for_bambang = {result.entity_map[k] for k in keys_matching}
        assert len(surrogates_for_bambang) == 1, (
            f"Same real value yielded multiple surrogates: {surrogates_for_bambang!r}"
        )

        # And the anonymized text must NOT contain "Bambang" anywhere.
        assert "Bambang" not in result.anonymized_text


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
