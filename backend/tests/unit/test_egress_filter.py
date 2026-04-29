"""D-66 egress filter exhaustive test matrix (PROVIDER-04, NFR-2).

These are PURE unit tests against the egress_filter() function. No DB, no
mocks of AsyncOpenAI — just inputs in, EgressResult out. The log-content
invariant (B4 / D-55) is asserted via caplog.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import pytest

from app.services.redaction.egress import (
    EgressResult,
    _EgressBlocked,
    _hash8,
    egress_filter,
)
from app.services.redaction.registry import ConversationRegistry, EntityMapping


# --- Stub registry for unit tests (no DB, no async). ---


@dataclass(frozen=True)
class _StubMapping:
    entity_type: str
    real_value: str


class _StubRegistry:
    """Minimal duck-typed stand-in for ConversationRegistry.

    Implements both entries() and canonicals() so it remains compatible
    with egress_filter after the Plan 05-07 D-48 gap-closure switch to
    canonicals(). For existing tests, mappings are treated as canonical
    (no variants); canonicals() returns the same set as entries().

    Phase 6 D-P6-16: thread_id attribute added so egress_filter trip log can
    read registry.thread_id without AttributeError.
    """

    thread_id: str = "stub-thread-id"

    def __init__(self, mappings):
        self._mappings = list(mappings)

    def entries(self):
        return self._mappings

    def canonicals(self):
        """Return mappings deduplicated by longest real_value per entity_type+value.

        For tests that pass pre-canonical mappings (no variants), this is a
        passthrough. For TestD48VariantCascade, the real ConversationRegistry
        is used so the invariant is exercised against actual canonicals() logic.
        """
        return self._mappings


# --- D-66 matrix. ---


class TestEgressFilter:
    """D-66 exhaustive unit matrix."""

    def test_exact_match_casefold_trips(self):
        """A registered value matching the payload (case-insensitive) trips."""
        reg = _StubRegistry([_StubMapping("PERSON", "John Doe")])
        result = egress_filter("Hello JOHN DOE!", reg, None)
        assert result.tripped is True
        assert result.match_count == 1
        assert "PERSON" in result.entity_types

    def test_word_boundary_johnson_does_not_trip_on_john(self):
        """Word boundary preservation — "Johnson" must NOT match registered "John"."""
        reg = _StubRegistry([_StubMapping("PERSON", "John")])
        result = egress_filter("Talked to Johnson today", reg, None)
        assert result.tripped is False
        assert result.match_count == 0

    def test_multi_word_value_trips_on_substring(self):
        """A multi-word registered value matches as a phrase substring."""
        reg = _StubRegistry([_StubMapping("PERSON", "Bambang Sutrisno")])
        result = egress_filter(
            "The contract was signed by bambang sutrisno yesterday.",
            reg,
            None,
        )
        assert result.tripped is True
        assert "PERSON" in result.entity_types

    def test_registry_only_path_no_provisional(self):
        """Only registry rows; no provisional set."""
        reg = _StubRegistry([_StubMapping("EMAIL_ADDRESS", "alice@example.com")])
        result = egress_filter(
            "Send an email to alice@example.com please.",
            reg,
            None,
        )
        assert result.tripped is True
        assert "EMAIL_ADDRESS" in result.entity_types

    def test_provisional_only_path_no_registry_rows(self):
        """No registry rows; only in-flight provisional set (D-56 first-turn case)."""
        reg = _StubRegistry([])
        provisional = {"Carla Wijaya": "Mock_Surrogate_Name_001"}
        result = egress_filter(
            "Hi Carla Wijaya, your invoice is ready.",
            reg,
            provisional,
        )
        assert result.tripped is True
        assert "PERSON" in result.entity_types

    def test_empty_inputs_no_trip(self):
        """Empty registry + empty provisional → no trip."""
        reg = _StubRegistry([])
        result = egress_filter("Some innocuous text.", reg, None)
        assert result.tripped is False
        assert result.match_count == 0
        assert result.entity_types == []
        assert result.match_hashes == []

    def test_empty_provisional_dict_no_trip(self):
        """An empty provisional dict (not None) is equivalent to None for filtering."""
        reg = _StubRegistry([])
        result = egress_filter("Some innocuous text.", reg, {})
        assert result.tripped is False
        assert result.match_count == 0

    def test_match_hashes_are_8char_sha256(self):
        """D-55: match_hashes are 8-char SHA-256 hashes; not raw values."""
        reg = _StubRegistry([_StubMapping("PERSON", "John Doe")])
        result = egress_filter("hello john doe", reg, None)
        assert result.tripped is True
        for h in result.match_hashes:
            assert isinstance(h, str)
            assert len(h) == 8
            int(h, 16)  # raises ValueError if not hex
        # The hash for "John Doe" should be in the result.
        assert _hash8("John Doe") in result.match_hashes

    def test_log_content_invariant_no_raw_values(self, caplog):
        """B4 / D-55: trip log MUST NOT contain raw value or first-N-chars of value."""
        reg = _StubRegistry([_StubMapping("PERSON", "John Doe")])
        with caplog.at_level(logging.WARNING, logger="app.services.redaction.egress"):
            egress_filter("hello john doe", reg, None)
        log_text = "\n".join(rec.getMessage() for rec in caplog.records)
        # The trip log should appear (only the WARNING-level line).
        assert "egress_filter_blocked" in log_text
        # The raw value MUST NOT appear (case-insensitive substring check).
        assert "john doe" not in log_text.lower()
        assert "John Doe" not in log_text
        # The 8-char hash MUST appear (forensic correlation).
        assert _hash8("John Doe") in log_text

    def test_log_content_no_warning_when_clean(self, caplog):
        """No WARNING line is emitted when the filter does not trip."""
        reg = _StubRegistry([_StubMapping("PERSON", "John Doe")])
        with caplog.at_level(logging.WARNING, logger="app.services.redaction.egress"):
            result = egress_filter("Hello world.", reg, None)
        assert result.tripped is False
        warning_records = [r for r in caplog.records if r.levelname == "WARNING"]
        assert warning_records == [], (
            "egress_filter must NOT emit a WARNING when no trip occurred"
        )

    def test_multiple_distinct_matches_all_counted(self):
        """Multiple distinct matches aggregate via match_count + entity_types + match_hashes."""
        reg = _StubRegistry(
            [
                _StubMapping("PERSON", "John Doe"),
                _StubMapping("EMAIL_ADDRESS", "john.doe@example.com"),
            ]
        )
        result = egress_filter(
            "John Doe sent an email from john.doe@example.com",
            reg,
            None,
        )
        assert result.tripped is True
        assert result.match_count == 2
        assert sorted(result.entity_types) == ["EMAIL_ADDRESS", "PERSON"]
        assert len(result.match_hashes) == 2

    def test_provisional_extends_registry_scope(self):
        """Both registry AND provisional contribute to the candidate set."""
        reg = _StubRegistry([_StubMapping("PERSON", "John Doe")])
        provisional = {"Carla Wijaya": "Mock_Surrogate_001"}
        # Payload contains BOTH; both should match.
        result = egress_filter(
            "John Doe and Carla Wijaya both attended.",
            reg,
            provisional,
        )
        assert result.tripped is True
        assert result.match_count == 2

    def test_egress_blocked_carries_result(self):
        """_EgressBlocked carries the EgressResult instance for caller inspection."""
        reg = _StubRegistry([_StubMapping("PERSON", "John Doe")])
        result = egress_filter("John Doe is here", reg, None)
        try:
            raise _EgressBlocked(result)
        except _EgressBlocked as exc:
            assert exc.result is result
            assert exc.result.tripped is True
            assert exc.result.match_count == 1

    def test_result_is_frozen(self):
        """EgressResult is a frozen dataclass — callers cannot mutate."""
        reg = _StubRegistry([_StubMapping("PERSON", "John Doe")])
        result = egress_filter("hello world", reg, None)
        assert isinstance(result, EgressResult)
        with pytest.raises((AttributeError, Exception)):
            result.tripped = True  # type: ignore[misc]

    def test_skips_empty_real_value(self):
        """A registry row with an empty real_value is skipped without raising."""
        reg = _StubRegistry(
            [
                _StubMapping("PERSON", ""),
                _StubMapping("PERSON", "John Doe"),
            ]
        )
        result = egress_filter("hello John Doe", reg, None)
        # Only the non-empty value should match.
        assert result.tripped is True
        assert result.match_count == 1


def _make_registry(*rows: tuple[str, str, str]) -> ConversationRegistry:
    """Helper: build a real ConversationRegistry from (real_value, surrogate, entity_type) tuples.

    Uses the real ConversationRegistry so canonicals() exercises actual invariant logic
    rather than the stub passthrough.
    """
    mappings = [
        EntityMapping(
            real_value=real_value,
            real_value_lower=real_value.casefold(),
            surrogate_value=surrogate,
            entity_type=entity_type,
        )
        for real_value, surrogate, entity_type in rows
    ]
    return ConversationRegistry(thread_id="test-thread", rows=mappings)


class TestD48VariantCascade:
    """D-48 variant cascade regression suite (Plan 05-07 gap-closure).

    Verifies that sub-surrogate variants (first-only / last-only) produced by
    D-48 clustering do NOT trip the egress filter on their own, while canonical
    real values still trip (privacy invariant preserved).

    Uses the real ConversationRegistry (not the stub) so that canonicals() is
    exercised against actual invariant logic.

    Scenario modeled: thread bf1b7325 from 2026-04-28 UAT where spaCy
    produced false-positive PERSON detections on legal terms ("Confidentiality
    Clause" → surrogate "Uda Hardiansyah, S.IP") and D-48 stored variants
    "Confidentiality" and "Clause" under the same surrogate. Subsequent
    anonymized assistant text containing the word "confidentiality" in normal
    prose caused egress to trip permanently after Turn 1.
    """

    def test_variant_only_match_does_not_trip(self):
        """D-48 variant appearing mid-sentence does NOT trip egress after gap-closure.

        Registry contains:
            canonical: "Confidentiality Clause" → "S1"
            variant:   "Confidentiality"        → "S1"  (D-48 first-word variant)
            variant:   "Clause"                 → "S1"  (D-48 last-word variant)

        Payload: anonymized assistant prose containing the standalone word
        "confidentiality" (lowercase, mid-sentence) — NOT the canonical phrase.

        Before fix: egress tripped on "Confidentiality" variant → EgressBlockedAbort.
        After fix:  canonical-only scan ignores variants → tripped is False.
        """
        reg = _make_registry(
            ("Confidentiality Clause", "S1", "PERSON"),
            ("Confidentiality", "S1", "PERSON"),
            ("Clause", "S1", "PERSON"),
        )
        # Payload resembles a real Turn 2 history message after batch anonymization:
        # the entity span "Confidentiality Clause" was replaced by surrogate "S1",
        # but the word "confidentiality" later in the sentence is plain prose.
        payload = (
            "6. **S1**: If necessary, include terms regarding confidentiality."
        )
        result = egress_filter(payload, reg, None)
        assert result.tripped is False, (
            f"Variant-only match must NOT trip egress. Got: {result}"
        )
        assert result.match_count == 0

    def test_canonical_leak_still_trips(self):
        """Privacy invariant: canonical real value leaking to payload still trips egress.

        Same registry as test_variant_only_match_does_not_trip. Payload now contains
        the CANONICAL phrase "confidentiality clause" (lowercase, mid-sentence) — this
        simulates a NER miss where the LLM response contained the full compound noun
        but spaCy failed to detect it as PERSON in context, so it passed through
        anonymization unreplaced.

        After gap-closure: canonical is STILL in the candidate set. Egress trips.
        """
        reg = _make_registry(
            ("Confidentiality Clause", "S1", "PERSON"),
            ("Confidentiality", "S1", "PERSON"),
            ("Clause", "S1", "PERSON"),
        )
        # Payload contains the full canonical phrase (e.g., NER miss — surrogate not applied).
        payload = (
            "Please review the confidentiality clause before proceeding."
        )
        result = egress_filter(payload, reg, None)
        assert result.tripped is True, (
            f"Canonical leak must still trip egress. Got: {result}"
        )
        assert result.match_count == 1

    def test_canonicals_picks_longest_real_value_per_surrogate(self):
        """Direct unit test of ConversationRegistry.canonicals() longest-wins selection.

        Registry contains three rows sharing surrogate "Aurora Natsir":
            "Ahmad Suryadi" (length 13) — canonical
            "Suryadi"       (length 7)  — D-48 last-name-only variant
            "Ahmad"         (length 5)  — D-48 first-name-only variant

        canonicals() must return exactly ONE entry with real_value == "Ahmad Suryadi".
        This proves the D-48 invariant: canonical is always longest; variants are
        derived by subtraction.
        """
        reg = _make_registry(
            ("Ahmad Suryadi", "Aurora Natsir", "PERSON"),
            ("Suryadi", "Aurora Natsir", "PERSON"),
            ("Ahmad", "Aurora Natsir", "PERSON"),
        )
        result = reg.canonicals()
        assert len(result) == 1, (
            f"canonicals() must return exactly 1 entry for 3 rows sharing 1 surrogate. Got: {result}"
        )
        assert result[0].real_value == "Ahmad Suryadi", (
            f"canonicals() must pick the longest real_value. Got: {result[0].real_value!r}"
        )
