"""Phase 5 D-92 — RedactionService.redact_text_batch primitive unit tests.

Single-asyncio.Lock-acquisition batch redaction primitive used by Plan 05-04
chat.py event_generator() (D-93) and Plan 05-02 tool_redaction.py walker.

Contract (verbatim from PLAN must_haves):
- Off-mode (D-84): returns list(texts) verbatim — shallow copy, no NER, no lock,
  no DB I/O.
- Empty input: returns [] — fast path, zero NER, zero lock acquisition.
- Registry-required: raises ValueError when registry is None (no stateless
  mode for the batch primitive).
- On-mode: acquires the per-thread asyncio.Lock ONCE; runs
  _redact_text_with_registry per string in input order; appends anonymized
  strings to a results list; returns the list AFTER the async with block exits.
- Order preservation: len(results) == len(texts); results[i] is the redaction
  of texts[i]; no asyncio.gather, no sorting.
- Span attributes: batch_size, hard_redacted_total, latency_ms — counts only
  (B4 invariant).
- Decorator: @traced(name="redaction.redact_text_batch").
"""

from __future__ import annotations

import inspect
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.asyncio

# Plan 05-08: system_settings stubs replace the old config.py settings stubs.
_SYS_OFF = {"pii_redaction_enabled": False, "llm_provider": "local"}
_SYS_ON = {"pii_redaction_enabled": True, "llm_provider": "local"}


class TestD92Signature:
    """Static-shape checks for the new batch primitive."""

    async def test_method_exists_and_is_async(self):
        from app.services.redaction_service import RedactionService

        assert hasattr(RedactionService, "redact_text_batch")
        assert inspect.iscoroutinefunction(RedactionService.redact_text_batch)

    async def test_signature_has_texts_and_registry_params(self):
        from app.services.redaction_service import RedactionService

        sig = inspect.signature(RedactionService.redact_text_batch)
        # Self + texts + registry (positional). No kw-only oddity.
        assert "texts" in sig.parameters
        assert "registry" in sig.parameters
        # texts is positional-or-keyword (D-93 caller passes it positionally).
        assert (
            sig.parameters["texts"].kind
            == inspect.Parameter.POSITIONAL_OR_KEYWORD
        )

    async def test_return_annotation_is_list_of_str(self):
        from app.services.redaction_service import RedactionService

        sig = inspect.signature(RedactionService.redact_text_batch)
        rendered = str(sig.return_annotation)
        # Accept "list[str]" or "List[str]" stylistic variants.
        assert "list[str]" in rendered or "List[str]" in rendered


class TestD92OffMode:
    """D-84 alignment at the batch primitive — when redaction is off, return
    list(texts) verbatim with no side effects."""

    async def test_off_mode_returns_input_verbatim(self):
        from app.services.redaction_service import get_redaction_service

        svc = get_redaction_service()
        with patch("app.services.redaction_service.get_system_settings", return_value=_SYS_OFF):
            out = await svc.redact_text_batch(
                ["Pak Bambang", "Hubungi Rina di rina@example.com"], None
            )

        assert out == ["Pak Bambang", "Hubungi Rina di rina@example.com"]

    async def test_off_mode_returns_shallow_copy_not_same_list(self):
        """list(texts) — returned list is a fresh container, defensive
        against caller mutation of the original."""
        from app.services.redaction_service import get_redaction_service

        svc = get_redaction_service()
        original = ["a", "b", "c"]
        with patch("app.services.redaction_service.get_system_settings", return_value=_SYS_OFF):
            out = await svc.redact_text_batch(original, None)

        assert out == original
        # Shallow copy: equal-but-not-identical container.
        assert out is not original

    async def test_off_mode_does_not_invoke_detect_entities(self):
        from app.services.redaction.registry import ConversationRegistry
        from app.services.redaction_service import get_redaction_service

        svc = get_redaction_service()
        reg = ConversationRegistry(thread_id="t-off", rows=[])
        with patch(
            "app.services.redaction_service.get_system_settings", return_value=_SYS_OFF
        ), patch(
            "app.services.redaction_service.detect_entities"
        ) as detect:
            detect.side_effect = AssertionError(
                "off-mode batch must not invoke NER"
            )
            out = await svc.redact_text_batch(["x", "y"], reg)

        detect.assert_not_called()
        assert out == ["x", "y"]


class TestD92RegistryRequired:
    """On-mode: registry must be supplied — strict primitive."""

    async def test_on_mode_none_registry_raises_value_error(self):
        from app.services.redaction_service import get_redaction_service

        svc = get_redaction_service()
        with pytest.raises(ValueError) as exc_info:
            await svc.redact_text_batch(["something"], None)

        # Exact message text doesn't matter — but it should say "registry"
        # so the caller knows what was wrong.
        assert "registry" in str(exc_info.value).lower()
        assert "redact_text_batch" in str(exc_info.value)


class TestD92EmptyInputFastPath:
    """Empty list input → empty list output, zero NER, zero lock acquisition."""

    async def test_empty_list_returns_empty_list(self):
        from app.services.redaction.registry import ConversationRegistry
        from app.services.redaction_service import get_redaction_service

        svc = get_redaction_service()
        reg = ConversationRegistry(thread_id="t-empty", rows=[])
        out = await svc.redact_text_batch([], reg)
        assert out == []

    async def test_empty_list_does_not_acquire_lock(self):
        from app.services.redaction.registry import ConversationRegistry
        from app.services.redaction_service import (
            RedactionService,
            get_redaction_service,
        )

        svc = get_redaction_service()
        reg = ConversationRegistry(thread_id="t-empty-lock", rows=[])

        async def _spy_lock(self, thread_id):  # noqa: ARG001
            raise AssertionError(
                "empty fast path must not acquire the per-thread lock"
            )

        with patch.object(RedactionService, "_get_thread_lock", _spy_lock):
            out = await svc.redact_text_batch([], reg)

        assert out == []

    async def test_empty_list_does_not_invoke_detect_entities(self):
        from app.services.redaction.registry import ConversationRegistry
        from app.services.redaction_service import get_redaction_service

        svc = get_redaction_service()
        reg = ConversationRegistry(thread_id="t-empty-ner", rows=[])
        with patch(
            "app.services.redaction_service.detect_entities"
        ) as detect:
            detect.side_effect = AssertionError(
                "empty fast path must not invoke NER"
            )
            out = await svc.redact_text_batch([], reg)

        detect.assert_not_called()
        assert out == []


class TestD92SingleLockAcquisition:
    """Critical D-92 invariant: ONE asyncio.Lock acquisition spans the
    entire batch (not one per string)."""

    async def test_single_lock_acquisition_for_n_strings(self):
        """Stub _redact_text_with_registry to record acquire/release order
        relative to the lock; assert lock is acquired exactly once."""
        from app.services.redaction.registry import ConversationRegistry
        from app.services.redaction_service import (
            RedactionResult,
            RedactionService,
            get_redaction_service,
        )

        svc = get_redaction_service()
        reg = ConversationRegistry(
            thread_id="00000000-0000-0000-0000-000000000001", rows=[]
        )

        # Real lock — but we wrap acquire/release to count entries.
        original_get_lock = RedactionService._get_thread_lock
        acquire_count = 0

        async def _counting_get_lock(self, thread_id):
            nonlocal acquire_count
            real_lock = await original_get_lock(self, thread_id)
            real_acquire = real_lock.acquire

            async def counting_acquire(*a, **kw):
                nonlocal acquire_count
                acquire_count += 1
                return await real_acquire(*a, **kw)

            real_lock.acquire = counting_acquire
            return real_lock

        # Stub _redact_text_with_registry so we don't need to run real NER.
        async def _stub_inner(self, text, registry, _scan_rerun_done=False):
            return RedactionResult(
                anonymized_text=f"redacted({text})",
                entity_map={},
                hard_redacted_count=0,
                latency_ms=0.1,
            )

        with patch.object(
            RedactionService, "_get_thread_lock", _counting_get_lock
        ), patch.object(
            RedactionService, "_redact_text_with_registry", _stub_inner
        ):
            out = await svc.redact_text_batch(
                ["one", "two", "three", "four", "five"], reg
            )

        assert acquire_count == 1, (
            f"D-92: expected exactly ONE lock acquire, got {acquire_count}"
        )
        assert out == [
            "redacted(one)",
            "redacted(two)",
            "redacted(three)",
            "redacted(four)",
            "redacted(five)",
        ]


class TestD92OrderPreservation:
    """T-05-01-2 mitigation: results are returned in input order with
    len(results) == len(texts). D-93 history reassembly relies on this."""

    async def test_results_in_input_order(self):
        from app.services.redaction.registry import ConversationRegistry
        from app.services.redaction_service import (
            RedactionResult,
            RedactionService,
            get_redaction_service,
        )

        svc = get_redaction_service()
        reg = ConversationRegistry(thread_id="t-order", rows=[])

        # Stub inner to map text -> "S{text}" so order is verifiable.
        async def _stub_inner(self, text, registry, _scan_rerun_done=False):
            return RedactionResult(
                anonymized_text=f"S:{text}",
                entity_map={},
                hard_redacted_count=0,
                latency_ms=0.1,
            )

        with patch.object(
            RedactionService, "_redact_text_with_registry", _stub_inner
        ):
            out = await svc.redact_text_batch(
                ["alpha", "beta", "gamma", "delta"], reg
            )

        assert out == ["S:alpha", "S:beta", "S:gamma", "S:delta"]
        assert len(out) == 4

    async def test_off_mode_preserves_order_and_length(self):
        from app.services.redaction_service import get_redaction_service

        svc = get_redaction_service()
        inputs = [f"item-{i}" for i in range(10)]
        with patch("app.services.redaction_service.get_system_settings", return_value=_SYS_OFF):
            out = await svc.redact_text_batch(inputs, None)

        assert out == inputs  # off-mode is identity, must round-trip in order
        for i, o in enumerate(out):
            assert o == inputs[i]


class TestD92TracedDecorator:
    """@traced(name='redaction.redact_text_batch') — span name is the
    OBS audit-continuity contract."""

    async def test_method_is_decorated_with_traced(self):
        """The method name must be referenced by the @traced decorator with
        the expected span name. We can't easily introspect a decorator
        applied at definition time without a wrapping marker, so check
        the source text instead."""
        import pathlib

        src_path = pathlib.Path(
            "app/services/redaction_service.py"
        )
        src = src_path.read_text()
        # The decorator is on a separate line directly above the method.
        # `redact_text_batch` is mentioned exactly once for definition.
        assert (
            '@traced(name="redaction.redact_text_batch")' in src
        ), "missing @traced(name='redaction.redact_text_batch') decorator"
