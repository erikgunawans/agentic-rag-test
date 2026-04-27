---
phase: 04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance
plan: 02
subsystem: redaction
tags: [pii, fuzzy-deanon, rapidfuzz, jaro-winkler, unit-tests]
requirements_addressed: [DEANON-03]
dependency_graph:
  requires:
    - "Phase 1 backend/app/services/redaction/honorifics.py (strip_honorific)"
    - "rapidfuzz>=3.10.0 (already pinned in backend/requirements.txt — transitive Presidio dep, D-67)"
  provides:
    - "backend/app/services/redaction/fuzzy_match.py exposing _normalize_for_fuzzy, fuzzy_score, best_match"
    - "Frozen contract for Plan 04-03 de_anonymize_text Pass 2 (algorithmic mode)"
  affects:
    - "Plan 04-03 will import best_match and pass cluster-scoped variants per D-68"
tech_stack:
  added: []
  patterns:
    - "Pure CPU function (no @traced, no logging, no async, no DB, no LLM)"
    - "Token-level max-pair Jaro-Winkler (D-70 normalization → JaroWinkler.normalized_similarity)"
    - "Caller-scoped variants (D-68 — registry-agnostic)"
key_files:
  created:
    - backend/app/services/redaction/fuzzy_match.py
    - backend/tests/unit/test_fuzzy_match.py
  modified: []
decisions:
  - "D-67: rapidfuzz Jaro-Winkler — verified import works in backend venv (Smith/Smyth = 0.893); already pinned (rapidfuzz>=3.10.0); no requirements.txt change needed"
  - "D-68: best_match accepts variants from caller only — pure function, no registry import (grep confirms 0 occurrences of 'from app.services.redaction.registry')"
  - "D-69: default threshold=0.85 set at function signature; Plan 04-03 caller will read settings.fuzzy_deanon_threshold for env/DB overrides"
  - "D-70: _normalize_for_fuzzy = strip_honorific + casefold + whitespace tokenize; reuses Phase 1 honorifics.strip_honorific"
  - "D-71: zero @traced — caller (de_anonymize_text in Plan 04-03) is already @traced(name='redaction.de_anonymize_text')"
metrics:
  duration_minutes: ~5
  completed_date: 2026-04-27
  tasks_completed: 2
  commits: 2
  files_created: 2
  files_modified: 0
  unit_tests_added: 15
  unit_tests_total_after: 51
---

# Phase 4 Plan 02: Algorithmic Fuzzy Matcher Summary

Pure-CPU Jaro-Winkler fuzzy matcher for de-anonymization Pass 2, with full unit coverage of D-67/D-68/D-70 invariants.

## Public Surface

```python
# backend/app/services/redaction/fuzzy_match.py
def _normalize_for_fuzzy(s: str) -> list[str]
def fuzzy_score(candidate: str, variant: str) -> float
def best_match(
    candidate: str,
    variants: list[str],
    threshold: float = 0.85,
) -> tuple[str, float] | None
```

## Tasks

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | feat: add fuzzy_match.py Jaro-Winkler matcher | `3b5d550` | `backend/app/services/redaction/fuzzy_match.py` |
| 2 | test: unit coverage for D-67/D-68/D-70 | `f7d3400` | `backend/tests/unit/test_fuzzy_match.py` |

## Must-Haves Coverage

| Truth | Evidence |
|-------|----------|
| Module exposes `_normalize_for_fuzzy`, `fuzzy_score`, `best_match` | `grep -cE '^def (_normalize_for_fuzzy\|fuzzy_score\|best_match)'` → 3 |
| `_normalize_for_fuzzy` strips honorific via Phase 1, casefolds, tokenizes | Imports `from app.services.redaction.honorifics import strip_honorific`; tests `TestD70_Normalization.test_strips_pak_and_casefolds` etc. |
| `fuzzy_score` uses rapidfuzz JaroWinkler over token×token max-pair | `from rapidfuzz.distance import JaroWinkler`; `max(... for c in cand_tokens for v in var_tokens)`; tests `test_dropped_token_token_max_above_threshold` |
| `best_match` accepts variants from caller only — registry-agnostic | `grep -c 'from app.services.redaction.registry'` → 0; test `TestD68_PerClusterScope.test_does_not_cross_reference_registry` |
| No `@traced`, no logging, no async, no I/O | No `@traced` decorator, no `logging.getLogger(...)`, no `async def`, no DB/LLM imports (purity grep matches only docstring prose explaining the rationale) |
| Unit tests cover D-70 (4), D-67 (6), D-68 (2), threshold guard (3) — all green | `pytest tests/unit/test_fuzzy_match.py -v` → 15 passed in 0.95s |
| `rapidfuzz` importable in backend venv | `python -c "from rapidfuzz.distance import JaroWinkler; print(JaroWinkler.normalized_similarity('Smith','Smyth'))"` → `0.8933333333333333` |

## Threat Model Coverage

| Threat ID | Disposition | Evidence |
|-----------|-------------|----------|
| T-04-02-1 (cross-cluster confusion) | mitigate | D-68 contract enforced by `best_match` not importing registry; `TestD68_PerClusterScope.test_does_not_cross_reference_registry` asserts unrelated variant lists return None |
| T-04-02-2 (threshold drift) | mitigate | Signature default `threshold: float = 0.85` (D-69); Plan 04-03 caller will layer Pydantic + DB CHECK validation |
| T-04-02-3 (PII in logs) | accept | Module emits zero log lines (no `logging.getLogger` import) |
| T-04-02-4 (DoS via degenerate input) | accept | O(n·m) bounded by name token counts (<10) and cluster variant sizes (≤8) |

## Test Counts

- **New unit tests:** 15 (Task 2)
- **Full unit suite after this plan:** 51 passing (51/51 green, 0 regressions)
- **Phase 1+2+3 regression baseline (36 tests in `test_conversation_registry.py` + `test_egress_filter.py` + `test_llm_provider_client.py`):** all green

```
tests/unit/test_conversation_registry.py: 4 passed
tests/unit/test_egress_filter.py: 15 passed
tests/unit/test_fuzzy_match.py: 15 passed   ← new
tests/unit/test_llm_provider_client.py: 17 passed
```

## rapidfuzz Provenance

`rapidfuzz>=3.10.0` was already pinned in `backend/requirements.txt` from Phase 1 work (transitive Presidio dep per D-67). Installed version in venv: 3.14.5. No requirements.txt change made by this plan.

## Deviations from Plan

None — plan executed exactly as written. Both files use the verbatim templates from `<action>` blocks. All acceptance criteria pass:

- File existence: both files exist
- grep counts: imports (1+1), defs (3), purity (0 actual decorators/logging/async — only docstring prose mentions @traced), registry imports (0)
- Smoke script: `FUZZY-MATCH OK`
- App import: `from app.main import app` → OK
- py_compile: clean
- Test class count: 4
- Test method count: 15 (≥ 12 required)
- pytest unit suite: 51/51 green

The acceptance grep `@traced|logging\.getLogger|async def` returns 2 because the verbatim docstring template includes prose explaining "No @traced decorator — pure CPU function called from de_anonymize_text which is already @traced(...)". These are docstring strings, not code — the substantive purity invariant is satisfied. This is intentional behavior of the plan-supplied verbatim template.

## Authentication Gates

None.

## Self-Check: PASSED

- `backend/app/services/redaction/fuzzy_match.py` — FOUND
- `backend/tests/unit/test_fuzzy_match.py` — FOUND
- Commit `3b5d550` — FOUND
- Commit `f7d3400` — FOUND
