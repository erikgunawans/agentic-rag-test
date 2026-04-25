# LexCore — PJAA CLM Platform

## What This Is

LexCore is an Indonesian legal AI platform for Contract Lifecycle Management (CLM). It pairs a chat-with-documents interface with structured CLM tooling (clause library, document templates, approvals, obligations, regulatory intelligence, executive dashboard, BJR decision tracking, compliance snapshots, UU PDP toolkit) and an admin/RBAC layer. Users are Indonesian legal teams managing contracts, regulatory exposure, and board-level decisions.

## Core Value

Indonesian legal teams can manage the full contract lifecycle — chat with documents, draft contracts, run compliance checks, route approvals, audit decisions — with confidence that AI outputs are accurate, citable, and traceable.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. Locked unless explicitly revisited. -->

#### Chat & RAG (CHAT-*)
- ✓ **CHAT-01**: User can chat with documents via SSE streaming with tool-calling loop — *existing (Phase 0 / chat.py)*
- ✓ **CHAT-02**: User can resume past conversations from sidebar with auto-generated thread titles — *existing (Apr 2026)*
- ✓ **CHAT-03**: System routes document queries through Research Agent via intent classification — *existing (agent_service)*
- ✓ **CHAT-04**: System retrieves context via hybrid retrieval (vector + fulltext + weighted RRF + optional rerank) — *existing (HybridRetrievalService)*
- ✓ **CHAT-05**: System dispatches tools (search_documents with filter_tags/folder_id/date filters, query_database, web_search) — *existing (ToolService)*
- ✓ **CHAT-06**: System emits SSE events `agent_start → tool_start → tool_result → delta → done` — *existing*
- ✓ **CHAT-07**: System applies confidence gating: `>= 0.85` auto-approved, lower → `pending_review` — *existing*

#### RAG Pipeline (RAG-*)
- ✓ **RAG-01**: System chunks documents structure-aware (paragraphs, headings, lists) — *existing (8/8 hooks)*
- ✓ **RAG-02**: System generates embeddings via OpenAI with custom-model override support — *existing*
- ✓ **RAG-03**: System falls back to GPT-4o vision OCR for scanned PDFs — *existing*
- ✓ **RAG-04**: System pre-filters retrieval by metadata (filter_tags, folder_id, date range) — *existing (RPC params)*
- ✓ **RAG-05**: System expands queries bilingually (Indonesian/English) — *existing*
- ✓ **RAG-06**: System fuses vector + fulltext via admin-configurable weighted RRF — *existing*
- ✓ **RAG-07**: System reranks via Cohere cross-encoder (none/llm/cohere modes) — *existing*
- ✓ **RAG-08**: System caches retrieval results with 5-minute semantic-cache TTL — *existing*
- ✓ **RAG-09**: System supports graph reindex via `POST /documents/{id}/reindex-graph` — *existing*
- ✓ **RAG-10**: Eval harness scores 20-query golden set with keyword hit rate + MRR — *existing (scripts/eval_rag.py)*

#### Document Tools (DOC-*)
- ✓ **DOC-01**: User can create / compare / check compliance / analyze documents via LLM tools — *existing (document_tools.py)*
- ✓ **DOC-02**: System validates document tool outputs via Pydantic + `json_object` response format — *existing (`_llm_json` helper)*
- ✓ **DOC-03**: User can upload documents manually with auto-detect for scanned PDFs — *existing*
- ✓ **DOC-04**: User can organize documents into folders (private + global "share with all") — *existing (Apr 2026, migration 028)*

#### CLM Modules — Phase 1 (CLM1-*)
- ✓ **CLM1-01**: User can manage a clause library with global/shared clauses — *existing*
- ✓ **CLM1-02**: User can create document templates with variable substitution — *existing*
- ✓ **CLM1-03**: User can route documents through approval workflows — *existing*
- ✓ **CLM1-04**: User can track obligations against contracts — *existing*
- ✓ **CLM1-05**: System maintains an audit trail of mutations via `log_action()` — *existing*
- ✓ **CLM1-06**: Admin can manage users, roles, and permissions — *existing*

#### CLM Modules — Phase 2 (CLM2-*)
- ✓ **CLM2-01**: User can browse regulatory intelligence — *existing*
- ✓ **CLM2-02**: User receives notifications about contract events — *existing*
- ✓ **CLM2-03**: Executive dashboard shows portfolio metrics — *existing*
- ✓ **CLM2-04**: System integrates with Dokmee for document storage — *existing*
- ✓ **CLM2-05**: User can export contracts/reports to Google Drive — *existing*

#### CLM Modules — Phase 3 (CLM3-*)
- ✓ **CLM3-01**: User can capture point-in-time compliance snapshots — *existing*
- ✓ **CLM3-02**: User can run UU PDP (Indonesian data-protection) compliance toolkit — *existing*

#### BJR Module (BJR-*)
- ✓ **BJR-01**: User can record board decisions, evidence, phase progression, and risks across 25 endpoints — *existing*
- ✓ **BJR-02**: Admin can manage BJR taxonomy (decision types, evidence categories, risk types) — *existing*

#### Auth, Admin, RBAC (AUTH-*)
- ✓ **AUTH-01**: User authenticates via Supabase Auth; `user_profiles.is_active` gates access — *existing*
- ✓ **AUTH-02**: System enforces RBAC via `require_admin` (`role == "super_admin"`) — *existing*
- ✓ **AUTH-03**: System enforces RLS on all tables; users see only their own data — *existing*
- ✓ **AUTH-04**: Admin can configure system settings, audit, and reviews via UI (`/admin/*`) — *existing*

#### Settings (SET-*)
- ✓ **SET-01**: System uses single-row `system_settings` cache with 60s TTL — *existing*
- ✓ **SET-02**: User can save per-user preferences — *existing*

#### Deployment (DEPLOY-*)
- ✓ **DEPLOY-01**: Frontend deploys to Vercel from `main` branch — *existing*
- ✓ **DEPLOY-02**: Backend deploys to Railway — *existing*
- ✓ **DEPLOY-03**: Production smoke tests pass 5/5 post-deploy — *existing*

### Active

<!-- Current scope for the in-progress milestone. Filled by /gsd-new-milestone. -->

(None yet — `/gsd-new-milestone` will populate this with the next milestone's scope.)

### Out of Scope

<!-- Explicit boundaries with reasoning. Prevents re-adding later. -->

- **LangChain / LangGraph** — Raw SDK calls only. Reason: debugging clarity, deterministic control flow, lower cognitive overhead for the maintainer.
- **Automatic / scheduled ingestion** — Manual file upload only. Reason: legal-document quality demands human-in-the-loop curation; auto-crawls would introduce uncited or low-quality material.
- **Non-Indonesian legal jurisdictions** — Indonesian law only (UU PDP, BJR, Indonesian regulatory). Reason: focus on the user base; cross-jurisdictional legal AI is a different product.
- **Per-user design-system customization** — Global design tokens in `frontend/src/index.css` only. Reason: consistency outweighs personalization for a B2B legal tool; calibrated restraint applies to everyone.

## Context

- **Domain**: Indonesian Contract Lifecycle Management (CLM) for legal teams. Heavy regulatory layer (UU PDP, BJR doctrine, sector-specific rules).
- **Codebase state**: 22 FastAPI routers, 18 services, 24 React pages, 27 sequential Supabase migrations. Knowledge graph at `graphify-out/` (1,211 nodes, 192 communities); god-nodes are `HybridRetrievalService` and `ToolService` (cross-community bridges).
- **Codebase map**: Living docs in `.planning/codebase/` (refreshed 2026-04-25): STACK, INTEGRATIONS, ARCHITECTURE, STRUCTURE, CONVENTIONS, TESTING, CONCERNS.
- **Live deployments**: Frontend `https://frontend-one-rho-88.vercel.app`, backend `https://api-production-cde1.up.railway.app`, Supabase project `qedhulpfezucnfadlfiz`.
- **Observability**: LangSmith for tracing.
- **Recent shipments**: Global folders (Apr 23), LLM thread auto-naming (Apr 23), sidebar collapse + purple buttons (Apr 23), SuggestionCards height adjustment (Apr 23 — uncommitted).
- **Known concerns**: 6 pre-existing ESLint errors in `DocumentsPage.tsx` (`react-hooks/set-state-in-effect`); Pydantic v1 warning under Python 3.14; full audit in `.planning/codebase/CONCERNS.md`.

## Constraints

- **Tech stack — Frontend**: React + Vite + Tailwind + shadcn/ui + base-ui (tooltips). Reason: shipped foundation, mature DX.
- **Tech stack — Backend**: Python + FastAPI (async, `venv`). Reason: rich AI/ML library ecosystem, Pydantic for structured LLM outputs.
- **Database**: Supabase (Postgres + pgvector + Auth + Storage + Realtime). Reason: single-vendor consolidation; pgvector means no separate vector DB.
- **LLMs**: OpenRouter (chat + document tools), OpenAI (embeddings only). Reason: chat-model flexibility through one API; embedding stability via OpenAI.
- **i18n**: Indonesian (default) + English via `I18nProvider`. Reason: primary user base.
- **Migrations**: Numbered `001` through `027`, applied. **Never edit applied migrations** — pre-commit hook blocks 001-027 edits. Use `/create-migration` to generate the next.
- **Design system**: 2026 Calibrated Restraint. Glass (`backdrop-blur`) only on transient overlays (tooltips, popovers); never on persistent panels. Gradients only on user chat bubbles. Tokens centralized in `frontend/src/index.css` `:root`.
- **Deployment**: Vercel deploys from `main` (NOT `master`). Always `git push origin master:main` after pushing master, or use `/deploy-lexcore`.
- **Security**: All tables require RLS. Users only see their own data unless `is_global = true` (clauses, templates, folders).
- **Performance**: Chat must stream via SSE; semantic cache 5-min TTL; Presidio-class NER models (when introduced) must be loaded once at startup.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Raw SDK over LangChain / LangGraph | Debugging clarity, deterministic flow, fewer abstractions to maintain | ✓ Good — shipped 22 routers without LC pain |
| pgvector over dedicated vector DB | One Postgres for app + auth + vectors; simpler ops | ✓ Good — RAG pipeline shipped end-to-end |
| OpenRouter for chat / OpenAI for embeddings | Chat-model flexibility through one API; embedding stability via OpenAI | ✓ Good — supports custom embedding models without lock-in |
| Manual document ingestion only | Legal-doc quality > automation; human-in-the-loop curation | ✓ Good — no quality regressions from bad auto-ingest |
| Vercel (frontend) + Railway (backend) split | Best-of-breed for each runtime | ✓ Good — both stable, independent deploy cadence |
| Single-row `system_settings` table | Simple admin config, single source of truth | ✓ Good — avoids key-value bloat |
| Indonesian-default i18n | Primary user base, regulatory context | ✓ Good — drives content quality |
| Pydantic + `json_object` for structured LLM outputs | Validation at boundary, OpenRouter compatibility | ✓ Good — used across document tools |
| Confidence gating at 0.85 (auto-approve) | Quality threshold for legal-AI outputs | — Pending — needs prod-data calibration |
| Cohere cross-encoder reranking | Best-in-class quality for the cost | ✓ Good — eval harness shows lift |
| 2026 Calibrated Restraint design system | Zinc-neutral base, purple accent, calibrated motion | ✓ Good — shipped sidebar + welcome card refinements without regressions |
| GSD-managed planning artifacts | Atomic-commit planning artifacts, parallel agent workflows | — Pending — initialized 2026-04-25 |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state (users, feedback, metrics)

---
*Last updated: 2026-04-25 after initialization (brownfield bootstrap from CLAUDE.md + codebase map)*
