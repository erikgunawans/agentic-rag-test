# LexCore — PJAA CLM Platform

## What This Is

LexCore is an Indonesian legal AI platform for Contract Lifecycle Management (CLM). It pairs a privacy-preserving chat interface (real PII never reaches cloud-LLM payloads — v1.0 milestone) with structured CLM tooling (clause library, document templates, approvals, obligations, regulatory intelligence, executive dashboard, BJR decision tracking, compliance snapshots, UU PDP toolkit) and an admin/RBAC layer. Users are Indonesian legal teams managing contracts, regulatory exposure, and board-level decisions.

## Core Value

Indonesian legal teams can manage the full contract lifecycle — chat with documents, draft contracts, run compliance checks, route approvals, audit decisions — with confidence that AI outputs are accurate, citable, and traceable, and that sensitive client PII never leaves the control boundary.

## Current Milestone: v1.3 Agent Harness & Domain-Specific Workflows

**Goal:** Transform LexCore from chat-with-tools into a full autonomous agent platform with two harness layers — a soft LLM-driven harness (Deep Mode) and a hard system-driven domain harness — delivering a Contract Review Harness as the first domain implementation.

**Target features:**
- General-Purpose Agent Harness (Deep Mode): per-message toggle, planning todos, virtual workspace filesystem, sub-agent task delegation, ask-user mid-task clarification, error handling, session persistence
- Domain-Specific Harness Engine: backend state machine with 5 phase types (programmatic / llm_single / llm_agent / llm_batch_agents / llm_human_input), `harness_runs` table, gatekeeper LLM, post-harness response LLM, human-in-the-loop context gathering, batched parallel sub-agents, file upload (DOCX/PDF), Plan Panel locked variant
- Contract Review Harness (first domain implementation): 8-phase deterministic workflow (intake → classification → context → playbook RAG → clause extraction → risk analysis batched → redline batched → executive summary + DOCX deliverable)
- Cross-cutting: 3 new tables (`agent_todos`, `workspace_files`, `harness_runs`) with RLS; `messages` modified with `deep_mode` boolean + `harness_mode` text; privacy invariant preserved across all new code paths

**Source PRD:** `docs/PRD-Agent-Harness.md`

**Phase numbering:** Continues from v1.2 (last phase 16) → v1.3 starts at Phase 17.

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

#### Advanced Tool Calling & Agent Intelligence — v1.2 (CTX-*, HIST-*, TOOL-*, BRIDGE-*, MCP-*, REDACT-01, TEST-01, UI-01)
- ✓ **CTX-01..06** — v1.2: Context window usage bar (token count + color thresholds), `usage` SSE event, `LLM_CONTEXT_WINDOW` env, `GET /settings/public`, per-thread reset, graceful no-bar on unsupported providers
- ✓ **HIST-01..06** — v1.2: Per-round message persistence in `tool_calls` JSONB, `buildInterleavedItems()` helper, `SubAgentPanel` + `CodeExecutionPanel` history reconstruction, `ToolCallCard` triple-branch routing
- ✓ **TOOL-01..06** — v1.2: Unified `ToolRegistry` with `register()`, native/skill/MCP sources, `tool_search` meta-tool (keyword + regex), compact catalog in system prompt (≤50 tools), `TOOL_REGISTRY_ENABLED` byte-identical fallback
- ✓ **BRIDGE-01..07** — v1.2: `/bridge/call|catalog|health` FastAPI endpoints, pre-baked `ToolClient` (stdlib-only) in sandbox Docker image, runtime typed stub injection, session-token auth, network isolation (bridge-only), `code_mode_start` SSE, dangerous-import block list preserved
- ✓ **MCP-01..06** — v1.2: `MCPClientManager` over stdio, `MCP_SERVERS` env parsing, eager OpenAI-format schema conversion, registry registration as `source="mcp"`, reconnect-with-exponential-backoff, zero startup cost when disabled
- ✓ **REDACT-01** — v1.2: Configurable PII domain-term deny list (`pii_domain_deny_list_extra` column, 60s-cached union, migration 037 applied)
- ✓ **TEST-01** — v1.2: Vitest bootstrapped; `CodeExecutionPanel.tsx` automated component tests (streaming, terminal, signed-URL, history parity)
- ✓ **UI-01** — v1.2: base-ui `asChild` shim sweep complete — `select.tsx`, `dropdown-menu.tsx`, `dialog.tsx` all support render-prop pattern

#### Agent Skills & Code Execution — v1.1 (SKILLS-*, SANDBOX-*, MEM-*)
- ✓ **SKILLS-01..07** — v1.1: Skills DB (migration 034+035), ZIP export/import, 8-endpoint router, LLM tool integration (`load_skill`, `save_skill`, `read_skill_file`), skill catalog injected into system prompt, frontend CRUD UI
- ✓ **SANDBOX-01..07** — v1.1: Code execution sandbox (`llm-sandbox`), per-thread IPython session reuse, 30-min idle TTL, signed-URL file downloads, `execute_code` tool (safe-off gate), `code_stdout`/`code_stderr` SSE events, `CodeExecutionPanel` UI
- ✓ **MEM-01..03** — v1.1: `code_executions` immutable audit table (migration 036), per-round tool-call persistence in `tool_calls` JSONB, history reconstruction in `_expand_history_row`

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

## Current State (Post-v1.2 complete — 2026-05-03)

**Completed milestone:** v1.2 Advanced Tool Calling & Agent Intelligence (2026-05-03)
**Live (prod) version:** v0.5.0.0 (tag `v0.5.0.0`) — v1.2 code committed but not yet deployed to production (all features dark behind `TOOL_REGISTRY_ENABLED=false` / `SANDBOX_ENABLED=false`)
**Live deployments:** Frontend on Vercel, backend on Railway, Supabase project `qedhulpfezucnfadlfiz` (migrations 001–037 applied)
**v1.2 outcome:** Milestone shipped 25 plans across 5 phases (12–16), executed in two parallel waves. Wave A (Phases 12‖13‖16) ran first; Wave B (Phases 14‖15) unblocked after Phase 13. All 34 v1.2 requirements covered. Phase 15 verified PASS (26/26 must-haves). Phase 14 18/18 byte-identical tests green. Vitest bootstrapped as the first frontend test framework. NoneType bug fixed in `_expand_with_neighbors`.

**Deferred to next milestone:**
- Async-lock cross-process upgrade (D-31) — per-process `asyncio.Lock` sufficient at current Railway scale
- PERF-02 — server-class hardware confirmation pending Railway test run
- Signed-URL download UX polish (cosmetic, no 404 vs 500 distinction)
- Multi-worker IPython session semantics for Railway horizontal scale-out
- Deploy v1.2 features to production (flip `TOOL_REGISTRY_ENABLED=true` + `SANDBOX_ENABLED=true` in Railway env, deploy Docker image, run smoke tests)
- Deploy v1.3 Phase 17–19 features to production (flip `DEEP_MODE_ENABLED=true` + `WORKSPACE_ENABLED=true` + `SUB_AGENT_ENABLED=true` in Railway env, deploy, run smoke tests). Operator decision on 2026-05-03 to hold dark until Phase 20 lands so the workspace + sub-agent + harness flags can flip together — `llm_agent` phase types in the harness engine reuse workspace, so combined validation is simpler than incremental flips.

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
| Adapter-wrap invariant (v1.2 D-P13-01) | Phase 13 wraps native tools without touching `tool_service.py` lines 1-1283; byte-identical fallback when flag off | ✓ Good — snapshot test + subprocess no-import test both PASS; zero-risk dark launch |
| Skill = first-class tool (v1.2 D-P13-02) | Each user skill registers as a distinct tool entry in the unified registry, not as a monolithic skill-runner | ✓ Good — tool_search can surface individual skills by name/description |
| Single unified catalog in system prompt (v1.2 D-P13-03) | One `## Available Tools` table (≤50 entries) replaces N individual tool schemas in the prompt | ✓ Good — prompt token cost stays bounded regardless of skill library size |
| `tool_search` as meta-callout (v1.2 D-P13-04) | LLM calls `tool_search` to pull full schemas on demand; active-set scoped to current turn | ✓ Good — scales to 100+ tools without bloating every prompt |
| Bridge ToolClient uses stdlib only (v1.2 D-P14-01) | `urllib.request` only in sandbox `tool_client.py` — no pip deps in sandbox image | ✓ Good — sandbox image stays lean; no dependency conflicts |
| Bridge token = per-execution JWT (v1.2 D-P14-03) | Short-lived JWT signed by host per execution, not user's auth token | ✓ Good — credential isolation; token leakage surface minimized |
| MCP stdio transport only (v1.2 D-P15) | MCP over stdio for v1.2; SSE transport deferred | ✓ Good — simpler subprocess model; SSE deferred to future milestone |
| `available` field on ToolDefinition (v1.2 D-P15-01) | Registry marks MCP tools unavailable on disconnect rather than removing them | ✓ Good — clean reconnect path without re-registration overhead |
| Vitest 3.2 for frontend tests (v1.2 D-P16-02) | Vitest 2.x incompatible with Vite 8; version bump required | ✓ Good — first frontend test suite established; co-located `__tests__/` convention |

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

*Last updated: 2026-05-02 — **Milestone v1.1 Agent Skills & Code Execution COMPLETE** ✅ — All 26 v1.1 REQ-IDs shipped. 5 phases (7–11), 26 plans, ~314 tests, 3 migrations (034–036). Skills system + Code Execution Sandbox + Persistent Tool Memory all live in prod as v0.5.0.0. Privacy invariant preserved (sandbox stdout/stderr anonymized through registry-based filter before reaching cloud LLM). Phase 11 verified PASS-WITH-CAVEATS (operational caveats only). Production smoke 5/5 green. Full archive: `.planning/milestones/v1.1-ROADMAP.md` and `.planning/milestones/v1.1-REQUIREMENTS.md`. No active milestone — `/gsd-new-milestone` to scope v1.2.*

*Last updated: 2026-05-02 — **Milestone v1.2 Advanced Tool Calling & Agent Intelligence started** (`/gsd-new-milestone`). Source PRD: `docs/superpowers/PRD-advanced-tool-calling.md`. Scope: 5 PRD features (Context Window Indicator, Interleaved History Rendering, Tool Registry + Search, Sandbox HTTP Bridge, MCP Client) + 3 bundled v1.1 backlog items (Fix B PII deny list, CodeExecutionPanel tests, base-ui asChild shim sweep). Phase numbering continues from 11 → starts at Phase 12. All tool-calling features ship dark behind `TOOL_REGISTRY_ENABLED` and `SANDBOX_ENABLED` flags.*

*Last updated: 2026-05-03 — **Milestone v1.2 Advanced Tool Calling & Agent Intelligence COMPLETE** ✅ — All 34 v1.2 REQ-IDs shipped (CTX×6, HIST×6, TOOL×6, BRIDGE×7, MCP×6, REDACT×1, TEST×1, UI×1). 5 phases (12–16), 25 plans, Wave A (12‖13‖16) + Wave B (14‖15) parallel execution. Phase 15 verified PASS (26/26 must-haves). Vitest bootstrapped. NoneType RAG bug fixed. Migration 037 live. All v1.2 requirements moved to Validated. Full archive: `.planning/milestones/v1.2-ROADMAP.md` and `.planning/milestones/v1.2-REQUIREMENTS.md`. Next: `/gsd-new-milestone` to scope v1.3.*

*Last updated: 2026-05-03 — **Milestone v1.3 Agent Harness & Domain-Specific Workflows started** (`/gsd-new-milestone docs/PRD-Agent-Harness.md`). Source PRD: `docs/PRD-Agent-Harness.md`. Scope: General-Purpose Deep Mode harness (7 features), Domain-Specific Harness Engine (7 features), Contract Review Harness as first domain implementation (8-phase workflow + DOCX deliverable). Phase numbering continues from 16 → starts at Phase 17. Research skipped (PRD highly prescriptive). Privacy invariant preserved — all new agent paths route through existing redaction pipeline.*

*Last updated: 2026-05-03 — **Phase 17 Deep Mode Foundation + Planning Todos + Plan Panel COMPLETE** ✅ — All 20 must-haves verified (DEEP×7, TODO×7, MIG-01, MIG-04, SEC-01, CONF×3). 7 plans across 4 waves: 17-01 migration 038 (`agent_todos` table + RLS + `messages.deep_mode`), 17-02 config knobs (`MAX_DEEP_ROUNDS=50`, `MAX_TOOL_ROUNDS=25`, `MAX_SUB_AGENT_ROUNDS=15`, `DEEP_MODE_ENABLED=false`), 17-03 `write_todos`/`read_todos` LLM tools, 17-04 `run_deep_mode_loop()` chat-loop branch (SC#5 byte-identical when off), 17-05 `GET /threads/{id}/todos` REST hydration endpoint, 17-06 frontend toggle + Deep Mode badge, 17-07 PlanPanel UI with SSE-driven real-time todos. Migration 038 applied to Supabase production (qedhulpfezucnfadlfiz). 2 inline gap fixes post-verification: CR-03 NameError in `_run_tool_loop_for_test` and CR-04 unconditional `_register_phase17_todos()` import — both resolved at commit 3e83a1e. Open warnings (CR-01 non-atomic write_todos, CR-02 deep-mode history drops, CR-05 missing stream_callback) are non-blocking for dark-launch and tracked in 17-REVIEW.md.*

*Last updated: 2026-05-03 — **Phase 18 Workspace Virtual Filesystem COMPLETE** ✅ — All 12/12 must-haves verified (WS-01–WS-11, MIG-02). 8 plans across 7 waves: 18-01 migration 039 (`workspace_files` table + RLS + `workspace-files` private Storage bucket), 18-02 `WorkspaceService` (path validator, text/binary CRUD, `register_sandbox_files`, structured LLM errors — 25 TDD tests), 18-03 4 LLM tools (`write_file`, `read_file`, `edit_file`, `list_files`) in tool registry (11 tests), 18-04 workspace REST API (`GET /threads/{id}/files`, `GET /threads/{id}/files/{path}`) behind `workspace_enabled` flag (8 API tests), 18-05 sandbox→workspace bridge in `sandbox_service._collect_and_upload_files` — fixes v1.1 disappearing-link bug (6 integration tests), 18-06 `workspace_updated` SSE at 3 emission sites in chat loop (3 SSE tests), 18-07 `WorkspacePanel.tsx` frontend with `workspaceFiles` state slice + i18n (7 Vitest tests), 18-08 E2E + privacy gate (20 tests: 16 E2E + 4 PII non-leakage). 65 total tests, 5 skipped. Migration 039 applied to Supabase production (qedhulpfezucnfadlfiz). Feature dark-launched (`workspace_enabled=False` default). 2 critical open items in 18-REVIEW.md (CR-01 read_file PII path, CR-02 storage orphan on binary write). Human UAT pending for E2E flag-on run + UI + prod flag decision. Phase 19 (Sub-Agent Delegation + Ask User + Status & Recovery) ready next.*

*Last updated: 2026-05-03 — **Phase 19 Sub-Agent Delegation + Ask User + Status & Recovery COMPLETE** ✅ — All 17/17 must-haves verified (TASK×7, ASK×4, STATUS×6). 10 plans across 5 waves: 19-01 migration 040 (`agent_runs` table — paused/resumable run state with partial-unique active-run index + `messages.parent_task_id`), 19-02 `AgentRunsService` (state-machine: start/transition/complete/error, RLS-scoped, race-protected via UNIQUE), 19-03 `sub_agent_loop.py` (493 LOC scoped Deep Mode loop with D-09 retention, D-11 cap, D-12 failure isolation, D-21 egress privacy, D-22 JWT inheritance), 19-04 `task` tool wired through tool_service adapter-wrap + chat.py dispatch with task_id-tagged SSE forwarding, 19-05 `ask_user` tool with two-request pause/resume handshake (Site B `agent_status:waiting_for_user` owner) + resume detection branch in `stream_chat`, 19-06 `agent_status` SSE Sites A/C/D + `agent_runs` lifecycle, 19-07 frontend (AgentStatusChip, TaskPanel, MessageView question-bubble, 12 i18n keys × 2 locales, SSE type extensions), 19-08 deep-mode prompt guidance replacing Phase 17 stubs, 19-09 backend E2E suite (12 tests, 17 REQ-IDs covered), 19-10 Vitest component tests (23 tests). 156+ tests pass. Migration 040 applied to Supabase production (qedhulpfezucnfadlfiz). Feature dark-launched (`sub_agent_enabled=False` default). Code review found 2 Critical + 3 Warning + 3 Info — 5 fixed in this phase (C-01 start_run inside try block, C-02 transition_status audit identity, W-01 tool_registry flag guard, W-02 dead elif removed, W-03 tool_call_id matching), 3 Info remain advisory. Bonus: 3 unrelated UI bugs caught during human UAT and fixed in same flight (settings subtitle i18n, ThreadPanel wordmark light-theme alignment via single-SVG + filter approach, WelcomeScreen logo replacement using lc-light/lc-dark PNGs). Phase 20 (Harness Engine Core + Gatekeeper + Post-Harness + File Upload + Locked Plan Panel) ready next.*

*Last updated: 2026-04-29 — Milestone v1.1 Agent Skills & Code Execution started (`/gsd-new-milestone`)*

*Last updated: 2026-04-29 — **Phase 7 Complete** ✅ — Skills Database & API Foundation shipped. 2 migrations (034 skills table + RLS + seed, 035 skill_files + Storage bucket + RLS), skill_zip_service (ZIP export/import, 32 unit tests), 8-endpoint skills router (CRUD + share + export/import), ASGI upload-size middleware, 29 integration tests all passing. 3 runtime bugs fixed post-verification. Phase 8 (LLM Tool Integration) is next.*

*Last updated: 2026-05-01 — **Phase 8 Complete** ✅ — LLM Tool Integration & Discovery shipped. 3 new LLM tools (`load_skill`, `save_skill`, `read_skill_file`) in tool_service.py with RLS-scoped token plumbing through `execute_tool()`; `skill_catalog_service.py` with `build_skill_catalog_block()` injected into both single-agent and multi-agent system-prompt sites in chat.py; 3 HTTP file endpoints (upload/delete/GET content) + dual-gate middleware extension (10 MB for skill files, 50 MB for import). 26 new tests (12 unit + 5 integration + 9 service). 2 code-review criticals fixed post-verification (audit log + global-skill storage fallback). Phase 9 (Skills Frontend) is next.*

*Last updated: 2026-05-01 — **Phase 10 Complete** ✅ — Code Execution Sandbox Backend shipped. Migration 036 adds `code_executions` (immutable audit, RLS: SELECT own + super_admin, INSERT only — no UPDATE/DELETE) + `sandbox-outputs` private bucket with 4-segment path RLS. `SandboxService` (399 LOC) wraps llm-sandbox with one-container-per-thread session reuse for variable persistence (D-P10-04), 30-min idle TTL via 60s asyncio cleanup loop (D-P10-10), per-call timeout via `asyncio.wait_for` + `run_in_executor` bridge (D-P10-12), and 1-hour signed URLs for output files (D-P10-14). `execute_code` tool registered in tool_service with `settings.sandbox_enabled` safe-off gate (default False, SANDBOX-05). Queue-adapter SSE streaming in chat.py emits `code_stdout`/`code_stderr` events with redaction-safe path (D-89 invariant honored). `GET /code-executions` router (RLS-scoped, signed URL refresh at read time) registered as router #23. 24/24 unit tests pass. 3 human UAT items pending (E2E Docker streaming, Supabase prod confirm, Dockerfile build smoke). Phase 11 (Code Execution UI & Persistent Tool Memory) is next.*
