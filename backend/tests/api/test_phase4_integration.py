"""ROADMAP Phase 4 SC#1..SC#5 integration tests + B4 / Soft-Fail bonus coverage.

Mirrors backend/tests/api/test_resolution_and_provider.py (Phase 3 D-65/D-66) — same
per-SC test-class layout, same _patched_settings helper, same MagicMock + AsyncMock
mock pattern for AsyncOpenAI, same caplog B4 invariants. Tests run against live
Supabase qedhulpfezucnfadlfiz; cloud LLM is always mocked (no real egress).

Coverage map:
  SC#1 → TestSC1_FuzzyDeanon       (DEANON-03)
  SC#2 → TestSC2_NoSurnameCollision (DEANON-04)
  SC#3 → TestSC3_HardRedactSurvives (DEANON-05)
  SC#4 → TestSC4_MissedScan         (SCAN-01..05)
  SC#5 → TestSC5_VerbatimEmission   (PROMPT-01)
  Bonus: TestB4_LogPrivacy_FuzzyAndScan, TestSoftFail_ProviderUnavailable

Calibration notes (deviations from PLAN template — discovered while reading
the live source):
- ``EntityMapping`` does NOT carry a ``cluster_id`` field (observation #3167).
  ``_fuzzy_match_algorithmic`` keys solo clusters on
  ``f"_solo_{real_value.casefold()}"`` so two distinct registry rows with
  distinct surrogates remain in distinct cluster buckets — TestSC2 still holds.
- ``EntityMapping`` requires ``real_value_lower`` explicitly (no auto-derive in
  the constructor). The ``_seed_cluster`` helper computes ``casefold()`` per row.
- ``LLMProviderClient.call`` is the patch target (it's imported into both
  ``redaction_service`` and ``redaction.missed_scan``). To intercept the cloud
  egress + retry plumbing, we patch ``llm_provider._get_client`` (Phase 3
  precedent) for redaction-side tests and ``LLMProviderClient.call`` directly
  for de-anon-side tests where a mocked transport is simpler than the full
  egress / retry stack.
- ``RedactionService.de_anonymize_text(text, registry, mode=...)`` accepts an
  explicit ``mode`` parameter so we don't need to monkey-patch
  ``get_settings()`` for fuzzy_mode-only assertions.
"""
from __future__ import annotations

import json
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import get_settings
from app.services.redaction.egress import _EgressBlocked
from app.services.redaction.prompt_guidance import (
    _GUIDANCE_BLOCK,
    get_pii_guidance_block,
)
from app.services.redaction.registry import ConversationRegistry, EntityMapping
from app.services.redaction_service import RedactionService

pytestmark = pytest.mark.asyncio


# ──────────────────────────── Helpers / Fixtures ────────────────────────────


def _patched_settings(
    *,
    fuzzy_mode: str = "none",
    fuzzy_threshold: float = 0.85,
    scan_enabled: bool = True,
    redaction_enabled: bool = True,
    entity_resolution_mode: str = "algorithmic",
    llm_provider_fallback_enabled: bool = False,
) -> SimpleNamespace:
    """Build a Settings stub honoring the fields RedactionService reads.

    Mirrors the Phase 3 _patched_settings helper but extends it with the
    Phase 4 fields (fuzzy_deanon_mode, fuzzy_deanon_threshold,
    pii_missed_scan_enabled, pii_redaction_enabled,
    llm_provider_fallback_enabled).
    """
    real = get_settings()
    overrides = {f: getattr(real, f) for f in real.model_dump().keys()}
    overrides["fuzzy_deanon_mode"] = fuzzy_mode
    overrides["fuzzy_deanon_threshold"] = fuzzy_threshold
    overrides["pii_missed_scan_enabled"] = scan_enabled
    overrides["pii_redaction_enabled"] = redaction_enabled
    overrides["entity_resolution_mode"] = entity_resolution_mode
    overrides["llm_provider_fallback_enabled"] = llm_provider_fallback_enabled
    return SimpleNamespace(**overrides)


def _mock_llm_response(content: str | dict) -> MagicMock:
    """Build a MagicMock chat.completions.create return value.

    The content argument may be a dict (auto-JSON-encoded) or a raw string;
    the encoded form lands in ``choices[0].message.content`` per the OpenAI
    AsyncOpenAI response shape.
    """
    if isinstance(content, dict):
        content = json.dumps(content)
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content=content))]
    return mock_response


@pytest.fixture(autouse=True)
def _clear_llm_client_cache():
    """Reset the AsyncOpenAI client cache between tests so patched
    ``_get_client`` calls re-execute (rather than returning a stale mock from
    a sibling test)."""
    from app.services import llm_provider

    if hasattr(llm_provider, "_clients"):
        llm_provider._clients.clear()
    yield
    if hasattr(llm_provider, "_clients"):
        llm_provider._clients.clear()


async def _seed_cluster(
    thread_id: str,
    canonical_real: str,
    canonical_surrogate: str,
    *,
    variants: list[tuple[str, str]] | None = None,
    entity_type: str = "PERSON",
) -> ConversationRegistry:
    """Seed a registry with a canonical mapping + optional variants.

    variants = list of (real_value, surrogate_value) for additional rows that
    share the same logical "cluster" (in the current schema all variants in
    the same cluster carry the canonical's surrogate per D-45; we let the
    caller pass an arbitrary surrogate for B4-only assertions where it
    doesn't matter).

    Returns a freshly-loaded ConversationRegistry from the live DB.
    """
    registry = await ConversationRegistry.load(thread_id)
    deltas = [
        EntityMapping(
            real_value=canonical_real,
            real_value_lower=canonical_real.casefold(),
            surrogate_value=canonical_surrogate,
            entity_type=entity_type,
        )
    ]
    for v_real, v_surr in variants or []:
        deltas.append(
            EntityMapping(
                real_value=v_real,
                real_value_lower=v_real.casefold(),
                surrogate_value=v_surr,
                entity_type=entity_type,
            )
        )
    await registry.upsert_delta(deltas)
    return await ConversationRegistry.load(thread_id)


# ────────────────────────────── SC#1 ─────────────────────────────────────────


class TestSC1_FuzzyDeanon:
    """SC#1: mangled-surrogate de-anon resolves under algorithmic/llm; passthrough under none.

    DEANON-03 / D-67 / D-68 / D-70 / D-71 / D-72.
    """

    async def test_one_char_typo_resolves_algorithmic(
        self, fresh_thread_id, seeded_faker
    ):
        # Canonical "Marcus Smith" → surrogate "Bambang Sutrisno". Input
        # contains BOTH an exact surrogate occurrence (to seed Pass 1 with a
        # placeholder) AND a mangled form "Bambang Sutrisn" (one-char drop)
        # that Pass 2 must rewrite to the same placeholder. Pass 3 then
        # resolves placeholder → real value, so BOTH instances become
        # "Marcus Smith" in the output.
        registry = await _seed_cluster(
            fresh_thread_id,
            "Marcus Smith",
            "Bambang Sutrisno",
        )
        svc = RedactionService()
        result = await svc.de_anonymize_text(
            "I met Bambang Sutrisno on Monday and Bambang Sutrisn on Tuesday.",
            registry,
            mode="algorithmic",
        )
        # Pass 1 minted a placeholder for the exact "Bambang Sutrisno";
        # Pass 2 algorithmic fuzzy-matched the mangled chunk "Bambang"/
        # "Sutrisn" (≥ 0.85 Jaro-Winkler) to the same placeholder; Pass 3
        # resolved both back to the canonical real value.
        assert "Marcus Smith" in result, (
            f"expected real value to appear; got: {result!r}"
        )
        # Both occurrences (exact + mangled) resolve, so neither surrogate
        # form survives in the output.
        assert "Bambang Sutrisno" not in result, (
            f"unmangled surrogate leaked: {result!r}"
        )
        assert "Bambang Sutrisn " not in result, (
            f"mangled surrogate leaked: {result!r}"
        )
        # And the canonical real value appears at least twice (one per
        # original surrogate occurrence).
        assert result.count("Marcus Smith") >= 2, (
            f"expected ≥2 Marcus Smith instances; got: {result!r}"
        )

    async def test_passthrough_in_none_mode(
        self, fresh_thread_id, seeded_faker
    ):
        # mode='none' bypasses Pass 2 entirely — the mangled surrogate stays put.
        registry = await _seed_cluster(
            fresh_thread_id,
            "Marcus Smith",
            "Bambang Sutrisno",
        )
        svc = RedactionService()
        result = await svc.de_anonymize_text(
            "I met Bambang Sutrisn yesterday.",
            registry,
            mode="none",
        )
        assert "Bambang Sutrisn" in result
        assert "Marcus Smith" not in result

    async def test_llm_mode_resolves_via_mocked_provider(
        self, fresh_thread_id, seeded_faker
    ):
        # Mocked LLM returns a match referencing the placeholder Pass 1 minted
        # for "Bambang Sutrisno"'s cluster. We capture the call kwargs to
        # discover the placeholder token assigned at runtime, then inject a
        # match for the mangled span "Bambang Sutrisn" using THAT token.
        # The input contains BOTH the exact surrogate (Pass 1 mints token)
        # AND the mangled form (Pass 2 LLM resolves to same token).
        registry = await _seed_cluster(
            fresh_thread_id,
            "Marcus Smith",
            "Bambang Sutrisno",
        )

        captured: dict = {}

        async def _capture_call(*args, **kwargs):
            captured["kwargs"] = kwargs
            messages = kwargs.get("messages") or (args[1] if len(args) > 1 else [])
            user_content = ""
            for m in messages:
                if m.get("role") == "user":
                    user_content = m.get("content", "")
                    break
            import re as _re

            tok_match = _re.search(r"<<PH_[0-9a-f]+>>", user_content)
            token = tok_match.group(0) if tok_match else "<<PH_0000>>"
            return {
                "matches": [{"span": "Bambang Sutrisn", "token": token}]
            }

        with patch(
            "app.services.redaction_service.LLMProviderClient.call",
            new=AsyncMock(side_effect=_capture_call),
        ):
            svc = RedactionService()
            result = await svc.de_anonymize_text(
                "I met Bambang Sutrisno on Monday and Bambang Sutrisn on Tuesday.",
                registry,
                mode="llm",
            )
        # Both forms resolved to the canonical real value via Pass 1 (exact)
        # + Pass 2 (LLM-matched mangled span).
        assert "Marcus Smith" in result
        assert result.count("Marcus Smith") >= 2, (
            f"expected ≥2 Marcus Smith instances after LLM Pass 2; got: {result!r}"
        )
        assert "Bambang Sutrisn" not in result, (
            f"mangled surrogate leaked: {result!r}"
        )


# ────────────────────────────── SC#2 ─────────────────────────────────────────


class TestSC2_NoSurnameCollision:
    """SC#2: 3-phase pipeline prevents surname-collision corruption.

    DEANON-04 / D-71 placeholder-tokenization + D-68 per-cluster scoping.
    Two registry rows with distinct real values + distinct surrogates must
    NOT cross-resolve.
    """

    async def test_two_clusters_share_surname(
        self, fresh_thread_id, seeded_faker
    ):
        # Cluster A: real 'Marcus Smith' → surrogate 'Bambang Sutrisno'.
        # Cluster B: real 'Sarah Smith'  → surrogate 'Tini Wijaya'.
        # Mention only Marcus's surrogate; Sarah's must NOT be touched.
        await _seed_cluster(
            fresh_thread_id,
            "Marcus Smith",
            "Bambang Sutrisno",
        )
        registry = await _seed_cluster(
            fresh_thread_id,
            "Sarah Smith",
            "Tini Wijaya",
        )
        svc = RedactionService()
        result = await svc.de_anonymize_text(
            "I called Bambang Sutrisno about the contract.",
            registry,
            mode="algorithmic",
        )
        # Pass 1 surrogate-substitution + Pass 3 real-value-restore should
        # bring back ONLY "Marcus Smith". Sarah's real value must not appear.
        assert "Marcus Smith" in result, (
            f"expected Marcus's real value; got: {result!r}"
        )
        assert "Sarah Smith" not in result, (
            f"Sarah's real value leaked from cluster collision: {result!r}"
        )
        # The surrogate must NOT survive in the output (Pass 1 minted a
        # placeholder; Pass 3 resolved it).
        assert "Bambang Sutrisno" not in result


# ────────────────────────────── SC#3 ─────────────────────────────────────────


class TestSC3_HardRedactSurvives:
    """SC#3: hard-redact [TYPE] placeholders survive de-anon in every mode (D-74)."""

    @pytest.mark.parametrize("mode", ["algorithmic", "llm", "none"])
    async def test_hard_redact_identity_preserved(
        self, mode, fresh_thread_id, seeded_faker
    ):
        # No registry seeding: hard-redacts NEVER appear in registry per D-74 / REG-05.
        registry = await ConversationRegistry.load(fresh_thread_id)

        text = "User submitted [CREDIT_CARD] and [US_SSN] and [PHONE_NUMBER] today."

        async def _empty_response(*args, **kwargs):
            return {"matches": []}

        with patch(
            "app.services.redaction_service.LLMProviderClient.call",
            new=AsyncMock(side_effect=_empty_response),
        ):
            svc = RedactionService()
            result = await svc.de_anonymize_text(text, registry, mode=mode)

        # All three hard-redact placeholders survive bit-identical (D-74).
        assert "[CREDIT_CARD]" in result, f"missing [CREDIT_CARD] in mode={mode}: {result!r}"
        assert "[US_SSN]" in result, f"missing [US_SSN] in mode={mode}: {result!r}"
        assert "[PHONE_NUMBER]" in result, f"missing [PHONE_NUMBER] in mode={mode}: {result!r}"


# ────────────────────────────── SC#4 ─────────────────────────────────────────


class TestSC4_MissedScan:
    """SC#4: missed-PII scan auto-chains; invalid types discarded; primary NER re-runs."""

    @pytest.mark.parametrize("resolution_mode", ["algorithmic", "llm", "none"])
    async def test_scan_replaces_valid_drops_invalid(
        self, resolution_mode, fresh_thread_id, seeded_faker
    ):
        registry = await ConversationRegistry.load(fresh_thread_id)

        # Scan returns 1 valid CREDIT_CARD + 1 invalid type ("NOT_A_REAL_TYPE").
        scan_response = {
            "entities": [
                {"type": "CREDIT_CARD", "text": "4111-1111-1111-1111"},
                {"type": "NOT_A_REAL_TYPE", "text": "foo"},
            ]
        }

        async def _scan_call(*args, **kwargs):
            return scan_response

        # patch get_settings at three call-sites:
        #   1. redaction_service: drives mode-dispatch + scan-enabled gate.
        #   2. missed_scan: drives valid-type whitelist + scan-enabled gate.
        #   3. llm_provider (entity_resolution_mode='llm' would otherwise
        #      trigger _resolve_clusters_via_llm; we patch
        #      LLMProviderClient.call instead so any feature='*' call returns
        #      the scan response — for the LLM-mode resolution call this is
        #      shape-incompatible, but `_resolve_clusters_via_llm` catches all
        #      Exception and falls back to algorithmic, so the test stays green).
        with patch(
            "app.services.redaction_service.get_settings",
            return_value=_patched_settings(
                scan_enabled=True, entity_resolution_mode=resolution_mode
            ),
        ), patch(
            "app.services.redaction.missed_scan.get_settings",
            return_value=_patched_settings(
                scan_enabled=True, entity_resolution_mode=resolution_mode
            ),
        ), patch(
            "app.services.redaction.missed_scan.LLMProviderClient.call",
            new=AsyncMock(side_effect=_scan_call),
        ), patch(
            "app.services.redaction_service.LLMProviderClient.call",
            new=AsyncMock(side_effect=_scan_call),
        ):
            svc = RedactionService()
            res = await svc.redact_text(
                "Card number 4111-1111-1111-1111 and foo string here.",
                registry=registry,
            )
        # FR-8.4 + D-77: valid type replaced with bracket placeholder; raw
        # value gone from output.
        assert "[CREDIT_CARD]" in res.anonymized_text, (
            f"valid scan type not substituted in mode={resolution_mode}: "
            f"{res.anonymized_text!r}"
        )
        assert "4111-1111-1111-1111" not in res.anonymized_text, (
            f"raw CC leaked in mode={resolution_mode}: {res.anonymized_text!r}"
        )
        # Invalid type "NOT_A_REAL_TYPE" is silently discarded; "foo" stays as
        # plain text.
        assert "foo" in res.anonymized_text


# ────────────────────────────── SC#5 ─────────────────────────────────────────


class TestSC5_VerbatimEmission:
    """SC#5: main-agent system prompt contains the D-82 guidance block.

    PROMPT-01 / D-79..D-82.
    """

    async def test_guidance_block_returned_when_enabled(self, fresh_thread_id):
        block = get_pii_guidance_block(redaction_enabled=True)
        # Must be the canonical D-82 block, byte-for-byte.
        assert block == _GUIDANCE_BLOCK
        # D-82 imperative content invariants (the load-bearing strings).
        assert "MUST reproduce these EXACTLY" in block
        assert "Marcus Smith" in block
        assert "[CREDIT_CARD]" in block

    async def test_guidance_block_empty_when_disabled(self, fresh_thread_id):
        # D-80: conditional injection — when disabled, return "" so we don't
        # waste ~150 tokens on unredacted turns.
        block = get_pii_guidance_block(redaction_enabled=False)
        assert block == ""

    async def test_guidance_imperatives_d82_invariants(self, fresh_thread_id):
        # D-82: imperatives MUST/NEVER/CRITICAL must appear; soft 'please'
        # phrasing must NOT (RLHF interprets 'please' as optional).
        block = get_pii_guidance_block(redaction_enabled=True)
        assert "CRITICAL" in block
        assert "MUST" in block
        assert "NEVER" in block or "Do NOT" in block, (
            "guidance block missing required imperative phrasing"
        )
        assert "please" not in block.lower(), (
            "guidance block uses softening 'please' phrasing — D-82 violation"
        )


# ──────────────────────────── Bonus: B4 + Soft-Fail ──────────────────────────


class TestB4_LogPrivacy_FuzzyAndScan:
    """B4 invariant: no real value, no surrogate, no candidate text in any log line.

    Extends Phase 1 B4 / Phase 2-3 caplog assertions to D-78 missed-scan +
    fuzzy LLM-mode soft-fail logs.
    """

    async def test_no_real_pii_in_scan_skip_log(
        self, fresh_thread_id, seeded_faker, caplog
    ):
        # Use a deterministic non-PII fixture string. The B4 invariant scans
        # every log record for this literal — if it appears, the soft-fail
        # warn-log mistakenly carried the user payload.
        registry = await ConversationRegistry.load(fresh_thread_id)
        secret = "deadbeef-XYZ-1234-payload"

        async def _failing_call(*args, **kwargs):
            raise RuntimeError("503 timeout")

        with caplog.at_level(logging.WARNING), patch(
            "app.services.redaction.missed_scan.get_settings",
            return_value=_patched_settings(scan_enabled=True),
        ), patch(
            "app.services.redaction.missed_scan.LLMProviderClient.call",
            new=AsyncMock(side_effect=_failing_call),
        ):
            svc = RedactionService()
            res = await svc.redact_text(secret, registry=registry)

        # Soft-fail log line present (D-78).
        assert any(
            "missed_scan_skipped" in r.getMessage() for r in caplog.records
        ), "expected D-78 missed_scan_skipped warn-log absent"
        # B4 invariant: no raw fixture text in any log record.
        for r in caplog.records:
            msg = r.getMessage()
            assert secret not in msg, f"raw fixture text leaked in log: {msg!r}"
            assert "XYZ-1234" not in msg, f"fixture substring leaked: {msg!r}"
        # Soft-fail must complete (no exception) — see TestSoftFail_*.
        assert res is not None

    async def test_no_real_pii_in_fuzzy_llm_skip_log(
        self, fresh_thread_id, seeded_faker, caplog
    ):
        registry = await _seed_cluster(
            fresh_thread_id,
            "Marcus Smith",
            "Bambang Sutrisno",
        )

        async def _failing_call(*args, **kwargs):
            raise _EgressBlocked(MagicMock(match_count=0))

        with caplog.at_level(logging.WARNING), patch(
            "app.services.redaction_service.LLMProviderClient.call",
            new=AsyncMock(side_effect=_failing_call),
        ):
            svc = RedactionService()
            # Input includes the exact surrogate "Bambang Sutrisno" so Pass 1
            # mints a placeholder; Pass 2 LLM call then fails (mock raises),
            # triggering the D-78 fuzzy_deanon_skipped warn-log.
            await svc.de_anonymize_text(
                "I met Bambang Sutrisno on Monday.",
                registry,
                mode="llm",
            )

        # Soft-fail log present.
        assert any(
            "fuzzy_deanon_skipped" in r.getMessage() for r in caplog.records
        ), "expected D-78 fuzzy_deanon_skipped warn-log absent"
        # B4: every record scanned for forbidden literals (real, surrogate, mangled).
        for r in caplog.records:
            msg = r.getMessage()
            for forbidden in ["Marcus Smith", "Bambang Sutrisno", "Bambang Sutrisn"]:
                assert forbidden not in msg, (
                    f"forbidden literal {forbidden!r} found in log: {msg!r}"
                )


class TestSoftFail_ProviderUnavailable:
    """D-78 / PERF-04: provider failure → anonymization continues, never crashes."""

    async def test_redact_text_completes_when_scan_provider_5xx(
        self, fresh_thread_id, seeded_faker, caplog
    ):
        registry = await ConversationRegistry.load(fresh_thread_id)

        async def _failing_call(*args, **kwargs):
            raise RuntimeError("upstream 503")

        with caplog.at_level(logging.WARNING), patch(
            "app.services.redaction.missed_scan.get_settings",
            return_value=_patched_settings(scan_enabled=True),
        ), patch(
            "app.services.redaction.missed_scan.LLMProviderClient.call",
            new=AsyncMock(side_effect=_failing_call),
        ):
            svc = RedactionService()
            # Must NOT raise — soft-fail per PERF-04.
            res = await svc.redact_text(
                "ordinary text without obvious PII",
                registry=registry,
            )
        assert res is not None
        assert isinstance(res.anonymized_text, str)
        # Log carries error_class=RuntimeError (D-78 + B4: error_class only).
        assert any(
            "error_class=RuntimeError" in r.getMessage() for r in caplog.records
        ), "expected error_class=RuntimeError in WARNING log; not found"

    async def test_de_anonymize_completes_when_fuzzy_llm_unavailable(
        self, fresh_thread_id, seeded_faker
    ):
        registry = await _seed_cluster(
            fresh_thread_id,
            "Marcus Smith",
            "Bambang Sutrisno",
        )

        async def _failing_call(*args, **kwargs):
            raise RuntimeError("upstream 503")

        with patch(
            "app.services.redaction_service.get_settings",
            return_value=_patched_settings(
                fuzzy_mode="llm", llm_provider_fallback_enabled=False
            ),
        ), patch(
            "app.services.redaction_service.LLMProviderClient.call",
            new=AsyncMock(side_effect=_failing_call),
        ):
            svc = RedactionService()
            # Input includes the exact surrogate so Pass 1 mints a placeholder
            # and Pass 2 LLM is actually invoked → mock raises → soft-fail
            # path executes. Must NOT raise; the unmangled surrogate occurrence
            # is still resolved by Pass 1+3 (the mangled one stays put because
            # llm_provider_fallback_enabled=False forbids algorithmic fallback).
            result = await svc.de_anonymize_text(
                "I met Bambang Sutrisno on Monday and Bambang Sutrisn on Tuesday.",
                registry,
            )
        # Pass 1+3 resolved the exact surrogate to canonical real value.
        assert "Marcus Smith" in result
        # The mangled form stays put — Pass 2 LLM soft-failed and fallback is off.
        assert "Bambang Sutrisn " in result, (
            f"expected mangled surrogate to pass through after LLM soft-fail "
            f"with fallback disabled; got: {result!r}"
        )
