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
- Palette: Zinc-neutral (`#09090B` base), purple accent (`oklch(0.55 0.20 280)`)
- Tokens: All in `frontend/src/index.css` `:root` block
- Glass (backdrop-blur): Transient overlays ONLY (tooltips, popovers, mobile panels). Never on persistent panels (sidebars, input cards).
- Sidebars: Solid `bg-sidebar` (`#111113`), no blur
- Buttons: Solid flat `bg-primary`, no gradients. Gradients only on user chat bubbles in `MessageView.tsx`.
- Typography: h1 `-0.02em`/600, h2 `-0.01em`/600, h3 500 (set in `@layer base`)
- Background: `mesh-bg` (purple radial glows) + `dot-grid` (3% opacity `::before` pseudo-element overlay on `<main>`)
- Spec: `docs/superpowers/specs/2026-04-14-design-2026-refresh.md`

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
- Ingestion is manual file upload only

## Admin / RBAC
- test@test.com is `super_admin` (set via `raw_app_meta_data.role`)
- Promote users: `python -m scripts.set_admin_role <email>`
- Admin pages: `/admin/settings`, `/admin/users`, `/admin/audit`, `/admin/reviews`
- RLS admin pattern: `(auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin'`

## Deployment

```bash
# Frontend (Vercel deploys from `main` branch)
git push origin master:main   # sync master → main first
cd frontend && npx vercel --prod  # or wait for auto-deploy from main

# Backend (Railway)
cd backend && railway up
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

User 1 (admin):
- **Email**: `test@test.com`
- **Password**: `!*-3-3?3uZ?b$v&`

User 2:
- **Email**: `test-2@test.com`
- **Password**: `fK4$Wd?HGKmb#A2`

- **Frontend**: `http://localhost:5173`
- **Backend**: `http://localhost:8000`

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

## Automations
- **Hooks**: PostToolUse auto-lints .ts/.tsx (ESLint + tsc) and .py (py_compile + full import check). PreToolUse blocks .env edits and applied migration edits (001-027).
- **Skills**: `/deploy-lexcore` (full deploy pipeline), `/run-api-tests` (pytest + RAG eval golden set), `/create-migration` (numbered Supabase migration with RLS template)
- **Agents**: `security-reviewer` (RLS bypass, missing auth, SQL injection, audit gaps), `rag-quality-reviewer` (retrieval pipeline correctness, RPC safety, cache keys)
- **MCP**: context7 (live docs), Supabase (direct DB), Playwright (browser automation) — configured in `.mcp.json`

## Gotchas

- Vercel deploys from `main` branch, NOT `master`. Always run `git push origin master:main` after pushing to master, or deploy directly with `cd frontend && npx vercel --prod`.
- `system_settings` is a single-row table with columns, NOT a key-value store. Use `get_system_settings()` from `system_settings_service.py`.
- base-ui tooltips use `render` prop, not `asChild`. The shim in `tooltip.tsx` translates `asChild` to `render`.
- Glass (`backdrop-blur`) must NEVER be added to persistent panels (sidebars, input cards). Only transient overlays (tooltips, popovers, mobile overlays).
- Python 3.14 shows Pydantic v1 warning from langsmith. Non-blocking.
- Supabase array containment filter: `.filter("col", "cs", "{value}")` not `.contains()`
- Search params in PostgREST filters must sanitize commas and parentheses.
- `get_current_user` makes a `user_profiles` DB call on every request (checks `is_active`, auto-creates for new signups).
- Headless browser (gstack browse): Special chars in passwords require native input setter (`Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set`), not `fill` command. React state won't update with standard input methods.
- Browse server restarts between `$B` calls — use `$B chain < file.json` to maintain session state across multiple commands (login + navigation + actions).

## Workflow
- When working in git worktrees, immediately confirm the current working directory and branch before starting. Do not explore the codebase if the goal is implementation — start writing code.
- When debugging frontend issues, verify the backend API is running and returning expected responses BEFORE investigating frontend code.
- Always confirm you're in the correct directory (`backend/` vs `frontend/` vs repo root) before running commands.

## Testing & CI
- Write tests before implementation when fixing bugs. Every bug fix gets a regression test.
- Before pushing, run: `cd frontend && npx tsc --noEmit && npm run lint` and `cd backend && python -c "from app.main import app; print('OK')"`
- After pushing, monitor CI and fix failures before moving on. Don't leave broken CI.
- Check for: missing eslintrc configs, missing pip dependencies, import mode compatibility.

## Deployment Checklist
Before deploying:
1. `git push origin master && git push origin master:main` (Vercel deploys from main)
2. Backend: `cd backend && railway up`
3. Frontend: `cd frontend && npx vercel --prod --yes`
4. Verify: `curl -s https://api-production-cde1.up.railway.app/health`
5. Smoke test critical endpoints

## Session Continuity
- Run `/sync` after every major milestone to persist state to PROGRESS.md and memory files.
- Every checkpoint must include: what was done, branch, files changed, what's next.
- If approaching context limits (conversation getting long, compaction happening), IMMEDIATELY run `/sync` before doing anything else.
- New sessions: read PROGRESS.md first, then check memory files, then start work.

## Progress

Check PROGRESS.md for current status. Phase 1 (7/7), Phase 2 (5/5), Phase 3 (2/2) complete. BJR module shipped. LLM e2e test passed. RAG pipeline complete (8/8 hooks shipped): structure-aware chunking, vision OCR, custom embeddings, metadata pre-filtering, bilingual query expansion, weighted fusion, cross-encoder reranking (Cohere), graph reindex endpoint. 27 migrations, 22 routers, 18 services.
