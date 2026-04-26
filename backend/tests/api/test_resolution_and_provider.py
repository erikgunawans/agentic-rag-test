"""Phase 3 ROADMAP success-criteria coverage (D-64).

SC#1: algorithmic clustering — multi-variant collapse to one canonical surrogate (live DB).
SC#2: cloud LLM mode + payload-with-real-value → egress trip → algorithmic fallback.
SC#3: local LLM mode sees raw real names; egress filter NEVER invoked.
SC#4: non-PERSON entities (EMAIL, PHONE, URL) NEVER appear in resolution-LLM payload.
SC#5: PATCH /admin/settings llm_provider=cloud → cache TTL → next _resolve_provider returns 'cloud'.

Live target: Supabase project qedhulpfezucnfadlfiz. Cloud LLM calls are mocked
at the AsyncOpenAI client level (D-65) — CI never hits a real cloud endpoint.

Calibration notes (Phase 2 precedent — three Rule-1 deviations from
test_redaction_registry.py header):
- xx-multilingual Presidio model is the active recogniser; ALL-CAPS PERSON is
  not consistently detected. Tests that need cross-call PERSON detection use
  Title-case or lower-case variants — not ALL-CAPS.
- "Pak Bambang Sutrisno" — detected with the honorific included. The bare
  form "Bambang Sutrisno" is detected separately. Variant-row counts in SC#1
  account for whichever forms Presidio actually returns.
- US_SSN is not consistently detected by xx-multilingual; SC#4 uses
  EMAIL_ADDRESS / PHONE_NUMBER / URL only.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import get_settings
from app.database import get_supabase_client
from app.services.llm_provider import _resolve_provider
from app.services.redaction.egress import _EgressBlocked
from app.services.redaction_service import get_redaction_service
from app.services.system_settings_service import (
    get_system_settings,
    update_system_settings,
)

pytestmark = pytest.mark.asyncio


def _patched_settings(mode: str) -> SimpleNamespace:
    """Return a Settings-like object with the desired entity_resolution_mode.

    redaction_service.redact_text() only reads ``settings.entity_resolution_mode``
    from get_settings(); patching that single function is the smallest blast
    radius. We mirror the real Settings shape via SimpleNamespace so other
    attribute reads (if any future change adds them) raise AttributeError loud.
    """
    real = get_settings()
    # Copy every field from real Settings + override the mode field.
    overrides = {f: getattr(real, f) for f in real.model_dump().keys()}
    overrides["entity_resolution_mode"] = mode
    return SimpleNamespace(**overrides)


# --- SC#1: algorithmic clustering — variant rows persist (live DB). ---


class TestSC1_AlgorithmicClustering:
    """Bambang Sutrisno / Pak Bambang / Sutrisno collapse and persist as
    multiple registry rows under ONE canonical surrogate (D-45 / D-48).
    Default mode is 'algorithmic' (Settings default), so no patching needed.
    """

    async def test_variants_collapse_to_one_canonical_surrogate(
        self, fresh_thread_id, seeded_faker
    ):
        from app.services.redaction.registry import ConversationRegistry

        service = get_redaction_service()
        registry = await ConversationRegistry.load(fresh_thread_id)

        # Three sentences mentioning the same person via different forms.
        text = (
            "Bambang Sutrisno menandatangani kontrak hari ini. "
            "Pak Bambang setuju dengan klausul lima. "
            "Sutrisno akan meninjau revisi minggu depan."
        )
        result = await service.redact_text(text, registry=registry)

        # Variant rows persisted in entity_registry — at least canonical +
        # one decomposed token (first-only or last-only). Honorific row only
        # appears if Presidio returned a honorific-prefixed span.
        client = get_supabase_client()
        rows = (
            client.table("entity_registry")
            .select("real_value,real_value_lower,surrogate_value,entity_type")
            .eq("thread_id", fresh_thread_id)
            .eq("entity_type", "PERSON")
            .execute()
            .data
        )
        assert len(rows) >= 2, (
            f"expected ≥2 PERSON variant rows for clustered name, got "
            f"{len(rows)}: {rows!r}"
        )
        # All PERSON rows must share ONE canonical surrogate (D-45 / D-48).
        surrogates = {r["surrogate_value"] for r in rows}
        assert len(surrogates) == 1, (
            f"variant rows should share one canonical surrogate; got {surrogates!r}"
        )
        # The anonymized text must NOT contain the real value.
        assert "Bambang Sutrisno" not in result.anonymized_text, (
            f"real value leaked in algorithmic mode: {result.anonymized_text!r}"
        )

    async def test_repeat_mention_reuses_surrogate(
        self, fresh_thread_id, seeded_faker
    ):
        """REG-04 / D-45: a second redact call with another mention reuses
        the canonical surrogate (no new surrogate allocated).
        """
        from app.services.redaction.registry import ConversationRegistry

        service = get_redaction_service()
        registry = await ConversationRegistry.load(fresh_thread_id)

        await service.redact_text(
            "Bambang Sutrisno menandatangani kontrak.", registry=registry
        )
        s1 = registry.lookup("Bambang Sutrisno")
        assert s1 is not None, "first call must persist a surrogate"

        # Second call — same canonical, plus an additional sentence.
        await service.redact_text(
            "Bambang Sutrisno akan hadir besok.", registry=registry
        )
        s2 = registry.lookup("Bambang Sutrisno")
        assert s2 == s1, (
            f"repeat mention must reuse surrogate; got {s1!r} vs {s2!r}"
        )


# --- SC#2: cloud LLM mode + egress trip → algorithmic fallback. ---


class TestSC2_CloudEgressFallback:
    """cloud + payload-with-real-value → trip → algorithmic fallback (no real
    value sent). The cloud SDK call MUST NEVER be made when the egress filter
    trips. The chat loop MUST NOT crash (NFR-3).
    """

    async def test_egress_trip_falls_back_to_algorithmic(
        self, fresh_thread_id, seeded_faker, caplog
    ):
        from app.services.redaction.registry import ConversationRegistry

        # Pre-seed the registry with a real value so the cloud payload trips on it.
        client = get_supabase_client()
        client.table("entity_registry").insert(
            {
                "thread_id": fresh_thread_id,
                "real_value": "John Doe",
                "real_value_lower": "john doe",
                "surrogate_value": "Mock_Surrogate_42",
                "entity_type": "PERSON",
            }
        ).execute()

        # Mock the AsyncOpenAI client — the cloud SDK call MUST NOT happen.
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock()

        service = get_redaction_service()

        # Patch settings to mode='llm'. Patch _get_client so cloud doesn't
        # talk to a real endpoint. Set ENTITY_RESOLUTION_LLM_PROVIDER=cloud
        # via env (D-51 priority 1) so _resolve_provider returns cloud.
        with patch(
            "app.services.redaction_service.get_settings",
            return_value=_patched_settings("llm"),
        ), patch(
            "app.services.llm_provider._get_client", return_value=mock_client
        ), patch.dict(
            "os.environ",
            {"ENTITY_RESOLUTION_LLM_PROVIDER": "cloud"},
            clear=False,
        ):
            # Need a fresh registry that includes the pre-seeded John Doe row.
            registry = await ConversationRegistry.load(fresh_thread_id)
            text = "John Doe has been reassigned. Maria Santos will lead."
            result = await service.redact_text(text, registry=registry)

        # The SDK call was NEVER made (egress trip aborted pre-call).
        assert mock_client.chat.completions.create.call_count == 0, (
            f"cloud SDK was called {mock_client.chat.completions.create.call_count} "
            f"times — egress filter failed to abort"
        )
        # The fallback path produced a result — the chat loop did not crash.
        assert result.anonymized_text is not None
        assert "John Doe" not in result.anonymized_text, (
            "real value leaked in fallback output"
        )
        # B4 invariant: no raw value in any captured log line.
        log_text = "\n".join(rec.getMessage() for rec in caplog.records)
        assert "John Doe" not in log_text, (
            f"raw PII leaked in log output: {log_text!r}"
        )


# --- SC#3: local LLM mode sees raw real names; egress filter NEVER invoked. ---


class TestSC3_LocalModeBypassesEgress:
    """local mode + LLM resolution — egress filter NEVER invoked (FR-9.2)."""

    async def test_local_mode_bypasses_egress_filter(
        self, fresh_thread_id, seeded_faker
    ):
        from app.services.redaction.registry import ConversationRegistry

        # Mock the local LLM SDK with a structured response.
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content='{"clusters": []}'))
        ]
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        service = get_redaction_service()
        registry = await ConversationRegistry.load(fresh_thread_id)

        with patch(
            "app.services.redaction_service.get_settings",
            return_value=_patched_settings("llm"),
        ), patch(
            "app.services.llm_provider._get_client", return_value=mock_client
        ), patch(
            "app.services.llm_provider.egress_filter"
        ) as egress_mock, patch.dict(
            "os.environ",
            {"ENTITY_RESOLUTION_LLM_PROVIDER": "local"},
            clear=False,
        ):
            text = "Bambang Sutrisno menandatangani kontrak hari ini."
            await service.redact_text(text, registry=registry)

        # FR-9.2: local mode → egress filter NEVER called.
        assert egress_mock.call_count == 0, (
            f"egress filter was invoked {egress_mock.call_count} times in "
            f"local mode — must be 0 (FR-9.2)"
        )


# --- SC#4: non-PERSON entities NEVER reach the resolution LLM. ---


class TestSC4_NonPersonNeverReachLLM:
    """SC#4 / RESOLVE-04: emails/phones/URLs go through normalize-only path
    and NEVER appear in any LLM resolution payload.
    """

    async def test_resolution_payload_contains_only_person_strings(
        self, fresh_thread_id, seeded_faker
    ):
        from app.services.redaction.registry import ConversationRegistry

        captured_payloads: list = []

        async def _capture(*args, **kwargs):
            payload = kwargs.get("messages") or (args[1] if len(args) > 1 else None)
            captured_payloads.append(payload)
            mock_response = MagicMock()
            mock_response.choices = [
                MagicMock(message=MagicMock(content='{"clusters": []}'))
            ]
            return mock_response

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=_capture)

        service = get_redaction_service()
        registry = await ConversationRegistry.load(fresh_thread_id)

        with patch(
            "app.services.redaction_service.get_settings",
            return_value=_patched_settings("llm"),
        ), patch(
            "app.services.llm_provider._get_client", return_value=mock_client
        ), patch.dict(
            "os.environ",
            {"ENTITY_RESOLUTION_LLM_PROVIDER": "local"},
            clear=False,
        ):
            text = (
                "Bambang Sutrisno will email alice@example.com from "
                "+62-812-3456-7890. Visit https://contoh.id/dokumen for the "
                "contract."
            )
            await service.redact_text(text, registry=registry)

        # If any LLM call was made, none of the captured payloads may contain
        # email / phone / URL substrings (RESOLVE-04). If no call was made
        # (e.g., Presidio detected zero PERSON spans), the assertion is
        # vacuously true — which is the correct invariant.
        for payload in captured_payloads:
            payload_str = str(payload)
            assert "alice@example.com" not in payload_str, (
                "EMAIL leaked into resolution-LLM payload (RESOLVE-04 violation)"
            )
            assert "+62-812-3456-7890" not in payload_str, (
                "PHONE leaked into resolution-LLM payload"
            )
            assert "https://contoh.id" not in payload_str, (
                "URL leaked into resolution-LLM payload"
            )
            assert "contoh.id/dokumen" not in payload_str, (
                "URL substring leaked into resolution-LLM payload"
            )


# --- SC#5: admin-UI provider switch propagates within cache window. ---


class TestSC5_AdminUIProviderPropagation:
    """PATCH /admin/settings llm_provider=cloud → cache invalidation → next
    _resolve_provider call sees 'cloud' (no redeploy required).

    Note: ``update_system_settings`` is sync (not async — see
    ``backend/app/services/system_settings_service.py`` L23). The plan's
    ``await update_system_settings(...)`` is a Rule-1 bug; this test calls
    the sync function directly.
    """

    async def test_provider_switch_propagates_within_cache_window(
        self, monkeypatch
    ):
        # Clear envs so _resolve_provider falls through to the DB layer
        # (D-51 priority 4 'global_db'). Without this, the env value would
        # win regardless of DB state.
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        monkeypatch.delenv("ENTITY_RESOLUTION_LLM_PROVIDER", raising=False)

        # Capture starting value so we can restore on teardown.
        original = get_system_settings().get("llm_provider", "local")
        try:
            # Set initial value via update_system_settings (invalidates cache).
            update_system_settings({"llm_provider": "local"})
            provider, source = _resolve_provider("entity_resolution")
            assert provider == "local", (
                f"after setting llm_provider=local, _resolve_provider returned "
                f"{provider!r} (source={source!r})"
            )
            assert source == "global_db", (
                f"resolution should hit global_db layer; got source={source!r}"
            )

            # PATCH to 'cloud' (invalidates cache; next read returns the new value).
            update_system_settings({"llm_provider": "cloud"})
            provider, source = _resolve_provider("entity_resolution")
            assert provider == "cloud", (
                f"after PATCH llm_provider=cloud, _resolve_provider returned "
                f"{provider!r} (source={source!r})"
            )
            assert source == "global_db"
        finally:
            # Restore the original DB value so subsequent test runs and the
            # live deployment are unaffected.
            update_system_settings({"llm_provider": original})

    async def test_feature_override_db_propagates(self, monkeypatch):
        """D-51 priority 2: feature_db override visible after cache invalidation."""
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        monkeypatch.delenv("ENTITY_RESOLUTION_LLM_PROVIDER", raising=False)

        original = get_system_settings().get("entity_resolution_llm_provider")
        try:
            # Clear feature override → resolution should fall through to global.
            update_system_settings({"entity_resolution_llm_provider": None})
            update_system_settings({"llm_provider": "local"})
            provider1, source1 = _resolve_provider("entity_resolution")
            assert provider1 == "local"

            # Set feature override to cloud → must beat global.
            update_system_settings({"entity_resolution_llm_provider": "cloud"})
            provider2, source2 = _resolve_provider("entity_resolution")
            assert provider2 == "cloud"
            assert source2 == "feature_db", (
                f"expected feature_db source; got {source2!r}"
            )
        finally:
            update_system_settings(
                {"entity_resolution_llm_provider": original}
            )
            update_system_settings({"llm_provider": "local"})


# --- B4 / D-55: log-privacy invariant across the Phase 3 surface. ---


class TestSC6_LogPrivacy:
    """B4 / D-18 / D-41 / D-55: no raw PII in any captured log line during
    Phase 3 redaction calls. Mirrors Phase 2 TestSC6_LogPrivacy.
    """

    async def test_no_real_pii_in_log_during_cloud_egress_trip(
        self, fresh_thread_id, seeded_faker, caplog
    ):
        import logging as _logging

        from app.services.redaction.registry import ConversationRegistry

        # Pre-seed registry; force cloud egress trip.
        client = get_supabase_client()
        client.table("entity_registry").insert(
            {
                "thread_id": fresh_thread_id,
                "real_value": "Bambang Sutrisno",
                "real_value_lower": "bambang sutrisno",
                "surrogate_value": "Andi Pratama",
                "entity_type": "PERSON",
            }
        ).execute()

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock()

        service = get_redaction_service()
        with patch(
            "app.services.redaction_service.get_settings",
            return_value=_patched_settings("llm"),
        ), patch(
            "app.services.llm_provider._get_client", return_value=mock_client
        ), patch.dict(
            "os.environ",
            {"ENTITY_RESOLUTION_LLM_PROVIDER": "cloud"},
            clear=False,
        ), caplog.at_level(_logging.DEBUG):
            registry = await ConversationRegistry.load(fresh_thread_id)
            text = "Bambang Sutrisno akan hadir besok."
            await service.redact_text(text, registry=registry)

        forbidden = ["Bambang Sutrisno", "Bambang", "Sutrisno"]
        for record in caplog.records:
            msg = record.getMessage()
            for value in forbidden:
                assert value not in msg, (
                    f"Real PII {value!r} leaked in log: {msg!r} "
                    f"(logger={record.name}, level={record.levelname})"
                )
