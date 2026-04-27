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
    """

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
