# Phase 1: Detection & Anonymization Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `01-CONTEXT.md` — this log preserves the alternatives considered.

**Date:** 2026-04-25
**Phase:** 01-detection-anonymization-foundation
**Areas discussed:** NER model for Indonesian, Faker locale & surrogates, UUID false-positive filter, Tracing + service shape

---

## Area Selection

| Option | Description | Selected |
|--------|-------------|----------|
| NER model for Indonesian | Which spaCy/Presidio model? `en_core_web_trf` vs `xx_ent_wiki_sm` vs hybrid vs `id_core_news_lg`. | ✓ |
| Faker locale & surrogates | Faker `id_ID` vs `en_US` vs auto-detect; collision-retry budget; surname x-check (FR-2.5). | ✓ |
| UUID false-positive filter | Pre-input mask vs post-NER drop; UUID regex scope. | ✓ |
| Tracing + service shape | Pluggable `TRACING_PROVIDER` vs hardcoded LangSmith; service public API; init pattern; test entry. | ✓ |

User selected ALL four areas (multiSelect).

---

## Area 1: NER Model for Indonesian

### Q1: Which spaCy NER model should Presidio use?

| Option | Description | Selected |
|--------|-------------|----------|
| Multilingual `xx_ent_wiki_sm` | ~12 MB, supports Indonesian. Recognizes 'Bambang Sutrisno' reliably. | ✓ |
| Hybrid `xx_ent_wiki_sm + en_core_web_lg` | ~750 MB total, slower (~2x), most accurate. | |
| `en_core_web_trf` only | English transformer, biases against Indonesian names. | |
| `id_core_news_lg` | Indonesian-specific. Weaker on English entities common in legal text. | |

**User's choice:** Multilingual `xx_ent_wiki_sm` (Recommended).

### Q2: How should Indonesian honorifics ('Pak', 'Bu', 'Ibu', 'Bapak') be handled?

| Option | Description | Selected |
|--------|-------------|----------|
| Strip before NER, re-attach after | Pre-process: strip honorific, run NER, reattach in surrogate. Highest accuracy. | ✓ |
| Treat honorific as part of entity span | NER decides. Surrogate may lose honorific. | |
| Defer to Phase 3 entity resolution | Phase 1 ignores; Phase 3 collapses inconsistencies. | |

**User's choice:** Strip before NER, re-attach after (Recommended).

### Q3: Should detection thresholds be adjusted from PRD defaults (0.7 / 0.3) for Indonesian?

| Option | Description | Selected |
|--------|-------------|----------|
| PRD defaults | 0.7 / 0.3. Tune later if eval shows over/under-detection. | ✓ |
| Lower surrogate threshold to 0.5 | Multilingual scores lower-confidence; more FP. | |
| Per-entity-type thresholds | Most tunable; adds env-var sprawl. Defer to Phase 6. | |

**User's choice:** Use PRD defaults (Recommended).

### Q4: More questions, or move on?

**User's choice:** Next area.

**Notes:** Phase 6 hardening can revisit thresholds with eval data. Indonesian academic titles (S.H., M.H., Dr., Prof.) deferred to Phase 4 (prompt-guidance phase).

---

## Area 2: Faker Locale & Surrogate Generation

### Q1: Which Faker locale should generate surrogates?

| Option | Description | Selected |
|--------|-------------|----------|
| `id_ID` only | All Indonesian. Cultural consistency. Foreign names get Indonesian surrogates (accepted tradeoff). | ✓ |
| Hybrid: detect-and-locale-match | langdetect per entity; extra latency. | |
| `en_US` default | PRD example uses Marcus Rodriguez. Cross-cultural; jarring in legal context. | |

**User's choice:** `id_ID` only (Recommended).

### Q2: Collision-retry budget?

| Option | Description | Selected |
|--------|-------------|----------|
| 10 retries → non-realistic fallback | Bounded latency. Realistic dictionary effectively never fails. | ✓ |
| 3 retries → fallback | Faster bound; higher chance of fallback firing. | |
| 100 retries, no fallback | Maximally realistic; pathological tail latency. | |

**User's choice:** 10 retries, then non-realistic fallback (Recommended).

### Q3: Surname / first-name cross-check (FR-2.5) — how strict?

| Option | Description | Selected |
|--------|-------------|----------|
| Strict per FR-2.5 | Reject any Faker output whose tokens overlap real-name tokens. | ✓ |
| Relaxed: only exact full-name match | Simpler. Opens FR-2.5 corruption scenario (PRD §7.5). | |
| Strict + log every rejection | Verbose; defer logging tuning to Phase 6. | |

**User's choice:** Strict per FR-2.5 (Recommended).

### Q4: Hard-redact placeholder format?

| Option | Description | Selected |
|--------|-------------|----------|
| All same type → same `[ENTITY_TYPE]` | Two credit cards both `[CREDIT_CARD]`. PRD-literal. | ✓ |
| Numbered: `[CREDIT_CARD_1]`, `[CREDIT_CARD_2]` | Disambiguates. Per-call counter per type. | |
| You decide | Claude picks. | |

**User's choice:** All same type → same placeholder (Recommended).

### Q5: More questions, or move on?

**User's choice:** Next area.

**Notes:** Gender-detection library is English-biased on Indonesian names — captured as D-05 (Indonesian first-name lookup table seeded from common Indonesian names). Faker seeding for test reproducibility captured as D-20.

---

## Area 3: UUID False-Positive Filter

### Q1: UUID-filter strategy?

| Option | Description | Selected |
|--------|-------------|----------|
| Pre-input mask + post-NER restore | UUIDs replaced with sentinels before NER, restored after. Bulletproof. | ✓ |
| Post-NER span-overlap drop | Run NER on raw text; drop entities whose spans overlap a UUID match. | |
| Both: pre-mask + post-drop safety net | Defense in depth. | |

**User's choice:** Pre-input mask, post-NER restore (Recommended).

### Q2: UUID regex scope?

| Option | Description | Selected |
|--------|-------------|----------|
| Standard 8-4-4-4-12 hex with dashes | Covers Supabase / Postgres `uuid_generate_v4()`. | ✓ |
| Standard + bare 32-hex (no dashes) | Broader; risks masking SHA hashes etc. | |
| Standard + numeric IDs (>8 digits) | Catches numeric PKs but also masks phone/bank numbers (which SHOULD be redacted). | |

**User's choice:** Standard 8-4-4-4-12 hex with dashes (Recommended).

### Q3: Should the filter protect document_id paths in tool args?

| Option | Description | Selected |
|--------|-------------|----------|
| No — Phase 1 is plain text only | Tool-arg structure-aware filtering is Phase 5. | ✓ |
| Yes — accept structured input with `don't_redact_keys` | Useful for Phase 5 plumbing; leaks Phase 5 design into Phase 1 API. | |
| You decide | Claude picks. | |

**User's choice:** No — Phase 1 only handles raw text (Recommended).

### Q4: More questions, or move on?

**User's choice:** Next area.

**Notes:** Sentinel-collision check (`<<UUID_` substring already in input) captured as D-11 — fail fast rather than silently corrupt.

---

## Area 4: Tracing Provider + Service API Shape

### Q1: How pluggable should tracing be in Phase 1?

| Option | Description | Selected |
|--------|-------------|----------|
| Full pluggable: `TRACING_PROVIDER=langsmith\|langfuse\|none` | Refactor `langsmith_service.py` → `tracing_service.py`. Phase 1 SC#5 explicit. | ✓ |
| Hardcoded LangSmith for Phase 1, defer to Phase 6 | Faster Phase 1 ship; reopens tracing layer later. | |
| Pluggable abstraction, langsmith-only adapter for Phase 1 | Locks API surface, defers langfuse adapter. | |

**User's choice:** Full pluggable: `TRACING_PROVIDER=langsmith|langfuse|none` (Recommended).

### Q2: Public API of `RedactionService`?

| Option | Description | Selected |
|--------|-------------|----------|
| Single async `redact_text(text) -> RedactionResult` | Simple. Internals are private helpers. | ✓ |
| Separate `detect()` + `anonymize()` public methods | More composable for Phase 2-5. | |
| Class-based with both | Most flexible; larger API surface. | |

**User's choice:** Single async `redact_text(text) -> RedactionResult` (Recommended).

### Q3: Lazy singleton vs eager startup warm?

| Option | Description | Selected |
|--------|-------------|----------|
| Lazy `@lru_cache` + eager warm in lifespan | Satisfies SC#5 ("lazy") AND NFR-1 ("at startup"). First request hot. | ✓ |
| Strict lazy (no startup warm) | First request pays init cost (~3-5s). | |
| Eager lifespan-only (no `@lru_cache`) | Slowest startup, best first-request latency. | |

**User's choice:** Lazy `@lru_cache` + eager lifespan warm (Recommended).

### Q4: How should Phase 1 be testable end-to-end?

| Option | Description | Selected |
|--------|-------------|----------|
| Pure pytest, no HTTP | Imports `RedactionService` directly. No new endpoint. | ✓ |
| Admin-only `POST /admin/redaction/test` | Adds endpoint that gets repurposed in Phase 5. | |
| Both | Maximum coverage; more code in Phase 1. | |

**User's choice:** Pure pytest unit tests, no HTTP endpoint (Recommended).

---

## Closing Question

**Q:** Any remaining gray areas, or ready for `CONTEXT.md`?

**User's choice:** I'm ready for context.

---

## Claude's Discretion

Per `<decisions>` section of `01-CONTEXT.md`:
- Exact directory layout for `redaction_service.py` vs sub-package
- Internal `Entity` Pydantic model fields
- DEBUG vs INFO log levels for non-traced operations
- Initial honorific list contents (start: Pak, Bapak, Bu, Ibu, Sdr., Sdri.)
- Initial Indonesian gender lookup table contents
- `RedactionResult.entity_map` key direction (real → surrogate, leaning toward this for Phase 2 compatibility)

## Deferred Ideas

Captured in detail in `01-CONTEXT.md` `<deferred>` section. Highlights:
- Conversation-scoped registry → Phase 2
- Round-trip de-anonymization → Phase 2 + Phase 4
- Entity resolution / nickname clustering → Phase 3
- LLM provider switch + egress filter → Phase 3
- Chat-loop integration → Phase 5
- Per-entity-type thresholds → Phase 6 (eval-driven)
- Numbered hard-redact placeholders → revisit if user feedback demands
- Bahasa-Indonesia academic titles (S.H., M.H., Dr., Prof.) → Phase 4
- Code-switched ID/EN legal text → defer until eval evidence
