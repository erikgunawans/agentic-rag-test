---
phase: 22-contract-review-harness-docx-deliverable
plan: 19
type: execute
wave: 1
depends_on: [18]
files_modified:
  - backend/app/harnesses/contract_review.py
  - backend/app/services/harness_engine.py
  - backend/tests/harnesses/test_contract_review_empty_redlines.py
autonomous: true
gap_closure: true
requirements: [CR-06, CR-07, CR-08]
must_haves:
  truths:
    - "CR-06 sub-agent system prompt explicitly grounds clause_index to the input clause object — sub-agents echo the int from input.clause_index verbatim, never invent line/char/page offsets"
    - "Filter step (_phase_filter_redline_candidates) handles ALL-DROP case without breaking downstream — when redline-candidates.json ends up [], the engine guarantees redlines.json is also written as []"
    - "CR-07 (redline-generation) writes redlines.json = [] when input redline-candidates.json is empty, rather than skipping silently and leaving the file unwritten"
    - "CR-08 (executive-summary) does NOT fail with 'workspace read failed' when redlines.json is empty []. CR-08 emits a valid ExecutiveSummary that explicitly states no redlines were warranted (or the relevant equivalent for the empty case)"
    - "A regression test exists that simulates the live-UAT-round-3 failure shape (risk-analysis with hallucinated clause_index=999 → empty redline-candidates → empty redlines → CR-08 succeeds with degraded-but-valid summary) and passes on the fix"
  artifacts:
    - path: "backend/app/harnesses/contract_review.py"
      provides: "CR-06 prompt with explicit clause_index grounding language; CR-07/CR-08 wired so empty redlines pipeline doesn't break downstream"
      contains: "echo the clause_index from the input"
    - path: "backend/app/services/harness_engine.py"
      provides: "LLM_BATCH_AGENTS empty-input handling so workspace_output is always written (even as []) — OR equivalent at the contract_review.py level if the engine is the wrong place"
      contains: "empty input batch"
    - path: "backend/tests/harnesses/test_contract_review_empty_redlines.py"
      provides: "Regression test that mirrors UAT round 3 failure shape — synthetic risk-analysis with one valid YELLOW + one hallucinated-index RED → filter drops the bad one → CR-07 writes [] → CR-08 produces valid ExecutiveSummary"
      contains: "test_empty_redlines_does_not_break_cr08"
  key_links:
    - from: "_phase_filter_redline_candidates"
      to: "redline-candidates.json"
      via: "JOIN clause_index → original_text from clauses.json"
      pattern: "clauses_by_idx\\.get\\(cr\\.clause_index\\)"
    - from: "PhaseDefinition(name='redline-generation', ...)"
      to: "redlines.json (workspace_output)"
      via: "LLM_BATCH_AGENTS over redline-candidates.json"
      pattern: "workspace_output=\"redlines\\.json\""
    - from: "PhaseDefinition(name='executive-summary', ...)"
      to: "redlines.json (workspace_input)"
      via: "engine workspace_inputs read"
      pattern: "workspace_inputs=\\[[^\\]]*\"redlines\\.json\""
---

<objective>
Close UAT-NEW-03 (BLOCKER discovered in live UAT round 3, 2026-05-06 13:32:58Z): with all 6 prior gap-closure plans (22-13..18) deployed, the harness now runs phases 1-7 cleanly against live Azure-routed gpt-4o, but phase 8 (CR-08 executive-summary) fails with `"workspace read failed"`. Root cause is upstream of CR-08:

1. **CR-06 LLM emits `clause_index: 185`** for clauses in a contract that has only ~7 clauses (real array indexes 0-6). The LLM is generating plausible-looking integers (likely line/character offsets from the source) instead of echoing the `clause_index` from the input clause object.
2. **Filter step drops all candidates** because the join `clauses_by_idx.get(cr.clause_index)` (`backend/app/harnesses/contract_review.py:789`) returns `None` for every nonsensical index. `redline-candidates.json` ends up `[]` (2 bytes) even when risk-analysis.json contains real RED findings.
3. **CR-07 (redline-generation) sees empty input** and skips silently — `redlines.json` is never written.
4. **CR-08 fails on workspace_input read** because the engine declares `workspace_inputs=[..., "redlines.json"]` (line 1156) and the file doesn't exist.

This is a TWO-LAYER bug:
- **Layer A — root cause:** CR-06 prompt doesn't strongly bind `clause_index` to the input. Fix by tightening prompt language to explicitly require echoing `input.clause_index` verbatim.
- **Layer B — defensive containment:** Even with the prompt fix, the LLM can still hallucinate an index occasionally. CR-07 should always produce `redlines.json` (even as `[]`) so CR-08's workspace read never fails. Fix by ensuring the engine/CR-07 writes the workspace_output file even on empty input batch.

Both fixes together make the pipeline robust: (A) reduces the rate of `[]` outputs; (B) ensures `[]` outputs don't break downstream.

Out of scope:
- Adding fallback matching by `(category, heading)` in the filter — adds complexity; prompt grounding + defensive writes are simpler and sufficient.
- Refactoring `workspace_inputs` to support optional vs required inputs (architectural change).
- Modifying the `RedlineCandidate` Pydantic model (the existing shape is correct).
- Adding `clause_index` upper-bound validation (the LLM can't realistically be constrained that way; the join check IS the validation).

Output: `contract_review.py` with tightened CR-06 prompt + (if needed) CR-07 always-writes-output behavior; possibly a small engine helper change; 1 new regression test that simulates the live failure shape.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/22-contract-review-harness-docx-deliverable/22-HUMAN-UAT.md
@.planning/phases/22-contract-review-harness-docx-deliverable/22-09-CR06-CR07-batch-risk-and-redlines-PLAN.md
@.planning/phases/22-contract-review-harness-docx-deliverable/22-10-CR08-summary-and-DOCX-postexecute-PLAN.md
@CLAUDE.md
@backend/app/harnesses/contract_review.py
@backend/app/services/harness_engine.py

<scope_verification>
**Live failure proof (UAT round 3 forensics — 2026-05-06 13:29-13:33 UTC, thread `29a3bad1-4207-42f4-b66c-e985b9575835`):**

```sql
SELECT file_path, source, size_bytes, created_at FROM workspace_files
WHERE thread_id = '29a3bad1-4207-42f4-b66c-e985b9575835' ORDER BY created_at;
```

| time UTC | file_path | size | meaning |
|---|---|---|---|
| 13:32:52 | risk-analysis.json | 4015 | CR-06 produced real risk grades |
| 13:32:58 | redline-candidates.json | **2** | filter joined to `[]` (every candidate dropped) |
| (missing) | redlines.json | — | CR-07 never wrote |
| (missing) | executive-summary.json | — | CR-08 failed: "workspace read failed" |

```sql
SELECT LEFT(content, 200) FROM workspace_files
WHERE thread_id = '29a3bad1-4207-42f4-b66c-e985b9575835'
  AND file_path = 'risk-analysis.json';
-- → "...{\"clause_index\":185,\"clause_category\":\"Liability\",\"risk_grade\":\"RED\",..."
```

`clause_index: 185` — synth-contract.docx has only ~7 clauses, so this is hallucinated. The `risk-analysis.jsonl` line for this row WAS valid YELLOW/RED — the LLM just put a wrong index.

```sql
SELECT status, current_phase, error_detail FROM harness_runs
WHERE thread_id = '29a3bad1-4207-42f4-b66c-e985b9575835';
-- → status=failed, current_phase=8, error_detail="workspace read failed"
```

CR-08 (current_phase=8) failed at workspace-read step, BEFORE its Azure LLM call (which means 22-18's helper is doing its job — it's not even getting to the schema-emission point because the input read fails first).

**Code-side contributing factors:**

1. CR-06 prompt (`contract_review.py:1019-1058`) says: "INPUTS PER SUB-AGENT (one clause per agent): clause: the JSON object {clause_index, category, heading, text, position}". The sub-agent is given the clause WITH clause_index, but the prompt does NOT explicitly require echoing it verbatim in the output. Output spec just says `"clause_index": <int>`.

2. Filter (`contract_review.py:740-808`) drops on miss (REVIEW #3 / plan 22-09): when `clauses_by_idx.get(cr.clause_index)` returns None, the row is logged + dropped. This is correct defensive behavior — the bug is upstream (LLM index drift), not in the filter.

3. CR-07 PhaseDefinition (`contract_review.py:1086-1125`) is `LLM_BATCH_AGENTS` with `workspace_inputs=["redline-candidates.json"]` and `workspace_output="redlines.json"`. When input is empty, the engine likely doesn't write the output at all (need to verify in `harness_engine.py`).

4. CR-08 PhaseDefinition (`contract_review.py:1130-1162`) declares `workspace_inputs=[..., "redlines.json"]`. Engine's workspace-read step fails if any declared input is missing.
</scope_verification>

<interfaces>
<!-- Authoritative source: backend/app/harnesses/contract_review.py:1031-1057 (CR-06 prompt) -->

**Layer A fix — CR-06 prompt strengthening:**

Add an EXPLICIT clause_index grounding clause to the CR-06 system_prompt_template. Insert it as a CRITICAL block right after the OUTPUT spec, before the "Stay focused" line:

```
"CRITICAL — clause_index grounding:\n"
"  The 'clause_index' field in your output JSON MUST be the EXACT integer from\n"
"  the input clause object's clause_index field. Do NOT generate a new number.\n"
"  Do NOT use line numbers, character offsets, page numbers, or paragraph counts.\n"
"  Do NOT 'estimate' or 'approximate' the index. ECHO IT VERBATIM.\n"
"  Example: input clause has 'clause_index': 3, output JSON has 'clause_index': 3.\n\n"
```

This is one small prompt addition, no schema or executor changes.

<!-- Authoritative source: backend/app/services/harness_engine.py — LLM_BATCH_AGENTS dispatch -->

**Layer B fix — CR-07 / engine empty-input contract:**

Investigate during execution whether the LLM_BATCH_AGENTS dispatch path in `harness_engine.py` writes `workspace_output` when the input batch is `[]`. Two cases:

1. **If the engine already writes `[]`** for empty input batches: no engine change needed; just verify with a unit test.
2. **If the engine SKIPS writing** for empty batches: add a one-liner that writes the workspace_output as `[]` (or equivalent empty structure for the phase's batch type) BEFORE returning. The fix likely lives near where workspace_output is written in `_dispatch_phase` or a similar function — search for `workspace_output` writes in LLM_BATCH_AGENTS path.

The implementation choice — engine-level vs. CR-07-level — depends on what's cleanest. Engine-level is more general (benefits any future LLM_BATCH_AGENTS phase); CR-07-level is more surgical. Defer to executor agent's judgment after reading the actual code, but document the choice in SUMMARY.md.

<!-- Authoritative source: backend/app/harnesses/contract_review.py:1156 (CR-08 inputs) -->

**CR-08 graceful handling of empty redlines.json:**

CR-08's `system_prompt_template` (line 1140-1147) already includes "redlines.json" in INPUTS. With Layer B in place, redlines.json will exist as `[]` in the empty case, and CR-08's LLM will see an empty list. The prompt should ALREADY handle this case if you read it carefully:
> "If playbook-context.md.context_quality == 'unfounded', BEGIN your recommendation with..."

The empty-redlines case is similar but distinct. ADD a parallel hint in the prompt:
> "If redlines.json is an empty array [], ACKNOWLEDGE it: 'No clauses warranted redlines under the current playbook + review context.' Then proceed to summarize the classification + risk grades from clauses.md/risk-analysis.json. The ExecutiveSummary is still required (overall_risk, recommendation, key_findings, risk_breakdown, next_steps)."

This makes CR-08 robust to the empty case at the LLM-output level, complementing the workspace-read fix.
</interfaces>
</context>

<tasks>

## Task 1 — Write the failing regression test (RED)

**Context budget:** ~6K tokens.

Create `backend/tests/harnesses/test_contract_review_empty_redlines.py` that simulates the live UAT round 3 failure shape end-to-end, against the contract_review module — at the harness/phase level, not by mocking everything.

```python
"""Regression test for UAT-NEW-03 (clause_index drift → empty redlines → CR-08 break).

Live failure shape captured 2026-05-06 13:29-13:33 UTC, thread
29a3bad1-4207-42f4-b66c-e985b9575835:
  - risk-analysis.json contains real YELLOW/RED rows
  - One row has hallucinated clause_index (out of range for clauses.json)
  - Filter joins by clause_index → drops the bad row → may end with []
  - CR-07 sees empty input → does not write redlines.json
  - CR-08 declares workspace_inputs=[..., 'redlines.json'] → workspace_read fails
  - harness_runs.status=failed, current_phase=8, error_detail='workspace read failed'

Plan 22-19 fixes this in two layers:
  A. CR-06 prompt now explicitly grounds clause_index to input.clause_index
     (reduces hallucination rate but cannot prevent it 100%).
  B. CR-07 always writes redlines.json (even as []) so CR-08 workspace_read succeeds;
     CR-08 prompt ALSO acknowledges the empty-redlines case at the LLM-output level.
"""

import json
import pytest

# (1) The filter step itself behaves correctly when an LLM hallucinates clause_index.
#     This test pins that behavior — it should pass on master AND on the fix.

from app.harnesses.contract_review import (
    _phase_filter_redline_candidates,
    Clause,
    ClauseRisk,
    RiskGrade,
)


# Fixtures shared by tests below. Constructed to mirror the live failure exactly.

CLAUSES_FIXTURE = [
    {"clause_index": 0, "category": "Liability", "heading": "LIABILITY",
     "text": "Each party's total liability shall not exceed USD 100,000."},
    {"clause_index": 1, "category": "Confidentiality", "heading": "CONFIDENTIALITY",
     "text": "Each party shall maintain the confidentiality of all information."},
    {"clause_index": 2, "category": "Payment", "heading": "PAYMENT",
     "text": "Payment shall be made within 30 days of invoicing."},
]

# Mimics the engine's LLM_BATCH_AGENTS canonical merge shape (REVIEW #2).
# One row has GOOD index (1, valid), one row has HALLUCINATED index (185, the live failure value).
RISK_ROWS_WITH_HALLUCINATION = [
    {
        "item_index": 0,
        "status": "ok",
        "result": {
            "terminal": {
                "text": '```json\n{"clause_index":1,"clause_category":"Confidentiality",'
                        '"clause_heading":"CONFIDENTIALITY","risk_grade":"YELLOW",'
                        '"rationale":"5-year tail is broader than firm baseline of 3 years.",'
                        '"alternative_language":"Reduce to 3 years.",'
                        '"grounding_doc_ids":[]}\n```'
            }
        }
    },
    {
        "item_index": 1,
        "status": "ok",
        "result": {
            "terminal": {
                "text": '```json\n{"clause_index":185,"clause_category":"Liability",'
                        '"clause_heading":"LIABILITY","risk_grade":"RED",'
                        '"rationale":"Cap of 100k is well below typical firm baseline of 10x ACV.",'
                        '"alternative_language":"Increase liability cap to USD 1,000,000.",'
                        '"grounding_doc_ids":[]}\n```'
            }
        }
    },
]


@pytest.mark.asyncio
async def test_filter_drops_hallucinated_clause_index_keeps_valid_one():
    """The filter MUST drop rows where clause_index doesn't resolve in clauses.json,
    AND keep rows that do. This is REVIEW #3 behavior; plan 22-19 does not change it.
    """
    output = await _phase_filter_redline_candidates(
        inputs={
            "risk-analysis.json": json.dumps(RISK_ROWS_WITH_HALLUCINATION),
            "clauses.json": json.dumps(CLAUSES_FIXTURE),
        },
        harness_run_id="test-harness-22-19",
    )
    candidates = json.loads(output["redline-candidates.json"])
    # Hallucinated index=185 dropped; valid index=1 kept
    assert len(candidates) == 1
    assert candidates[0]["clause_index"] == 1
    assert candidates[0]["risk_grade"] == "YELLOW"
    # original_text MUST be the verbatim text from clauses.json[1]
    assert candidates[0]["original_text"] == CLAUSES_FIXTURE[1]["text"]


# (2) CR-06 prompt MUST contain the clause_index grounding language (Layer A fix).

def test_cr06_prompt_grounds_clause_index_to_input():
    """The CR-06 system prompt MUST contain explicit instructions that bind
    clause_index in the output to clause_index in the input. Without this guard,
    LLMs hallucinate plausible-looking integers (e.g., line offsets) and break
    the filter join.
    """
    from app.harnesses.contract_review import CONTRACT_REVIEW
    cr06 = next(p for p in CONTRACT_REVIEW.phases if p.name == "risk-analysis")
    prompt = cr06.system_prompt_template
    assert "echo" in prompt.lower() and "clause_index" in prompt.lower(), (
        "CR-06 system prompt MUST instruct sub-agents to echo clause_index from "
        "input verbatim. Plan 22-19 / UAT-NEW-03."
    )
    # Negative examples (line/char/page-number drift) must be explicitly forbidden
    assert any(forbidden in prompt.lower() for forbidden in (
        "line number", "character offset", "page number"
    )), (
        "CR-06 prompt MUST forbid common drift patterns explicitly. "
        "Vague guidance is not enough."
    )


# (3) CR-07 / engine MUST produce redlines.json even when input is empty (Layer B).
#     Implementation choice (engine-level vs CR-07-level) is up to the executor;
#     this test is shape-agnostic — it asserts the EFFECT, not the mechanism.

@pytest.mark.asyncio
async def test_empty_redline_candidates_produces_empty_redlines_json(monkeypatch, tmp_path):
    """When the filter produces redline-candidates.json = [], CR-07 (redline-generation)
    MUST still produce redlines.json = [] so CR-08's workspace_read does not fail.

    This test is integration-flavored — it exercises the real LLM_BATCH_AGENTS dispatch
    path with an empty input. If the engine handles empty-batch correctly, redlines.json
    is written as []. If CR-07 writes its own output, that's also acceptable.

    The executor MAY choose to mock OpenRouter — but the workspace_output write MUST
    be exercised, not stubbed.
    """
    # Implementation hint: see harness_engine.py LLM_BATCH_AGENTS dispatch; locate where
    # workspace_output is written. The fix should ensure that path is reached even when
    # the input batch is []. The executor decides the precise injection point.
    pytest.skip(
        "Integration test scaffold — executor implements during Task 2 once the "
        "engine code path is identified. Skip is intentional pending implementation."
    )


# (4) CR-08 prompt MUST acknowledge the empty-redlines case (Layer B containment).

def test_cr08_prompt_handles_empty_redlines():
    """CR-08's prompt MUST tell the LLM what to do when redlines.json is []. Without
    this guidance, the LLM may produce a degenerate or confused ExecutiveSummary.
    """
    from app.harnesses.contract_review import CONTRACT_REVIEW
    cr08 = next(p for p in CONTRACT_REVIEW.phases if p.name == "executive-summary")
    prompt = cr08.system_prompt_template
    assert "empty" in prompt.lower() and "redlines" in prompt.lower(), (
        "CR-08 prompt MUST contain explicit guidance for the empty-redlines case. "
        "Plan 22-19 / UAT-NEW-03."
    )
```

Run the test — it must FAIL on master HEAD `b3b3b0f`:

```bash
cd backend && source venv/bin/activate && \
  pytest tests/harnesses/test_contract_review_empty_redlines.py -xvs
```

Expected RED:
- `test_filter_drops_hallucinated_clause_index_keeps_valid_one` — should PASS on master (REVIEW #3 already implements this; this test pins the regression)
- `test_cr06_prompt_grounds_clause_index_to_input` — FAIL on master (prompt lacks "echo" + forbidden-drift language)
- `test_empty_redline_candidates_produces_empty_redlines_json` — SKIP on master (placeholder)
- `test_cr08_prompt_handles_empty_redlines` — FAIL on master (prompt lacks empty-redlines guidance)

Two of the four tests fail. That's acceptable RED — failures are specific and named.

**Commit:** `test(22-19): add failing regression tests for clause_index grounding + empty redlines pipeline`

**Verification gate before Task 2:**
- The 4 tests collect cleanly (no ImportError).
- The 2 prompt-content tests FAIL with assertion failure messages naming "echo"/"clause_index" or "empty"/"redlines".
- The filter test PASSES (pre-existing REVIEW #3 behavior pinned).
- The integration test is skipped (placeholder).

---

## Task 2 — Apply the fixes (GREEN)

**Context budget:** ~6K tokens.

### Edit 1 — Tighten CR-06 prompt (Layer A)

In `backend/app/harnesses/contract_review.py`, locate the CR-06 PhaseDefinition (search for `name="risk-analysis"`). In its `system_prompt_template`, insert the CRITICAL clause_index grounding block AFTER the OUTPUT spec (after the `"  Stay focused"` line, OR before that line — whichever reads better). Match existing prompt indentation (no leading spaces on lines, single-quote-per-string-piece pattern).

Required content:
```
"CRITICAL — clause_index grounding (plan 22-19):\n"
"  The 'clause_index' field in your output JSON MUST be the EXACT integer from\n"
"  the input clause object's clause_index field. Do NOT generate a new number.\n"
"  Do NOT use line numbers, character offsets, page numbers, or paragraph counts.\n"
"  Do NOT 'estimate' or 'approximate' the index. ECHO IT VERBATIM.\n"
"  Example: input clause has 'clause_index': 3, output JSON has 'clause_index': 3.\n\n"
```

The exact phrasing can be adjusted but must include the words: `echo`, `clause_index`, `line number`, `character offset`, `page number` — these are what the test asserts.

### Edit 2 — Empty-input handling (Layer B)

Investigate `backend/app/services/harness_engine.py`. Find the LLM_BATCH_AGENTS dispatch — search for `LLM_BATCH_AGENTS` in the phase_type dispatch logic. Identify where `workspace_output` gets written for this phase type.

**Two implementation paths (executor chooses):**

**Path A (engine-level, preferred if clean):** add an empty-batch short-circuit at the top of LLM_BATCH_AGENTS dispatch. If the input batch is `[]` (after parsing the workspace_inputs), write the workspace_output as `[]` (or empty JSON list) and skip the LLM call entirely. This is general — benefits any future LLM_BATCH_AGENTS phase.

**Path B (CR-07-level, surgical fallback):** add a `post_execute` hook on the CR-07 PhaseDefinition that asserts `redlines.json` exists and writes `[]` if missing. This is more localized but doesn't generalize.

Document the choice in SUMMARY.md. Either is acceptable — A is preferred unless the engine code makes A awkward.

### Edit 3 — CR-08 prompt graceful empty-redlines

In the CR-08 PhaseDefinition (`name="executive-summary"`), add to the `system_prompt_template`:

```
"If redlines.json is an empty array [], ACKNOWLEDGE it explicitly:\n"
"  'No clauses warranted redlines under the current playbook + review context.'\n"
"Then proceed to summarize classification + risk grades from clauses.md and\n"
"risk-analysis.json. The ExecutiveSummary is still required (overall_risk,\n"
"recommendation, key_findings, risk_breakdown, next_steps).\n"
```

Match existing prompt indentation. The test asserts the words `empty` AND `redlines` appear in the prompt.

### Verify GREEN

1. Re-run regression test:
   ```bash
   cd backend && source venv/bin/activate && \
     pytest tests/harnesses/test_contract_review_empty_redlines.py -xvs
   ```
   Expected: 4/4 pass (filter test + 2 prompt tests + the integration test now actually implemented and passing).

2. Full harness/services suite for regression coverage:
   ```bash
   pytest tests/harnesses/ \
          tests/services/test_harness_engine.py \
          tests/services/test_harness_engine_post_execute.py \
          tests/services/test_harness_engine_todos.py \
          tests/services/test_harness_engine_strict_schema.py \
          tests/services/test_post_harness.py \
          tests/services/test_gatekeeper.py \
          tests/services/test_gatekeeper_eval.py \
          -q --tb=short
   ```
   Expected: all pass (165 baseline + new tests). Pre-existing test counts may shift slightly if Layer B requires touching engine internals; net should still be all-green.

3. Backend import check:
   ```bash
   python -c "from app.main import app; print('OK')"
   ```

4. Spot-check the CR-06 prompt:
   ```bash
   python3 -c "
   from app.harnesses.contract_review import CONTRACT_REVIEW
   cr06 = next(p for p in CONTRACT_REVIEW.phases if p.name == 'risk-analysis')
   import re
   assert 'echo' in cr06.system_prompt_template.lower()
   assert 'clause_index' in cr06.system_prompt_template.lower()
   assert 'line number' in cr06.system_prompt_template.lower()
   print('CR-06 prompt grounding present.')
   "
   ```

**Commit:** `fix(22-19): ground CR-06 clause_index + empty-redlines defensive write + CR-08 empty-case prompt`

**Verification gate before SUMMARY:**
- All 4 regression tests pass (the integration test now implemented).
- Full suite green — no regressions in test_harness_engine* / test_post_harness / test_gatekeeper*.
- Backend imports cleanly.
- Spot-check confirms prompt language landed.

---

## Task 3 — SUMMARY.md and commit

**Context budget:** ~2K tokens.

Write `.planning/phases/22-contract-review-harness-docx-deliverable/22-19-clause-index-grounding-and-empty-redlines-SUMMARY.md` following the executor-contract template:

- **Objective:** Close UAT-NEW-03 (clause_index drift + empty redlines pipeline)
- **Files changed:** 1-2 source files, 1 new test file
- **Test result:** RED → GREEN proof; explain the implementation choice for Layer B (engine vs CR-07)
- **Verification:** the 4 commands from Task 2's verify-GREEN with their outputs
- **Deviations:** any deviations from the plan as written
- **Follow-ups:** Live UAT round 4 expected to drive CR-08 to completion + DOCX deliverable. If a NEW ceiling appears (DOCX rendering issue, sandbox failure, etc.), it's a separate plan.

**Commit:** `docs(22-19): complete clause-index-grounding plan — SUMMARY + state update`

</tasks>

<verification>

Plan-level verification (after all 3 tasks commit):

1. **Frozen-range invariant** — does not touch tool_service.py:1-1283:
   ```bash
   git diff b3b3b0f..HEAD -- backend/app/services/tool_service.py | wc -l
   # expected: 0
   ```

2. **Plan-scope grep — no scope creep:**
   ```bash
   git diff --stat b3b3b0f..HEAD -- backend/
   # expected: 2-3 source files: contract_review.py, possibly harness_engine.py, plus the new test file
   ```

3. **CR-06 prompt grounding language present at runtime:**
   ```bash
   python3 -c "
   from app.harnesses.contract_review import CONTRACT_REVIEW
   p = next(p for p in CONTRACT_REVIEW.phases if p.name == 'risk-analysis').system_prompt_template
   for needle in ['echo', 'clause_index', 'line number']:
     assert needle in p.lower(), f'missing: {needle}'
   print('OK')
   "
   ```

4. **Live UAT round 4 unblocks CR-08 + DOCX** (manual; not part of plan automation):
   - Open https://frontend-pi-lovat-22.vercel.app
   - Sign in test@test.com, upload synth-contract.docx
   - Send "review for risk", respond to HIL prompt
   - Watch Plan Panel — ALL 9 phases must transition `running → completed`
   - DOCX file card MUST appear in the chat as a downloadable artifact
   - Whatever surfaces next (if anything) is plan 22-20 territory.

</verification>

<scope_creep_guards>

- **Do NOT** add fallback `(category, heading)` matching to the filter step. Prompt grounding + defensive output writes are sufficient; secondary matching adds complexity for marginal benefit.
- **Do NOT** modify `RedlineCandidate` Pydantic model or the filter's drop-on-miss behavior. The filter is correct as-is; the bug is upstream.
- **Do NOT** introduce optional vs required `workspace_inputs` distinction in the engine. That's an architectural change beyond the scope of UAT-NEW-03.
- **Do NOT** revert any of plans 22-13..18's changes. They're all proven working in production.
- **Do NOT** weaken Azure strict mode or the `_to_azure_strict_schema` helper. CR-08 fails AFTER the helper succeeds — the helper is doing its job.
- **Do NOT** add `clause_index` upper-bound validation to ClauseRisk Pydantic. The LLM emits whatever it wants; the join check IS the validation.

</scope_creep_guards>

<rollback>

If any task fails verification:

```bash
# Discard uncommitted changes
git checkout -- backend/app/harnesses/contract_review.py backend/app/services/harness_engine.py
rm -f backend/tests/harnesses/test_contract_review_empty_redlines.py

# Revert atomic commits if landed
git revert <task-2-commit-hash> <task-1-commit-hash>
```

The plan is bounded: 1-2 source files + 1 test file. Rollback is trivial.

</rollback>

<confidence>

**Confidence: 92%**

Why lower than 22-18's 98%:
- The Layer B (empty-batch handling) implementation depends on engine internals I haven't fully inspected. Path A (engine-level short-circuit) requires identifying the right location in `harness_engine.py`'s LLM_BATCH_AGENTS dispatch; Path B (CR-07-level post_execute hook) requires verifying the post_execute timing. Either is achievable, but the executor will need to make a judgment call after reading the engine code.
- The CR-06 prompt fix should reduce hallucination rate but cannot eliminate it. Layer B is the actual safety net. Both layers must work for the pipeline to be robust.
- Live UAT round 4 will be the proof — the regression test plus integration test cover the deterministic surface, but the LLM-grounding behavior is probabilistic.

The remaining 8%:
- 4% reserved for "engine LLM_BATCH_AGENTS empty-batch path is more entangled than expected" — could require touching adjacent code.
- 4% reserved for "even with both fixes, LLM still hallucinates indexes and the pipeline degrades to all-empty in some runs" — would require Path B (defensive containment) to handle gracefully end-to-end. The CR-08 prompt fix should cover this.

Pass count: 1 self-verify (live failure forensics from UAT round 3, exact line numbers for every edit, two-layer fix architecture, executor judgment call documented for Layer B implementation, regression tests cover both deterministic surface AND prompt content).

</confidence>
