# Progress

Track your progress through the masterclass. Update this file as you complete modules - Claude Code reads this to understand where you are in the project.

## Convention

- `[ ]` = Not started
- `[-]` = In progress
- `[x]` = Completed

## Modules

### Module 1: App Shell + Observability ✅ COMPLETE

- [x] Project setup (Vite frontend, FastAPI backend, venv, env config)
- [x] Supabase schema (threads + messages tables, RLS policies) — migration at `supabase/migrations/001_initial_schema.sql`
- [x] Backend core (FastAPI, Pydantic settings, Supabase client, JWT auth)
- [x] OpenAI Responses API service + LangSmith tracing
- [x] Backend chat API (thread CRUD + SSE streaming endpoint)
- [x] Frontend auth (login/signup, AuthGuard, protected routes)
- [x] Frontend chat UI (ThreadList, MessageView, streaming, MessageInput)
- [x] End-to-end validated — migration applied, env configured, streaming chat confirmed, RLS verified, messages persisted in DB
- [x] Bug fixes — lifespan replaces deprecated on_event, SSE Cache-Control headers added, apiFetch error check simplified

## Notes

- `openai>=2.30.0` required (responses API + `.stream()` context manager not in v1)
- User message is saved to DB before streaming starts; assistant message is only persisted if the stream produces a response (stream errors no longer create orphaned messages)
- `text-embedding-3-small` cosine similarity scores are typically 0.3–0.6 for semantically related text — use `RAG_SIMILARITY_THRESHOLD=0.3` (not 0.7)
- `pymupdf>=1.25.0` and `tiktoken>=0.8.0` required (Python 3.14 compatible versions)

### Module 2: BYO Retrieval + Memory ✅ COMPLETE

- [x] Plan 8: DB schema + ingestion pipeline (`supabase/migrations/002_module2_schema.sql`, `embedding_service.py`, `ingestion_service.py`, `documents.py` router)
- [x] Plan 9: OpenRouter + stateless chat + RAG retrieval (`openrouter_service.py`, refactor `chat.py` with history + context injection)
- [x] Plan 10: Supabase Realtime ingestion status (frontend `useDocumentRealtime.ts` hook)
- [x] Plan 11: Documents UI (`DocumentsPage.tsx`, `FileUpload.tsx`, `DocumentList.tsx`, nav link)
- [x] Settings UI — per-user LLM model + embedding model with lock enforcement (`user_settings` table, `SettingsPage.tsx`)

#### Module 2 Architecture Summary

- **LLM**: OpenRouter Chat Completions, per-user model (default: `openai/gpt-4o-mini`)
- **Retrieval**: pgvector IVFFlat index, cosine similarity, top-5 chunks, similarity ≥ 0.3
- **Memory**: Stateless — load full thread history from DB, send with every request
- **Ingestion**: Upload → Supabase Storage → BackgroundTask → PyMuPDF parse → tiktoken chunk (500t/50 overlap) → OpenAI embed → pgvector store
- **Status**: Supabase Realtime on `documents` table (pending → processing → completed/failed)
- **Settings**: Per-user LLM + embedding model; embedding locked once documents are indexed
- **New env vars**: `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, `OPENAI_EMBEDDING_MODEL`, `RAG_TOP_K`, `RAG_SIMILARITY_THRESHOLD`, `STORAGE_BUCKET`
- **New tables**: `documents`, `document_chunks`, `user_settings` (all with RLS)
- **Accepted file types**: `.pdf`, `.txt`, `.md`

#### Sub-Plan Files

- `.agent/plans/8.m2-db-ingestion-pipeline.md`
- `.agent/plans/9.m2-openrouter-stateless-chat.md`
- `.agent/plans/10.m2-realtime-status.md`
- `.agent/plans/11.m2-documents-ui.md`

### Module 3: Record Manager ✅ COMPLETE

- [x] Migration `supabase/migrations/004_record_manager.sql` — add `content_hash` column + partial index to `documents` table
- [x] Backend dedup logic — SHA-256 hashing, check for completed/pending/failed duplicates in `documents.py` upload endpoint
- [x] Frontend feedback — `FileUpload.tsx` shows info message for duplicate uploads; `database.types.ts` updated with `content_hash` field
- [x] API tests — `TestDocumentDedup` class with 5 dedup tests in `tests/api/test_documents.py`

#### Module 3 Architecture Summary

- **Hashing**: SHA-256 of raw file bytes, computed before any storage or DB writes
- **Dedup scope**: Per-user — two users uploading the same file each get their own copy
- **On completed duplicate**: Return 200 `{id, filename, status, duplicate: true}` — no storage upload, no DB insert, no background task
- **On pending/processing duplicate**: Return 409
- **On failed duplicate**: Delete failed record + storage file, then proceed with fresh upload
- **Schema**: `content_hash text` column (nullable), partial index on `(user_id, content_hash) WHERE content_hash IS NOT NULL`
- **Legacy docs**: Pre-Module 3 documents have `content_hash = NULL` and are never matched as duplicates

#### Sub-Plan Files

- `.agent/plans/12.m3-record-manager.md`

### Module 4: Metadata Extraction ✅ COMPLETE

- [x] Migration `supabase/migrations/005_document_metadata.sql` — add `metadata` JSONB column + GIN index to `documents`, add `match_document_chunks_with_metadata` RPC
- [x] Pydantic model `backend/app/models/metadata.py` — `DocumentMetadata` with title, author, date_period, category, tags, summary
- [x] Metadata extraction service `backend/app/services/metadata_service.py` — LLM extraction via OpenRouter with `json_object` response format, LangSmith traced
- [x] Ingestion pipeline integration `backend/app/services/ingestion_service.py` — extract metadata after parse, best-effort (failures don't block ingestion)
- [x] Documents router `backend/app/routers/documents.py` — pass `llm_model` to ingestion, include `metadata` in list, add `GET /documents/{id}/metadata` endpoint
- [x] Enhanced retrieval `backend/app/services/embedding_service.py` — `retrieve_chunks_with_metadata()` using new RPC
- [x] Chat enrichment `backend/app/routers/chat.py` — system prompt includes `[Source: "filename" | Category: X | Tags: ...]` per chunk
- [x] Frontend types `frontend/src/lib/database.types.ts` — `DocumentMetadata` interface, `metadata` field on `Document`
- [x] Frontend UI `frontend/src/components/documents/DocumentList.tsx` — show category badge, tags, summary for completed docs
- [x] API tests `tests/api/test_documents.py` — `TestDocumentMetadata` class with META-01 through META-06

#### Module 4 Architecture Summary

- **Extraction**: LLM (user's selected OpenRouter model) extracts structured metadata after text parsing; truncated to 4000 tokens; `json_object` response format; best-effort (extraction failure skips metadata but ingestion succeeds)
- **Schema**: Fixed Pydantic model — `title`, `author`, `date_period`, `category` (enum), `tags` (list), `summary`; stored as JSONB on `documents.metadata`
- **Retrieval**: `match_document_chunks_with_metadata` RPC joins chunks with documents, returns metadata alongside each chunk; optional `filter_category` parameter
- **Chat**: System prompt now includes `[Source: "filename" | Category: X | Tags: y, z]` header before each chunk, giving LLM document-level context
- **Frontend**: Documents page shows category badge (color-coded), keyword tags, and summary for completed documents with metadata; backward compatible with pre-Module 4 docs

#### Sub-Plan Files

- `.agent/plans/13.m4-metadata-extraction.md`

### Module 5: Multi-Format Support ✅ COMPLETE

- [x] Backend dependencies — `python-docx>=1.1.0`, `beautifulsoup4>=4.12.0` added to `requirements.txt`
- [x] Backend MIME whitelist — expanded `ALLOWED_MIME_TYPES` in `documents.py` to include DOCX, CSV, HTML, JSON
- [x] Format parsers — added `_parse_docx`, `_parse_csv`, `_parse_html`, `_parse_json` in `ingestion_service.py`
- [x] Frontend validation — expanded `ACCEPTED_TYPES` and UI text in `FileUpload.tsx`
- [x] Test fixtures — `sample.docx`, `sample.csv`, `sample.html`, `sample.json` in `tests/fixtures/`
- [x] API tests — `TestMultiFormatUpload` class with FMT-01 through FMT-08, all 31 tests passing
- [x] End-to-end validated — all formats ingested to `completed` status with chunks verified

#### Module 5 Architecture Summary

- **New formats**: DOCX (python-docx), CSV (stdlib csv), HTML (beautifulsoup4 + html.parser), JSON (stdlib json)
- **Pattern**: Each format has a `_parse_<format>(file_bytes) -> str` helper; `parse_text()` dispatches by MIME type
- **No schema changes**: Existing `documents` table and ingestion pipeline handle all formats generically
- **Backward compatible**: PDF, TXT, Markdown handling unchanged
- **Accepted MIME types**: `application/pdf`, `text/plain`, `text/markdown`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`, `text/csv`, `text/html`, `application/json`
- **Test note**: `upload_docx` helper generates DOCX in-memory with a UUID paragraph per call (avoids content-hash dedup collisions); requires `python-docx` in the test runner's Python env (`pip3 install python-docx`)

### Module 6: Hybrid Search & Reranking ✅ COMPLETE

- [x] Migration `supabase/migrations/006_hybrid_search.sql` — add `fts tsvector` column, GIN index, auto-populate trigger, `match_document_chunks_fulltext` RPC
- [x] Config additions — `rag_hybrid_enabled`, `rag_rrf_k`, `rag_rerank_enabled`, `rag_rerank_model` in `backend/app/config.py`
- [x] Rerank model — `backend/app/models/rerank.py` with `RerankScore` and `RerankResponse`
- [x] Hybrid retrieval service — `backend/app/services/hybrid_retrieval_service.py` with vector search, full-text search, RRF fusion, optional LLM reranker
- [x] Chat router updated — `backend/app/routers/chat.py` uses `HybridRetrievalService` instead of `EmbeddingService`
- [x] Search diagnostics endpoint — `POST /documents/search` with `hybrid`, `vector`, `fulltext` modes
- [x] API tests — `TestHybridSearch` class with HYB-01 through HYB-08, all 75 tests passing

#### Module 6 Architecture Summary

- **Hybrid search**: Combines pgvector cosine similarity (semantic) + Postgres `tsvector`/`tsquery` full-text search (lexical)
- **Fusion**: Reciprocal Rank Fusion (RRF) merges rankings from both methods; formula: `score = sum(1 / (k + rank + 1))`, default `k=60`
- **Pipeline**: Over-fetch `top_k * 3` candidates from each method concurrently (`asyncio.gather`), fuse via RRF, return top-k
- **Reranking**: Optional LLM-based reranker via OpenRouter (gated by `RAG_RERANK_ENABLED=true`), uses `json_object` response format, best-effort fallback
- **Full-text search**: `websearch_to_tsquery` for natural query support (quoted phrases, boolean operators)
- **Trigger**: Postgres trigger auto-populates `fts` column on chunk INSERT/UPDATE — no ingestion pipeline changes needed
- **Fallback**: When `RAG_HYBRID_ENABLED=false`, delegates to vector-only search (existing behavior)
- **No new dependencies**: Uses existing OpenAI SDK + Supabase client + Postgres built-in full-text search
- **No frontend changes**: Hybrid search is transparent — same response shape as vector-only

#### Sub-Plan Files

- `.claude/plans/polymorphic-watching-codd.md`

### Module 7: Additional Tools ✅ COMPLETE

- [x] Migration `supabase/migrations/007_tool_calls.sql` — add `tool_calls` JSONB to messages, `execute_user_document_query` RPC
- [x] Config additions — `tavily_api_key`, `tools_enabled`, `tools_max_iterations` in `backend/app/config.py`
- [x] Pydantic models — `ToolCallRecord`, `ToolCallSummary` in `backend/app/models/tools.py`
- [x] Tool service — `backend/app/services/tool_service.py` with `search_documents`, `query_database`, `web_search` tools
- [x] OpenRouter service — `complete_with_tools()` method for non-streaming tool-calling completions
- [x] Chat router refactor — agentic tool-calling loop with extended SSE protocol (`tool_start`, `tool_result`, `delta` events)
- [x] Frontend types — `ToolCallRecord`, `SSEEvent` types in `database.types.ts`
- [x] Frontend SSE parsing — `ChatPage.tsx` handles `tool_start`, `tool_result`, `delta` events
- [x] ToolCallCard component — collapsible tool execution display with icons and attribution
- [x] MessageView updated — renders tool cards inline (streaming and persisted)
- [x] API tests — `TestToolCalling`, `TestSQLSafety`, `TestToolPersistence`, `TestSSECompat`, `TestToolErrorHandling` (TOOL-01 through TOOL-09)

#### Module 7 Architecture Summary

- **Agentic loop**: Chat endpoint now uses a tool-calling loop — LLM decides which tools to invoke, backend executes them, results feed back to LLM, final text response is streamed
- **Three tools**: `search_documents` (hybrid RAG retrieval), `query_database` (text-to-SQL with safety), `web_search` (Tavily API fallback)
- **Non-streaming iterations**: Tool-calling rounds use regular completions (fast); only the final text response is streamed via SSE
- **SQL safety**: Postgres RPC `execute_user_document_query` with `SECURITY DEFINER` + `STABLE`, SELECT-only validation, mandatory user_id scoping, write-keyword rejection
- **Web search**: Tavily API via httpx; optional — gated by `TAVILY_API_KEY` env var; tool hidden if not configured
- **SSE protocol**: Extended with `type` field — `tool_start`, `tool_result`, `delta` events; backward compatible (delta events still have `done` field)
- **Attribution**: Every tool call visible in UI via collapsible ToolCallCard; web search shows source URLs, SQL shows query, doc search shows chunk count
- **Persistence**: Tool execution records stored in `messages.tool_calls` JSONB; rendered on page reload
- **Fallback**: `TOOLS_ENABLED=false` → identical to Module 6 behavior; tool errors caught and reported to LLM gracefully
- **No new dependencies**: Uses existing `httpx` for Tavily; no LangChain/LangGraph
- **New env vars**: `TAVILY_API_KEY` (optional), `TOOLS_ENABLED` (default true), `TOOLS_MAX_ITERATIONS` (default 5)

#### Sub-Plan Files

- `.claude/plans/expressive-tinkering-avalanche.md`

### Module 8: Sub-Agents ✅ COMPLETE

- [x] Config additions — `agents_enabled`, `agents_orchestrator_model` in `backend/app/config.py`
- [x] Pydantic models — `AgentDefinition`, `OrchestratorResult` in `backend/app/models/agents.py`; `agent` field added to `ToolCallSummary`
- [x] OpenRouter service — `complete_with_tools()` updated with optional `tools` and `response_format` params
- [x] Agent service — `backend/app/services/agent_service.py` with registry (research, data_analyst, general), `classify_intent()`, `get_agent_tools()`
- [x] Chat router refactor — conditional orchestrator + sub-agent dispatch when `agents_enabled=true`; Module 7 behavior preserved as default
- [x] Frontend types — `AgentStartEvent`, `AgentDoneEvent` in `database.types.ts`; `agent` field on `tool_calls`
- [x] AgentBadge component — `frontend/src/components/chat/AgentBadge.tsx` with active and badge modes
- [x] ChatPage SSE parsing — `activeAgent` state, handles `agent_start`/`agent_done` events
- [x] MessageView updated — renders AgentBadge during streaming and on persisted messages
- [x] API tests — `TestOrchestratorRouting`, `TestSubAgentExecution`, `TestAgentSSEProtocol`, `TestAgentPersistence` (AGENT-01 through AGENT-12)

#### Module 8 Architecture Summary

- **Multi-agent routing**: Orchestrator classifies intent via single non-streaming LLM call with `json_object` response format, routes to specialist sub-agent
- **Three agents**: Research Agent (search_documents, 5 iterations), Data Analyst (query_database, 5 iterations), General Assistant (web_search, 3 iterations)
- **Tool isolation**: Each sub-agent only sees its assigned tools — LLM can't call tools outside its definition
- **SSE protocol**: Extended with `agent_start` (agent name + display name) and `agent_done` events wrapping the tool loop + delta stream
- **Persistence**: Agent name stored in `tool_calls.agent` JSONB field — no migration needed
- **Backward compatible**: `AGENTS_ENABLED=false` (default) preserves exact Module 7 single-agent behavior
- **Fallback**: Invalid orchestrator response gracefully falls back to general agent
- **No new dependencies**: Reuses existing OpenRouter, tool service, and httpx
- **New env vars**: `AGENTS_ENABLED` (default false), `AGENTS_ORCHESTRATOR_MODEL` (optional, defaults to user's model)
