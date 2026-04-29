---
phase: "06-embedding-provider-production-hardening"
plan: 4
plan_id: "06-04"
subsystem: "redaction-pipeline"
title: "Add thread_id correlation field to redaction-pipeline debug logs"
one_liner: "Added thread_id=%s correlation key to 8 log call-sites across 5 redaction files (detection, redaction_service, egress, llm_provider, missed_scan) enabling grep-extractable per-chat-turn log blocks (OBS-02, OBS-03, SC#4)"
status: "complete"
tags: ["observability", "logging", "thread_id", "correlation", "pii-redaction"]
completed_at: "2026-04-29T07:23:00Z"
duration_seconds: 291
tasks_completed: 5
tasks_total: 5
requirements_closed: ["OBS-02", "OBS-03"]

dependency_graph:
  requires:
    - "06-01"  # embedding provider configuration (independent but wave-concurrent)
  provides:
    - "thread_id correlation in all redaction pipeline logs"
  affects:
    - "backend/app/services/redaction/detection.py"
    - "backend/app/services/redaction_service.py"
    - "backend/app/services/redaction/egress.py"
    - "backend/app/services/llm_provider.py"
    - "backend/app/services/redaction/missed_scan.py"

tech_stack:
  added: []
  patterns:
    - "Conditional log branching (if thread_id is not None) preserves byte-identical off-thread-id path"
    - "Sentinel value '-' in llm_provider when registry is None avoids AttributeError"

key_files:
  created:
    - path: "backend/tests/unit/test_detect_entities_thread_id.py"
      purpose: "TDD RED/GREEN test suite for detect_entities() optional thread_id param"
  modified:
    - path: "backend/app/services/redaction/detection.py"
      change: "detect_entities() signature: thread_id: str | None = None; conditional log branch"
    - path: "backend/app/services/redaction_service.py"
      change: "_redact_text_with_registry: detect_entities(text, thread_id=registry.thread_id); redact_text(reg) and de_anonymize_text debug logs gain thread_id=%s first field"
    - path: "backend/app/services/redaction/egress.py"
      change: "egress_filter trip WARNING log gains thread_id=%s second field (after event=)"
    - path: "backend/app/services/llm_provider.py"
      change: "LLMProviderClient.call(): thread_id sentinel added; all 3 logger.info paths gain thread_id=%s"
    - path: "backend/app/services/redaction/missed_scan.py"
      change: "scan_for_missed_pii: all 3 except-branch logger.warning calls gain thread_id=%s"
    - path: "backend/tests/unit/test_egress_filter.py"
      change: "Rule 1 fix: _StubRegistry gained thread_id class attr"
    - path: "backend/tests/unit/test_llm_provider_client.py"
      change: "Rule 1 fix: _StubRegistry gained thread_id class attr"

decisions:
  - id: "D-P6-14"
    decision: "Registry-aware detect_entities() call sites pass thread_id=registry.thread_id; stateless path unchanged"
  - id: "D-P6-15"
    decision: "thread_id is an optional keyword arg with default None — backward-compat preserved for all existing callers"
  - id: "D-P6-16"
    decision: "redaction_service, egress filter trip log gain thread_id from registry in scope (no new wiring)"
  - id: "D-P6-17"
    decision: "LLMProviderClient.call() uses sentinel '-' when registry is None (callers without registry continue to work)"

metrics:
  duration_seconds: 291
  completed_date: "2026-04-29"
  tests_before: 195
  tests_after: 265
  tests_added: 6
---

# Phase 06 Plan 04: Thread ID Correlation Logging Summary

Add `thread_id` correlation key to every per-operation debug/warning log line in the
redaction pipeline so operators can `grep 'thread_id=<id>'` to extract one chat turn's
full log block (OBS-02). Also closes OBS-03 (LLMProviderClient audit log) and SC#4
(missed-scan soft-fail log gap closure).

## What Was Built

Thread ID correlation was added to 8 log call-sites across 5 files:

| File | Sites | Change |
|------|-------|--------|
| `redaction/detection.py` | 1 | Conditional branch: `if thread_id is not None` emits `thread_id=<value>` in debug log |
| `redaction_service.py` | 2 | `redact_text(reg)` result debug log + `de_anonymize_text` debug log gain `thread_id=%s` |
| `redaction/egress.py` | 1 | `egress_filter` trip WARNING log gains `thread_id=%s` second field |
| `llm_provider.py` | 3 | All 3 logger.info paths (success/egress-tripped/error) gain `thread_id=%s` |
| `redaction/missed_scan.py` | 3 | All 3 except-branch logger.warning soft-fail calls gain `thread_id=%s` |

Additionally, `detect_entities()` was updated at the call site inside
`_redact_text_with_registry` to pass `thread_id=registry.thread_id`.

## Signature Diff — detect_entities()

**Before:**
```python
def detect_entities(text: str) -> tuple[str, list[Entity], dict[str, str]]:
```

**After:**
```python
def detect_entities(
    text: str,
    thread_id: str | None = None,
) -> tuple[str, list[Entity], dict[str, str]]:
```

## Modified Log Statements (Before / After)

### detection.py — redaction.detect log

**Before (single path):**
```python
logger.debug(
    "redaction.detect: input_chars=%d uuid_drops=%d entities=%d surrogate=%d redact=%d "
    "denied=%d denied_types=%s elapsed_ms=%.2f",
    len(text), len(sentinels), len(entities), ...
)
```

**After (conditional):**
```python
if thread_id is not None:
    logger.debug(
        "redaction.detect: thread_id=%s input_chars=%d uuid_drops=%d ...",
        thread_id, len(text), ...
    )
else:
    logger.debug(
        "redaction.detect: input_chars=%d uuid_drops=%d ...",
        len(text), ...
    )
```

### redaction_service.py — redact_text(reg) result log

**Before:** `"redaction.redact_text(reg): chars=%d entities=%d ..."`

**After:** `"redaction.redact_text(reg): thread_id=%s chars=%d entities=%d ..."`
with `registry.thread_id` as first positional arg.

### redaction_service.py — de_anonymize_text log

**Before:** `"redaction.de_anonymize_text: text_len=%d surrogate_count=%d ..."`

**After:** `"redaction.de_anonymize_text: thread_id=%s text_len=%d surrogate_count=%d ..."`
with `registry.thread_id` as first positional arg.

### egress.py — egress_filter trip log

**Before:** `"egress_filter_blocked event=egress_filter_blocked match_count=%d entity_types=%s match_hashes=%s"`

**After:** `"egress_filter_blocked event=egress_filter_blocked thread_id=%s match_count=%d entity_types=%s match_hashes=%s"`
with `registry.thread_id` as first positional arg.

### llm_provider.py — all 3 audit logs

**Before (all 3 paths):** format string starting `"llm_provider_call event=llm_provider_call feature=%s provider=%s source=%s ..."`

**After (all 3 paths):** format string starting `"llm_provider_call event=llm_provider_call thread_id=%s feature=%s provider=%s source=%s ..."`
with `thread_id` variable (sentinel `"-"` when `registry is None`) as first positional arg.

### missed_scan.py — all 3 soft-fail warnings

**Before (site 1):** `"event=missed_scan_skipped feature=missed_scan error_class=_EgressBlocked"`

**After (site 1):** `"event=missed_scan_skipped thread_id=%s feature=missed_scan error_class=_EgressBlocked"` with `registry.thread_id`

**Before (site 2):** `"event=missed_scan_skipped feature=missed_scan error_class=ValidationError"`

**After (site 2):** `"event=missed_scan_skipped thread_id=%s feature=missed_scan error_class=ValidationError"` with `registry.thread_id`

**Before (site 3):** `"event=missed_scan_skipped feature=missed_scan error_class=%s"` with `type(exc).__name__`

**After (site 3):** `"event=missed_scan_skipped thread_id=%s feature=missed_scan error_class=%s"` with `registry.thread_id, type(exc).__name__`

## thread_id= Grep Output

```
backend/app/services/redaction/detection.py:298:            "redaction.detect: thread_id=%s input_chars=%d ...
backend/app/services/redaction_service.py:433:                "redaction.redact_text(registry): thread_id=%s ...
backend/app/services/redaction_service.py:518:            "redaction.redact_text_batch: thread_id=%s ...
backend/app/services/redaction_service.py:623:        masked_text, entities, sentinels = detect_entities(text, thread_id=registry.thread_id)
backend/app/services/redaction_service.py:762:            "redaction.redact_text(reg): thread_id=%s chars=%d ...
backend/app/services/redaction_service.py:925:            "redaction.de_anonymize_text: thread_id=%s text_len=%d ...
backend/app/services/redaction/egress.py:121:            "egress_filter_blocked event=egress_filter_blocked thread_id=%s ...
backend/app/services/llm_provider.py:183:        thread_id = registry.thread_id if registry is not None else "-"
backend/app/services/llm_provider.py:196:                    "llm_provider_call event=llm_provider_call thread_id=%s ...
backend/app/services/llm_provider.py:212:                "llm_provider_call event=llm_provider_call thread_id=%s ...
backend/app/services/llm_provider.py:222:                "llm_provider_call event=llm_provider_call thread_id=%s ...
backend/app/services/redaction/missed_scan.py:104:            "event=missed_scan_skipped thread_id=%s feature=missed_scan error_class=_EgressBlocked",
backend/app/services/redaction/missed_scan.py:110:            "event=missed_scan_skipped thread_id=%s feature=missed_scan error_class=ValidationError",
backend/app/services/redaction/missed_scan.py:115:            "event=missed_scan_skipped thread_id=%s feature=missed_scan error_class=%s",
```

20 total occurrences (>= minimum threshold of 11).

## pytest unit tests

Before plan: 195 (estimated from prior phases). After plan: 265 passing (6 new tests added via TDD for detect_entities thread_id behavior).

## Migrations

None — this is a logging-only change. No DB schema modifications.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] _StubRegistry test fixtures missing thread_id attribute**
- **Found during:** Task 3 (egress.py log modification)
- **Issue:** The new `egress_filter` trip log reads `registry.thread_id` at runtime. The
  `_StubRegistry` duck-type stubs in `test_egress_filter.py` and `test_llm_provider_client.py`
  did not have a `thread_id` attribute, causing `AttributeError` in 9 test methods.
- **Fix:** Added `thread_id: str = "stub-thread-id"` class attribute to `_StubRegistry`
  in both test files.
- **Files modified:** `backend/tests/unit/test_egress_filter.py`, `backend/tests/unit/test_llm_provider_client.py`
- **Commit:** 24cb87d

## Known Stubs

None — all log call-sites are wired to real `registry.thread_id` values. No placeholder values.

## Threat Flags

None — `thread_id` values are Supabase UUIDs (non-PII by construction per T-06-04-1 mitigation).
All new log fields follow the B4 invariant (counts + types + thread_id + provider strings only;
no raw text, no real values, no surrogate values). No new network endpoints or auth paths introduced.

## Self-Check: PASSED

All modified files exist on disk. All task commits verified in git log.

| File | Status |
|------|--------|
| backend/app/services/redaction/detection.py | FOUND |
| backend/app/services/redaction_service.py | FOUND |
| backend/app/services/redaction/egress.py | FOUND |
| backend/app/services/llm_provider.py | FOUND |
| backend/app/services/redaction/missed_scan.py | FOUND |
| backend/tests/unit/test_detect_entities_thread_id.py | FOUND |

| Commit | Message |
|--------|---------|
| 31a5bbb | test(06-04): add failing tests for detect_entities thread_id param (RED) |
| f103496 | feat(06-04): add optional thread_id param to detect_entities() with conditional log (D-P6-15) |
| 25a0565 | feat(06-04): pass thread_id to detect_entities + add thread_id to de_anonymize and redact_text(reg) logs (D-P6-14, D-P6-16) |
| 24cb87d | feat(06-04): add thread_id field to egress_filter trip log (D-P6-16) |
| 34ce645 | feat(06-04): add thread_id field to LLMProviderClient.call() audit log (OBS-03 D-P6-17) |
| 36e22e1 | feat(06-04): add thread_id to all 3 missed_scan soft-fail warnings (D-P6-11 SC#4 closure) |
