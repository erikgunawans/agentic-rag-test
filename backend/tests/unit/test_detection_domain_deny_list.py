"""Domain-term deny list at the detection layer.

Verifies that domain-common terms are denied while real PII still passes
through the bucket filter unchanged.
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

    def test_jakarta_not_on_deny_list(self):
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


# ---------------------------------------------------------------------------
# REDACT-01 / Phase 16: runtime-extras configurability tests
# (extends this file per D-P16-05; do NOT create a new test file)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=False)
def _reset_deny_list_cache(monkeypatch):
    """Reset the module-level cache so each test starts with a cold cache.

    The cache lives at module scope in detection.py; tests below mutate it
    via monkeypatch.setattr so cleanup is automatic on test exit.
    """
    from app.services.redaction import detection as _detection

    monkeypatch.setattr(_detection, "_deny_list_cache", _detection._DENY_LIST_CASEFOLD)
    monkeypatch.setattr(_detection, "_deny_list_cache_ts", 0.0)
    monkeypatch.setattr(_detection, "_deny_list_cache_extras_key", "")
    return _detection


def test_runtime_extras_extend_deny_list(_reset_deny_list_cache, monkeypatch):
    """Runtime extras from system_settings union with the baked-in baseline."""
    detection = _reset_deny_list_cache

    def fake_get_system_settings():
        return {"pii_domain_deny_list_extra": "foobar, BAZ ,quux"}

    monkeypatch.setattr(
        "app.services.system_settings_service.get_system_settings",
        fake_get_system_settings,
    )

    # Force cache refresh
    monkeypatch.setattr(detection, "_deny_list_cache_ts", 0.0)

    assert detection._is_domain_term("foobar") is True
    assert detection._is_domain_term("baz") is True
    assert detection._is_domain_term("Quux") is True  # case-fold
    assert detection._is_domain_term("random_string_xyz") is False


@pytest.mark.parametrize(
    "term",
    [
        "Indonesian",
        "OJK",
        "UU PDP",
        "BJR",
        "KUHP",
        "KUHAP",
        "UU ITE",
        "UUPK",
        "Bahasa",
        "Mahkamah Agung",
        "BI",
        "KPK",
        "BPK",
        "Indonesia",
        "Indonesians",
        "English",
    ],
)
def test_baseline_unchanged_when_extras_empty(_reset_deny_list_cache, monkeypatch, term):
    """D-P16-02 zero-regression: empty extras yields byte-identical baseline.

    This is the bf1b7325 regression guard — the full set of domain terms that
    were on the baked-in deny list before Phase 16 must still be denied when
    pii_domain_deny_list_extra is the empty string default.
    """
    detection = _reset_deny_list_cache

    def fake_get_system_settings():
        return {"pii_domain_deny_list_extra": ""}

    monkeypatch.setattr(
        "app.services.system_settings_service.get_system_settings",
        fake_get_system_settings,
    )

    # Force cache refresh on first call
    monkeypatch.setattr(detection, "_deny_list_cache_ts", 0.0)

    assert detection._is_domain_term(term) is True, (
        f"{term!r} should still be denied with empty extras (baseline guarantee)"
    )


def test_real_pii_still_detected_under_both_modes(_reset_deny_list_cache, monkeypatch):
    """Real PII (PERSON spans) survive the deny-list filter in both modes.

    Sanity check that the deny list short-circuits ONLY domain terms before
    bucket dispatch — real PII like a phone number and a person's name still
    enter the entity list.
    """
    detection = _reset_deny_list_cache

    text = "Pak Budi mengajukan klaim. Telp +62 812-3456-7890."
    results = [
        _mk_result("PERSON", 0, 8),  # "Pak Budi"
        _mk_result("PHONE_NUMBER", 32, 50, score=0.9),  # the +62 number
    ]

    for extras in ["", "foobar"]:
        def fake_get_system_settings(extras_value=extras):
            return {"pii_domain_deny_list_extra": extras_value}

        monkeypatch.setattr(
            "app.services.system_settings_service.get_system_settings",
            fake_get_system_settings,
        )
        # Force cache refresh
        monkeypatch.setattr(detection, "_deny_list_cache_ts", 0.0)
        monkeypatch.setattr(detection, "_deny_list_cache_extras_key", "_force_rebuild_")

        with patch(
            "app.services.redaction.detection.get_analyzer"
        ) as mock_analyzer_factory:
            mock_analyzer_factory.return_value.analyze.return_value = results
            _masked, entities, _sentinels = detect_entities(text)

        assert len(entities) >= 1, (
            f"At least one Entity must survive when extras={extras!r}"
        )
        kept_text = [e.text for e in entities]
        assert "Indonesian" not in kept_text, (
            "Sanity: 'Indonesian' is on the baseline deny list and must not appear"
        )
