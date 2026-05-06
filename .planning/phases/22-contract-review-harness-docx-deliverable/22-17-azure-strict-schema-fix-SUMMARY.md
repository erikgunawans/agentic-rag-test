---
phase: 22-contract-review-harness-docx-deliverable
plan: 17
subsystem: harness-engine
tags: [gap-closure, tdd, pydantic, azure-strict-mode, uat-new-01]
dependency_graph:
  requires: []
  provides: [azure-strict-schema-compliant-output-models]
  affects: [harness-engine-llm-single-dispatch, harness-engine-hil-dispatch]
tech_stack:
  added: []
  patterns: [pydantic-v2-model-config-extra-forbid]
key_files:
  created:
    - backend/tests/harnesses/test_contract_review_strict_schema.py
  modified:
    - backend/app/harnesses/contract_review.py
    - backend/app/services/harness_engine.py
decisions:
  - "Fixed the import name mismatch: plan specified HARNESS_CONTRACT_REVIEW but actual export is CONTRACT_REVIEW — test was corrected to use the real name (auto-fix Rule 1)"
  - "model_config placed after the docstring and before the first Field, matching Pydantic v2 idiom"
metrics:
  duration: 12m
  completed_date: 2026-05-06T04:58:47Z
  tasks_completed: 3
  files_changed: 3
---

# Phase 22 Plan 17: Azure Strict-Mode Schema Fix Summary

Closed UAT-NEW-01 (BLOCKER): three Pydantic models passed to OpenRouter as `response_format` with `strict: True` were missing `additionalProperties: false`, causing HTTP 400 from Azure's gpt-4o deployment on every CR-02 (classify) and CR-08 (executive-summary) invocation. Added `model_config = ConfigDict(extra="forbid")` to `ContractClassification`, `ExecutiveSummary`, and `HumanInputQuestion`; a registry-walking regression test guards against future drift.

## Objective

Close UAT-NEW-01: Azure strict-mode schema validation blocker. The three models used in OpenRouter `response_format=json_schema` with `strict: True` emitted no `additionalProperties` key in their JSON schema. Azure's gpt-4o deployment enforces that `additionalProperties: false` is explicitly present and rejects schemas that omit it with HTTP 400. OpenAI direct is lenient; Azure is not. OpenRouter routes opportunistically so the bug surfaces intermittently in production.

## Files Changed

| File | Change |
|------|--------|
| `backend/app/harnesses/contract_review.py` | Added `ConfigDict` to pydantic import; added `model_config = ConfigDict(extra="forbid")` to `ContractClassification` and `ExecutiveSummary` |
| `backend/app/services/harness_engine.py` | Added `ConfigDict` to pydantic import; added `model_config = ConfigDict(extra="forbid")` to `HumanInputQuestion` |
| `backend/tests/harnesses/test_contract_review_strict_schema.py` | New registry-walking regression test for Azure strict-mode schema compliance |

## TDD Gate Compliance

| Gate | Commit | Status |
|------|--------|--------|
| RED  | `09c2671` | PASS — both tests failed as expected (assertion error naming all 3 models) |
| GREEN | `693f5e8` | PASS — both tests pass; 159/159 full suite green |

### RED Output (before fix)

```
FAILED tests/harnesses/test_contract_review_strict_schema.py::test_human_input_question_is_strict_compliant
AssertionError: HumanInputQuestion schema (or one of its $defs) is missing
additionalProperties: false. Azure strict mode will reject this.
assert None is False
```

### GREEN Output (after fix)

```
tests/harnesses/test_contract_review_strict_schema.py::test_human_input_question_is_strict_compliant PASSED
tests/harnesses/test_contract_review_strict_schema.py::test_every_output_schema_is_strict_compliant PASSED
2 passed, 2 warnings in 0.48s
```

## Verification

### 1. Spot-check JSON schema output

```
  ContractClassification     additionalProperties: False
  ExecutiveSummary           additionalProperties: False
  HumanInputQuestion         additionalProperties: False
```

All three models now emit `additionalProperties: False`.

### 2. Full harness + service test suite

```
159 passed, 2 warnings in 4.14s
```

Zero regressions across all harness and service tests.

### 3. Backend import check

```
OK
```

`from app.main import app` imports cleanly.

### 4. Scope guard verification

Only 3 files modified. `ClauseExtractionResult`, `PlaybookContext`, `PlaybookDoc`, `Clause`, `ClauseRisk`, `RedlineCandidate`, `Redline`, and `RiskGrade` are untouched.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Import name mismatch: HARNESS_CONTRACT_REVIEW vs CONTRACT_REVIEW**
- **Found during:** Task 1 (RED phase — collection error)
- **Issue:** Plan specified `from app.harnesses.contract_review import HARNESS_CONTRACT_REVIEW` but the actual module exports the variable as `CONTRACT_REVIEW` (verified via grep on contract_review.py and existing tests in test_contract_review_cr06_cr07.py)
- **Fix:** Corrected test to import `CONTRACT_REVIEW` and reference `CONTRACT_REVIEW.phases`
- **Files modified:** `backend/tests/harnesses/test_contract_review_strict_schema.py`
- **Impact:** Test behavior unchanged — walks same registry, same coverage

## Commits

| Task | Commit | Message |
|------|--------|---------|
| Task 1 (RED) | `09c2671` | `test(22-17): add failing regression test for Azure strict-mode schema compliance` |
| Task 2 (GREEN) | `693f5e8` | `fix(22-17): add model_config extra='forbid' to output_schema models for Azure strict mode` |

## Follow-ups

The live UAT re-run is now unblocked at CR-02. Any new failure surfaced at CR-03 (HIL prompt), CR-04 (playbook), CR-05 (clauses), CR-06 (risk), or CR-08 (executive summary) is a separate plan, not a defect in 22-17.

If OpenRouter's Azure routing surfaces additional strictness requirements beyond `additionalProperties: false` (e.g., `required` on every nullable field, or mandatory `description` annotations), those will be addressed in a follow-up gap-closure plan.

## Self-Check: PASSED

- `backend/tests/harnesses/test_contract_review_strict_schema.py` — exists, 2 tests, both GREEN
- `09c2671` — confirmed in git log (RED test commit)
- `693f5e8` — confirmed in git log (GREEN fix commit)
- 159/159 tests pass (full harness + service suite)
- Backend import OK
