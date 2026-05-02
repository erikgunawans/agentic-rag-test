# Milestones: LexCore

## v1.2 Advanced Tool Calling & Agent Intelligence (Shipped: 2026-05-02)

**Phases completed:** 5 phases, 26 plans, 1 tasks

**Key accomplishments:**

- Found during:
- EXECUTED + VERIFIED

---

## v1.0 — PII Redaction System

**Shipped:** 2026-04-29
**Phases:** 1–6 (6 phases, 44 plans)
**Timeline:** 2026-04-25 → 2026-04-29 (4 days)
**Commits:** ~240 | Files changed: ~240 | Insertions: ~56,500
**Tests at close:** 352 passing (non-slow suite)

### Delivered

Privacy-preserving chat layer for LexCore. Real PII never reaches cloud-LLM payloads. Conversation-scoped entity registry anonymizes incoming messages, LLM works with Faker-generated surrogates, responses are de-anonymized before user display. Full admin configurability (toggle, provider, per-feature overrides), graceful degradation on provider failure, and complete observability via thread_id correlation logging.

### Key Accomplishments

1. Presidio + spaCy NER pipeline with two-pass thresholds (surrogate vs hard-redact), 16 entity types, UUID filter, Indonesian gender-matched Faker surrogates (Phase 1)
2. Conversation-scoped entity registry — Supabase `entity_registry` table, asyncio lock, UNIQUE constraint race-protection, case-insensitive lookups (Phase 2)
3. Three-mode entity resolution (algorithmic Union-Find / LLM / none) with pre-flight egress filter blocking real-PII cloud calls; admin UI for provider and mode overrides (Phase 3)
4. Placeholder-tokenized 3-phase de-anonymization pipeline with Jaro-Winkler fuzzy matching, optional LLM missed-PII scan, and system-prompt surrogate-preservation guidance (Phase 4)
5. End-to-end chat-loop integration: full response buffering, `redaction_status` SSE events, symmetric anonymize/de-anonymize across all tools and sub-agents; D-48 canonical-only egress scan; DB-backed admin toggle (Phase 5)
6. `EMBEDDING_PROVIDER=local|cloud` switch; graceful fallback for all 3 LLM failure modes; thread_id correlation logging across 5 modules; 352/352 tests passing (Phase 6)

### Stats

| Metric | Value |
|--------|-------|
| Phases | 6 |
| Plans | 44 |
| Tests passing | 352 (non-slow) |
| Timeline | 4 days (Apr 25–29) |
| Commits | ~240 |
| Files changed | ~240 |
| New services | 10 (redaction subsystem) |
| Migrations applied | 5 (029–033) |

### Known Deferred Items at Close

- PERF-02 (500ms anonymization budget on server hardware): 2000ms hard gate passed; 500ms primary target unconfirmed on dev hardware. Run `pytest tests/services/redaction/test_perf_latency.py -m slow -v` on CI/Railway to confirm.

### Archive

- Roadmap: `.planning/milestones/v1.0-ROADMAP.md`
- Requirements: `.planning/milestones/v1.0-REQUIREMENTS.md`

---

_More milestones will be appended here as they ship._
