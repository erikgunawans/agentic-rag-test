---
phase: 05-chat-loop-integration-buffering-sse-status-tool-sub-agent-co
plan: "07"
subsystem: pii-redaction-egress
tags: [pii-redaction, egress-filter, d-48-variants, gap-closure, blocker, registry]
dependency_graph:
  requires: []
  provides: [canonical-only-egress-filter, ConversationRegistry.canonicals]
  affects: [backend/app/services/redaction/egress.py, backend/app/services/redaction/registry.py]
tech_stack:
  added: []
  patterns: [longest-real-value-per-surrogate aggregation, O(n)-one-pass canonical selection]
key_files:
  created: []
  modified:
    - backend/app/services/redaction/registry.py
    - backend/app/services/redaction/egress.py
    - backend/tests/unit/test_egress_filter.py
decisions:
  - "D-48 invariant: canonical is always the longest real_value per surrogate; canonicals() uses longest-wins O(n) one-pass aggregation"
  - "Variants stay in entries() and the DB for D-72 Pass 2 fuzzy de-anonymization; they are excluded only from egress candidates"
  - "_StubRegistry in tests updated to expose canonicals() matching entries() passthrough — no test behavior change for existing tests"
  - "New tests use real ConversationRegistry (not stub) to exercise actual canonicals() invariant logic"
metrics:
  duration: "~10 minutes"
  completed: "2026-04-28"
  tasks_completed: 3
  tasks_total: 3
  files_changed: 3
---

# Phase 05 Plan 07: Canonical-Only Egress Filtering — D-48 Variant Cascade Fix Summary

## One-liner

Structural fix for multi-turn chat blocker: egress filter now scans canonical real values only (longest per surrogate), excluding D-48 sub-variants that caused false-positive trip cascades on legal vocabulary in production thread bf1b7325.

## What Was Built

### Task 1: ConversationRegistry.canonicals() method

Added `canonicals()` to `backend/app/services/redaction/registry.py` immediately after `entries()` (line 151). The method performs an O(n) one-pass aggregation over `self._rows`, keeping one `EntityMapping` per unique `surrogate_value` — the one with the longest `real_value`. This is the D-48 invariant in code: all D-48 variants share the canonical's surrogate, and the canonical is always the longest real_value because variants are derived by subtraction (first-only, last-only, honorific-prefixed).

The method returns a new list each call (callers cannot mutate internal state). `entries()` is unchanged.

### Task 2: Switch egress_filter to canonical-only scan

Modified `backend/app/services/redaction/egress.py` to call `registry.canonicals()` instead of `registry.entries()` when building the egress candidate list. The provisional surrogates path (in-flight PERSON-only set from D-56) is unchanged.

Updated the module docstring to document that the egress filter now scans `registry.canonicals()` and explicitly notes that D-48 sub-surrogate variants are excluded, with a reference to the Plan 05-07 gap-closure rationale.

Also updated `_StubRegistry` in the test file to expose a `canonicals()` method (passthrough to the same mappings as `entries()`, since existing tests have no variants). This keeps all 15 existing `TestEgressFilter` tests passing.

### Task 3: TestD48VariantCascade regression suite

Added `TestD48VariantCascade` class to `backend/tests/unit/test_egress_filter.py` with three tests:

1. **test_variant_only_match_does_not_trip** — Registry with canonical "Confidentiality Clause" + variants "Confidentiality" + "Clause" (all sharing surrogate "S1"). Payload contains standalone "confidentiality" mid-sentence. After fix: `tripped is False`. This is the exact UAT scenario from thread bf1b7325.

2. **test_canonical_leak_still_trips** — Same registry. Payload contains the full canonical phrase "confidentiality clause". After fix: `tripped is True`, `match_count == 1`. Privacy invariant preserved.

3. **test_canonicals_picks_longest_real_value_per_surrogate** — Direct unit test of `canonicals()`: registry with "Ahmad Suryadi" (len 13), "Suryadi" (len 7), "Ahmad" (len 5) — all sharing surrogate "Aurora Natsir". Asserts `canonicals()` returns exactly one entry with `real_value == "Ahmad Suryadi"`.

Tests use real `ConversationRegistry` (not `_StubRegistry`) to exercise actual invariant logic.

## Test Results

```
18 passed, 1 warning in 0.57s
  - TestEgressFilter: 15 tests (all existing — regression clean)
  - TestD48VariantCascade: 3 tests (new regression suite — all green)
```

## Commits

| Task | Commit | Message |
|------|--------|---------|
| 1    | 026b95c | fix(05-07): add ConversationRegistry.canonicals() for D-48 gap-closure |
| 2    | f3bfcaf | fix(05-07): switch egress_filter to canonical-only scan (D-48 variant cascade fix) |
| 3    | 03b8578 | test(05-07): add TestD48VariantCascade regression suite |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Functionality] Updated _StubRegistry to expose canonicals()**
- **Found during:** Task 2 — switching egress_filter to call canonicals() would have broken all 15 existing tests since _StubRegistry only had entries()
- **Issue:** _StubRegistry duck-typed stub lacked canonicals() method required by the updated egress_filter
- **Fix:** Added canonicals() to _StubRegistry returning same mappings as entries() (passthrough — correct behavior since existing test fixtures have no variants)
- **Files modified:** backend/tests/unit/test_egress_filter.py
- **Committed with:** Task 2 commit (f3bfcaf) — logically grouped since it was a prerequisite for existing tests to remain green

No other deviations. Plan executed as specified.

## Known Stubs

None — all new code is fully implemented with no placeholder values.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. The change is entirely in-process (in-memory registry reads). The egress boundary is the same function; only the candidate construction logic changed. No new threat flags.

## Self-Check: PASSED

- backend/app/services/redaction/registry.py — FOUND (contains `def canonicals`)
- backend/app/services/redaction/egress.py — FOUND (contains `registry.canonicals()`)
- backend/tests/unit/test_egress_filter.py — FOUND (contains `TestD48VariantCascade`)
- Commit 026b95c — FOUND
- Commit f3bfcaf — FOUND
- Commit 03b8578 — FOUND
- 18/18 tests passing
