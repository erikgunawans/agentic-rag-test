import asyncio
import hashlib
import json
import logging
import time
from openai import AsyncOpenAI
from app.services.tracing_service import traced
from app.config import get_settings
from app.database import get_supabase_client
from app.services.embedding_service import EmbeddingService
from app.models.rerank import RerankResponse

logger = logging.getLogger(__name__)
settings = get_settings()

# Semantic cache — mirrors system_settings_service.py pattern
_retrieval_cache: dict[str, tuple[float, list[dict]]] = {}
_CACHE_TTL = 300  # 5 minutes
_CACHE_MAX = 1000


def _cache_key(
    query: str,
    user_id: str,
    top_k: int,
    category: str | None,
    *,
    filter_tags: list[str] | None = None,
    filter_folder_id: str | None = None,
    filter_date_from: str | None = None,
    filter_date_to: str | None = None,
) -> str:
    raw = f"{query.lower().strip()}:{user_id}:{top_k}:{category or ''}:{','.join(sorted(filter_tags or []))}:{filter_folder_id or ''}:{filter_date_from or ''}:{filter_date_to or ''}"
    return hashlib.md5(raw.encode()).hexdigest()


class HybridRetrievalService:
    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.openrouter_client = AsyncOpenAI(
            api_key=settings.openrouter_api_key,
            base_url="https://openrouter.ai/api/v1",
        )
        self._cohere_client: "httpx.AsyncClient | None" = None

    @traced(name="hybrid_retrieve")
    async def retrieve(
        self,
        query: str,
        user_id: str,
        top_k: int,
        threshold: float,
        embedding_model: str | None = None,
        llm_model: str | None = None,
        category: str | None = None,
        filter_tags: list[str] | None = None,
        filter_folder_id: str | None = None,
        filter_date_from: str | None = None,
        filter_date_to: str | None = None,
    ) -> list[dict]:
        """Main retrieval entry point with cache, query expansion, and neighbor context."""
        from app.services.system_settings_service import get_system_settings

        # Semantic cache check
        key = _cache_key(
            query, user_id, top_k, category,
            filter_tags=filter_tags, filter_folder_id=filter_folder_id,
            filter_date_from=filter_date_from, filter_date_to=filter_date_to,
        )
        now = time.time()
        if key in _retrieval_cache:
            ts, cached = _retrieval_cache[key]
            if now - ts < _CACHE_TTL:
                return cached

        sys_settings = get_system_settings()

        filter_kw = dict(
            filter_tags=filter_tags, filter_folder_id=filter_folder_id,
            filter_date_from=filter_date_from, filter_date_to=filter_date_to,
        )

        if not settings.rag_hybrid_enabled:
            results = await self.embedding_service.retrieve_chunks_with_metadata(
                query=query,
                user_id=user_id,
                top_k=top_k,
                threshold=threshold,
                model=embedding_model,
                category=category,
                **filter_kw,
            )
            _retrieval_cache[key] = (now, results)
            return results

        candidate_count = top_k * 3

        # Query expansion for bilingual (ID/EN) retrieval
        fulltext_queries = [query]
        if sys_settings.get("rag_query_expansion_enabled"):
            try:
                expanded = await self._expand_query(query, llm_model)
                fulltext_queries = expanded
            except Exception as e:
                logger.warning("Query expansion failed, using original: %s", e)

        # Parallel vector + fulltext (fulltext uses all query variants)
        fulltext_tasks = [
            self._fulltext_search(q, user_id, candidate_count, category, **filter_kw)
            for q in fulltext_queries
        ]
        all_results = await asyncio.gather(
            self._vector_search(query, user_id, candidate_count, threshold, embedding_model, category, **filter_kw),
            *fulltext_tasks,
        )

        vector_results = all_results[0]
        fulltext_combined = []
        seen_ids = set()
        for ft_result in all_results[1:]:
            for chunk in ft_result:
                if chunk["id"] not in seen_ids:
                    seen_ids.add(chunk["id"])
                    fulltext_combined.append(chunk)

        fused = self._reciprocal_rank_fusion(
            vector_results, fulltext_combined,
            weights=[sys_settings.get("rag_vector_weight", 1.0), sys_settings.get("rag_fulltext_weight", 1.0)],
        )

        rerank_mode = sys_settings.get("rag_rerank_mode", "none")
        if rerank_mode == "cohere" and settings.cohere_api_key and fused:
            fused = await self._cohere_rerank(query, fused, top_n=top_k)
        elif rerank_mode == "llm" and fused:
            fused = await self._llm_rerank(query, fused, settings.rag_rerank_model or llm_model)

        results = fused[:top_k]

        # Neighboring chunk expansion
        neighbor_window = sys_settings.get("rag_neighbor_window", 0)
        if neighbor_window > 0:
            results = await self._expand_with_neighbors(results, user_id, neighbor_window)

        # Graph context enrichment
        if sys_settings.get("graph_enabled") and results:
            try:
                from app.services.graph_service import GraphService
                graph_service = GraphService()
                chunk_ids = [r["id"] for r in results]
                graph_data = await graph_service.get_graph_context(chunk_ids, user_id)
                if graph_data and (graph_data.get("entities") or graph_data.get("relationships")):
                    graph_text = graph_service.format_graph_context(graph_data)
                    for result in results:
                        result["graph_context"] = graph_text
            except Exception as e:
                logger.warning("Graph context enrichment failed: %s", e)

        # Cache result (evict oldest if over limit)
        if len(_retrieval_cache) >= _CACHE_MAX:
            oldest_key = min(_retrieval_cache, key=lambda k: _retrieval_cache[k][0])
            del _retrieval_cache[oldest_key]
        _retrieval_cache[key] = (time.time(), results)

        return results

    @traced(name="vector_search")
    async def _vector_search(
        self,
        query: str,
        user_id: str,
        count: int,
        threshold: float,
        model: str | None,
        category: str | None,
        filter_tags: list[str] | None = None,
        filter_folder_id: str | None = None,
        filter_date_from: str | None = None,
        filter_date_to: str | None = None,
    ) -> list[dict]:
        return await self.embedding_service.retrieve_chunks_with_metadata(
            query=query,
            user_id=user_id,
            top_k=count,
            threshold=threshold,
            model=model,
            category=category,
            filter_tags=filter_tags,
            filter_folder_id=filter_folder_id,
            filter_date_from=filter_date_from,
            filter_date_to=filter_date_to,
        )

    @traced(name="fulltext_search")
    async def _fulltext_search(
        self,
        query: str,
        user_id: str,
        count: int,
        category: str | None,
        filter_tags: list[str] | None = None,
        filter_folder_id: str | None = None,
        filter_date_from: str | None = None,
        filter_date_to: str | None = None,
    ) -> list[dict]:
        try:
            params: dict = {
                "search_query": query,
                "match_user_id": user_id,
                "match_count": count,
                "filter_category": category,
            }
            if filter_tags:
                params["filter_tags"] = filter_tags
            if filter_folder_id:
                params["filter_folder_id"] = filter_folder_id
            if filter_date_from:
                params["filter_date_from"] = filter_date_from
            if filter_date_to:
                params["filter_date_to"] = filter_date_to
            result = get_supabase_client().rpc(
                "match_document_chunks_fulltext", params,
            ).execute()
            return result.data or []
        except Exception as e:
            logger.warning("Full-text search failed, returning empty: %s", e)
            return []

    def _reciprocal_rank_fusion(self, *result_lists: list[dict], weights: list[float] | None = None) -> list[dict]:
        k = settings.rag_rrf_k
        scores: dict[str, float] = {}
        chunk_map: dict[str, dict] = {}

        for list_idx, results in enumerate(result_lists):
            w = weights[list_idx] if weights and list_idx < len(weights) else 1.0
            for rank_idx, chunk in enumerate(results):
                chunk_id = chunk["id"]
                scores[chunk_id] = scores.get(chunk_id, 0) + w / (k + rank_idx + 1)
                chunk_map[chunk_id] = chunk

        sorted_ids = sorted(scores, key=lambda cid: scores[cid], reverse=True)
        fused = []
        for cid in sorted_ids:
            item = chunk_map[cid].copy()
            item["rrf_score"] = scores[cid]
            fused.append(item)
        return fused

    @traced(name="llm_rerank")
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
                enumerate(chunks),
                key=lambda ic: scored.get(ic[0], 0),
                reverse=True,
            )
            return [c for _, c in reranked]
        except Exception as e:
            logger.warning("LLM reranking failed, keeping original order: %s", e)
            return chunks

    @traced(name="cohere_rerank")
    async def _cohere_rerank(
        self, query: str, chunks: list[dict], top_n: int | None = None
    ) -> list[dict]:
        """Rerank chunks using Cohere Rerank v2 API."""
        documents = [c["content"][:4096] for c in chunks]
        try:
            if self._cohere_client is None:
                import httpx
                self._cohere_client = httpx.AsyncClient(timeout=10)
            resp = await self._cohere_client.post(
                "https://api.cohere.com/v2/rerank",
                headers={
                    "Authorization": f"Bearer {settings.cohere_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "rerank-v3.5",
                    "query": query,
                    "documents": documents,
                    "top_n": top_n or len(chunks),
                },
            )
            resp.raise_for_status()
            ranked_indices = [r["index"] for r in resp.json()["results"]]
            return [chunks[i] for i in ranked_indices]
        except Exception as e:
            logger.warning("Cohere reranking failed, keeping original order: %s", e)
            return chunks

    @traced(name="query_expansion")
    async def _expand_query(self, query: str, model: str | None) -> list[str]:
        """Generate query variants for bilingual (ID/EN) retrieval."""
        result = await self.openrouter_client.chat.completions.create(
            model=model or settings.openrouter_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You expand Indonesian legal queries for document search. "
                        "Given a query, return 2 alternative phrasings: one in formal "
                        "legal Indonesian, one using common English legal terms. "
                        'Return JSON: {"variants": ["...", "..."]}'
                    ),
                },
                {"role": "user", "content": query},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        raw = result.choices[0].message.content or "{}"
        variants = json.loads(raw).get("variants", [])
        return [query] + variants[:2]

    async def _expand_with_neighbors(
        self, results: list[dict], user_id: str, window: int = 1
    ) -> list[dict]:
        """Fetch neighboring chunks to provide surrounding context."""
        client = get_supabase_client()
        for result in results:
            doc_id = result.get("document_id")
            chunk_idx = result.get("chunk_index")
            if doc_id and chunk_idx is not None:
                try:
                    neighbors = (
                        client.table("document_chunks")
                        .select("content, chunk_index")
                        .eq("document_id", doc_id)
                        .eq("user_id", user_id)
                        .gte("chunk_index", chunk_idx - window)
                        .lte("chunk_index", chunk_idx + window)
                        .neq("chunk_index", chunk_idx)
                        .order("chunk_index")
                        .execute()
                    )
                    if neighbors.data:
                        result["surrounding_context"] = "\n---\n".join(
                            n["content"] for n in neighbors.data
                        )
                except Exception as e:
                    logger.warning("Neighbor expansion failed for chunk %s: %s", chunk_idx, e)
        return results
