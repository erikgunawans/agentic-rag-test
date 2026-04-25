# Codebase Structure

**Analysis Date:** 2026-04-25

## Directory Layout

```
claude-code-agentic-rag-masterclass-1/
|-- backend/                          # FastAPI backend (Python 3.14, venv)
|   |-- app/
|   |   |-- main.py                   # FastAPI app + lifespan + router mounts
|   |   |-- config.py                 # Pydantic Settings (env vars)
|   |   |-- database.py               # get_supabase_client / get_supabase_authed_client
|   |   |-- dependencies.py           # get_current_user, require_admin, require_dpo
|   |   |-- routers/                  # 22 HTTP routers (one per domain)
|   |   |-- services/                 # 18 service modules (domain logic)
|   |   `-- models/                   # Pydantic schemas
|   |-- scripts/                      # CLI utilities
|   |-- tests/api/                    # 8 pytest API test files
|   |-- requirements.txt
|   `-- venv/                         # Local virtualenv (gitignored)
|
|-- frontend/                         # React 19 + Vite SPA
|   |-- src/
|   |   |-- main.tsx                  # createRoot entry
|   |   |-- App.tsx                   # BrowserRouter + provider stack + routes
|   |   |-- index.css                 # Tailwind + design tokens (:root)
|   |   |-- pages/                    # 24 route-level page components
|   |   |-- components/{auth,chat,documents,bjr,layout,shared,ui}/
|   |   |-- contexts/                 # AuthContext, ChatContext
|   |   |-- hooks/                    # useChatState, useDocumentRealtime, useSidebar, useToolHistory
|   |   |-- layouts/                  # AppLayout
|   |   |-- lib/                      # api.ts, supabase.ts, messageTree.ts, models.ts, utils.ts, database.types.ts
|   |   |-- i18n/                     # I18nProvider (ID/EN)
|   |   |-- theme/                    # ThemeContext (light/dark)
|   |   `-- assets/
|   |-- vite.config.ts
|   |-- tailwind.config.js
|   `-- package.json
|
|-- supabase/migrations/              # 001_*.sql .. 027_*.sql (applied; do not edit)
|-- docs/                             # PRD, design specs, references
|-- tests/                            # Cross-cutting / e2e tests
|-- graphify-out/                     # Code knowledge graph (1,211 nodes / 192 communities)
|-- .planning/codebase/               # Codebase mapping docs (this directory)
|-- CLAUDE.md, AGENTS.md, PROGRESS.md, PRD.md, README.md, VERSION
`-- .mcp.json                         # MCP servers (context7, Supabase, Playwright)
```

## Directory Purposes

**`backend/app/main.py`** -- FastAPI bootstrap. `lifespan` configures LangSmith and recovers stalled `processing` documents. Mounts 21 routers. Exposes `GET /health`. (61 lines.)

**`backend/app/routers/`** -- HTTP layer; one router per domain. 22 files.
- Core: `chat.py` (SSE + tool-calling), `threads.py`, `documents.py`, `folders.py`.
- Document ops: `document_tools.py` (LLM create/compare/compliance/analyze).
- Phase 1 CLM: `clause_library.py`, `document_templates.py`, `approvals.py`, `obligations.py`, `audit_trail.py`, `user_management.py`.
- Phase 2: `regulatory.py`, `notifications.py`, `dashboard.py`, `integrations.py` (Dokmee), `google_export.py`.
- BJR: `bjr.py` (25 endpoints).
- Phase 3: `compliance_snapshots.py`, `pdp.py` (UU PDP).
- Settings: `admin_settings.py`, `user_preferences.py`.

**`backend/app/services/`** -- Domain logic. 18 files.
- RAG: `hybrid_retrieval_service.py` (god-node), `embedding_service.py`, `metadata_service.py`, `vision_service.py`, `ingestion_service.py`, `graph_service.py`.
- LLM: `openrouter_service.py` (chat + streaming), `openai_service.py` (embeddings only), `tool_service.py` (god-node), `agent_service.py` (multi-agent registry), `document_tool_service.py`.
- Cross-cutting: `system_settings_service.py`, `audit_service.py`, `langsmith_service.py`.
- Domain: `bjr_service.py`, `pdp_service.py`.

**`backend/app/models/`** -- Pydantic schemas. Files: `tools.py` (`ToolCallRecord`, `ToolCallSummary`), `agents.py` (`AgentClassification`, `AgentDefinition`), `metadata.py`, `rerank.py` (`RerankResponse`), `bjr.py`, `pdp.py`, `graph.py`.

**`backend/scripts/`** -- CLI utilities (`python -m scripts.<name>`): `set_admin_role`, `eval_rag`.

**`backend/tests/api/`** -- 8 pytest API tests against deployed backend. Run: `TEST_EMAIL=... TEST_PASSWORD=... API_BASE_URL=... pytest tests/api/ -v`.

**`frontend/src/pages/`** -- One file per route. 24 files. Naming: `<Domain>Page.tsx`. Examples: `ChatPage.tsx`, `DocumentsPage.tsx`, `DocumentCreationPage.tsx` (has BOTH mobile + desktop panels -- new sections must be added to both), `BJRDashboardPage.tsx`, `AdminSettingsPage.tsx`.

**`frontend/src/components/`** -- Reusable UI grouped by domain.
- `auth/` -- `AuthGuard`, `AdminGuard`, login/signup forms.
- `chat/` -- `MessageView`, `SuggestionCards`, `ToolBadges`, ...
- `documents/` -- `FolderTree`, `UploadZone`, `DocumentList` (mobile + desktop variants).
- `bjr/` -- BJR module components.
- `layout/` -- `IconRail`, `Sidebar`, `Header`.
- `shared/` -- Cross-domain widgets.
- `ui/` -- shadcn/ui primitives + base-ui shims (`tooltip.tsx` translates `asChild` -> `render`).

**`frontend/src/contexts/`** -- React Context providers (`AuthContext`, `ChatContext`). `ThemeContext` lives in `theme/`, `I18nContext` in `i18n/`.

**`frontend/src/hooks/`** --
- `useChatState.ts` -- Chat-screen state machine (threads, messages, branches, SSE streaming).
- `useDocumentRealtime.ts` -- Supabase Realtime on `documents`.
- `useSidebar.ts` -- Panel collapse.
- `useToolHistory.ts` -- Tool-call history badges.

**`frontend/src/layouts/AppLayout.tsx`** -- 60px IconRail + 340px collapsible sidebar + `<Outlet />` content area.

**`frontend/src/lib/`** --
- `api.ts` -- `apiFetch(path, opts)` injects Bearer JWT, handles errors.
- `supabase.ts` -- Supabase client singleton.
- `database.types.ts` -- Supabase-generated types + hand-written `SSEEvent` discriminated union, `Thread`, `Message`.
- `messageTree.ts` -- `buildChildrenMap` + `getActivePath` for branch-aware chat.
- `models.ts` -- Domain types not generated by Supabase.
- `utils.ts` -- `cn(...)` Tailwind class merger.

**`supabase/migrations/`** -- 27 numbered, append-only SQL migrations. Two `024_*.sql` files coexist by design (knowledge_base_explorer + rag_improvements). Editing 001-027 is BLOCKED by PreToolUse hook.

**`graphify-out/`** -- Auto-generated semantic graph (`graphify update .`). Read `GRAPH_REPORT.md` first for god-nodes / bridge nodes. Open `graph.html` for interactive exploration. 1,211 nodes / 192 communities as of 2026-04-23.

## Key File Locations

**Entry Points:**
- Backend: `backend/app/main.py`.
- Frontend: `frontend/src/main.tsx`, `frontend/src/App.tsx`.

**Configuration:**
- `backend/app/config.py` -- Pydantic Settings reading env vars (`OPENROUTER_API_KEY`, `SUPABASE_URL`, `RAG_*` knobs, etc.).
- `backend/.env`, `frontend/.env` (gitignored).
- `frontend/vite.config.ts`, `frontend/tailwind.config.js`, `frontend/tsconfig.json`.
- `.mcp.json` -- MCP server registry.

**Auth / Security:**
- `backend/app/dependencies.py` -- `get_current_user`, `require_admin`, `require_dpo`.
- `backend/app/database.py` -- `get_supabase_client` (service-role), `get_supabase_authed_client` (RLS).
- `frontend/src/components/auth/AuthGuard.tsx`, `AdminGuard.tsx`.
- `frontend/src/contexts/AuthContext.tsx`.

**Core Logic:**
- Chat SSE: `backend/app/routers/chat.py`.
- RAG retrieval: `backend/app/services/hybrid_retrieval_service.py`.
- Tool dispatch: `backend/app/services/tool_service.py`.
- Multi-agent: `backend/app/services/agent_service.py`.
- Ingestion: `backend/app/services/ingestion_service.py`.
- Document tools: `backend/app/services/document_tool_service.py`.

**Frontend chat state:**
- `frontend/src/hooks/useChatState.ts`.
- `frontend/src/lib/messageTree.ts`.

**Design system:**
- Tokens: `frontend/src/index.css` `:root`.
- Spec: `docs/superpowers/specs/2026-04-14-design-2026-refresh.md`.

**Testing:**
- Backend API: `backend/tests/api/`.
- RAG eval: `python -m scripts.eval_rag --base-url <url> --token <jwt>`.

## Naming Conventions

**Backend files:**
- Routers: `<domain>.py` (e.g., `chat.py`, `clause_library.py`).
- Services: `<domain>_service.py` (e.g., `hybrid_retrieval_service.py`). Exception: `agent_service` is a module-level service.
- Models: `<domain>.py` inside `app/models/`.

**Backend identifiers:**
- Functions / variables: `snake_case`.
- Classes: `PascalCase` (`HybridRetrievalService`, `ToolService`).
- Pydantic models: `PascalCase` (`ToolCallRecord`, `RerankResponse`).
- Constants: `UPPER_SNAKE_CASE` (`_WRITE_KEYWORDS`, `MAX_FILE_SIZE`, `TOOL_DEFINITIONS`).
- Private helpers: prefix `_` (`_run_tool_loop`, `_cache_key`).

**Frontend files:**
- Pages: `<Domain>Page.tsx`.
- Components: `PascalCase.tsx` (`MessageView.tsx`, `FolderTree.tsx`).
- Hooks: `use<Name>.ts`.
- Lib files: `camelCase.ts`.

**Frontend identifiers:**
- Components: `PascalCase`. Functions / variables: `camelCase`. Types/interfaces: `PascalCase`.

**Routes:**
- Backend: `/<resource>` with `prefix="/<name>"` and `tags=["<name>"]` per router.
- Frontend: kebab-case (`/clause-library`, `/admin/settings`).

**Database:**
- Tables: `snake_case` plural (`documents`, `messages`, `user_profiles`, `audit_log`).
- Columns: `snake_case`. FKs: `<entity>_id`.
- Migration files: `NNN_<snake_case>.sql`.

## Where to Add New Code

**New backend domain:**
1. Create `backend/app/routers/<domain>.py` with `APIRouter(prefix="/<domain>", tags=["<domain>"])`.
2. Register in `backend/app/main.py` (import + `app.include_router(<domain>.router)`).
3. Non-trivial logic -> `backend/app/services/<domain>_service.py`.
4. LLM I/O Pydantic models -> `backend/app/models/<domain>.py`.
5. DB schema -> next sequential migration via `/create-migration` (NEVER edit applied 001-027). Always include RLS policies.
6. Audit: call `log_action(...)` in mutating endpoints.
7. Tests: `backend/tests/api/test_<domain>.py`.

**New API endpoint in an existing router:**
- Edit the existing `backend/app/routers/<domain>.py`. Reuse the `router` instance.
- Add `Depends(get_current_user)` (or `require_admin` / `require_dpo`).
- User-scoped reads: prefer `get_supabase_authed_client(user["token"])` (RLS).
- Admin/system writes: use `get_supabase_client()` and explicit filters.

**New frontend page:**
1. Create `frontend/src/pages/<Domain>Page.tsx`.
2. Register in `frontend/src/App.tsx` inside the `<AppLayout />` `<Route>` block. Wrap with `<AdminGuard>` if admin-only.
3. Sidebar / icon-rail entry under `frontend/src/components/layout/`.
4. i18n strings -> `frontend/src/i18n/`.

**New chat tool:**
1. Append to `TOOL_DEFINITIONS` in `backend/app/services/tool_service.py` with the OpenAI tool schema.
2. Add the dispatch branch in `ToolService.execute_tool(name, args, user_id, ctx)`.
3. UI badge: extend `frontend/src/components/chat/` and `SSEEvent` types in `frontend/src/lib/database.types.ts`.

**New agent:**
1. Add an entry to the agent registry in `backend/app/services/agent_service.py` (`system_prompt`, `display_name`, `allowed_tools`, `max_iterations`).
2. Update intent classification prompt / few-shot examples in the same file.

**New chat UI behavior:**
- Place under `frontend/src/components/chat/`. Wire via `useChatState` and `ChatContext`.
- New SSE event: extend `SSEEvent` union in `frontend/src/lib/database.types.ts` and add a branch in `useChatState.ts`'s SSE handler.

**Utilities:**
- Backend: prefer adding to the most relevant `*_service.py`. There is no `app/utils/`.
- Frontend: `frontend/src/lib/utils.ts` (or new `lib/<name>.ts`).

**Database migration:**
- Always use `/create-migration` for the next-numbered file with the RLS template.
- Never renumber. Two `024_*.sql` files coexist by design.

## Special Directories

**`graphify-out/`** -- Auto-generated semantic graph. Read `GRAPH_REPORT.md` first when answering architecture questions. Run `graphify update .` after code changes (AST-only, no API cost).

**`backend/venv/`** -- Python virtualenv. Generated. Gitignored.

**`frontend/node_modules/`** -- npm packages. Generated. Gitignored.

**`.planning/`** -- GSD planning artifacts. Subdir `codebase/` holds these mapping docs. Subdirs `phases/`, `meta/` for plans. Committed for traceability.

**`References/`** -- External reference materials. Committed.

**`__pycache__/`** -- Python bytecode. Gitignored.

**`.claude/`, `.agents/`** -- Agent configs / skills / hooks. PostToolUse auto-lints; PreToolUse blocks `.env` and applied migration edits (001-027).

---

*Structure analysis: 2026-04-25*
