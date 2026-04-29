"""Phase 6 Plan 06-03 unit tests — EMBEDDING_PROVIDER branch in EmbeddingService.

D-P6-02 verifies:
  - cloud mode: AsyncOpenAI(api_key=<openai key>) — RAG-02 byte-identical
  - local mode: AsyncOpenAI(base_url=<local url>, api_key="not-needed")
  - embed_batch passes input=texts (no per-string serial calls — D-P6-Discretion bullet 3)
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _fake_settings(provider: str, local_base_url: str = "", openai_api_key: str = "sk-test-cloud", openai_embedding_model: str = "text-embedding-3-small") -> SimpleNamespace:
    return SimpleNamespace(
        embedding_provider=provider,
        local_embedding_base_url=local_base_url,
        openai_api_key=openai_api_key,
        openai_embedding_model=openai_embedding_model,
    )


def test_embed_cloud_provider_uses_openai_key(monkeypatch):
    """D-P6-02 cloud branch: AsyncOpenAI receives only api_key (no base_url)."""
    fake = _fake_settings(provider="cloud", openai_api_key="sk-cloud-XXX")

    captured_kwargs: dict = {}

    class _StubAsyncOpenAI:
        def __init__(self, **kwargs):
            captured_kwargs.update(kwargs)
            self.embeddings = MagicMock()

    # IMPORTANT: patch the symbol where embedding_service.py imports it from.
    monkeypatch.setattr("app.services.embedding_service.AsyncOpenAI", _StubAsyncOpenAI)
    monkeypatch.setattr("app.services.embedding_service.settings", fake)

    # monkeypatch.setattr replaces the module-level symbol in place;
    # subsequent attribute reads (settings.embedding_provider) hit the patched object.
    from app.services.embedding_service import EmbeddingService

    service = EmbeddingService()
    assert service.model == "text-embedding-3-small"
    assert captured_kwargs == {"api_key": "sk-cloud-XXX"}, f"cloud branch should pass only api_key; got {captured_kwargs}"
    assert "base_url" not in captured_kwargs


def test_embed_local_provider_uses_local_base_url(monkeypatch):
    """D-P6-02 local branch: AsyncOpenAI receives base_url + api_key='not-needed'."""
    fake = _fake_settings(provider="local", local_base_url="http://localhost:11434/v1")

    captured_kwargs: dict = {}

    class _StubAsyncOpenAI:
        def __init__(self, **kwargs):
            captured_kwargs.update(kwargs)
            self.embeddings = MagicMock()

    monkeypatch.setattr("app.services.embedding_service.AsyncOpenAI", _StubAsyncOpenAI)
    monkeypatch.setattr("app.services.embedding_service.settings", fake)

    from app.services.embedding_service import EmbeddingService

    service = EmbeddingService()
    assert captured_kwargs.get("base_url") == "http://localhost:11434/v1"
    assert captured_kwargs.get("api_key") == "not-needed"


@pytest.mark.asyncio
async def test_embed_batch_local_passes_full_list_no_serial_calls(monkeypatch):
    """D-P6-Discretion bullet 3: local-mode embed_batch passes input=texts as a single list."""
    fake = _fake_settings(provider="local", local_base_url="http://localhost:11434/v1")

    fake_response = SimpleNamespace(
        data=[
            SimpleNamespace(embedding=[0.1, 0.2], index=0),
            SimpleNamespace(embedding=[0.3, 0.4], index=1),
            SimpleNamespace(embedding=[0.5, 0.6], index=2),
        ]
    )
    create_mock = AsyncMock(return_value=fake_response)

    class _StubAsyncOpenAI:
        def __init__(self, **kwargs):
            self.embeddings = SimpleNamespace(create=create_mock)

    monkeypatch.setattr("app.services.embedding_service.AsyncOpenAI", _StubAsyncOpenAI)
    monkeypatch.setattr("app.services.embedding_service.settings", fake)

    from app.services.embedding_service import EmbeddingService

    service = EmbeddingService()
    texts = ["alpha", "beta", "gamma"]
    result = await service.embed_batch(texts)

    # Single API call, full list — NOT one call per string.
    assert create_mock.await_count == 1, f"embed_batch must NOT serialize per-string; got {create_mock.await_count} calls"
    kwargs = create_mock.await_args.kwargs
    assert kwargs["input"] == texts
    assert result == [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]
