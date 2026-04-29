"""Unit tests for LLMProviderClient + _resolve_provider (D-49, D-51, D-52, D-65).

Cloud / local SDK calls are mocked at the AsyncOpenAI client level — CI never
hits a real Ollama / LM Studio / OpenAI endpoint. These are pure-unit tests:
no DB, no live Supabase, no network.
"""
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


# --- Stub registry (duck-typed; same shape as test_egress_filter.py). ---


@dataclass(frozen=True)
class _StubMapping:
    entity_type: str
    real_value: str


class _StubRegistry:
    """Duck-typed stand-in for ConversationRegistry.

    Phase 6 D-P6-16: thread_id attribute added so egress_filter trip log
    can read registry.thread_id without AttributeError.
    """

    thread_id: str = "stub-thread-id"

    def __init__(self, mappings):
        self._mappings = list(mappings)

    def entries(self):
        return self._mappings

    def canonicals(self):
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
        with patch(
            "app.services.llm_provider.get_system_settings", return_value={}
        ):
            provider, source = _resolve_provider("entity_resolution")
        assert (provider, source) == ("local", "default")

    def test_feature_env_wins_over_db(self, monkeypatch):
        monkeypatch.setenv("ENTITY_RESOLUTION_LLM_PROVIDER", "cloud")
        with patch(
            "app.services.llm_provider.get_system_settings",
            return_value={
                "entity_resolution_llm_provider": "local",
                "llm_provider": "local",
            },
        ):
            provider, source = _resolve_provider("entity_resolution")
        assert (provider, source) == ("cloud", "feature_env")

    def test_feature_db_wins_over_global_env(self, monkeypatch):
        monkeypatch.delenv("ENTITY_RESOLUTION_LLM_PROVIDER", raising=False)
        monkeypatch.setenv("LLM_PROVIDER", "local")
        with patch(
            "app.services.llm_provider.get_system_settings",
            return_value={
                "entity_resolution_llm_provider": "cloud",
                "llm_provider": "local",
            },
        ):
            provider, source = _resolve_provider("entity_resolution")
        assert (provider, source) == ("cloud", "feature_db")

    def test_global_env_wins_over_global_db(self, monkeypatch):
        monkeypatch.delenv("ENTITY_RESOLUTION_LLM_PROVIDER", raising=False)
        monkeypatch.setenv("LLM_PROVIDER", "cloud")
        with patch(
            "app.services.llm_provider.get_system_settings",
            return_value={"llm_provider": "local"},
        ):
            provider, source = _resolve_provider("entity_resolution")
        assert (provider, source) == ("cloud", "global_env")

    def test_global_db_used_when_no_env(self, monkeypatch):
        monkeypatch.delenv("ENTITY_RESOLUTION_LLM_PROVIDER", raising=False)
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        with patch(
            "app.services.llm_provider.get_system_settings",
            return_value={"llm_provider": "cloud"},
        ):
            provider, source = _resolve_provider("entity_resolution")
        assert (provider, source) == ("cloud", "global_db")

    def test_invalid_env_value_falls_through(self, monkeypatch):
        """Bad enum at any layer is treated as unset (defense in depth, D-51)."""
        monkeypatch.setenv("ENTITY_RESOLUTION_LLM_PROVIDER", "aws_bedrock")
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        with patch(
            "app.services.llm_provider.get_system_settings", return_value={}
        ):
            provider, source = _resolve_provider("entity_resolution")
        assert (provider, source) == ("local", "default")

    def test_invalid_db_value_skipped(self, monkeypatch):
        """Bad DB enum is also skipped — defense in depth even though D-60 CHECK should prevent."""
        monkeypatch.delenv("ENTITY_RESOLUTION_LLM_PROVIDER", raising=False)
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        with patch(
            "app.services.llm_provider.get_system_settings",
            return_value={
                "entity_resolution_llm_provider": "garbage",
                "llm_provider": "garbage",
            },
        ):
            provider, source = _resolve_provider("entity_resolution")
        assert (provider, source) == ("local", "default")


# --- LLMProviderClient — local mode (no egress filter). ---


class TestProviderClientLocalMode:
    """Local mode bypasses egress filter; sees raw real names per FR-9.2."""

    @pytest.mark.asyncio
    async def test_local_call_does_not_invoke_egress_filter(self, monkeypatch):
        # Force local provider via env (highest priority per D-51).
        monkeypatch.setenv("ENTITY_RESOLUTION_LLM_PROVIDER", "local")

        # Mock the AsyncOpenAI client at the lazy-cache layer.
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content='{"clusters": []}'))
        ]
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch(
            "app.services.llm_provider._get_client", return_value=mock_client
        ), patch("app.services.llm_provider.egress_filter") as egress_mock:
            client = LLMProviderClient()
            registry = _StubRegistry([_StubMapping("PERSON", "John Doe")])
            result = await client.call(
                feature="entity_resolution",
                messages=[{"role": "user", "content": "hello John Doe"}],
                registry=registry,
                provisional_surrogates=None,
            )
            # Local mode never invokes the egress filter (FR-9.2).
            assert egress_mock.call_count == 0
            # The mocked SDK call WAS invoked exactly once.
            assert mock_client.chat.completions.create.call_count == 1
            assert isinstance(result, dict)


# --- LLMProviderClient — cloud mode + egress filter trip. ---


class TestProviderClientCloudMode:
    """Cloud mode wraps payload with egress filter; raises _EgressBlocked on trip."""

    @pytest.mark.asyncio
    async def test_cloud_egress_trip_raises_egress_blocked_pre_call(
        self, monkeypatch
    ):
        monkeypatch.setenv("ENTITY_RESOLUTION_LLM_PROVIDER", "cloud")

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock()

        registry = _StubRegistry([_StubMapping("PERSON", "John Doe")])

        with patch(
            "app.services.llm_provider._get_client", return_value=mock_client
        ):
            client = LLMProviderClient()
            with pytest.raises(_EgressBlocked) as excinfo:
                await client.call(
                    feature="entity_resolution",
                    messages=[
                        {"role": "user", "content": "Hello John Doe!"}
                    ],
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
        mock_response.choices = [
            MagicMock(message=MagicMock(content='{"clusters": []}'))
        ]
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        # Empty registry + empty provisional → no egress trip.
        registry = _StubRegistry([])

        with patch(
            "app.services.llm_provider._get_client", return_value=mock_client
        ):
            client = LLMProviderClient()
            result = await client.call(
                feature="entity_resolution",
                messages=[{"role": "user", "content": "Hello world"}],
                registry=registry,
                provisional_surrogates=None,
            )
        assert mock_client.chat.completions.create.call_count == 1
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_cloud_provisional_surrogates_in_filter_scope(self, monkeypatch):
        """D-56: in-flight provisional set is part of egress filter scope."""
        monkeypatch.setenv("ENTITY_RESOLUTION_LLM_PROVIDER", "cloud")

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock()

        # Empty registry, but provisional has the real value → still must trip.
        registry = _StubRegistry([])
        provisional = {"Carla Wijaya": "Mock_Surrogate_001"}

        with patch(
            "app.services.llm_provider._get_client", return_value=mock_client
        ):
            client = LLMProviderClient()
            with pytest.raises(_EgressBlocked):
                await client.call(
                    feature="entity_resolution",
                    messages=[
                        {"role": "user", "content": "Hi Carla Wijaya here."}
                    ],
                    registry=registry,
                    provisional_surrogates=provisional,
                )
        assert mock_client.chat.completions.create.call_count == 0


# --- LLMProviderClient — fallback boundary (D-52). ---


class TestProviderClientFallback:
    """D-52: network/5xx/invalid SDK exceptions PROPAGATE OUT — caller decides on fallback."""

    @pytest.mark.asyncio
    async def test_5xx_propagates_to_caller(self, monkeypatch):
        monkeypatch.setenv("ENTITY_RESOLUTION_LLM_PROVIDER", "cloud")

        class _SimulatedSDKError(Exception):
            pass

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=_SimulatedSDKError("simulated 503")
        )

        with patch(
            "app.services.llm_provider._get_client", return_value=mock_client
        ):
            client = LLMProviderClient()
            with pytest.raises(_SimulatedSDKError):
                await client.call(
                    feature="entity_resolution",
                    messages=[{"role": "user", "content": "anything"}],
                    registry=_StubRegistry([]),
                    provisional_surrogates=None,
                )

    @pytest.mark.asyncio
    async def test_local_5xx_propagates_to_caller(self, monkeypatch):
        """D-52: local provider exceptions also propagate (no try/except inside .call)."""
        monkeypatch.setenv("ENTITY_RESOLUTION_LLM_PROVIDER", "local")

        class _SimulatedLocalDown(Exception):
            pass

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=_SimulatedLocalDown("local llm unreachable")
        )

        with patch(
            "app.services.llm_provider._get_client", return_value=mock_client
        ):
            client = LLMProviderClient()
            with pytest.raises(_SimulatedLocalDown):
                await client.call(
                    feature="entity_resolution",
                    messages=[{"role": "user", "content": "anything"}],
                    registry=_StubRegistry([]),
                    provisional_surrogates=None,
                )

    def test_lazy_cache_returns_same_instance(self):
        """D-50: per-provider AsyncOpenAI clients cached in module-level dict."""
        c1 = _get_client("local")
        c2 = _get_client("local")
        assert c1 is c2

    def test_lazy_cache_separates_providers(self):
        """D-50: 'local' and 'cloud' get DIFFERENT cached instances."""
        c_local = _get_client("local")
        c_cloud = _get_client("cloud")
        assert c_local is not c_cloud


# --- LLMProviderClient — JSON parse boundary. ---


class TestProviderClientJSONParse:
    """call() always returns a dict so caller doesn't crash on a non-JSON response."""

    @pytest.mark.asyncio
    async def test_non_json_response_wrapped_in_raw_key(self, monkeypatch):
        monkeypatch.setenv("ENTITY_RESOLUTION_LLM_PROVIDER", "local")

        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content="not valid json"))
        ]
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch(
            "app.services.llm_provider._get_client", return_value=mock_client
        ):
            client = LLMProviderClient()
            result = await client.call(
                feature="entity_resolution",
                messages=[{"role": "user", "content": "hi"}],
                registry=_StubRegistry([]),
                provisional_surrogates=None,
            )
        assert isinstance(result, dict)
        assert result.get("raw") == "not valid json"

    @pytest.mark.asyncio
    async def test_none_content_returns_dict_with_empty_raw(self, monkeypatch):
        monkeypatch.setenv("ENTITY_RESOLUTION_LLM_PROVIDER", "local")

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content=None))]
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch(
            "app.services.llm_provider._get_client", return_value=mock_client
        ):
            client = LLMProviderClient()
            result = await client.call(
                feature="entity_resolution",
                messages=[{"role": "user", "content": "hi"}],
                registry=_StubRegistry([]),
                provisional_surrogates=None,
            )
        assert isinstance(result, dict)
        assert result.get("raw") == ""
