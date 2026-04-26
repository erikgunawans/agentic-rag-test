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
in any log message produced by these tests. TestSC6_LogPrivacy enforces the
no-real-PII invariant for the new methods (redact_text(registry=...) and
de_anonymize_text).

Detection notes (calibrated against the live xx-multilingual Presidio model):
- "Maria Santos" / "maria santos" — both detected as PERSON. ALL-CAPS variants
  are NOT reliably detected by the xx model, so case-insensitive cross-call
  tests use Title vs. lower casings, not Title vs. ALL-CAPS.
- "Pak Bambang Sutrisno" — detected with the honorific included. The bare
  form "Bambang Sutrisno" is detected separately. Tests that need a
  predictable lookup key use the bare form.
- US_SSN is not consistently detected by the xx-multilingual recogniser
  (the UsSsnRecognizer only ships for "en"); CREDIT_CARD does work.
"""

from __future__ import annotations

import asyncio

import pytest

pytestmark = pytest.mark.asyncio


# ---------- SC#1: case-insensitive consistency within a turn ----------------


class TestSC1_CaseInsensitiveConsistency:
    """SC#1: Within a single thread, mentioning the same real person, email,
    or phone number twice (in different casings) yields the same surrogate
    both times; the registry exposes case-insensitive lookups.
    Covers: REG-01, REG-03, REG-04.
    """

    async def test_person_title_vs_lower_same_surrogate(
        self, redaction_service, empty_registry, seeded_faker,
    ):
        # Title-case detection then lower-case detection — both pass through
        # Presidio xx PERSON recognition. The registry collapses them via
        # casefold-keyed lookup (REG-03 / D-36).
        await redaction_service.redact_text(
            "Maria Santos works here.", registry=empty_registry,
        )
        await redaction_service.redact_text(
            "maria santos called.", registry=empty_registry,
        )

        s1 = empty_registry.lookup("Maria Santos")
        s2 = empty_registry.lookup("maria santos")
        s3 = empty_registry.lookup("MARIA SANTOS")  # case-insensitive lookup
        assert s1 is not None, "registry must have entry for Maria Santos"
        assert s1 == s2, (
            f"Case-insensitive lookup must return same surrogate; got {s1!r} vs {s2!r}"
        )
        assert s1 == s3, (
            f"Case-insensitive lookup must work for ALL-CAPS query; got {s1!r} vs {s3!r}"
        )

    async def test_email_case_insensitive_consistency(
        self, redaction_service, empty_registry, seeded_faker,
    ):
        # Presidio's EmailRecognizer detects emails regardless of casing,
        # so cross-call lower vs. ALL-CAPS works for emails (unlike PERSON).
        text1 = "Email: bambang.s@example.com tolong dijaga."
        text2 = "Hubungi BAMBANG.S@EXAMPLE.COM untuk verifikasi."
        await redaction_service.redact_text(text1, registry=empty_registry)
        await redaction_service.redact_text(text2, registry=empty_registry)

        s1 = empty_registry.lookup("bambang.s@example.com")
        s2 = empty_registry.lookup("BAMBANG.S@EXAMPLE.COM")
        assert s1 is not None, "registry must have entry for bambang.s@example.com"
        assert s1 == s2, (
            f"Case-insensitive email lookup must return same surrogate; got {s1!r} vs {s2!r}"
        )

    async def test_only_one_registry_row_per_lower_value(
        self, redaction_service, empty_registry, seeded_faker,
    ):
        """REG-04 + D-23 composite UNIQUE: even with multiple casings across
        multiple calls, the registry retains exactly ONE row per lower value.
        """
        from app.database import get_supabase_client

        await redaction_service.redact_text(
            "Maria Santos works here.", registry=empty_registry,
        )
        await redaction_service.redact_text(
            "maria santos called.", registry=empty_registry,
        )

        client = get_supabase_client()
        rows = (
            client.table("entity_registry")
            .select("id")
            .eq("thread_id", empty_registry.thread_id)
            .eq("real_value_lower", "maria santos")
            .execute()
            .data
        )
        assert len(rows) == 1, (
            f"Expected exactly one registry row for 'maria santos', got {len(rows)}"
        )


# ---------- SC#2: resume across restart -------------------------------------


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
        await redaction_service.redact_text(
            "Maria Santos works here.", registry=reg1,
        )
        s1 = reg1.lookup("Maria Santos")
        assert s1 is not None, "first call must persist a surrogate"
        del reg1  # simulate restart

        reg2 = await ConversationRegistry.load(fresh_thread_id)
        s2 = reg2.lookup("Maria Santos")
        assert s2 is not None, (
            "second load must observe persisted surrogate (REG-02)"
        )
        assert s1 == s2, (
            f"Restart-reloaded surrogate diverged: {s1!r} vs {s2!r}"
        )

    async def test_resumed_registry_reuses_surrogate_in_subsequent_call(
        self, redaction_service, fresh_thread_id, seeded_faker,
    ):
        """REG-02 + REG-04: after reload, a NEW redact_text call mentioning
        the same real entity returns the persisted surrogate (not a new one).
        """
        from app.services.redaction.registry import ConversationRegistry

        reg1 = await ConversationRegistry.load(fresh_thread_id)
        r1 = await redaction_service.redact_text(
            "Maria Santos works here.", registry=reg1,
        )
        original_surrogate = reg1.lookup("Maria Santos")
        assert original_surrogate is not None
        # Simulate process restart: drop in-memory state.
        del reg1

        # Re-load and run a NEW redact call with the same real entity.
        reg2 = await ConversationRegistry.load(fresh_thread_id)
        r2 = await redaction_service.redact_text(
            "maria santos called again.", registry=reg2,
        )
        # The output must contain the SAME surrogate as before.
        assert original_surrogate in r2.anonymized_text, (
            f"After resume, expected surrogate {original_surrogate!r} in "
            f"output {r2.anonymized_text!r}"
        )


# ---------- SC#3: case-insensitive de-anon round-trip -----------------------


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
        assert email_surrogate is not None, "email surrogate must be persisted"

        # Simulate LLM emitting the surrogate uppercased.
        llm_output = f"The email {email_surrogate.upper()} was used."
        roundtrip = await redaction_service.de_anonymize_text(
            llm_output, empty_registry,
        )
        assert "bambang.s@example.com" in roundtrip, (
            f"De-anon failed to restore original casing email; got: {roundtrip!r}"
        )

    async def test_titlecased_person_surrogate_resolves_to_original_real(
        self, redaction_service, empty_registry, seeded_faker,
    ):
        await redaction_service.redact_text(
            "Maria Santos works here.", registry=empty_registry,
        )
        person_surrogate = empty_registry.lookup("Maria Santos")
        assert person_surrogate is not None

        # LLM emits the surrogate in a different case (lower).
        llm_output = f"Hello, {person_surrogate.lower()}, welcome."
        roundtrip = await redaction_service.de_anonymize_text(
            llm_output, empty_registry,
        )
        assert "Maria Santos" in roundtrip, (
            f"De-anon failed to restore original casing PERSON; got: {roundtrip!r}"
        )

    async def test_mixed_case_surrogate_round_trip(
        self, redaction_service, empty_registry, seeded_faker,
    ):
        """DEANON-02: every casing of the surrogate (lower / upper / mixed)
        round-trips back to the original real value's exact casing.
        """
        await redaction_service.redact_text(
            "Email saya bambang.s@example.com sudah lama.",
            registry=empty_registry,
        )
        surr = empty_registry.lookup("bambang.s@example.com")
        assert surr is not None

        for case_variant in (surr.lower(), surr.upper(), surr.title()):
            llm_output = f"Use {case_variant} for verification."
            roundtrip = await redaction_service.de_anonymize_text(
                llm_output, empty_registry,
            )
            assert "bambang.s@example.com" in roundtrip, (
                f"De-anon failed for case_variant={case_variant!r}; "
                f"got: {roundtrip!r}"
            )


# ---------- SC#4: hard-redact never persisted; survives de-anon -------------


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
        assert "[CREDIT_CARD]" in result.anonymized_text, (
            f"hard-redact placeholder missing; got {result.anonymized_text!r}"
        )

        client = get_supabase_client()
        rows = (
            client.table("entity_registry")
            .select("entity_type")
            .eq("thread_id", empty_registry.thread_id)
            .execute()
            .data
        )
        types = {r["entity_type"] for r in rows}
        assert "CREDIT_CARD" not in types, (
            f"Hard-redact leaked into registry; persisted types: {types!r}"
        )
        # Defense in depth: no row's real_value_lower should equal the
        # raw card number either.
        rows_full = (
            client.table("entity_registry")
            .select("real_value_lower")
            .eq("thread_id", empty_registry.thread_id)
            .execute()
            .data
        )
        for r in rows_full:
            assert "4111" not in r["real_value_lower"], (
                f"Raw credit card number leaked into registry: {r!r}"
            )

    async def test_credit_card_placeholder_survives_de_anon(
        self, redaction_service, empty_registry, seeded_faker,
    ):
        """D-35 / DEANON-05: hard-redact placeholders pass through
        de_anonymize_text unchanged (they are never in the registry).
        """
        from app.services.redaction.registry import ConversationRegistry

        text_in = "Card 4111-1111-1111-1111 belongs to Pak Bambang."
        result = await redaction_service.redact_text(
            text_in, registry=empty_registry,
        )
        assert "[CREDIT_CARD]" in result.anonymized_text

        # Re-load fresh registry to simulate per-turn lifecycle.
        reg2 = await ConversationRegistry.load(empty_registry.thread_id)
        roundtrip = await redaction_service.de_anonymize_text(
            result.anonymized_text, reg2,
        )
        assert "[CREDIT_CARD]" in roundtrip, (
            f"hard-redact placeholder lost after de-anon; got {roundtrip!r}"
        )

    async def test_synthetic_hard_redact_placeholders_survive_de_anon(
        self, redaction_service, empty_registry, seeded_faker,
    ):
        """D-35: any [ENTITY_TYPE] placeholder in input text passes through
        de_anonymize_text unchanged. We feed synthetic placeholders directly
        so the test is independent of which Presidio recognisers are loaded
        for the active language model.
        """
        # Pre-populate the registry with one PERSON entry so de_anon has
        # SOMETHING to substitute (proves placeholders aren't matched even
        # when the substitution loop runs).
        await redaction_service.redact_text(
            "Maria Santos works here.", registry=empty_registry,
        )

        synthetic_text = (
            "Sensitive: [CREDIT_CARD] and [US_SSN] and [IBAN_CODE] "
            "must never be exposed."
        )
        roundtrip = await redaction_service.de_anonymize_text(
            synthetic_text, empty_registry,
        )
        assert "[CREDIT_CARD]" in roundtrip, (
            f"[CREDIT_CARD] lost; got {roundtrip!r}"
        )
        assert "[US_SSN]" in roundtrip, (
            f"[US_SSN] lost; got {roundtrip!r}"
        )
        assert "[IBAN_CODE]" in roundtrip, (
            f"[IBAN_CODE] lost; got {roundtrip!r}"
        )


# ---------- SC#5: concurrent registry-write race ----------------------------


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

        # Both texts mention "Maria Santos" — the same real PERSON.
        text_a = "Maria Santos works here in the office."
        text_b = "maria santos called this morning."

        await asyncio.gather(
            redaction_service.redact_text(text_a, registry=empty_registry),
            redaction_service.redact_text(text_b, registry=empty_registry),
        )

        sa = empty_registry.lookup("Maria Santos")
        sb = empty_registry.lookup("maria santos")
        assert sa is not None, "race must still produce a surrogate"
        assert sa == sb, (
            f"Race produced divergent surrogates: {sa!r} vs {sb!r}"
        )

        # Critical assertion: composite UNIQUE constraint + per-thread
        # asyncio.Lock together guarantee exactly ONE row.
        client = get_supabase_client()
        rows = (
            client.table("entity_registry")
            .select("id,surrogate_value")
            .eq("thread_id", empty_registry.thread_id)
            .eq("real_value_lower", "maria santos")
            .execute()
            .data
        )
        assert len(rows) == 1, (
            f"Expected exactly one registry row, got {len(rows)} — "
            f"composite UNIQUE constraint or per-thread asyncio.Lock failed: "
            f"{rows!r}"
        )

    async def test_concurrent_calls_do_not_corrupt_anonymized_output(
        self, redaction_service, empty_registry, seeded_faker,
    ):
        """PERF-03: under concurrent gather, both anonymized outputs must
        substitute the entity to the same agreed-upon surrogate (no half-
        applied state from a racing coroutine).
        """
        text_a = "Maria Santos works here in the office."
        text_b = "Maria Santos called this morning."

        ra, rb = await asyncio.gather(
            redaction_service.redact_text(text_a, registry=empty_registry),
            redaction_service.redact_text(text_b, registry=empty_registry),
        )

        # Both outputs must NOT contain the real value.
        assert "Maria Santos" not in ra.anonymized_text, (
            f"Real value leaked in concurrent output A: {ra.anonymized_text!r}"
        )
        assert "Maria Santos" not in rb.anonymized_text, (
            f"Real value leaked in concurrent output B: {rb.anonymized_text!r}"
        )
        # Both outputs must use the SAME surrogate (no torn state).
        sa = ra.entity_map.get("Maria Santos")
        sb = rb.entity_map.get("Maria Santos")
        assert sa is not None and sb is not None, (
            f"entity_map missing key in race: a={ra.entity_map!r} b={rb.entity_map!r}"
        )
        assert sa == sb, (
            f"Concurrent calls produced different surrogates for same real "
            f"value: {sa!r} vs {sb!r}"
        )


# ---------- PRD §7.5 / D-37: cross-turn surname collision -------------------


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
        assert s1 is not None, "turn 1 surrogate must be persisted"

        await redaction_service.redact_text(
            "Margaret Thompson called.", registry=empty_registry,
        )
        s2 = empty_registry.lookup("Margaret Thompson")
        assert s2 is not None, "turn 3 surrogate must be persisted"
        sur2_tokens = {t.casefold() for t in s2.split()}

        # Phase 2 invariant: turn-3 surrogate avoids real tokens already in
        # registry (maria, santos) AND turn-3 reals (margaret, thompson).
        for forbidden in {"maria", "santos", "margaret", "thompson"}:
            assert forbidden not in sur2_tokens, (
                f"Cross-turn collision: surrogate {s2!r} contains forbidden "
                f"token {forbidden!r}"
            )


# ---------- B4 / D-18 / D-41: log-privacy invariant for new methods --------


class TestSC6_LogPrivacy:
    """B4 / D-18 / D-41: enforce that no real PII value reaches log output
    from the NEW Phase 2 methods (redact_text(registry=...) and
    de_anonymize_text). Mirrors the Phase 1 TestSC5_LogPrivacy regression.
    """

    async def test_no_real_pii_in_log_output_registry_path(
        self, redaction_service, empty_registry, seeded_faker, caplog,
    ):
        import logging as _logging

        text = (
            "Pak Bambang Sutrisno (email: bambang.s@example.com, "
            "telp +62-812-1234-5678) tinggal di Jakarta."
        )
        with caplog.at_level(_logging.DEBUG):
            result = await redaction_service.redact_text(
                text, registry=empty_registry,
            )
            await redaction_service.de_anonymize_text(
                result.anonymized_text, empty_registry,
            )

        forbidden = [
            "Bambang Sutrisno",
            "Bambang",
            "Sutrisno",
            "bambang.s@example.com",
            "+62-812-1234-5678",
            "Jakarta",
        ]
        for record in caplog.records:
            msg = record.getMessage()
            for value in forbidden:
                assert value not in msg, (
                    f"Real PII {value!r} leaked in log record: {msg!r} "
                    f"(logger={record.name}, level={record.levelname})"
                )
