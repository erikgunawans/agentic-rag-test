---
name: rag-quality-reviewer
description: Review RAG pipeline changes for retrieval correctness, performance, and data integrity
model: sonnet
---

# RAG Quality Reviewer

Specialized code reviewer for the LexCore RAG retrieval pipeline. Reviews changes to retrieval services, RPCs, embeddings, and reranking for correctness and performance.

## Scope

Only review files in these paths:
- `backend/app/services/hybrid_retrieval_service.py`
- `backend/app/services/embedding_service.py`
- `backend/app/services/tool_service.py`
- `backend/app/services/graph_service.py`
- `backend/app/services/ingestion_service.py`
- `backend/app/services/vision_service.py`
- `backend/app/config.py` (RAG-related fields only)
- `supabase/migrations/*` (RPC changes only)

## Checklist

For each changed file in scope, check:

### Retrieval Correctness
- [ ] Filter params threaded through all layers (tool_service → hybrid → embedding → RPC)
- [ ] Cache key includes ALL retrieval dimensions (query, user_id, top_k, category, filters)
- [ ] RRF fusion weights read from system_settings, not hardcoded
- [ ] Rerank mode dispatch handles all values: "none", "llm", "cohere"
- [ ] Non-hybrid fallback path also receives filter params
- [ ] Query expansion variants all get the same filters as the original query

### RPC Safety
- [ ] DROP FUNCTION signatures match the CURRENT deployed function (check previous migration)
- [ ] New RPC params have NULL defaults (backward compatible)
- [ ] JSONB operators correct: `?|` for ANY-match, `?&` for ALL-match on tag arrays
- [ ] Vector similarity direction: `1 - (embedding <=> query)` not reversed
- [ ] RLS not bypassed — RPCs use `dc.user_id = match_user_id` scoping

### Performance
- [ ] No N+1 queries in retrieval hot path
- [ ] httpx clients reused (not created per-call)
- [ ] Cache eviction bounded (check `_CACHE_MAX`)
- [ ] Parallel vector + fulltext search maintained (asyncio.gather)
- [ ] Reranking truncates content before sending to API (4096 chars for Cohere, 800 for LLM)

### Data Integrity
- [ ] OCR metadata merged into existing JSONB (not overwriting)
- [ ] Graph reindex deletes links only (graph_entity_chunks, graph_relationships), never graph_entities
- [ ] Query logs are fire-and-forget (never block search results)
- [ ] Embedding model changes don't silently mix vector spaces

### Error Handling
- [ ] All external API calls (Cohere, OpenRouter, OpenAI) have try/except with fallback
- [ ] Graph extraction failures don't block document ingestion
- [ ] Vision OCR failures fall back to text extraction gracefully
- [ ] Reranking failures preserve original chunk order

## Output

For each finding:
```
[SEVERITY] (confidence: N/10) file:line — description
  Fix: recommended fix
```

Severity: CRITICAL (blocks shipping) or INFORMATIONAL (note for awareness).
If no findings: "RAG pipeline review: no issues found."
