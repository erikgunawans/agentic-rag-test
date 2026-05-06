---
phase: 22-contract-review-harness-docx-deliverable
plan: 19
subsystem: harness-engine / contract-review
tags: [gap-closure, uat-new-03, clause-index, redlines, empty-batch, cr06, cr07, cr08]
dependency_graph:
  requires: [22-18]
  provides: [UAT-NEW-03-fix, CR-06-grounding, CR-07-empty-write, CR-08-empty-prompt]
  affects: [contract_review.py, harness_engine.py]
tech_stack:
  added: []
  patterns: [engine-level-empty-batch-short-circuit, tdd-red-green]
key_files:
  created:
    - backend/tests/harnesses/test_contract_review_empty_redlines.py
  modified:
    - backend/app/harnesses/contract_review.py
    - backend/app/services/harness_engine.py
decisions:
  - "Layer B implemented as Path A (engine-level LLM_BATCH_AGENTS short-circuit on items_total==0) — more general than CR-07 post_execute hook, benefits any future LLM_BATCH_AGENTS phase"
  - "Empty-batch write path uses merged_path (redlines.json) directly with content '[]' — bypasses _merge_jsonl_to_json which is a no-op when JSONL never existed"
metrics:
  duration: ~20 minutes
  completed_date: "2026-05-06"
  tasks_completed: 3
  files_changed: 3
---

# Phase 22 Plan 19: Clause-Index Grounding and Empty Redlines SUMMARY

**One-liner:** Two-layer fix for UAT-NEW-03 — CR-06 prompt now grounds `clause_index` to input verbatim (Layer A), and the LLM_BATCH_AGENTS engine short-circuits on empty input to always write `workspace_output=[]` (Layer B), unblocking CR-08 workspace read.

## Objective

Close UAT-NEW-03 (BLOCKER from live UAT round 3, 2026-05-06 13:32:58 UTC): CR-08 executive-summary failed with `"workspace read failed"` because `redlines.json` was never written. Root cause: CR-06 LLM emitted `clause_index: 185` for a contract with only ~7 clauses; the filter join dropped all candidates; CR-07 saw empty input and the engine skipped the workspace_output write entirely.

## Layer A — CR-06 Prompt Grounding

Added a `CRITICAL — clause_index grounding` block to the CR-06 `system_prompt_template` in `contract_review.py` (inserted between the `\`\`\`` output spec closing and the "Stay focused" line). The block:

- Instructs the LLM to echo `clause_index` verbatim from the input clause object
- Explicitly forbids line numbers, character offsets, page numbers, and paragraph counts as index sources
- Provides a concrete example: "input clause has 'clause_index': 3, output JSON has 'clause_index': 3"

## Layer B — Engine-Level Empty-Batch Short-Circuit (Path A chosen)

**Implementation choice: Path A (engine-level)** over Path B (CR-07 post_execute hook).

**Reason:** The LLM_BATCH_AGENTS empty-batch case is a general engine concern. The existing `if not remaining:` branch at line 1091 (harness_engine.py) correctly handles "all items previously completed" via `_merge_jsonl_to_json`, but that function is a no-op when no JSONL file exists (early return on read-error at line 1396-1397). The fix adds an explicit `items_total == 0` check BEFORE the `remaining` check:

```python
if items_total == 0:
    # Plan 22-19 / UAT-NEW-03: empty input batch — write workspace_output as []
    if phase.workspace_output:
        await ws.write_text_file(thread_id, merged_path, "[]", source="harness")
    yield {"_terminal_phase_result": {"text": "Empty input batch — wrote workspace_output as []"}}
    return
```

This benefits any future LLM_BATCH_AGENTS phase (not just CR-07), and is surgically minimal.

## Layer B Containment — CR-08 Prompt

Added an explicit empty-redlines hint to the CR-08 `system_prompt_template`:

```
If redlines.json is an empty array [], ACKNOWLEDGE it explicitly:
  'No clauses warranted redlines under the current playbook + review context.'
Then proceed to summarize classification + risk grades from clauses.md and
risk-analysis.json. The ExecutiveSummary is still required (overall_risk,
recommendation, key_findings, risk_breakdown, next_steps).
```

## Test Result (RED → GREEN)

**Task 1 (RED):** 4 tests collected — 1 pass (filter pins REVIEW #3), 2 fail (prompt asserts), 1 skip (integration scaffold).

**Task 2 (GREEN):** 4/4 pass:
- `test_filter_drops_hallucinated_clause_index_keeps_valid_one` — PASS (pre-existing, pinned)
- `test_cr06_prompt_grounds_clause_index_to_input` — PASS (Layer A)
- `test_empty_redline_candidates_produces_empty_redlines_json` — PASS (Layer B, engine path)
- `test_cr08_prompt_handles_empty_redlines` — PASS (Layer B containment)

## Verification Commands and Output

**1. Regression test suite:**
```
pytest tests/harnesses/test_contract_review_empty_redlines.py -v
4 passed, 2 warnings in 0.51s
```

**2. Full harness/services suite:**
```
pytest tests/harnesses/ tests/services/test_harness_engine.py \
       tests/services/test_harness_engine_post_execute.py \
       tests/services/test_harness_engine_todos.py \
       tests/services/test_harness_engine_strict_schema.py \
       tests/services/test_post_harness.py \
       tests/services/test_gatekeeper_eval.py \
       tests/services/test_gatekeeper.py -q --tb=short
169 passed, 2 warnings in 3.87s
```

**3. Backend import check:**
```
python -c "from app.main import app; print('OK')"
OK
```

**4. CR-06 prompt spot-check:**
```
python3 -c "
from app.harnesses.contract_review import CONTRACT_REVIEW
p = next(p for p in CONTRACT_REVIEW.phases if p.name == 'risk-analysis').system_prompt_template
for needle in ['echo', 'clause_index', 'line number', 'character offset', 'page number']:
    assert needle in p.lower(), f'missing: {needle}'
print('CR-06 prompt grounding present — all needles found.')
"
CR-06 prompt grounding present — all needles found.
```

## Scope Verification

```
git diff b3b3b0f..HEAD --stat -- backend/
 backend/app/harnesses/contract_review.py           |  13 +-
 backend/app/services/harness_engine.py             |  18 ++
 tests/harnesses/test_contract_review_empty_redlines.py | 214 ++++
 3 files changed, 244 insertions(+), 1 deletion(-)
```

Frozen-range invariant (tool_service.py:1-1283): `git diff b3b3b0f..HEAD -- backend/app/services/tool_service.py | wc -l` = 0.

## Deviations from Plan

**1. [Rule 1 - Bug] Test fixture used wrong output key and missing required args**
- **Found during:** Task 1 RED phase (pytest run)
- **Issue:** Plan's test template called `_phase_filter_redline_candidates` without `token` and `thread_id` (required keyword args), and accessed `output["redline-candidates.json"]` instead of `output["content"]` (the actual key returned by the function)
- **Fix:** Added `token="t", thread_id="thr"` to the call; changed to `output["content"]`; the fix also adds `assert "error" not in output` as defensive check
- **Commits:** In the same `test(22-19)` commit (caught before RED gate)

**2. [Rule 1 - Bug] Integration test used wrong module path and wrong `_dispatch_phase` signature**
- **Found during:** Task 2 GREEN phase (first integration test run)
- **Issue:** `app.services.harness_models` does not exist; `PhaseDefinition`/`PhaseType` live in `app.harnesses.types`. Also `_dispatch_phase` takes `registry=` not `tool_context=`
- **Fix:** Corrected import to `app.harnesses.types`; corrected arg to `registry=None`
- **Commits:** In the same `fix(22-19)` commit

## Follow-ups

Live UAT round 4 expected to drive all 9 phases to completion and produce the DOCX deliverable. If a new ceiling appears (DOCX sandbox failure, LLM schema violation in CR-08, etc.), it becomes plan 22-20.

## Self-Check: PASSED

Files exist:
- `backend/tests/harnesses/test_contract_review_empty_redlines.py` — created
- `backend/app/harnesses/contract_review.py` — modified (CR-06 + CR-08 prompts)
- `backend/app/services/harness_engine.py` — modified (empty-batch short-circuit)

Commits exist:
- `70ba8bf` — test(22-19): add failing regression tests
- `cb71269` — fix(22-19): ground CR-06 clause_index + empty-redlines defensive write + CR-08 empty-case prompt
