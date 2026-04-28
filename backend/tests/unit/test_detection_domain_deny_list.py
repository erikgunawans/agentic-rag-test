"""ADR-0008 Fix B: domain-term deny list at the detection layer.

Country adjectives, language names, and government regulatory acronyms
identify GROUPS, not individuals. Treating them as PII pollutes the
ConversationRegistry and trips the egress filter on legitimate platform
content (e.g., the LexCore system prompt mentions "Indonesian"). The
deny list is applied AFTER Presidio analysis but BEFORE the entity is
appended to the result list, so denied terms never enter the registry.

Cities (Jakarta, Surabaya, Bandung, ...) are deliberately EXCLUDED from
the deny list — they can appear in real personal addresses, where a
false negative is worse than a false positive on the bare city name.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.redaction.detection import (
    _DENY_LIST_CASEFOLD,
    _is_domain_term,
    detect_entities,
)


def _mk_result(entity_type: str, start: int, end: int, score: float = 0.85):
    """Build a Presidio-shaped RecognizerResult lookalike."""
    r = MagicMock()
    r.entity_type = entity_type
    r.start = start
    r.end = end
    r.score = score
    return r


# ---------------------------------------------------------------------------
# Pure helper: _is_domain_term
# ---------------------------------------------------------------------------


class TestIsDomainTerm:
    """Casefold + exact-match lookup against the deny list."""

    @pytest.mark.parametrize(
        "span",
        [
            "Indonesian",
            "INDONESIAN",
            "indonesian",
            "Indonesia",
            "indonesia",
            "Indonesians",
            "Bahasa",
            "bahasa indonesia",
            "Bahasa Indonesia",
            "OJK",
            "KPK",
            "BPK",
            "Mahkamah Agung",
            "UU PDP",
            "uu pdp",
            "BJR",
            "KUHP",
            "KUHAP",
            "UU ITE",
            "UUPK",
        ],
    )
    def test_recognized_domain_terms_are_denied(self, span: str):
        assert _is_domain_term(span) is True, f"{span!r} should be on the deny list"

    @pytest.mark.parametrize(
        "span",
        [
            "Pak Budi",
            "Budi Sutomo",
            "Jakarta",  # cities deliberately NOT on deny list
            "Surabaya",
            "Bandung",
            "Jl. Sudirman 10",
            "budi@example.com",
            "+62 812 3456 7890",
            "",
        ],
    )
    def test_non_domain_terms_pass_through(self, span: str):
        assert _is_domain_term(span) is False, f"{span!r} must NOT be denied"


# ---------------------------------------------------------------------------
# Integration: detect_entities applies the deny list
# ---------------------------------------------------------------------------


class TestDetectEntitiesAppliesDenyList:
    """The filter runs inside detect_entities, after Presidio, before bucket dispatch."""

    def test_indonesian_filtered_pak_budi_kept(self):
        """The canonical false-positive: 'Indonesian contract law on Pak Budi'.

        Presidio detects both 'Indonesian' (LOCATION) and 'Pak Budi' (PERSON).
        After the deny-list filter, only Pak Budi survives so only Pak Budi
        enters the registry.
        """
        text = "Indonesian contract law on Pak Budi"
        # offsets in the masked_text (apply_uuid_mask is a no-op here — no UUIDs).
        results = [
            _mk_result("LOCATION", 0, 10),  # "Indonesian"
            _mk_result("PERSON", 27, 35),  # "Pak Budi"
        ]
        with patch(
            "app.services.redaction.detection.get_analyzer"
        ) as mock_analyzer_factory:
            mock_analyzer = MagicMock()
            mock_analyzer.analyze.return_value = results
            mock_analyzer_factory.return_value = mock_analyzer

            _masked, entities, _sentinels = detect_entities(text)

        kept_types = [e.type for e in entities]
        kept_text = [e.text for e in entities]

        assert "LOCATION" not in kept_types, (
            "Indonesian must be denied (domain-common adjective)"
        )
        assert "PERSON" in kept_types, "Pak Budi must still be detected"
        assert "Pak Budi" in kept_text

    def test_ojk_filtered_real_person_kept(self):
        """Government acronyms are filtered; real PII still detected."""
        text = "OJK regulates Pak Budi"
        results = [
            _mk_result("ORGANIZATION", 0, 3),  # "OJK"
            _mk_result("PERSON", 14, 22),  # "Pak Budi"
        ]
        with patch(
            "app.services.redaction.detection.get_analyzer"
        ) as mock_analyzer_factory:
            mock_analyzer_factory.return_value.analyze.return_value = results
            _masked, entities, _sentinels = detect_entities(text)

        kept_text = [e.text for e in entities]
        assert "OJK" not in kept_text
        assert "Pak Budi" in kept_text

    def test_jakarta_NOT_on_deny_list(self):
        """Cities are deliberately excluded — they can appear in real addresses."""
        text = "Pak Budi tinggal di Jakarta"
        results = [
            _mk_result("PERSON", 0, 8),  # "Pak Budi"
            _mk_result("LOCATION", 20, 27),  # "Jakarta"
        ]
        with patch(
            "app.services.redaction.detection.get_analyzer"
        ) as mock_analyzer_factory:
            mock_analyzer_factory.return_value.analyze.return_value = results
            _masked, entities, _sentinels = detect_entities(text)

        kept_text = [e.text for e in entities]
        assert "Pak Budi" in kept_text
        assert "Jakarta" in kept_text, (
            "Jakarta must still be detected — cities are not on the deny list"
        )

    def test_deny_list_is_frozenset(self):
        """Constant should be a frozenset (immutable, fast lookup, casefolded)."""
        assert isinstance(_DENY_LIST_CASEFOLD, frozenset)
        # Every entry is already casefolded so lookups don't need to recompute.
        for entry in _DENY_LIST_CASEFOLD:
            assert entry == entry.casefold(), (
                f"deny-list entry {entry!r} must be pre-casefolded"
            )
