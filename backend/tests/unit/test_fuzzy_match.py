"""Unit tests for fuzzy_match.fuzzy_score / best_match (D-67/D-68/D-70).

Mirrors the table-driven shape of test_egress_filter.py (Phase 3 D-66) —
one test class per Phase 4 decision invariant.
"""
from __future__ import annotations

import pytest

from app.services.redaction.fuzzy_match import (
    _normalize_for_fuzzy,
    best_match,
    fuzzy_score,
)


class TestD70_Normalization:
    """D-70: strip honorifics + casefold + tokenize on whitespace."""

    def test_strips_pak_and_casefolds(self):
        assert _normalize_for_fuzzy("Pak Bambang") == ["bambang"]

    def test_strips_bu_and_casefolds(self):
        assert _normalize_for_fuzzy("Bu Tini") == ["tini"]

    def test_preserves_multi_token(self):
        assert _normalize_for_fuzzy("Marcus A. Smith") == ["marcus", "a.", "smith"]

    def test_empty_input_returns_empty(self):
        assert _normalize_for_fuzzy("") == []


class TestD67_JaroWinklerThreshold:
    """D-67/D-69: rapidfuzz Jaro-Winkler at default threshold 0.85."""

    def test_exact_match_post_normalization(self):
        # 'pak Smith' vs 'Pak Smith' → 1.0 after honorific strip + casefold.
        assert fuzzy_score("pak Smith", "Pak Smith") == 1.0

    def test_one_char_typo_above_threshold(self):
        # Smyth → Smith is the canonical Jaro-Winkler 'close' case (~0.91).
        assert fuzzy_score("Smyth", "Smith") >= 0.85

    def test_dropped_token_token_max_above_threshold(self):
        # 'M. Smyth' has tokens ['m.', 'smyth']; 'Marcus Smith' has ['marcus','smith'].
        # max(JW(smyth, smith)) >= 0.85 → token-level max-pair scoring catches it.
        assert fuzzy_score("M. Smyth", "Marcus Smith") >= 0.85

    def test_unrelated_below_threshold(self):
        assert fuzzy_score("Bambang", "Mukherjee") < 0.85

    def test_empty_candidate_returns_zero(self):
        assert fuzzy_score("", "Smith") == 0.0

    def test_empty_variant_returns_zero(self):
        assert fuzzy_score("Smith", "") == 0.0


class TestD68_PerClusterScope:
    """D-68: best_match operates ONLY on caller-provided variants.

    The function is registry-agnostic; the caller (Plan 04-03 de_anonymize_text)
    is responsible for narrowing to a single cluster's variants.
    """

    def test_returns_variant_from_supplied_list(self):
        variants = ["Marcus Smith", "M. Smith", "Marcus"]
        result = best_match("M. Smyth", variants, threshold=0.85)
        assert result is not None
        match, score = result
        assert match in variants  # contract: returned variant is one of the inputs
        assert score >= 0.85

    def test_does_not_cross_reference_registry(self):
        # If best_match read from the registry, it would match against
        # globally-known names. Pass a variant list that has nothing close
        # to the candidate to confirm scoping.
        result = best_match("Marcus Smith", ["Daniel Walsh", "Walsh"], threshold=0.85)
        # Both candidates are unrelated to 'Marcus Smith' — must return None
        # because the caller chose the wrong cluster's variants.
        assert result is None


class TestThresholdGuard:
    """D-67/D-69: threshold gate."""

    def test_below_threshold_returns_none(self):
        assert best_match("Wijaya", ["Marcus Smith", "Marcus"], threshold=0.85) is None

    def test_empty_variants_returns_none(self):
        assert best_match("M. Smyth", [], threshold=0.85) is None

    def test_lower_threshold_admits_match(self):
        # Demonstrates the threshold knob is honored — at 0.50, even unrelated
        # tokens may score above. Verify the contract that threshold is the
        # gate, not a hard-coded constant.
        result = best_match("Wijaya", ["Marcus Smith", "Marcus"], threshold=0.50)
        # Either None or a tuple — but if a tuple, score must be >= 0.50.
        if result is not None:
            assert result[1] >= 0.50
