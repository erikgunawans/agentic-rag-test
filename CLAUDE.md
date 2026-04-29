# CLAUDE.md

PJAA CLM (Contract Lifecycle Management) platform. Indonesian legal AI with chat, document tools, clause library, approval workflows, regulatory intelligence, and executive dashboard. RBAC with admin UI.

## Stack
- Frontend: React + Vite + Tailwind + shadcn/ui + base-ui (tooltips)
- Backend: Python + FastAPI (async, `venv`)
- Database: Supabase (Postgres, pgvector, Auth, Storage, Realtime)
- LLM: OpenRouter (chat + document tools), OpenAI (embeddings only)
- Observability: LangSmith

## Quick Start

```bash
# Backend
cd backend && python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend && npm install && npm run dev
```

## Architecture

### Backend (22 routers in `backend/app/routers/`)
- **Core**: `chat.py` (SSE streaming + tool-calling loop), `threads.py`, `documents.py`
- **Document tools**: `document_tools.py` (create/compare/compliance/analyze with LLM)
- **Phase 1**: `clause_library.py`, `document_templates.py`, `approvals.py`, `obligations.py`, `audit_trail.py`, `user_management.py`
- **Phase 2**: `regulatory.py`, `notifications.py`, `dashboard.py`, `integrations.py` (Dokmee), `google_export.py`
- **BJR**: `bjr.py` (25 endpoints — decisions, evidence, phase progression, risks, admin CRUD)
- **Phase 3**: `compliance_snapshots.py` (point-in-time compliance), `pdp.py` (UU PDP toolkit)
- **Settings**: `admin_settings.py` (system-wide), `user_preferences.py` (per-user)

### Frontend (24 pages in `frontend/src/pages/`)
- Layout: `AppLayout` with `IconRail` (60px) + collapsible sidebar (340px) + content
- State: `useChatState` hook + `ChatContext`, `useSidebar` for panel collapse
- i18n: Indonesian (default) + English via `I18nProvider`

## Design System (2026 Calibrated Restraint)
- Tokens in `frontend/src/index.css` `:root`. Zinc-neutral base, purple accent. Full spec: `docs/superpowers/specs/2026-04-14-design-2026-refresh.md`
- Glass (`backdrop-blur`): transient overlays ONLY (tooltips, popovers). NEVER on persistent panels (sidebars, input cards).
- Buttons: solid flat, no gradients. Gradients only on user chat bubbles (`MessageView.tsx`).

## Key Patterns
- **Auth**: `get_current_user` dependency returns `{id, email, token, role}`, checks `user_profiles.is_active`
- **Admin**: `require_admin` dependency, checks `role == "super_admin"`
- **DB clients**: `get_supabase_authed_client(token)` for RLS-scoped, `get_supabase_client()` for service-role
- **system_settings**: Single-row table (`id=1`), cached via `get_system_settings()` with 60s TTL. Never query as key-value.
- **Audit**: `log_action(user_id, user_email, action, resource_type, resource_id)` on all mutations
- **Form duplication**: DocumentCreationPage has BOTH mobile and desktop panels. Add new form sections to both.

## Rules
- No LangChain, no LangGraph. Raw SDK calls only.
- Use Pydantic for structured LLM outputs (`json_object` response format)
- All tables need Row-Level Security. Users only see their own data.
- Global/shared data uses `is_global = true` pattern (clauses, templates)
- Stream chat responses via SSE
- Ingestion is manual file upload only. Scanned PDFs auto-detect and fall back to GPT-4o vision OCR.

## Admin / RBAC
- test@test.com is `super_admin` (set via `raw_app_meta_data.role`)
- Promote users: `python -m scripts.set_admin_role <email>`
- Admin pages: `/admin/settings`, `/admin/users`, `/admin/audit`, `/admin/reviews`
- RLS admin pattern: `(auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin'`

## Deployment

**Quick deploy**: `/deploy-lexcore` (runs the full pipeline below)

```bash
git push origin master && git push origin master:main  # Vercel deploys from main
cd backend && railway up                                # Backend
cd frontend && npx vercel --prod --yes                  # Frontend (or auto-deploy from main)
curl -s https://api-production-cde1.up.railway.app/health  # Verify
```

- **Frontend**: https://frontend-one-rho-88.vercel.app
- **Backend**: https://api-production-cde1.up.railway.app
- **Supabase project**: `qedhulpfezucnfadlfiz`

## Planning
- Plans saved to `~/.claude/plans/` (session-scoped) or `.agent/plans/` (legacy)
- Complexity indicators: simple, medium, complex

## Plan Verification Protocol

Every plan MUST self-verify before presenting. Check: completeness, correct file paths/schemas, dependency ordering, blast radius, concrete verification steps, reuse of existing utilities. Rate confidence 0-100%. If < 95%, investigate and re-verify until >= 95%. Report confidence + pass count at the bottom of every plan.

## Testing

**Quick run**: `/run-api-tests` (runs pytest + RAG eval with credentials pre-filled)

Test accounts:
- Admin: `test@test.com` / `!*-3-3?3uZ?b$v&`
- User 2: `test-2@test.com` / `fK4$Wd?HGKmb#A2`

Local URLs: frontend `http://localhost:5173`, backend `http://localhost:8000`

## Code Quality

```bash
# Frontend lint
cd frontend && npm run lint

# Frontend type check
cd frontend && npx tsc --noEmit

# Backend API tests (8 test files)
cd backend && source venv/bin/activate && \
  TEST_EMAIL="test@test.com" TEST_PASSWORD='!*-3-3?3uZ?b$v&' \
  TEST_EMAIL_2="test-2@test.com" TEST_PASSWORD_2='fK4$Wd?HGKmb#A2' \
  API_BASE_URL="https://api-production-cde1.up.railway.app" \
  pytest tests/api/ -v --tb=short

# Backend import check
cd backend && source venv/bin/activate && python -c "from app.main import app; print('OK')"
```

## LLM Pipeline
- **Multi-agent**: `agents_enabled` in config. Research Agent auto-selected for document queries via `agent_service.classify_intent()`
- **Tool dispatch**: `ToolService.execute_tool()` dispatches `search_documents` (with filter_tags/folder_id/date_from/date_to), `query_database`, `web_search`
- **RAG**: `HybridRetrievalService.retrieve()` — vector (pgvector) + fulltext (tsvector) + weighted RRF fusion (admin-configurable weights). Rerank modes: none/llm/cohere. Metadata pre-filtering via RPC params.
- **RAG extras**: Structure-aware chunking, bilingual query expansion (ID/EN), semantic cache (5min TTL), neighbor chunk expansion, GraphRAG entity context, OCR metadata tracking, custom embedding model support
- **Document tools**: `_llm_json()` helper in `document_tool_service.py` — OpenRouter with `json_object` response format, Pydantic validation
- **Confidence gating**: Results with `confidence_score >= 0.85` are `auto_approved`, below → `pending_review`
- **SSE events**: `agent_start` → `tool_start` → `tool_result` → `delta` (progressive) → `done:true`
- **Graph reindex**: `POST /documents/{id}/reindex-graph` — re-extracts graph entities for existing documents without re-embedding
- **RAG eval**: `python -m scripts.eval_rag --base-url <url> --token <jwt>` — 20-query golden set with keyword hit rate + MRR metrics
- **PII Redaction (v0.3.0.0)**: Conversation-scoped detection + anonymization + de-anonymization. Toggle via `pii_redaction_enabled` system setting. When ON: incoming messages anonymized via Presidio + Faker (xx_ent_wiki_sm spaCy model), surrogates persisted in `entity_registry` table per-thread (migration 029), LLM only sees surrogates, response de-anonymized before user sees it. Cloud egress filter (`backend/app/services/redaction/egress.py`) blocks any cloud-LLM call where registry-known PII would leak. Per-feature provider override (entity resolution, missed-scan, fuzzy de-anon, title-gen, metadata) via admin UI, settings cached 60s. Off-mode is byte-identical to pre-v0.3 behavior (SC#5 invariant). Privacy invariant: real PII never reaches cloud-LLM payloads.

## Automations
- **Hooks**: PostToolUse auto-lints .ts/.tsx (ESLint + tsc) and .py (py_compile + full import check). PreToolUse blocks .env edits and applied migration edits (001-032).
- **Skills**: `/deploy-lexcore` (full deploy pipeline), `/run-api-tests` (pytest + RAG eval golden set), `/create-migration` (numbered Supabase migration with RLS template)
- **Agents**: `security-reviewer` (RLS bypass, missing auth, SQL injection, audit gaps), `rag-quality-reviewer` (retrieval pipeline correctness, RPC safety, cache keys)
- **MCP**: context7 (live docs), Supabase (direct DB), Playwright (browser automation) — configured in `.mcp.json`

## Gotchas

- Vercel deploys from `main` branch, NOT `master`. Always run `git push origin master:main` after pushing to master, or deploy directly with `cd frontend && npx vercel --prod`.
- **Railway backend deploy is manual.** `git push` does NOT auto-deploy the backend — there is no GitHub integration trigger. After backend changes: `cd backend && railway up` (or use `/deploy-lexcore`). The Procfile's `release: python -m spacy download xx_ent_wiki_sm` is **ignored** because Railway uses the Dockerfile path (Procfile release hooks are a Heroku-buildpack feature).
- **Presidio spaCy model must be downloaded at Docker BUILD time, not runtime.** `backend/Dockerfile` has `RUN python -m spacy download xx_ent_wiki_sm` before the `USER app` switch. Without it, Presidio's lifespan-hook init calls `spacy.cli.download` at runtime as non-root `app`, which fails with `EACCES` on `/nonexistent/.cache/pip` and the container crash-loops. Do NOT remove that RUN line.
- `system_settings` is a single-row table with columns, NOT a key-value store. Use `get_system_settings()` from `system_settings_service.py`.
- base-ui tooltips use `render` prop, not `asChild`. The shim in `tooltip.tsx` translates `asChild` to `render`.
- Glass (`backdrop-blur`) must NEVER be added to persistent panels (sidebars, input cards). Only transient overlays (tooltips, popovers, mobile overlays).
- Python 3.14 shows Pydantic v1 warning from langsmith. Non-blocking.
- Supabase array containment filter: `.filter("col", "cs", "{value}")` not `.contains()`
- Search params in PostgREST filters must sanitize commas and parentheses.
- `get_current_user` makes a `user_profiles` DB call on every request (checks `is_active`, auto-creates for new signups).
- Migrations are numbered sequentially (`001_` through `032_`). Use `/create-migration` to generate the next one. Never edit applied migrations (hook blocks 001-032).
- Two `024_*.sql` files exist (knowledge_base_explorer + rag_improvements). Both are applied. Don't renumber.
- **`EMBEDDING_PROVIDER` switch does NOT trigger re-embedding (Phase 6 / EMBED-02).** Setting `EMBEDDING_PROVIDER=local` and `LOCAL_EMBEDDING_BASE_URL=http://localhost:11434/v1` redirects FUTURE ingestions to the local endpoint (e.g., Ollama bge-m3 / nomic-embed-text). Existing document vectors stay in their original embedding space until manually re-ingested. RAG retrieval quality may degrade for queries that span both old and new chunks. Deployer-managed migration: re-ingest documents (drop + re-upload) when consolidating to a single provider.

## Workflow
- When working in git worktrees, immediately confirm the current working directory and branch before starting. Do not explore the codebase if the goal is implementation — start writing code.
- When debugging frontend issues, verify the backend API is running and returning expected responses BEFORE investigating frontend code.
- Always confirm you're in the correct directory (`backend/` vs `frontend/` vs repo root) before running commands.

## Pre-Push Checks
- Every bug fix gets a regression test. Write the test first.
- Before pushing: `cd frontend && npx tsc --noEmit && npm run lint` and `cd backend && python -c "from app.main import app; print('OK')"` (PostToolUse hook runs these automatically on file edits)

## Session Continuity
- Run `/sync` after every major milestone to persist state to PROGRESS.md and memory files.
- Every checkpoint must include: what was done, branch, files changed, what's next.
- If approaching context limits (conversation getting long, compaction happening), IMMEDIATELY run `/sync` before doing anything else.
- New sessions: read PROGRESS.md first, then check memory files, then start work.

## Progress

Check PROGRESS.md for current status. Phase 1 (7/7), Phase 2 (5/5), Phase 3 (2/2) complete. BJR module shipped. LLM e2e test passed. RAG pipeline complete (8/8 hooks shipped): structure-aware chunking, vision OCR, custom embeddings, metadata pre-filtering, bilingual query expansion, weighted fusion, cross-encoder reranking (Cohere), graph reindex endpoint. **PII Redaction System v1.0 SHIPPED (v0.3.0.0, 2026-04-28)** — Phases 1-5 complete (detection, anonymization, conversation-scoped registry, entity resolution, fuzzy de-anon, chat-loop integration); Phase 6 (cross-process async-lock upgrade per D-31) remains. 32 migrations, 22 routers, 19 services.

## graphify

This project has a graphify knowledge graph at graphify-out/.

Rules:
- Before answering architecture or codebase questions, read graphify-out/GRAPH_REPORT.md for god nodes and community structure
- If graphify-out/wiki/index.md exists, navigate it instead of reading raw files
- After modifying code files in this session, run `graphify update .` to keep the graph current (AST-only, no API cost)
