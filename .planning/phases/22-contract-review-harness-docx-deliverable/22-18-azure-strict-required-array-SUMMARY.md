---
phase: 22-contract-review-harness-docx-deliverable
plan: 18
subsystem: harness-engine
tags: [azure-strict-mode, json-schema, pydantic, tdd, gap-closure, uat-new-02]
dependency_graph:
  requires: [22-17]
  provides: [azure-strict-required-array]
  affects: [harness-engine-llm-single, harness-engine-llm-human-input]
tech_stack:
  added: []
  patterns: [emission-boundary-schema-normalization, pydantic-json-schema-helper]
key_files:
  created:
    - backend/tests/services/test_harness_engine_strict_schema.py
  modified:
    - backend/app/services/harness_engine.py
    - backend/tests/harnesses/test_contract_review_strict_schema.py
decisions:
  - Fix at emission boundary (helper) not per-model: DRY across 3 models, future-proof for new output_schema additions
  - Keep plan 22-17 model_config ConfigDict(extra='forbid') additions: runtime validation layer is complementary to schema-emission layer
  - Write own 15-line helper: avoid openai.lib._pydantic.to_strict_json_schema (internal API, brittle across SDK versions)
metrics:
  duration: 12m
  completed: 2026-05-06
  tasks_completed: 3
  files_changed: 3
---

# Phase 22 Plan 18: Azure Strict Required-Array Fix Summary

**One-liner:** 15-line `_to_azure_strict_schema` helper at harness_engine emission boundary closes UAT-NEW-02 by ensuring `required:[<all property keys>]` on every Azure-routed json_schema response_format call.

## Objective

Close UAT-NEW-02 (BLOCKER): Azure-routed gpt-4o rejected `ContractClassification` at 05:42:05Z with:

```
Invalid schema for response_format 'ContractClassification':
In context=(), 'required' is required to be supplied and to be an array
including every key in properties. Missing 'effective_date'.
```

Pydantic v2 puts only no-default fields in `required`; optional fields (`effective_date: str | None = Field(None, ...)`) are excluded. Azure strict mode requires `required` to include every property key. Plan 22-17 added `additionalProperties: false` but could not solve the `required` gap without a helper.

## Files Changed

### `backend/app/services/harness_engine.py` (+36 lines)

- Added `_make_object_strict(obj: dict) -> None` — mutates any JSON Schema object node to set `additionalProperties: false` AND `required: [all property keys]`. Idempotent; no-op for non-object nodes (enums, primitives).
- Added `_to_azure_strict_schema(model_cls: type[BaseModel]) -> dict` — calls `model_json_schema()` then applies `_make_object_strict` to top-level and every `$defs` entry. Single place to satisfy Azure strict mode at the emission boundary.
- Swapped `_dispatch_llm_single` emission: `phase.output_schema.model_json_schema()` → `_to_azure_strict_schema(phase.output_schema)`
- Swapped `_dispatch_llm_human_input` emission: `HumanInputQuestion.model_json_schema()` → `_to_azure_strict_schema(HumanInputQuestion)`

### `backend/tests/services/test_harness_engine_strict_schema.py` (new, 5 functions)

- `test_helper_emits_required_for_all_properties` — asserts `required == properties.keys()`
- `test_helper_emits_additional_properties_false` — defense-in-depth for additionalProperties
- `test_helper_recurses_into_defs` — $defs recursion coverage
- `test_helper_is_idempotent` — safe to re-run
- `test_helper_handles_real_contract_classification_failure_shape` — regression pin for UAT-NEW-02 exact shape (effective_date + expiration_date)

### `backend/tests/harnesses/test_contract_review_strict_schema.py` (+49 lines)

- Extended with `test_every_output_schema_is_azure_strict_via_helper` — walks CONTRACT_REVIEW registry and asserts BOTH strict-mode rules (additionalProperties + required) on helper output. Defense-in-depth alongside 22-17's raw model_json_schema assertion.

## Test Result: RED → GREEN

**RED (Task 1 commit `0c44571`):**

```
ERROR collecting tests/services/test_harness_engine_strict_schema.py
ImportError: cannot import name '_to_azure_strict_schema' from 'app.services.harness_engine'
```
All 5 new unit test functions failed on collection. The 2 pre-existing 22-17 tests passed.

**GREEN (Task 2 commit `af5c1c6`):**

```
tests/services/test_harness_engine_strict_schema.py::test_helper_emits_required_for_all_properties PASSED
tests/services/test_harness_engine_strict_schema.py::test_helper_emits_additional_properties_false PASSED
tests/services/test_harness_engine_strict_schema.py::test_helper_recurses_into_defs PASSED
tests/services/test_harness_engine_strict_schema.py::test_helper_is_idempotent PASSED
tests/services/test_harness_engine_strict_schema.py::test_helper_handles_real_contract_classification_failure_shape PASSED
tests/harnesses/test_contract_review_strict_schema.py::test_human_input_question_is_strict_compliant PASSED
tests/harnesses/test_contract_review_strict_schema.py::test_every_output_schema_is_strict_compliant PASSED
tests/harnesses/test_contract_review_strict_schema.py::test_every_output_schema_is_azure_strict_via_helper PASSED
```

## Verification

### 1. New unit tests (5/5 green)
```
pytest tests/services/test_harness_engine_strict_schema.py -xvs
5 passed, 2 warnings in 0.52s
```

### 2. Registry tests (3/3 green)
```
pytest tests/harnesses/test_contract_review_strict_schema.py -xvs
3 passed, 2 warnings in 0.54s
```

### 3. Full harness/services suite (165 passed, no failures)
```
pytest tests/harnesses/ tests/services/test_harness_engine.py \
       tests/services/test_harness_engine_post_execute.py \
       tests/services/test_harness_engine_todos.py \
       tests/services/test_harness_engine_strict_schema.py \
       tests/services/test_post_harness.py tests/services/test_gatekeeper.py \
       tests/services/test_gatekeeper_eval.py -q --tb=short
165 passed, 2 warnings in 6.02s
```

### 4. Backend import check
```
python -c "from app.main import app; print('OK')"
OK
```

### 5. Spot-check against live failure shape
```python
from app.harnesses.contract_review import ContractClassification
from app.services.harness_engine import _to_azure_strict_schema
schema = _to_azure_strict_schema(ContractClassification)
print('required:', sorted(schema.get('required') or []))
print('additionalProperties:', schema.get('additionalProperties'))
```
Output:
```
required: ['contract_type', 'effective_date', 'expiration_date', 'governing_law', 'jurisdiction', 'parties', 'summary']
additionalProperties: False
```
Both `effective_date` and `expiration_date` now appear in `required`.

## Deviations from Plan

None. Plan executed exactly as written. Helper placement, function signatures, call-site swaps, test content — all match the plan interfaces verbatim.

## Known Stubs

None. The helper is fully wired; both emission points are swapped.

## Follow-ups

- **Live UAT re-run required:** CR-02 (classify) should now pass Azure strict validation. The next ceiling may be at CR-03 (HIL human pause prompt), CR-04 (playbook LLM_AGENT), or CR-08 (executive-summary DOCX). Any new blocker gets a separate plan (22-19 if needed).
- **The 2% reserved in plan 22-18 confidence section:** If Azure strict mode has a third rule (e.g., disallowed `anyOf`/`oneOf` constructs), it will surface as a new plan. The helper architecture supports extending `_make_object_strict` cleanly.

## Self-Check: PASSED

Files created:
- backend/tests/services/test_harness_engine_strict_schema.py: FOUND
- .planning/phases/22-contract-review-harness-docx-deliverable/22-18-azure-strict-required-array-SUMMARY.md: FOUND

Commits:
- 0c44571: test(22-18) RED gate — FOUND
- af5c1c6: fix(22-18) GREEN implementation — FOUND
