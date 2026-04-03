import asyncio
import json
import logging
from openai import AsyncOpenAI
from langsmith import traceable
from app.config import get_settings
from app.database import get_supabase_client
from app.services.embedding_service import EmbeddingService
from app.models.rerank import RerankResponse

logger = logging.getLogger(__name__)
settings = get_settings()


class HybridRetrievalService:
    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.openrouter_client = AsyncOpenAI(
            api_key=settings.openrouter_api_key,
            base_url="https://openrouter.ai/api/v1",
        )

    @traceable(name="hybrid_retrieve")
    async def retrieve(
        self,
        query: str,
        user_id: str,
        top_k: int,
        threshold: float,
        embedding_model: str | None = None,
        llm_model: str | None = None,
        category: str | None = None,
    ) -> list[dict]:
        """Main retrieval entry point. Routes to hybrid or vector-only."""
        if not settings.rag_hybrid_enabled:
            return await self.embedding_service.retrieve_chunks_with_metadata(
                query=query,
                user_id=user_id,
                top_k=top_k,
                threshold=threshold,
                model=embedding_model,
                category=category,
            )

        candidate_count = top_k * 3

        vector_results, fulltext_results = await asyncio.gather(
            self._vector_search(query, user_id, candidate_count, threshold, embedding_model, category),
            self._fulltext_search(query, user_id, candidate_count, category),
        )

        fused = self._reciprocal_rank_fusion(vector_results, fulltext_results)

        if settings.rag_rerank_enabled and fused:
            rerank_model = settings.rag_rerank_model or llm_model
            fused = await self._llm_rerank(query, fused, rerank_model)

        return fused[:top_k]

    @traceable(name="vector_search")
    async def _vector_search(
        self,
        query: str,
        user_id: str,
        count: int,
        threshold: float,
        model: str | None,
        category: str | None,
    ) -> list[dict]:
        return await self.embedding_service.retrieve_chunks_with_metadata(
            query=query,
            user_id=user_id,
            top_k=count,
            threshold=threshold,
            model=model,
            category=category,
        )

    @traceable(name="fulltext_search")
    async def _fulltext_search(
        self,
        query: str,
        user_id: str,
        count: int,
        category: str | None,
    ) -> list[dict]:
        try:
            result = get_supabase_client().rpc(
                "match_document_chunks_fulltext",
                {
                    "search_query": query,
                    "match_user_id": user_id,
                    "match_count": count,
                    "filter_category": category,
                },
            ).execute()
            return result.data or []
        except Exception as e:
            logger.warning("Full-text search failed, returning empty: %s", e)
            return []

    def _reciprocal_rank_fusion(self, *result_lists: list[dict]) -> list[dict]:
        k = settings.rag_rrf_k
        scores: dict[str, float] = {}
        chunk_map: dict[str, dict] = {}

        for results in result_lists:
            for rank_idx, chunk in enumerate(results):
                chunk_id = chunk["id"]
                scores[chunk_id] = scores.get(chunk_id, 0) + 1.0 / (k + rank_idx + 1)
                chunk_map[chunk_id] = chunk

        sorted_ids = sorted(scores, key=lambda cid: scores[cid], reverse=True)
        fused = []
        for cid in sorted_ids:
            item = chunk_map[cid].copy()
            item["rrf_score"] = scores[cid]
            fused.append(item)
        return fused

    @traceable(name="llm_rerank")
    async def _llm_rerank(
        self, query: str, chunks: list[dict], model: str | None
    ) -> list[dict]:
        # Truncate each chunk to ~200 tokens for the reranker prompt
        truncated = []
        for i, c in enumerate(chunks):
            text = c["content"][:800]
            truncated.append(f"[{i}] {text}")

        system_prompt = (
            "You are a relevance scorer. Given a query and a list of text chunks, "
            "rate each chunk's relevance to the query on a scale of 0 to 10.\n\n"
            "Return a JSON object with a single key \"scores\" containing an array of objects, "
            "each with \"index\" (int) and \"score\" (float 0-10)."
        )
        user_prompt = f"Query: {query}\n\nChunks:\n" + "\n\n".join(truncated)

        try:
            response = await self.openrouter_client.chat.completions.create(
                model=model or settings.openrouter_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0,
            )
            raw = response.choices[0].message.content or ""
            parsed = RerankResponse.model_validate_json(raw)

            scored = {s.index: s.score for s in parsed.scores}
            reranked = sorted(
                chunks,
                key=lambda c: scored.get(chunks.index(c), 0),
                reverse=True,
            )
            return reranked
        except Exception as e:
            logger.warning("LLM reranking failed, keeping original order: %s", e)
            return chunks
