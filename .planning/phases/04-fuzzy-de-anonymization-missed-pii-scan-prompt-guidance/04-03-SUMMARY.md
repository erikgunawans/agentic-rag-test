---
phase: 04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance
plan: 03
subsystem: redaction
tags: [pii, de-anonymization, fuzzy-deanon, 3-phase-pipeline, llm-provider, placeholder-tokenization]
requirements_addressed: [DEANON-03, DEANON-04, DEANON-05]
dependency_graph:
  requires:
    - "Plan 04-01 settings: fuzzy_deanon_mode + fuzzy_deanon_threshold (60s TTL cache per Phase 2 D-21)"
    - "Plan 04-02 fuzzy_match.best_match (Jaro-Winkler matcher, D-67/D-68/D-70)"
    - "Phase 3 LLMProviderClient.call(feature='fuzzy_deanon', ...) + _EgressBlocked"
    - "Phase 2 ConversationRegistry.entries() + EntityMapping.cluster_id (Phase 3 D-48)"
  provides:
    - "RedactionService.de_anonymize_text 3-phase pipeline with optional mode kwarg"
    - "Frozen contracts for Plan 04-07 integration tests (TestSC1/TestSC2/TestSC3/TestB4_LogPrivacy)"
  affects:
    - "Plan 5 SSE de-anon site can opt into fuzzy mode by passing mode='algorithmic' or 'llm'"
    - "Phase 2 round-trip callers (DEANON-01/DEANON-02) unchanged — mode=None default preserves behavior"
tech_stack:
  added: []
  patterns:
    - "Optional mode parameter with Settings fallback (D-71)"
    - "Pydantic _FuzzyMatchResponse with regex-pinned token + extra=forbid + max_length=50 (D-73)"
    - "Soft-fail triple-catch (_EgressBlocked / ValidationError / Exception) — never raises (D-78)"
    - "Server-side token membership validation (LLM cannot inject foreign-cluster tokens)"
    - "Per-cluster best_match scoping with cluster_id grouping (D-68)"
    - "D-74 belt-and-suspenders hard-redact survival (skip <<PH_*>> + [ENTITY_TYPE] in chunk iterator)"
    - "Right-to-left replacement to preserve offsets across multiple matches"
key_files:
  created: []
  modified:
    - backend/app/services/redaction_service.py
decisions:
  - "D-71: mode kwarg defaults to None → resolves via get_settings().fuzzy_deanon_mode; backward compat with Phase 2 callers preserved (105/105 GREEN with mode unset)"
  - "D-72: mode dispatch lives in de_anonymize_text body; algorithmic and LLM branches selectable via single kwarg"
  - "D-73: cloud LLM payload = Pass-1-output text (real values already replaced by <<PH_xxxx>>) + JSON variant list (surrogate-form only); Pydantic schema regex-pins token to ^<<PH_[0-9a-f]+>>$; server validates token ∈ Pass-1 placeholders dict (drops fabricated tokens)"
  - "D-74: hard-redact [ENTITY_TYPE] survival is STRUCTURAL (Phase 2 D-24/REG-05 — never in registry) + belt-and-suspenders (algorithmic chunk skip + LLM-mode bracket-span filter)"
  - "D-78: soft-fail catches _EgressBlocked / ValidationError / Exception; falls back to algorithmic Pass 2 when settings.llm_provider_fallback_enabled=True (D-52); else skips Pass 2 entirely; WARNING log carries error_class only (B4)"
  - "Tracing pattern: codebase has no current_span().set_attribute API; matches established redact_text pattern of structured logger.debug emission with mode + counts (B4 invariant honored)"
metrics:
  duration_minutes: 12
  tasks_completed: 2
  files_modified: 1
  commits: 2
  tests_pass: "105/105"
  completed_date: 2026-04-27
---

# Phase 4 Plan 03: de_anonymize_text 3-Phase Upgrade Summary

**One-liner:** In-place upgrade of `RedactionService.de_anonymize_text` to a 3-phase placeholder-tokenized pipeline (Pass 1 surrogate→<<PH_xxxx>>, Pass 2 fuzzy/LLM-match against cluster variants, Pass 3 placeholder→real_value) with optional mode kwarg, soft-fail fallback, and structural hard-redact survival.

## What Shipped

### Signature Change (Task 1, commit `ce9fd5f`)

```python
@traced(name="redaction.de_anonymize_text")
async def de_anonymize_text(
    self,
    text: str,
    registry: ConversationRegistry,
    mode: Literal["algorithmic", "llm", "none"] | None = None,  # NEW (D-71)
) -> str
```

`mode=None` → resolves via `get_settings().fuzzy_deanon_mode` (default `'none'`). Phase 2 callers (DEANON-01/DEANON-02) pass no mode arg; behavior identical to pre-Phase-4.

### Pydantic Models (Task 1)

Two new module-scope models with `extra="forbid"`:

- `_FuzzyMatch`: `span` (1..500 chars) + `token` (regex `^<<PH_[0-9a-f]+>>$`)
- `_FuzzyMatchResponse`: `matches` list capped at 50

### Pass 2 Dispatch (Task 2, commit `da86211`)

Splice between existing Pass 1 (lines 700-713) and Pass 3 (lines 729-733):

```python
if mode == "algorithmic":
    out, fuzzy_matches_resolved = self._fuzzy_match_algorithmic(
        out, registry, placeholders, threshold
    )
elif mode == "llm":
    out, fuzzy_matches_resolved, fuzzy_provider_fallback = (
        await self._fuzzy_match_llm(out, registry, placeholders)
    )
# else mode == "none" → skip Pass 2 entirely (Phase 2 behavior preserved).
```

### New Helper Methods on RedactionService (Task 2)

| Method | Sync/Async | Purpose |
|---|---|---|
| `_fuzzy_match_algorithmic` | sync | D-72 algorithmic branch — group by cluster_id, per-cluster `best_match` against surrogate variants, replace mangled spans with the cluster's `<<PH_xxxx>>` token; right-to-left replacement preserves offsets |
| `_fuzzy_match_llm` | async | D-72/D-73 LLM branch — build messages (placeholder-tokenized text + JSON variant list), call `LLMProviderClient.call(feature='fuzzy_deanon', registry=registry, provisional_surrogates=None)`, Pydantic-validate, server-validate `match.token ∈ placeholders.keys()`, soft-fail per D-78 |

### Soft-Fail Triple-Catch (D-78)

```python
except _EgressBlocked:
    logger.warning("event=fuzzy_deanon_skipped feature=fuzzy_deanon error_class=_EgressBlocked")
    if settings.llm_provider_fallback_enabled:
        # algorithmic fallback
    return text, 0, True
except (ValidationError, Exception) as exc:
    logger.warning("event=fuzzy_deanon_skipped feature=fuzzy_deanon error_class=%s", type(exc).__name__)
    # same fallback logic
```

Method **never** re-raises to the chat loop. Logs carry `error_class` only — never raw text, span values, or registry contents (B4 invariant honored).

### Hard-Redact Survival (D-74)

- **Structural:** `[ENTITY_TYPE]` placeholders are never in registry per Phase 2 D-24/REG-05 → Pass 1 cannot mint them → not resolved by Pass 3.
- **Belt-and-suspenders (algorithmic):** chunk iterator skips `^<<PH_[0-9a-f]+>>$` and `^\[[A-Z_]+\]$` patterns.
- **Belt-and-suspenders (LLM):** server validates `match.token ∈ Pass-1 placeholders.keys()` (drops fabricated tokens) AND drops match spans matching `\[[A-Z_]+\]`.

### Tracing / Observability

Span attributes via the established structured-log pattern (codebase has **no** `current_span().set_attribute(...)` API — matches `redact_text` precedent):

```python
logger.debug(
    "redaction.de_anonymize_text: text_len=%d surrogate_count=%d "
    "placeholders_resolved=%d fuzzy_deanon_mode=%s "
    "fuzzy_matches_resolved=%d fuzzy_provider_fallback=%s ms=%.2f",
    ...
)
```

Counts and mode strings only — never raw values, surrogate values, or matched spans (B4 invariant).

## must_haves Coverage

| Truth | Status |
|---|---|
| `mode` kwarg with Settings fallback (D-71); Phase 2 callers unchanged | OK — sig has `mode: ... \| None = None`; 105/105 GREEN |
| 3-phase pipeline runs; mode='none' bypasses Pass 2 | OK — splice in place; `else` branch leaves text unchanged |
| Algorithmic branch: cluster_id grouping + best_match + per-cluster variants + threshold from Settings | OK — `_fuzzy_match_algorithmic` |
| LLM branch: placeholder-tokenized messages + JSON variant list + LLMProviderClient.call(feature='fuzzy_deanon', provisional=None); zero raw values; egress filter wraps | OK — `_fuzzy_match_llm` |
| Pydantic `_FuzzyMatchResponse` validation + server token membership check | OK — `model_validate` + `match.token in valid_tokens` |
| Soft-fail D-78 triple-catch + log error_class only + algorithmic fallback gated on `llm_provider_fallback_enabled` | OK — both `_EgressBlocked` and `(ValidationError, Exception)` caught |
| Hard-redact `[ENTITY_TYPE]` survival in all 3 modes (D-74 structural + belt-and-suspenders) | OK — structural via D-24/REG-05; algorithmic skip via `hard_redact_re`; LLM skip via `re.fullmatch` |
| Phase 2 DEANON-01/DEANON-02 round-trip remain GREEN | OK — 105/105 pytest |
| Span attributes: fuzzy_deanon_mode + fuzzy_matches_resolved (counts only) | OK — emitted via `logger.debug` (codebase pattern; see Deviations) |

## Threat Model Coverage

| Threat ID | Disposition | Mitigation in this plan |
|---|---|---|
| T-04-03-1 (raw PII to cloud LLM) | mitigate | D-73 placeholder-tokenization invariant (cloud payload = post-Pass-1 text + variant list of surrogate-form strings); Phase 3 D-53..D-56 egress filter wraps `LLMProviderClient.call` |
| T-04-03-2 (LLM injects foreign placeholder token) | mitigate | Pydantic regex `^<<PH_[0-9a-f]+>>$` + server-side `match.token ∈ placeholders.keys()` membership check |
| T-04-03-3 (hard-redact leak) | mitigate | Structural (D-24/REG-05) + algorithmic chunk skip + LLM-mode bracket-span filter |
| T-04-03-4 (provider failure crashes chat) | mitigate | Triple-catch + soft-fail; method NEVER raises |
| T-04-03-5 (raw value in span attrs) | mitigate | logger.debug emits counts + mode strings only; no real values, no surrogate values, no matched spans |

## Acceptance Criteria

| Check | Result |
|---|---|
| `grep -c '^class _FuzzyMatch(BaseModel):'` == 1 | PASS (1) |
| `grep -c '^class _FuzzyMatchResponse(BaseModel):'` == 1 | PASS (1) |
| `grep -c 'pattern=r"\^<<PH_\[0-9a-f\]+>>\$"'` == 1 | PASS (1) |
| `grep -c 'from app.services.redaction.fuzzy_match import best_match'` == 1 | PASS (1) |
| `grep -c '\| None = None'` for mode signature | PASS (1) |
| `grep -c 'def _fuzzy_match_algorithmic\('` == 1 | PASS (1) |
| `grep -c 'async def _fuzzy_match_llm\('` == 1 | PASS (1) |
| `grep -c 'feature="fuzzy_deanon"'` >= 1 | PASS (1) |
| `grep -c '_EgressBlocked'` >= 2 | PASS (6) |
| `grep -c 'event=fuzzy_deanon_skipped'` >= 2 | PASS (2) |
| `grep -c 'llm_provider_fallback_enabled'` >= 1 | PASS (3) |
| `grep -c 'mode == "algorithmic"'` >= 1 | PASS (2) |
| `grep -c 'mode == "llm"'` >= 1 | PASS (2) |
| `grep -c 'hard_redact_re'` >= 1 | PASS (2) |
| `python -c "from app.main import app"` | PASS |
| `pytest tests/ -x` | PASS — 105/105 |

## Deviations from Plan

### Auto-Adjusted (Rule 3 — No Existing API)

**1. [Rule 3 - Missing Helper API] Span attributes via structured log instead of `current_span().set_attribute(...)`**

- **Found during:** Task 2 verification (acceptance criteria checked `set_attribute("fuzzy_deanon_mode"`).
- **Issue:** The plan's Step 4 specified `from app.services.tracing_service import current_span; span = current_span(); span.set_attribute(...)`. The actual `tracing_service.py` exports only `configure_tracing()` and `traced(...)` decorator — no `current_span()` function, no codebase-wide `set_attribute` usage (`grep -rn "set_attribute\|current_span" backend/app/` returns empty).
- **Fix:** Match the established pattern from `redact_text` (lines 604-622 of redaction_service.py): emit mode + counts via `logger.debug(...)` structured log line. The plan's Step 4 explicitly authorized this fallback ("If the existing codebase uses a different tracing API for span-attribute access — e.g., a context manager or a `traced(...)` return value — match that pattern from redaction_service.py's existing redact_text instrumentation").
- **Files modified:** `backend/app/services/redaction_service.py` (existing `logger.debug` block in `de_anonymize_text` updated to include `fuzzy_deanon_mode`, `fuzzy_matches_resolved`, `fuzzy_provider_fallback`).
- **B4 invariant honored:** counts + mode strings only; no real values, no surrogate values, no matched spans.
- **Commit:** `da86211`.

No other deviations. Plan executed as written.

## Authentication Gates

None.

## Known Stubs

None — all code paths are wired and exercised by Phase 2 round-trip tests (mode=None default).

## Self-Check: PASSED

- File `backend/app/services/redaction_service.py`: FOUND
- Commit `ce9fd5f` (Task 1): FOUND in `git log`
- Commit `da86211` (Task 2): FOUND in `git log`
- pytest 105/105: PASS
- `python -c "from app.main import app"`: PASS
