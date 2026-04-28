"""Phase 5 Plan 05-03 — TDD RED tests for ``agent_service.classify_intent``.

These tests assert the new contract:

- Signature gains a NEW keyword-only ``registry: ConversationRegistry | None
  = None`` parameter (D-94 / D-96).
- When ``registry is not None`` and ``pii_redaction_enabled=True``, the
  function pre-flight-egress-filters the messages payload BEFORE the
  cloud LLM call.
- On egress trip: returns ``OrchestratorResult(agent='general',
  reasoning='egress_blocked')`` and emits a B4-compliant warning log
  ``egress_blocked event=egress_blocked feature=classify_intent
  entity_count=<int>`` (counts only — no payload, no real values, no
  surrogates).
- When ``registry is None`` (legacy callers): the egress wrapper is
  SKIPPED. Function behaves identically to Phase 0 baseline (SC#5
  invariant).
- When ``pii_redaction_enabled=False``: the egress wrapper is SKIPPED
  (D-83 off-mode global gate; SC#5 invariant).

These tests use stub registries / mocked openrouter clients — no DB, no
network. They sit in ``tests/unit/`` per the Wave 1 pattern set by
``test_redact_text_batch.py`` and ``test_redaction_service_d84_gate.py``.
"""
from __future__ import annotations

import inspect
import json
import logging
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.agents import OrchestratorResult
from app.services import agent_service
from app.services.agent_service import classify_intent


# ---------- Stub registry (no DB) ----------------------------------------


@dataclass(frozen=True)
class _StubMapping:
    entity_type: str
    real_value: str


class _StubRegistry:
    """Minimal duck-typed stand-in for ConversationRegistry."""

    def __init__(self, mappings=(), thread_id="00000000-0000-0000-0000-000000000000"):
        self._mappings = list(mappings)
        self.thread_id = thread_id

    def entries(self):
        return self._mappings

    def canonicals(self):
        return self._mappings


def _sys_settings_override(**overrides):
    """Returns a system_settings dict stub for patching agent_service.get_system_settings.

    Plan 05-08: pii_redaction_enabled now sourced from system_settings (DB-backed).
    """
    base = {"pii_redaction_enabled": True, "llm_provider": "local"}
    base.update(overrides)
    return base


# ---------- Test class ----------------------------------------------------


class TestClassifyIntentSignature:
    """D-94 / D-96 — keyword-only registry kwarg with default None."""

    def test_registry_param_is_keyword_only_with_default_none(self):
        sig = inspect.signature(classify_intent)
        params = sig.parameters
        assert "registry" in params, (
            f"registry param missing; params={list(params.keys())}"
        )
        assert params["registry"].kind == inspect.Parameter.KEYWORD_ONLY, (
            f"registry must be keyword-only, got {params['registry'].kind}"
        )
        assert params["registry"].default is None, (
            f"registry default must be None, got {params['registry'].default!r}"
        )

    def test_classify_intent_is_async(self):
        assert inspect.iscoroutinefunction(classify_intent)


class TestClassifyIntentBackwardCompat:
    """SC#5 — Phase 0 callers (no registry kwarg) still work."""

    @pytest.mark.asyncio
    async def test_no_registry_kwarg_skips_egress_calls_llm(self):
        """When ``registry is None`` the egress wrapper must be SKIPPED.

        The function behaves identically to Phase 0: builds messages,
        calls openrouter.complete_with_tools, parses JSON, returns
        OrchestratorResult.
        """
        fake_or = MagicMock()
        fake_or.complete_with_tools = AsyncMock(
            return_value={"content": '{"agent": "research", "reasoning": "doc query"}'}
        )

        # Patch egress_filter at the agent_service module to detect any leak.
        with patch.object(
            agent_service, "egress_filter", side_effect=AssertionError(
                "egress_filter must NOT be called when registry=None"
            )
        ):
            result = await classify_intent(
                "what's in my contracts?",
                [],
                fake_or,
                "gpt-4o-mini",
            )

        assert isinstance(result, OrchestratorResult)
        assert result.agent == "research"
        assert fake_or.complete_with_tools.call_count == 1


class TestClassifyIntentOffModeGlobal:
    """D-83 / SC#5 — pii_redaction_enabled=False short-circuits the egress wrapper."""

    @pytest.mark.asyncio
    async def test_off_mode_skips_egress_even_with_registry(self):
        fake_or = MagicMock()
        fake_or.complete_with_tools = AsyncMock(
            return_value={"content": '{"agent": "general", "reasoning": "off-mode"}'}
        )
        registry = _StubRegistry([_StubMapping("PERSON", "John Doe")])

        with patch.object(
            agent_service, "egress_filter", side_effect=AssertionError(
                "egress_filter must NOT be called when pii_redaction_enabled=False"
            )
        ), patch.object(
            agent_service, "get_system_settings",
            return_value=_sys_settings_override(pii_redaction_enabled=False),
        ):
            result = await classify_intent(
                "hi",
                [],
                fake_or,
                "gpt-4o-mini",
                registry=registry,
            )

        assert isinstance(result, OrchestratorResult)
        assert result.agent == "general"
        assert fake_or.complete_with_tools.call_count == 1


class TestClassifyIntentEgressTrip:
    """D-94 — egress filter trips → no LLM call → fallback returned."""

    @pytest.mark.asyncio
    async def test_egress_trip_skips_llm_and_returns_fallback(self):
        fake_or = MagicMock()
        fake_or.complete_with_tools = AsyncMock(
            return_value={"content": '{"agent": "research", "reasoning": "X"}'}
        )
        registry = _StubRegistry([_StubMapping("PERSON", "John Doe")])

        tripped_result = MagicMock(tripped=True, match_count=2)

        with patch.object(
            agent_service, "egress_filter", return_value=tripped_result,
        ) as mock_egress, patch.object(
            agent_service, "get_system_settings",
            return_value=_sys_settings_override(pii_redaction_enabled=True),
        ):
            result = await classify_intent(
                "find John Doe",
                [],
                fake_or,
                "gpt-4o-mini",
                registry=registry,
            )

        # Egress called exactly once.
        assert mock_egress.call_count == 1
        # LLM NOT called when egress trips.
        assert fake_or.complete_with_tools.call_count == 0
        # Fallback returned with reasoning='egress_blocked'.
        assert isinstance(result, OrchestratorResult)
        assert result.agent == "general"
        assert result.reasoning == "egress_blocked"

    @pytest.mark.asyncio
    async def test_egress_trip_log_is_b4_compliant(self, caplog):
        """B4 invariant — egress trip log emits counts ONLY.

        Log message must contain the literal substring
        ``egress_blocked event=egress_blocked feature=classify_intent
        entity_count=<int>``. It must NEVER contain the messages payload,
        registered real_value, or surrogate_value.
        """
        fake_or = MagicMock()
        fake_or.complete_with_tools = AsyncMock()
        # The egress filter would normally see "John Doe" in the haystack;
        # we stub it to trip with match_count=3 so we can grep the formatted
        # log line for the literal "entity_count=3" substring.
        registry = _StubRegistry([_StubMapping("PERSON", "John Doe")])
        tripped_result = MagicMock(tripped=True, match_count=3)

        caplog.set_level(logging.WARNING, logger="app.services.agent_service")
        with patch.object(
            agent_service, "egress_filter", return_value=tripped_result,
        ), patch.object(
            agent_service, "get_system_settings",
            return_value=_sys_settings_override(pii_redaction_enabled=True),
        ):
            await classify_intent(
                "find John Doe",
                [],
                fake_or,
                "gpt-4o-mini",
                registry=registry,
            )

        # Find the structured warning record.
        relevant = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(relevant) >= 1, (
            f"expected at least 1 WARNING record; got: {[r.getMessage() for r in caplog.records]}"
        )
        formatted = " | ".join(r.getMessage() for r in relevant)
        # Required structured-log substrings.
        assert "egress_blocked" in formatted, formatted
        assert "event=egress_blocked" in formatted, formatted
        assert "feature=classify_intent" in formatted, formatted
        assert "entity_count=3" in formatted, formatted
        # B4 invariant: the registered real value must NEVER appear.
        assert "John Doe" not in formatted, (
            f"B4 violation — real PII in log: {formatted!r}"
        )
        # Payload (messages content) must NEVER appear.
        assert "find John Doe" not in formatted, (
            f"B4 violation — messages payload in log: {formatted!r}"
        )

    @pytest.mark.asyncio
    async def test_egress_no_trip_proceeds_to_llm_call(self):
        """When egress passes (tripped=False), classify_intent calls the LLM normally."""
        fake_or = MagicMock()
        fake_or.complete_with_tools = AsyncMock(
            return_value={"content": '{"agent": "research", "reasoning": "X"}'}
        )
        registry = _StubRegistry([])  # empty — nothing to match
        not_tripped = MagicMock(tripped=False, match_count=0)

        with patch.object(
            agent_service, "egress_filter", return_value=not_tripped,
        ) as mock_egress, patch.object(
            agent_service, "get_system_settings",
            return_value=_sys_settings_override(pii_redaction_enabled=True),
        ):
            result = await classify_intent(
                "anonymized message",
                [],
                fake_or,
                "gpt-4o-mini",
                registry=registry,
            )

        assert mock_egress.call_count == 1
        assert fake_or.complete_with_tools.call_count == 1
        assert result.agent == "research"

    @pytest.mark.asyncio
    async def test_egress_called_with_serialized_messages_and_registry(self):
        """D-94 contract: payload is the JSON-serialized messages list, registry
        is the kwarg-passed registry, provisional set is None (D-93 already
        committed)."""
        fake_or = MagicMock()
        fake_or.complete_with_tools = AsyncMock(
            return_value={"content": '{"agent": "general", "reasoning": "x"}'}
        )
        registry = _StubRegistry([])
        not_tripped = MagicMock(tripped=False, match_count=0)

        with patch.object(
            agent_service, "egress_filter", return_value=not_tripped,
        ) as mock_egress, patch.object(
            agent_service, "get_system_settings",
            return_value=_sys_settings_override(pii_redaction_enabled=True),
        ):
            await classify_intent(
                "anon-msg",
                [{"role": "user", "content": "anon-history"}],
                fake_or,
                "gpt-4o-mini",
                registry=registry,
            )

        assert mock_egress.call_count == 1
        args, kwargs = mock_egress.call_args
        # First positional: serialized payload string. Should parse as JSON
        # array of message dicts.
        payload = args[0] if args else kwargs.get("payload")
        assert isinstance(payload, str)
        parsed = json.loads(payload)
        assert isinstance(parsed, list)
        # The user message should be in the serialized payload (anonymized
        # form — caller responsibility per D-93).
        assert any("anon-msg" in (m.get("content") or "") for m in parsed), parsed
        # Second positional: the registry instance.
        passed_registry = args[1] if len(args) >= 2 else kwargs.get("registry")
        assert passed_registry is registry
