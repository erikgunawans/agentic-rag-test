# Product Status

The evolution of Knowledge Hub, from a RAG learning project to a legal document intelligence platform.

## Current Product: LexCore v2.1 (codename Knowledge Hub)

**What it is:** An AI-powered legal document workspace for Indonesian professionals. Chat with your documents, generate contracts, compare versions, check compliance, analyze risks, all with privacy-first PII handling that keeps real names, emails, and phone numbers out of cloud-LLM payloads.

**Target market:** Indonesian legal professionals, compliance officers, and business teams who work with contracts, NDAs, and regulatory documents daily, especially those subject to UU PDP and OJK data-residency requirements.

**Status:** Feature-complete (v2.1, semver 0.3.0.0), deployed (Vercel + Railway). RAG pipeline 8/8 shipped, BJR governance live, UU PDP toolkit live, **PII Redaction System v1.0 live (Phases 1-5 of 6 complete; Phase 6 cross-process async-lock upgrade remaining)**. 31 migrations, 22 routers, 19 services. Backend Railway deploy is manual via `railway up`; frontend Vercel deploys from `main` branch.

---

## Product Evolution Timeline

### Phase 1: RAG Foundation (Modules 1-6)
**Period:** Initial build
**Focus:** Core RAG infrastructure

Built the technical foundation: document ingestion, vector search, hybrid retrieval, metadata extraction, multi-format support. At this stage the product was a generic RAG chat tool with no domain focus.

**Key decisions:**
- Chose OpenRouter over OpenAI-only for model flexibility
- Stateless chat architecture (full history sent each request) over managed threads
- pgvector + full-text search hybrid over vector-only
- No LangChain/LangGraph, raw SDK calls only

### Phase 2: Agentic Capabilities (Modules 7-8)
**Period:** After RAG foundation
**Focus:** Tool calling + sub-agents

Added tool calling (document search, text-to-SQL, web search) and sub-agent routing (research, data analyst, general). The product gained the ability to reason about which tool to use and delegate to specialists.

**Key decisions:**
- Three-agent architecture (research, data_analyst, general) over monolithic agent
- Non-streaming tool rounds + streaming final response over fully streaming everything
- Tool results visible in UI (attribution) over hidden execution

### Phase 3: Enterprise Controls (Module 9)
**Period:** After agentic capabilities
**Focus:** RBAC + admin configuration

Added role-based access control with super_admin role, system-wide settings (LLM model, RAG params, tool/agent toggles), and per-user preferences. Separated admin configuration from user settings.

**Key decisions:**
- 3-layer RBAC enforcement (database RLS, backend dependency, frontend guard)
- Single-row system_settings table over per-user configuration
- Admin promotion via CLI script (not self-service)

### Phase 4: Legal Domain Focus (Figma UI + Document Tools)
**Period:** After enterprise controls
**Focus:** Legal document intelligence features

Pivoted from generic RAG to legal-specific tools: document creation (NDAs, contracts, service agreements), document comparison, compliance checking (OJK, GDPR, international), and contract risk analysis. Added bilingual support (Indonesian + English).

**Key decisions:**
- Four specialized tools over a single "analyze document" feature
- Bilingual output (English + Indonesian) for legal documents
- FormData file upload over base64 encoding
- Stateless operations initially, then added result persistence

**Market signal:** Indonesian legal professionals need tools that understand local regulatory frameworks (OJK) alongside international standards (GDPR). Bilingual output is not optional, it is the default.

### Phase 5: Design Maturity
**Period:** 2026-04-12
**Focus:** Production-grade UI/UX

Comprehensive design overhaul: mobile responsive layout, accessibility compliance, AI slop elimination, micro-interactions, unified sidebar behavior. Design Score improved from B- to A, AI Slop Score from B+ to A+.

**Key decisions:**
- Mobile-first responsive with hamburger menu + panel overlays
- Eliminated all AI slop patterns (icon circles, pulse rings, gradient borders)
- Shared sidebar collapse state across all pages (not per-page)
- Chat input pinned to bottom (matching ChatGPT/Claude pattern)
- prefers-reduced-motion support for all animations

### Phase 6: 2026 Design Refresh + Light Theme
**Period:** 2026-04-14 to 2026-04-15
**Focus:** Calibrated Restraint design system

Zinc-neutral palette, solid sidebars (no glass on persistent panels), flat buttons, grouped icon rail (14→7 items with flyout groups), light/dark/system theme support, FOUC prevention. Design spec: `docs/superpowers/specs/2026-04-14-design-2026-refresh.md`.

### Phase 7: BJR Decision Governance
**Period:** 2026-04-17
**Focus:** Business Judgment Rule compliance

Full BJR module: 6 tables, 25 endpoints, regulatory matrix (28 regulations, 4 layers), 16-item checklist, LLM evidence assessment, phase progression workflow, risk register, GCG aspect tracking.

### Phase 8: Compliance + PDP Toolkit
**Period:** 2026-04-17
**Focus:** Point-in-time compliance + Indonesian data protection

F13: compliance snapshots with timeline view + diff comparison. F14: UU PDP toolkit with data inventory, DPO appointment, breach incident management (72-hour countdown), LLM personal data scanner.

### Phase 9: RAG Pipeline Complete
**Period:** 2026-04-18 to 2026-04-20
**Focus:** Full retrieval pipeline + developer tooling

8 RAG hooks: structure-aware chunking, vision OCR for scanned PDFs, custom embedding models, metadata pre-filtering (tags/folder/date), bilingual query expansion, weighted RRF fusion, Cohere Rerank v2, graph re-indexing. Plus: RAG evaluation golden set, Claude Code automations (.mcp.json, hooks, skills, agents).

### Phase 10: PII Redaction System v1.0
**Period:** 2026-04-26 to 2026-04-28 (semver v0.3.0.0; GSD milestone v1.0)
**Focus:** Privacy-first PII handling for cloud-LLM calls

Shipped the privacy invariant: real PII (names, emails, phones, locations, dates, URLs, IPs) never reaches cloud-LLM payloads. Indonesian-aware detection via Presidio + spaCy `xx_ent_wiki_sm` with honorifics (Pak/Bu/Bpk/Ibu/Sdr/Sdri) and gender-matched Faker surrogates. Phases 1-5 complete (detection, conversation-scoped registry, entity resolution, fuzzy de-anonymization, chat-loop integration). Phase 6 (cross-process async-lock upgrade per D-31, `pg_advisory_xact_lock`) deferred. 256/256 tests pass at ship.

**Key decisions:**
- Conversation-scoped registry (`entity_registry` table, migration 029) instead of session-scoped or global, so the same real value always maps to the same surrogate within a thread (REG-04 / FR-3.4)
- Pre-flight egress filter is the security primitive: any cloud-LLM call passes through `egress_filter()` before bytes leave the process; a registry-known PII match in the payload aborts the call
- Per-feature LLM provider overrides (entity resolution, missed-scan, fuzzy de-anon, title-gen, metadata) over a single global provider, so an admin can route privacy-sensitive auxiliary calls to the local LM Studio endpoint while keeping cheap/non-sensitive calls cloud-bound
- Off-mode (`pii_redaction_enabled=false`) is byte-identical to pre-v0.3 behavior (SC#5 invariant) — zero cost when disabled
- 3-phase de-anonymization (Pass 1 longest-surrogate-first registry lookup, Pass 2 optional Jaro-Winkler fuzzy match, Pass 3 substitution) handles slightly-mangled LLM output ("M. Smyth" → "Marcus Smith")
- Buffered SSE delivery when redaction is on (batch de-anon at end of turn) over progressive delta streaming
- Tool I/O symmetry walker (`anonymize_tool_output` / `deanonymize_tool_args`) so tool calls round-trip surrogates correctly across the LLM ↔ tool ↔ LLM boundary
- Hard-redact entity types (CREDIT_CARD, US_SSN, etc.) emit `[ENTITY_TYPE]` placeholders, never registered, never round-trippable — intentionally one-way

**Infrastructure additions:**
- 3 migrations: 029 `entity_registry` table (RLS service-role-only), 030 9 PII provider columns on `system_settings`, 031 fuzzy de-anon mode + threshold
- New service modules: `redaction/{registry, anonymization, clustering, egress, fuzzy_match, missed_scan, nicknames_id, prompt_guidance, tool_redaction, detection, name_extraction, honorifics, gender_id, uuid_filter, errors}.py`
- `LLMProviderClient` with provider-aware branching (`local` / `cloud`) and egress wrapping
- Admin UI: 14 new settings in PII section at `/admin/settings`
- `chat.py` grew 291 → 517 LOC with full privacy wiring: per-turn registry lifecycle, batched history anon, tool walker wrap, 3 egress guard sites, redaction_status SSE events

**Production deploy gotcha:** spaCy model must be downloaded at Docker build time (Dockerfile `RUN python -m spacy download xx_ent_wiki_sm` before USER switch); runtime download fails as non-root user. Procfile release hooks are ignored when Dockerfile is present. Backend deploys are manual via `railway up`, not git-push-triggered.

---

## Feature Matrix

| Feature | Status | Added In | Notes |
|---------|--------|----------|-------|
| Document ingestion (PDF, TXT, MD) | Shipped | Phase 1 | Core RAG pipeline |
| Multi-format (DOCX, CSV, HTML, JSON) | Shipped | Phase 1 | Module 5 |
| Vector search (pgvector) | Shipped | Phase 1 | Cosine similarity, IVFFlat index |
| Hybrid search (vector + full-text) | Shipped | Phase 1 | RRF fusion, configurable |
| Metadata extraction | Shipped | Phase 1 | LLM-based, best-effort |
| Content deduplication | Shipped | Phase 1 | SHA-256 hash, per-user scope |
| Chat with streaming | Shipped | Phase 1 | SSE, stateless history |
| Conversation branching | Shipped | Phase 1 | Fork at any message, branch switching |
| Tool calling (3 tools) | Shipped | Phase 2 | Doc search, SQL, web search |
| Sub-agent routing | Shipped | Phase 2 | Research, data analyst, general |
| RBAC (admin/user roles) | Shipped | Phase 3 | 3-layer enforcement |
| System settings (admin) | Shipped | Phase 3 | LLM, RAG, tool config |
| Document creation (NDA, contracts) | Shipped | Phase 4 | Bilingual, 4 doc types |
| Document comparison | Shipped | Phase 4 | Side-by-side diff, risk assessment |
| Compliance checking | Shipped | Phase 4 | OJK, GDPR, international |
| Contract analysis | Shipped | Phase 4 | Risk identification, obligations |
| Result persistence + history | Shipped | Phase 4 | Per-user, per-tool history sidebar |
| Mobile responsive | Shipped | Phase 5 | Hamburger menu, panel overlays, FABs |
| Accessibility (a11y) | Shipped | Phase 5 | Reduced motion, focus-visible |
| i18n (Indonesian + English) | Shipped | Phase 4 | Full coverage, localStorage persist |
| Clause library | Shipped | Phase 3 | Global + user-scoped, reusable in doc creation |
| Document templates | Shipped | Phase 3 | Pre-built templates with field defaults |
| Approval workflows | Shipped | Phase 3 | Admin inbox, phase progression |
| Obligation tracking | Shipped | Phase 3 | Contract obligation monitoring |
| Audit trail | Shipped | Phase 3 | All mutations logged with user/action/resource |
| User management (admin) | Shipped | Phase 3 | Active/inactive, role management |
| Regulatory intelligence | Shipped | Phase 4 | 4 Indonesian regulatory sources |
| Executive dashboard | Shipped | Phase 4 | Summary cards + trends |
| Light/dark theme | Shipped | Phase 6 | System preference detection, FOUC prevention |
| Grouped icon rail | Shipped | Phase 6 | 7 items with flyout groups (was 14) |
| BJR governance module | Shipped | Phase 7 | 25 endpoints, evidence assessment, risk register |
| Point-in-time compliance | Shipped | Phase 8 | Snapshots, timeline view, diff comparison |
| UU PDP toolkit | Shipped | Phase 8 | Data inventory, DPO, breach incidents (72h countdown) |
| Structure-aware chunking | Shipped | Phase 9 | BAB/Pasal/numbered section detection |
| Vision OCR (scanned PDFs) | Shipped | Phase 9 | GPT-4o vision, OCR metadata tracking |
| GraphRAG entity extraction | Shipped | Phase 9 | Entity/relationship graph across documents |
| Metadata pre-filtering | Shipped | Phase 9 | Tags, folder, date range filtering via LLM tool |
| Weighted RRF fusion | Shipped | Phase 9 | Admin-configurable vector/fulltext weights |
| Cohere Rerank v2 | Shipped | Phase 9 | Cross-encoder reranking (~200ms) |
| Graph re-indexing | Shipped | Phase 9 | POST endpoint for backfilling graph data |
| RAG evaluation | Shipped | Phase 9 | 20-query golden set with MRR + hit rate |
| LLM e2e pipeline | Validated | Phase 5 | Upload → embed → RAG chat → tool-calling → streaming verified |
| PII detection (Presidio) | Shipped | Phase 10 | Indonesian-aware: PERSON/EMAIL/PHONE/LOCATION/DATE/URL/IP, honorifics-stripped, UUID-pre-masked |
| PII anonymization (Faker surrogates) | Shipped | Phase 10 | Gender-matched surrogates, no-collision guard, hard-redact bucket for sensitive types |
| Conversation-scoped registry | Shipped | Phase 10 | Per-thread real↔surrogate mapping, persisted in `entity_registry` (migration 029), survives restart |
| Entity resolution (Union-Find) | Shipped | Phase 10 | Three modes: algorithmic / llm / none. Indonesian nickname dictionary, partial-name + title-stripped coreference |
| Cloud egress filter | Shipped | Phase 10 | Pre-flight regex match against registry; aborts cloud-LLM call on PII match (B4 invariant: counts/hashes only in logs) |
| Per-feature LLM provider overrides | Shipped | Phase 10 | Admin routes entity resolution / missed-scan / fuzzy de-anon / title-gen / metadata to local or cloud independently |
| Fuzzy de-anonymization | Shipped | Phase 10 | Jaro-Winkler match for slightly-mangled LLM output (e.g. "M. Smyth" → "Marcus Smith") |
| Missed-PII scan (auto-chain) | Shipped | Phase 10 | Optional secondary LLM scan re-redacts entities Presidio missed |
| Tool I/O symmetry walker | Shipped | Phase 10 | Tool args de-anonymized before execute, output anonymized after; recursive dict/list walk |
| Buffered SSE redaction status | Shipped | Phase 10 | `redaction_status:anonymizing` / `:deanonymizing` events; batched delta on turn complete |
| Cross-process async-lock | Pending | Phase 11 | D-31 upgrade: `pg_advisory_xact_lock(hashtext(thread_id))` for multi-worker correctness |

---

## Market Observations

### What Indonesian legal teams actually need (validated)
1. **Bilingual document generation** is table stakes, not a feature. Every legal document needs both Indonesian and English versions.
2. **OJK compliance** is the first framework people ask about. International and GDPR are secondary.
3. **NDA generation** is the most common use case. It is the entry point for adoption.
4. **Document comparison** for contract version tracking. Teams compare draft vs final, v1 vs v2.

### What could come next (backlog, unvalidated)
- **Collaboration** — multiple users reviewing/editing the same document
- **Export** — PDF/DOCX download of generated documents
- **API access** — programmatic document generation for integration with existing legal workflows
- **Embedding fine-tuning** — train custom embedding model from query_logs data (infrastructure ready, model TBD)
- **Query slot-filling** — extract structured filters from natural language ("Pasal 5 dari NDA bulan lalu")
- **Admin RAG dashboard** — surface retrieval quality metrics, entity counts, OCR status per document

### Previously backlogged, now shipped
- ~~Point-in-Time Compliance Querying~~ → Phase 8 (compliance snapshots)
- ~~UU PDP Compliance Toolkit~~ → Phase 8 (data inventory, DPO, breach incidents)
- ~~Audit trail~~ → Phase 3 (all mutations logged)
- ~~Knowledge graphs~~ → Phase 9 (GraphRAG entity extraction + graph reindex)

### Competitive landscape
- Generic RAG tools (no legal domain expertise, no Indonesian language)
- International legal AI (not built for Indonesian regulatory framework)
- Indonesian legal tech (mostly document management, not AI-powered generation)

**Our position:** The only AI-powered legal document workspace built specifically for Indonesian regulatory requirements with bilingual output.

---

## Technical Debt

| Item | Severity | Notes |
|------|----------|-------|
| No automated tests for frontend | Medium | Backend has 8 test files, frontend has Playwright e2e specs but no unit tests |
| No PDF/DOCX export | Medium | Generated documents are text-only, no download |
| Graph extraction duplicated | Low | `_reindex_graph_task` in documents.py mirrors ingestion_service.py graph block — could extract shared function |
| Pydantic v1 warning on Python 3.14 | Low | LangSmith compatibility, non-blocking |
| `/documents/search` vector mode bug | Low | Fixed `user_settings` → `sys_settings` but vector/fulltext modes don't expose filter params (hybrid mode does) |

---

## Version History

| Version | Date | Highlights |
|---------|------|------------|
| v2.1 | 2026-04-28 | PII Redaction System v1.0 (Phases 1-5 of 6 complete). Privacy invariant: real PII never reaches cloud-LLM payloads. Conversation-scoped registry, pre-flight egress filter, fuzzy de-anonymization, chat-loop integration. Semver `0.3.0.0`. |
| v2.0 | 2026-04-20 | RAG pipeline 8/8, Claude Code automations, CLAUDE.md 100/100, pre-ship pipeline |
| v1.3 | 2026-04-18 | Embedding fine-tuning infra, GraphRAG, vision OCR, knowledge base explorer |
| v1.2 | 2026-04-17 | Phase 3 complete (PIT compliance + UU PDP), BJR governance shipped + hardened |
| v1.1 | 2026-04-15 | 2026 design refresh, light/dark theme, grouped icon rail, visual QA passed |
| v1.0 | 2026-04-12 | Feature-complete: all modules shipped, design A/A+, mobile responsive, data cleaned |
| v0.9 | 2026-04-12 | Document tool persistence, form validation, settings/admin redesign |
| v0.8 | 2026-04-11 | Figma UI migration, document tool backend, 4 feature pages |
| v0.7 | 2026-04-10 | UI redesign (dark theme, icon rail, glassmorphism, bento grid) |
| v0.6 | 2026-04-09 | Module 10 (conversation branching) |
| v0.5 | 2026-04-08 | Module 9 (RBAC settings) + deployment (Vercel + Railway) |
| v0.4 | 2026-04-07 | Modules 7-8 (tool calling + sub-agents) |
| v0.3 | 2026-04-06 | Module 6 (hybrid search + reranking) |
| v0.2 | 2026-04-05 | Modules 3-5 (dedup, metadata, multi-format) |
| v0.1 | 2026-04-04 | Modules 1-2 (app shell, RAG pipeline, chat) |
