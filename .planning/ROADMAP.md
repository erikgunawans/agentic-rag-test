# Roadmap: LexCore

**Created:** 2026-04-25
**Project:** LexCore — PJAA CLM Platform
**Core Value:** Indonesian legal teams can manage the full contract lifecycle with confidence that AI outputs are accurate, citable, and traceable.

> **Brownfield baseline + first GSD milestone.** Validated baseline (38 requirements) shipped pre-GSD and is preserved under "Completed Phases (Pre-GSD)" below. Milestone v1.0 (PII Redaction System) is the first GSD-managed milestone; phases 1–6 below derive from the 54 v1.0 REQ-IDs in `REQUIREMENTS.md`.

## Active Phases

**Milestone:** v1.0 — PII Redaction System
**Source PRD:** [`docs/PRD-PII-Redaction-System-v1.1.md`](../docs/PRD-PII-Redaction-System-v1.1.md)
**Privacy invariant:** No raw PII reaches cloud chat / auxiliary LLM providers. Cloud auxiliary calls (entity resolution, missed-scan, fuzzy de-anon, title generation, metadata extraction) only ever see surrogate-form data.

### Phases (summary)

- [x] **Phase 1: Detection & Anonymization Foundation** ✅ 2026-04-26 — Presidio NER + Faker surrogates wired in as lazy singletons with tracing (21 commits, 20/20 tests pass, 5/5 SCs verified)
- [ ] **Phase 2: Conversation-Scoped Registry & Round-Trip** — Per-thread registry persists; basic surrogate→real de-anonymization round-trip works
- [ ] **Phase 3: Entity Resolution & LLM Provider Configuration** — `algorithmic`/`llm`/`none` resolution modes; global + per-feature `LLM_PROVIDER` plumbing with egress filter and admin UI
- [ ] **Phase 4: Fuzzy De-anonymization, Missed-PII Scan & Prompt Guidance** — 3-phase placeholder-tokenized de-anon pipeline; optional secondary LLM scan; system-prompt formatting guidance
- [ ] **Phase 5: Chat-Loop Integration (Buffering, SSE Status, Tool/Sub-Agent Coverage)** — Full end-to-end privacy invariant: buffered responses, status events, symmetric tool/sub-agent anonymization
- [ ] **Phase 6: Embedding Provider & Production Hardening** — `EMBEDDING_PROVIDER=local|cloud`; latency target met; graceful provider-failure degradation; full audit logging

## Phase Details

### Phase 1: Detection & Anonymization Foundation
**Goal:** Ship the always-on detection-and-substitution layer so any text passing through the new redaction service yields realistic, gender-matched, collision-free surrogates without leaking real values into logs.
**Depends on:** Nothing (first phase of the milestone).
**Requirements:** PII-01, PII-02, PII-03, PII-04, PII-05, ANON-01, ANON-02, ANON-03, ANON-04, ANON-05, ANON-06, PERF-01, OBS-01
**Success Criteria** (what must be TRUE):
  1. Calling the new redaction service on a representative Indonesian legal paragraph returns text where every detected PERSON / EMAIL / PHONE / LOCATION / DATE / URL is replaced with a Faker-generated surrogate, while hard-redact entity types appear as `[ENTITY_TYPE]` placeholders.
  2. Two-pass NER thresholds are honoured — `PII_SURROGATE_SCORE_THRESHOLD=0.7` and `PII_REDACT_SCORE_THRESHOLD=0.3` (and the bucket env vars `PII_SURROGATE_ENTITIES` / `PII_REDACT_ENTITIES`) take effect without restarting per-call processing.
  3. A document-ID lookalike string (UUID segment) inside chat input is NOT redacted; tool calls that pass UUIDs continue to work end-to-end.
  4. Person-name surrogates are gender-matched (female-original yields female surrogate when gender is detectable; ambiguous originals fall back to random) and never reuse a real surname or first name from the same input batch.
  5. A backend cold-start loads Presidio NER, gender-detection model, and the nickname dictionary exactly once (lazy-singleton); subsequent redaction calls reuse them, and every call appears as a span in the configured tracing provider (`TRACING_PROVIDER=langsmith` or `langfuse`).
**Plans**: 01-01..01-07 ✅ executed 2026-04-26 (21 commits `8d06ffe`..`0857bb2`; 20/20 tests pass)

### Phase 2: Conversation-Scoped Registry & Round-Trip
**Goal:** Ship the conversation-scoped real↔surrogate registry so the same real entity always maps to the same surrogate within a thread, the mapping survives a thread reload, and surrogates round-trip back to real values for user display.
**Depends on:** Phase 1 (NER + anonymization must produce stable surrogates before they can be stored).
**Requirements:** REG-01, REG-02, REG-03, REG-04, REG-05, DEANON-01, DEANON-02, PERF-03
**Success Criteria** (what must be TRUE):
  1. Within a single thread, mentioning the same real person, email, or phone number twice (in different casings) yields the **same** surrogate both times; the registry exposes case-insensitive lookups.
  2. Closing a thread, restarting the backend, and resuming the thread produces identical surrogates for previously-seen entities (registry persisted to DB and reloaded on resume).
  3. Surrogates emitted by the LLM in any letter-case round-trip back to the original real values before user-facing display (e.g. `John.Doe@example.com` → original `john.doe@example.com`).
  4. Hard-redacted placeholders (`[CREDIT_CARD]`, `[US_SSN]`, …) never appear as keys in the registry — they are intentionally one-way.
  5. Two simultaneous chat requests on the same thread that introduce the same new entity produce a single registry row (no duplicate surrogates, no race) — verified by an async-lock contention test.
**Plans**: 6 plans across 5 waves
  - [x] **Wave 1** — 02-01-PLAN.md — Migration 029 entity_registry table (REG-01..05) ✓ commit `f7a3ff5` (2026-04-26)
  - [x] **Wave 1** — 02-02-PLAN.md — ConversationRegistry + EntityMapping skeleton (REG-01..05) ✓ commit `26cf393` (2026-04-26)
  - [x] **Wave 2** — 02-03-PLAN.md — [BLOCKING] supabase db push migration 029 ✓ applied via Supabase MCP `apply_migration` (2026-04-26) — local CLI absent
  - [x] **Wave 3** — 02-04-PLAN.md — Registry DB methods (load / upsert_delta) + reexports ✓ commits `abe7c55` + `865cec2` (2026-04-26); 20/20 Phase 1 regression pass; live load() smoke against real DB succeeded
  - [x] **Wave 4** — 02-05-PLAN.md — redaction_service wiring (locks, redact_text widening, de_anonymize_text) ✓ commits `d0b8dc3` + `9cc1f42` (2026-04-26); 20/20 Phase 1 regression pass; round-trip + hard-redact-passthrough + case-insensitive smoke tests pass
  - [ ] **Wave 5** — 02-06-PLAN.md — Pytest coverage all 5 SCs incl. SC#5 race (real DB)

### Phase 3: Entity Resolution & LLM Provider Configuration
**Goal:** Ship the three entity-resolution modes (`algorithmic` / `llm` / `none`) on top of a configurable LLM-provider abstraction, so PERSON-entity coreference (nicknames, partial names, title-stripped variants) collapses to one canonical surrogate, and any cloud auxiliary call is gated by a pre-flight egress filter.
**Depends on:** Phases 1–2 (resolution operates on detected entities and writes into the per-thread registry).
**Requirements:** RESOLVE-01, RESOLVE-02, RESOLVE-03, RESOLVE-04, PROVIDER-01, PROVIDER-02, PROVIDER-03, PROVIDER-04, PROVIDER-05, PROVIDER-06, PROVIDER-07
**Success Criteria** (what must be TRUE):
  1. With `ENTITY_RESOLUTION_MODE=algorithmic`, mentions of "Bambang Sutrisno", "Pak Bambang", "Sutrisno", and the nickname "Bambang" within one conversation collapse to a single canonical surrogate via Union-Find clustering with the three documented merge rules.
  2. With `ENTITY_RESOLUTION_MODE=llm` + `ENTITY_RESOLUTION_LLM_PROVIDER=cloud`, the cloud LLM only ever sees provisional surrogates from algorithmic pre-clustering; the pre-flight egress filter aborts the call (and the test passes) when a real value would have leaked, and the call falls back to algorithmic clustering on any provider failure.
  3. With `ENTITY_RESOLUTION_MODE=llm` + provider=`local`, the local OpenAI-compatible endpoint (LM Studio / Ollama) operates on raw real content with no third-party egress.
  4. Non-PERSON entities (emails, phones, URLs) use exact-match normalization and are never sent to the resolution LLM.
  5. An admin can switch `LLM_PROVIDER` and any per-feature override (`ENTITY_RESOLUTION_LLM_PROVIDER`, `MISSED_SCAN_LLM_PROVIDER`, `TITLE_GEN_LLM_PROVIDER`, `METADATA_LLM_PROVIDER`, `FUZZY_DEANON_LLM_PROVIDER`) from the admin settings UI; changes take effect within the 60s `system_settings` cache window without redeploy.
**Plans**: TBD
**UI hint**: yes

### Phase 4: Fuzzy De-anonymization, Missed-PII Scan & Prompt Guidance
**Goal:** Ship the production-grade de-anonymization pipeline (placeholder-tokenized 3-phase) with optional fuzzy and LLM-driven missed-PII passes, plus the system-prompt guidance that keeps surrogates verbatim through model output.
**Depends on:** Phase 3 (fuzzy LLM mode and missed-PII LLM mode both consume the provider abstraction; algorithmic fuzzy mode and the prompt change are provider-agnostic).
**Requirements:** DEANON-03, DEANON-04, DEANON-05, SCAN-01, SCAN-02, SCAN-03, SCAN-04, SCAN-05, PROMPT-01
**Success Criteria** (what must be TRUE):
  1. A response containing a slightly-mangled surrogate (e.g. surname dropped, casing flipped, one-character typo) is correctly de-anonymized to the real value when `FUZZY_DEANON_MODE=algorithmic` (Jaro-Winkler ≥ 0.85) or `FUZZY_DEANON_MODE=llm`; with `none`, the mangled surrogate passes through unchanged.
  2. The 3-phase placeholder-tokenized pipeline (replace surrogates → fuzzy-match on placeholders → resolve placeholders) prevents surname-collision corruption — verified by a test where two surrogates share a surname component and only the correct one is resolved.
  3. Hard-redacted `[ENTITY_TYPE]` placeholders survive de-anonymization unchanged in every mode.
  4. With `PII_MISSED_SCAN_ENABLED=true`, the secondary LLM scan runs across all three resolution modes; any entities it returns are validated against the configured hard-redact set (invalid types discarded), and when it does replace text the primary NER engine re-runs to recompute surrogate positions.
  5. The main-agent system prompt instructs the LLM to reproduce names, emails, phones, locations, dates, and URLs verbatim; an end-to-end test shows the LLM emits surrogates in their exact source format (no abbreviation, no reformatting) on a representative legal-Q&A turn.
**Plans**: TBD

### Phase 5: Chat-Loop Integration (Buffering, SSE Status, Tool/Sub-Agent Coverage)
**Goal:** Ship the end-to-end chat-loop wiring so a real chat round-trip preserves the privacy invariant — full response buffering when redaction is active, `redaction_status` SSE events for UX, and symmetric anonymize-input / de-anonymize-output coverage across every tool and sub-agent.
**Depends on:** Phases 1–4 (this phase composes the full pipeline through the existing `chat.py` + `ToolService` + sub-agent paths).
**Requirements:** BUFFER-01, BUFFER-02, BUFFER-03, TOOL-01, TOOL-02, TOOL-03, TOOL-04
**Success Criteria** (what must be TRUE):
  1. A chat turn that mentions a real PERSON, EMAIL, and PHONE produces an answer in which the user sees the **real** values, while every recorded LLM request payload (chat + auxiliary) and every LangSmith / Langfuse span shows **only surrogates** — verified by a privacy-invariant assertion test on the captured trace.
  2. While redaction is active, the frontend receives `redaction_status` SSE events with `stage: anonymizing` and `stage: deanonymizing`; the cloud LLM's response is fully buffered and emitted to the user as a single de-anonymized batch (sub-agent reasoning events suppressed).
  3. A `search_documents` call whose query mentions a registered surrogate runs against the index using the **real** value (de-anonymized before search) and returns results that are re-anonymized before the LLM sees them.
  4. A `query_database` (SQL) tool call and a text-search/grep tool call both exhibit the same symmetric pattern (de-anon input → execute → re-anon output) and a sub-agent invocation (document analyzer / KB explorer / nested explorer→sub-agent) shares the parent's redaction-service instance with no double-anonymization.
  5. With redaction disabled (`PII_REDACTION_ENABLED=false`), chat reverts to normal SSE streaming with no buffering, no status events, and no behavioural regression versus the pre-milestone baseline.
**Plans**: TBD
**UI hint**: yes

### Phase 6: Embedding Provider & Production Hardening
**Goal:** Ship the `EMBEDDING_PROVIDER` switch, the v1.0 latency target, the graceful provider-failure degradation paths, and the full debug + audit logging — closing out the milestone with a production-ready, observable, resilient redaction system.
**Depends on:** Phases 1–5 (hardening targets the integrated system; embedding-provider config is independent of chat-time redaction but ships with this milestone).
**Requirements:** EMBED-01, EMBED-02, OBS-02, OBS-03, PERF-02, PERF-04
**Success Criteria** (what must be TRUE):
  1. Setting `EMBEDDING_PROVIDER=cloud` (default) preserves the existing OpenAI-embeddings flow (RAG-02 unchanged); setting `EMBEDDING_PROVIDER=local` with an OpenAI-API-compatible local endpoint (e.g. `bge-m3` via Ollama) lets the deployer ingest **new** documents without third-party egress, and switching providers does NOT trigger automatic re-embedding of existing documents.
  2. Anonymization completes in under 500 ms for a typical chat message (< 2000 tokens) — measured by a latency-budget regression test on the redaction service.
  3. When the configured `LLM_PROVIDER` is unavailable: entity resolution falls back to algorithmic clustering, the missed-PII scan is skipped, and title/metadata generation falls back to a templated default — failures are logged but never crash the chat loop and never leak raw PII.
  4. Debug-level logs capture (per redaction operation) entities detected, surrogates assigned, fuzzy matches, missed-PII scan results, UUID-filter drops, the resolved LLM provider per call, and pre-flight egress-filter results for cloud calls — all verifiable by inspecting a single chat turn's log block.
  5. Every LLM call records its **resolved** provider (after per-feature override resolution) for audit, and the production smoke-test suite extends to a full anonymize → resolve → buffer → de-anonymize round-trip without raw-PII leakage.
**Plans**: TBD
**UI hint**: yes

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Detection & Anonymization Foundation | 0/0 | Not started | — |
| 2. Conversation-Scoped Registry & Round-Trip | 4/6 | In progress | — |
| 3. Entity Resolution & LLM Provider Configuration | 0/0 | Not started | — |
| 4. Fuzzy De-anonymization, Missed-PII Scan & Prompt Guidance | 0/0 | Not started | — |
| 5. Chat-Loop Integration (Buffering, SSE Status, Tool/Sub-Agent Coverage) | 0/0 | Not started | — |
| 6. Embedding Provider & Production Hardening | 0/0 | Not started | — |

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

Milestone v1.0 phase numbering starts at **Phase 1** (workflow flag `--reset-phase-numbers` active for the first GSD milestone). Subsequent milestones may continue numbering from the prior milestone's last phase unless `--reset-phase-numbers` is passed again.

- **Integer phases (1, 2, 3, …):** Planned milestone work.
- **Decimal phases (e.g. 2.1, 2.2):** Urgent insertions after planning, created via `/gsd-insert-phase`.

## Coverage

- Validated Baseline (Pre-GSD): 38 requirements ✓
- Active milestone phases (v1.0): **6**
- v1.0 requirements mapped: **54 / 54** ✓
  - Phase 1 — 13 (PII-01..05, ANON-01..06, PERF-01, OBS-01)
  - Phase 2 — 8 (REG-01..05, DEANON-01..02, PERF-03)
  - Phase 3 — 11 (RESOLVE-01..04, PROVIDER-01..07)
  - Phase 4 — 9 (DEANON-03..05, SCAN-01..05, PROMPT-01)
  - Phase 5 — 7 (BUFFER-01..03, TOOL-01..04)
  - Phase 6 — 6 (EMBED-01..02, OBS-02..03, PERF-02, PERF-04)
- Orphaned / unmapped: 0 ✓
- Duplicates (REQ-ID in multiple phases): 0 ✓

---
*Roadmap created: 2026-04-25 (brownfield baseline)*
*Last updated: 2026-04-26 — Phase 2 plan list re-waved (Plan 05 → Wave 4, Plan 06 → Wave 5) following revision iter 1 of `/gsd-plan-phase`*
*Last updated: 2026-04-26 — Phase 2 plan 02-01 SHIPPED ✓ (commit `f7a3ff5`); migration 029 entity_registry table written to disk*
*Last updated: 2026-04-26 — Phase 2 plan 02-02 SHIPPED ✓ (commit `26cf393`); ConversationRegistry + EntityMapping skeleton (127 lines, no DB methods); Wave 1 complete; ready for Wave 2 (02-03 supabase db push)*
*Last updated: 2026-04-26 — Phase 2 plan 02-04 SHIPPED ✓ (commits `abe7c55` + `865cec2`); ConversationRegistry.load + upsert_delta wired to live entity_registry table; ConversationRegistry + EntityMapping re-exported from `app.services.redaction` (de_anonymize_text deliberately NOT re-exported per D-39 option b); 20/20 Phase 1 regression pass; live load() smoke succeeded; Wave 3 complete; ready for Wave 4 (02-05 redaction_service wiring)*
</content>
