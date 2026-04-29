"""TDD tests for detect_entities() optional thread_id parameter (D-P6-15, OBS-02).

RED phase: these tests verify the NEW behavior before implementation.

Behavior specification:
  - Test 1: detect_entities("hello") (no thread_id) returns 3-tuple; debug log
    does NOT contain 'thread_id='.
  - Test 2: detect_entities("hello", thread_id="thread-xyz") returns 3-tuple;
    debug log DOES contain 'thread_id=thread-xyz'.
  - Test 3: detect_entities("hello", thread_id=None) is byte-identical to Test 1
    (None defaults to omitted field — log does NOT contain 'thread_id=').
"""
from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest

from app.services.redaction.detection import detect_entities


@pytest.fixture()
def _patched_analyzer():
    """Patch get_analyzer so tests don't need the spaCy model loaded."""
    with patch(
        "app.services.redaction.detection.get_analyzer"
    ) as mock_factory:
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.return_value = []
        mock_factory.return_value = mock_analyzer
        yield mock_factory


class TestDetectEntitiesThreadId:
    """D-P6-15: detect_entities() accepts optional thread_id kwarg (backward-compat)."""

    def test_no_thread_id_returns_3_tuple(self, _patched_analyzer):
        """Existing callers (no thread_id) still get a 3-tuple back."""
        result = detect_entities("hello world")
        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_with_thread_id_returns_3_tuple(self, _patched_analyzer):
        """New callers passing thread_id still get a 3-tuple back."""
        result = detect_entities("hello world", thread_id="thread-xyz")
        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_no_thread_id_log_has_no_thread_id_field(
        self, _patched_analyzer, caplog
    ):
        """When thread_id is omitted, 'thread_id=' must NOT appear in the debug log."""
        with caplog.at_level(logging.DEBUG, logger="app.services.redaction.detection"):
            detect_entities("hello world")
        log_text = " ".join(r.getMessage() for r in caplog.records)
        assert "thread_id=" not in log_text, (
            "Log must NOT include thread_id= when thread_id is not supplied"
        )

    def test_with_thread_id_log_has_thread_id_field(
        self, _patched_analyzer, caplog
    ):
        """When thread_id is supplied, 'thread_id=thread-xyz' must appear in debug log."""
        with caplog.at_level(logging.DEBUG, logger="app.services.redaction.detection"):
            detect_entities("hello world", thread_id="thread-xyz")
        log_text = " ".join(r.getMessage() for r in caplog.records)
        assert "thread_id=thread-xyz" in log_text, (
            "Log MUST include thread_id=<value> when thread_id is supplied"
        )

    def test_thread_id_none_log_has_no_thread_id_field(
        self, _patched_analyzer, caplog
    ):
        """thread_id=None is byte-identical to no argument — 'thread_id=' must NOT appear."""
        with caplog.at_level(logging.DEBUG, logger="app.services.redaction.detection"):
            detect_entities("hello world", thread_id=None)
        log_text = " ".join(r.getMessage() for r in caplog.records)
        assert "thread_id=" not in log_text, (
            "thread_id=None must produce the same log as no thread_id argument"
        )

    def test_backward_compat_no_positional_required(self, _patched_analyzer):
        """Existing calls WITHOUT thread_id must still work (backward-compat D-P6-15)."""
        # These are the existing positional call patterns from prior tests:
        masked, entities, sentinels = detect_entities("some input text")
        # All three return values should be the expected types
        assert isinstance(masked, str)
        assert isinstance(entities, list)
        assert isinstance(sentinels, dict)
