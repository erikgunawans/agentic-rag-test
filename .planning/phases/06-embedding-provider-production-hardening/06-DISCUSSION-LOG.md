# Phase 6: Embedding Provider & Production Hardening - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-29
**Phase:** 6-Embedding Provider & Production Hardening
**Areas discussed:** Embedding switch surface, Latency budget test, Fallback scope, Observability format

---

## Embedding Switch Surface

### Q1: Admin UI or env-var only?

| Option | Description | Selected |
|--------|-------------|----------|
| Env-var only | No new system_settings column or migration. Consistent with CUSTOM_EMBEDDING_MODEL. Deploy-time decision. | ✓ |
| Admin UI toggle | New DB column + migration + admin settings field. Runtime toggle, same pattern as LLM provider Phase 3. Risks mid-production vector space inconsistency. | |

**User's choice:** Env-var only
**Notes:** Cleaner approach — switching providers is a deploy decision, not an admin console action.

### Q2: Extend EmbeddingService or new class?

| Option | Description | Selected |
|--------|-------------|----------|
| Extend EmbeddingService | Add provider branch in existing 87-line file. Minimal surgery. | ✓ |
| New EmbeddingProviderClient | Mirrors LLMProviderClient architecture. More consistent but ~150 lines of new structure for a two-branch switch. | |

**User's choice:** Extend EmbeddingService

### Q3: Env var name for local endpoint?

| Option | Description | Selected |
|--------|-------------|----------|
| LOCAL_EMBEDDING_BASE_URL | Mirrors LOCAL_LLM_BASE_URL from Phase 3. Consistent naming. | ✓ |
| EMBEDDING_BASE_URL | Shorter but ambiguous — could imply cloud endpoint override. | |

**User's choice:** LOCAL_EMBEDDING_BASE_URL

---

## Latency Budget Test

### Q1: What to measure?

| Option | Description | Selected |
|--------|-------------|----------|
| redact_text_batch on 2000-token text | Pure service-layer test. No HTTP overhead. Cleanest signal for 500ms SLO. | ✓ |
| Full chat API round-trip | Captures everything but mixes latency sources. Hard to attribute to redaction alone. | |

**User's choice:** redact_text_batch on 2000-token text

### Q2: Real Presidio or mocked NER?

| Option | Description | Selected |
|--------|-------------|----------|
| Real Presidio, marked slow | @pytest.mark.slow; skipped in default CI. Actually catches NER regressions. | ✓ |
| Mocked NER, always fast | Always passes <100ms but doesn't test real performance. | |

**User's choice:** Real Presidio, marked @pytest.mark.slow

---

## Fallback Scope

### Q1: Enable fallback by default?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — enable by default | Phase 6 fully ships PERF-04. Provider outage degrades gracefully instead of crashing. Admin can still disable. | ✓ |
| Keep default false | Safer for auditable deployments where silent degradation is less desirable. | |

**User's choice:** Enable by default (flip Phase 3 D-52's default from false to true)

### Q2: Title fallback format?

| Option | Description | Selected |
|--------|-------------|----------|
| First 6 words of anonymized message | Meaningful stub, visible immediately, stays in surrogate form until de-anonymized. | ✓ |
| Static "New Thread" | Simple but thread stays unnamed. | |
| Timestamp-based | Always unique but meaningless. | |

**User's choice:** First 6 words of anonymized message

### Q3: Cloud→local crossover in scope?

| Option | Description | Selected |
|--------|-------------|----------|
| Out of scope | PERF-04 only requires algorithmic/template/skip fallbacks. Crossover remains plumbed-but-disabled per Phase 3 D-52. | ✓ |
| In scope | Enable cloud→local crossover with pre-anonymization. Larger blast radius for the last milestone phase. | |

**User's choice:** Out of scope

---

## Observability Format

### Q1: How to achieve "single chat turn log block"?

| Option | Description | Selected |
|--------|-------------|----------|
| Add thread_id correlation to existing debug lines | Use registry.thread_id inside existing logger.debug calls. grep thread_id=<id> extracts all lines for one turn. Minimal new code. | ✓ |
| New per-turn summary log entry | One structured JSON line aggregating all counts. Easier to parse programmatically but adds a new coordinator concept. | |

**User's choice:** Add thread_id correlation

### Q2: thread_id passing strategy?

| Option | Description | Selected |
|--------|-------------|----------|
| Use registry.thread_id inside existing methods | registry is already a param everywhere; read thread_id from it. Zero call-site changes. | ✓ |
| Pass thread_id explicitly everywhere | Adds string param to every function signature. Larger diff. | |

**User's choice:** Use registry.thread_id inside method bodies (no new call-site params)

---

## Claude's Discretion

- Log field format: `thread_id=<value>` space-separated key=value, matching existing `detection.py` format.
- Test fixture content: hardcoded Indonesian-language legal text with PERSON, EMAIL_ADDRESS, PHONE_NUMBER entities.
- `embed_batch()` local path: use same `AsyncOpenAI` batching as cloud path.

## Deferred Ideas

- Cloud→local crossover for PERF-04 (Phase 3 D-52 plumbed-but-disabled state preserved)
- Postgres advisory lock D-31 (FUTURE-WORK, not a Phase 6 requirement)
- `messages.anonymized_content` sibling-column cache (Phase 5 deferred; revisit if latency test reveals bottleneck)
- Fake-stream chunked delivery of buffered de-anon output
