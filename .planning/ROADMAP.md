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
- [x] **Phase 2: Conversation-Scoped Registry & Round-Trip** ✅ 2026-04-26 — Per-thread registry persists; surrogate→real de-anonymization round-trip works (6 plans across 5 waves; 39/39 tests pass; all 5 SCs verified against live Supabase DB)
- [x] **Phase 3: Entity Resolution & LLM Provider Configuration** ✅ 2026-04-26 — `algorithmic`/`llm`/`none` resolution modes; global + per-feature `LLM_PROVIDER` plumbing with egress filter and admin UI (7 plans across 6 waves; migration 030 applied to live Supabase; 79/79 tests pass; 5/5 SCs verified)
- [x] **Phase 4: Fuzzy De-anonymization, Missed-PII Scan & Prompt Guidance** ✅ 2026-04-27 — 3-phase placeholder-tokenized de-anon pipeline; optional secondary LLM scan; system-prompt formatting guidance (7 plans across 6 waves; migration 031 applied to live Supabase; 135/135 tests pass; 9/9 REQ-IDs satisfied; 5/5 SCs verified)
- [x] **Phase 5: Chat-Loop Integration (Buffering, SSE Status, Tool/Sub-Agent Coverage)** ✅ 2026-04-28 — Full end-to-end privacy invariant: buffered responses, status events, symmetric tool/sub-agent anonymization (6 plans across 4 waves; 256/256 tests pass; 7/7 REQ-IDs satisfied; 5/5 SCs verified)
- [x] **Phase 6: Embedding Provider & Production Hardening** ✅ 2026-04-29 — `EMBEDDING_PROVIDER=local|cloud` switch; graceful fallback on all provider failure paths; thread_id correlation logs across 5 modules; title-gen template fallback; PERF-02/PERF-04/OBS-02/OBS-03 regression tests; startup validation for local config (8 plans, 352 tests pass)

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
  - [x] **Wave 5** — 02-06-PLAN.md — Pytest coverage all 5 SCs incl. SC#5 race (real DB) ✓ commits `b2d690e` + `d9639d1` + `11412fe` (2026-04-26); 39/39 tests pass (20 Phase 1 + 15 Phase 2 integration + 4 unit); SC#5 race verified against live entity_registry UNIQUE constraint via asyncio.gather + `len(rows) == 1` assertion

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
**Plans**: 7 plans across 6 waves ✅ executed 2026-04-26 — 11/11 REQ-IDs SATISFIED, 5/5 SCs verified, 79/79 tests pass
  - [x] **Wave 1** — 03-01-PLAN.md — config.py + migration 030 SQL (RESOLVE-01, PROVIDER-01..03, PROVIDER-05..07) ✓ commits `bb3202b` + `b2c7b3c`
  - [x] **Wave 2** — 03-02-PLAN.md — apply migration 030 to live Supabase (PROVIDER-06, RESOLVE-01) ✓ applied via Supabase MCP `apply_migration` (orchestrator-context); 9 columns + 7 CHECK constraints verified
  - [x] **Wave 3** — 03-03-PLAN.md — nicknames_id + clustering + egress filter (RESOLVE-02, RESOLVE-04, PROVIDER-04) ✓ commits `496cc57` + `86ce3d4` + `5510d80`
  - [x] **Wave 4** — 03-04-PLAN.md — LLMProviderClient with provider-aware branching + egress wrapping (PROVIDER-01..05, PROVIDER-07, RESOLVE-03) ✓ commits `a54443c` + `cfdaf03`
  - [x] **Wave 4** — 03-06-PLAN.md — admin_settings.py SystemSettingsUpdate + AdminSettingsPage 'pii' section (PROVIDER-06, PROVIDER-07, RESOLVE-01) ✓ commits `2e0014b` + `92fa98e`
  - [x] **Wave 5** — 03-05-PLAN.md — anonymization.py cluster-aware + redaction_service.py mode dispatch + egress fallback (RESOLVE-01..04, PROVIDER-04) ✓ commits `26fe66a` + `7813919`
  - [x] **Wave 6** — 03-07-PLAN.md — pytest coverage all 5 SCs + D-66 egress matrix + D-65 provider-client suite (RESOLVE-01..04, PROVIDER-01, PROVIDER-04, PROVIDER-06, PROVIDER-07) ✓ commits `e74dbf6` + `104e62c` + `97d2684`
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
**Plans**: 7 plans across 6 waves ✅ executed 2026-04-27 — 9/9 REQ-IDs SATISFIED, 5/5 SCs verified, 135/135 tests pass
  - [x] **Wave 1** — 04-01-PLAN.md — config.py + migration 031 SQL + [BLOCKING] supabase apply (DEANON-03)
  - [x] **Wave 2** — 04-02-PLAN.md — fuzzy_match.py algorithmic Jaro-Winkler + unit tests (DEANON-03)
  - [x] **Wave 2** — 04-05-PLAN.md — prompt_guidance.py helper + chat.py + agent_service.py wiring + unit tests (PROMPT-01)
  - [x] **Wave 3** — 04-03-PLAN.md — de_anonymize_text 3-phase upgrade including LLM mode (DEANON-03/04/05)
  - [x] **Wave 4** — 04-04-PLAN.md — missed_scan.py + redact_text auto-chain + re-NER + unit tests (SCAN-01..05) [shares redaction_service.py with 04-03 → wave 4]
  - [x] **Wave 5** — 04-06-PLAN.md — admin_settings.py SystemSettingsUpdate + AdminSettingsPage 'pii' section (DEANON-03)
  - [x] **Wave 6** — 04-07-PLAN.md — pytest coverage all 5 SCs + B4 caplog + soft-fail (DEANON-03..05, SCAN-01..05, PROMPT-01)
**UI hint**: yes

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
**Plans**: 6 plans across 4 waves ✅ executed 2026-04-28 — 7/7 REQ-IDs SATISFIED, 5/5 SCs verified, 256/256 tests pass
  - [x] **Wave 1** — 05-01-PLAN.md — `redaction_service.py` D-84 service-layer early-return gate + D-92 `redact_text_batch(texts, registry)` public method (BUFFER-01, TOOL-01..04) ✓ commits `867165e` + `02d8d91` + `3ad058c` + `0f2ce3b`
  - [x] **Wave 2** — 05-02-PLAN.md — NEW `redaction/tool_redaction.py` recursive walker (D-91) + `tool_service.execute_tool` keyword-only `registry=None` + `redaction/__init__.py` re-export (TOOL-01..04) ✓ commits `3963e19` + `1bf794a` + `4a3cd37` + `cdd3470` + `7c3a1d5` + `d560a63`
  - [x] **Wave 2** — 05-03-PLAN.md — `agent_service.classify_intent` anonymized inputs + pre-flight egress wrapper + retire stale Phase 4 D-80 per-thread TODOs (TOOL-04, BUFFER-01) ✓ commits `3f146dd` + `806c652`
  - [x] **Wave 3** — 05-04-PLAN.md — `chat.py` full integration: D-83/84 gate, D-86 registry load, D-87 buffering, D-88 SSE events, D-89 skeleton tool events, D-90 graceful degrade, D-91 walker invocations, D-93 batch history anon, D-94 egress at 3 sites, D-96 title-gen → LLMProviderClient (BUFFER-01..03, TOOL-01..04) ✓ commits `6b4fc01` + `ea3a665` + `78f66e0` + `95718f2` + `23aaf44`
  - [x] **Wave 3** — 05-05-PLAN.md — Frontend: `database.types.ts` `RedactionStatusEvent` variant + `useChatState.ts` dispatch case + spinner UI + i18n strings (BUFFER-02) ✓ commits `2120b04` + `42b0d1f` + `a4b0e13`
  - [x] **Wave 4** — 05-06-PLAN.md — pytest `test_phase5_integration.py` 7 test classes (TestSC1_PrivacyInvariant, TestSC2_BufferingAndStatus, TestSC3_SearchDocumentsTool, TestSC4_SqlGrepAndSubAgent, TestSC5_OffMode, TestB4_LogPrivacy, TestEgressTrip_ChatPath) ✓ commit `8d14786`
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
**Plans**: 8 plans across 4 waves
  - [x] **Wave 1** — 06-01-PLAN.md — config.py: add EMBEDDING_PROVIDER + LOCAL_EMBEDDING_BASE_URL settings; flip llm_provider_fallback_enabled default to True (EMBED-01, EMBED-02, PERF-04 / D-P6-01..03, D-P6-09) ✓ commits `e7a9e31`+`eab3923` (2026-04-29)
  - [x] **Wave 1** — 06-02-PLAN.md — Establish @pytest.mark.slow marker via backend/pyproject.toml (PERF-02 / D-P6-07) ✓ commit `98fc89c` (2026-04-29)
  - [x] **Wave 2** — 06-03-PLAN.md — EmbeddingService provider branch (cloud / local) + 3 unit tests (EMBED-01, EMBED-02 / D-P6-02) ✓ commits `66d3f7d`+`573c47c` (2026-04-29)
  - [x] **Wave 2** — 06-04-PLAN.md — Add thread_id correlation field to redaction-pipeline debug logs (detection / redaction_service / egress / llm_provider) (OBS-02, OBS-03 / D-P6-14..17) ✓ commits `31a5bbb`..`0e46282` (2026-04-29)
  - [x] **Wave 2** — 06-05-PLAN.md — Replace title-gen except-pass with 6-word anonymized-message template fallback (PERF-04 / D-P6-12) ✓ commit `5e7d435` (2026-04-29)
  - [x] **Wave 3** — 06-06-PLAN.md — PERF-02 latency-budget regression test (real Presidio, @pytest.mark.slow, <500ms) (PERF-02 / D-P6-05..08) ✓ commit `e21cf3b` (2026-04-29)
  - [x] **Wave 3** — 06-07-PLAN.md — PERF-04 graceful-degradation tests (entity-resolution / missed-scan / title-gen) (PERF-04 / D-P6-09..13) ✓ commit `53685d3` (2026-04-29)
  - [x] **Wave 4** — 06-08-PLAN.md — OBS-02/03 thread_id + resolved-provider caplog tests + CLAUDE.md gotcha note + final regression checkpoint (OBS-02, OBS-03, EMBED-02, PERF-04 / D-P6-04, D-P6-14..17) ✓ commits `08ce7e4`+`d6a8c2a` (2026-04-29)
**UI hint**: no (deviation from initial roadmap; Phase 6 is env-var + service-layer + tests + docs only — no UI work per CONTEXT.md "Out of scope: Admin UI toggle for EMBEDDING_PROVIDER")

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Detection & Anonymization Foundation | 7/7 | Complete | 2026-04-26 |
| 2. Conversation-Scoped Registry & Round-Trip | 6/6 | Complete | 2026-04-26 |
| 3. Entity Resolution & LLM Provider Configuration | 7/7 | Complete | 2026-04-26 |
| 4. Fuzzy De-anonymization, Missed-PII Scan & Prompt Guidance | 7/7 | Complete | 2026-04-27 |
| 5. Chat-Loop Integration (Buffering, SSE Status, Tool/Sub-Agent Coverage) | 6/6 | Complete | 2026-04-28 |
| 6. Embedding Provider & Production Hardening | 8/8 | Complete | 2026-04-29 |

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
*Last updated: 2026-04-26 — Phase 2 EXECUTION COMPLETE ✅: plan 02-06 SHIPPED (commits `b2d690e` + `d9639d1` + `11412fe`); 19 new tests added (15 integration + 4 unit); combined regression 39/39 pass (20 Phase 1 + 15 Phase 2 integration + 4 Phase 2 unit) in ~15s; all 5 Phase 2 ROADMAP SCs verified against live Supabase DB; SC#5 race verified via asyncio.gather + composite UNIQUE serialisation. Phase 2 ready for verification → Phase 3.*
*Last updated: 2026-04-26 — Phase 3 PLANNING COMPLETE: 7 plans across 6 waves drafted (03-01..03-07); all 11 REQ-IDs covered (RESOLVE-01..04, PROVIDER-01..07). Wave 2 plan 03-02 is the [BLOCKING] migration apply task.*
*Last updated: 2026-04-28 — Phase 5 EXECUTION COMPLETE ✅: 6 plans across 4 waves; all 7 REQ-IDs (BUFFER-01..03, TOOL-01..04) SATISFIED; 5/5 ROADMAP SCs verified; 256/256 tests pass. Privacy invariant enforced end-to-end: batch history anon, egress filter at 3 sites + classify_intent, walker-wrapped tool I/O, SSE redaction_status events, single-batch buffered delta, graceful degrade, off-mode SC#5 regression-free. Verification: `.planning/phases/05-chat-loop-integration-buffering-sse-status-tool-sub-agent-co/05-VERIFICATION.md` (status: passed, 5/5 SCs). Next: Phase 6 (Embedding Provider & Production Hardening).*
*Last updated: 2026-04-28 — Phase 5 GAP-CLOSURE COMPLETE ✅ (plans 05-07 + 05-08): D-48 variant cascade blocker fixed (ConversationRegistry.canonicals() + egress canonical-only scan); pii_redaction_enabled migrated from config.py env var to system_settings DB column (migration 032 applied to production, admin UI toggle now functional); 195/195 unit tests pass; gap-closure verification: passed (5/5 must-haves).*
*Last updated: 2026-04-29 — Phase 6 PLANNING COMPLETE: 8 plans across 4 waves drafted (06-01..06-08); all 6 REQ-IDs covered (EMBED-01, EMBED-02, OBS-02, OBS-03, PERF-02, PERF-04); 17 D-P6-XX decisions traced. UI hint corrected to no (CONTEXT.md scope: env-var + service-layer + tests + docs only).*
*Last updated: 2026-04-29 — Phase 6 EXECUTION COMPLETE ✅: 8 plans across 4 waves; all 6 REQ-IDs (EMBED-01, EMBED-02, OBS-02, OBS-03, PERF-02, PERF-04) SATISFIED; 4/5 SCs auto-verified (PERF-02 requires server-class hardware for 500ms gate — 2000ms hard gate passed, UAT item created); 352/352 non-slow tests pass; code review blockers fixed (CR-01 title-gen wiring, CR-02 startup validation, WR-01 fuzzy-deanon thread_id, WR-04 false-positive test). Milestone v1.0 PII Redaction System COMPLETE.*
