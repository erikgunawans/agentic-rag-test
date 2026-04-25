# Architecture

**Analysis Date:** 2026-04-25

## Pattern Overview

**Overall:** Decoupled SPA + REST/SSE API. Frontend (React + Vite) talks to a stateless FastAPI backend; both share a Supabase Postgres database with Row-Level Security (RLS) as the authorization boundary. Backend is layered (routers -> services -> Supabase clients -> DB).

**Key Characteristics:**
- 22 thin FastAPI routers in `backend/app/routers/` orchestrate ~18 service modules in `backend/app/services/`. Routers handle HTTP/auth; services hold domain logic; the Supabase Python SDK acts as the repository layer (no separate repository classes).
- Streaming-first chat: `POST /chat/stream` returns Server-Sent Events. An agentic tool-calling loop iterates LLM calls until no more tools are requested, then streams the final text via `delta` events.
- RLS-based authorization: queries either use `get_supabase_authed_client(token)` (RLS-enforced) or `get_supabase_client()` service-role + explicit `user_id` filters.
- Pluggable RAG: `HybridRetrievalService` fuses vector (pgvector) + fulltext (tsvector) via weighted RRF, with optional Cohere/LLM rerank, bilingual query expansion, semantic cache, and metadata pre-filtering. Knobs live in `system_settings` (single-row table).
- No LangChain / LangGraph. Raw OpenRouter / OpenAI / Cohere SDK calls only. Pydantic models define structured outputs.
- Multi-agent orchestration (feature-flagged via `agents_enabled`): orchestrator classifies intent then dispatches to a sub-agent (Research, General, ...) with a scoped tool subset.
- Graphify knowledge graph at `graphify-out/` (1,211 nodes / 192 communities as of 2026-04-23) for cross-community navigation; `HybridRetrievalService` and `ToolService` are identified bridge nodes.

## Layers

**HTTP layer (Routers):**
- Purpose: Bind FastAPI endpoints, validate Pydantic requests, run auth dependencies, persist mutations, return JSON or `StreamingResponse`.
- Location: `backend/app/routers/*.py`
- Contains: `APIRouter` instances, request/response Pydantic models, SSE generators.
- Depends on: `app.services.*`, `app.dependencies` (auth), `app.database`, `app.config`.
- Used by: `backend/app/main.py` via `app.include_router(...)`.

**Service layer (Domain logic):**
- Purpose: Business logic, LLM orchestration, retrieval, ingestion, audit, system-settings caching.
- Location: `backend/app/services/*.py`
- Contains: Class- or module-level singletons (`HybridRetrievalService`, `ToolService`, `OpenRouterService`, `EmbeddingService`, `agent_service` module).
- Depends on: External SDKs (`openai`, `httpx`, `supabase`, `langsmith`, `fitz`, `tiktoken`), `app.database`, `app.models`.
- Used by: Routers and other services. Cross-service composition is common.

**Repository layer (Supabase clients):**
- Purpose: Persistence. There is no dedicated repository module; Supabase calls are made inline.
- Location: `backend/app/database.py`
- Contains:
  - `get_supabase_client()` -- service-role client (bypasses RLS). Used for cross-user reads, admin ops.
  - `get_supabase_authed_client(token)` -- anon client with user JWT (RLS-enforced).
- Pattern: `client.table("...").select(...).eq(...).execute()` chained-builder calls inline in routers/services.

**Models layer (Pydantic schemas):**
- Purpose: Validate LLM structured outputs, persist tool-call records, type cross-service contracts.
- Location: `backend/app/models/`
- Files: `agents.py`, `bjr.py`, `graph.py`, `metadata.py`, `pdp.py`, `rerank.py`, `tools.py`.

**Database layer (Supabase Postgres):**
- Migrations: `supabase/migrations/001_*.sql` through `027_*.sql` (numbered, append-only, blocked from edits by PreToolUse hook).
- Extensions: `pgvector`, `tsvector`, `pg_trgm`.
- RLS enforced on every user-data table.

**Frontend SPA (Presentation):**
- Location: `frontend/src/`
- Stack: React 19 + Vite + Tailwind + shadcn/ui + base-ui (tooltips). React Router v6.
- State: `useChatState` hook + `ChatContext`; `AuthContext`, `ThemeContext`, `I18nContext` providers; `useSidebar` for layout.

## Data Flow

**Flow 1 -- Chat with tool-calling and SSE streaming:**

End-to-end trace of `POST /chat/stream` (`backend/app/routers/chat.py`):

1. Frontend: `ChatPage` -> `useChatState.sendMessageToThread()` calls `apiFetch('/chat/stream', { method: 'POST', body: { thread_id, message, parent_message_id } })` (`frontend/src/hooks/useChatState.ts:124`). `apiFetch` injects `Authorization: Bearer <jwt>` from `supabase.auth.getSession()` (`frontend/src/lib/api.ts:6`).
2. Auth: `get_current_user` (`backend/app/dependencies.py:8`) validates JWT via `client.auth.get_user(token)`, checks `user_profiles.is_active`, auto-creates profile for new signups, returns `{id, email, token, role}`.
3. Thread validation: `chat.py:43-53` confirms thread ownership.
4. History assembly: branch-aware. If `parent_message_id` is given, walks the ancestor chain via `parent_message_id`; else loads flat history ordered by `created_at` (`chat.py:56-84`).
5. User message persisted into `messages` with `parent_message_id` link before streaming (`chat.py:91-98`).
6. System settings loaded via `get_system_settings()` (single-row `system_settings`, 60s TTL).
7. SSE generator wrapped in `StreamingResponse(..., media_type="text/event-stream")` with `Cache-Control: no-cache` and `X-Accel-Buffering: no`.
8. Branch A -- multi-agent (`settings.agents_enabled=true`):
   - `agent_service.classify_intent(message, history, openrouter, orch_model)` returns the agent name.
   - Emit `agent_start: {agent, display_name}`.
   - Build messages with the agent's `system_prompt`; restrict tools to `agent.allowed_tools`.
9. Branch B -- single-agent: uses the global `SYSTEM_PROMPT` and full tool registry from `tool_service.get_available_tools()`.
10. Tool-calling loop (`_run_tool_loop`, `chat.py:108-161`), up to `tools_max_iterations`:
    - `openrouter.complete_with_tools(messages, tools, model)` returns `{tool_calls, content}`.
    - If empty `tool_calls`, break.
    - For each call: emit `tool_start: {tool, input}` -> `tool_service.execute_tool(name, args, user_id, ctx)` -> record `ToolCallRecord` -> emit `tool_result: {tool, output}` -> append assistant `tool_calls` and `tool` role messages.
11. Tool dispatch (`ToolService.execute_tool`):
    - `search_documents` -> `HybridRetrievalService.retrieve(...)` with `filter_tags`/`filter_folder_id`/`filter_date_from`/`filter_date_to`.
    - `query_database` -> SQL guard rejects writes (`_WRITE_KEYWORDS` regex), enforces `WHERE user_id = :user_id`.
    - `web_search`, `kb_list_files`, `kb_read_document`, etc.
12. Hybrid retrieval (`backend/app/services/hybrid_retrieval_service.py:46`):
    - Cache check (`_retrieval_cache`, 5min TTL, MD5 of query+user+filters).
    - Optional bilingual query expansion (`_expand_query` via LLM).
    - Parallel `_vector_search` (pgvector cosine) + multiple `_fulltext_search` (tsvector) via `asyncio.gather`.
    - Weighted Reciprocal Rank Fusion using `rag_vector_weight` / `rag_fulltext_weight` from `system_settings`.
    - Optional cross-encoder rerank (Cohere or LLM, `RerankResponse` Pydantic model).
    - Neighbor chunk expansion (+/-N adjacent chunks).
    - Optional GraphRAG entity context.
    - Cache write, return.
13. Final answer streaming via `openrouter_service.stream_response(messages, model)`. Each token becomes `delta: {delta, done: false}`.
14. Persistence: assistant message inserted with `parent_message_id = user_msg_id`. If tool calls happened, `tool_calls` JSONB column is set to `ToolCallSummary(agent, calls).model_dump()` (`backend/app/models/tools.py`).
15. Auto-title: if `thread.title == "New Thread"`, a small LLM call generates a <=6-word title and emits `thread_title: {thread_id, title}`.
16. Done: `delta: {delta: "", done: true}` terminates the stream.
17. Frontend (`useChatState.ts:138-183`): reads SSE stream, dispatches by `event.type`: `thread_title` (update sidebar), `agent_start`/`agent_done` (toggle banner), `tool_start`/`tool_result` (update tool badges), `delta` (append to `streamingContent`). After `done`, refetches all messages and rebuilds the branch tree via `messageTree.buildChildrenMap` + `getActivePath`.

**SSE event sequence:**
```
agent_start -> tool_start -> tool_result -> tool_start -> tool_result -> ... ->
delta (progressive tokens) -> ... -> thread_title (first exchange only) ->
agent_done -> delta {done: true}
```

**Flow 2 -- Document upload + RAG ingestion:**

1. Frontend posts `apiFetch('/documents/upload', { method: 'POST', body: FormData })` from `DocumentsPage` / `FolderTree`.
2. Router `backend/app/routers/documents.py:33` validates MIME (PDF, TXT, MD, DOCX, CSV, HTML, JSON) and 50MB limit.
3. Deduplication via SHA-256 against `documents.content_hash` for the same `user_id`. `completed` -> return as duplicate; `pending`/`processing` -> 409; `failed` -> clean up storage and retry.
4. Service-role client uploads bytes to Supabase Storage bucket `settings.storage_bucket`.
5. Insert `documents` row with `status='pending'`, `content_hash`, `folder_id`, empty `metadata`.
6. `BackgroundTasks.add_task(process_document, doc_id)` -> 202.
7. Ingestion (`backend/app/services/ingestion_service.py`):
   - Status -> `processing`.
   - `parse_text_async` (line 23): PyMuPDF (`fitz`) for PDFs; auto-detects scanned PDFs and falls back to GPT-4o vision OCR via `VisionService.ocr_pdf()`. DOCX via `python-docx`; CSV stdlib; HTML via BeautifulSoup; JSON pretty-printed.
   - Structure-aware chunking (token-counted via `tiktoken`).
   - `metadata_service.extract_metadata(...)` -> `{title, author, category, tags, summary, date_period}`.
   - `embedding_service.embed_chunks_batch(chunks, model)` -- OpenAI embeddings (default `text-embedding-3-small`, custom override).
   - Bulk-insert into `chunks` (`embedding vector(1536)` + `tsv tsvector` generated column).
   - Optional `graph_service` populates `graph_entities`/`graph_relations`.
   - Status -> `completed` with `chunk_count`, `metadata`, OCR info.
8. Frontend `useDocumentRealtime` subscribes to `documents` row changes via Supabase Realtime; UI updates live.

**Flow 3 -- Auth (RBAC):**

1. Sign-in: `AuthPage` -> Supabase Auth -> JWT in browser session.
2. Frontend `<AuthGuard>` (`frontend/src/components/auth/AuthGuard.tsx`) checks `AuthContext.session`; redirects to `/auth` if absent.
3. `<AdminGuard>` checks `user.app_metadata.role === 'super_admin'`.
4. Backend `get_current_user` returns `{id, email, token, role}`. `require_admin` and `require_dpo` are role-gated wrappers (`backend/app/dependencies.py:40-53`).
5. DB-level RBAC: RLS uses `(auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin'`. Admin role set via `python -m scripts.set_admin_role <email>` writing `auth.users.raw_app_meta_data`.
6. Audit: every mutation calls `audit_service.log_action(...)` -> `audit_log` table.

**State Management (Frontend):**
- React Context: `AuthContext`, `ThemeContext`, `I18nContext`.
- `useChatState` hook owns chat-screen state (threads, messages, branch selections, streaming buffers).
- `ChatContext` exposes `useChatState` to nested components.
- `useSidebar` controls panel collapse.
- Realtime via `supabase.channel(...)` (e.g., `useDocumentRealtime`).
- Branch tree maintained client-side: `buildChildrenMap(allMessages)` + `getActivePath(childrenMap, branchSelections)` (`frontend/src/lib/messageTree.ts`).

## Key Abstractions

**`HybridRetrievalService`** (`backend/app/services/hybrid_retrieval_service.py`):
- The RAG retrieval engine. Single async entry point `retrieve()` handles cache, query expansion, parallel hybrid search, RRF fusion, rerank, neighbor expansion.
- Pattern: class with async methods; `@traceable` LangSmith decoration on `retrieve` and sub-methods.
- Cache: in-process `_retrieval_cache: dict[str, tuple[float, list[dict]]]`, 5min TTL, 1000-entry cap.
- Identified as a god-node / cross-community bridge in the graphify report -- changes here cascade across chat, document tools, dashboards.

**`ToolService`** (`backend/app/services/tool_service.py`):
- Tool registry + dispatcher. Defines `TOOL_DEFINITIONS` (OpenAI tool-calling schema) and `execute_tool(name, args, user_id, ctx)`.
- Tools: `search_documents`, `query_database`, `web_search`, `kb_list_files`, `kb_read_document`, plus more KB exploration tools.
- SQL safety: `_WRITE_KEYWORDS` regex blocks writes; `:user_id` binding required.
- Used by `chat.py` (single-agent) and `agent_service` (sub-agent tool subsetting).

**`agent_service`** (`backend/app/services/agent_service.py`, module-level):
- Multi-agent registry with intent classification.
- `classify_intent(message, history, openrouter, orch_model)` -> `AgentClassification` (Pydantic).
- `get_agent(name)`, `get_agent_tools(agent, all_tools)`.
- 4 agents: `general`, `research`, plus 2 others.
- Each agent has `system_prompt`, `display_name`, `allowed_tools`, `max_iterations`.

**`document_tool_service`** (`backend/app/services/document_tool_service.py`):
- LLM-powered document tools (create / compare / compliance / analyze).
- `_llm_json(prompt, schema_model, ctx)` helper -- OpenRouter call with `response_format: {"type": "json_object"}`, parsed via Pydantic.
- Confidence gating: `confidence_score >= 0.85` -> `auto_approved`; below -> `pending_review` (queues into approvals).
- Used by `backend/app/routers/document_tools.py`.

**`OpenRouterService`** (`backend/app/services/openrouter_service.py`):
- Wrapper around OpenRouter with `AsyncOpenAI` client.
- `complete_with_tools(messages, tools, model)` (non-streaming for tool-call rounds), `stream_response(messages, model)` (async generator yielding `{delta, done}`).

**`EmbeddingService`** (`backend/app/services/embedding_service.py`):
- OpenAI embedding generation + retrieval RPCs. Owns `embed_chunks_batch`, `embed_query`, `retrieve_chunks_with_metadata` (Supabase RPC `match_chunks` with metadata filters).

**`get_system_settings()`** (`backend/app/services/system_settings_service.py`):
- Cached read of the single-row `system_settings` table (60s TTL).
- The table has columns, NOT key/value pairs. Always use this helper.

## Entry Points

**Backend:**
- File: `backend/app/main.py`
- Triggered by: `uvicorn app.main:app --reload --port 8000` (local), Railway in production.
- Responsibilities:
  1. `lifespan` async context manager configures LangSmith and resets stuck `processing` documents to `pending` on cold start.
  2. Constructs `FastAPI(title="RAG Masterclass API", lifespan=lifespan)`.
  3. CORS middleware allows origins from `settings.frontend_url`.
  4. Mounts 21 routers via `app.include_router(...)` (lines 36-56).
  5. Exposes `GET /health` returning `{"status": "ok"}`.

**Frontend:**
- File: `frontend/src/main.tsx`
- Triggered by: Vite dev server (`npm run dev`) or production build served by Vercel.
- Responsibilities: `createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>)`.

**Frontend router:**
- File: `frontend/src/App.tsx`
- Provider stack: `BrowserRouter -> AuthProvider -> ThemeProvider -> I18nProvider -> TooltipProvider`.
- `<AuthGuard>` wraps `<AppLayout>` for all authenticated routes; `<AdminGuard>` further gates `/admin/*`.
- `<AppLayout>` (`frontend/src/layouts/AppLayout.tsx`) renders 60px IconRail + 340px collapsible sidebar + `<Outlet />` content area.

**Background entry point:**
- `BackgroundTasks.add_task(process_document, doc_id)` in `backend/app/routers/documents.py` -- spawns ingestion in the FastAPI worker (no Celery / queue).

## Error Handling

**Strategy:** Defensive at HTTP boundaries (`HTTPException` with status + detail); permissive within streaming generators (catch + log, never break the stream).

**Patterns:**
- Auth failures raise `HTTPException(401, "Invalid or expired token")` from `get_current_user` (`backend/app/dependencies.py:34-37`). `apiFetch` parses the error body and throws.
- Streaming errors caught inside `event_generator()` (`chat.py:238-240`) and logged via `logging.getLogger(__name__).error(..., exc_info=True)` -- the SSE stream still terminates cleanly with `{done: true}`.
- Tool execution errors wrapped per-tool: failures become `{"error": str(e)}` in `tool_output` and an `error` field on `ToolCallRecord` (`chat.py:139-143`). The loop continues so the LLM can react.
- LLM JSON parsing errors surface from Pydantic validation; the calling route returns 422 or auto-retries.
- Ingestion failures flip `documents.status` to `failed`; the `/documents/upload` retry path cleans up the failed row.
- PreToolUse hooks auto-lint .ts/.tsx (ESLint + tsc) and .py (py_compile) on every edit; block edits to `.env` and applied migrations 001-027.

## Cross-Cutting Concerns

**Logging:**
- Backend: stdlib `logging.getLogger(__name__)`; service-level `logger` defined at module top.
- LangSmith tracing: `@traceable(name="...")` on hot paths (retrieval, embeddings). Configured via `configure_langsmith()` in `lifespan`.
- Frontend: `console.*` only.

**Validation:**
- Backend: Pydantic for request bodies, `system_settings` shape, LLM `json_object` outputs, tool-call records (`ToolCallRecord`, `ToolCallSummary`), agent classifications.
- Frontend: TypeScript types from `frontend/src/lib/database.types.ts` (Supabase-generated) + hand-written `SSEEvent` discriminated union.

**Authentication:**
- Token: Supabase JWT. Frontend reads from `supabase.auth.getSession()`; backend validates via `client.auth.get_user(token)`.
- RBAC: `app_metadata.role` in {`user`, `dpo`, `super_admin`}. Enforced at three layers -- frontend `<AdminGuard>`, backend `require_admin` dependency, Postgres RLS predicate on `auth.jwt()`.
- Profile gate: `user_profiles.is_active = false` returns 403 even with a valid JWT.

**Audit:**
- `audit_service.log_action(user_id, user_email, action, resource_type, resource_id)` called from every mutating router.
- Read at `/admin/audit`.

**Caching:**
- `system_settings`: 60s TTL in-process cache.
- Retrieval results: 5min TTL keyed by `(query, user_id, top_k, filters)`.
- No Redis -- all caches are in-process. Multi-instance deployments rely on cache miss tolerance.

**Realtime:**
- Supabase Realtime channels (Postgres logical replication) on `documents` and `messages`. Subscribed via `frontend/src/hooks/useDocumentRealtime.ts`.

**Observability:**
- LangSmith for LLM call tracing.
- Health check: `GET /health` (used by Railway and `/deploy-lexcore`).

---

*Architecture analysis: 2026-04-25*
