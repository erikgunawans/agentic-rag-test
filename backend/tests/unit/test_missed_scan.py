"""Unit tests for missed_scan.scan_for_missed_pii (D-75/D-77/D-78).

One test class per Phase 4 decision invariant — mirrors the table-driven
shape of test_fuzzy_match.py and test_egress_filter.py.
"""
from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.redaction.missed_scan import (
    MissedEntity,
    MissedScanResponse,
    scan_for_missed_pii,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_registry():
    """Minimal registry stub (only feature used: pass-through to LLMProviderClient)."""
    reg = MagicMock()
    reg.thread_id = "test-thread"
    return reg


def _patch_settings(enabled: bool = True, entities: str = "PERSON,EMAIL_ADDRESS,PHONE_NUMBER"):
    """Return a context-manager that patches get_settings() for missed_scan."""
    settings = MagicMock()
    settings.pii_missed_scan_enabled = enabled
    settings.pii_redact_entities = entities
    return patch("app.services.redaction.missed_scan.get_settings", return_value=settings)


def _patch_llm(return_value: dict):
    """Patch LLMProviderClient.call to return a fixed dict (pre-Pydantic-parse)."""
    client = AsyncMock()
    client.call = AsyncMock(return_value=return_value)
    return patch("app.services.redaction.missed_scan.LLMProviderClient", return_value=client)


# ---------------------------------------------------------------------------
# D-75: gating
# ---------------------------------------------------------------------------

class TestD75_Gating:
    """D-75: scan is gated by pii_missed_scan_enabled. Returns (input, 0) when off."""

    @pytest.mark.asyncio
    async def test_disabled_returns_input_unchanged(self):
        with _patch_settings(enabled=False):
            text = "Acme Corp called Alice."
            result_text, count = await scan_for_missed_pii(text, _make_registry())
        assert result_text == text
        assert count == 0

    @pytest.mark.asyncio
    async def test_disabled_never_calls_llm(self):
        with _patch_settings(enabled=False):
            with patch("app.services.redaction.missed_scan.LLMProviderClient") as mock_cls:
                await scan_for_missed_pii("some text", _make_registry())
                mock_cls.assert_not_called()

    @pytest.mark.asyncio
    async def test_disabled_with_empty_entities_also_early_exits(self):
        with _patch_settings(enabled=True, entities=""):
            text = "Some text with Alice here."
            result_text, count = await scan_for_missed_pii(text, _make_registry())
        assert result_text == text
        assert count == 0


# ---------------------------------------------------------------------------
# D-77: schema validation, invalid-type drop, valid-type replace
# ---------------------------------------------------------------------------

class TestD77_SchemaAndReplace:
    """D-77: server validates type ∈ pii_redact_entities; invalid types dropped silently."""

    @pytest.mark.asyncio
    async def test_valid_entity_replaced(self):
        llm_response = {"entities": [{"type": "PERSON", "text": "Alice"}]}
        with _patch_settings(), _patch_llm(llm_response):
            text = "Hello Alice, how are you?"
            result_text, count = await scan_for_missed_pii(text, _make_registry())
        assert "[PERSON]" in result_text
        assert "Alice" not in result_text
        assert count == 1

    @pytest.mark.asyncio
    async def test_invalid_type_dropped_silently(self):
        llm_response = {"entities": [{"type": "BOGUS_TYPE", "text": "Alice"}]}
        with _patch_settings(), _patch_llm(llm_response):
            text = "Hello Alice."
            result_text, count = await scan_for_missed_pii(text, _make_registry())
        assert result_text == text  # unchanged — type not in whitelist
        assert count == 0

    @pytest.mark.asyncio
    async def test_mixed_valid_and_invalid_types(self):
        llm_response = {
            "entities": [
                {"type": "PERSON", "text": "Alice"},
                {"type": "MADE_UP", "text": "Wonderland"},
            ]
        }
        with _patch_settings(), _patch_llm(llm_response):
            text = "Alice went to Wonderland."
            result_text, count = await scan_for_missed_pii(text, _make_registry())
        assert "[PERSON]" in result_text
        assert "Alice" not in result_text
        assert "Wonderland" in result_text  # MADE_UP dropped → unchanged
        assert count == 1

    @pytest.mark.asyncio
    async def test_multiple_occurrences_replaced_by_subn(self):
        llm_response = {"entities": [{"type": "PERSON", "text": "Bob"}]}
        with _patch_settings(), _patch_llm(llm_response):
            text = "Bob and Bob met Bob."
            result_text, count = await scan_for_missed_pii(text, _make_registry())
        assert "Bob" not in result_text
        assert result_text.count("[PERSON]") == 3
        assert count == 3

    @pytest.mark.asyncio
    async def test_empty_entities_list_returns_unchanged(self):
        llm_response = {"entities": []}
        with _patch_settings(), _patch_llm(llm_response):
            text = "No PII here."
            result_text, count = await scan_for_missed_pii(text, _make_registry())
        assert result_text == text
        assert count == 0

    @pytest.mark.asyncio
    async def test_pydantic_validates_missing_type_field(self):
        """LLM returns entity missing 'type' → ValidationError → soft-fail."""
        llm_response = {"entities": [{"text": "Alice"}]}  # missing 'type'
        with _patch_settings(), _patch_llm(llm_response):
            text = "Hello Alice."
            result_text, count = await scan_for_missed_pii(text, _make_registry())
        assert result_text == text
        assert count == 0


# ---------------------------------------------------------------------------
# D-78: soft-fail + B4 log privacy
# ---------------------------------------------------------------------------

class TestD78_SoftFail:
    """D-78: on any provider failure → (input, 0); only error_class in logs."""

    @pytest.mark.asyncio
    async def test_timeout_error_returns_unchanged(self):
        with _patch_settings():
            with patch("app.services.redaction.missed_scan.LLMProviderClient") as mock_cls:
                mock_instance = AsyncMock()
                mock_instance.call.side_effect = TimeoutError("provider timeout")
                mock_cls.return_value = mock_instance
                text = "Alice is here."
                result_text, count = await scan_for_missed_pii(text, _make_registry())
        assert result_text == text
        assert count == 0

    @pytest.mark.asyncio
    async def test_generic_exception_returns_unchanged(self):
        with _patch_settings():
            with patch("app.services.redaction.missed_scan.LLMProviderClient") as mock_cls:
                mock_instance = AsyncMock()
                mock_instance.call.side_effect = RuntimeError("connection refused")
                mock_cls.return_value = mock_instance
                text = "Bob 555-1234."
                result_text, count = await scan_for_missed_pii(text, _make_registry())
        assert result_text == text
        assert count == 0

    @pytest.mark.asyncio
    async def test_soft_fail_log_contains_no_pii(self, caplog):
        """B4 invariant: log records on failure must not contain raw entity text."""
        with _patch_settings():
            with patch("app.services.redaction.missed_scan.LLMProviderClient") as mock_cls:
                mock_instance = AsyncMock()
                mock_instance.call.side_effect = RuntimeError("network error")
                mock_cls.return_value = mock_instance
                with caplog.at_level(logging.WARNING, logger="app.services.redaction.missed_scan"):
                    await scan_for_missed_pii("Alice Smith 555-0000.", _make_registry())
        full_log = " ".join(r.message for r in caplog.records)
        for raw_value in ("Alice", "Smith", "555-0000"):
            assert raw_value not in full_log, f"B4 violation: '{raw_value}' in logs"
        # error_class should be present
        assert "RuntimeError" in full_log or "error_class" in full_log

    @pytest.mark.asyncio
    async def test_egress_blocked_returns_unchanged(self):
        from app.services.llm_provider import _EgressBlocked
        with _patch_settings():
            with patch("app.services.redaction.missed_scan.LLMProviderClient") as mock_cls:
                mock_instance = AsyncMock()
                mock_instance.call.side_effect = _EgressBlocked("raw PII detected")
                mock_cls.return_value = mock_instance
                text = "Carol 555-9999."
                result_text, count = await scan_for_missed_pii(text, _make_registry())
        assert result_text == text
        assert count == 0
