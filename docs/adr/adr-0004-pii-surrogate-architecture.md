---
title: "ADR-0004: PII Surrogate Architecture (Conversation-Scoped Anonymization)"
status: "Accepted"
date: "2026-04-28"
authors: "Erik Gunawan Supriatna (LexCore Engineering)"
tags: ["architecture", "decision", "pii", "privacy", "compliance", "redaction", "uu-pdp"]
supersedes: ""
superseded_by: ""
---

# ADR-0004: PII Surrogate Architecture (Conversation-Scoped Anonymization)

## Status

**Accepted** — shipped with v0.3.0.0 (PII Redaction System v1.0). Phases 1–5 complete; Phase 6 (cross-process async-lock upgrade per D-31) remains. Architecture invariant SC#5 (off-mode byte-identical to pre-v0.3) is enforced by tests.

## Context

LexCore handles Indonesian legal and contractual content that frequently contains personal data covered by **UU PDP (Undang-Undang Pelindungan Data Pribadi)**. Real PII (names, NIK numbers, addresses, phone numbers, emails) must not reach cloud-LLM providers (OpenRouter, OpenAI, Cohere) in their raw form. The architectural choice was:

- **Redaction (mask/black-bar)** — replace PII with `[REDACTED]` or `[NAME]` placeholders.
- **Anonymization (surrogate substitution)** — replace PII with realistic-but-fake surrogates from Faker, maintained per-conversation in a registry.
- **On-prem LLM only** — host an open-weights model locally and never send PII to cloud providers.
- **Pure encryption** — encrypt PII end-to-end, decrypt at the user's browser.

Critical considerations:

- **LLM reasoning quality.** Redaction (`[REDACTED]`) breaks semantic context — the model can no longer reason about "who did what". Surrogates preserve syntactic structure and pronoun coreference.
- **Cross-turn consistency.** When the user mentions "Pak Budi" in turn 1 and "he" in turn 3, the registry must remember that "Pak Budi" maps to surrogate "Pak Andika" so the model sees consistent identity.
- **Reversibility.** The user must see real names in the response; the system de-anonymizes on the way out.
- **Defense in depth.** A single anonymization scan can miss entities. A second-line egress guard must block any cloud-LLM call where registry-known PII would still leak.
- **Cost and latency.** Per-turn detection + registry I/O adds latency; this is acceptable for legal-grade compliance.
- **Off-mode invariance.** When the toggle is off, the pipeline must be a perfect bypass — byte-identical to pre-v0.3 behavior. This is a hard SLA.

## Decision

Adopt **conversation-scoped surrogate substitution** as the architecture:

1. On every incoming user message (when `pii_redaction_enabled = true`), Presidio + spaCy (`xx_ent_wiki_sm`) scans for entities.
2. Detected entities are mapped to Faker-generated surrogates and persisted in the `entity_registry` table, keyed by `(thread_id, entity_value)`.
3. The LLM only ever sees surrogates. The cloud-egress guard inspects every outgoing payload and blocks if any registry-known real PII would leak.
4. On the response path, surrogates are reversed back to real values before the user sees them.
5. When the toggle is off, the entire pipeline is bypassed — no scans, no DB calls, no surrogate map.

## Consequences

### Positive

- **POS-001**: LLM reasoning capability preserved — the model sees realistic names, addresses, etc., and can perform full coreference and inference.
- **POS-002**: Cross-turn consistency — "Pak Budi" → "Pak Andika" stays stable for the entire thread; pronouns resolve correctly.
- **POS-003**: Reversibility — the user always sees real names; surrogates are an internal-only representation.
- **POS-004**: Defense in depth — even if Presidio misses an entity, the egress guard catches registry-known PII before the cloud call. Layered safety.
- **POS-005**: UU PDP alignment — real PII never enters cloud-LLM payloads, satisfying data-localization and minimization principles.
- **POS-006**: Per-feature LLM provider override — entity resolution, missed-scan, fuzzy de-anon, title-gen, and metadata tasks can be routed to local or cloud LLMs independently via `system_settings`.
- **POS-007**: Off-mode invariant (SC#5) — when the toggle is off, the system behaves byte-identically to pre-v0.3, enabling rollback by toggle without redeploy.

### Negative

- **NEG-001**: Per-turn latency — Presidio scan + DB registry I/O adds tens to low-hundreds of milliseconds per turn.
- **NEG-002**: Detection-quality ceiling — Indonesian-specific name patterns (honorifics, nicknames, gendered forms) require custom heuristics in `redaction/name_extraction.py`, `nicknames_id.py`, `honorifics.py`. False negatives are mitigated but not eliminated.
- **NEG-003**: Operational complexity — 12-module redaction sub-package with leaf-module circular-import discipline. Onboarding cost is real.
- **NEG-004**: Storage growth — `entity_registry` grows over time; retention/cleanup policy is a follow-up concern.
- **NEG-005**: The egress guard adds a hard failure mode (`blocked` SSE event) — UX must communicate why a turn was blocked.
- **NEG-006**: spaCy model `xx_ent_wiki_sm` must be downloaded at Docker BUILD time — runtime download fails with EACCES on Railway's non-root container. Hard requirement on the Dockerfile.

## Alternatives Considered

### Pure Redaction (Mask/Placeholder)

- **ALT-001**: **Description**: Replace PII with `[REDACTED]` or `[NAME]` placeholders before sending to LLM.
- **ALT-002**: **Rejection Reason**: Breaks LLM reasoning. The model cannot resolve "who did what to whom" when all entities collapse to placeholders. Coreference and pronoun resolution fail; answers degrade noticeably on legal queries.

### On-Prem LLM Only

- **ALT-003**: **Description**: Host an open-weights model (Llama, Qwen) locally and never send PII to cloud providers.
- **ALT-004**: **Rejection Reason**: Open-weights model quality on Indonesian legal content lags Claude/GPT-4 substantially. Cost of the GPU infrastructure is significant. We retain on-prem LLM as an *option* for specific features via the per-feature provider override, but not as the primary architecture.

### Pure Encryption

- **ALT-005**: **Description**: Encrypt PII end-to-end; decrypt only at the user's browser.
- **ALT-006**: **Rejection Reason**: The LLM cannot reason on encrypted text. This option does not address the problem.

### Per-Request Random Surrogates

- **ALT-007**: **Description**: Generate fresh surrogates on every request, no registry.
- **ALT-008**: **Rejection Reason**: Cross-turn consistency is impossible. "Pak Budi" → "Pak Andika" in turn 1 and "Pak Wahyu" in turn 3 — the model gets confused; coreference breaks.

## Implementation Notes

- **IMP-001**: Pipeline modules live in `backend/app/services/redaction/`. Top-level `redaction/__init__.py` re-exports public API. Internal modules import only from leaf modules (`errors.py` has no internal imports) to avoid circular imports.
- **IMP-002**: Per-thread registry is keyed by `(thread_id, entity_value, entity_type)` in the `entity_registry` table (migration 029).
- **IMP-003**: Egress guard (`redaction/egress.py`) raises `EgressBlockedAbort`; the chat router catches and emits a `blocked` SSE event with reason.
- **IMP-004**: Off-mode is enforced in the chat router *before* importing redaction modules — when the flag is false, the redaction package is not exercised at all. This protects the SC#5 invariant.
- **IMP-005**: Per-thread async lock prevents concurrent registry writes within a single Python process. Cross-process locking is Phase 6 work (D-31).
- **IMP-006**: Presidio's spaCy model must be downloaded in the Dockerfile (`RUN python -m spacy download xx_ent_wiki_sm`) before the `USER app` switch — runtime download fails with EACCES.
- **IMP-007**: 17 unit tests + 5 integration tests cover the pipeline. SC#5 invariant has dedicated tests asserting byte-identical off-mode behavior.

## References

- **REF-001**: ADR-0001 — Raw SDK over Framework (the redaction wrapper sits cleanly atop raw OpenRouter calls).
- **REF-002**: ADR-0002 — Single-Row System Settings (the `pii_redaction_enabled` toggle).
- **REF-003**: ADR-0007 — Chain-of-Thought Observability (reasoning tokens MUST also flow through the egress guard and de-anonymization).
- **REF-004**: `docs/PRD-PII-Redaction-System-v1.1.md` — full product requirements.
- **REF-005**: `backend/app/services/redaction/` — implementation modules.
- **REF-006**: Migrations `029_entity_registry.sql`, `030_provider_settings.sql`, `031_fuzzy_settings.sql`, `032_redaction_master_toggle.sql`.
- **REF-007**: UU PDP — Undang-Undang Republik Indonesia Nomor 27 Tahun 2022 tentang Pelindungan Data Pribadi.
- **REF-008**: Microsoft Presidio — https://microsoft.github.io/presidio/
