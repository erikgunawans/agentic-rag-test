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
        token="t",
        thread_id="thr",
        harness_run_id="test-harness-22-19",
    )
    assert "error" not in output, f"Filter executor returned error: {output}"
    candidates = json.loads(output["content"])
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
