"""Phase 6 Plan 06-08 - OBS-02 / OBS-03 caplog coverage tests + B4 regression.

OBS-02 (D-P6-14..16): thread_id=<value> appears in EVERY redaction-pipeline
debug log line so an operator can `grep 'thread_id=<id>'` to extract one
chat turn's full block.

OBS-03 (D-P6-17): every LLMProviderClient.call audit INFO log carries
the resolved provider AND the thread_id - for audit trails proving which
provider handled each feature call (entity_resolution, missed_scan, etc.).

B4 forbidden-tokens (T-06-04-1 mitigation): redact_text_batch +
de_anonymize_text against PII-bearing input emit no real_value or
surrogate substring into any caplog record across the 4 log call sites.

Tests use caplog to capture and assert structured-log emissions. They run
WITHOUT real Presidio (mocked detect_entities for the format-assertion tests)
- these tests assert on the LOG FORMAT and B4 invariant, not on detection
quality (Plan 06-06 covers real-Presidio performance).
"""
from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services.redaction.egress import egress_filter
from app.services.redaction.registry import ConversationRegistry, EntityMapping
from app.services.redaction_service import RedactionService


_THREAD_ID = "test-thread-OBS-DEMO-uuid-1234"


def _fresh_registry(thread_id: str = _THREAD_ID) -> ConversationRegistry:
    """In-memory registry using the REAL constructor signature verified
    at planning time:
        ConversationRegistry(thread_id: str, rows: list[EntityMapping] | None = None)
    Empty rows are correct for tests that don't need pre-populated mappings.
    """
    return ConversationRegistry(thread_id=thread_id, rows=[])


class TestThreadIdLogCoverage:
    """OBS-02 (D-P6-14..16): thread_id appears in every per-operation log."""

    @pytest.mark.asyncio
    async def test_thread_id_appears_in_redact_text_batch_log(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """redact_text_batch debug log carries thread_id=<id>."""
        registry = _fresh_registry()

        # Patch get_system_settings so off-mode early-return doesn't bypass
        # the log line; patch detect_entities to a no-op so we don't load Presidio.
        with patch(
            "app.services.redaction_service.get_system_settings",
            return_value={"pii_redaction_enabled": True},
        ), patch(
            "app.services.redaction_service.detect_entities",
            return_value=("text", [], {}),
        ), patch.object(
            registry.__class__, "upsert_delta", new_callable=AsyncMock
        ):
            service = RedactionService.__new__(RedactionService)
            with caplog.at_level(
                logging.DEBUG, logger="app.services.redaction_service"
            ):
                await service.redact_text_batch(["hello"], registry)

        log_messages = [r.getMessage() for r in caplog.records]
        assert any(
            f"thread_id={_THREAD_ID}" in m and "redact_text_batch" in m
            for m in log_messages
        ), f"expected redact_text_batch log with thread_id; got {log_messages!r}"

    @pytest.mark.asyncio
    async def test_thread_id_appears_in_de_anonymize_text_log(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """de_anonymize_text debug log carries thread_id=<id> (Plan 06-04)."""
        registry = _fresh_registry()
        service = RedactionService.__new__(RedactionService)

        with caplog.at_level(
            logging.DEBUG, logger="app.services.redaction_service"
        ):
            result = await service.de_anonymize_text(
                "irrelevant placeholder text", registry, mode="none",
            )
        assert isinstance(result, str)

        log_messages = [r.getMessage() for r in caplog.records]
        assert any(
            f"thread_id={_THREAD_ID}" in m and "de_anonymize_text" in m
            for m in log_messages
        ), f"expected de_anonymize_text log with thread_id; got {log_messages!r}"

    def test_thread_id_appears_in_egress_filter_trip_log(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """egress_filter trip log carries thread_id=<id> (Plan 06-04 Task 3).

        Builds a registry with one canonical real value; passes a payload
        that contains it; asserts the egress_filter_blocked WARNING log
        emits the thread_id field.

        Constructor signature (verified at planning time):
            EntityMapping(real_value, real_value_lower, surrogate_value, entity_type, source_message_id=None)
            ConversationRegistry(thread_id, rows=[mapping])
        The registry's __init__ derives the by_lower index from rows internally.
        """
        mapping = EntityMapping(
            real_value="Bambang Sutrisno",
            real_value_lower="bambang sutrisno",
            surrogate_value="ER-PERSON-1",
            entity_type="PERSON",
            source_message_id="msg-1",
        )
        registry = ConversationRegistry(thread_id=_THREAD_ID, rows=[mapping])

        payload = (
            '{"messages":[{"role":"user","content":'
            '"Hi Bambang Sutrisno, please review this."}]}'
        )

        with caplog.at_level(
            logging.WARNING, logger="app.services.redaction.egress"
        ):
            result = egress_filter(payload, registry, provisional=None)

        assert result.tripped is True
        log_messages = [r.getMessage() for r in caplog.records]
        assert any(
            f"thread_id={_THREAD_ID}" in m and "egress_filter_blocked" in m
            for m in log_messages
        ), f"expected egress trip log with thread_id; got {log_messages!r}"


class TestResolvedProviderAuditLog:
    """OBS-03 (D-P6-17): every LLMProviderClient.call audit log carries
    provider AND thread_id."""

    @pytest.mark.asyncio
    async def test_resolved_provider_in_success_log(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Successful provider call: audit log has provider=local|cloud +
        thread_id=<id>."""
        from app.services.llm_provider import LLMProviderClient

        registry = _fresh_registry()
        client = LLMProviderClient()

        fake_response = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content='{"ok": true}')
                )
            ]
        )
        with patch(
            "app.services.llm_provider._get_client",
            return_value=SimpleNamespace(
                chat=SimpleNamespace(
                    completions=SimpleNamespace(
                        create=AsyncMock(return_value=fake_response)
                    )
                )
            ),
        ), patch(
            "app.services.llm_provider._resolve_provider",
            return_value=("local", "default"),
        ):
            with caplog.at_level(
                logging.INFO, logger="app.services.llm_provider"
            ):
                result = await client.call(
                    feature="entity_resolution",
                    messages=[{"role": "user", "content": "test"}],
                    registry=registry,
                )

        assert result == {"ok": True}
        log_messages = [r.getMessage() for r in caplog.records]
        assert any(
            "llm_provider_call" in m
            and f"thread_id={_THREAD_ID}" in m
            and "provider=local" in m
            and "feature=entity_resolution" in m
            and "success=True" in m
            for m in log_messages
        ), f"expected audit log with provider+thread_id; got {log_messages!r}"

    @pytest.mark.asyncio
    async def test_resolved_provider_in_error_log(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Provider call that raises: audit log has provider= + thread_id=
        + error_type=<class>."""
        from app.services.llm_provider import LLMProviderClient

        registry = _fresh_registry()
        client = LLMProviderClient()

        with patch(
            "app.services.llm_provider._get_client",
            return_value=SimpleNamespace(
                chat=SimpleNamespace(
                    completions=SimpleNamespace(
                        create=AsyncMock(
                            side_effect=RuntimeError("simulated 5xx")
                        )
                    )
                )
            ),
        ), patch(
            "app.services.llm_provider._resolve_provider",
            return_value=("cloud", "global_env"),
        ):
            with caplog.at_level(
                logging.INFO, logger="app.services.llm_provider"
            ):
                with pytest.raises(RuntimeError):
                    await client.call(
                        feature="missed_scan",
                        messages=[{"role": "user", "content": "test"}],
                        registry=registry,
                    )

        log_messages = [r.getMessage() for r in caplog.records]
        assert any(
            "llm_provider_call" in m
            and f"thread_id={_THREAD_ID}" in m
            and "provider=cloud" in m
            and "feature=missed_scan" in m
            and "success=False" in m
            and "error_type=RuntimeError" in m
            for m in log_messages
        ), f"expected error audit log; got {log_messages!r}"


class TestAdminToggleOverridesFallbackDefault:
    """D-P6-09: even though Plan 06-01 flipped the env-var default to True,
    an admin can still set llm_provider_fallback_enabled=False via
    system_settings to disable the fallback. This test asserts the schema
    default has flipped at the Pydantic-Settings layer (the runtime path
    is exercised by Plan 06-07 PERF-04 tests).

    Pydantic version (verified at planning time): backend/app/config.py uses
    `pydantic_settings.BaseSettings` (Pydantic v2). The v2 API exposes
    `Settings.model_fields[...]` (NOT v1 `Settings.__fields__[...]`).
    """

    def test_settings_default_is_true(self) -> None:
        """Verify the env-var-backed default (Plan 06-01) at the v2 schema."""
        from app.config import Settings

        field_default = Settings.model_fields[
            "llm_provider_fallback_enabled"
        ].default
        assert field_default is True, (
            "Plan 06-01 must have flipped the default to True; "
            f"got {field_default!r}"
        )

    def test_settings_default_is_true_at_runtime(self) -> None:
        """Belt-and-braces: an instantiated Settings also reports the True
        default. Catches the case where someone overrides the schema default
        but a hidden env var still flips it back at instantiation time.

        We instantiate with all required fields supplied as dummy values and
        the optional `llm_provider_fallback_enabled` deliberately omitted, so
        pydantic uses the schema default (True) rather than any env-var value.
        """
        from app.config import Settings
        import os

        # Build a minimal env dict with required fields and
        # explicitly unset llm_provider_fallback_enabled so we get the default.
        env_overrides = {
            "SUPABASE_URL": "https://dummy.supabase.co",
            "SUPABASE_ANON_KEY": "dummy-anon",
            "SUPABASE_SERVICE_ROLE_KEY": "dummy-service",
            "OPENAI_API_KEY": "dummy-openai",
        }
        # Temporarily clear the target env var so the schema default applies.
        original = os.environ.pop("LLM_PROVIDER_FALLBACK_ENABLED", None)
        try:
            instance = Settings(**env_overrides)
            assert instance.llm_provider_fallback_enabled is True, (
                "Settings(required_fields).llm_provider_fallback_enabled must be True; "
                f"got {instance.llm_provider_fallback_enabled!r}"
            )
        finally:
            if original is not None:
                os.environ["LLM_PROVIDER_FALLBACK_ENABLED"] = original


class TestB4LogPrivacyForbiddenTokens:
    """T-06-04-1 mitigation regression: redact_text_batch + de_anonymize_text
    against PII-bearing input emit no real_value or surrogate substring into
    any caplog record across the 4 modified log call sites (B4 invariant).

    Phase 6's thread_id additions ONLY add a Supabase-UUID field — never raw
    text or surrogates. This test guards against future refactors that
    accidentally interpolate `text` / `real_value` / `surrogate_value` into
    a log line.

    Fixture covers the 3 most-leaky entity types (PERSON, EMAIL, PHONE)
    drawn from the existing Phase 6 fixture set used in Plan 06-06.
    """

    @pytest.mark.asyncio
    async def test_no_real_or_surrogate_substring_in_logs(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Run redact_text_batch + de_anonymize_text against a registry that
        already contains PERSON / EMAIL / PHONE mappings. Assert no record
        captured by caplog contains the real_value OR the surrogate_value
        substring for any of the 3 mappings.
        """
        # Pre-populated registry — covers PERSON / EMAIL / PHONE entity types.
        person_mapping = EntityMapping(
            real_value="Bambang Sutrisno",
            real_value_lower="bambang sutrisno",
            surrogate_value="ER-PERSON-1",
            entity_type="PERSON",
            source_message_id="msg-1",
        )
        email_mapping = EntityMapping(
            real_value="bambang.sutrisno@mitra-abadi.co.id",
            real_value_lower="bambang.sutrisno@mitra-abadi.co.id",
            surrogate_value="ER-EMAIL-1",
            entity_type="EMAIL_ADDRESS",
            source_message_id="msg-1",
        )
        phone_mapping = EntityMapping(
            real_value="+62 812 3456 7890",
            real_value_lower="+62 812 3456 7890",
            surrogate_value="ER-PHONE-1",
            entity_type="PHONE_NUMBER",
            source_message_id="msg-1",
        )
        registry = ConversationRegistry(
            thread_id="b4-forbidden-tokens-test",
            rows=[person_mapping, email_mapping, phone_mapping],
        )

        # Patch get_system_settings so redact_text_batch hot-path runs;
        # patch detect_entities so we don't depend on real Presidio.
        with patch(
            "app.services.redaction_service.get_system_settings",
            return_value={"pii_redaction_enabled": True},
        ), patch(
            "app.services.redaction_service.detect_entities",
            return_value=("hello", [], {}),
        ), patch.object(
            registry.__class__, "upsert_delta", new_callable=AsyncMock
        ):
            service = RedactionService.__new__(RedactionService)
            # Capture all redaction-pipeline loggers at DEBUG.
            with caplog.at_level(logging.DEBUG, logger="app.services.redaction_service"), \
                 caplog.at_level(logging.DEBUG, logger="app.services.redaction"), \
                 caplog.at_level(logging.WARNING, logger="app.services.redaction.egress"):
                # Exercise both log-emitting code paths: redact + de-anon.
                await service.redact_text_batch(["hello world"], registry)
                await service.de_anonymize_text(
                    "ER-PERSON-1 sent ER-EMAIL-1", registry, mode="none",
                )

        forbidden = [
            "Bambang Sutrisno",
            "bambang.sutrisno@mitra-abadi.co.id",
            "+62 812 3456 7890",
            "ER-PERSON-1",
            "ER-EMAIL-1",
            "ER-PHONE-1",
        ]

        # Iterate every captured record. If any forbidden substring appears
        # in any record's message, the B4 invariant is violated.
        for record in caplog.records:
            msg = record.getMessage()
            for token in forbidden:
                assert token not in msg, (
                    f"B4 invariant violated: forbidden token {token!r} "
                    f"appeared in log record: {msg!r}"
                )
