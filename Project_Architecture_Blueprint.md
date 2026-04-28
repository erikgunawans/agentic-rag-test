# LexCore — Project Architecture Blueprint

> **Generated:** 2026-04-28  
> **Version:** v0.3.0.1 (post Phase 5 gap-closures)  
> **Graph:** 2,035 nodes · 3,739 edges · 209 communities (graphify build)

---

## Table of Contents

1. [Architectural Overview](#1-architectural-overview)
2. [System Visualization (C4)](#2-system-visualization-c4)
3. [Core Architectural Components](#3-core-architectural-components)
4. [Architectural Layers and Dependencies](#4-architectural-layers-and-dependencies)
5. [Data Architecture](#5-data-architecture)
6. [Cross-Cutting Concerns](#6-cross-cutting-concerns)
7. [Service Communication Patterns](#7-service-communication-patterns)
8. [Technology-Specific Patterns](#8-technology-specific-patterns)
9. [Implementation Patterns](#9-implementation-patterns)
10. [Testing Architecture](#10-testing-architecture)
11. [Deployment Architecture](#11-deployment-architecture)
12. [Extension and Evolution Patterns](#12-extension-and-evolution-patterns)
13. [Architectural Decision Records](#13-architectural-decision-records)
14. [Architecture Governance](#14-architecture-governance)
15. [Blueprint for New Development](#15-blueprint-for-new-development)

---

## 1. Architectural Overview

LexCore is an **Indonesian legal AI platform** — a Contract Lifecycle Management (CLM) system with AI-powered document tools, clause library, approval workflows, regulatory intelligence, and PII-safe chat. It is built as a **layered, API-first monolith with SSE streaming**, deployed as two discrete services (frontend SPA + backend API) backed by a single Supabase Postgres database.

### Guiding Principles

| Principle | Evidence |
|-----------|---------|
| **Raw SDK over framework** | No LangChain/LangGraph; direct OpenRouter/OpenAI SDK calls throughout |
| **Single-table settings, not key-value** | `system_settings` is a single row; admin toggles are columns, not records |
| **RLS-first data access** | Every table has Row-Level Security; service-role client used only where intentional |
| **Privacy by architecture** | PII never reaches cloud-LLM payloads; surrogate substitution at chat-loop boundary |
| **Audit all mutations** | `log_action()` called on every write; fire-and-forget, never raises |
| **Streaming by default** | Chat responses streamed via SSE; no polling patterns |

### Architectural Style

The system uses a **Layered + Event-Driven hybrid**:
- **Backend:** Three-layer (Router → Service → Database), strictly top-down
- **Frontend:** Provider-scoped context + unidirectional state hooks + SSE event stream
- **Communication:** REST for CRUD, SSE for chat streaming, Realtime subscriptions for document updates

---

## 2. System Visualization (C4)

### Level 1 — System Context

```
┌─────────────────────────────────────────────────────────────┐
│                        LexCore Platform                      │
│                                                             │
│  ┌──────────────┐    REST/SSE    ┌──────────────────────┐   │
│  │  Browser SPA │◄──────────────►│  FastAPI Backend     │   │
│  │  (React/Vite)│                │  (Railway)           │   │
│  └──────────────┘                └──────────┬───────────┘   │
│                                             │               │
│                              ┌──────────────▼──────────┐    │
│                              │  Supabase               │    │
│                              │  Postgres + pgvector    │    │
│                              │  Auth + Storage +       │    │
│                              │  Realtime               │    │
│                              └─────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
          │                               │
          ▼                               ▼
   [Vercel CDN]                  [OpenRouter] [OpenAI]
                                 [Cohere] [LangSmith]
                                 [Tavily]
```

### Level 2 — Container Diagram

```
Frontend (Vercel)              Backend (Railway)            Data (Supabase)
┌──────────────────┐           ┌──────────────────────────┐ ┌─────────────────┐
│ React SPA        │  REST/SSE │ FastAPI (uvicorn)         │ │ Postgres        │
│                  │◄─────────►│                          │ │  - 32 migrations│
│ AuthProvider     │           │ 21 Routers               │ │  - pgvector     │
│ ThemeProvider    │           │   chat, documents,       │◄►│  - RLS on all   │
│ I18nProvider     │           │   threads, admin,        │ │    tables       │
│ ChatContext      │           │   bjr, pdp, ...          │ │                 │
│                  │           │                          │ │ Auth            │
│ 24 Pages         │           │ 25+ Services             │ │  - JWT tokens   │
│ AppLayout        │           │   hybrid_retrieval,      │ │  - app_metadata │
│ IconRail         │           │   redaction/*,           │ │    for roles    │
│ Sidebar          │           │   embedding, graph,      │ │                 │
│                  │           │   agent, tool, ...       │ │ Storage         │
│ SSE reader       │           │                          │ │  - Documents    │
│ Realtime sub     │           │ Dependencies             │ │                 │
│                  │           │   get_current_user       │ │ Realtime        │
└──────────────────┘           │   require_admin          │ │  - doc status   │
                               │   require_dpo            │ └─────────────────┘
                               └──────────────────────────┘
```

### Level 3 — Chat Feature Data Flow

```
Browser                Frontend                  Backend                 External
──────                 ────────                  ───────                 ────────
User types        →  useChatState.send()   →  POST /chat/stream    →  OpenRouter
                     SSE connection             event_generator()        (LLM)
                     (EventSource)              │
                                                ├─ anonymize_message()  → [PII pipeline]
                                                ├─ agent_service.classify_intent()
                                                ├─ ToolService.dispatch()
                                                │    └─ HybridRetrievalService.retrieve()
                                                │         ├─ EmbeddingService (vector)
                                                │         ├─ fulltext_search (tsvector)
                                                │         ├─ RRF fusion
                                                │         ├─ [rerank: cohere|llm|none]
                                                │         └─ GraphService.get_graph_context()
                                                ├─ deanonymize_response()
                                                └─ SSE: agent_start → tool_start
                                                         → tool_result → delta → done
                     ◄── SSE events ──────────────────────────────────
```

---

## 3. Core Architectural Components

### 3.1 Backend: Router Layer (`backend/app/routers/`)

21 router modules, each responsible for a single domain:

| Router | Domain | Key Endpoints |
|--------|--------|---------------|
| `chat.py` | AI chat streaming | `POST /chat/stream` (SSE) |
| `threads.py` | Conversation threads | CRUD + branch management |
| `documents.py` | Document CRUD + search | upload, search, reindex-graph |
| `document_tools.py` | AI document ops | create, compare, compliance, analyze |
| `admin_settings.py` | System config | `GET/PATCH /admin/settings` |
| `user_preferences.py` | Per-user config | `GET/PUT /user/preferences` |
| `audit_trail.py` | Compliance log | `GET /audit` |
| `clause_library.py` | Clause CRUD | global + user clauses |
| `document_templates.py` | Template CRUD | global + user templates |
| `approvals.py` | Approval workflows | create, review, escalate |
| `obligations.py` | Contract obligations | extract, track |
| `user_management.py` | Admin user ops | list, activate, deactivate |
| `regulatory.py` | Regulatory intelligence | fetch, sync, alert |
| `notifications.py` | Notifications | list, mark-read |
| `dashboard.py` | Executive KPIs | aggregated metrics |
| `integrations.py` | Dokmee DMS | connect, sync |
| `google_export.py` | Google Docs export | export, auth |
| `bjr.py` | BJR governance (25 endpoints) | decisions, evidence, risks |
| `compliance_snapshots.py` | Point-in-time compliance | snapshot, diff |
| `pdp.py` | UU PDP toolkit | inventory, incidents |
| `folders.py` | Document folders | CRUD + tree |

**Router pattern:**
```python
router = APIRouter(prefix="/domain", tags=["Domain"])

@router.post("/", ...)
async def create_item(
    body: CreateRequest,
    user: dict = Depends(get_current_user),
    supabase = Depends(get_supabase_authed_client),  # RLS-scoped
):
    result = await domain_service.create(body, user)
    await log_action(user["id"], user["email"], "create_item", "domain", result["id"])
    return result
```

### 3.2 Backend: Service Layer (`backend/app/services/`)

25+ service modules, each encapsulating a single technical concern:

| Service | Responsibility |
|---------|---------------|
| `hybrid_retrieval_service.py` | RAG pipeline: vector + FTS + RRF + rerank |
| `embedding_service.py` | OpenAI embeddings, chunk storage/retrieval |
| `graph_service.py` | GraphRAG entity extraction and context |
| `agent_service.py` | Intent classification, multi-agent orchestration |
| `tool_service.py` | Tool dispatch (search_documents, query_database, web_search, file ops) |
| `document_tool_service.py` | LLM-powered document ops with Pydantic validation |
| `ingestion_service.py` | Chunking, OCR, embedding ingestion pipeline |
| `system_settings_service.py` | Single-row system config with 60s TTL cache |
| `audit_service.py` | Fire-and-forget audit logging |
| `openrouter_service.py` | OpenRouter API client + provider abstraction |
| `openai_service.py` | OpenAI embeddings only |
| `llm_provider.py` | Provider routing (local/cloud/fallback) |
| `vision_service.py` | GPT-4o OCR for scanned PDFs |
| `tracing_service.py` | LangSmith/Langfuse instrumentation |
| `redaction/` | 12-module PII pipeline (see §3.3) |

### 3.3 PII Redaction Sub-Package (`backend/app/services/redaction/`)

A self-contained 12-module package implementing conversation-scoped PII anonymization:

```
redaction/
├── __init__.py          re-exports: RedactionError, ConversationRegistry, tool_redaction exports
├── errors.py            leaf module; no internal imports
├── registry.py          ConversationRegistry — per-thread entity surrogate map
├── detection.py         Presidio + spaCy (xx_ent_wiki_sm) detection
├── anonymization.py     surrogate substitution using Faker
├── clustering.py        entity clustering across turns
├── egress.py            cloud-LLM call guard (blocks if real PII would leak)
├── tool_redaction.py    anonymize_tool_output / deanonymize_tool_args (Phase 5)
├── fuzzy_match.py       fuzzy de-anonymization (Phase 4)
├── missed_scan.py       LLM-based missed PII detection (Phase 4)
├── name_extraction.py   Indonesian name heuristics
├── nicknames_id.py      Indonesian nickname dictionary
├── honorifics.py        Indonesian honorific handling
├── gender_id.py         Indonesian gender inference
├── prompt_guidance.py   system-prompt injection for PII awareness
└── uuid_filter.py       UUID entity filter
```

**Pipeline flow (when `pii_redaction_enabled = true`):**
```
Incoming message → anonymize() → [build surrogate registry]
                                 → egress guard check
                                 → LLM (sees surrogates only)
                → deanonymize() → [restore real entities in response]
                                 → user sees real names
```

**Architecture invariant (SC#5):** When `pii_redaction_enabled = false`, the pipeline is bypassed entirely — byte-identical to pre-v0.3.0 behavior.

### 3.4 Frontend: Context Layer (`frontend/src/contexts/`)

| Context | Provides |
|---------|---------|
| `AuthContext` | `user`, `session`, `signIn`, `signOut`, `loading` |
| `ChatContext` | Wraps `useChatState()` hook; consumed by `ChatPage` |
| `ThemeContext` | `theme` (`light`/`dark`), `toggleTheme` |
| `I18nContext` | `lang` (`id`/`en`), `t()` translation function |

**Provider nesting order** (enforced in `main.tsx`):
```
AuthProvider → ThemeProvider → I18nProvider → TooltipProvider → Routes
```
This order is load-bearing: theme cannot depend on auth state, and i18n cannot depend on theme.

### 3.5 Frontend: State Hook (`frontend/src/hooks/useChatState.ts`)

The primary state machine for the chat interface. Manages:

```typescript
{
  threads: Thread[],
  activeThreadId: string | null,
  allMessages: Message[],            // full message tree
  messages: Message[],               // active branch only
  branchSelections: Map<string, string>,
  isStreaming: boolean,
  streamingContent: string,
  activeTools: ToolStartEvent[],
  toolResults: ToolResultEvent[],
  activeAgent: { agent: string; display_name: string } | null,
  redactionStage: 'anonymizing' | 'deanonymizing' | 'blocked' | null,
  loadingThreads: boolean,
  // actions
  handleSelectThread, handleCreateThread, handleSendMessage,
  rebuildVisibleMessages, ...
}
```

Branch-aware: uses `buildChildrenMap` + `getActivePath` to resolve which message chain is visible when threads have forked.

---

## 4. Architectural Layers and Dependencies

### Dependency Rules

```
Frontend                    Backend
────────                    ───────
Pages                       Routers
  └─ uses → Contexts          └─ depends on → Dependencies
  └─ uses → Hooks               (get_current_user, require_admin)
  └─ calls → lib/api.ts       └─ calls → Services
              │                └─ calls → log_action (audit)
              │ HTTP/SSE
              ▼
           Backend Routers
              └─ MUST NOT import from → Other Routers
              └─ MAY import from → Services, Models, Dependencies
              └─ Services MUST NOT import from → Routers
              └─ Services MAY import from → Other Services (acyclic)
```

**Enforced boundaries:**
- Routers never import from other routers
- Services are instantiated per-request (no shared mutable state)
- `get_supabase_authed_client(token)` is the only way to get an RLS-scoped client; service-role client requires explicit intent
- Frontend `lib/api.ts` is the single HTTP boundary — no direct `fetch()` in components

### Layer Diagram

```
┌─────────────────────────────────────────────────────┐
│  FastAPI Application                                 │
│                                                     │
│  ┌─────────────────────────────────────────────┐    │
│  │  Router Layer (21 modules)                  │    │
│  │  • Request validation (Pydantic)            │    │
│  │  • Auth enforcement (Depends)               │    │
│  │  • Audit logging (log_action)               │    │
│  │  • Response serialization                   │    │
│  └───────────────────┬─────────────────────────┘    │
│                      │ calls                        │
│  ┌───────────────────▼─────────────────────────┐    │
│  │  Service Layer (25+ modules)                │    │
│  │  • Business logic                           │    │
│  │  • LLM orchestration                        │    │
│  │  • RAG pipeline                             │    │
│  │  • PII redaction                            │    │
│  └───────────────────┬─────────────────────────┘    │
│                      │ reads/writes                 │
│  ┌───────────────────▼─────────────────────────┐    │
│  │  Database Layer (Supabase client)           │    │
│  │  • RLS-scoped client (authed)               │    │
│  │  • Service-role client (admin ops)          │    │
│  │  • pgvector (vector search)                 │    │
│  │  • tsvector (fulltext search)               │    │
│  └─────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
```

---

## 5. Data Architecture

### Schema Overview

32 migration files define the complete schema. Key domains:

| Migration Range | Domain |
|----------------|--------|
| 001–005 | Core schema: users, documents, chunks, embeddings, metadata |
| 006–012 | Search, tool calls, branching, bilingual FTS, audit, confidence |
| 013–020 | Obligations, templates, approvals, security hardening, regulatory, notifications, DMS, Google |
| 021–023 | BJR governance, compliance snapshots, UU PDP toolkit |
| 024–028 | Knowledge base explorer, RAG improvements, graph entities, embedding training, global folders |
| 029–032 | PII entity registry, provider settings, fuzzy settings, redaction master toggle |

**Note:** Two `024_*.sql` files exist (`024_knowledge_base_explorer.sql` and `024_rag_improvements.sql`) — both applied, neither renumbered. This is a known dual-024 artifact.

### Key Tables

```
documents              — user document records (id, user_id, status, metadata)
document_chunks        — chunked text with embeddings (vector 1536-dim)
threads                — conversation threads
messages               — branching message tree (parent_id → child structure)
entity_registry        — per-thread PII surrogate map (migration 029)
system_settings        — single row (id=1), all admin-toggleable features
user_profiles          — role, is_active, auto-created on first login
audit_logs             — immutable mutation log
clause_library         — clauses (is_global + user-owned)
document_templates     — templates (is_global + user-owned)
bjr_decisions          — BJR governance records
```

### Data Access Patterns

**RLS-scoped (user data):**
```python
supabase = get_supabase_authed_client(user["token"])
result = await supabase.table("documents").select("*").eq("user_id", user["id"]).execute()
```

**Service-role (admin / system data):**
```python
supabase = get_supabase_client()  # service-role
result = await supabase.table("system_settings").select("*").eq("id", 1).single().execute()
```

**Global/shared data pattern:**
Clauses and templates use `is_global = true` to expose system-wide records to all users without RLS bypass.

**Supabase-specific gotchas:**
- Array containment: `.filter("col", "cs", "{value}")` not `.contains()`
- Search param sanitization: escape commas and parentheses in PostgREST filters

### Caching Strategy

| Cache | Location | TTL | Invalidation |
|-------|----------|-----|-------------|
| System settings | `system_settings_service.py` LRU | 60s | `update_system_settings()` clears cache |
| Semantic search results | `hybrid_retrieval_service.py` (`_cache_key`) | 5 min | Key-based (query + user + filters) |
| `get_current_user` | None — DB hit on every request | — | Stateless; validates `is_active` per-call |

### Embedding Architecture

- **Model:** OpenAI `text-embedding-3-small` (default) or custom model (configurable)
- **Dimensions:** 1536 for default model
- **Storage:** `document_chunks.embedding` column (pgvector)
- **Retrieval:** `EmbeddingService.retrieve_chunks_with_metadata()` via RPC with pre-filter support

---

## 6. Cross-Cutting Concerns

### 6.1 Authentication & Authorization

**Identity provider:** Supabase Auth (JWT tokens)

**Role hierarchy:**
```
super_admin → full access (AdminGuard on frontend, require_admin on backend)
dpo         → data protection officer ops (require_dpo)
user        → standard access (get_current_user)
```

**Backend enforcement chain:**
```python
# Step 1: Token extraction + Supabase validation
async def get_current_user(credentials: HTTPAuthorizationCredentials) -> dict:
    user = await supabase.auth.get_user(token)
    # Auto-creates user_profiles row for new signups
    # Checks user_profiles.is_active
    return {"id": user.id, "email": user.email, "token": token, "role": role}

# Step 2: Role gate (composed via Depends)
async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] != "super_admin":
        raise HTTPException(403)
    return user
```

**Frontend enforcement:**
- `AuthGuard` wraps all protected routes
- `AdminGuard` wraps `/admin/*` routes
- Role from JWT `app_metadata.role` field

**RLS pattern (Supabase SQL):**
```sql
-- User data: own records only
CREATE POLICY "users_own_data" ON documents
  FOR ALL USING (auth.uid() = user_id);

-- Admin access: super_admin bypasses RLS
CREATE POLICY "admin_all" ON documents
  FOR ALL USING (
    (auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin'
  );
```

### 6.2 Error Handling & Resilience

**Backend:**
- Services raise `HTTPException` with appropriate status codes
- PII pipeline raises `RedactionError` (caught at chat router boundary)
- Egress guard raises `EgressBlockedAbort` (caught, SSE event emitted with `blocked` stage)
- Startup: stalled `processing` documents reset to `pending` on boot
- No retry/circuit-breaker at application layer — delegated to Railway platform

**Frontend:**
- SSE errors handled in `useChatState` event listener
- `redactionStage: 'blocked'` surfaces egress blocks to user
- API errors from `lib/api.ts` bubble to component error boundaries

### 6.3 Logging & Monitoring

**Audit logging (compliance):**
```python
await log_action(
    user_id=user["id"],
    user_email=user["email"],
    action="create_document",
    resource_type="document",
    resource_id=doc_id,
    details={"filename": name},
)
```
Fire-and-forget pattern — never raises, never blocks response.

**LLM tracing (observability):**
- Provider: LangSmith or Langfuse (configurable via `tracing_provider` env var)
- Configured via `configure_tracing()` lifespan hook
- Traces: LLM calls, tool executions, retrieval steps

**Structured logging:**
- Python standard `logging` module
- No additional log aggregation configured at app layer

### 6.4 Validation

**Backend — Pydantic everywhere:**
```python
class CreateDocumentRequest(BaseModel):
    filename: str
    content_type: str
    folder_id: Optional[str] = None

# LLM outputs validated via structured response format
class ClauseAnalysisResult(BaseModel):
    clause_type: str
    risk_level: Literal["low", "medium", "high"]
    summary: str
```

**LLM output validation pattern:**
```python
async def _llm_json(prompt: str, schema: Type[T]) -> T:
    response = await openrouter.chat.completions.create(
        response_format={"type": "json_object"},
        ...
    )
    return schema.model_validate_json(response.choices[0].message.content)
```

**Frontend — TypeScript types from Supabase:**
- `lib/database.types.ts` generated from Supabase schema
- `lib/models.ts` for domain model interfaces
- No runtime validation at frontend layer

### 6.5 Configuration Management

**Two-tier configuration:**

| Tier | Location | Scope | Mutability |
|------|----------|-------|-----------|
| Env vars (`config.py` → Pydantic `Settings`) | `.env` / Railway env | Infrastructure | Deploy-time |
| System settings (`system_settings` table) | Supabase DB row | Feature flags | Runtime (admin UI) |

**System settings** are admin-toggleable at runtime (e.g., `pii_redaction_enabled`, fusion weights, rerank mode) — fetched with 60s TTL cache on every retrieval call.

**Env vars** cover API keys, service URLs, and infrastructure settings — never stored in DB.

---

## 7. Service Communication Patterns

### Synchronous (REST)

All CRUD operations use standard REST via FastAPI:
- `GET /resource` — list with filtering
- `POST /resource` — create
- `GET /resource/{id}` — fetch single
- `PATCH /resource/{id}` — partial update
- `DELETE /resource/{id}` — soft or hard delete

**No API versioning** — single `/` prefix for all endpoints.

### Asynchronous (SSE)

Chat is the only SSE endpoint:
```
POST /chat/stream → EventSource (long-lived)
```

SSE event sequence:
```
agent_start   → {"agent": "Research Agent", "display_name": "..."}
tool_start    → {"tool": "search_documents", "input": {...}}
tool_result   → {"tool": "search_documents", "output": {...}}
delta         → {"content": "partial text"}  (many, progressive)
done          → {"done": true, "thread_id": "...", "message_id": "..."}
```

Error events:
```
error         → {"error": "message"}
blocked       → {"blocked": true, "reason": "egress_pii_detected"}
```

### Realtime (Supabase Realtime)

Document processing status updates pushed via Supabase Realtime subscriptions:
- `useDocumentRealtime` hook subscribes to `documents` table changes
- Used for: upload progress, OCR completion, embedding status

### Internal Service-to-Service

All service calls are direct Python function calls — no HTTP between services, no message queue. Services are stateless and instantiated per-request.

---

## 8. Technology-Specific Patterns

### 8.1 Python / FastAPI Patterns

**Async everywhere:**
All router handlers and services are `async def`. Supabase client calls are awaited. LLM API calls use `httpx` async client under the hood.

**Dependency injection (FastAPI `Depends`):**
```python
@router.get("/documents")
async def list_documents(
    user: dict = Depends(get_current_user),         # auth
    supabase = Depends(get_supabase_authed_client),  # RLS client
    settings = Depends(get_settings),               # config
):
    ...
```

**Lifespan hooks (startup/shutdown):**
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    configure_tracing()
    await warm_up_redaction_service()
    await reset_stalled_documents()
    yield
    # shutdown (nothing currently)
```

**Pydantic models in `app/models/`:**
- `agents.py` — agent intent/response schemas
- `bjr.py` — BJR governance schemas
- `graph.py` — graph entity schemas
- `rerank.py` — `RerankResponse` for reranker outputs
- `tools.py` — tool call schemas
- `pdp.py` — UU PDP toolkit schemas

### 8.2 React Patterns

**Component hierarchy:**
```
AppLayout
  ├── IconRail (60px fixed, navigation icons)
  ├── Sidebar (340px collapsible, thread/document list)
  └── MainContent (flex-fill, active page)
       └── <Page /> (route-resolved)
```

**State architecture:**
- Global state: React Contexts (Auth, Theme, I18n)
- Feature state: Custom hooks (`useChatState`, `useSidebar`, `useDocumentRealtime`, `useToolHistory`)
- Local state: `useState` within components
- No Redux/Zustand/Jotai — contexts + hooks are sufficient for this scale

**SSE consumption pattern:**
```typescript
// in useChatState
const es = new EventSource(`/chat/stream`, { headers: { Authorization: `Bearer ${token}` } })
es.onmessage = (e) => {
  const event = JSON.parse(e.data)
  if (event.delta) appendStreamingContent(event.delta.content)
  if (event.tool_start) setActiveTools(prev => [...prev, event])
  if (event.done) finalizeMessage(event)
  if (event.blocked) setRedactionStage('blocked')
}
```

**Design system (2026 Calibrated Restraint):**
- Design tokens in `frontend/src/index.css` `:root`
- Zinc-neutral base, purple accent
- `backdrop-blur` (glass) only on transient overlays — never on persistent panels
- Buttons: solid flat, no gradients (except user chat bubbles in `MessageView.tsx`)

**Routing:**
- React Router v6 with nested routes
- `AuthGuard` and `AdminGuard` as wrapper components
- Catch-all `*` redirects to `/` (ChatPage)

---

## 9. Implementation Patterns

### 9.1 New Router Pattern

```python
# backend/app/routers/my_feature.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from ..dependencies import get_current_user, get_supabase_authed_client
from ..services.audit_service import log_action
from ..services.my_feature_service import MyFeatureService

router = APIRouter(prefix="/my-feature", tags=["My Feature"])

class CreateMyFeatureRequest(BaseModel):
    name: str
    description: Optional[str] = None

@router.post("/")
async def create(
    body: CreateMyFeatureRequest,
    user: dict = Depends(get_current_user),
    supabase = Depends(get_supabase_authed_client),
):
    result = await MyFeatureService(supabase).create(body, user["id"])
    await log_action(user["id"], user["email"], "create_my_feature", "my_feature", result["id"])
    return result
```

Then register in `main.py`:
```python
from app.routers import my_feature
app.include_router(my_feature.router)
```

### 9.2 New Service Pattern

```python
# backend/app/services/my_feature_service.py
from ..services.system_settings_service import get_system_settings

class MyFeatureService:
    def __init__(self, supabase):
        self.supabase = supabase

    async def create(self, body, user_id: str) -> dict:
        settings = get_system_settings()  # admin-toggleable config
        result = await self.supabase.table("my_feature").insert({
            "user_id": user_id,
            "name": body.name,
        }).execute()
        return result.data[0]
```

### 9.3 Admin-Only Endpoint

```python
from ..dependencies import require_admin

@router.get("/admin/my-feature")
async def admin_list(admin: dict = Depends(require_admin)):
    supabase = get_supabase_client()  # service-role for admin ops
    ...
```

### 9.4 LLM JSON Output Pattern

```python
from pydantic import BaseModel
from ..services.openrouter_service import openrouter_client

class MyLLMOutput(BaseModel):
    field_a: str
    field_b: int

async def analyze_with_llm(text: str) -> MyLLMOutput:
    response = await openrouter_client.chat.completions.create(
        model="anthropic/claude-sonnet-4-6",
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": f"Analyze: {text}"}],
    )
    return MyLLMOutput.model_validate_json(response.choices[0].message.content)
```

### 9.5 New Migration

Use `/create-migration` skill — it generates the next numbered migration file with RLS template:
```sql
-- 033_my_feature.sql
CREATE TABLE my_feature (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id),
    ...
);
ALTER TABLE my_feature ENABLE ROW LEVEL SECURITY;
CREATE POLICY "users_own_data" ON my_feature
    FOR ALL USING (auth.uid() = user_id);
```

---

## 10. Testing Architecture

### Test Pyramid

```
                    ┌─────────────────┐
                    │   E2E (Playwright│  5 specs
                    │   chat, docs,   │  tests/e2e/
                    │   auth, settings│
                    └────────┬────────┘
               ┌─────────────▼──────────────┐
               │  Integration / API Tests    │  8 suites (tests/api/)
               │  chat, documents, agents,   │  + 5 suites (backend/tests/api/)
               │  hybrid_search, security,   │
               │  settings, threads, tools,  │
               │  phase4, phase5, redaction  │
               └─────────────┬──────────────┘
        ┌─────────────────────▼──────────────────────┐
        │   Unit Tests (backend/tests/unit/)          │  23 modules
        │   chat_router_wiring, egress_filter,        │
        │   redaction_service, conversation_registry, │
        │   tool_service_signature, ...               │
        └────────────────────────────────────────────┘
```

### Test Organization

| Layer | Location | Tools | Scope |
|-------|----------|-------|-------|
| Unit | `backend/tests/unit/` | pytest | Single function/class |
| API Integration | `tests/api/` | pytest + httpx | Full HTTP round-trip |
| PII Integration | `backend/tests/api/` | pytest + mocks | Redaction pipeline |
| E2E | `tests/e2e/` | Playwright (TypeScript) | Browser flows |

### Auth Strategy

```python
# conftest.py pattern — real credentials against production API
@pytest.fixture
def auth_headers():
    return {"Authorization": f"Bearer {get_token(TEST_EMAIL, TEST_PASSWORD)}"}
```

Tests run against the **production API** (`https://api-production-cde1.up.railway.app`) by default — no mocking of the database layer. Only PII unit tests mock the Supabase client via `conftest.py` stubs.

### Test Naming Convention (RAG/Chat)

Tests use ticket-ID naming to link test to requirement:
- `CHAT-01`: POST /chat/stream returns valid SSE stream
- `HYB-07`: Chat stream works end-to-end through hybrid pipeline
- `SC#5`: Simultaneous chat requests with same PII maintain surrogate isolation

---

## 11. Deployment Architecture

### Infrastructure Topology

```
[GitHub master branch]
        │
        ├── git push origin master:main
        │         │
        │         ▼
        │   [Vercel] (auto-deploy from main)
        │   Frontend SPA
        │   vercel.json: SPA rewrite rule
        │   URL: https://frontend-one-rho-88.vercel.app
        │
        └── cd backend && railway up  (MANUAL — no auto-deploy)
                  │
                  ▼
            [Railway]
            Backend FastAPI
            Dockerfile: python:3.12-slim
              - Pre-downloads spaCy xx_ent_wiki_sm at BUILD time
              - Non-root user 'app'
              - CMD: uvicorn app.main:app --host 0.0.0.0 --port $PORT
            URL: https://api-production-cde1.up.railway.app

[Supabase Cloud]
Project: qedhulpfezucnfadlfiz
  - Postgres + pgvector
  - Auth (JWT, app_metadata roles)
  - Storage (documents)
  - Realtime (document status)
```

### Critical Deployment Gotchas

1. **Vercel deploys from `main`, not `master`:** Always run `git push origin master:main` after pushing to master, or use `cd frontend && npx vercel --prod`.

2. **Railway backend is manual:** `git push` does NOT trigger Railway deployment. Run `cd backend && railway up` explicitly after backend changes.

3. **spaCy model must be at Docker build time:** The `Dockerfile` has `RUN python -m spacy download xx_ent_wiki_sm` before the `USER app` switch. Do not remove this line — runtime download fails with `EACCES` on Railway's non-root container.

4. **Procfile release hooks are ignored on Railway when Dockerfile is present** — they are a Heroku-buildpack concept.

### Environment Variables

| Category | Vars | Location |
|----------|------|----------|
| Supabase | `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` | Railway env |
| LLM | `OPENROUTER_API_KEY`, `OPENAI_API_KEY`, `COHERE_API_KEY` | Railway env |
| Tracing | `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`, `LANGCHAIN_TRACING_V2` | Railway env |
| Search | `TAVILY_API_KEY` | Railway env |
| Frontend | `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, `VITE_API_BASE_URL` | Vercel env |

---

## 12. Extension and Evolution Patterns

### Adding a New Feature Domain

1. **Create migration** (`/create-migration`): `033_my_domain.sql` with table + RLS policies
2. **Create service**: `backend/app/services/my_domain_service.py`
3. **Create router**: `backend/app/routers/my_domain.py`
4. **Register router** in `backend/app/main.py`
5. **Create models** (if needed): `backend/app/models/my_domain.py`
6. **Create frontend page**: `frontend/src/pages/MyDomainPage.tsx`
7. **Add route** in `frontend/src/App.tsx`
8. **Add nav icon** in `frontend/src/components/layout/IconRail.tsx`
9. **Write tests**: `tests/api/test_my_domain.py` covering happy path + auth

### Adding a New Admin Toggle

1. **Add migration**: `ALTER TABLE system_settings ADD COLUMN my_feature_enabled BOOLEAN DEFAULT true`
2. **No settings service changes needed** — `get_system_settings()` returns all columns
3. **Read in service**: `settings = get_system_settings(); if not settings["my_feature_enabled"]: return early`
4. **Add UI toggle** in `frontend/src/pages/AdminSettingsPage.tsx` (both mobile and desktop panels — `CLAUDE.md` gotcha)

### Adding a New LLM Tool

1. Add tool definition in `ToolService.get_tool_definitions()`
2. Add handler in `ToolService.execute_tool()`
3. Create `_execute_my_tool()` private method
4. Tool dispatch is automatically available to the chat loop

### Integrating a New External Service

Follow the adapter pattern:
1. Create `backend/app/services/my_external_service.py` wrapping the SDK/HTTP client
2. Add config fields to `backend/app/config.py`
3. Never call external APIs directly from routers
4. Add corresponding env var documentation

### Migration Numbering

Migrations are strictly sequential (`001`–`032`). Use `/create-migration` to generate the next one. **Never edit applied migrations** (PostToolUse hook blocks edits to 001–032). The dual-024 anomaly is a frozen historical artifact — do not renumber.

---

## 13. Architectural Decision Records

> **Standalone ADR files live in `docs/adr/`.** The summaries below are quick-reference; the standalone files contain full alternatives analysis, implementation notes, and references.

| ID | Title | Status | File |
|----|-------|--------|------|
| ADR-0001 | Raw SDK over Framework (No LangChain) | Accepted | [`docs/adr/adr-0001-raw-sdk-no-langchain.md`](docs/adr/adr-0001-raw-sdk-no-langchain.md) |
| ADR-0002 | Single-Row System Settings Table | Accepted | [`docs/adr/adr-0002-single-row-system-settings.md`](docs/adr/adr-0002-single-row-system-settings.md) |
| ADR-0003 | SSE over WebSocket for Chat | Accepted | [`docs/adr/adr-0003-sse-over-websocket-chat.md`](docs/adr/adr-0003-sse-over-websocket-chat.md) |
| ADR-0004 | PII Surrogate Architecture | Accepted | [`docs/adr/adr-0004-pii-surrogate-architecture.md`](docs/adr/adr-0004-pii-surrogate-architecture.md) |
| ADR-0005 | Tests Against Production API | Accepted | [`docs/adr/adr-0005-tests-against-production-api.md`](docs/adr/adr-0005-tests-against-production-api.md) |
| ADR-0006 | Hybrid Frontend Deployment (Vercel + main) | Accepted | [`docs/adr/adr-0006-hybrid-vercel-main-deployment.md`](docs/adr/adr-0006-hybrid-vercel-main-deployment.md) |
| ADR-0007 | Model Chain-of-Thought / Reasoning Observability | Proposed | [`docs/adr/adr-0007-model-cot-observability.md`](docs/adr/adr-0007-model-cot-observability.md) |
| ADR-0008 | Internal-First Information Retrieval (Web Search Opt-In) | Proposed | [`docs/adr/adr-0008-internal-first-retrieval.md`](docs/adr/adr-0008-internal-first-retrieval.md) |

### ADR-0001: Raw SDK over Framework (No LangChain)

**Context:** LLM orchestration frameworks like LangChain were available.  
**Decision:** Raw OpenRouter/OpenAI SDK calls only. Observability tooling (e.g., LangSmith via `wrap_openai`) is permitted because it observes without altering control flow.  
**Rationale:** Framework abstraction cost (version coupling, opaque behavior, debugging difficulty) outweighs the saved boilerplate for a codebase with well-understood LLM call patterns.  
**Consequence:** More verbose LLM calls, but full control over prompts, token counts, and error handling. No "magic" abstractions hiding failure modes.

### ADR-0002: Single-Row System Settings Table

**Context:** Feature flags could be stored as a key-value table or as columns.  
**Decision:** Single row with typed columns, `id = 1`.  
**Rationale:** Type safety, Pydantic-friendly deserialization, JOIN-free reads, cache-invalidation is trivially `clear_cache()`.  
**Consequence:** Schema migrations required for new toggles; cannot add toggles at runtime without a migration. Accepted trade-off for type safety.

### ADR-0003: SSE over WebSocket for Chat

**Context:** Bidirectional streaming could use WebSocket.  
**Decision:** Server-Sent Events (SSE) for chat responses.  
**Rationale:** SSE is unidirectional (server → client) and sufficient for streaming LLM responses. Simpler than WebSocket (no connection state, standard HTTP semantics, works through proxies).  
**Consequence:** Client sends new messages via POST; SSE channel is receive-only. Multi-turn is handled by sequential POST + new SSE streams, not persistent WebSocket. ADR-0007 extends this contract with the `reasoning_delta` event.

### ADR-0004: PII Surrogate Architecture

**Context:** Real PII must not reach cloud-LLM providers.  
**Decision:** Presidio + Faker surrogate substitution at chat-loop boundary, per-thread registry in DB.  
**Rationale:** Surrogate approach preserves LLM reasoning capability (vs. redaction/masking which breaks semantic context). Registry in DB enables de-anonymization across turns and sessions.  
**Consequence:** Added latency per turn (Presidio scan + DB registry ops). Egress guard adds a hard block as defense-in-depth. ADR-0007 extends the redaction surface to cover model reasoning tokens identically.

### ADR-0005: Tests Against Production API

**Context:** Integration tests could use local/mocked environment.  
**Decision:** API integration tests run against `https://api-production-cde1.up.railway.app`.  
**Rationale:** Avoids mock/prod divergence (the team was burned by this pattern in the past). Tests verify the actual deployed system.  
**Consequence:** Tests are slower, require network access, and can be affected by production state. Acceptable for a compliance-grade platform where test fidelity is paramount.

### ADR-0006: Hybrid Frontend Deployment (Vercel + main Branch)

**Context:** Vercel could deploy from any branch.  
**Decision:** Vercel deploys from `main`; development happens on `master`.  
**Rationale:** Legacy configuration artifact from initial setup. `git push origin master:main` is the deployment trigger pattern.  
**Consequence:** Requires discipline to push to both branches; captured in CLAUDE.md gotchas.

### ADR-0007: Model Chain-of-Thought / Reasoning Observability *(Proposed)*

**Context:** Users need visibility into how the AI reasoned about their query, in addition to engineers needing trace-level debugging.  
**Decision:** Two-part approach without framework adoption — (A) LangSmith for backend developer tracing via `wrap_openai()`; (B) OpenRouter `reasoning` parameter for end-user CoT, exposed as a new `reasoning_delta` SSE event and a collapsible UI block in `MessageView.tsx`. Defer LangGraph adoption pending future triggers (BJR multi-agent orchestration, cyclic self-correction, HITL pauses, durable execution).  
**Rationale:** Solves both observability needs without violating ADR-0001. Provider-agnostic via OpenRouter abstraction. PII-safe via existing redaction pipeline.  
**Consequence:** New SSE event type, new `messages.reasoning` column, new admin toggle (`chain_of_thought_enabled`). LangGraph re-evaluation has explicit pre-agreed triggers documented in the standalone ADR.

### ADR-0008: Internal-First Information Retrieval (Web Search Opt-In) *(Proposed)*

**Context:** The Research Agent currently auto-selects among `search_documents`, `query_database`, and `web_search` (Tavily). Auto-selected web search exfiltrates query context to a third-party API, blurs answer provenance, and incurs cost/latency. Legal users want internal-first behavior with explicit opt-in for external research.  
**Decision:** Adopt internal-first as an architectural principle. Web search is **never auto-selected** by the agent classifier. Three-layer toggle gates the tool: L1 system kill switch (`system_settings.web_search_enabled`, default ON), L2 per-user default (`user_preferences.web_search_default`, default OFF), L3 per-message override on the chat composer. Effective state = `L1 AND (L3 if provided else L2)`. PII egress guard extends to inspect outbound search queries.  
**Rationale:** Privacy-by-default, predictable provenance, configurable compliance posture, explicit audit trail of every external-API call.  
**Consequence:** Migration `034_web_search_toggle.sql`. `tool_service.get_tool_definitions()` becomes parameterized by effective toggle. Citation UX distinguishes web vs. internal sources. Feature plan in `docs/PRD-Web-Search-Toggle.md` (to follow).

---

## 14. Architecture Governance

### Automated Enforcement

| Check | Trigger | What It Enforces |
|-------|---------|-----------------|
| ESLint + tsc | PostToolUse hook (`.ts`/`.tsx` edits) | TypeScript type correctness, lint rules |
| `py_compile` + import check | PostToolUse hook (`.py` edits) | Python syntax, import chain validity |
| Migration edit block | PreToolUse hook | Never modify applied migrations (001–032) |
| `.env` edit block | PreToolUse hook | Never commit secrets |

### Security Review Agents

- **`security-reviewer`**: Checks RLS bypass, missing auth, SQL injection, audit gaps
- **`rag-quality-reviewer`**: Checks retrieval pipeline correctness, RPC safety, cache keys

### Development Workflow Gates

Before every push:
```bash
cd frontend && npx tsc --noEmit && npm run lint
cd backend && python -c "from app.main import app; print('OK')"
```

Every bug fix: write regression test first.

### Planning Artifacts

- Plans saved to `~/.claude/plans/` (session-scoped) or `.agent/plans/` (legacy)
- Every plan self-verifies to 95%+ confidence before presenting
- PROGRESS.md tracks phase completion; updated after every major milestone via `/sync`

---

## 15. Blueprint for New Development

### Starting Points by Feature Type

| Feature Type | Start Here | Key Files to Copy Pattern From |
|-------------|-----------|-------------------------------|
| CRUD domain | `/create-migration` → service → router | `clause_library.py` (router + service) |
| AI document tool | `document_tools.py` router + `document_tool_service.py` | `_llm_json()` pattern |
| Admin toggle | Migration + `AdminSettingsPage.tsx` | `admin_settings.py` PATCH handler |
| Chat tool | `tool_service.py` `get_tool_definitions()` | `_execute_search_documents()` |
| Frontend page | `App.tsx` route + `IconRail.tsx` nav | `ChatPage.tsx` or `BJRDashboardPage.tsx` |

### Implementation Sequence (New Backend Feature)

```
1. Migration      → 033_my_feature.sql (table + RLS)
2. Model          → app/models/my_feature.py (Pydantic schemas)
3. Service        → app/services/my_feature_service.py
4. Router         → app/routers/my_feature.py
5. Registration   → app/main.py include_router()
6. Tests          → tests/api/test_my_feature.py
7. Frontend       → lib/api.ts function + page + route + nav
```

### Common Pitfalls to Avoid

| Pitfall | Correct Pattern |
|---------|----------------|
| Calling `get_supabase_client()` in user-scoped routes | Use `get_supabase_authed_client(user["token"])` for RLS |
| Adding glass/backdrop-blur to sidebar or input card | Glass only on transient overlays (tooltips, popovers) |
| Adding form fields to only one DocumentCreationPage panel | Always update both mobile and desktop panels |
| Modifying applied migrations | Create new migration; hook will block you anyway |
| Pushing backend code without `railway up` | Railway does not auto-deploy; run `cd backend && railway up` |
| Pushing frontend to master only | Always also push `master:main` for Vercel |
| Using `.contains()` for Supabase array filter | Use `.filter("col", "cs", "{value}")` |
| Storing `pii_redaction_enabled` in env vars | It lives in `system_settings` table, not config |

### Testing Checklist for New Features

- [ ] Happy path test (authenticated user, valid input)
- [ ] Auth test (unauthenticated → 401)
- [ ] Role test (wrong role → 403, if admin-only)
- [ ] Audit log verified in `audit_logs` table
- [ ] RLS verified (user cannot see other users' data)
- [ ] Regression test if this is a bug fix

---

*Blueprint generated 2026-04-28 from graphify knowledge graph (2,035 nodes · 3,739 edges) and live codebase analysis.*  
*Regenerate after major architectural changes with `/architecture-blueprint-generator`.*
