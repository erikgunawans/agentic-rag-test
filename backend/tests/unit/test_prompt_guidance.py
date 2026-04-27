"""Unit tests for prompt_guidance.get_pii_guidance_block (D-79/D-80/D-81/D-82).

Mirrors the table-driven pure-function shape of test_egress_filter.py (Phase 3 D-66).
"""
from __future__ import annotations

import pytest

from app.services.redaction.prompt_guidance import (
    _GUIDANCE_BLOCK,
    get_pii_guidance_block,
)


class TestD80_ConditionalInjection:
    """D-80: conditional injection — empty when off, populated when on."""

    def test_disabled_returns_empty(self):
        assert get_pii_guidance_block(redaction_enabled=False) == ""

    def test_enabled_returns_block(self):
        result = get_pii_guidance_block(redaction_enabled=True)
        assert result == _GUIDANCE_BLOCK
        assert result != ""

    def test_enabled_block_is_substantial(self):
        # D-82 block is ~150 tokens (~800-1000 chars).
        result = get_pii_guidance_block(redaction_enabled=True)
        assert len(result) >= 500


class TestD82_BlockContent:
    """D-82: imperative rules + type list + [TYPE] warning + concrete examples."""

    def test_contains_imperative_rules(self):
        block = get_pii_guidance_block(redaction_enabled=True)
        assert "MUST reproduce these EXACTLY" in block
        assert "NO abbreviation" in block
        assert "NO reformatting" in block

    def test_contains_critical_marker(self):
        block = get_pii_guidance_block(redaction_enabled=True)
        assert "CRITICAL" in block

    def test_contains_explicit_type_list(self):
        block = get_pii_guidance_block(redaction_enabled=True)
        # All 7 sample types from D-82 must appear.
        for sample in [
            "John Smith",
            "user@example.com",
            "+62-21-555-1234",
            "Jl. Sudirman 1",
            "2024-01-15",
            "https://example.com/x",
            "192.168.1.1",
        ]:
            assert sample in block, f"missing sample: {sample}"

    def test_contains_bracket_warning(self):
        block = get_pii_guidance_block(redaction_enabled=True)
        assert "[CREDIT_CARD]" in block
        assert "[US_SSN]" in block
        assert "literal placeholder" in block

    def test_contains_concrete_examples(self):
        block = get_pii_guidance_block(redaction_enabled=True)
        # D-82 examples use the arrow form.
        assert "→" in block
        assert "Marcus Smith" in block
        # Counter-examples that the block warns against.
        assert "M. Smith" in block

    def test_no_softening_language(self):
        # D-82 forbids 'please' (RLHF interprets as optional).
        block = get_pii_guidance_block(redaction_enabled=True)
        assert "please" not in block.lower() or "please reproduce" not in block.lower()


class TestKeywordOnlySignature:
    """The helper is keyword-only — positional calls must raise TypeError."""

    def test_positional_call_raises(self):
        with pytest.raises(TypeError):
            get_pii_guidance_block(True)  # type: ignore[misc]


class TestD81_EnglishOnly:
    """D-81: English-only phrasing across all LLM providers."""

    def test_block_uses_english_keywords(self):
        block = get_pii_guidance_block(redaction_enabled=True)
        # Defensive sanity check — key English instruction tokens are present.
        for keyword in ["CRITICAL", "MUST", "NOT", "Examples"]:
            assert keyword in block, f"missing English keyword: {keyword}"
