"""Phase 5 D-84 service-layer early-return gate — pure-unit tests.

When `PII_REDACTION_ENABLED=false`, `RedactionService.redact_text` MUST return
an identity `RedactionResult` (input text unchanged, entity_map={}, counts/lat
zero) BEFORE acquiring `_get_thread_lock` or making any NER / DB call. This
covers SC#5's service-layer surface (defense-in-depth alongside Plan 05-04's
top-level branch in chat.py).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.asyncio


def _patched_settings(real_settings, **overrides):
    """Return a SimpleNamespace clone of `real_settings` with overrides
    applied, preserving every other field so downstream attribute access
    inside redact_text continues to work."""
    fields = {f: getattr(real_settings, f) for f in real_settings.model_dump().keys()}
    fields.update(overrides)
    return SimpleNamespace(**fields)


class TestD84ServiceLayerGate:
    """D-84: PII_REDACTION_ENABLED=false → identity RedactionResult, no
    side effects (no lock, no NER, no DB I/O)."""

    async def test_off_mode_stateless_path_returns_identity(self):
        """`redact_text(text)` with no registry returns identity in off-mode."""
        from app.config import get_settings as real_gs
        from app.services.redaction_service import get_redaction_service

        svc = get_redaction_service()
        with patch("app.services.redaction_service.get_settings") as gs:
            gs.return_value = _patched_settings(
                real_gs(), pii_redaction_enabled=False
            )
            result = await svc.redact_text("Pak Bambang Sutrisno called.")

        assert result.anonymized_text == "Pak Bambang Sutrisno called."
        assert result.entity_map == {}
        assert result.hard_redacted_count == 0
        assert result.latency_ms == 0.0

    async def test_off_mode_explicit_none_registry_returns_identity(self):
        """`redact_text(text, registry=None)` returns identity in off-mode."""
        from app.config import get_settings as real_gs
        from app.services.redaction_service import get_redaction_service

        svc = get_redaction_service()
        with patch("app.services.redaction_service.get_settings") as gs:
            gs.return_value = _patched_settings(
                real_gs(), pii_redaction_enabled=False
            )
            result = await svc.redact_text(
                "Email me at andi@example.com please.", registry=None
            )

        assert result.anonymized_text == "Email me at andi@example.com please."
        assert result.entity_map == {}
        assert result.hard_redacted_count == 0
        assert result.latency_ms == 0.0

    async def test_off_mode_with_registry_returns_identity_no_lock(self):
        """`redact_text(text, registry=<loaded>)` returns identity AND does not
        acquire the per-thread lock in off-mode (no `_get_thread_lock` call)."""
        from app.config import get_settings as real_gs
        from app.services.redaction.registry import ConversationRegistry
        from app.services.redaction_service import (
            RedactionService,
            get_redaction_service,
        )

        svc = get_redaction_service()
        reg = ConversationRegistry(
            thread_id="00000000-0000-0000-0000-000000000000", rows=[]
        )

        # Patch _get_thread_lock to record whether it was called. In off-mode
        # it MUST NOT be called.
        lock_calls: list[str] = []

        async def _spy_lock(self, thread_id):  # noqa: ARG001
            lock_calls.append(thread_id)
            raise AssertionError(
                "D-84: off-mode must NOT acquire the per-thread lock"
            )

        with patch("app.services.redaction_service.get_settings") as gs, patch.object(
            RedactionService, "_get_thread_lock", _spy_lock
        ):
            gs.return_value = _patched_settings(
                real_gs(), pii_redaction_enabled=False
            )
            result = await svc.redact_text(
                "Bambang called Andi about contract.", registry=reg
            )

        assert lock_calls == []  # belt-and-suspenders
        assert result.anonymized_text == "Bambang called Andi about contract."
        assert result.entity_map == {}
        assert result.hard_redacted_count == 0
        assert result.latency_ms == 0.0

    async def test_off_mode_does_not_invoke_detect_entities(self):
        """D-84: off-mode must short-circuit BEFORE the NER call."""
        from app.config import get_settings as real_gs
        from app.services.redaction_service import get_redaction_service

        svc = get_redaction_service()
        with patch(
            "app.services.redaction_service.get_settings"
        ) as gs, patch(
            "app.services.redaction_service.detect_entities"
        ) as detect:
            gs.return_value = _patched_settings(
                real_gs(), pii_redaction_enabled=False
            )
            detect.side_effect = AssertionError(
                "D-84: off-mode must NOT invoke detect_entities"
            )
            result = await svc.redact_text("Pak Bambang lives in Jakarta.")

        detect.assert_not_called()
        assert result.anonymized_text == "Pak Bambang lives in Jakarta."

    async def test_on_mode_stateless_path_unchanged(self):
        """When pii_redaction_enabled=True (default), stateless path keeps
        Phase 1 behavior — entity detected, surrogate produced (sanity check
        that the gate did NOT break the on-path)."""
        from app.services.redaction_service import get_redaction_service

        svc = get_redaction_service()
        # Default settings: pii_redaction_enabled=True.
        result = await svc.redact_text("Bambang Sutrisno called.")

        # On-path always sets a real (non-zero) latency — the off-mode short-circuit
        # uses latency_ms=0.0 as a deterministic identity marker. If this assertion
        # fails, the gate is firing when it shouldn't (reading enabled=False
        # somehow) — a regression on the default-True path.
        assert result.latency_ms > 0.0
