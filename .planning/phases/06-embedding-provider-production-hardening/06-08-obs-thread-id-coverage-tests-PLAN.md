---
plan_id: "06-08"
title: "OBS-02 / OBS-03 thread_id + resolved-provider log coverage tests + final regression + CLAUDE.md doc note"
phase: "06-embedding-provider-production-hardening"
plan: 8
type: execute
wave: 4
depends_on: ["06-04", "06-05", "06-06", "06-07"]
autonomous: false
files_modified:
  - backend/tests/services/redaction/test_thread_id_logging.py
  - CLAUDE.md
requirements: [OBS-02, OBS-03, EMBED-02, PERF-04]
must_haves:
  truths:
    - "OBS-02 verifiable: redact_text_batch + de_anonymize_text + egress_filter trip log lines all carry thread_id=<id> — extractable by grep 'thread_id=<id>' (D-P6-14, D-P6-16)"
    - "OBS-03 verifiable: each LLMProviderClient.call audit INFO line contains both `provider=<value>` AND `thread_id=<value>` (D-P6-17)"
    - "PERF-04 admin-toggle invariant: Pydantic Settings default for `llm_provider_fallback_enabled` is True (Plan 06-01 flip verified at the Pydantic v2 schema layer via `Settings.model_fields`, not just at runtime)"
    - "B4 forbidden-tokens invariant: redact_text_batch + de_anonymize_text against PII-bearing input emit no real_value or surrogate substring into any caplog record across the 4 modified log call sites (T-06-04-1 mitigation regression test)"
    - "EMBED-02 documented: CLAUDE.md notes that switching EMBEDDING_PROVIDER does NOT trigger automatic re-embedding (D-P6-04)"
    - "Final phase regression: pre-existing unit tests + Phase 5 integration tests + Phase 6 new tests all pass; slow-marked PERF-02 test passes when explicitly invoked"
    - "Off-mode invariant (SC#5): when pii_redaction_enabled=false the entire chat path remains byte-identical to pre-v0.3 behavior — no thread_id log spam, no fallback log spam"
  artifacts:
    - path: "backend/tests/services/redaction/test_thread_id_logging.py"
      provides: "OBS-02 + OBS-03 + admin-toggle + B4-forbidden-tokens caplog regression tests"
      contains: "test_thread_id_appears_in_redact_text_batch_log"
    - path: "CLAUDE.md"
      provides: "EMBED-02 deploy gotcha: switching EMBEDDING_PROVIDER does NOT auto re-embed"
      contains: "EMBEDDING_PROVIDER"
  key_links:
    - from: "backend/tests/services/redaction/test_thread_id_logging.py"
      to: "backend/app/services/redaction_service.py debug log lines (post-Plan-06-04)"
      via: "caplog assertion on thread_id=<id>"
      pattern: "thread_id=<id>"
    - from: "backend/tests/services/redaction/test_thread_id_logging.py"
      to: "backend/app/services/llm_provider.py audit log lines (post-Plan-06-04)"
      via: "caplog assertion on provider= AND thread_id="
      pattern: "provider=.+thread_id="
threat_model:
  - id: "T-06-08-1"
    description: "Test fixtures with realistic-looking PII that get checked into git could leak privacy contracts. Risk: fixture strings (synthetic names like 'Bambang Sutrisno') become indexed by code search and search-engine crawlers."
    mitigation: "All fixture names in this plan's tests are synthetic and already used in the upstream Plan 06-06 fixture (which is itself committed). No new realistic-looking PII strings are introduced. Acceptance criteria includes a grep gate verifying no real-looking emails/phones/addresses outside the existing legal-document fixture pattern."
    severity: "low"
---

<objective>
Add the OBS-02 + OBS-03 caplog coverage tests, add the B4 forbidden-tokens regression test (T-06-04-1 mitigation), document the EMBED-02 no-auto-re-embed deploy note in CLAUDE.md, and run the final phase regression. This plan is the last on the dependency tree — Plans 06-04 (thread_id wiring) and 06-07 (PERF-04 tests) must be in place first.

Purpose: Phase 6 SC#4 (debug log block extractable by grep) and SC#5 (every LLM call logs resolved provider for audit). These are observability invariants future refactors could silently regress; caplog tests are the gate. The plan also adds the B4 forbidden-tokens regression test that Plan 06-04 T-06-04-1 cites in its mitigation, captures the D-P6-04 deployment-note (no auto-re-embed) in CLAUDE.md, and acts as the phase's manual-checkpoint gate before the executor commits.

Output: 1 new test file (7 caplog tests across 4 test classes), 1 CLAUDE.md edit (gotcha note), and a final regression run + manual verification checkpoint.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/06-embedding-provider-production-hardening/06-CONTEXT.md
@.planning/phases/06-embedding-provider-production-hardening/06-04-SUMMARY.md
@.planning/phases/06-embedding-provider-production-hardening/06-07-SUMMARY.md
@backend/app/services/redaction_service.py
@backend/app/services/llm_provider.py
@backend/app/services/redaction/egress.py
@backend/app/services/redaction/detection.py
@backend/app/services/redaction/registry.py
@backend/app/config.py
@CLAUDE.md

<interfaces>
<!-- Post-Plan-06-04 log lines this plan asserts against. -->

```
# redaction_service.py log call sites (post-Plan-06-04) — all carry thread_id:
#   line 432: redaction.redact_text(registry): thread_id=%s ...
#   line 517: redaction.redact_text_batch: thread_id=%s ...
#   line 762: redaction.redact_text(reg): thread_id=%s ...
#   line 923: redaction.de_anonymize_text: thread_id=%s ...

# llm_provider.py audit log sites (post-Plan-06-04) — all carry thread_id + provider + source:
#   line 192-197: thread_id=%s feature=%s provider=%s source=%s success=False egress_tripped=True
#   line 209-214: thread_id=%s feature=%s provider=%s source=%s success=True latency_ms=%d
#   line 220-226: thread_id=%s feature=%s provider=%s source=%s success=False error_type=%s

# egress.py trip log (post-Plan-06-04):
#   egress_filter_blocked event=egress_filter_blocked thread_id=%s match_count=%d entity_types=%s match_hashes=%s

# missed_scan.py soft-fail logs (post-Plan-06-04):
#   event=missed_scan_skipped thread_id=%s feature=missed_scan error_class=%s
```

```python
# backend/app/services/redaction/registry.py — VERIFIED constructor signature
# (read at planning time):
class ConversationRegistry:
    def __init__(
        self,
        thread_id: str,
        rows: list[EntityMapping] | None = None,
    ) -> None: ...
# The registry derives the by_lower index internally from rows. Do NOT pass
# `lookup=`, `entries_list=`, or `forbidden_tokens=` kwargs — these names do
# not exist on __init__ and will raise TypeError.

class EntityMapping(BaseModel):
    real_value: str
    real_value_lower: str
    surrogate_value: str
    entity_type: str  # PERSON / EMAIL_ADDRESS / PHONE_NUMBER / LOCATION / DATE_TIME / URL / IP_ADDRESS
    source_message_id: str | None = None
```

```python
# backend/app/config.py — VERIFIED at planning time:
#   from pydantic_settings import BaseSettings, SettingsConfigDict
#   class Settings(BaseSettings): ...
# Pydantic v2. Use `Settings.model_fields["..."].default` (NOT v1 `__fields__`).
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Write OBS-02/03 + admin-toggle + B4-forbidden-tokens caplog tests in test_thread_id_logging.py</name>
  <read_first>
    - backend/app/services/redaction_service.py (post-Plan-06-04 log lines at 432, 517, 762, 923)
    - backend/app/services/llm_provider.py (post-Plan-06-04 log lines at 192-197, 209-214, 220-226)
    - backend/app/services/redaction/egress.py (post-Plan-06-04 trip log line)
    - backend/app/services/redaction/registry.py (VERIFIED at planning time: `ConversationRegistry(thread_id, rows=[...])`; `EntityMapping(real_value, real_value_lower, surrogate_value, entity_type, source_message_id=None)`. Use ONLY these signatures.)
    - backend/app/config.py (VERIFIED at planning time: Pydantic v2 — uses `pydantic_settings.BaseSettings`. Test must use `Settings.model_fields["..."].default`, not v1 `__fields__`.)
    - backend/tests/services/redaction/test_perf04_degradation.py (Plan 06-07 — established AsyncMock + ConversationRegistry pattern; mirror it)
    - .planning/phases/06-embedding-provider-production-hardening/06-CONTEXT.md (D-P6-14..D-P6-17 verbatim)
  </read_first>
  <files>backend/tests/services/redaction/test_thread_id_logging.py</files>
  <action>
Create the test file with 7 caplog assertion tests across 4 test classes. The `ConversationRegistry(...)` and `EntityMapping(...)` constructor calls use ONLY the verified real signatures.

```python
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
        """Belt-and-braces: an instantiated Settings (with no env file) also
        reports the True default. Catches the case where someone overrides
        the schema default but a hidden env var still flips it back at
        instantiation time.
        """
        from app.config import Settings

        # _env_file=None disables .env loading so we get the schema default.
        instance = Settings(_env_file=None)
        assert instance.llm_provider_fallback_enabled is True, (
            "Settings(_env_file=None).llm_provider_fallback_enabled must be True; "
            f"got {instance.llm_provider_fallback_enabled!r}"
        )


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
```

The `ConversationRegistry(...)` and `EntityMapping(...)` constructor calls use ONLY the verified real signatures. There are NO `lookup`, `entries_list`, or `forbidden_tokens` kwargs in the real `ConversationRegistry.__init__` — those names are not part of `__init__` and WILL raise `TypeError` if passed. The registry derives the by_lower index internally from `rows`.

The Pydantic version assertion uses `Settings.model_fields[...]` (Pydantic v2 — verified at planning time that `backend/app/config.py` uses `pydantic_settings.BaseSettings`). A second runtime-instantiation test (`test_settings_default_is_true_at_runtime`) provides belt-and-braces coverage in case the schema default ever drifts from the runtime default.

Do NOT mock `egress_filter` itself - Task 1's third sub-test asserts the REAL filter's log line.

Do NOT mock `_resolve_provider`'s internal logic - the test patches the function symbol so the test controls the resolution outcome deterministically.
  </action>
  <verify>
    <automated>cd backend &amp;&amp; source venv/bin/activate &amp;&amp; pytest tests/services/redaction/test_thread_id_logging.py -v --tb=short</automated>
  </verify>
  <acceptance_criteria>
    - File `backend/tests/services/redaction/test_thread_id_logging.py` exists
    - `grep -nE "class TestThreadIdLogCoverage|class TestResolvedProviderAuditLog|class TestAdminToggleOverridesFallbackDefault|class TestB4LogPrivacyForbiddenTokens" backend/tests/services/redaction/test_thread_id_logging.py` returns exactly 4 matches
    - `grep -nE "test_thread_id_appears_in_redact_text_batch_log|test_thread_id_appears_in_de_anonymize_text_log|test_thread_id_appears_in_egress_filter_trip_log|test_resolved_provider_in_success_log|test_resolved_provider_in_error_log|test_settings_default_is_true|test_settings_default_is_true_at_runtime|test_no_real_or_surrogate_substring_in_logs" backend/tests/services/redaction/test_thread_id_logging.py` returns exactly 8 matches
    - `grep -cE 'thread_id=\{_THREAD_ID\}' backend/tests/services/redaction/test_thread_id_logging.py` returns at least 5 matches (caplog assertions)
    - `grep -n '"provider=local"' backend/tests/services/redaction/test_thread_id_logging.py` returns at least 1 match (OBS-03 success path)
    - `grep -n '"provider=cloud"' backend/tests/services/redaction/test_thread_id_logging.py` returns at least 1 match (OBS-03 error path)
    - Real-constructor compliance: `grep -cE "lookup=|entries_list=|forbidden_tokens=" backend/tests/services/redaction/test_thread_id_logging.py` returns 0 (none of the fabricated 4-kwarg form leaked)
    - `grep -cE "ConversationRegistry\(thread_id=.*rows=" backend/tests/services/redaction/test_thread_id_logging.py` returns at least 2 (real signature in helper + B4 test)
    - `grep -c "EntityMapping(" backend/tests/services/redaction/test_thread_id_logging.py` returns at least 4 (egress test mapping + 3 B4 mappings)
    - Pydantic v2 API used: `grep -c "Settings.model_fields\[" backend/tests/services/redaction/test_thread_id_logging.py` returns at least 1
    - No Pydantic v1 API used: `grep -c "Settings.__fields__\[" backend/tests/services/redaction/test_thread_id_logging.py` returns 0
    - B4 forbidden-tokens test present: `grep -c 'forbidden = \[' backend/tests/services/redaction/test_thread_id_logging.py` returns at least 1
    - `cd backend &amp;&amp; source venv/bin/activate &amp;&amp; pytest tests/services/redaction/test_thread_id_logging.py -v --tb=short 2>&amp;1 | grep -E "passed|failed" | tail -1` shows `8 passed`
  </acceptance_criteria>
  <done>8 caplog tests pass: 3 OBS-02 thread_id-in-debug-log + 2 OBS-03 resolved-provider-in-audit-log + 2 admin-toggle-default check (schema + runtime) + 1 B4 forbidden-tokens regression. All tests use the REAL ConversationRegistry / EntityMapping signatures and the Pydantic v2 API.</done>
</task>

<task type="auto">
  <name>Task 2: Document EMBED-02 no-auto-re-embed in CLAUDE.md "Gotchas"</name>
  <read_first>
    - CLAUDE.md (full file - find the "## Gotchas" section; the new note is appended as a new bullet alongside existing Vercel/Railway gotchas)
    - .planning/phases/06-embedding-provider-production-hardening/06-CONTEXT.md (D-P6-04 verbatim - "switching providers does NOT trigger automatic re-embedding"; documentation only, no code)
    - .planning/phases/06-embedding-provider-production-hardening/06-03-SUMMARY.md (the deployer-instructions paragraph from the embedding branch plan)
  </read_first>
  <files>CLAUDE.md</files>
  <action>
Locate the existing `## Gotchas` section in CLAUDE.md (line ~92 in the current file; the section runs to roughly line 105 with bullets about Vercel deploys, Railway deploys, Presidio Dockerfile, system_settings, base-ui tooltips, glass, Pydantic warning, Postgrest filters, get_current_user, migrations, and 024_*.sql duplicates).

APPEND a single new bullet at the END of that bulleted list (immediately before the next `## ...` heading - the next heading after Gotchas is `## Workflow`). Do NOT add a sub-heading; the new content is one dash-prefixed bullet using the same markdown style as the surrounding bullets.

Use exactly this text:

```
- **`EMBEDDING_PROVIDER` switch does NOT trigger re-embedding (Phase 6 / EMBED-02).** Setting `EMBEDDING_PROVIDER=local` and `LOCAL_EMBEDDING_BASE_URL=http://localhost:11434/v1` redirects FUTURE ingestions to the local endpoint (e.g., Ollama bge-m3 / nomic-embed-text). Existing document vectors stay in their original embedding space until manually re-ingested. RAG retrieval quality may degrade for queries that span both old and new chunks. Deployer-managed migration: re-ingest documents (drop + re-upload) when consolidating to a single provider.
```

Do NOT modify the existing Vercel / Railway / Presidio / system_settings / migration gotchas - additive only.

Do NOT touch any other section of CLAUDE.md (Stack, Architecture, Design System, Key Patterns, Rules, Admin / RBAC, Deployment, Planning, Plan Verification Protocol, Testing, Code Quality, LLM Pipeline, Automations, Workflow, Pre-Push Checks, Session Continuity, Progress, graphify).

Do NOT introduce code blocks or sub-bullets within the new line.
  </action>
  <verify>
    <automated>grep -nE "EMBEDDING_PROVIDER.*re-embed|re-embed.*EMBEDDING_PROVIDER" CLAUDE.md</automated>
  </verify>
  <acceptance_criteria>
    - `grep -nE "EMBEDDING_PROVIDER" CLAUDE.md` returns at least 1 match (new bullet)
    - `grep -nE "Phase 6 / EMBED-02" CLAUDE.md` returns exactly 1 match
    - `grep -nE "Ollama bge-m3" CLAUDE.md` returns exactly 1 match (verifies the example endpoint string is preserved verbatim)
    - `grep -cE "^## Gotchas" CLAUDE.md` returns exactly 1 match (we did not add a new heading)
    - `grep -cE "^## Workflow" CLAUDE.md` returns exactly 1 match (next heading still present, indicating we did not delete/duplicate)
    - The pre-Plan-06-08 gotcha bullets (Vercel deploys from main, Railway is manual, Presidio spaCy build-time, etc.) are all still present - check via `grep -cE "^- \*\*" CLAUDE.md` and confirm count is BASELINE+1
  </acceptance_criteria>
  <done>One new bullet appended to the Gotchas section; existing bullets and headings unchanged.</done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 3: Final phase regression + manual checkpoint before commit</name>
  <what-built>
    Phase 6 deliverables 1-4 wired across plans 06-01..06-08:
    - 2 new Settings (embedding_provider, local_embedding_base_url) + 1 default flip (llm_provider_fallback_enabled=True)
    - pyproject.toml with [tool.pytest.ini_options] markers list (slow)
    - Provider-branched EmbeddingService.__init__ + 3 unit tests
    - thread_id correlation in detect_entities + redaction_service + egress + llm_provider + missed_scan (Plan 06-04, 5 files)
    - 6-word title-gen template fallback in chat.py (Plan 06-05)
    - PERF-02 latency regression test (slow, real Presidio, Plan 06-06)
    - PERF-04 graceful-degradation tests (entity-resolution / missed-scan / title-gen, Plan 06-07)
    - OBS-02 / OBS-03 caplog tests + admin-toggle default check + B4 forbidden-tokens regression (this plan, Task 1)
    - CLAUDE.md gotcha note for EMBED-02 deployer-managed re-embed (this plan, Task 2)
  </what-built>
  <how-to-verify>
    Run, in order, on a clean shell with `cd backend && source venv/bin/activate` already executed:

    1. **Default unit-test run** (must show pre-existing 195+ tests + Phase 6 new tests passing; slow test excluded):
       ```
       pytest tests/unit -m 'not slow' -v --tb=short -q 2>&1 | tail -10
       pytest tests/services/redaction -m 'not slow' -v --tb=short 2>&1 | tail -10
       ```
       Both should report `XX passed` with zero failures.

    2. **Slow-marked PERF-02 test** (must complete <500ms, or <2000ms on slow CI):
       ```
       pytest tests/services/redaction/test_perf_latency.py -m slow -v --tb=short 2>&1 | tail -10
       ```
       Expect `1 passed` and the printed elapsed_ms below 500.

    3. **Phase 5 integration regression** (tool/sub-agent invariants must still hold):
       ```
       pytest tests/api -v --tb=short -k "phase5" 2>&1 | tail -10
       ```
       Must show no new failures.

    4. **Backend import check**:
       ```
       cd backend && python -c "from app.main import app; print('OK')"
       ```
       Must print `OK`.

    5. **Docs gate**:
       ```
       grep -nE "EMBEDDING_PROVIDER" CLAUDE.md
       ```
       Must show the new gotcha bullet.

    6. **Manual privacy-invariant smoke** (operator inspection — confirms SC#5):
       Open `backend/app/services/redaction_service.py` and `backend/app/services/llm_provider.py`. Confirm by eye that no `logger.debug` / `logger.info` / `logger.warning` line interpolates raw `text`, `real_value`, or `surrogate_value` — the only new fields are `thread_id=` (UUID, non-PII) and the existing counts/types/hashes. The B4 invariant must still hold. Note: the automated B4 forbidden-tokens regression test (`TestB4LogPrivacyForbiddenTokens`) covers this invariant programmatically; the manual inspection is a defense-in-depth check.

    7. **No-new-migration gate**:
       ```
       find backend/migrations -name '*.sql' -newer .planning/phases/06-embedding-provider-production-hardening/06-CONTEXT.md
       ```
       Must return zero lines (D-P6-01: Phase 6 introduces no migrations).

    Confirm each step output. If all pass, commit per Plan 06-08 Output instructions; if any fail, stop and surface the failure for review.
  </how-to-verify>
  <resume-signal>Type "approved" to mark phase 6 verified, or describe failures (e.g. "PERF-02 test reports 612ms - needs profiling").</resume-signal>
</task>

</tasks>

<verification>
1. `cd backend && source venv/bin/activate && pytest tests/services/redaction/test_thread_id_logging.py -v --tb=short` — 8/8 OBS + B4 tests pass.
2. `cd backend && source venv/bin/activate && pytest tests/ -m 'not slow' -v --tb=short -q 2>&1 | tail -10` — full pre-existing + Phase 6 non-slow suite passes.
3. `cd backend && source venv/bin/activate && pytest tests/services/redaction/test_perf_latency.py -m slow -v --tb=short 2>&1 | tail -10` — PERF-02 test passes.
4. `grep -nE "EMBEDDING_PROVIDER" CLAUDE.md` — confirms the docs note is present.
5. `find backend/migrations -name '*.sql' -newer .planning/phases/06-embedding-provider-production-hardening/06-CONTEXT.md | wc -l` returns `0` — D-P6-01 invariant.
</verification>

<success_criteria>
- 8 caplog regression tests in test_thread_id_logging.py pass (3 OBS-02 + 2 OBS-03 + 2 admin-toggle + 1 B4 forbidden-tokens)
- Real ConversationRegistry / EntityMapping constructor signatures used (`thread_id`, `rows`); Pydantic v2 `Settings.model_fields[...]` API used (NOT v1 `__fields__`)
- B4 forbidden-tokens regression test (T-06-04-1 mitigation) covers PERSON / EMAIL / PHONE entity types and asserts no real_value or surrogate substring leaks across the 4 modified log call sites
- CLAUDE.md Gotchas section gains 1 new bullet about EMBEDDING_PROVIDER + no-auto-re-embed (D-P6-04)
- All pre-existing 195+ unit + Phase 5 integration + Phase 6 new (non-slow) tests pass
- PERF-02 slow test passes when explicitly invoked with `-m slow`
- Backend imports cleanly
- No new migrations introduced (D-P6-01 invariant)
- Manual privacy-invariant inspection (Task 3 step 6) confirms B4 — no raw values in any log
- Operator approves phase completion
</success_criteria>

<output>
After completion (and the operator's "approved" signal in Task 3), create `.planning/phases/06-embedding-provider-production-hardening/06-08-SUMMARY.md` documenting:
- Output of `pytest tests/services/redaction/test_thread_id_logging.py -v --tb=short`
- Output of `pytest tests/ -m 'not slow' -v --tb=short -q | tail -10` (final regression baseline)
- Output of `pytest tests/services/redaction/test_perf_latency.py -m slow -v --tb=short | tail -10` (PERF-02 timing record)
- Verbatim diff of CLAUDE.md (just the new bullet)
- Confirmation `find backend/migrations -name '*.sql' -newer ...` returns zero lines (D-P6-01)
- The operator's "approved" signal (or list of follow-ups before commit)
</output>
</content>
