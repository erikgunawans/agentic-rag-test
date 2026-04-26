"""Phase 2 ConversationRegistry pure-unit tests (no DB).

Exercises the in-memory primitives — lookup case-insensitivity, entries()
copy semantics, forbidden_tokens() per-PERSON filter (D-38). For DB-backed
behaviour (load, upsert_delta, race), see tests/api/test_redaction_registry.py.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


class TestConversationRegistryUnit:
    """Pure-unit coverage for ConversationRegistry — no DB access."""

    async def test_lookup_is_casefold_correct(self):
        from app.services.redaction.registry import (
            ConversationRegistry,
            EntityMapping,
        )

        reg = ConversationRegistry(
            thread_id="t-1",
            rows=[
                EntityMapping(
                    real_value="Bambang Sutrisno",
                    real_value_lower="bambang sutrisno",
                    surrogate_value="Andi Pratama",
                    entity_type="PERSON",
                ),
            ],
        )
        assert reg.lookup("bambang sutrisno") == "Andi Pratama"
        assert reg.lookup("BAMBANG SUTRISNO") == "Andi Pratama"
        assert reg.lookup("Bambang Sutrisno") == "Andi Pratama"
        assert reg.lookup("Margaret Thompson") is None

    async def test_entries_returns_a_copy(self):
        from app.services.redaction.registry import (
            ConversationRegistry,
            EntityMapping,
        )

        m = EntityMapping(
            real_value="x",
            real_value_lower="x",
            surrogate_value="y",
            entity_type="PERSON",
        )
        reg = ConversationRegistry(thread_id="t-1", rows=[m])
        entries = reg.entries()
        entries.append(m)  # mutate caller's copy
        assert len(reg.entries()) == 1, (
            "entries() must return a copy, not the internal list"
        )

    async def test_forbidden_tokens_only_persons(self):
        """D-38: per-PERSON only. Email / phone / URL contributions excluded."""
        from app.services.redaction.registry import (
            ConversationRegistry,
            EntityMapping,
        )

        rows = [
            EntityMapping(
                real_value="Bambang Sutrisno",
                real_value_lower="bambang sutrisno",
                surrogate_value="Andi Pratama",
                entity_type="PERSON",
            ),
            EntityMapping(
                real_value="bambang.s@example.com",
                real_value_lower="bambang.s@example.com",
                surrogate_value="someone@elsewhere.com",
                entity_type="EMAIL_ADDRESS",
            ),
        ]
        reg = ConversationRegistry(thread_id="t-1", rows=rows)
        tokens = reg.forbidden_tokens()
        assert "bambang" in tokens
        assert "sutrisno" in tokens
        # Email parts MUST NOT contribute (D-38).
        assert "example.com" not in tokens
        assert "bambang.s@example.com" not in tokens

    async def test_thread_id_property_immutable(self):
        from app.services.redaction.registry import ConversationRegistry

        reg = ConversationRegistry(thread_id="t-abc", rows=[])
        assert reg.thread_id == "t-abc"
        # property is read-only — assignment must raise
        with pytest.raises(AttributeError):
            reg.thread_id = "t-xyz"  # type: ignore
