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

<!-- Active scope for milestone v1.0 — PII Redaction System.
     Source PRD: docs/PRD-PII-Redaction-System-v1.1.md -->

**Milestone v1.0:** PII Redaction System
**Goal:** Ensure real PII never reaches cloud chat / auxiliary LLM providers while keeping the user experience transparent — anonymize on-the-fly at chat-time, de-anonymize before display. Embeddings remain configurable (local or cloud) with documented tradeoff.

### PII Detection (PII-*)

- [ ] **PII-01**: System detects 16 PII entity types via Presidio NER — PERSON, EMAIL_ADDRESS, PHONE_NUMBER, LOCATION, DATE_TIME, URL, IP_ADDRESS, CREDIT_CARD, US_SSN, US_ITIN, US_BANK_NUMBER, IBAN_CODE, CRYPTO, US_PASSPORT, US_DRIVER_LICENSE, MEDICAL_LICENSE *(PRD FR-1.1)*
- [ ] **PII-02**: System runs two-pass NER detection — high threshold (0.7) for surrogate entities, low threshold (0.3) for hard-redact entities *(FR-1.2)*
- [ ] **PII-03**: System loads entity-type bucket configuration from env vars `PII_SURROGATE_ENTITIES` and `PII_REDACT_ENTITIES` *(FR-1.3)*
- [ ] **PII-04**: System filters NER results to exclude UUID-segment false positives so document-ID corruption never breaks tool calls *(FR-1.4)*
- [ ] **PII-05**: System exposes detection thresholds as configurable env vars `PII_SURROGATE_SCORE_THRESHOLD` and `PII_REDACT_SCORE_THRESHOLD` *(FR-1.5)*

### Anonymization (ANON-*)

- [ ] **ANON-01**: System replaces surrogate-bucket entities with realistic Faker-generated values *(FR-2.1)*
- [ ] **ANON-02**: System replaces hard-redact-bucket entities with irreversible `[ENTITY_TYPE]` placeholders *(FR-2.2)*
- [ ] **ANON-03**: System guarantees collision-free surrogate generation against existing real values and existing surrogates in the registry *(FR-2.3)*
- [ ] **ANON-04**: System gender-matches person-name surrogates via gender detection (female-original → female-surrogate, fallback to random for ambiguous) *(FR-2.4)*
- [ ] **ANON-05**: System cross-checks surrogate surnames so no Faker-generated name component reuses a real surname or first name within the conversation *(FR-2.5)*
- [ ] **ANON-06**: System performs anonymization via programmatic find-and-replace (never via LLM-generated rewrite) *(FR-2.6)*

### Conversation-Scoped Entity Registry (REG-*)

- [ ] **REG-01**: System maintains one entity registry per conversation/thread (no cross-conversation sharing) *(FR-3.1)*
- [ ] **REG-02**: System persists the registry to the database and reloads it when a conversation is resumed *(FR-3.2)*
- [ ] **REG-03**: Registry lookups are case-insensitive *(FR-3.3)*
- [ ] **REG-04**: Within a conversation, the same real entity always produces the same surrogate (consistency guarantee) *(FR-3.4)*
- [ ] **REG-05**: Hard-redacted entities are NOT stored in the registry *(FR-3.5)*

### Entity Resolution (RESOLVE-*)

- [ ] **RESOLVE-01**: System supports three entity-resolution modes via `ENTITY_RESOLUTION_MODE`: `algorithmic`, `llm`, `none` *(FR-4.1)*
- [ ] **RESOLVE-02**: Algorithmic mode parses names, resolves nicknames, applies Union-Find clustering with three merge rules, and derives sub-surrogates *(FR-4.2)*
- [ ] **RESOLVE-03**: LLM mode supports both local and cloud providers via `LLM_PROVIDER` (cloud receives only provisional surrogates from algorithmic pre-clustering; pre-flight egress assertion before any cloud call; falls back to algorithmic on failure) *(FR-4.3.1, FR-4.3.2, FR-4.3.3)*
- [ ] **RESOLVE-04**: Entity resolution applies only to PERSON entities; other types use exact-match normalization (lowercase emails, normalized phones, lowercase URLs, etc.) *(FR-4.4)*

### De-Anonymization (DEANON-*)

- [ ] **DEANON-01**: System replaces surrogates back to real values before user-facing display *(FR-5.1)*
- [ ] **DEANON-02**: De-anonymization uses case-insensitive matching to handle LLM case-reformatting *(FR-5.2)*
- [ ] **DEANON-03**: Fuzzy de-anonymization runs in three modes — algorithmic (Jaro-Winkler ≥ 0.85), LLM (provider follows `LLM_PROVIDER`), or none *(FR-5.3)*
- [ ] **DEANON-04**: De-anonymization uses a placeholder-tokenized 3-phase pipeline (replace surrogates → fuzzy-match on placeholders → resolve placeholders) to prevent surname-collision corruption *(FR-5.4)*
- [ ] **DEANON-05**: Hard-redacted placeholders survive de-anonymization unchanged *(FR-5.5)*

### Response Buffering & SSE (BUFFER-*)

- [ ] **BUFFER-01**: When redaction is active, the cloud LLM's response is fully buffered before de-anonymization and delivery *(FR-6.1)*
- [ ] **BUFFER-02**: System emits SSE `redaction_status` events (`stage: anonymizing` and `stage: deanonymizing`) so the frontend can show progress *(FR-6.2)*
- [ ] **BUFFER-03**: Sub-agent reasoning events are suppressed during generation when redaction is active; the de-anonymized result is emitted as a single batch on completion *(FR-6.3)*

### System-Prompt Guidance (PROMPT-*)

- [ ] **PROMPT-01**: Main agent system prompt instructs the LLM to reproduce names, emails, phone numbers, locations, dates/times, and URLs in their exact source format (no abbreviation, no reformatting) *(FR-7.1)*

### Missed-PII Secondary Scan (SCAN-*)

- [ ] **SCAN-01**: System supports an optional secondary LLM-based scan over already-anonymized text, gated by `PII_MISSED_SCAN_ENABLED` *(FR-8.1)*
- [ ] **SCAN-02**: The missed-PII scan runs across all entity-resolution modes (algorithmic, LLM, none) when enabled *(FR-8.2)*
- [ ] **SCAN-03**: The scan provider follows the global `LLM_PROVIDER` setting; cloud-mode calls run through the same pre-flight egress filter *(FR-8.3)*
- [ ] **SCAN-04**: System validates missed entities against the configured hard-redact set; invalid types are discarded *(FR-8.4)*
- [ ] **SCAN-05**: When missed entities are replaced, the primary NER engine re-runs to recalculate surrogate positions on the modified text *(FR-8.5)*

### LLM Provider Configuration (PROVIDER-*)

- [ ] **PROVIDER-01**: System exposes a global `LLM_PROVIDER` (`local` | `cloud`) for entity resolution, missed-PII scan, fuzzy de-anonymization, title generation, and metadata extraction *(FR-9.1)*
- [ ] **PROVIDER-02**: Local-provider mode uses `LOCAL_LLM_BASE_URL` and `LOCAL_LLM_MODEL`; auxiliary calls operate on raw real content (no third-party egress) *(FR-9.2)*
- [ ] **PROVIDER-03**: Cloud-provider mode uses `CLOUD_LLM_BASE_URL` / `CLOUD_LLM_MODEL` / `CLOUD_LLM_API_KEY` (secret-managed); auxiliary calls operate on pre-anonymized data only; outputs are de-anonymized locally *(FR-9.3)*
- [ ] **PROVIDER-04**: Every cloud LLM request passes through a pre-flight egress filter that scans the payload against the conversation registry and aborts on any real-value match *(FR-9.3, NFR-2)*
- [ ] **PROVIDER-05**: Both providers use OpenAI-compatible APIs (`/v1/chat/completions`); local works with LM Studio / Ollama, cloud with OpenAI / Together.ai / similar *(FR-9.4)*
- [ ] **PROVIDER-06**: Configuration is available through both env vars and the admin settings API/UI *(FR-9.5)*
- [ ] **PROVIDER-07**: System supports per-feature provider overrides — `ENTITY_RESOLUTION_LLM_PROVIDER`, `MISSED_SCAN_LLM_PROVIDER`, `TITLE_GEN_LLM_PROVIDER`, `METADATA_LLM_PROVIDER`, `FUZZY_DEANON_LLM_PROVIDER` — each falling back to the global `LLM_PROVIDER` *(FR-9.6)*

### Tool-Call & Sub-Agent Coverage (TOOL-*)

- [ ] **TOOL-01**: Document search tool — LLM-generated query (with surrogates) is de-anonymized before search; results are anonymized before returning to the LLM *(PRD §3.4)*
- [ ] **TOOL-02**: SQL-query tool — query is de-anonymized before execution; results are anonymized before returning to the LLM *(PRD §3.4)*
- [ ] **TOOL-03**: Text-search/grep tool — search pattern is de-anonymized before execution; results are anonymized in the next chat-loop iteration *(PRD §3.4)*
- [ ] **TOOL-04**: Sub-agents (document analyzer, knowledge-base explorer, nested explorer→sub-agent) — share the parent's redaction-service instance; thread tool-arg de-anonymization and result re-anonymization through nested invocations; revert to normal streaming when redaction is off *(PRD §3.5)*

### Embedding Provider Configuration (EMBED-*)

- [ ] **EMBED-01**: System supports `EMBEDDING_PROVIDER=local|cloud`; default `cloud` preserves the existing OpenAI-embeddings flow (RAG-02) *(NEW for v1.0 — deviation from PRD §3.2; logged in PROJECT.md Key Decisions)*
- [ ] **EMBED-02**: Local embedding mode supports an OpenAI-API-compatible local endpoint (e.g., bge-m3 / nomic-embed-text via Ollama or LM Studio); the deployer-managed migration to local does NOT trigger automatic re-embedding of existing documents *(NEW for v1.0)*

### Observability & Tracing (OBS-*)

- [ ] **OBS-01**: All redaction operations are traced via the application's observability provider, switchable via `TRACING_PROVIDER` env var (`langsmith`, `langfuse`, or empty) *(NFR-4)*
- [ ] **OBS-02**: Debug-level logs capture entities detected, surrogates assigned, fuzzy matches found, missed-PII scan results, UUID-filter drops, LLM provider per call, and pre-flight egress-filter results for cloud calls *(NFR-4)*
- [ ] **OBS-03**: Each LLM call logs its resolved provider (after per-feature override resolution) for audit *(FR-4.3.3, FR-9.6)*

### Reliability & Performance (PERF-*)

- [ ] **PERF-01**: Presidio NER engine, gender-detection model, and nickname dictionary are loaded once at application startup as lazy singletons *(NFR-1)*
- [ ] **PERF-02**: Anonymization completes in under 500 ms for typical chat messages (< 2000 tokens) *(NFR-1)*
- [ ] **PERF-03**: Concurrent requests writing to the same conversation registry are serialized via async lock to prevent race conditions *(NFR-3)*
- [ ] **PERF-04**: When the configured LLM provider is unavailable, auxiliary features degrade per NFR-3 — entity resolution → algorithmic clustering, missed-PII scan → skipped, title/metadata → templated default; failures are logged but never crash the application or leak raw PII *(FR-9.7, NFR-3)*

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

<!-- Maps requirements to phases. Validated Baseline maps to "Pre-GSD" (shipped before initialization).
     v1.0 phase mapping is filled by the gsd-roadmapper agent in the next workflow step. -->

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
| PII-01..05 | v1.0 — TBD (roadmapper) | ☐ Pending |
| ANON-01..06 | v1.0 — TBD (roadmapper) | ☐ Pending |
| REG-01..05 | v1.0 — TBD (roadmapper) | ☐ Pending |
| RESOLVE-01..04 | v1.0 — TBD (roadmapper) | ☐ Pending |
| DEANON-01..05 | v1.0 — TBD (roadmapper) | ☐ Pending |
| BUFFER-01..03 | v1.0 — TBD (roadmapper) | ☐ Pending |
| PROMPT-01 | v1.0 — TBD (roadmapper) | ☐ Pending |
| SCAN-01..05 | v1.0 — TBD (roadmapper) | ☐ Pending |
| PROVIDER-01..07 | v1.0 — TBD (roadmapper) | ☐ Pending |
| TOOL-01..04 | v1.0 — TBD (roadmapper) | ☐ Pending |
| EMBED-01..02 | v1.0 — TBD (roadmapper) | ☐ Pending |
| OBS-01..03 | v1.0 — TBD (roadmapper) | ☐ Pending |
| PERF-01..04 | v1.0 — TBD (roadmapper) | ☐ Pending |

**Coverage:**
- Validated Baseline: 38 requirements (✓ Complete, shipped pre-GSD)
- v1.0 (Active) requirements: 54 — across 13 categories, mapping to phases TBD by roadmapper
- v2 (Deferred) requirements: 0
- Unmapped: 0 ✓

**v1.0 requirement counts by category:**
- PII detection: 5 | Anonymization: 6 | Entity registry: 5 | Entity resolution: 4
- De-anonymization: 5 | Response buffering & SSE: 3 | System prompt: 1 | Missed-PII scan: 5
- LLM provider config: 7 | Tool / sub-agent coverage: 4 | Embedding provider: 2
- Observability: 3 | Reliability & performance: 4

---
*Requirements defined: 2026-04-25*
*Last updated: 2026-04-25 — milestone v1.0 PII Redaction System requirements added (54 REQ-IDs from `docs/PRD-PII-Redaction-System-v1.1.md`)*
