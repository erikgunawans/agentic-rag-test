---
phase: "06-embedding-provider-production-hardening"
plan: 1
subsystem: "config"
tags: [embedding, provider-switch, fallback, settings, phase6]
dependency_graph:
  requires: []
  provides:
    - "settings.embedding_provider (EMBED-01)"
    - "settings.local_embedding_base_url (EMBED-02)"
    - "settings.llm_provider_fallback_enabled default=True (PERF-04)"
  affects:
    - "backend/app/services/embedding_service.py (Plan 06-03 consumer)"
    - "backend/app/services/redaction_service.py (fallback knob consumer)"
    - "backend/app/services/redaction/missed_scan.py (fallback knob consumer)"
tech_stack:
  added: []
  patterns:
    - "pydantic-settings BaseSettings env-var-backed field (Literal['local','cloud'])"
key_files:
  created: []
  modified:
    - "backend/app/config.py"
decisions:
  - "D-P6-01: EMBEDDING_PROVIDER env-var only, no migration, no system_settings column"
  - "D-P6-03: LOCAL_EMBEDDING_BASE_URL mirrors LOCAL_LLM_BASE_URL empty-default convention"
  - "D-P6-09: llm_provider_fallback_enabled flipped to True — PERF-04 ships fallback ON by default"
metrics:
  duration: "1m 13s"
  completed: "2026-04-29T07:14:22Z"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 1
---

# Phase 6 Plan 1: Config Settings Summary

**One-liner:** Added `embedding_provider`/`local_embedding_base_url` env-var Settings fields and flipped `llm_provider_fallback_enabled` default to True for PERF-04.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add embedding_provider + local_embedding_base_url | e7a9e31 | backend/app/config.py |
| 2 | Flip llm_provider_fallback_enabled default to True | eab3923 | backend/app/config.py |

## Changes Made

### New lines added to `backend/app/config.py` (verbatim)

```python
    # Phase 6: Embedding provider switch (EMBED-01, EMBED-02; D-P6-01..D-P6-03)
    # `cloud` (default) preserves the existing OpenAI-embeddings flow (RAG-02 unchanged).
    # `local` uses an OpenAI-API-compatible local endpoint (Ollama bge-m3, nomic-embed-text, LM Studio).
    # NOTE: Switching providers does NOT trigger automatic re-embedding of existing documents
    # (D-P6-04 / EMBED-02 — deployer-managed migration; document only, no code).
    embedding_provider: Literal["local", "cloud"] = "cloud"
    local_embedding_base_url: str = ""  # e.g. "http://localhost:11434/v1" for Ollama
```

### Line whose default flipped (Task 2)

Before:
```python
    llm_provider_fallback_enabled: bool = False
```

After:
```python
    llm_provider_fallback_enabled: bool = True  # Phase 6 D-P6-09: PERF-04 ships fallback ON by default
```

## Smoke-Check Outputs

```
# Combined verification (all three settings)
$ cd backend && source venv/bin/activate && python -c "from app.config import get_settings; s = get_settings(); assert s.embedding_provider == 'cloud' and s.local_embedding_base_url == '' and s.llm_provider_fallback_enabled is True; print('OK')"
OK

# Backend import check
$ source venv/bin/activate && python -c "from app.main import app; print('OK')"
OK

# Unit test regression check
$ pytest tests/unit -v --tb=short -q
256 passed, 557 warnings in 2.44s
```

## No Migration Introduced

Confirmed: zero new migration files added under `backend/migrations/`. This satisfies the D-P6-01 env-var-only invariant and Plan 06-08's `find backend/migrations -newer ...` gate will find zero new migration files from this plan.

## Deviations from Plan

None — plan executed exactly as written.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. Config-only change. Threat model items T-06-01-1 and T-06-01-2 noted:
- T-06-01-1 (medium): Fallback-on-by-default masked provider failure — mitigated by existing log paths (Plans 06-06/06-08 verify this).
- T-06-01-2 (low): Local embedding endpoint bypasses cloud egress by design — opt-in via env var, documented tradeoff.

## Self-Check: PASSED

- [x] `backend/app/config.py` exists and contains `embedding_provider` field (line 60)
- [x] `backend/app/config.py` exists and contains `local_embedding_base_url` field (line 61)
- [x] `backend/app/config.py` has `llm_provider_fallback_enabled: bool = True` (line 102)
- [x] Task 1 commit `e7a9e31` verified in git log
- [x] Task 2 commit `eab3923` verified in git log
- [x] 256/256 unit tests pass
- [x] No migration files added
