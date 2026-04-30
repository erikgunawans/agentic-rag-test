# LexCore — PJAA CLM Platform

## What This Is

LexCore is an Indonesian legal AI platform for Contract Lifecycle Management (CLM). It pairs a privacy-preserving chat interface (real PII never reaches cloud-LLM payloads — v1.0 milestone) with structured CLM tooling (clause library, document templates, approvals, obligations, regulatory intelligence, executive dashboard, BJR decision tracking, compliance snapshots, UU PDP toolkit) and an admin/RBAC layer. Users are Indonesian legal teams managing contracts, regulatory exposure, and board-level decisions.

## Core Value

Indonesian legal teams can manage the full contract lifecycle — chat with documents, draft contracts, run compliance checks, route approvals, audit decisions — with confidence that AI outputs are accurate, citable, and traceable, and that sensitive client PII never leaves the control boundary.

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
- ✓ **RAG-01**: Structure-aware chunking — *existing*
- ✓ **RAG-02**: OpenAI embeddings with custom-model override + `EMBEDDING_PROVIDER=local|cloud` switch — *existing + v1.0*
- ✓ **RAG-03**: GPT-4o vision OCR fallback for scanned PDFs — *existing*
- ✓ **RAG-04**: Metadata pre-filtering (filter_tags, folder_id, date range) — *existing*
- ✓ **RAG-05**: Bilingual query expansion (Indonesian/English) — *existing*
- ✓ **RAG-06**: Admin-configurable weighted RRF fusion — *existing*
- ✓ **RAG-07**: Cohere cross-encoder reranking (none/llm/cohere modes) — *existing*
- ✓ **RAG-08**: 5-minute semantic-cache TTL — *existing*
- ✓ **RAG-09**: Graph reindex endpoint `POST /documents/{id}/reindex-graph` — *existing*
- ✓ **RAG-10**: 20-query golden-set eval harness (keyword hit rate + MRR) — *existing*

#### Document Tools (DOC-*)
- ✓ **DOC-01..04**: Create/compare/compliance/analyze; Pydantic validation; manual ingestion; folder organization — *existing*

#### CLM Modules (CLM1-*, CLM2-*, CLM3-*)
- ✓ **CLM1-01..06**: Clause library, templates, approvals, obligations, audit trail, user management — *existing*
- ✓ **CLM2-01..05**: Regulatory intelligence, notifications, dashboard, Dokmee, Google export — *existing*
- ✓ **CLM3-01..02**: Compliance snapshots, UU PDP toolkit — *existing*

#### BJR Module (BJR-*)
- ✓ **BJR-01..02**: 25 endpoints for board decisions/evidence/risks/taxonomy — *existing*

#### Auth, Admin, RBAC (AUTH-*)
- ✓ **AUTH-01..04**: Supabase Auth, RBAC, RLS, admin UI — *existing*

#### Settings & Deployment (SET-*, DEPLOY-*)
- ✓ **SET-01..02**: System settings cache (60s TTL), per-user preferences — *existing*
- ✓ **DEPLOY-01..03**: Vercel + Railway pipeline, smoke tests — *existing*

#### PII Redaction System — v1.0 (PII-*, ANON-*, REG-*, RESOLVE-*, DEANON-*, BUFFER-*, PROMPT-*, SCAN-*, PROVIDER-*, TOOL-*, EMBED-*, OBS-*, PERF-*)
- ✓ **PII-01..05** — v1.0: Presidio + spaCy NER, two-pass thresholds, UUID filter, 16 entity types, lazy singletons
- ✓ **ANON-01..06** — v1.0: Faker surrogates, hard-redact placeholders, collision-free, gender-matched (Indonesian lookup), programmatic find-and-replace
- ✓ **REG-01..05** — v1.0: Per-thread DB-persisted registry, case-insensitive, consistency guarantee, race-protected (asyncio lock + UNIQUE constraint)
- ✓ **RESOLVE-01..04** — v1.0: Algorithmic / LLM / none modes; Union-Find clustering with 3 merge rules; pre-anonymized cloud path; non-PERSON exact-match only
- ✓ **DEANON-01..05** — v1.0: Real-value replacement, case-insensitive, Jaro-Winkler fuzzy (algorithmic/LLM/none), 3-phase placeholder-tokenized pipeline, hard-redact pass-through
- ✓ **BUFFER-01..03** — v1.0: Full response buffering when active, `redaction_status` SSE events (`anonymizing`/`deanonymizing`), sub-agent reasoning suppression
- ✓ **PROMPT-01** — v1.0: System-prompt surrogate-preservation guidance across main agent and all sub-agents
- ✓ **SCAN-01..05** — v1.0: Optional LLM missed-PII scan; all resolution modes; provider follows global setting; type validation; single-re-run cap
- ✓ **PROVIDER-01..07** — v1.0: Global `LLM_PROVIDER` + per-feature overrides; OpenAI-compatible APIs; pre-flight egress filter; secret-managed API key; admin settings UI; graceful degradation
- ✓ **TOOL-01..04** — v1.0: Symmetric anonymize/de-anonymize for search_documents, query_database, web_search, and all sub-agents
- ✓ **EMBED-01..02** — v1.0: `EMBEDDING_PROVIDER=local|cloud`; default cloud; local endpoint support; no auto-re-embedding on switch
- ✓ **OBS-01..03** — v1.0: Pluggable tracing (LangSmith/Langfuse); debug logs with `thread_id` correlation across 5 modules; resolved-provider audit log
- ✓ **PERF-01, PERF-03, PERF-04** — v1.0: Lazy singletons at startup; asyncio-lock race-protection; graceful LLM-failure degradation
- ✓* **PERF-02** — v1.0: <500ms anonymization target — 2000ms hard gate passed; 500ms unconfirmed on dev hardware (pending server-class run)

## Current Milestone: v1.1 Agent Skills & Code Execution

**Goal:** Transform LexCore's chat interface into a customizable AI agent platform where users create and manage reusable skills, attach resource files, execute sandboxed Python code, and maintain persistent tool memory across conversation turns.

**Target features:**
- Agent Skills — CRUD + discovery (lightweight catalog in system prompt, on-demand loading via `load_skill`/`save_skill` LLM tools), private/global ownership model, 3 creation paths (AI-guided, manual form, import from ZIP), Skills tab in navigation
- Skill Building-Block Files — file attachments per skill stored in Supabase Storage, on-demand LLM reading via `read_skill_file` tool, file preview panel in skill editor
- Code Execution Sandbox — sandboxed Docker Python execution (llm-sandbox), IPython session persistence per thread (TTL 30min), SSE streaming output, generated-file download via signed URLs, `SANDBOX_ENABLED` feature flag
- Skills Open Standard — ZIP import/export in agentskills.io-compatible format (SKILL.md frontmatter), bulk import support, naming conflict reporting
- Persistent Tool Memory — tool results stored in messages JSONB `tool_calls` column, reconstructed on conversation history load, no schema migration required

### Active

<!-- Fresh scope for v1.1 milestone — will be populated after requirements scoping -->

### Out of Scope

<!-- Explicit boundaries with reasoning. Prevents re-adding later. -->

- **LangChain / LangGraph** — Raw SDK calls only. Reason: debugging clarity, deterministic control flow, lower cognitive overhead.
- **Automatic / scheduled ingestion** — Manual file upload only. Reason: legal-document quality demands human-in-the-loop curation.
- **Non-Indonesian legal jurisdictions** — Indonesian law only (UU PDP, BJR, Indonesian regulatory). Reason: focus on the user base.
- **Per-user design-system customization** — Global design tokens only. Reason: consistency outweighs personalization for B2B legal tool.
- **Re-embedding on `EMBEDDING_PROVIDER` switch** — Deployer-managed migration. Reason: no automatic re-embedding avoids silent index degradation; documented in CLAUDE.md Gotchas.
- **Per-user PII toggle** — Global system_settings toggle only (admin-controlled). Reason: uniform privacy guarantee simpler to audit and support.
- **Filename / document-metadata PII redaction** — Chat message content only. Reason: metadata PII less frequently cited in LLM responses; deferred.

## Context

- **Domain**: Indonesian Contract Lifecycle Management (CLM) for legal teams. Heavy regulatory layer (UU PDP, BJR doctrine, sector-specific rules).
- **Codebase state**: 22 FastAPI routers, ~22 services (+ 10-module `redaction/` subsystem), 24 React pages, 33 sequential Supabase migrations (029–033 added in v1.0). Knowledge graph at `graphify-out/`.
- **Codebase map**: Living docs in `.planning/codebase/` (refreshed 2026-04-25). `.codegraph/` initialized.
- **Live deployments**: Frontend `https://frontend-one-rho-88.vercel.app`, backend `https://api-production-cde1.up.railway.app`, Supabase project `qedhulpfezucnfadlfiz`.
- **Observability**: LangSmith for tracing. Thread_id correlation logging across all redaction operations.
- **Test suite**: 352 tests passing (non-slow); PERF-02 slow test skips on dev hardware (passes 2000ms hard gate).
- **Privacy invariant (v1.0)**: No raw PII reaches cloud-LLM payloads. Egress filter verified at 3 call sites. `pii_redaction_enabled` DB-backed toggle in admin UI.
- **Known concerns**: 6 pre-existing ESLint errors in `DocumentsPage.tsx`; Pydantic v1 warning under Python 3.14; PERF-02 latency unconfirmed on server hardware.

## Constraints

- **Tech stack — Frontend**: React + Vite + Tailwind + shadcn/ui + base-ui (tooltips). Reason: shipped foundation, mature DX.
- **Tech stack — Backend**: Python + FastAPI (async, `venv`). Reason: rich AI/ML library ecosystem, Pydantic for structured LLM outputs.
- **Database**: Supabase (Postgres + pgvector + Auth + Storage + Realtime). Reason: single-vendor consolidation; pgvector means no separate vector DB.
- **LLMs**: OpenRouter (chat + document tools), OpenAI (embeddings, default). `EMBEDDING_PROVIDER=local` supported for local endpoints. Reason: chat-model flexibility; embedding stability.
- **i18n**: Indonesian (default) + English via `I18nProvider`. Reason: primary user base.
- **Migrations**: Numbered `001` through `033`, applied. **Never edit applied migrations** — pre-commit hook blocks 001-033 edits. Use `/create-migration` to generate the next.
- **Design system**: 2026 Calibrated Restraint. Glass (`backdrop-blur`) only on transient overlays; never on persistent panels. Gradients only on user chat bubbles.
- **Deployment**: Vercel deploys from `main` (NOT `master`). Always `git push origin master:main` after pushing master, or use `/deploy-lexcore`.
- **Security**: All tables require RLS. Users only see their own data unless `is_global = true`.
- **Performance**: Chat must stream via SSE; semantic cache 5-min TTL; Presidio NER models loaded once at startup (lazy singletons).

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Raw SDK over LangChain / LangGraph | Debugging clarity, deterministic flow, fewer abstractions | ✓ Good — shipped 22 routers + full redaction subsystem without LC complexity |
| pgvector over dedicated vector DB | One Postgres for app + auth + vectors; simpler ops | ✓ Good — RAG pipeline shipped end-to-end |
| OpenRouter for chat / OpenAI for embeddings | Chat-model flexibility; embedding stability | ✓ Good — `EMBEDDING_PROVIDER=local` option added without breaking RAG-02 |
| Manual document ingestion only | Legal-doc quality > automation | ✓ Good — no quality regressions from bad auto-ingest |
| Vercel (frontend) + Railway (backend) split | Best-of-breed for each runtime | ✓ Good — both stable, independent deploy cadence |
| Single-row `system_settings` table | Simple admin config, single source of truth | ✓ Good — used for PII toggle, provider settings, and all existing config |
| Indonesian-default i18n | Primary user base, regulatory context | ✓ Good — drives content quality |
| Pydantic + `json_object` for structured LLM outputs | Validation at boundary, OpenRouter compatibility | ✓ Good — used across document tools and redaction service |
| Confidence gating at 0.85 (auto-approve) | Quality threshold for legal-AI outputs | — Pending — needs prod-data calibration |
| Cohere cross-encoder reranking | Best-in-class quality for the cost | ✓ Good — eval harness shows lift |
| 2026 Calibrated Restraint design system | Zinc-neutral base, purple accent, calibrated motion | ✓ Good — shipped sidebar + welcome card refinements without regressions |
| GSD-managed planning artifacts | Atomic-commit planning artifacts, parallel agent workflows | ✓ Good — v1.0 milestone (6 phases, 44 plans) executed cleanly; parallel worktree agents effective |
| Chat-time anonymization (not ingestion-time) | Avoids double-anonymization chains, preserves chunk boundaries, enables conversation-scoped entity resolution | ✓ Good — no chunk-boundary corruption in production; entity resolution works correctly within thread scope |
| Conversation-scoped entity registries | Cross-conversation surrogate isolation; bounded registry growth | ✓ Good — SC#5 race verified against live Supabase UNIQUE constraint; thread isolation working |
| Buffer-and-de-anonymize over stream-and-de-anonymize | Eliminates surrogate-boundary edge cases; enables fuzzy de-anon on complete response | ✓ Good — SSE status events preserved UX; user-visible latency acceptable for legal workflow |
| Two-pass Presidio detection (0.7 surrogate / 0.3 hard-redact) | Single threshold trades off false-pos vs false-neg unsafely for mixed risk profiles | ✓ Good — surrogate and hard-redact buckets cleanly separated; no false-positive hard-redacts in testing |
| Pre-anonymized cloud LLM path | Privacy invariant: no real PII to cloud; defense-in-depth against vendor breach/training-data leakage | ✓ Good — egress filter verified at 3 auxiliary call sites; test suite asserts no raw PII in any LLM payload |
| `EMBEDDING_PROVIDER` configurable (local/cloud) | Deployer choice; preserves RAG-02 by default; no auto-re-embedding on switch | ✓ Good — documented in CLAUDE.md Gotchas; EMBED-02 correctly scoped as deployer-managed migration |
| D-48 canonical-only egress scan | Only longest real value per surrogate for egress, not all variants | ✓ Good — fixed production false-positive trips on legal vocabulary (thread bf1b7325) |
| `pii_redaction_enabled` moved to `system_settings` DB | Admin can toggle without Railway redeploy | ✓ Good — migration 032 applied; admin UI toggle functional |

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
*Last updated: 2026-04-25 — milestone v1.0 PII Redaction System started (`/gsd-new-milestone`)*

*Last updated: 2026-04-29 — **Milestone v1.0 PII Redaction System COMPLETE** ✅ — All 54 v1.0 REQ-IDs shipped (53 full + PERF-02 partial pending hardware). 6 phases, 44 plans, 352 tests, 5 migrations (029–033). Privacy invariant end-to-end: no real PII reaches cloud-LLM payloads. Active requirements moved to Validated. Key Decisions updated.*

*Last updated: 2026-04-29 — Milestone v1.1 Agent Skills & Code Execution started (`/gsd-new-milestone`)*

*Last updated: 2026-04-29 — **Phase 7 Complete** ✅ — Skills Database & API Foundation shipped. 2 migrations (034 skills table + RLS + seed, 035 skill_files + Storage bucket + RLS), skill_zip_service (ZIP export/import, 32 unit tests), 8-endpoint skills router (CRUD + share + export/import), ASGI upload-size middleware, 29 integration tests all passing. 3 runtime bugs fixed post-verification. Phase 8 (LLM Tool Integration) is next.*

*Last updated: 2026-05-01 — **Phase 8 Complete** ✅ — LLM Tool Integration & Discovery shipped. 3 new LLM tools (`load_skill`, `save_skill`, `read_skill_file`) in tool_service.py with RLS-scoped token plumbing through `execute_tool()`; `skill_catalog_service.py` with `build_skill_catalog_block()` injected into both single-agent and multi-agent system-prompt sites in chat.py; 3 HTTP file endpoints (upload/delete/GET content) + dual-gate middleware extension (10 MB for skill files, 50 MB for import). 26 new tests (12 unit + 5 integration + 9 service). 2 code-review criticals fixed post-verification (audit log + global-skill storage fallback). Phase 9 (Skills Frontend) is next.*
