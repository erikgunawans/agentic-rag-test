"""Fix D: filter_tool_output_by_registry — registry-only real→surrogate scan.

Verifies that web_search output containing registry-known real PII is masked
with the existing surrogate WITHOUT registering new entities. Tests use
ConversationRegistry directly (no mocks needed — the filter is a pure walk).
"""
from __future__ import annotations

import pytest

from app.services.redaction.registry import ConversationRegistry, EntityMapping
from app.services.redaction.tool_redaction import filter_tool_output_by_registry


def _registry(pairs: list[tuple[str, str, str]]) -> ConversationRegistry:
    """Build a registry from (real, surrogate, entity_type) tuples."""
    rows = [
        EntityMapping(
            real_value=real,
            real_value_lower=real.casefold(),
            surrogate_value=surrogate,
            entity_type=et,
        )
        for real, surrogate, et in pairs
    ]
    return ConversationRegistry(thread_id="test-thread", rows=rows)


# ---------------------------------------------------------------------------
# Core behaviour
# ---------------------------------------------------------------------------


class TestFilterRealValuesInOutput:
    def test_real_name_in_string_replaced_with_surrogate(self):
        reg = _registry([("Pak Budi", "Aurora Natsir", "PERSON")])
        result = filter_tool_output_by_registry(
            {"content": "Pak Budi signed the contract."},
            reg,
        )
        assert result == {"content": "Aurora Natsir signed the contract."}

    def test_public_figure_not_in_registry_untouched(self):
        reg = _registry([("Pak Budi", "Aurora Natsir", "PERSON")])
        result = filter_tool_output_by_registry(
            {"content": "Prabowo Subianto announced new policy."},
            reg,
        )
        assert result == {"content": "Prabowo Subianto announced new policy."}

    def test_surrogate_value_in_tavily_not_replaced(self):
        """Codex [P2] residual: surrogate appearing as real public figure in Tavily
        is NOT double-replaced by this filter (filter only replaces real→surrogate).
        The attribution error is still possible; this just confirms the filter
        doesn't make it worse by double-transforming."""
        reg = _registry([("Pak Budi", "Aurora Natsir", "PERSON")])
        # Tavily result contains "Aurora Natsir" as a real person (coincidental collision).
        result = filter_tool_output_by_registry(
            {"content": "Aurora Natsir won the award."},
            reg,
        )
        # The filter doesn't replace the surrogate — it only looks for real values.
        assert result == {"content": "Aurora Natsir won the award."}

    def test_empty_registry_output_unchanged(self):
        reg = _registry([])
        output = {"results": [{"title": "Test", "content": "Pak Budi"}]}
        assert filter_tool_output_by_registry(output, reg) == output

    def test_case_insensitive_match(self):
        reg = _registry([("Pak Budi", "Aurora Natsir", "PERSON")])
        result = filter_tool_output_by_registry(
            {"content": "PAK BUDI and pak budi and Pak Budi"},
            reg,
        )
        assert "Pak Budi" not in result["content"]
        assert "PAK BUDI" not in result["content"]
        assert "pak budi" not in result["content"]
        assert result["content"].count("Aurora Natsir") == 3

    def test_longest_real_value_wins_no_partial_overlap(self):
        """Longest match replaced first so "Pak Budi Sutomo" isn't partially stomped."""
        reg = _registry([
            ("Pak Budi Sutomo", "Aurora Natsir", "PERSON"),
            ("Pak Budi", "Dewi Rahayu", "PERSON"),
        ])
        result = filter_tool_output_by_registry(
            {"content": "Pak Budi Sutomo signed the deal."},
            reg,
        )
        # "Pak Budi Sutomo" (len=15) should be replaced as a unit, not "Pak Budi" (len=8) first.
        assert "Pak Budi" not in result["content"]
        assert "Sutomo" not in result["content"]


# ---------------------------------------------------------------------------
# Structural walking
# ---------------------------------------------------------------------------


class TestStructuralWalk:
    def test_nested_dict_with_list(self):
        reg = _registry([("budi@example.com", "surr@fake.com", "EMAIL_ADDRESS")])
        output = {
            "results": [
                {"title": "Doc A", "content": "From budi@example.com"},
                {"title": "Doc B", "content": "Unrelated content"},
            ]
        }
        result = filter_tool_output_by_registry(output, reg)
        assert result["results"][0]["content"] == "From surr@fake.com"
        assert result["results"][1]["content"] == "Unrelated content"

    def test_list_at_top_level(self):
        reg = _registry([("Pak Budi", "Aurora Natsir", "PERSON")])
        result = filter_tool_output_by_registry(["Pak Budi is here"], reg)
        assert result == ["Aurora Natsir is here"]

    def test_non_string_leaves_unchanged(self):
        reg = _registry([("Pak Budi", "Aurora Natsir", "PERSON")])
        output = {"count": 42, "active": True, "score": 0.9, "null_field": None}
        result = filter_tool_output_by_registry(output, reg)
        assert result == output

    def test_does_not_mutate_input(self):
        reg = _registry([("Pak Budi", "Aurora Natsir", "PERSON")])
        original = {"content": "Pak Budi here"}
        filter_tool_output_by_registry(original, reg)
        assert original == {"content": "Pak Budi here"}


# ---------------------------------------------------------------------------
# Skip rules
# ---------------------------------------------------------------------------


class TestSkipRules:
    def test_uuid_string_not_touched(self):
        reg = _registry([("Pak Budi", "Aurora Natsir", "PERSON")])
        uuid = "12345678-1234-1234-1234-123456789abc"
        result = filter_tool_output_by_registry({"id": uuid}, reg)
        assert result["id"] == uuid

    def test_short_string_not_touched(self):
        reg = _registry([("ab", "XY", "PERSON")])
        result = filter_tool_output_by_registry({"val": "ab"}, reg)
        assert result["val"] == "ab"


# ---------------------------------------------------------------------------
# No new entity registration (the key invariant)
# ---------------------------------------------------------------------------


class TestNoNewRegistration:
    def test_registry_size_unchanged_after_filter(self):
        """filter_tool_output_by_registry must NEVER add rows to the registry."""
        reg = _registry([("Pak Budi", "Aurora Natsir", "PERSON")])
        initial_count = len(reg.entries())

        filter_tool_output_by_registry(
            {"content": "Pak Budi and Prabowo Subianto discussed the contract."},
            reg,
        )
        # "Prabowo Subianto" is a new public figure — must NOT be registered.
        assert len(reg.entries()) == initial_count
