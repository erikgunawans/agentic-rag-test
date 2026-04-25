# Roadmap: LexCore

**Created:** 2026-04-25
**Project:** LexCore — PJAA CLM Platform
**Core Value:** Indonesian legal teams can manage the full contract lifecycle with confidence that AI outputs are accurate, citable, and traceable.

> **Brownfield baseline.** This file initializes empty. The next milestone (`/gsd-new-milestone`) will spawn the roadmapper to derive phases from milestone-scoped REQ-IDs in REQUIREMENTS.md and append them here.

## Active Phases

<!-- Filled by /gsd-new-milestone via the gsd-roadmapper agent. -->

(None yet — awaiting `/gsd-new-milestone` to define the next milestone's scope and derive phases.)

## Completed Phases (Pre-GSD)

The following capabilities shipped before GSD initialization. They are tracked as the Validated Baseline in `REQUIREMENTS.md` (38 requirements). They were not produced via GSD phases, so they have no per-phase plan, success criteria, or verification artifacts here — refer to `git log` and PROGRESS.md for shipment history.

- **Chat & RAG pipeline** (CHAT-01..07, RAG-01..10) — SSE chat with hybrid retrieval (vector + fulltext + RRF + Cohere rerank), structure-aware chunking, vision OCR, bilingual query expansion, semantic cache, graph reindex, eval harness
- **Document tools** (DOC-01..04) — Create/compare/compliance/analyze via LLM with Pydantic validation; manual ingestion; folder organization (private + global)
- **CLM Phase 1** (CLM1-01..06) — Clause library, document templates, approvals, obligations, audit trail, user management
- **CLM Phase 2** (CLM2-01..05) — Regulatory intelligence, notifications, dashboard, Dokmee integration, Google export
- **CLM Phase 3** (CLM3-01..02) — Compliance snapshots, UU PDP toolkit
- **BJR Module** (BJR-01..02) — 25 endpoints for board decisions, evidence, risks, taxonomy admin
- **Auth & Admin** (AUTH-01..04) — Supabase Auth, RBAC, RLS, admin UI
- **Settings** (SET-01..02) — System settings cache, per-user preferences
- **Deployment** (DEPLOY-01..03) — Vercel + Railway pipeline, smoke tests

## Phase Numbering

GSD-managed phases will start at **Phase 1** under the next milestone (`/gsd-new-milestone`). Each milestone continues phase numbering from the prior milestone's last phase unless `--reset-phase-numbers` is passed.

## Coverage

- Validated Baseline (Pre-GSD): 38 requirements ✓
- Active milestone phases: 0 (awaiting milestone definition)
- Total v1 requirements mapped: N/A — to be tracked when first milestone is defined

---
*Roadmap created: 2026-04-25 (brownfield baseline)*
*Last updated: 2026-04-25*
