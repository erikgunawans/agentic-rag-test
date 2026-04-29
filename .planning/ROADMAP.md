# Roadmap: LexCore

**Created:** 2026-04-25
**Project:** LexCore — PJAA CLM Platform
**Core Value:** Indonesian legal teams can manage the full contract lifecycle with confidence that AI outputs are accurate, citable, and traceable.

## Milestones

- ✅ **v1.0 PII Redaction System** — Phases 1–6 (shipped 2026-04-29)
- 📋 **v1.1 [Next Milestone]** — Phases TBD (not yet planned — run `/gsd-new-milestone`)

## Phases

<details>
<summary>✅ v1.0 PII Redaction System (Phases 1–6) — SHIPPED 2026-04-29</summary>

Full archive: `.planning/milestones/v1.0-ROADMAP.md`

- [x] **Phase 1: Detection & Anonymization Foundation** (7/7 plans) — completed 2026-04-26
- [x] **Phase 2: Conversation-Scoped Registry & Round-Trip** (6/6 plans) — completed 2026-04-26
- [x] **Phase 3: Entity Resolution & LLM Provider Configuration** (7/7 plans) — completed 2026-04-26
- [x] **Phase 4: Fuzzy De-anonymization, Missed-PII Scan & Prompt Guidance** (7/7 plans) — completed 2026-04-27
- [x] **Phase 5: Chat-Loop Integration (Buffering, SSE Status, Tool/Sub-Agent Coverage)** (9/9 plans) — completed 2026-04-28
- [x] **Phase 6: Embedding Provider & Production Hardening** (8/8 plans) — completed 2026-04-29

**Total:** 44 plans · 352 tests · 5 migrations (029–033) · privacy invariant enforced end-to-end

</details>

### 📋 v1.1 [Next Milestone] — Not yet planned

Next phases will be added here after running `/gsd-new-milestone`.

## Completed Phases (Pre-GSD)

The following capabilities shipped before GSD initialization. Tracked as the Validated Baseline in `.planning/milestones/v1.0-REQUIREMENTS.md` (38 requirements).

- **Chat & RAG pipeline** (CHAT-01..07, RAG-01..10) — SSE chat with hybrid retrieval (vector + fulltext + RRF + Cohere rerank), structure-aware chunking, vision OCR, bilingual query expansion, semantic cache, graph reindex, eval harness
- **Document tools** (DOC-01..04) — Create/compare/compliance/analyze via LLM; manual ingestion; folder organization
- **CLM Phase 1** (CLM1-01..06) — Clause library, templates, approvals, obligations, audit trail, user management
- **CLM Phase 2** (CLM2-01..05) — Regulatory intelligence, notifications, dashboard, Dokmee integration, Google export
- **CLM Phase 3** (CLM3-01..02) — Compliance snapshots, UU PDP toolkit
- **BJR Module** (BJR-01..02) — 25 endpoints for board decisions, evidence, risks, taxonomy admin
- **Auth & Admin** (AUTH-01..04) — Supabase Auth, RBAC, RLS, admin UI
- **Settings & Deployment** (SET-01..02, DEPLOY-01..03) — System settings cache, per-user preferences, Vercel + Railway pipeline

## Phase Numbering

- **Integer phases (1, 2, 3, …):** Planned milestone work. Numbering resets at each new milestone.
- **Decimal phases (e.g. 2.1):** Urgent insertions created via `/gsd-insert-phase`.

---
*Roadmap created: 2026-04-25*
*v1.0 milestone archived: 2026-04-29 — see `.planning/milestones/v1.0-ROADMAP.md` for full phase details*
