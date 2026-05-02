"""Regression test: _expand_with_neighbors must return results, not None.

Bug: the method mutated chunks in-place but had no return statement,
implicitly returning None. This caused HybridRetrievalService.retrieve()
to return None when rag_neighbor_window > 0, which in turn caused
`for chunk in chunks` in tool_service.py to raise
TypeError: 'NoneType' object is not iterable.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from app.services.hybrid_retrieval_service import HybridRetrievalService


def _make_service() -> HybridRetrievalService:
    with patch("app.services.hybrid_retrieval_service.EmbeddingService"), \
         patch("app.services.hybrid_retrieval_service.AsyncOpenAI"):
        return HybridRetrievalService()


class TestExpandWithNeighbors:
    """_expand_with_neighbors must always return a list[dict]."""

    def test_returns_empty_list_when_no_chunks(self):
        svc = _make_service()
        with patch("app.services.hybrid_retrieval_service.get_supabase_client"):
            result = asyncio.run(svc._expand_with_neighbors([], "user-1", window=1))
        assert result is not None, "_expand_with_neighbors returned None on empty input"
        assert result == []

    def test_returns_original_chunks_when_no_doc_id(self):
        svc = _make_service()
        chunks = [{"content": "x", "id": "c1"}]  # no document_id
        with patch("app.services.hybrid_retrieval_service.get_supabase_client"):
            result = asyncio.run(svc._expand_with_neighbors(chunks, "user-1", window=1))
        assert result is not None
        assert len(result) == 1

    def test_returns_chunks_with_context_on_success(self):
        svc = _make_service()
        chunks = [{"content": "x", "id": "c1", "document_id": "doc-1", "chunk_index": 2}]

        mock_resp = MagicMock()
        mock_resp.data = [{"content": "neighbor", "chunk_index": 1}]
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value \
            .eq.return_value.eq.return_value \
            .gte.return_value.lte.return_value \
            .neq.return_value.order.return_value \
            .execute.return_value = mock_resp

        with patch("app.services.hybrid_retrieval_service.get_supabase_client",
                   return_value=mock_client):
            result = asyncio.run(svc._expand_with_neighbors(chunks, "user-1", window=1))

        assert result is not None
        assert result[0].get("surrounding_context") == "neighbor"

    def test_returns_chunks_even_when_neighbor_fetch_raises(self):
        svc = _make_service()
        chunks = [{"content": "x", "id": "c1", "document_id": "doc-1", "chunk_index": 2}]

        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value \
            .eq.return_value.eq.return_value \
            .gte.return_value.lte.return_value \
            .neq.return_value.order.return_value \
            .execute.side_effect = RuntimeError("DB error")

        with patch("app.services.hybrid_retrieval_service.get_supabase_client",
                   return_value=mock_client):
            result = asyncio.run(svc._expand_with_neighbors(chunks, "user-1", window=1))

        assert result is not None
        assert len(result) == 1
