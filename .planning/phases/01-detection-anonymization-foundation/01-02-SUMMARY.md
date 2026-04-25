---
phase: 1
plan: 02
title: "Config / env-var additions: PII thresholds, entity buckets, tracing provider"
subsystem: config
tags: [config, settings, pii, tracing, env-vars]
requirements: [PII-03, PII-05, OBS-01]
dependency_graph:
  requires: []
  provides:
    - "settings.pii_redaction_enabled (master toggle, Phase 5 will gate on this)"
    - "settings.pii_surrogate_entities (D-04 surrogate bucket)"
    - "settings.pii_redact_entities (D-08 hard-redact bucket)"
    - "settings.pii_surrogate_score_threshold = 0.7 (D-03)"
    - "settings.pii_redact_score_threshold = 0.3 (D-03)"
    - "settings.tracing_provider (D-16, consumed by tracing_service.py)"
  affects:
    - "Plan 01-05 (Detection module) — reads pii_*_score_threshold and pii_*_entities"
    - "Plan 01-06 (Anonymization / RedactionService) — reads pii_*_entities"
    - "Plan 01-01 tracing_service.py (already shipped) — reads tracing_provider"
tech_stack:
  added: []
  patterns:
    - "pydantic-settings BaseSettings with auto env-var resolution (uppercase mapping)"
    - "extra='ignore' keeps existing .env files non-breaking when new fields are added"
    - "Comma-separated entity bucket strings (parsed into sets by downstream consumers in Plan 01-04/01-05)"
key_files:
  created: []
  modified:
    - "backend/app/config.py (+14 lines)"
decisions:
  - "Defaults match PRD §6 / CONTEXT.md D-03/D-04/D-08/D-16 exactly so a fresh deploy without overrides ships PRD-correct behaviour."
  - "tracing_provider default is empty string (D-16) — no-op decorator path; zero overhead in local dev."
  - "pii_redaction_enabled added in Phase 1 even though Phase 5 will use it; cheap forward-compat."
metrics:
  duration: "~1 min"
  tasks_completed: "1/1"
  files_changed: 1
  lines_added: 14
  lines_removed: 0
  completed_at: "2026-04-25T18:20:10Z"
commits:
  - "4f165cf — feat(01-02): add PII redaction settings (thresholds, buckets, tracing_provider)"
---

# Phase 1 Plan 02: Config / Env-Var Additions Summary

Extended `Settings(BaseSettings)` in `backend/app/config.py` with 6 new env-var-backed fields (5 PII + 1 tracing) so downstream Phase 1 plans (Detection, Anonymization, RedactionService) and the already-shipped tracing_service.py have a single source of truth for env-var resolution.

## Exact Block Appended to `Settings`

Inserted after the existing `langchain_tracing_v2: str = "false"` line (line 71) and before `@lru_cache def get_settings()`:

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

## Env-Var Names Downstream Code Can Rely On

pydantic-settings auto-uppercases attribute names → env var names. Downstream code reads via `get_settings()`:

| Settings attribute               | Env var                          | Default                                                                                                       | Type    | Source                  |
| -------------------------------- | -------------------------------- | ------------------------------------------------------------------------------------------------------------- | ------- | ----------------------- |
| `pii_redaction_enabled`          | `PII_REDACTION_ENABLED`          | `True`                                                                                                        | `bool`  | Phase 5 forward-compat  |
| `pii_surrogate_entities`         | `PII_SURROGATE_ENTITIES`         | `"PERSON,EMAIL_ADDRESS,PHONE_NUMBER,LOCATION,DATE_TIME,URL,IP_ADDRESS"`                                       | `str`   | CONTEXT.md D-04         |
| `pii_redact_entities`            | `PII_REDACT_ENTITIES`            | `"CREDIT_CARD,US_SSN,US_ITIN,US_BANK_NUMBER,IBAN_CODE,CRYPTO,US_PASSPORT,US_DRIVER_LICENSE,MEDICAL_LICENSE"` | `str`   | CONTEXT.md D-08         |
| `pii_surrogate_score_threshold`  | `PII_SURROGATE_SCORE_THRESHOLD`  | `0.7`                                                                                                         | `float` | CONTEXT.md D-03 / PII-05 |
| `pii_redact_score_threshold`     | `PII_REDACT_SCORE_THRESHOLD`     | `0.3`                                                                                                         | `float` | CONTEXT.md D-03 / PII-05 |
| `tracing_provider`               | `TRACING_PROVIDER`               | `""`                                                                                                          | `str`   | CONTEXT.md D-16 / OBS-01 |

## Compatibility Note

`SettingsConfigDict(env_file=".env", extra="ignore")` was already configured on the `Settings` class. Adding these 6 fields cannot break existing deployments — the `extra="ignore"` policy means unknown env vars in any `.env` are silently dropped, and previously unset env vars now resolve to the documented PRD-correct defaults rather than raising.

## Verification Performed

- `python -c "from app.config import get_settings; s = get_settings(); assert s.pii_surrogate_score_threshold == 0.7; assert s.pii_redact_score_threshold == 0.3; assert 'PERSON' in s.pii_surrogate_entities; assert 'CREDIT_CARD' in s.pii_redact_entities; assert s.tracing_provider == ''; assert s.pii_redaction_enabled is True; print('OK')"` → `OK`
- `python -c "from app.config import get_settings; s = get_settings(); print(s.pii_surrogate_score_threshold, s.pii_redact_score_threshold)"` → `0.7 0.3`
- `python -c "from app.main import app; print('OK')"` → `OK` (no other imports broken)
- `grep` acceptance checks (bucket strings, exact threshold/tracing lines) → all return 1 match each

## Success Criteria Status

- [x] PII-03 satisfied at config layer — `PII_SURROGATE_ENTITIES` / `PII_REDACT_ENTITIES` resolve into `settings.pii_surrogate_entities` / `settings.pii_redact_entities`.
- [x] PII-05 satisfied at config layer — `PII_SURROGATE_SCORE_THRESHOLD=0.7` and `PII_REDACT_SCORE_THRESHOLD=0.3` are documented defaults; pydantic-settings handles env-var overrides.
- [x] OBS-01 unblocked — `settings.tracing_provider` is the single read point for tracing_service.py provider resolution.
- [x] No regression — `from app.main import app` imports cleanly.

## Deviations from Plan

None — plan executed exactly as written. Append-only edit, six fields with PRD-correct defaults, single commit.

## Self-Check: PASSED

- File exists: `backend/app/config.py` — verified via `grep -n` returning 6 new field lines.
- Commit exists: `4f165cf` — verified via `git log --oneline`.
- Backend imports: `from app.main import app` exits 0 — verified.
- Defaults correct: `0.7`, `0.3`, `""`, `True` — verified via runtime assertion.
