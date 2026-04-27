---
phase: 1
plan_number: 02
title: "Config / env-var additions: Settings fields for PII thresholds, entity buckets, and tracing provider"
wave: 1
depends_on: []
requirements: [PII-03, PII-05, OBS-01]
files_modified:
  - backend/app/config.py
autonomous: true
must_haves:
  - "Settings exposes pii_surrogate_entities, pii_redact_entities, pii_surrogate_score_threshold (=0.7), pii_redact_score_threshold (=0.3), and tracing_provider env-var-backed fields."
  - "Defaults match PRD §6 / CONTEXT.md D-03 exactly so a fresh deploy without overrides ships PRD-correct behaviour."
  - "Bucket env vars are comma-separated strings parseable into Python sets without runtime errors on empty or whitespace-padded values."
---

<objective>
Extend `backend/app/config.py` `Settings` with the env-var fields that downstream Phase 1 plans need to read: PII threshold scalars, surrogate / hard-redact entity bucket strings, and the tracing provider switch (consumed by Plan 01's tracing_service.py). All defaults match the PRD (`docs/PRD-PII-Redaction-System-v1.1.md` §6) and the locked decisions in `01-CONTEXT.md` (D-03 thresholds, D-04 surrogate-bucket entity list, D-08 hard-redact-bucket entity list, D-16 tracing provider).

Purpose: Phase 1 PII-03 ("System loads entity-type bucket configuration from env vars `PII_SURROGATE_ENTITIES` and `PII_REDACT_ENTITIES`") and PII-05 ("System exposes detection thresholds as configurable env vars") are direct config-surface requirements. Plan 05 (Detection module) and Plan 06 (Anonymization / RedactionService) read all of these. Plan 01 (Tracing service) reads `tracing_provider`. Centralising the field declarations here keeps `Settings` the single source of truth and avoids each downstream plan re-declaring env-var names.

Output: `backend/app/config.py` with a new `# PII Redaction (Phase 1, milestone v1.0)` section appended to the `Settings` class, containing 5 new fields with PRD-correct defaults.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/phases/01-detection-anonymization-foundation/01-CONTEXT.md
@backend/app/config.py

<interfaces>
<!-- Existing Settings class: pydantic-settings BaseSettings with SettingsConfigDict(env_file=".env", extra="ignore"). -->
<!-- Append fields ONLY — do not rename or reformat existing fields. Existing pattern (verbatim from current file): -->

```python
# RAG tuning
rag_top_k: int = 5
rag_similarity_threshold: float = 0.3

# Cohere Rerank (Phase 2)
cohere_api_key: str = ""

# LangSmith (optional)
langsmith_api_key: str = ""
langsmith_project: str = "rag-masterclass"
```

<!-- Pattern for new fields: comment header + grouped fields. -->
<!-- Env vars resolve via pydantic-settings auto-uppercase: settings.tracing_provider reads $TRACING_PROVIDER. -->
</interfaces>
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: Append PII Redaction config fields to Settings class</name>
  <files>backend/app/config.py</files>
  <read_first>
    - backend/app/config.py (existing 76-line Settings class — append-only edit; do NOT modify existing fields)
    - .planning/phases/01-detection-anonymization-foundation/01-CONTEXT.md (D-03 thresholds, D-16 tracing provider; canonical_refs section names PRD §6 as the authoritative defaults source)
    - docs/PRD-PII-Redaction-System-v1.1.md §6 if available locally (Configuration Reference — defines the 16 entity types and their bucket assignment)
  </read_first>
  <action>
Add a new section at the END of the `Settings` class (after the existing `langchain_tracing_v2` field at line 71, BEFORE the closing class boundary), exactly:

```python
    # PII Redaction (milestone v1.0 — Phase 1 Detection & Anonymization Foundation)
    # See docs/PRD-PII-Redaction-System-v1.1.md §6 and .planning/phases/01-detection-anonymization-foundation/01-CONTEXT.md D-03/D-04/D-08
    pii_redaction_enabled: bool = True
    pii_surrogate_entities: str = "PERSON,EMAIL_ADDRESS,PHONE_NUMBER,LOCATION,DATE_TIME,URL,IP_ADDRESS"
    pii_redact_entities: str = "CREDIT_CARD,US_SSN,US_ITIN,US_BANK_NUMBER,IBAN_CODE,CRYPTO,US_PASSPORT,US_DRIVER_LICENSE,MEDICAL_LICENSE"
    pii_surrogate_score_threshold: float = 0.7
    pii_redact_score_threshold: float = 0.3

    # Tracing provider switch (OBS-01)
    # "" / "none"  → no-op @traced decorator (zero overhead)
    # "langsmith" → wraps langsmith.traceable
    # "langfuse"  → wraps langfuse.observe
    tracing_provider: str = ""
```

Field-by-field rationale (must match these exact strings — they are the PRD §6 / CONTEXT.md D-03/D-04/D-08 contract):

1. `pii_redaction_enabled: bool = True` — master toggle so `PII_REDACTION_ENABLED=false` reverts chat to baseline (referenced in Phase 5 SC#5 but field declared here for forward compat; cheap to add now).

2. `pii_surrogate_entities: str = "PERSON,EMAIL_ADDRESS,PHONE_NUMBER,LOCATION,DATE_TIME,URL,IP_ADDRESS"` — D-04 enumerates exactly these 7 entity types as the surrogate bucket. Comma-separated, no spaces, uppercase to match Presidio's entity-type names.

3. `pii_redact_entities: str = "CREDIT_CARD,US_SSN,US_ITIN,US_BANK_NUMBER,IBAN_CODE,CRYPTO,US_PASSPORT,US_DRIVER_LICENSE,MEDICAL_LICENSE"` — the 9 hard-redact types per PII-01 (16 total minus the 7 surrogate types). These render as `[ENTITY_TYPE]` placeholders.

4. `pii_surrogate_score_threshold: float = 0.7` — D-03, PII-05.

5. `pii_redact_score_threshold: float = 0.3` — D-03, PII-05.

6. `tracing_provider: str = ""` — D-16, OBS-01. Empty default keeps local dev tracing-free (D-16 explicitly: "Empty value → no-op decorator (zero overhead)").

Do NOT touch existing fields (`langsmith_api_key`, `langsmith_project`, `langchain_tracing_v2` remain in place — Plan 01's tracing_service.py reads them when `tracing_provider="langsmith"`). The `extra="ignore"` config means unknown env vars in `.env` are silently dropped, so adding these fields cannot break existing deployments.
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && python -c "from app.config import get_settings; s = get_settings(); assert s.pii_surrogate_score_threshold == 0.7, s.pii_surrogate_score_threshold; assert s.pii_redact_score_threshold == 0.3, s.pii_redact_score_threshold; assert 'PERSON' in s.pii_surrogate_entities; assert 'CREDIT_CARD' in s.pii_redact_entities; assert s.tracing_provider == ''; print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "pii_surrogate_entities" backend/app/config.py` returns at least 1 match.
    - `grep -n "pii_redact_entities" backend/app/config.py` returns at least 1 match.
    - `grep -n "pii_surrogate_score_threshold: float = 0.7" backend/app/config.py` returns exactly 1 match.
    - `grep -n "pii_redact_score_threshold: float = 0.3" backend/app/config.py` returns exactly 1 match.
    - `grep -n "tracing_provider: str = \"\"" backend/app/config.py` returns exactly 1 match.
    - `grep -c "PERSON,EMAIL_ADDRESS,PHONE_NUMBER,LOCATION,DATE_TIME,URL,IP_ADDRESS" backend/app/config.py` returns 1 (the surrogate bucket default contains all 7 entity types in the canonical order).
    - `grep -c "CREDIT_CARD,US_SSN,US_ITIN,US_BANK_NUMBER,IBAN_CODE,CRYPTO,US_PASSPORT,US_DRIVER_LICENSE,MEDICAL_LICENSE" backend/app/config.py` returns 1 (the hard-redact bucket default contains all 9 entity types).
    - `cd backend && source venv/bin/activate && python -c "from app.config import get_settings; s = get_settings(); print(s.pii_surrogate_score_threshold, s.pii_redact_score_threshold)"` prints `0.7 0.3`.
    - `cd backend && source venv/bin/activate && python -c "from app.main import app; print('OK')"` exits 0 (no other imports broken).
  </acceptance_criteria>
  <done>config.py extended with 6 new fields (5 PII + 1 tracing); defaults exactly match PRD §6 / CONTEXT.md D-03/D-04/D-08/D-16; backend imports cleanly.</done>
</task>

</tasks>

<verification>
After the task completes, validate the new fields are wired:
```bash
cd backend && source venv/bin/activate
python -c "from app.config import get_settings; s = get_settings(); print(vars(s))" | grep -E "pii_|tracing_provider"
# Expected: 6 lines, one per new field, with the documented defaults.
```
</verification>

<success_criteria>
1. PII-03 satisfied at the config layer: `PII_SURROGATE_ENTITIES` and `PII_REDACT_ENTITIES` env vars resolve into `settings.pii_surrogate_entities` / `settings.pii_redact_entities`.
2. PII-05 satisfied at the config layer: `PII_SURROGATE_SCORE_THRESHOLD=0.7` and `PII_REDACT_SCORE_THRESHOLD=0.3` are the documented defaults and respond to env-var overrides via pydantic-settings.
3. OBS-01 unblocked: `settings.tracing_provider` is the single read point Plan 01's tracing_service.py uses to resolve provider mode.
4. No regression: `python -c "from app.main import app; print('OK')"` still exits 0.
</success_criteria>

<output>
After completion, create `.planning/phases/01-detection-anonymization-foundation/01-02-SUMMARY.md` capturing the exact field block appended to `Settings`, the env-var names downstream code can rely on, and a one-line note that `extra="ignore"` keeps existing `.env` files non-breaking.
</output>
