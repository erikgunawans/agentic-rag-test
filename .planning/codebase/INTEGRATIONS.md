# External Integrations

**Analysis Date:** 2026-04-25

## APIs & External Services

**LLM (chat completions, tool-calling, document tools):**
- **OpenRouter** — OpenAI-compatible API at `https://openrouter.ai/api/v1`
  - SDK/Client: `openai>=2.30.0` (`AsyncOpenAI`) configured with custom `base_url`
  - Implementation: `backend/app/services/openrouter_service.py` (lines ~10-13 set `api_key=settings.openrouter_api_key`, `base_url="https://openrouter.ai/api/v1"`)
  - Auth env: `OPENROUTER_API_KEY`
  - Default model env: `OPENROUTER_MODEL=openai/gpt-4o-mini`
  - Used for: streaming chat (`stream_response`), tool-calling completions (`complete_with_tools`), document tools (`_llm_json` in `backend/app/services/document_tool_service.py`), agent classification, optional graph entity extraction
  - Tracing: `@traceable` decorators emit spans to LangSmith

**LLM (embeddings):**
- **OpenAI** — direct API
  - SDK/Client: `openai>=2.30.0` (`AsyncOpenAI`)
  - Implementation: `backend/app/services/embedding_service.py` (`embed_text`, `embed_batch`) and `backend/app/services/openai_service.py`
  - Auth env: `OPENAI_API_KEY`
  - Default model env: `OPENAI_EMBEDDING_MODEL=text-embedding-3-small`
  - Optional override: `CUSTOM_EMBEDDING_MODEL` (Phase 3 fine-tuned embeddings — infrastructure ready)
  - Legacy: `OPENAI_VECTOR_STORE_ID` (no longer used from Module 2 onward; kept for backward compat in `backend/app/services/openai_service.py`)

**Reranking:**
- **Cohere Rerank v2** — `https://api.cohere.com/v2/rerank`
  - SDK/Client: `httpx.AsyncClient` (no Cohere SDK; raw POST)
  - Implementation: `backend/app/services/hybrid_retrieval_service.py` `_cohere_rerank` (lines 290-317), gated by `rerank_mode == "cohere"` and presence of `COHERE_API_KEY`
  - Auth env: `COHERE_API_KEY` (sent as `Authorization: Bearer ...`)
  - Failure mode: warns and keeps original RRF order
  - Tracing: `@traceable(name="cohere_rerank")`

**Web Search (tool):**
- **Tavily** — `https://api.tavily.com/search`
  - SDK/Client: `httpx` raw POST
  - Implementation: `backend/app/services/tool_service.py` (lines 401-410); tool exposed as `web_search` in the tool-calling loop
  - Auth env: `TAVILY_API_KEY` (gated — when missing, the `web_search` tool is filtered out of the tool list)
  - Optional integration; degrades gracefully

**Document Management Integration (stub):**
- **Dokmee** — DMS connector
  - SDK/Client: planned `httpx` (currently stub)
  - Implementation: `backend/app/routers/integrations.py` (`/integrations/dokmee/status`, `/dokmee/browse`, `/dokmee/import`, `/dokmee/export`)
  - Auth source: `system_settings` table fields `dokmee_api_url` and `dokmee_api_key` (read via `get_system_settings()`)
  - Status: scaffolded — returns empty listings until API credentials are configured

**Google Workspace Export (OAuth):**
- **Google OAuth + Drive/Docs** — export chat results to Google Docs
  - Implementation: `backend/app/routers/google_export.py` (`/google/status`, `/google/callback`, `/google/export`)
  - Tokens stored in Postgres table `google_tokens` (per-user)
  - Configuration: `system_settings.google_client_id` (and matching client secret/redirect)
  - Auth flow: OAuth authorization code via `GoogleCallback.code`

**Observability / Tracing:**
- **LangSmith** — `langsmith==0.1.117`
  - Implementation: `backend/app/services/langsmith_service.py` `configure_langsmith()` invoked in `backend/app/main.py:12` lifespan startup
  - Decorators: `@traceable` on streaming chat, tool calls, embedding calls, retrieval, Cohere rerank
  - Auth env: `LANGSMITH_API_KEY`
  - Project env: `LANGSMITH_PROJECT=rag-masterclass`
  - Toggle: `LANGCHAIN_TRACING_V2=false` (default) — set to `true` to enable tracing

## Data Storage

**Primary Database:**
- **Supabase Postgres** (project `qedhulpfezucnfadlfiz`)
  - Extensions used: `pgvector` (embedding columns), `tsvector` (fulltext), RLS, triggers
  - Backend client: `supabase==2.7.4`
  - Two client modes in `backend/app/database.py`:
    - `get_supabase_client()` — service-role key, bypasses RLS (admin / system jobs)
    - `get_supabase_authed_client(token)` — anon key + user JWT, RLS-scoped queries
  - Connection envs: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`
  - Schema: 27+ numbered migrations under `backend/migrations/` (also `supabase/`)
  - RPC functions used for hybrid retrieval / metadata pre-filtering by `backend/app/services/hybrid_retrieval_service.py`

**File / Object Storage:**
- **Supabase Storage** — bucket configurable via `STORAGE_BUCKET` env (default `documents`)
  - Used for: uploaded contracts, generated DOCX exports
  - Access: same Supabase clients as DB

**Caching:**
- In-process caches only:
  - `system_settings` 60-second TTL cache in `backend/app/services/system_settings_service.py` (single-row table `id=1`)
  - Semantic cache (5-min TTL) for chat retrieval results (per `CLAUDE.md` LLM Pipeline notes)
  - `functools.lru_cache` on `get_settings()` in `backend/app/config.py:74`
- No external Redis / Memcached

**Realtime:**
- **Supabase Realtime** — used from frontend hook `frontend/src/hooks/useDocumentRealtime.ts` to subscribe to document status changes

## Authentication & Identity

**Auth Provider:**
- **Supabase Auth** — email/password with JWT
  - Frontend: `frontend/src/contexts/AuthContext.tsx`, `frontend/src/lib/supabase.ts`, `frontend/src/pages/AuthPage.tsx` (`signInWithPassword`, `signUp`)
  - Backend: `get_current_user` dependency (in `backend/app/dependencies.py`) validates JWT, hits `user_profiles` to check `is_active`, returns `{id, email, token, role}`
  - Admin: `require_admin` dependency checks `role == "super_admin"` (set via `raw_app_meta_data.role` in JWT)
  - Auto-provision: `user_profiles` row auto-created for new signups on first authenticated request

**Roles / RBAC:**
- Roles stored in JWT `app_metadata.role` and Postgres `user_profiles.role`
- RLS pattern for admins: `(auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin'`
- Admin promotion script: `python -m scripts.set_admin_role <email>`

## Monitoring & Observability

**Error Tracking:**
- None detected (no Sentry, Datadog, Bugsnag dependencies)

**Tracing:**
- LangSmith on LLM/retrieval pipelines (see above)

**Logs:**
- Python `logging` module in services (e.g. `logger.warning("Cohere reranking failed ...")` in `backend/app/services/hybrid_retrieval_service.py`)
- Railway captures stdout/stderr from the container; no log shipper configured

**Health endpoint:**
- `GET /health` → `{"status": "ok"}` (`backend/app/main.py:60-61`)

**Audit Trail:**
- Internal — `backend/app/services/audit_service.py` `log_action(...)` writes to `audit_log` table on all mutations (called from routers like `integrations.py`, `google_export.py`, etc.)

## CI/CD & Deployment

**Hosting:**
- **Frontend → Vercel**: `https://frontend-one-rho-88.vercel.app`
  - Deploys from `main` branch (NOT `master`) — `git push origin master:main` is required after pushing to master
  - SPA rewrite configured in `frontend/vercel.json`
  - Manual deploy: `cd frontend && npx vercel --prod --yes`
- **Backend → Railway**: `https://api-production-cde1.up.railway.app`
  - Container image built from `backend/Dockerfile` (`python:3.12-slim`)
  - Railway injects `$PORT`; uvicorn binds `0.0.0.0:$PORT`
  - Deploy command: `cd backend && railway up`
- **Database → Supabase managed** (project `qedhulpfezucnfadlfiz`)

**CI Pipeline:**
- No GitHub Actions / CI workflows detected
- Local pre-push checks via PostToolUse hooks (auto-lint `.ts/.tsx` and `.py` import-check) per `CLAUDE.md`
- Manual gates: `cd frontend && npm run lint && npx tsc --noEmit`, `cd backend && python -c "from app.main import app; print('OK')"`, `pytest tests/api/`

**Deploy aggregator:**
- `/deploy-lexcore` slash command runs the full pipeline (push to master + main, Railway up, Vercel prod, health check)

## Environment Configuration

**Required env vars (backend, `backend/app/config.py`):**
- `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` — required
- `OPENAI_API_KEY` — required (embeddings)
- `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` — required for chat (defaults to `openai/gpt-4o-mini`)

**Optional env vars:**
- `COHERE_API_KEY` — enables Cohere reranking
- `TAVILY_API_KEY` — enables `web_search` tool
- `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`, `LANGCHAIN_TRACING_V2` — observability
- `CUSTOM_EMBEDDING_MODEL` — fine-tuned embedding override
- `GRAPH_ENABLED`, `GRAPH_ENTITY_EXTRACTION_MODEL` — GraphRAG toggle
- `AGENTS_ENABLED`, `AGENTS_ORCHESTRATOR_MODEL` — multi-agent toggle
- `FRONTEND_URL` — CORS allow-origin (comma-separated for multiple)
- `STORAGE_BUCKET` — Supabase Storage bucket (default `documents`)

**Required env vars (frontend, `import.meta.env`):**
- `VITE_SUPABASE_URL` — `frontend/src/lib/supabase.ts:3`
- `VITE_SUPABASE_ANON_KEY` — `frontend/src/lib/supabase.ts:4`
- `VITE_API_BASE_URL` — `frontend/src/lib/api.ts:3` (backend Railway URL in prod)

**Secrets location:**
- Local: `.env` files (gitignored), template at `.env.example`
- Railway: project environment variables (injected at runtime)
- Vercel: project environment variables (`VITE_*` baked into client bundle at build time)
- Pre-tool hook blocks `.env` edits (per `CLAUDE.md` Automations)

**Runtime DB-backed config:**
- `system_settings` Postgres table (single row, `id=1`) holds runtime-tunable values:
  - `dokmee_api_url`, `dokmee_api_key` (`backend/app/routers/integrations.py:_get_dokmee_config`)
  - `google_client_id` (`backend/app/routers/google_export.py:_is_google_configured`)
  - RAG weights, rerank mode, fusion weights (admin-tunable via `/admin/settings`)
  - Read via `get_system_settings()` with 60s TTL (`backend/app/services/system_settings_service.py`)

## Webhooks & Callbacks

**Incoming:**
- `POST /google/callback` — Google OAuth authorization-code exchange (`backend/app/routers/google_export.py`)
- No third-party webhook receivers (Stripe, Twilio, etc.) detected

**Outgoing:**
- OpenRouter chat completions (streaming + tool-calling) — `backend/app/services/openrouter_service.py`
- OpenAI embeddings — `backend/app/services/embedding_service.py`, `backend/app/services/openai_service.py`
- Cohere rerank — `backend/app/services/hybrid_retrieval_service.py:_cohere_rerank`
- Tavily search — `backend/app/services/tool_service.py` (`web_search` tool)
- LangSmith trace ingestion — implicit via `@traceable`
- Supabase REST/Realtime/Storage — both backend (Python SDK) and frontend (JS SDK)
- Dokmee API — stubbed in `backend/app/routers/integrations.py` (will use `httpx` once configured)
- Google Drive/Docs export — `backend/app/routers/google_export.py`

## SSE / Streaming

**Server-Sent Events (custom protocol, no third-party):**
- Endpoint: `POST /chat` streams via `text/event-stream`
- Event sequence: `agent_start` → `tool_start` → `tool_result` → `delta` (progressive) → `done:true`
- Implementation: `backend/app/routers/chat.py` (consumes async generators from `OpenRouterService.stream_response`)

---

*Integration audit: 2026-04-25*
