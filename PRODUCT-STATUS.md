# Product Status

The evolution of Knowledge Hub, from a RAG learning project to a legal document intelligence platform.

## Current Product: Knowledge Hub v1.0

**What it is:** An AI-powered legal document workspace for Indonesian professionals. Chat with your documents, generate contracts, compare versions, check compliance, and analyze risks.

**Target market:** Indonesian legal professionals, compliance officers, and business teams who work with contracts, NDAs, and regulatory documents daily.

**Status:** Feature-complete, deployed (Vercel + Railway), design-reviewed (Score A / A+).

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

### Phase 5: Design Maturity (Current)
**Period:** 2026-04-12
**Focus:** Production-grade UI/UX

Comprehensive design overhaul: mobile responsive layout, accessibility compliance, AI slop elimination, micro-interactions, unified sidebar behavior. Design Score improved from B- to A, AI Slop Score from B+ to A+.

**Key decisions:**
- Mobile-first responsive with hamburger menu + panel overlays
- Eliminated all AI slop patterns (icon circles, pulse rings, gradient borders)
- Shared sidebar collapse state across all pages (not per-page)
- Chat input pinned to bottom (matching ChatGPT/Claude pattern)
- prefers-reduced-motion support for all animations

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

---

## Market Observations

### What Indonesian legal teams actually need (validated)
1. **Bilingual document generation** is table stakes, not a feature. Every legal document needs both Indonesian and English versions.
2. **OJK compliance** is the first framework people ask about. International and GDPR are secondary.
3. **NDA generation** is the most common use case. It is the entry point for adoption.
4. **Document comparison** for contract version tracking. Teams compare draft vs final, v1 vs v2.

### What could come next (backlog, unvalidated)
- **Template library** — pre-built templates for common Indonesian legal documents
- **Clause library** — reusable clauses that can be inserted into generated documents
- **Collaboration** — multiple users reviewing/editing the same document
- **Export** — PDF/DOCX download of generated documents
- **Audit trail** — track who generated/reviewed/approved each document
- **API access** — programmatic document generation for integration with existing legal workflows
- **Knowledge graphs** — entity extraction and relationship mapping across document corpus

### Competitive landscape
- Generic RAG tools (no legal domain expertise, no Indonesian language)
- International legal AI (not built for Indonesian regulatory framework)
- Indonesian legal tech (mostly document management, not AI-powered generation)

**Our position:** The only AI-powered legal document workspace built specifically for Indonesian regulatory requirements with bilingual output.

---

## Technical Debt

| Item | Severity | Notes |
|------|----------|-------|
| No automated tests for frontend | Medium | Backend has 75+ API tests, frontend has none |
| No PDF/DOCX export | Medium | Generated documents are text-only, no download |
| Pydantic v1 warning on Python 3.14 | Low | LangSmith compatibility, non-blocking |
| Thread group headers 28px | Low | Below 44px touch target, polish item |
| Floating orbs are decorative | Low | Could be removed for cleaner look |

---

## Version History

| Version | Date | Highlights |
|---------|------|------------|
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
