"""Phase 5 Plan 05-02 D-91/D-92: tests for the centralized walker module.

Covers:
  - de-anon Pass-1 longest-surrogate-first transform across recursive structure.
  - anon collect-then-batch leaf strategy with ONE redact_text_batch call.
  - UUID skip rule + len<3 skip rule at every leaf-string boundary.
  - dict / list / tuple recursion + tuple type preservation.
  - input immutability (no in-place mutation).
  - empty-leaves fast path skips the batch call.
  - depth limit guards against pathological recursion (no RecursionError).
  - both public functions are async + have @traced(name="redaction.<verb>") decorator.

These tests use MagicMock for the registry + redaction_service so the walker
is exercised in pure isolation (no NER, no DB, no spaCy model load).
"""

from __future__ import annotations

import inspect
import re
from unittest.mock import AsyncMock, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _entry(real: str, surrogate: str) -> MagicMock:
    """Build a fake EntityMapping with the two fields the walker reads."""
    m = MagicMock()
    m.real_value = real
    m.surrogate_value = surrogate
    return m


def _registry(entries: list[MagicMock]) -> MagicMock:
    reg = MagicMock()
    reg.entries.return_value = entries
    reg.thread_id = "test-thread"
    return reg


def _service_with_batch(side_effect=None) -> MagicMock:
    """Build a fake RedactionService whose redact_text_batch is an AsyncMock."""
    svc = MagicMock()
    if side_effect is None:
        async def _identity(texts, registry):
            return [f"ANON_{t}" for t in texts]
        side_effect = _identity
    svc.redact_text_batch = AsyncMock(side_effect=side_effect)
    return svc


# ---------------------------------------------------------------------------
# Module-level invariants
# ---------------------------------------------------------------------------

class TestModuleSurface:
    def test_module_exports_two_async_functions(self):
        from app.services.redaction.tool_redaction import (
            anonymize_tool_output,
            deanonymize_tool_args,
        )
        assert inspect.iscoroutinefunction(deanonymize_tool_args)
        assert inspect.iscoroutinefunction(anonymize_tool_output)

    def test_constants_are_present_and_correct(self):
        from app.services.redaction.tool_redaction import (
            _MAX_DEPTH,
            _MIN_LEN,
            _UUID_RE,
        )
        assert _MAX_DEPTH == 10
        assert _MIN_LEN == 3
        # UUID regex must be anchored
        assert _UUID_RE.fullmatch("550e8400-e29b-41d4-a716-446655440000") is not None
        assert _UUID_RE.fullmatch("not-a-uuid") is None
        assert (
            _UUID_RE.fullmatch("550e8400-e29b-41d4-a716-446655440000-extra") is None
        ), "regex must be fully anchored"
        # Uppercase hex is rejected (lowercase-only per plan)
        assert _UUID_RE.fullmatch("550E8400-E29B-41D4-A716-446655440000") is None

    def test_no_logger_imports_b4_invariant(self):
        """B4 invariant: walker module emits NO logger calls."""
        import pathlib
        src = pathlib.Path(
            "app/services/redaction/tool_redaction.py"
        ).read_text()
        # The literal string "logger." (a call) and `import logging` are forbidden.
        assert "import logging" not in src, "walker must not import logging"
        assert "logger." not in src, "walker must not call logger"
        assert "logging." not in src, "walker must not call logging directly"


# ---------------------------------------------------------------------------
# de-anon walker (Pass-1 lookup)
# ---------------------------------------------------------------------------

class TestDeanonymizeToolArgs:
    @pytest.mark.asyncio
    async def test_basic_pass1_replacement(self):
        from app.services.redaction.tool_redaction import deanonymize_tool_args

        reg = _registry([
            _entry(real="Bambang Sutrisno", surrogate="Aaron Thompson DDS"),
        ])
        svc = MagicMock()
        result = await deanonymize_tool_args(
            {"query": "Pak Aaron Thompson DDS sent email"}, reg, svc
        )
        assert result == {"query": "Pak Bambang Sutrisno sent email"}

    @pytest.mark.asyncio
    async def test_longest_surrogate_first(self):
        """When two surrogates overlap (e.g. 'Aaron Thompson DDS' contains
        'Aaron'), the longer one wins so we don't corrupt the longer match."""
        from app.services.redaction.tool_redaction import deanonymize_tool_args

        reg = _registry([
            _entry(real="Bambang Sutrisno", surrogate="Aaron Thompson DDS"),
            _entry(real="Andi", surrogate="Aaron"),
        ])
        svc = MagicMock()
        result = await deanonymize_tool_args(
            {"query": "Aaron Thompson DDS"}, reg, svc
        )
        # Without longest-first ordering, "Aaron" would match first and corrupt
        # the longer surrogate. The plan mirrors redaction_service.py:865-869.
        assert result == {"query": "Bambang Sutrisno"}

    @pytest.mark.asyncio
    async def test_uuid_skip_rule(self):
        from app.services.redaction.tool_redaction import deanonymize_tool_args

        reg = _registry([
            _entry(real="Bambang Sutrisno", surrogate="Aaron Thompson DDS"),
        ])
        svc = MagicMock()
        # Note: the UUID is one whole leaf-string; the entry surrogate would
        # NOT match it, but we still want to confirm the skip-rule path.
        result = await deanonymize_tool_args(
            {
                "doc_id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "Aaron Thompson DDS",
            },
            reg,
            svc,
        )
        assert result["doc_id"] == "550e8400-e29b-41d4-a716-446655440000"
        assert result["name"] == "Bambang Sutrisno"

    @pytest.mark.asyncio
    async def test_len_lt_3_skip_rule(self):
        from app.services.redaction.tool_redaction import deanonymize_tool_args

        reg = _registry([
            _entry(real="Bambang Sutrisno", surrogate="Aaron Thompson DDS"),
        ])
        svc = MagicMock()
        result = await deanonymize_tool_args(
            {"op": "eq", "name": "Aaron Thompson DDS"}, reg, svc
        )
        # "eq" is len 2 — short-circuit; "name" value is transformed.
        assert result["op"] == "eq"
        assert result["name"] == "Bambang Sutrisno"

    @pytest.mark.asyncio
    async def test_input_not_mutated(self):
        from app.services.redaction.tool_redaction import deanonymize_tool_args

        reg = _registry([
            _entry(real="Bambang Sutrisno", surrogate="Aaron Thompson DDS"),
        ])
        svc = MagicMock()
        original = {"query": "Pak Aaron Thompson DDS"}
        snapshot = dict(original)
        _ = await deanonymize_tool_args(original, reg, svc)
        assert original == snapshot, "input was mutated in place"

    @pytest.mark.asyncio
    async def test_recursive_dict_list_tuple(self):
        from app.services.redaction.tool_redaction import deanonymize_tool_args

        reg = _registry([
            _entry(real="Bambang Sutrisno", surrogate="Aaron Thompson DDS"),
        ])
        svc = MagicMock()
        result = await deanonymize_tool_args(
            {
                "list_of_strings": ["Aaron Thompson DDS", "no match here"],
                "tuple_inside": ("Aaron Thompson DDS", 42),
                "nested": {"deeper": ["Aaron Thompson DDS"]},
            },
            reg,
            svc,
        )
        assert result["list_of_strings"][0] == "Bambang Sutrisno"
        assert result["list_of_strings"][1] == "no match here"
        # Tuple type preservation
        assert isinstance(result["tuple_inside"], tuple)
        assert result["tuple_inside"] == ("Bambang Sutrisno", 42)
        assert result["nested"]["deeper"][0] == "Bambang Sutrisno"

    @pytest.mark.asyncio
    async def test_non_container_leaves_returned_identity(self):
        from app.services.redaction.tool_redaction import deanonymize_tool_args

        reg = _registry([])
        svc = MagicMock()
        result = await deanonymize_tool_args(
            {"int": 42, "float": 3.14, "bool": True, "none": None, "bytes": b"raw"},
            reg,
            svc,
        )
        assert result == {
            "int": 42,
            "float": 3.14,
            "bool": True,
            "none": None,
            "bytes": b"raw",
        }

    @pytest.mark.asyncio
    async def test_depth_limit_no_recursion_error(self):
        """Depth=15 nesting must NOT raise; past _MAX_DEPTH the leaf is identity."""
        from app.services.redaction.tool_redaction import deanonymize_tool_args

        reg = _registry([
            _entry(real="Bambang Sutrisno", surrogate="Aaron Thompson DDS"),
        ])
        svc = MagicMock()
        deep: dict = {"k": {}}
        cur = deep["k"]
        for _ in range(15):
            cur["nested"] = {}
            cur = cur["nested"]
        cur["leaf"] = "Aaron Thompson DDS"
        # Must not raise — depth limit returns identity past 10.
        _ = await deanonymize_tool_args(deep, reg, svc)

    @pytest.mark.asyncio
    async def test_empty_dict_returns_empty_dict(self):
        from app.services.redaction.tool_redaction import deanonymize_tool_args

        reg = _registry([])
        svc = MagicMock()
        result = await deanonymize_tool_args({}, reg, svc)
        assert result == {}


# ---------------------------------------------------------------------------
# anon walker (collect-then-batch via redact_text_batch)
# ---------------------------------------------------------------------------

class TestAnonymizeToolOutput:
    @pytest.mark.asyncio
    async def test_one_batch_call_for_recursive_structure(self):
        """D-92 invariant: regardless of structure, redact_text_batch is called
        EXACTLY ONCE with the flat list of all transformable leaves."""
        from app.services.redaction.tool_redaction import anonymize_tool_output

        reg = _registry([])
        collected_calls = []

        async def fake_batch(texts, registry):
            collected_calls.append(list(texts))
            return [f"ANON_{t}" for t in texts]

        svc = MagicMock()
        svc.redact_text_batch = AsyncMock(side_effect=fake_batch)

        out = await anonymize_tool_output(
            {
                "results": [
                    {"content": "Pak Bambang called", "id": "550e8400-e29b-41d4-a716-446655440000"},
                    {"content": "Bu Siti emailed"},
                ],
                "summary": "Found two records",
            },
            reg,
            svc,
        )
        assert len(collected_calls) == 1
        # Order doesn't matter for this test, but the set of leaves does.
        assert set(collected_calls[0]) == {
            "Pak Bambang called",
            "Bu Siti emailed",
            "Found two records",
        }
        # Re-zip preserved structure
        assert out["results"][0]["id"] == "550e8400-e29b-41d4-a716-446655440000"
        # All three transformable leaves are anonymized
        for leaf in ("Pak Bambang called", "Bu Siti emailed", "Found two records"):
            assert f"ANON_{leaf}" in str(out)

    @pytest.mark.asyncio
    async def test_uuid_skipped_from_batch(self):
        from app.services.redaction.tool_redaction import anonymize_tool_output

        reg = _registry([])
        collected_calls = []

        async def fake_batch(texts, registry):
            collected_calls.append(list(texts))
            return [f"ANON_{t}" for t in texts]

        svc = MagicMock()
        svc.redact_text_batch = AsyncMock(side_effect=fake_batch)
        out = await anonymize_tool_output(
            {"id": "550e8400-e29b-41d4-a716-446655440000", "content": "Hello"},
            reg,
            svc,
        )
        assert collected_calls[0] == ["Hello"]
        assert out["id"] == "550e8400-e29b-41d4-a716-446655440000"
        assert out["content"] == "ANON_Hello"

    @pytest.mark.asyncio
    async def test_short_strings_skipped(self):
        from app.services.redaction.tool_redaction import anonymize_tool_output

        reg = _registry([])
        collected_calls = []

        async def fake_batch(texts, registry):
            collected_calls.append(list(texts))
            return [f"ANON_{t}" for t in texts]

        svc = MagicMock()
        svc.redact_text_batch = AsyncMock(side_effect=fake_batch)
        out = await anonymize_tool_output(
            {"op": "eq", "value": "Pak Bambang"}, reg, svc
        )
        assert collected_calls[0] == ["Pak Bambang"]
        assert out["op"] == "eq"
        assert out["value"] == "ANON_Pak Bambang"

    @pytest.mark.asyncio
    async def test_empty_leaves_fast_path_skips_batch(self):
        from app.services.redaction.tool_redaction import anonymize_tool_output

        reg = _registry([])
        svc = MagicMock()
        svc.redact_text_batch = AsyncMock()
        out = await anonymize_tool_output(
            {"id": "550e8400-e29b-41d4-a716-446655440000", "count": 5}, reg, svc
        )
        assert svc.redact_text_batch.call_count == 0
        assert out == {"id": "550e8400-e29b-41d4-a716-446655440000", "count": 5}

    @pytest.mark.asyncio
    async def test_empty_input_returns_empty(self):
        from app.services.redaction.tool_redaction import anonymize_tool_output

        reg = _registry([])
        svc = MagicMock()
        svc.redact_text_batch = AsyncMock()
        assert await anonymize_tool_output({}, reg, svc) == {}
        assert await anonymize_tool_output([], reg, svc) == []
        assert svc.redact_text_batch.call_count == 0

    @pytest.mark.asyncio
    async def test_tuple_type_preservation(self):
        from app.services.redaction.tool_redaction import anonymize_tool_output

        reg = _registry([])
        svc = MagicMock()

        async def fake_batch(texts, registry):
            return [f"ANON_{t}" for t in texts]

        svc.redact_text_batch = AsyncMock(side_effect=fake_batch)
        out = await anonymize_tool_output(
            ("Pak Bambang called", 5, ("nested", "data")), reg, svc
        )
        assert isinstance(out, tuple)
        assert isinstance(out[2], tuple)
        assert out[1] == 5  # int identity

    @pytest.mark.asyncio
    async def test_input_not_mutated(self):
        from app.services.redaction.tool_redaction import anonymize_tool_output

        reg = _registry([])
        svc = MagicMock()

        async def fake_batch(texts, registry):
            return [f"ANON_{t}" for t in texts]

        svc.redact_text_batch = AsyncMock(side_effect=fake_batch)
        original = {"results": ["Pak Bambang called"]}
        snapshot = {"results": list(original["results"])}
        _ = await anonymize_tool_output(original, reg, svc)
        assert original == snapshot, "input was mutated in place"

    @pytest.mark.asyncio
    async def test_depth_limit_no_recursion_error(self):
        from app.services.redaction.tool_redaction import anonymize_tool_output

        reg = _registry([])
        svc = MagicMock()

        async def fake_batch(texts, registry):
            return [f"ANON_{t}" for t in texts]

        svc.redact_text_batch = AsyncMock(side_effect=fake_batch)
        deep: dict = {"k": {}}
        cur = deep["k"]
        for _ in range(20):
            cur["nested"] = {}
            cur = cur["nested"]
        cur["leaf"] = "Pak Bambang"
        # Must not raise.
        _ = await anonymize_tool_output(deep, reg, svc)

    @pytest.mark.asyncio
    async def test_marker_tuple_does_not_collide_with_real_tuple(self):
        """The internal marker tuple shape ('__PII_LEAF__', int) must not
        collide with a real tuple a user passes in. The walker's collect
        phase substitutes the marker for transformable strings in a SHADOW
        tree, so a literal tuple ('__PII_LEAF__', 0) at input must round-trip
        unchanged (its first element is len-12, will be transformed; the int
        is identity)."""
        from app.services.redaction.tool_redaction import anonymize_tool_output

        reg = _registry([])
        svc = MagicMock()

        async def fake_batch(texts, registry):
            return [f"ANON_{t}" for t in texts]

        svc.redact_text_batch = AsyncMock(side_effect=fake_batch)
        out = await anonymize_tool_output(("__PII_LEAF__", 0), reg, svc)
        # The string "__PII_LEAF__" is len 13, transformable → anonymized.
        assert isinstance(out, tuple)
        assert out[0] == "ANON___PII_LEAF__"
        assert out[1] == 0


# ---------------------------------------------------------------------------
# @traced decorator presence
# ---------------------------------------------------------------------------

class TestTracedDecorator:
    def test_deanonymize_decorated(self):
        import pathlib
        src = pathlib.Path(
            "app/services/redaction/tool_redaction.py"
        ).read_text()
        assert re.search(
            r'@traced\(name="redaction\.deanonymize_tool_args"\)\s*\nasync def deanonymize_tool_args',
            src,
        ), "deanonymize_tool_args missing @traced decorator with correct span name"

    def test_anonymize_decorated(self):
        import pathlib
        src = pathlib.Path(
            "app/services/redaction/tool_redaction.py"
        ).read_text()
        assert re.search(
            r'@traced\(name="redaction\.anonymize_tool_output"\)\s*\nasync def anonymize_tool_output',
            src,
        ), "anonymize_tool_output missing @traced decorator with correct span name"
