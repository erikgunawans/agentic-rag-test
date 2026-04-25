# Technology Stack

**Analysis Date:** 2026-04-25

## Languages

**Primary:**
- TypeScript ~5.9.3 — frontend (`frontend/src/**/*.ts`, `frontend/src/**/*.tsx`)
- Python 3.12 (Docker base) / 3.14 (local dev — emits Pydantic v1 deprecation warning from langsmith) — backend (`backend/app/**/*.py`)

**Secondary:**
- SQL — Supabase Postgres migrations (`backend/migrations/*.sql`, `supabase/`)
- Bash — deployment scripts (`backend/run.sh`)

## Runtime

**Frontend:**
- Node.js — required for Vite 8.x (Node ≥ 20 expected by Vite 8). No `.nvmrc` detected.
- Module type: ESM (`"type": "module"` in `frontend/package.json`)
- Browser target: ES2020 (`frontend/eslint.config.js` → `ecmaVersion: 2020`)

**Backend:**
- Python 3.12-slim in Docker (`backend/Dockerfile` line 1)
- Python venv local dev (`backend/venv/`, activated via `backend/run.sh`)
- ASGI server: `uvicorn[standard]==0.30.6` on port 8000 (Railway override via `$PORT`)

**Package Manager:**
- Frontend: npm (lockfile present at `frontend/package-lock.json`)
- Backend: pip with pinned `backend/requirements.txt`
- Lockfiles: present (frontend), no pip lockfile (versions partially pinned with `==` and `>=`)

## Frameworks

**Frontend Core:**
- React 19.2.4 (`react`, `react-dom`) — `frontend/package.json:20-21`
- React Router DOM 7.13.2 — client-side routing
- Vite 8.0.1 — dev server + production bundler (`frontend/vite.config.ts`)
- Tailwind CSS 4.2.2 + `@tailwindcss/vite` 4.2.2 — utility CSS via Vite plugin
- shadcn 4.1.2 + base-ui/react ^1.3.0 — component primitives (tooltips render-prop API)
- class-variance-authority 0.7.1, clsx 2.1.1, tailwind-merge 3.5.0 — variant/class utilities
- lucide-react 1.7.0 — icon set
- react-markdown 10.1.0 — chat message rendering
- tw-animate-css 1.4.0 — animation utilities
- @fontsource-variable/geist 5.2.8 — Geist variable font

**Backend Core:**
- FastAPI 0.115.0 — async HTTP framework with OpenAPI (`backend/app/main.py:23`)
- Pydantic v2 (via `pydantic-settings==2.5.2`) — settings + request/response models
- Supabase Python SDK 2.7.4 — Postgres / Auth / Storage / Realtime client (`backend/app/database.py`)
- OpenAI Python SDK ≥ 2.30.0 — used for embeddings (`text-embedding-3-small`) and as the OpenAI-compatible client pointed at OpenRouter
- LangSmith 0.1.117 — tracing decorators (`@traceable`) on LLM/retrieval calls
- httpx 0.27.2 — async HTTP client (Cohere rerank, Tavily search, Dokmee, Google)
- python-multipart 0.0.12 — multipart form parsing for file uploads

**Document Processing:**
- pymupdf ≥ 1.25.0 — PDF text extraction
- python-docx ≥ 1.1.0 — DOCX export
- beautifulsoup4 ≥ 4.12.0 — HTML parsing (regulatory ingestion)
- tiktoken ≥ 0.8.0 — tokenizer for chunk-size accounting

**Testing:**
- Backend: pytest (run via `cd backend && pytest tests/api/ -v --tb=short` per `CLAUDE.md`)
- Frontend: no unit test framework wired into `package.json` scripts (only `lint` and `build`)

**Build/Dev:**
- Frontend build: `tsc -b && vite build` (`frontend/package.json:8`)
- Linting: ESLint 9.39.4 + typescript-eslint 8.57.0 + eslint-plugin-react-hooks 7.0.1 + eslint-plugin-react-refresh 0.5.2 (`frontend/eslint.config.js`)
- Type checking: TypeScript ~5.9.3 with project references (`frontend/tsconfig.json`, `tsconfig.app.json`, `tsconfig.node.json`)
- Vite plugins: `@vitejs/plugin-react` 6.0.1, `@tailwindcss/vite` 4.2.2

## Key Dependencies

**Critical (Backend):**
- `supabase==2.7.4` — primary data layer; both service-role and JWT-scoped clients in `backend/app/database.py`
- `openai>=2.30.0` — used twice: native OpenAI for embeddings (`backend/app/services/embedding_service.py`) and as OpenAI-compatible client against OpenRouter base URL `https://openrouter.ai/api/v1` (`backend/app/services/openrouter_service.py`)
- `fastapi==0.115.0` + `uvicorn[standard]==0.30.6` — HTTP/SSE serving
- `langsmith==0.1.117` — tracing on chat, retrieval, rerank, tool calls
- `httpx==0.27.2` — outbound HTTP for non-OpenAI third parties (Cohere, Tavily, Dokmee, Google)
- `pydantic-settings==2.5.2` — env-driven config in `backend/app/config.py`

**Critical (Frontend):**
- `@supabase/supabase-js` ^2.101.1 — auth + realtime + storage from browser (`frontend/src/lib/supabase.ts`)
- `react` ^19.2.4 / `react-dom` ^19.2.4 — UI runtime
- `react-router-dom` ^7.13.2 — routing
- `tailwindcss` ^4.2.2 + `@tailwindcss/vite` ^4.2.2 — styling pipeline
- `@base-ui/react` ^1.3.0 — accessible primitives (tooltips use `render` prop)

**Infrastructure:**
- `python-dotenv==1.0.1` — local `.env` loading for backend
- Path alias `@/*` → `./src/*` (`frontend/tsconfig.json` + `frontend/vite.config.ts`)

## Configuration

**Environment files:**
- `.env.example` — root template; both backend and Vite frontend variables documented
- `.env` — local dev (gitignored, contents NOT inspected)
- `frontend/.env*` — Vite-prefixed vars (`VITE_*`) at build time
- `backend/.env` — loaded by `pydantic-settings` via `model_config = SettingsConfigDict(env_file=".env", extra="ignore")` in `backend/app/config.py:6`

**Backend config (declared in `backend/app/config.py`):**
- Supabase: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`
- OpenAI: `OPENAI_API_KEY`, `OPENAI_EMBEDDING_MODEL` (default `text-embedding-3-small`), `OPENAI_VECTOR_STORE_ID` (legacy)
- OpenRouter: `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` (default `openai/gpt-4o-mini`)
- RAG tuning: `RAG_TOP_K=5`, `RAG_SIMILARITY_THRESHOLD=0.3`, `RAG_CHUNK_SIZE=500`, `RAG_CHUNK_OVERLAP=50`
- Hybrid search: `RAG_HYBRID_ENABLED=True`, `RAG_RRF_K=60`, `RAG_RERANK_ENABLED=False`, `RAG_RERANK_MODEL`
- RAG improvements: `RAG_CONTEXT_ENABLED=True`, `RAG_NEIGHBOR_WINDOW=1`, `RAG_QUERY_EXPANSION_ENABLED=False`
- Fusion weights: `RAG_VECTOR_WEIGHT=1.0`, `RAG_FULLTEXT_WEIGHT=1.0`
- GraphRAG: `GRAPH_ENABLED=False`, `GRAPH_ENTITY_EXTRACTION_MODEL`
- Cohere rerank: `COHERE_API_KEY`
- Custom embeddings: `CUSTOM_EMBEDDING_MODEL`
- Tools: `TAVILY_API_KEY`, `TOOLS_ENABLED=True`, `TOOLS_MAX_ITERATIONS=5`
- Sub-agents: `AGENTS_ENABLED=False`, `AGENTS_ORCHESTRATOR_MODEL`
- Deployment / CORS: `FRONTEND_URL` (comma-separated origins, default `http://localhost:5173`)
- Storage: `STORAGE_BUCKET=documents` (Supabase bucket name)
- LangSmith: `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT=rag-masterclass`, `LANGCHAIN_TRACING_V2=false`

**Frontend config (Vite-prefixed, `import.meta.env.*`):**
- `VITE_SUPABASE_URL` — used in `frontend/src/lib/supabase.ts:3`
- `VITE_SUPABASE_ANON_KEY` — used in `frontend/src/lib/supabase.ts:4`
- `VITE_API_BASE_URL` — used in `frontend/src/lib/api.ts:3` (e.g. `http://localhost:8000` or Railway URL)

**Build / framework configs:**
- `frontend/vite.config.ts` — React + Tailwind plugins, `@/*` alias
- `frontend/tsconfig.json` (+ `tsconfig.app.json`, `tsconfig.node.json`) — project references, ES2020 target
- `frontend/eslint.config.js` — flat ESLint v9 config with typescript-eslint
- `frontend/components.json` — shadcn registry config
- `frontend/vercel.json` — SPA rewrite (`/(.*)` → `/index.html`)
- `backend/Dockerfile` — Railway image (`python:3.12-slim`, non-root `app` user, `$PORT`)
- `backend/run.sh` — local dev launcher (`uvicorn ... --reload --port 8000`)
- `.mcp.json` — MCP server registry (context7, Supabase, Playwright)

## Platform Requirements

**Development:**
- Node.js + npm for frontend (`cd frontend && npm install && npm run dev` → `http://localhost:5173`)
- Python 3.12+ with venv for backend (`cd backend && python -m venv venv && pip install -r requirements.txt && uvicorn app.main:app --reload --port 8000`)
- Supabase project (Postgres + pgvector + Auth + Storage + Realtime) at `qedhulpfezucnfadlfiz.supabase.co`
- API keys: OpenAI (embeddings), OpenRouter (chat). Optional: Cohere, Tavily, LangSmith

**Production:**
- Backend: Railway container deploy from `backend/Dockerfile` (`https://api-production-cde1.up.railway.app`)
- Frontend: Vercel SPA from `main` branch (`https://frontend-one-rho-88.vercel.app`); SPA fallback in `frontend/vercel.json`
- Database: Supabase managed (project `qedhulpfezucnfadlfiz`)
- CORS: backend `FRONTEND_URL` must include the Vercel domain

---

*Stack analysis: 2026-04-25*
