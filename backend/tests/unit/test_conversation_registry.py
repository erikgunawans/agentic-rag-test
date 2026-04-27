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

    async def test_contains_lower_hit_and_miss(self):
        from app.services.redaction.registry import (
            ConversationRegistry,
            EntityMapping,
        )

        reg = ConversationRegistry(
            thread_id="t-cl",
            rows=[
                EntityMapping(
                    real_value="Siti Rahayu",
                    real_value_lower="siti rahayu",
                    surrogate_value="Anna Smith",
                    entity_type="PERSON",
                ),
            ],
        )
        assert reg.contains_lower("siti rahayu") is True
        assert reg.contains_lower("unknown@example.com") is False

    async def test_contains_lower_is_already_casefolded(self):
        from app.services.redaction.registry import (
            ConversationRegistry,
            EntityMapping,
        )

        reg = ConversationRegistry(
            thread_id="t-cl2",
            rows=[
                EntityMapping(
                    real_value="Dewi Lestari",
                    real_value_lower="dewi lestari",
                    surrogate_value="Jane Doe",
                    entity_type="PERSON",
                ),
            ],
        )
        # contains_lower expects pre-casefolded input (callers casefold before calling)
        assert reg.contains_lower("dewi lestari") is True
        assert reg.contains_lower("Dewi Lestari") is False  # not casefolded by contains_lower

    async def test_forbidden_tokens_empty_registry(self):
        from app.services.redaction.registry import ConversationRegistry

        reg = ConversationRegistry(thread_id="t-empty", rows=[])
        assert reg.forbidden_tokens() == set()

    async def test_forbidden_tokens_cache_returns_same_object(self):
        from unittest.mock import patch

        from app.services.redaction.registry import (
            ConversationRegistry,
            EntityMapping,
        )

        reg = ConversationRegistry(
            thread_id="t-cache",
            rows=[
                EntityMapping(
                    real_value="Budi Santoso",
                    real_value_lower="budi santoso",
                    surrogate_value="Mark Brown",
                    entity_type="PERSON",
                ),
            ],
        )
        first = reg.forbidden_tokens()
        with patch(
            "app.services.redaction.registry.extract_name_tokens",
            side_effect=AssertionError("should not be called on cache hit"),
        ):
            second = reg.forbidden_tokens()
        assert first is second

    async def test_forbidden_tokens_cache_invalidated_on_person_upsert(self):
        from unittest.mock import AsyncMock, patch

        from app.services.redaction.registry import (
            ConversationRegistry,
            EntityMapping,
        )

        reg = ConversationRegistry(thread_id="t-inv", rows=[])
        _ = reg.forbidden_tokens()  # populate cache (empty set)
        assert reg._forbidden_tokens_cache is not None

        new_entry = EntityMapping(
            real_value="Agus Salim",
            real_value_lower="agus salim",
            surrogate_value="Tom White",
            entity_type="PERSON",
        )
        with patch.object(reg, "_by_lower", reg._by_lower), \
             patch("app.services.redaction.registry.get_supabase_client") as mock_client:
            mock_client.return_value.table.return_value.upsert.return_value.execute = AsyncMock(return_value=None)
            import asyncio

            async def fake_upsert():
                pass

            with patch("asyncio.to_thread", new=AsyncMock(return_value=None)):
                await reg.upsert_delta([new_entry])

        assert reg._forbidden_tokens_cache is None  # cache cleared after PERSON upsert

    async def test_upsert_delta_db_error_propagates(self):
        from unittest.mock import AsyncMock, patch

        from app.services.redaction.registry import (
            ConversationRegistry,
            EntityMapping,
        )

        reg = ConversationRegistry(thread_id="t-err", rows=[])
        entry = EntityMapping(
            real_value="Faisal Rahman",
            real_value_lower="faisal rahman",
            surrogate_value="Chris Black",
            entity_type="PERSON",
        )
        db_error = RuntimeError("DB write failed")
        with patch("asyncio.to_thread", side_effect=db_error):
            with pytest.raises(RuntimeError, match="DB write failed"):
                await reg.upsert_delta([entry])
        # In-memory state must NOT be updated after a DB failure (REG-04)
        assert reg.contains_lower("faisal rahman") is False
