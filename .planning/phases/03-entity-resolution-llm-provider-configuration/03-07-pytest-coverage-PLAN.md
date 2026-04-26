---
phase: 03-entity-resolution-llm-provider-configuration
plan: 07
type: execute
wave: 6
depends_on: [04, 05, 06]
files_modified:
  - backend/tests/unit/test_egress_filter.py
  - backend/tests/unit/test_llm_provider_client.py
  - backend/tests/api/test_resolution_and_provider.py
autonomous: true
requirements_addressed: [RESOLVE-01, RESOLVE-02, RESOLVE-03, RESOLVE-04, PROVIDER-01, PROVIDER-04, PROVIDER-06, PROVIDER-07]
must_haves:
  truths:
    - "All 5 Phase 3 ROADMAP success criteria have at least one test class each"
    - "D-66 egress-filter unit matrix exhaustive: exact-casefold trip, word-boundary preservation, multi-word match, registry-only, provisional-only, empty-empty, log-content invariant"
    - "Cloud-mode call WITH a registered real value triggers _EgressBlocked → algorithmic fallback (SC#2)"
    - "Local-mode call passes raw real names through to the local LLM mock (SC#3); egress filter NEVER invoked"
    - "Non-PERSON entities (EMAIL, PHONE, URL) NEVER appear in the resolution-LLM payload (SC#4 / RESOLVE-04)"
    - "PATCH /admin/settings with llm_provider=cloud → wait for cache TTL → next _resolve_provider call returns 'cloud' (SC#5)"
    - "Phase 1 + Phase 2 + Phase 3 combined regression: ≥45 tests pass against live Supabase project qedhulpfezucnfadlfiz (39 baseline + ~6+ new Phase 3 tests)"
    - "B4 / D-55 caplog invariant — no raw PII appears in any captured log line during any Phase 3 test"
  artifacts:
    - path: "backend/tests/unit/test_egress_filter.py"
      provides: "Pure-function table-driven tests for egress_filter (D-66 exhaustive matrix)"
      min_lines: 90
    - path: "backend/tests/unit/test_llm_provider_client.py"
      provides: "Unit tests for _resolve_provider + LLMProviderClient with AsyncOpenAI mocked"
      min_lines: 120
    - path: "backend/tests/api/test_resolution_and_provider.py"
      provides: "Integration test classes TestSC1..TestSC5 covering all 5 ROADMAP SCs"
      min_lines: 200
  key_links:
    - from: "backend/tests/api/test_resolution_and_provider.py"
      to: "live entity_registry table"
      via: "redact_text → upsert_delta with variant rows"
      pattern: "client\\.table\\(['\"]entity_registry['\"]\\)"
    - from: "backend/tests/api/test_resolution_and_provider.py"
      to: "system_settings new columns"
      via: "PATCH /admin/settings + cache TTL probe"
      pattern: "system_settings"
    - from: "backend/tests/unit/test_llm_provider_client.py"
      to: "openai.AsyncOpenAI"
      via: "AsyncMock patches at module level"
      pattern: "AsyncMock|patch"
---

<objective>
Cover all 5 Phase 3 ROADMAP success criteria + the D-66 egress-filter unit matrix + the D-65 LLM provider client unit suite. Closes the Phase 3 verification loop.

Purpose: Wave 6 (final) — test coverage gates ROADMAP marking phase 3 as complete. SC#5 (admin propagation within 60s) MUST exercise the live cache TTL; SC#1 (multi-variant clustering) MUST hit the live entity_registry to confirm sub-surrogate variant rows persist.

Output: Three new/extended test files. Combined ≥45 passing tests.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/03-entity-resolution-llm-provider-configuration/03-CONTEXT.md
@.planning/phases/03-entity-resolution-llm-provider-configuration/03-PATTERNS.md
@CLAUDE.md
@backend/tests/conftest.py
@backend/tests/api/test_redaction_registry.py
@backend/tests/unit/test_conversation_registry.py
@backend/app/services/redaction/egress.py
@backend/app/services/llm_provider.py
@backend/app/services/redaction_service.py
@backend/app/services/redaction/clustering.py

<interfaces>
<!-- Existing primitives this plan uses. Read once; no codebase exploration needed. -->

From backend/tests/conftest.py (Phase 2 — existing fixtures Phase 3 reuses):
- `test_user_id` (session-scoped) — supabase admin user.
- `fresh_thread_id` — per-test threads-row INSERT + ON DELETE CASCADE teardown.
- `empty_registry` — `ConversationRegistry.load(fresh_thread_id)`.
- `_reset_thread_locks` (autouse) — clears `_thread_locks` between tests + rebinds `_thread_locks_master`.

These fixtures DO NOT need modification for Phase 3. Reuse them.

From backend/tests/api/test_redaction_registry.py (Phase 2 — pattern for live-DB integration tests):
- One test class per SC; each class has ≥1 `@pytest.mark.asyncio` method.
- Live Supabase project `qedhulpfezucnfadlfiz` is the DB target; service-role client.
- Hard-redact + B4 + asyncio.gather race patterns established here.

From backend/app/services/redaction/egress.py (Plan 03-03 Task 3 output):
- `egress_filter(payload, registry, provisional)` — pure function.
- `EgressResult(tripped, match_count, entity_types, match_hashes)` — frozen.
- `_EgressBlocked(Exception)` — internal-only.

From backend/app/services/llm_provider.py (Plan 03-04 output):
- `LLMProviderClient.call(feature, messages, registry=None, provisional_surrogates=None) -> dict`.
- `_resolve_provider(feature) -> tuple[provider, source]`.
- Module-level `_clients: dict[str, AsyncOpenAI]` (lazy cache).

From backend/app/services/redaction_service.py (Plan 03-05 output):
- `RedactionService.redact_text(text, thread_id)` dispatches on `entity_resolution_mode`.
- `_EgressBlocked` caught locally → algorithmic fallback.

From backend/app/services/system_settings_service.py:
- 60s TTL cache; PATCH /admin/settings invalidates the cache. SC#5 test sleeps just past the TTL window OR explicitly invalidates.

Pytest conventions (project precedent):
- `pytest.mark.asyncio` for async tests.
- `monkeypatch` for env-var manipulation.
- `caplog` for log-capture invariant assertions.
- Fixtures live in `conftest.py`; per-test isolation via the autouse reset.
- TEST_EMAIL / TEST_PASSWORD / API_BASE_URL env vars used for live calls (CLAUDE.md).
</interfaces>
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: Write backend/tests/unit/test_egress_filter.py — D-66 exhaustive matrix</name>
  <files>backend/tests/unit/test_egress_filter.py</files>
  <read_first>
    - backend/tests/unit/test_conversation_registry.py (Phase 2 — pure unit-test pattern, no DB)
    - backend/app/services/redaction/egress.py (Plan 03-03 Task 3 output — egress_filter signature)
    - backend/app/services/redaction/registry.py (ConversationRegistry + EntityMapping shapes — needed to build a stub registry for tests)
    - .planning/phases/03-entity-resolution-llm-provider-configuration/03-CONTEXT.md D-66
    - .planning/phases/03-entity-resolution-llm-provider-configuration/03-PATTERNS.md §"backend/tests/unit/test_egress_filter.py"
  </read_first>
  <action>
Create `backend/tests/unit/test_egress_filter.py`. Pure unit tests against the `egress_filter` pure function — NO DB, NO mocks of AsyncOpenAI. Use a tiny stub `ConversationRegistry` (or a real one with no `load` call) to feed `entries()`.

The D-66 matrix is non-negotiable; every test below MUST exist.

File content:

```python
"""D-66 egress filter exhaustive test matrix (PROVIDER-04, NFR-2).

These are PURE unit tests against the egress_filter() function. No DB, no
mocks of AsyncOpenAI — just inputs in, EgressResult out. The log-content
invariant (B4 / D-55) is asserted via caplog.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import pytest

from app.services.redaction.egress import (
    EgressResult,
    _EgressBlocked,
    _hash8,
    egress_filter,
)


# --- Stub registry for unit tests (no DB, no async). ---


@dataclass(frozen=True)
class _StubMapping:
    entity_type: str
    real_value: str


class _StubRegistry:
    """Minimal duck-typed stand-in for ConversationRegistry.entries()."""
    def __init__(self, mappings):
        self._mappings = list(mappings)
    def entries(self):
        return self._mappings


# --- D-66 matrix. ---


class TestEgressFilter:
    """D-66 exhaustive unit matrix."""

    def test_exact_match_casefold_trips(self):
        """A registered value matching the payload (case-insensitive) trips."""
        reg = _StubRegistry([_StubMapping("PERSON", "John Doe")])
        result = egress_filter("Hello JOHN DOE!", reg, None)
        assert result.tripped is True
        assert result.match_count == 1
        assert "PERSON" in result.entity_types

    def test_word_boundary_johnson_does_not_trip_on_john(self):
        """Word boundary preservation — "Johnson" must NOT match registered "John"."""
        reg = _StubRegistry([_StubMapping("PERSON", "John")])
        result = egress_filter("Talked to Johnson today", reg, None)
        assert result.tripped is False
        assert result.match_count == 0

    def test_multi_word_value_trips_on_substring(self):
        """A multi-word registered value matches as a phrase substring."""
        reg = _StubRegistry([_StubMapping("PERSON", "Bambang Sutrisno")])
        result = egress_filter(
            "The contract was signed by bambang sutrisno yesterday.",
            reg, None,
        )
        assert result.tripped is True
        assert "PERSON" in result.entity_types

    def test_registry_only_path_no_provisional(self):
        """Only registry rows; no provisional set."""
        reg = _StubRegistry([_StubMapping("EMAIL_ADDRESS", "alice@example.com")])
        result = egress_filter(
            "Send an email to alice@example.com please.",
            reg, None,
        )
        assert result.tripped is True
        assert "EMAIL_ADDRESS" in result.entity_types

    def test_provisional_only_path_no_registry_rows(self):
        """No registry rows; only in-flight provisional set (D-56 first-turn case)."""
        reg = _StubRegistry([])
        provisional = {"Carla Wijaya": "Mock_Surrogate_Name_001"}
        result = egress_filter(
            "Hi Carla Wijaya, your invoice is ready.",
            reg, provisional,
        )
        assert result.tripped is True
        assert "PERSON" in result.entity_types

    def test_empty_inputs_no_trip(self):
        """Empty registry + empty provisional → no trip."""
        reg = _StubRegistry([])
        result = egress_filter("Some innocuous text.", reg, None)
        assert result.tripped is False
        assert result.match_count == 0
        assert result.entity_types == []
        assert result.match_hashes == []

    def test_match_hashes_are_8char_sha256(self):
        """D-55: match_hashes are 8-char SHA-256 hashes; not raw values."""
        reg = _StubRegistry([_StubMapping("PERSON", "John Doe")])
        result = egress_filter("hello john doe", reg, None)
        assert result.tripped is True
        for h in result.match_hashes:
            assert isinstance(h, str)
            assert len(h) == 8
            int(h, 16)  # raises ValueError if not hex
        # The hash for "John Doe" should be in the result.
        assert _hash8("John Doe") in result.match_hashes

    def test_log_content_invariant_no_raw_values(self, caplog):
        """B4 / D-55: trip log MUST NOT contain raw value or first-N-chars of value."""
        reg = _StubRegistry([_StubMapping("PERSON", "John Doe")])
        with caplog.at_level(logging.WARNING, logger="app.services.redaction.egress"):
            egress_filter("hello john doe", reg, None)
        log_text = "\n".join(rec.getMessage() for rec in caplog.records)
        # The trip log should appear (only the WARNING-level line).
        assert "egress_filter_blocked" in log_text
        # The raw value MUST NOT appear (case-insensitive substring check).
        assert "john doe" not in log_text.lower()
        assert "John Doe" not in log_text
        # The 8-char hash MUST appear (forensic correlation).
        assert _hash8("John Doe") in log_text

    def test_multiple_distinct_matches_all_counted(self):
        """Multiple distinct matches aggregate via match_count + entity_types + match_hashes."""
        reg = _StubRegistry([
            _StubMapping("PERSON", "John Doe"),
            _StubMapping("EMAIL_ADDRESS", "john.doe@example.com"),
        ])
        result = egress_filter(
            "John Doe sent an email from john.doe@example.com",
            reg, None,
        )
        assert result.tripped is True
        assert result.match_count == 2
        assert sorted(result.entity_types) == ["EMAIL_ADDRESS", "PERSON"]
        assert len(result.match_hashes) == 2

    def test_egress_blocked_carries_result(self):
        """_EgressBlocked carries the EgressResult instance for caller inspection."""
        reg = _StubRegistry([_StubMapping("PERSON", "John Doe")])
        result = egress_filter("John Doe is here", reg, None)
        try:
            raise _EgressBlocked(result)
        except _EgressBlocked as exc:
            assert exc.result is result
            assert exc.result.tripped is True
            assert exc.result.match_count == 1
```

Run the test:
```bash
cd backend && source venv/bin/activate && pytest tests/unit/test_egress_filter.py -v
```
Expected: 10 passing tests, 0 failures.
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pytest tests/unit/test_egress_filter.py -v 2>&1 | tail -10 | grep -E "[0-9]+ passed"</automated>
  </verify>
  <acceptance_criteria>
    - File `backend/tests/unit/test_egress_filter.py` exists.
    - Contains class `TestEgressFilter`.
    - Contains the following test methods (D-66 matrix verbatim): `test_exact_match_casefold_trips`, `test_word_boundary_johnson_does_not_trip_on_john`, `test_multi_word_value_trips_on_substring`, `test_registry_only_path_no_provisional`, `test_provisional_only_path_no_registry_rows`, `test_empty_inputs_no_trip`, `test_log_content_invariant_no_raw_values`, plus at least 2 additional tests for hash-format and multi-match aggregation.
    - The log-content invariant test uses `caplog.at_level(logging.WARNING, logger="app.services.redaction.egress")` and asserts `"john doe" not in log_text.lower()` AND `_hash8("John Doe") in log_text`.
    - `pytest tests/unit/test_egress_filter.py -v` shows ≥10 passing tests, 0 failures.
  </acceptance_criteria>
  <done>D-66 exhaustive unit matrix shipped; 10+ tests pass; B4 log invariant verified for the egress filter.</done>
</task>

<task type="auto" tdd="false">
  <name>Task 2: Write backend/tests/unit/test_llm_provider_client.py — _resolve_provider + cloud egress + fallback</name>
  <files>backend/tests/unit/test_llm_provider_client.py</files>
  <read_first>
    - backend/tests/unit/test_egress_filter.py (Plan 03-07 Task 1 — same unit-test style with stub registries)
    - backend/app/services/llm_provider.py (Plan 03-04 — LLMProviderClient + _resolve_provider signatures)
    - backend/app/services/redaction/egress.py (egress_filter behaviour the cloud branch invokes)
    - .planning/phases/03-entity-resolution-llm-provider-configuration/03-CONTEXT.md D-49, D-51, D-52, D-65
    - .planning/phases/03-entity-resolution-llm-provider-configuration/03-PATTERNS.md §"backend/tests/unit/test_llm_provider_client.py"
  </read_first>
  <action>
Create `backend/tests/unit/test_llm_provider_client.py`. Unit tests with `AsyncOpenAI` mocked at the module level (D-65 — CI never hits a real Ollama / LM Studio / OpenAI).

File content:

```python
"""Unit tests for LLMProviderClient + _resolve_provider (D-49, D-51, D-52, D-65)."""
from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.llm_provider import (
    LLMProviderClient,
    _Feature,  # noqa: F401  (import for module sanity)
    _get_client,
    _resolve_provider,
)
from app.services.redaction.egress import _EgressBlocked


# --- Stub registry (duck-typed) ---


@dataclass(frozen=True)
class _StubMapping:
    entity_type: str
    real_value: str


class _StubRegistry:
    def __init__(self, mappings):
        self._mappings = list(mappings)
    def entries(self):
        return self._mappings


@pytest.fixture(autouse=True)
def _clear_client_cache():
    """Clear the module-level AsyncOpenAI cache between tests (D-50)."""
    from app.services import llm_provider
    llm_provider._clients.clear()
    yield
    llm_provider._clients.clear()


# --- _resolve_provider — D-51 resolution order. ---


class TestResolveProvider:
    """D-51: feature_env > feature_db > global_env > global_db > default."""

    def test_default_local_when_nothing_set(self, monkeypatch):
        monkeypatch.delenv("ENTITY_RESOLUTION_LLM_PROVIDER", raising=False)
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        with patch("app.services.llm_provider.get_system_settings", return_value={}):
            provider, source = _resolve_provider("entity_resolution")
        assert (provider, source) == ("local", "default")

    def test_feature_env_wins_over_db(self, monkeypatch):
        monkeypatch.setenv("ENTITY_RESOLUTION_LLM_PROVIDER", "cloud")
        with patch("app.services.llm_provider.get_system_settings",
                   return_value={"entity_resolution_llm_provider": "local",
                                 "llm_provider": "local"}):
            provider, source = _resolve_provider("entity_resolution")
        assert (provider, source) == ("cloud", "feature_env")

    def test_feature_db_wins_over_global_env(self, monkeypatch):
        monkeypatch.delenv("ENTITY_RESOLUTION_LLM_PROVIDER", raising=False)
        monkeypatch.setenv("LLM_PROVIDER", "local")
        with patch("app.services.llm_provider.get_system_settings",
                   return_value={"entity_resolution_llm_provider": "cloud",
                                 "llm_provider": "local"}):
            provider, source = _resolve_provider("entity_resolution")
        assert (provider, source) == ("cloud", "feature_db")

    def test_global_env_wins_over_global_db(self, monkeypatch):
        monkeypatch.delenv("ENTITY_RESOLUTION_LLM_PROVIDER", raising=False)
        monkeypatch.setenv("LLM_PROVIDER", "cloud")
        with patch("app.services.llm_provider.get_system_settings",
                   return_value={"llm_provider": "local"}):
            provider, source = _resolve_provider("entity_resolution")
        assert (provider, source) == ("cloud", "global_env")

    def test_global_db_used_when_no_env(self, monkeypatch):
        monkeypatch.delenv("ENTITY_RESOLUTION_LLM_PROVIDER", raising=False)
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        with patch("app.services.llm_provider.get_system_settings",
                   return_value={"llm_provider": "cloud"}):
            provider, source = _resolve_provider("entity_resolution")
        assert (provider, source) == ("cloud", "global_db")

    def test_invalid_env_value_falls_through(self, monkeypatch):
        """Bad enum at any layer is treated as unset (defense in depth)."""
        monkeypatch.setenv("ENTITY_RESOLUTION_LLM_PROVIDER", "aws_bedrock")
        with patch("app.services.llm_provider.get_system_settings", return_value={}):
            provider, source = _resolve_provider("entity_resolution")
        assert (provider, source) == ("local", "default")


# --- LLMProviderClient — local mode (no egress filter). ---


class TestProviderClientLocalMode:
    """Local mode bypasses egress filter; sees raw real names per FR-9.2."""

    @pytest.mark.asyncio
    async def test_local_call_does_not_invoke_egress_filter(self, monkeypatch):
        # Force local provider.
        monkeypatch.setenv("ENTITY_RESOLUTION_LLM_PROVIDER", "local")

        # Mock the AsyncOpenAI client at the lazy-cache layer.
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content='{"clusters": []}'))]
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch("app.services.llm_provider._get_client", return_value=mock_client) as get_client_mock, \
             patch("app.services.llm_provider.egress_filter") as egress_mock:
            client = LLMProviderClient()
            registry = _StubRegistry([_StubMapping("PERSON", "John Doe")])
            result = await client.call(
                feature="entity_resolution",
                messages=[{"role": "user", "content": "hello John Doe"}],
                registry=registry,
                provisional_surrogates=None,
            )
            # Local mode never invokes the egress filter.
            assert egress_mock.call_count == 0
            # The mocked SDK call WAS invoked.
            assert mock_client.chat.completions.create.call_count == 1
            assert isinstance(result, dict)


# --- LLMProviderClient — cloud mode + egress filter trip. ---


class TestProviderClientCloudMode:
    """Cloud mode wraps payload with egress filter; raises _EgressBlocked on trip."""

    @pytest.mark.asyncio
    async def test_cloud_egress_trip_raises_egress_blocked_pre_call(self, monkeypatch):
        monkeypatch.setenv("ENTITY_RESOLUTION_LLM_PROVIDER", "cloud")

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock()

        registry = _StubRegistry([_StubMapping("PERSON", "John Doe")])

        with patch("app.services.llm_provider._get_client", return_value=mock_client):
            client = LLMProviderClient()
            with pytest.raises(_EgressBlocked) as excinfo:
                await client.call(
                    feature="entity_resolution",
                    messages=[{"role": "user", "content": "Hello John Doe!"}],
                    registry=registry,
                    provisional_surrogates=None,
                )
        # The SDK call was NEVER made (the trip aborted before the cloud call).
        assert mock_client.chat.completions.create.call_count == 0
        # The EgressResult is carried by the exception.
        assert excinfo.value.result.tripped is True
        assert excinfo.value.result.match_count == 1

    @pytest.mark.asyncio
    async def test_cloud_clean_payload_passes_through(self, monkeypatch):
        monkeypatch.setenv("ENTITY_RESOLUTION_LLM_PROVIDER", "cloud")

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content='{"clusters": []}'))]
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        # Empty registry + empty provisional → no egress trip.
        registry = _StubRegistry([])

        with patch("app.services.llm_provider._get_client", return_value=mock_client):
            client = LLMProviderClient()
            result = await client.call(
                feature="entity_resolution",
                messages=[{"role": "user", "content": "Hello world"}],
                registry=registry,
                provisional_surrogates=None,
            )
        assert mock_client.chat.completions.create.call_count == 1
        assert isinstance(result, dict)


# --- LLMProviderClient — fallback boundary (D-52). ---


class TestProviderClientFallback:
    """D-52: network/5xx/invalid SDK exceptions PROPAGATE OUT — caller decides on fallback."""

    @pytest.mark.asyncio
    async def test_5xx_propagates_to_caller(self, monkeypatch):
        monkeypatch.setenv("ENTITY_RESOLUTION_LLM_PROVIDER", "cloud")

        class _SimulatedSDKError(Exception):
            pass

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=_SimulatedSDKError("simulated 503"))

        with patch("app.services.llm_provider._get_client", return_value=mock_client):
            client = LLMProviderClient()
            with pytest.raises(_SimulatedSDKError):
                await client.call(
                    feature="entity_resolution",
                    messages=[{"role": "user", "content": "anything"}],
                    registry=_StubRegistry([]),
                    provisional_surrogates=None,
                )

    @pytest.mark.asyncio
    async def test_lazy_cache_returns_same_instance(self, monkeypatch):
        """D-50: per-provider AsyncOpenAI clients cached in module-level dict."""
        c1 = _get_client("local")
        c2 = _get_client("local")
        assert c1 is c2
```

Run the test:
```bash
cd backend && source venv/bin/activate && pytest tests/unit/test_llm_provider_client.py -v
```
Expected: ≥10 passing tests, 0 failures.
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pytest tests/unit/test_llm_provider_client.py -v 2>&1 | tail -10 | grep -E "[0-9]+ passed"</automated>
  </verify>
  <acceptance_criteria>
    - File `backend/tests/unit/test_llm_provider_client.py` exists.
    - Contains class `TestResolveProvider` with at least 6 methods covering each D-51 layer (default, feature_env, feature_db, global_env, global_db, invalid-value-fall-through).
    - Contains class `TestProviderClientLocalMode` with `test_local_call_does_not_invoke_egress_filter` asserting `egress_mock.call_count == 0`.
    - Contains class `TestProviderClientCloudMode` with `test_cloud_egress_trip_raises_egress_blocked_pre_call` asserting `mock_client.chat.completions.create.call_count == 0` (the trip aborts BEFORE the SDK call).
    - Contains `test_cloud_clean_payload_passes_through` asserting the SDK call IS made when no value matches.
    - Contains class `TestProviderClientFallback` with `test_5xx_propagates_to_caller` (SDK exception propagates — D-52 caller-side fallback).
    - Contains `test_lazy_cache_returns_same_instance` (D-50).
    - Autouse fixture `_clear_client_cache` clears `llm_provider._clients` between tests.
    - `pytest tests/unit/test_llm_provider_client.py -v` shows ≥10 passing tests, 0 failures.
  </acceptance_criteria>
  <done>D-65 LLM provider client unit suite shipped; 10+ tests pass; D-51 resolution order + D-49 egress wrapping + D-52 fallback all covered.</done>
</task>

<task type="auto" tdd="false">
  <name>Task 3: Write backend/tests/api/test_resolution_and_provider.py — TestSC1..TestSC5 against live DB</name>
  <files>backend/tests/api/test_resolution_and_provider.py</files>
  <read_first>
    - backend/tests/api/test_redaction_registry.py (Phase 2 — pattern: one test class per SC, live DB target, asyncio.gather race idiom)
    - backend/tests/conftest.py (existing fixtures `test_user_id`, `fresh_thread_id`, `empty_registry`, `_reset_thread_locks`)
    - backend/app/services/redaction_service.py (Plan 03-05 — redact_text dispatch on entity_resolution_mode)
    - backend/app/services/llm_provider.py (Plan 03-04 — for AsyncOpenAI mock targets)
    - .planning/phases/03-entity-resolution-llm-provider-configuration/03-CONTEXT.md D-64, D-65 (test scope)
    - .planning/phases/03-entity-resolution-llm-provider-configuration/03-PATTERNS.md §"backend/tests/api/test_resolution_and_provider.py"
    - .planning/ROADMAP.md §"Phase 3 Success Criteria" (the 5 SCs verbatim)
    - CLAUDE.md "Testing" — TEST_EMAIL / TEST_PASSWORD / API_BASE_URL env vars + supabase project qedhulpfezucnfadlfiz
  </read_first>
  <action>
Create `backend/tests/api/test_resolution_and_provider.py`. Five test classes, one per SC. Hit the live DB for SC#1 (verifies variant rows persist) and SC#5 (verifies cache propagation). SC#2-4 use mocks of `AsyncOpenAI` — never hit a real cloud LLM in CI.

File content (the test class skeletons + the live-DB integration assertions; the executor refines specific Presidio model behaviour using Phase 2's three Rule-1 deviations memo from STATE.md L29):

```python
"""Phase 3 ROADMAP success-criteria coverage (D-64).

SC#1: algorithmic clustering — 4 variants collapse to 1 surrogate (live DB).
SC#2: cloud LLM mode + payload-with-real-value → egress trip → algorithmic fallback.
SC#3: local LLM mode sees raw real names; egress filter NEVER invoked.
SC#4: non-PERSON entities (EMAIL, PHONE, URL) NEVER appear in resolution-LLM payload.
SC#5: PATCH /admin/settings llm_provider=cloud → cache TTL → next _resolve_provider returns 'cloud'.

Live target: Supabase project qedhulpfezucnfadlfiz. Cloud LLM calls are mocked
at the AsyncOpenAI client level (D-65) — CI never hits a real cloud endpoint.
"""
from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.database import get_supabase_client
from app.services.llm_provider import _resolve_provider
from app.services.redaction.egress import _EgressBlocked
from app.services.redaction_service import get_redaction_service
from app.services.system_settings_service import get_system_settings, update_system_settings


# --- SC#1: algorithmic clustering of 4 variants → 1 surrogate (live DB). ---


class TestSC1_AlgorithmicClustering:
    """Bambang Sutrisno / Pak Bambang / Sutrisno / Bambang collapse to one cluster."""

    @pytest.mark.asyncio
    async def test_four_variants_collapse_to_one_canonical(self, fresh_thread_id, monkeypatch):
        monkeypatch.setenv("ENTITY_RESOLUTION_MODE", "algorithmic")
        # Force algorithmic mode through both env + cache invalidation.
        await update_system_settings({"entity_resolution_mode": "algorithmic"})

        service = get_redaction_service()
        text = (
            "Bambang Sutrisno menandatangani kontrak. "
            "Pak Bambang setuju dengan klausul 5. "
            "Sutrisno akan meninjau revisi."
        )
        result = await service.redact_text(text, thread_id=fresh_thread_id)
        # Single PERSON surrogate across the three multi/single-token mentions.
        person_surrogates_in_map = {
            v for k, v in result.entity_map.items()
            if any(token in k for token in ("Bambang", "Sutrisno"))
        }
        assert len(person_surrogates_in_map) == 1, (
            f"expected 1 cluster surrogate, got {len(person_surrogates_in_map)}; "
            f"map={result.entity_map}"
        )
        # Variant rows persisted in entity_registry.
        client = get_supabase_client()
        rows = client.table("entity_registry").select("real_value, surrogate_value, entity_type").eq(
            "thread_id", fresh_thread_id,
        ).eq("entity_type", "PERSON").execute().data
        # At least 3 variant rows (canonical + first-only + last-only); honorific-prefixed when honorific stripped.
        assert len(rows) >= 3, f"expected ≥3 variant rows, got {len(rows)}: {rows}"
        # All PERSON rows share the same surrogate (D-48 invariant).
        surrogates = {r["surrogate_value"] for r in rows}
        assert len(surrogates) == 1, (
            f"variant rows should share one surrogate; got {surrogates}"
        )


# --- SC#2: cloud LLM mode + egress trip → algorithmic fallback. ---


class TestSC2_CloudEgressFallback:
    """cloud + payload-with-real-value → trip → algorithmic fallback (no real value sent)."""

    @pytest.mark.asyncio
    async def test_egress_trip_falls_back_to_algorithmic(self, fresh_thread_id, monkeypatch, caplog):
        monkeypatch.setenv("ENTITY_RESOLUTION_MODE", "llm")
        monkeypatch.setenv("ENTITY_RESOLUTION_LLM_PROVIDER", "cloud")
        # Pre-seed the registry with a real value so the cloud payload trips on it.
        client = get_supabase_client()
        client.table("entity_registry").insert({
            "thread_id": fresh_thread_id,
            "real_value": "John Doe",
            "real_value_lower": "john doe",
            "surrogate_value": "Mock_Surrogate_42",
            "entity_type": "PERSON",
        }).execute()

        # Mock the AsyncOpenAI client — the cloud SDK call MUST NOT happen.
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock()

        with patch("app.services.llm_provider._get_client", return_value=mock_client):
            service = get_redaction_service()
            text = "John Doe has been reassigned. Maria Santos will lead the project."
            result = await service.redact_text(text, thread_id=fresh_thread_id)
        # The SDK call was NEVER made (egress trip aborted pre-call).
        assert mock_client.chat.completions.create.call_count == 0
        # The fallback path produced a result — the chat loop did not crash.
        assert result.anonymized_text is not None
        assert "John Doe" not in result.anonymized_text  # the real value was redacted
        # The fallback log line was emitted with no raw values.
        log_text = "\n".join(rec.getMessage() for rec in caplog.records)
        assert "John Doe" not in log_text  # B4 invariant


# --- SC#3: local LLM mode sees raw real names; egress filter NEVER invoked. ---


class TestSC3_LocalModeBypassesEgress:
    """local mode + LLM resolution; egress filter NEVER invoked."""

    @pytest.mark.asyncio
    async def test_local_mode_bypasses_egress_filter(self, fresh_thread_id, monkeypatch):
        monkeypatch.setenv("ENTITY_RESOLUTION_MODE", "llm")
        monkeypatch.setenv("ENTITY_RESOLUTION_LLM_PROVIDER", "local")

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content='{"clusters": []}'))]
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch("app.services.llm_provider._get_client", return_value=mock_client) as get_client_mock, \
             patch("app.services.llm_provider.egress_filter") as egress_mock:
            service = get_redaction_service()
            text = "Bambang Sutrisno menandatangani kontrak hari ini."
            await service.redact_text(text, thread_id=fresh_thread_id)
        # Local mode → egress filter never called.
        assert egress_mock.call_count == 0


# --- SC#4: non-PERSON entities NEVER reach the resolution LLM. ---


class TestSC4_NonPersonNeverReachLLM:
    """SC#4 / RESOLVE-04: emails/phones/URLs go through normalize-only path."""

    @pytest.mark.asyncio
    async def test_resolution_payload_contains_only_person_strings(self, fresh_thread_id, monkeypatch):
        monkeypatch.setenv("ENTITY_RESOLUTION_MODE", "llm")
        monkeypatch.setenv("ENTITY_RESOLUTION_LLM_PROVIDER", "local")

        captured_payloads = []

        async def _capture(*args, **kwargs):
            payload = kwargs.get("messages") or args[1] if len(args) > 1 else None
            captured_payloads.append(payload)
            mock_response = MagicMock()
            mock_response.choices = [MagicMock(message=MagicMock(content='{"clusters": []}'))]
            return mock_response

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=_capture)

        with patch("app.services.llm_provider._get_client", return_value=mock_client):
            service = get_redaction_service()
            text = (
                "Bambang Sutrisno will email alice@example.com from +62-812-3456-7890. "
                "Visit https://contoh.id/dokumen for the contract."
            )
            await service.redact_text(text, thread_id=fresh_thread_id)
        # Non-PERSON values MUST NOT appear in any payload sent to the LLM.
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


# --- SC#5: admin-UI provider switch propagates within cache TTL. ---


class TestSC5_AdminUIProviderPropagation:
    """PATCH /admin/settings llm_provider=cloud → cache TTL → next _resolve_provider returns 'cloud'."""

    @pytest.mark.asyncio
    async def test_provider_switch_propagates_within_cache_window(self, monkeypatch):
        # Clear env to force the resolver to hit the DB.
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        monkeypatch.delenv("ENTITY_RESOLUTION_LLM_PROVIDER", raising=False)

        # Set initial value via update_system_settings (invalidates cache).
        await update_system_settings({"llm_provider": "local"})
        provider, source = _resolve_provider("entity_resolution")
        assert provider == "local"
        assert source in ("global_db", "default")

        # PATCH to 'cloud' (invalidates cache; next read returns the new value).
        await update_system_settings({"llm_provider": "cloud"})
        provider, source = _resolve_provider("entity_resolution")
        assert provider == "cloud"
        assert source == "global_db"

        # Reset for cleanup.
        await update_system_settings({"llm_provider": "local"})
```

The test file MUST handle the realities documented in STATE.md L29 — three Rule-1 deviations from Phase 2 (xx-multilingual model behaviour, ALL-CAPS PERSON detection, US_SSN unavailability for 'id'). If a Phase 3 test trips on a Presidio model nuance, write the test against actual model behaviour rather than the idealized version (Phase 2 precedent: "ALL-CAPS PERSON test rewritten to Title vs lower").

Run the full Phase 3 suite + the prior Phase 1 + Phase 2 regression:
```bash
cd backend && source venv/bin/activate && \
  TEST_EMAIL="test@test.com" TEST_PASSWORD='!*-3-3?3uZ?b$v&' \
  pytest tests/ -v
```
Expected combined: ≥45 passing tests (39 Phase 1+2 baseline + 5+ Phase 3 SCs + ~20 unit tests from Tasks 1+2).

Note the existing autouse `_reset_thread_locks` from Phase 2 conftest — it clears `_thread_locks` AND rebinds `_thread_locks_master` to current event loop. Phase 3 tests do not need additional lock-state management.

CLAUDE.md gotchas applicable:
- The PostToolUse hook auto-runs `pytest tests/` (or equivalent) on .py edits — be aware that the regression run is automatic.
- TEST_EMAIL / TEST_PASSWORD env vars must be set for live-DB tests to authenticate.
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && TEST_EMAIL="test@test.com" TEST_PASSWORD='!*-3-3?3uZ?b$v&' pytest tests/ -x -q 2>&1 | tail -5 | grep -E "[0-9]+ passed"</automated>
  </verify>
  <acceptance_criteria>
    - File `backend/tests/api/test_resolution_and_provider.py` exists.
    - Contains exactly 5 top-level test classes: `TestSC1_AlgorithmicClustering`, `TestSC2_CloudEgressFallback`, `TestSC3_LocalModeBypassesEgress`, `TestSC4_NonPersonNeverReachLLM`, `TestSC5_AdminUIProviderPropagation`.
    - SC#1 test asserts ≥3 variant rows in `entity_registry` for one cluster, all sharing the same `surrogate_value`.
    - SC#2 test asserts `mock_client.chat.completions.create.call_count == 0` after the egress trip.
    - SC#2 test asserts the raw real value `"John Doe"` does NOT appear in any captured log line (B4 invariant).
    - SC#3 test asserts `egress_mock.call_count == 0` for local-mode call.
    - SC#4 test asserts `"alice@example.com" not in payload_str` for every captured LLM payload (RESOLVE-04).
    - SC#5 test calls `update_system_settings({"llm_provider": "cloud"})` then `_resolve_provider("entity_resolution")` and asserts the new value is observable.
    - Combined run: `pytest tests/` returns ≥45 passing tests, 0 failures.
    - No raw PII in any captured log line across the entire Phase 3 suite (verified by grep over `caplog.text` in any test that uses caplog).
  </acceptance_criteria>
  <done>All 5 ROADMAP SCs covered with at least one test each; combined regression ≥45 passing tests; B4 log invariant preserved across the entire Phase 3 suite.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| test process → live Supabase | SC#1 + SC#5 hit the real DB; conftest's per-test thread cleanup ensures no test pollution |
| test process → mocked AsyncOpenAI | SC#2 + SC#3 + SC#4 use `unittest.mock` to verify CALL behaviour without hitting a real cloud endpoint |
| test process → captured log records | caplog inspection enforces the B4 invariant during automated tests |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-CI-01 | Information Disclosure | A failing test prints raw PII via `assert ... == 'John Doe'` and the failure trace ends up in CI logs | mitigate | Tests assert OPPOSITE direction: `assert "John Doe" not in result.anonymized_text`. The expected behaviour is that real values are absent; the assertion message itself doesn't echo a real value (Python prints the not-in operand on failure but the operand IS absent in the success case, so passing tests don't print it). |
| T-CI-02 | Information Disclosure | The captured log assertion `assert "John Doe" not in log_text` echoes the real value into the test's failure message on regression | accept | Trade-off: the value `"John Doe"` is a synthetic test fixture, not real PII. Acceptable in the test suite. Real-PII Phase 1 / Phase 2 tests already follow this pattern. |
| T-DB-01 | Tampering | SC#1 / SC#2 leave variant rows in `entity_registry` after the test | mitigate | conftest's `fresh_thread_id` fixture uses `ON DELETE CASCADE` from the `threads` table — variant rows are auto-deleted on per-test thread teardown (Phase 2 D-22 invariant). |
| T-CACHE-01 | Tampering | SC#5 leaves system_settings row pinned to a non-default state if the test crashes mid-test | mitigate | SC#5 ends with `await update_system_settings({"llm_provider": "local"})` reset. If the test crashes before that line, the next test run's autouse fixture or the next `update_system_settings` call will overwrite. |
| T-NETWORK-01 | Reliability | SC#2-4 tests call a real cloud endpoint by accident | mitigate | Every cloud-mode test patches `app.services.llm_provider._get_client` with a MagicMock — the real AsyncOpenAI client is never instantiated under test. Any real cloud call would surface as `mock_client.chat.completions.create.assert_called_once()` mismatch. |
</threat_model>

<verification>
After this plan completes:
- `git status` shows three new test files.
- Phase 1 + Phase 2 + Phase 3 combined: `pytest tests/ -x` returns ≥45 passing tests, 0 failures.
- D-66 egress-filter unit matrix complete (10+ tests).
- D-65 LLM provider client unit suite complete (10+ tests).
- All 5 Phase 3 SCs have ≥1 test class each; SC#1 + SC#5 hit live DB.
- B4 / D-55 / D-18 log invariant preserved across the full Phase 3 test surface.
</verification>

<success_criteria>
- All 5 Phase 3 ROADMAP success criteria covered with at least one test.
- D-66 egress-filter exhaustive unit matrix shipped.
- D-65 LLM provider client unit suite shipped.
- ≥45 combined tests pass; 0 failures.
- No raw PII appears in any captured log line during any test.
- Phase 3 ready for verification by the orchestrator's checker.
</success_criteria>

<output>
Create `.planning/phases/03-entity-resolution-llm-provider-configuration/03-07-SUMMARY.md` with:
- Three new test files + line counts
- Test counts per file (TestSC1..TestSC5 + D-66 matrix + D-65 suite)
- Combined regression: ≥45 / ≥45 pass
- SC↔file mapping (SC#1→TestSC1; SC#2→TestSC2; ...; SC#5→TestSC5)
- Any Rule-1 deviations applied during test calibration to live model behaviour (Phase 2 precedent)
- B4 log-content invariant verification across the suite
- Phase 3 EXECUTION COMPLETE marker.
</output>
