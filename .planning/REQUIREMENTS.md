# Requirements: LexCore

**Defined:** 2026-04-25
**Core Value:** Indonesian legal teams can manage the full contract lifecycle (chat with documents, draft contracts, run compliance checks, route approvals, audit decisions) with confidence that AI outputs are accurate, citable, and traceable.

> **Brownfield baseline.** This file's "Validated Baseline" section captures requirements already shipped before GSD initialization (commit `6d3bc79`). The v1 (Active) section is empty until `/gsd-new-milestone` populates it; future milestones append to v1, then move requirements into "Validated Baseline" upon completion.

## Validated Baseline

<!-- Shipped pre-GSD. Mirrors PROJECT.md "Validated" set. Locked unless explicitly revisited. -->

### Chat & RAG

- ✓ **CHAT-01**: User can chat with documents via SSE streaming with tool-calling loop
- ✓ **CHAT-02**: User can resume past conversations from sidebar with auto-generated thread titles
- ✓ **CHAT-03**: System routes document queries through Research Agent via intent classification
- ✓ **CHAT-04**: System retrieves context via hybrid retrieval (vector + fulltext + weighted RRF + optional rerank)
- ✓ **CHAT-05**: System dispatches tools (search_documents, query_database, web_search) with metadata filters
- ✓ **CHAT-06**: System emits SSE events `agent_start → tool_start → tool_result → delta → done`
- ✓ **CHAT-07**: System applies confidence gating: `>= 0.85` auto-approved, lower → `pending_review`

### RAG Pipeline

- ✓ **RAG-01**: System chunks documents structure-aware (paragraphs, headings, lists)
- ✓ **RAG-02**: System generates embeddings via OpenAI with custom-model override support
- ✓ **RAG-03**: System falls back to GPT-4o vision OCR for scanned PDFs
- ✓ **RAG-04**: System pre-filters retrieval by metadata (filter_tags, folder_id, date range)
- ✓ **RAG-05**: System expands queries bilingually (Indonesian / English)
- ✓ **RAG-06**: System fuses vector + fulltext via admin-configurable weighted RRF
- ✓ **RAG-07**: System reranks via Cohere cross-encoder (none / llm / cohere modes)
- ✓ **RAG-08**: System caches retrieval results with 5-minute semantic-cache TTL
- ✓ **RAG-09**: System supports graph reindex via `POST /documents/{id}/reindex-graph`
- ✓ **RAG-10**: Eval harness scores 20-query golden set with keyword hit rate + MRR

### Document Tools

- ✓ **DOC-01**: User can create / compare / check compliance / analyze documents via LLM tools
- ✓ **DOC-02**: System validates document tool outputs via Pydantic + `json_object` response format
- ✓ **DOC-03**: User can upload documents manually with auto-detect for scanned PDFs
- ✓ **DOC-04**: User can organize documents into folders (private + global "share with all")

### CLM Phase 1 (Core Workflow)

- ✓ **CLM1-01**: User can manage a clause library with global/shared clauses
- ✓ **CLM1-02**: User can create document templates with variable substitution
- ✓ **CLM1-03**: User can route documents through approval workflows
- ✓ **CLM1-04**: User can track obligations against contracts
- ✓ **CLM1-05**: System maintains an audit trail of mutations via `log_action()`
- ✓ **CLM1-06**: Admin can manage users, roles, and permissions

### CLM Phase 2 (Intelligence + Integrations)

- ✓ **CLM2-01**: User can browse regulatory intelligence
- ✓ **CLM2-02**: User receives notifications about contract events
- ✓ **CLM2-03**: Executive dashboard shows portfolio metrics
- ✓ **CLM2-04**: System integrates with Dokmee for document storage
- ✓ **CLM2-05**: User can export contracts/reports to Google Drive

### CLM Phase 3 (Compliance Toolkits)

- ✓ **CLM3-01**: User can capture point-in-time compliance snapshots
- ✓ **CLM3-02**: User can run UU PDP (Indonesian data-protection) compliance toolkit

### BJR Module

- ✓ **BJR-01**: User can record board decisions, evidence, phase progression, and risks across 25 endpoints
- ✓ **BJR-02**: Admin can manage BJR taxonomy (decision types, evidence categories, risk types)

### Auth, Admin, RBAC

- ✓ **AUTH-01**: User authenticates via Supabase Auth; `user_profiles.is_active` gates access
- ✓ **AUTH-02**: System enforces RBAC via `require_admin` (`role == "super_admin"`)
- ✓ **AUTH-03**: System enforces RLS on all tables; users see only their own data
- ✓ **AUTH-04**: Admin can configure system settings, audit, and reviews via UI (`/admin/*`)

### Settings

- ✓ **SET-01**: System uses single-row `system_settings` cache with 60s TTL
- ✓ **SET-02**: User can save per-user preferences

### Deployment

- ✓ **DEPLOY-01**: Frontend deploys to Vercel from `main` branch
- ✓ **DEPLOY-02**: Backend deploys to Railway
- ✓ **DEPLOY-03**: Production smoke tests pass 5/5 post-deploy

## v1 Requirements

<!-- Active scope for the in-progress milestone. Filled by /gsd-new-milestone. -->

(None yet — `/gsd-new-milestone` will populate this with the next milestone's REQ-IDs.)

## v2 Requirements

<!-- Acknowledged but deferred. Not in any current roadmap. -->

(None yet — populated as ideas surface during milestones.)

## Out of Scope

| Feature | Reason |
|---------|--------|
| LangChain / LangGraph | Raw SDK only — debugging clarity, deterministic flow, lower cognitive overhead |
| Automatic / scheduled ingestion | Manual upload only — legal-doc quality demands human-in-the-loop curation |
| Non-Indonesian legal jurisdictions | Indonesian law only (UU PDP, BJR, Indonesian regulatory) — focus on user base |
| Per-user design-system customization | Global tokens only — consistency outweighs personalization for B2B legal tool |

## Traceability

<!-- Maps requirements to phases. Validated Baseline maps to "Pre-GSD" (shipped before initialization). -->

| Requirement | Phase | Status |
|-------------|-------|--------|
| CHAT-01 through CHAT-07 | Pre-GSD | ✓ Complete |
| RAG-01 through RAG-10 | Pre-GSD | ✓ Complete |
| DOC-01 through DOC-04 | Pre-GSD | ✓ Complete |
| CLM1-01 through CLM1-06 | Pre-GSD | ✓ Complete |
| CLM2-01 through CLM2-05 | Pre-GSD | ✓ Complete |
| CLM3-01 through CLM3-02 | Pre-GSD | ✓ Complete |
| BJR-01 through BJR-02 | Pre-GSD | ✓ Complete |
| AUTH-01 through AUTH-04 | Pre-GSD | ✓ Complete |
| SET-01 through SET-02 | Pre-GSD | ✓ Complete |
| DEPLOY-01 through DEPLOY-03 | Pre-GSD | ✓ Complete |

**Coverage:**
- Validated Baseline: 38 requirements (✓ Complete, shipped pre-GSD)
- v1 (Active) requirements: 0 — awaiting `/gsd-new-milestone`
- v2 (Deferred) requirements: 0
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-25*
*Last updated: 2026-04-25 after brownfield initialization (baseline captured from existing codebase)*
