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
- **PR**: #2 merged to master via squash merge (commit `c1561fe`)

#### Sub-Plan Files

- `.claude/plans/expressive-tinkering-avalanche.md`

### Module 9: RBAC Settings Architecture ✅ COMPLETE

- [x] Migration `backend/migrations/008_rbac_settings.sql` — `system_settings` (single-row, admin-only RLS), `user_preferences` (per-user RLS), `is_super_admin()` SQL helper
- [x] Admin promotion script `backend/scripts/set_admin_role.py` — CLI to set `app_metadata.role = super_admin` via Supabase Admin API
- [x] Backend `dependencies.py` — extract `role` from JWT `app_metadata`, add `require_admin` FastAPI dependency (403 for non-admins)
- [x] System settings service `backend/app/services/system_settings_service.py` — cached reader with 60s TTL, service-role client
- [x] Admin settings router `backend/app/routers/admin_settings.py` — `GET/PATCH /admin/settings` (admin-only)
- [x] User preferences router `backend/app/routers/user_preferences.py` — `GET/PATCH /preferences` (per-user)
- [x] Refactored `chat.py` + `documents.py` — replaced `get_or_create_settings` with `get_system_settings()`
- [x] Removed deprecated `user_settings.py` router and registration
- [x] Frontend `AuthContext` — provides `user`, `role`, `isAdmin` from JWT `app_metadata`
- [x] Frontend `AdminGuard` component — redirects non-admins away from admin routes
- [x] Frontend `AdminSettingsPage` — Global Configuration Dashboard (LLM, embedding, RAG tuning, tools, agents)
- [x] Frontend `SettingsPage` refactored — converted to user preferences (theme picker + notification toggle)
- [x] Frontend routing — `/admin/settings` with `AuthGuard` + `AdminGuard`, `AuthProvider` wrapping all routes
- [x] Frontend `ChatPage` — conditional Shield icon in sidebar nav for admins

#### Module 9 Architecture Summary

- **3-layer enforcement**: Database RLS (`is_super_admin()` checks JWT claim), Backend (`require_admin` dependency), Frontend (`AdminGuard` component)
- **Role storage**: Supabase `auth.users.raw_app_meta_data.role` — embedded in JWT, only writable via service-role key
- **System settings**: Single-row table (`CHECK (id = 1)`), stores LLM model, embedding model, RAG params, tool/agent config
- **User preferences**: Per-user table with theme and notifications_enabled
- **Settings decoupled**: System config (admin-only, DB table) vs user preferences (per-user, personal)
- **Cache**: 60s TTL on system settings to avoid DB hit per request
- **Promotion**: `python -m scripts.set_admin_role <email>` — user must sign out/in for JWT refresh
- **Backward compatible**: `chat.py` and `documents.py` read from `system_settings` instead of per-user `user_settings`
- **PR**: #4 merged to master

### UI Improvements ✅ COMPLETE

- [x] Animated thinking indicator — bouncing dots animation (`ThinkingIndicator.tsx`) while waiting for LLM response, replaces static blinking cursor
- [x] Collapsible thread groups — threads grouped by date (Today, Yesterday, Previous 7 Days, Older) with expand/collapse chevrons and count badges
- **PR**: #5 merged to master

### UI Redesign ✅ COMPLETE

- [x] Dark navy theme — oklch color palette, purple accent, removed light mode
- [x] Layout system — Icon rail (vertical nav) + collapsible ThreadPanel + content area via `AppLayout.tsx`
- [x] ChatPage refactor — 231 → 35 lines, state extracted to `useChatState.ts` hook + `ChatContext.tsx`
- [x] Welcome screen — brand icon, greeting, `MessageInput`, `SuggestionChips` (interactive, pre-fills chat input on click)
- [x] Full i18n — Indonesian (default) + English, `I18nProvider` with localStorage persistence
- [x] i18n coverage — AuthPage, FileUpload, DocumentList all use `useI18n()` translations
- [x] Admin input styling — number inputs use `bg-secondary text-foreground` for dark theme
- [x] Deleted `App.css` — styles consolidated into `index.css` with CSS variables

#### UI Redesign Architecture Summary

- **Layout**: `AppLayout` wraps `<Outlet>` with `IconRail` (60px) + conditional `ThreadPanel` (240px); thread panel shown only on chat routes
- **State**: `useChatState` hook manages threads, messages, streaming, tool/agent events; exposed via `ChatContext`
- **i18n**: `I18nProvider` → `useI18n()` → `t(key, params?)` with `{param}` interpolation; 2 locales (id, en); persisted to localStorage
- **Theme**: Dark-only, oklch color space, custom CSS variables for icon-rail and sidebar colors
- **Components**: `IconRail` (brand + nav + avatar), `ThreadPanel` (new chat + date-grouped threads), `UserAvatar` (initials + sign-out menu), `WelcomeScreen` (greeting + input + chips)

### Admin i18n + Cleanup ✅ COMPLETE

- [x] AdminSettingsPage fully i18n-ized — 30 translation keys (Indonesian + English) for all sections: LLM, embedding, RAG config, tool calling, sub-agents, errors, save actions
- [x] `.gitignore` updated — rules for `*.png`, `*.zip`, `excalidraw.log`, `.playwright-mcp/` to remove design asset clutter
- [x] UI redesign deployed to production (Vercel + Railway)

### Module 10: Conversation Branching ✅ COMPLETE

- [x] Migration `supabase/migrations/009_conversation_branching.sql` — add `parent_message_id` column, index, backfill existing linear chains
- [x] Backend `chat.py` — accept `parent_message_id`, branch-aware history loading (walk ancestor chain), chain user + assistant message inserts
- [x] Frontend `messageTree.ts` — `buildChildrenMap`, `getActivePath`, `getForkPoints` utilities
- [x] Frontend `useChatState.ts` — `allMessages`, `branchSelections`, `forkParentId` state; `handleSwitchBranch`, `handleForkAt`, `handleCancelFork` handlers
- [x] Frontend `MessageView.tsx` — fork button (GitFork icon on hover), `BranchIndicator` (1/3 with arrows) at fork points
- [x] Frontend `MessageInput.tsx` — fork-mode banner with cancel button
- [x] Frontend `ChatPage.tsx` — wire new props from context
- [x] Frontend `database.types.ts` — `parent_message_id` on Message interface
- [x] i18n — `branch.forkMode`, `branch.fork`, `branch.cancel` in Indonesian + English
- [x] End-to-end tested — backward compat (existing threads load), new message chaining, fork creation (two children of same parent), branch-aware LLM history (only ancestor messages sent)

#### Module 10 Architecture Summary

- **Message tree**: `parent_message_id` self-FK on `messages` table; adjacency list pattern
- **Backfill**: Existing linear conversations auto-linked via `LAG()` window function in migration
- **History construction**: When `parent_message_id` provided, backend walks ancestor chain from that message to root; only ancestor messages sent to LLM
- **Frontend tree**: `buildChildrenMap` groups messages by parent; `getActivePath` walks tree following `branchSelections`; only the active branch path is rendered
- **UI**: Fork icon appears on hover; clicking sets `forkParentId` and shows banner in input area; after send, new branch created; fork points show `BranchIndicator` with left/right arrows to switch
- **Backward compatible**: Existing flat threads work unchanged (backfill sets parent chains; `parent_message_id=None` falls back to flat mode)
- **New env vars**: None — uses existing infrastructure
- **New tables**: None — single column addition to `messages`

#### Sub-Plan Files

- `.claude/plans/enumerated-hugging-otter.md`

### Figma UI Migration ✅ COMPLETE

- [x] Shared components — `FeaturePageLayout`, `DropZone`, `HistorySection`, `EmptyState`, `SectionLabel` in `components/shared/`
- [x] IconRail expanded to 6 nav items (Chat, Documents, Create, Compare, Compliance, Analysis) + flyout "More Modules" menu
- [x] `DocumentCreationPage` — doc type selector, form fields, language toggle, reference/template uploads (static UI)
- [x] `DocumentComparisonPage` — dual document upload, swap button, comparison focus selector (static UI)
- [x] `ComplianceCheckPage` — doc upload, framework selector, scope multi-select, context textarea (static UI)
- [x] `ContractAnalysisPage` — doc upload, analysis type multi-select, governing law, depth selector (static UI)
- [x] All 4 pages wired to backend with API calls, loading states, and result display panels
- [x] Full i18n support (Indonesian + English) for all new screens (~80 keys per locale)
- [x] Feature accent colors added (creation/purple, management/cyan, compliance/emerald, analysis/amber)
- [x] shadcn/ui select, textarea, popover components installed
- [x] Routes added to `App.tsx` for `/create`, `/compare`, `/compliance`, `/analysis`

### Document Tool Backend ✅ COMPLETE

- [x] Backend service `document_tool_service.py` — Pydantic response models + LLM prompts for all 4 operations (create, compare, compliance, analyze), reuses `parse_text` from ingestion service, OpenRouter with `json_object` response format
- [x] Backend router `document_tools.py` — 4 FormData endpoints (`POST /document-tools/create`, `/compare`, `/compliance`, `/analyze`), file upload validation, auth required
- [x] Router registered in `main.py`
- [x] Frontend wiring — all 4 pages updated with controlled form state, `apiFetch` calls, loading spinners, error display, structured result rendering in right panel
- [x] Create page: generated document preview (title, summary, content)
- [x] Compare page: differences table with significance badges, risk assessment, recommendation
- [x] Compliance page: overall status badge (pass/review/fail), findings list, missing provisions
- [x] Analysis page: risk cards, obligations table, critical clauses, missing provisions
- [x] QA fix: Generate Draft button disabled until required fields are filled (per doc type validation)
- [x] Backend fix: bilingual document creation handles dict content response from LLM
- [x] Result persistence: `document_tool_results` Supabase table with RLS, history endpoints, frontend history sidebars

#### Document Tool Architecture Summary

- **Pattern**: File upload → parse text (reuse ingestion `parse_text`) → LLM structured output (OpenRouter + `json_object` format) → Pydantic validation → JSON response → persist to `document_tool_results`
- **Persistence**: Results stored in `document_tool_results` table (JSONB), history sidebar shows recent results per tool type, `GET /document-tools/history` endpoint
- **File handling**: FormData with optional files (reference/template for creation, two docs for comparison, single doc for compliance/analysis)
- **Truncation**: Document text capped at ~48k chars (~12k tokens) to stay within LLM context
- **Validation**: Red border + inline error messages on required fields when clicking disabled button; per doc type required field lists
- **No new dependencies**: Reuses existing OpenRouter service, ingestion parser, auth middleware

#### Sub-Plan Files

- `.agent/plans/11.figma-ui-migration.md`

### Welcome Screen Redesign ✅ COMPLETE

- [x] Sparkle icon replaces "K" badge, gradient text for user name
- [x] `WelcomeInput` — large card-style input with action bar (attach, doc icon, "Legal AI v1.0" label, mic, send)
- [x] `SuggestionCards` — Bento grid with left accent borders + inline icons (no icon circles), responsive (stacks on mobile)
- [x] `ThreadPanel` — search bar, "Chat History" subtitle, fully collapsible (340px expanded ↔ hidden), toggle in IconRail

### Page Layout Redesign ✅ COMPLETE

- [x] `DocumentCreationPage` — 3-column layout (Icon Rail | Form 75% + History 25% | Preview empty state), dynamic form fields per doc type (Generic, NDA, Sales, Service), output language radio, reference/template uploads
- [x] `DocumentsPage` — 3-column layout with upload section (dropzone, recent uploads, storage quota), filter section (type filters, status checkboxes), main area (top bar with search + grid/list toggle, responsive document card grid)
- [x] `DocumentComparisonPage` — same 3-column pattern with dual doc upload, swap button, comparison focus, blank results area
- [x] `ComplianceCheckPage` — same 3-column pattern with framework selector, scope multi-select, blank results area
- [x] `ContractAnalysisPage` — same 3-column pattern with analysis type, governing law, depth selector, blank results area
- [x] All column 2 panels standardized to 340px width
- [x] Unified sidebar collapse — shared state via `useSidebar` hook, `PanelLeftClose`/`PanelLeftOpen` icons, panels collapse fully (no 50px strip)
- [x] Settings/Admin pages — 3-column layout with section navigation, centered content with section icons

### Design Quality (A / A+) ✅ COMPLETE

- [x] **Mobile responsive** — hamburger menu header, panel overlays with backdrop, responsive grids, FAB on all feature pages
- [x] **AI slop eliminated** — icon-in-circle cards replaced with accent-border + inline icon, pulse rings removed from EmptyState
- [x] **Touch targets** — all interactive elements 40px+, icon rail 44px, focus-ring on all custom buttons
- [x] **Accessibility** — `prefers-reduced-motion` support for all animations, focus-visible rings on all interactive elements
- [x] **Micro-interactions** — `interactive-lift` hover effect, purposeful active/press states
- [x] **Typography hierarchy** — `font-extrabold tracking-tight` on page headings, 3-tier weight system
- [x] **Document card variety** — category-colored left borders, colored dots, multi-format file type badges (PDF/DOC/MD/CSV/JSON/TXT)
- [x] **Chat layout** — input pinned to bottom, messages scroll above (matches ChatGPT/Claude pattern)
- [x] **Indonesian language** — all panel subtitles translated, consistent language throughout
- [x] **Design Score: A** | **AI Slop Score: A+** (verified by /design-review regression audit)

### 2026 Design System ✅ COMPLETE

- [x] **Font**: Geist Variable (single family, not a default stack)
- [x] **Colors**: oklch/oklab color space, 11 unique colors, coherent dark navy palette
- [x] **Glassmorphism** — `glass` utility on Icon Rail, ThreadPanel, MessageInput, AuthPage, WelcomeInput
- [x] **Layered shadows** — `--shadow-xs/sm/md/lg` CSS variables
- [x] **Gradient accents** — gradient user message bubbles, gradient text for user name
- [x] **Bento grid** — Row 1: equal halves, Row 2: wider left (3fr) + narrower right (2fr)
- [x] **Mesh background** — radial glows, dot grid texture, floating orbs
- [x] **Staggered animations** — `stagger-children` for sequential card entrance
- [x] **Feature accent colors** — per-page left border colors (purple/cyan/emerald/amber)
- [x] **Icon Rail gradient bar** — 3px gradient left accent on active nav items

---

## Deployment Status

### Frontend (Vercel) — ✅ DEPLOYED

- **URL**: https://frontend-one-rho-88.vercel.app
- **Platform**: Vercel (auto-detected Vite)
- **Env vars**: `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, `VITE_API_BASE_URL` (points to Railway backend)
- **Redeploy**: `cd frontend && npx vercel --prod`

### Backend (Railway) — ✅ DEPLOYED

- **URL**: https://api-production-cde1.up.railway.app
- **Platform**: Railway (Dockerized FastAPI)
- **Health check**: `GET /health` → `{"status": "ok"}`
- **CORS**: Configured via `FRONTEND_URL` env var (comma-separated origins)
- **Redeploy**: `cd backend && railway up`

### Git History

| PR | Branch | Description | Status |
|----|--------|-------------|--------|
| #1 | `feat/module-6-7` | Modules 6+7 — Hybrid Search + Tool Calling | Merged |
| #2 | `feat/module-8-sub-agents` | Module 8 — Sub-Agent Architecture | Merged |
| #3 | `feat/deploy` | Deploy backend (Railway) + frontend (Vercel) | Merged |
| #4 | `feat/rbac-settings` | Module 9 — RBAC Settings Architecture | Merged |
| #5 | `feat/ui-improvements` | Animated thinking indicator + collapsible thread groups | Merged |

---

## PJAA CLM Platform Upgrade

Based on PJAA stakeholder survey (53 questions, 7 findings) — see `References/PJAA-Research-Synthesis-CLM-Compliance.docx.md`.
Full gap analysis and specs: `.agent/plans/15.pjaa-clm-gap-analysis-specs.md`

### Phase 1: Go-Live Foundation (Weeks 1-8)

#### Feature 1: Audit Trail & Activity Logging ✅ COMPLETE

- [x] Migration `supabase/migrations/011_audit_trail.sql` — `audit_logs` table with 4 indexes, RLS enabled (admin-only read)
- [x] Backend `audit_service.py` — fire-and-forget `log_action()` function, service-role client
- [x] Backend `audit_trail.py` router — `GET /admin/audit-logs` (paginated + filtered), CSV export, distinct actions
- [x] Instrumented 4 existing routers (documents, document_tools, admin_settings, threads) with audit log calls
- [x] Frontend `AuditTrailPage.tsx` — admin-only, date/action/resource filters, pagination, CSV export button
- [x] Route at `/admin/audit`, nav link in SettingsPage (mobile + desktop)
- [x] i18n: 17 keys in both Bahasa Indonesia and English
- [x] Security hardening: RLS enabled on audit_logs (caught by adversarial review — was exposed via PostgREST)
- **Commit**: `59a277a`, hardening fix: `ca60078`

#### Feature 7: Bahasa Indonesia Full-Text Search ✅ COMPLETE

- [x] Migration `supabase/migrations/010_bahasa_fts.sql` — FTS trigger + RPC switched from `'english'` to `'simple'` config
- [x] Backfill existing document chunks with new config
- [x] No backend/frontend changes needed — existing search automatically benefits
- **Commit**: `59a277a`

#### Feature 2: AI Confidence Scoring & HITL Gates ✅ COMPLETE

- [x] Migration `supabase/migrations/012_confidence_hitl.sql` — `confidence_score`, `review_status`, `reviewed_by/at/notes` on `document_tool_results`; `confidence_threshold` on `system_settings`; RLS for admin review access
- [x] All 4 Pydantic models updated with `confidence_score: float = 0.0`
- [x] All 4 LLM system prompts request `confidence_score` in JSON response
- [x] `_save_result` computes `review_status` based on configurable threshold (default 0.85)
- [x] Review queue endpoints: `GET /document-tools/review-queue`, `PATCH /document-tools/review/{id}` with `ReviewAction` Pydantic model
- [x] `get_result` endpoint updated — admins can view any user's results (for review)
- [x] `ConfidenceBadge.tsx` component — percentage badge + review status badge
- [x] Badges added to all 4 tool result pages (DocumentCreation, Comparison, Compliance, Analysis)
- [x] `ReviewQueuePage.tsx` — filter by status, approve/reject with notes, audit logged
- [x] `AdminSettingsPage.tsx` — HITL Gates section with threshold input + visual preview
- [x] i18n: 22 keys in both Bahasa Indonesia and English
- [x] Security hardening: `ReviewAction` Pydantic model (validates action, caps notes at 2000 chars), re-review guard (409 if not pending), `confidence_threshold` bounded to 0.0-1.0
- **Commit**: `7c4b20e`, hardening fix: `ca60078`

#### Feature 4: Obligation Lifecycle Tracker ✅ COMPLETE

- [x] Migration `supabase/migrations/013_obligations.sql` — `obligations` table with 15 columns, RLS (4 policies), 3 indexes, `updated_at` trigger, `check_overdue_obligations()` RPC
- [x] Backend `obligations.py` router — 7 endpoints: list (filtered), summary, create, extract from analysis, check-deadlines, update, soft-delete
- [x] Frontend `ObligationsPage.tsx` — summary cards (5 statuses), filter tabs, obligations table with status badges, deadline formatting (relative), "Mark Complete" button
- [x] "Import Obligations" button on `ContractAnalysisPage.tsx` — extracts obligations from analysis results into structured rows
- [x] IconRail nav item (`ClipboardList` icon) + route at `/obligations`
- [x] i18n: 23 keys in both Bahasa Indonesia and English
- **Commit**: `d5ca1be`

#### Feature 3: Enhanced Drafting Workbench — `[ ]` NOT STARTED

- [ ] Clause library table + CRUD
- [ ] Document templates table + CRUD
- [ ] 7 doc types (add vendor, JV, property lease, employment, SOP/board resolution)
- [ ] Per-clause risk scoring in generated documents

#### Feature 5: Approval Workflow Engine — `[ ]` NOT STARTED

- [ ] Workflow templates, approval requests, approval actions tables
- [ ] Sequential/parallel approval chains
- [ ] Mobile-first approval inbox (375px viewport)
- [ ] "Submit for Approval" button on doc creation & compliance results

#### Feature 6: MFA & Security Hardening — `[ ]` NOT STARTED

- [ ] Supabase TOTP MFA enrollment + challenge
- [ ] Admin user management (list, deactivate, reactivate)
- [ ] User profiles table (department, is_active, last_login)

### Phase 1 Summary

| Feature | Status | Commit | Lines |
|---------|--------|--------|-------|
| F1: Audit Trail | ✅ Done | `59a277a` | +1,994 |
| F7: Bahasa FTS | ✅ Done | `59a277a` | (included above) |
| F2: Confidence & HITL | ✅ Done | `7c4b20e` | +553 |
| Hardening (review fixes) | ✅ Done | `ca60078` | +30 |
| F4: Obligation Tracker | ✅ Done | `d5ca1be` | +1,519 |
| F3: Drafting Workbench | Not started | — | — |
| F5: Approval Workflows | Not started | — | — |
| F6: MFA & Security | Not started | — | — |

**Phase 1 progress: 4 of 7 features complete** (F1, F2, F4, F7)

### Phase 2: Enterprise Capabilities (Weeks 9-16) — NOT STARTED

- [ ] F8: Regulatory Intelligence Engine
- [ ] F9: WhatsApp Notifications
- [ ] F10: Executive Dashboard
- [ ] F11: Dokmee DMS Integration
- [ ] F12: Google Workspace Export

### Phase 3: Advanced Compliance (Months 5-6) — NOT STARTED

- [ ] F13: Point-in-Time Compliance Querying
- [ ] F14: UU PDP Compliance Toolkit
