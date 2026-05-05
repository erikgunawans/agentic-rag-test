"""Phase 22 / Plan 22-09 — Unit tests for CR-06 (risk-analysis) and CR-07 (redline-generation).

15 test cases:
 Test 1:  CR-06 prompt contains GREEN, YELLOW, RED risk grades.
 Test 2:  CR-06 prompt instructs sub-agent to call search_documents_by_doc_ids with
          doc_ids=playbook_context.clause_category_to_playbook[clause.category].
 Test 3:  CR-06 prompt mentions empty-playbook fallback (context_quality == 'unfounded').
 Test 4:  CR-06 phase has tools=["search_documents_by_doc_ids"] (REVIEW #1: NO analyze_document).
 Test 5:  CR-06 has batch_size=5.
 Test 6:  CR-07 prompt explicitly says it processes ONLY YELLOW/RED clauses.
 Test 7:  CR-07 prompt instructs original/proposed_text/rationale/fallback_positions JSON output
          AND mentions that original_text is provided in the input row (REVIEW #3).
 Test 8:  CR-07 phase has batch_size=5.
 Test 9:  ClauseRisk schema validates RiskGrade enum, requires rationale >=20 chars.
 Test 10: Redline schema validates non-empty original_text + proposed_text.
 Test 11: filter phase (phases[6]) is PROGRAMMATIC, name == "filter-redline-candidates",
          executor is _phase_filter_redline_candidates.
 Test 12: (REVIEW #2) _parse_subagent_json_terminal extracts JSON from fenced ```json``` block.
          Returns None on unparseable input.
 Test 13: (REVIEW #2) filter executor consumes the engine's CANONICAL merge shape
          [{item_index, status, result: {text, terminal: {text: <LLM JSON>}}}, ...],
          parses each row's result.terminal.text for ClauseRisk JSON, and keeps only YELLOW/RED.
 Test 14: (REVIEW #3) filter executor joins clause_index -> original_text from clauses.json;
          resulting redline-candidates.json rows have non-empty original_text from clauses.json.
 Test 15: (REVIEW #3) when clause_index doesn't match any clauses.json row, the row is
          DROPPED (skipped_no_clause_match incremented); empty original_text NEVER forwarded.

Run:
    cd backend && source venv/bin/activate && \\
        pytest tests/harnesses/test_contract_review_cr06_cr07.py -v --tb=short
"""
from __future__ import annotations

import importlib
import json
import sys
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures / helpers (mirrors test_contract_review_cr03_cr04.py pattern)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_registry():
    """Clear the harness registry before and after each test."""
    from app.services import harness_registry
    harness_registry._reset_for_tests()
    yield
    harness_registry._reset_for_tests()


def _reload_contract_review(
    harness_enabled: bool = True,
    contract_review_enabled: bool = True,
    tool_registry_enabled: bool = True,
):
    """Reload app.harnesses.contract_review under a patched settings object."""
    mock_settings = MagicMock()
    mock_settings.harness_enabled = harness_enabled
    mock_settings.contract_review_enabled = contract_review_enabled
    mock_settings.tool_registry_enabled = tool_registry_enabled

    mod_name = "app.harnesses.contract_review"
    sys.modules.pop(mod_name, None)

    with patch("app.config.get_settings", return_value=mock_settings):
        mod = importlib.import_module(mod_name)

    return mod


# ---------------------------------------------------------------------------
# Test 1: CR-06 prompt contains GREEN, YELLOW, RED
# ---------------------------------------------------------------------------

def test_cr06_prompt_contains_risk_grades():
    """Test 1: CR-06 system_prompt_template contains GREEN, YELLOW, RED."""
    mod = _reload_contract_review()
    cr06 = mod.CONTRACT_REVIEW.phases[5]
    assert cr06.name == "risk-analysis", f"Expected phases[5] = risk-analysis, got {cr06.name}"
    assert cr06.system_prompt_template != "STUB", "CR-06 system_prompt_template must not be STUB"
    prompt = cr06.system_prompt_template
    assert "GREEN" in prompt, "CR-06 prompt must contain GREEN risk grade"
    assert "YELLOW" in prompt, "CR-06 prompt must contain YELLOW risk grade"
    assert "RED" in prompt, "CR-06 prompt must contain RED risk grade"


# ---------------------------------------------------------------------------
# Test 2: CR-06 prompt instructs search_documents_by_doc_ids with playbook mapping
# ---------------------------------------------------------------------------

def test_cr06_prompt_instructs_search_by_doc_ids():
    """Test 2: CR-06 prompt instructs sub-agent to call search_documents_by_doc_ids
    with doc_ids=playbook_context.clause_category_to_playbook[clause.category]."""
    mod = _reload_contract_review()
    cr06 = mod.CONTRACT_REVIEW.phases[5]
    prompt = cr06.system_prompt_template
    assert "search_documents_by_doc_ids" in prompt, (
        "CR-06 prompt must reference search_documents_by_doc_ids (D-22-06)"
    )
    assert "clause_category_to_playbook" in prompt, (
        "CR-06 prompt must reference clause_category_to_playbook to guide doc_ids selection"
    )


# ---------------------------------------------------------------------------
# Test 3: CR-06 prompt mentions empty-playbook fallback (context_quality == 'unfounded')
# ---------------------------------------------------------------------------

def test_cr06_prompt_mentions_unfounded_fallback():
    """Test 3: CR-06 prompt mentions empty-playbook fallback (D-22-07)."""
    mod = _reload_contract_review()
    cr06 = mod.CONTRACT_REVIEW.phases[5]
    prompt = cr06.system_prompt_template
    assert "unfounded" in prompt, (
        "CR-06 prompt must mention the D-22-07 empty-playbook fallback "
        "(context_quality == 'unfounded')"
    )


# ---------------------------------------------------------------------------
# Test 4: CR-06 tools list = ["search_documents_by_doc_ids"] (REVIEW #1)
# ---------------------------------------------------------------------------

def test_cr06_tools_curated_no_analyze_document():
    """Test 4 (REVIEW #1): CR-06 tools must be exactly ['search_documents_by_doc_ids'].
    No analyze_document (does not exist in tool_service.py)."""
    mod = _reload_contract_review()
    cr06 = mod.CONTRACT_REVIEW.phases[5]
    assert cr06.tools == ["search_documents_by_doc_ids"], (
        f"REVIEW #1: CR-06 tools must be ['search_documents_by_doc_ids']; got {cr06.tools}"
    )
    assert "analyze_document" not in cr06.tools, (
        "analyze_document does not exist in this codebase — must not appear in CR-06 tools"
    )


# ---------------------------------------------------------------------------
# Test 5: CR-06 has batch_size=5
# ---------------------------------------------------------------------------

def test_cr06_batch_size():
    """Test 5: CR-06 batch_size must be 5."""
    mod = _reload_contract_review()
    cr06 = mod.CONTRACT_REVIEW.phases[5]
    assert cr06.batch_size == 5, f"CR-06 batch_size must be 5; got {cr06.batch_size}"


# ---------------------------------------------------------------------------
# Test 6: CR-07 prompt says ONLY YELLOW/RED processed
# ---------------------------------------------------------------------------

def test_cr07_prompt_mentions_yellow_red_filter():
    """Test 6: CR-07 prompt explicitly states it processes ONLY YELLOW/RED clauses."""
    mod = _reload_contract_review()
    cr07 = mod.CONTRACT_REVIEW.phases[7]
    assert cr07.name == "redline-generation", f"Expected phases[7] = redline-generation, got {cr07.name}"
    assert cr07.system_prompt_template != "STUB", "CR-07 system_prompt_template must not be STUB"
    prompt = cr07.system_prompt_template
    # Prompt must reference YELLOW + RED
    assert "YELLOW" in prompt and "RED" in prompt, (
        "CR-07 prompt must mention YELLOW and RED (the filter pre-conditions)"
    )
    # Prompt must indicate pre-filtering has happened
    assert "pre-filter" in prompt.lower() or "filter" in prompt.lower(), (
        "CR-07 prompt must say it processes pre-filtered YELLOW/RED candidates only"
    )


# ---------------------------------------------------------------------------
# Test 7: CR-07 prompt instructs original_text, proposed_text, rationale, fallback_positions
#         AND mentions original_text is provided in input (REVIEW #3)
# ---------------------------------------------------------------------------

def test_cr07_prompt_output_schema_and_original_text():
    """Test 7 (REVIEW #3): CR-07 prompt instructs JSON output with original_text/proposed_text/
    rationale/fallback_positions, and notes that original_text is provided in the input."""
    mod = _reload_contract_review()
    cr07 = mod.CONTRACT_REVIEW.phases[7]
    prompt = cr07.system_prompt_template
    assert "original_text" in prompt, (
        "REVIEW #3: CR-07 prompt must reference original_text (provided by filter join)"
    )
    assert "proposed_text" in prompt, "CR-07 prompt must instruct proposed_text in JSON output"
    assert "rationale" in prompt, "CR-07 prompt must instruct rationale in JSON output"
    assert "fallback_positions" in prompt, "CR-07 prompt must instruct fallback_positions in JSON output"
    # Prompt must note that original_text comes from the input (REVIEW #3 — verbatim clause body)
    assert "verbatim" in prompt.lower() or "provided" in prompt.lower() or "joined" in prompt.lower(), (
        "REVIEW #3: CR-07 prompt must indicate that original_text is the verbatim clause body "
        "provided by the filter step (not something the sub-agent fetches)"
    )


# ---------------------------------------------------------------------------
# Test 8: CR-07 has batch_size=5
# ---------------------------------------------------------------------------

def test_cr07_batch_size():
    """Test 8: CR-07 batch_size must be 5."""
    mod = _reload_contract_review()
    cr07 = mod.CONTRACT_REVIEW.phases[7]
    assert cr07.batch_size == 5, f"CR-07 batch_size must be 5; got {cr07.batch_size}"


# ---------------------------------------------------------------------------
# Test 9: ClauseRisk schema validates RiskGrade enum, requires rationale >= 20 chars
# ---------------------------------------------------------------------------

def test_clause_risk_schema_validation():
    """Test 9: ClauseRisk schema validates RiskGrade enum and rationale length."""
    mod = _reload_contract_review()
    ClauseRisk = mod.ClauseRisk
    RiskGrade = mod.RiskGrade

    # Valid GREEN
    cr = ClauseRisk(
        clause_index=0,
        clause_category="Liability",
        clause_heading="Section 1.",
        risk_grade=RiskGrade.GREEN,
        rationale="Clause matches playbook expectations precisely.",
        alternative_language=None,
        grounding_doc_ids=[],
    )
    assert cr.risk_grade == RiskGrade.GREEN

    # Valid RED
    cr_red = ClauseRisk(
        clause_index=1,
        clause_category="IP",
        clause_heading="IP Ownership",
        risk_grade=RiskGrade.RED,
        rationale="Materially adverse — IP assignment too broad for our position.",
        grounding_doc_ids=["doc-001"],
    )
    assert cr_red.risk_grade == RiskGrade.RED

    # Invalid: rationale too short (< 20 chars)
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        ClauseRisk(
            clause_index=2,
            clause_category="Payment",
            clause_heading="Payment",
            risk_grade=RiskGrade.YELLOW,
            rationale="Too short",  # < 20 chars
        )

    # Invalid: bad enum value
    with pytest.raises((ValidationError, ValueError)):
        ClauseRisk(
            clause_index=3,
            clause_category="Other",
            clause_heading="Other",
            risk_grade="BLUE",  # not in enum
            rationale="Some sufficiently long rationale for testing purposes.",
        )


# ---------------------------------------------------------------------------
# Test 10: Redline schema validates non-empty original_text + proposed_text
# ---------------------------------------------------------------------------

def test_redline_schema_validation():
    """Test 10: Redline schema requires non-empty original_text and proposed_text."""
    mod = _reload_contract_review()
    Redline = mod.Redline

    # Valid redline
    r = Redline(
        clause_index=0,
        clause_category="Liability",
        original_text="Seller's liability is unlimited.",
        proposed_text="Seller's aggregate liability shall not exceed USD 1,000,000.",
        rationale="Unlimited liability creates unacceptable exposure for our firm.",
        fallback_positions=["Cap at 2x contract value", "Cap at USD 5M"],
    )
    assert r.original_text == "Seller's liability is unlimited."
    assert len(r.fallback_positions) == 2

    # Invalid: empty original_text
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        Redline(
            clause_index=1,
            clause_category="IP",
            original_text="",  # min_length=1
            proposed_text="Some proposed text.",
            rationale="Rationale that is long enough to pass validation.",
        )

    # Invalid: rationale too short
    with pytest.raises(ValidationError):
        Redline(
            clause_index=2,
            clause_category="Other",
            original_text="Original clause text here.",
            proposed_text="Proposed replacement text.",
            rationale="Too short",  # < 20 chars
        )


# ---------------------------------------------------------------------------
# Test 11: filter phase is PROGRAMMATIC, correct name + executor
# ---------------------------------------------------------------------------

def test_filter_phase_is_programmatic_with_correct_executor():
    """Test 11: phases[6] is PROGRAMMATIC, name='filter-redline-candidates',
    executor is _phase_filter_redline_candidates."""
    mod = _reload_contract_review()
    filter_phase = mod.CONTRACT_REVIEW.phases[6]
    from app.harnesses.types import PhaseType
    assert filter_phase.phase_type == PhaseType.PROGRAMMATIC, (
        f"phases[6] must be PROGRAMMATIC; got {filter_phase.phase_type}"
    )
    assert filter_phase.name == "filter-redline-candidates", (
        f"phases[6].name must be 'filter-redline-candidates'; got {filter_phase.name}"
    )
    assert filter_phase.executor is mod._phase_filter_redline_candidates, (
        "phases[6].executor must be _phase_filter_redline_candidates (REVIEW #2 + #3 fix)"
    )


# ---------------------------------------------------------------------------
# Test 12: (REVIEW #2) _parse_subagent_json_terminal handles fenced ```json``` block
# ---------------------------------------------------------------------------

def test_parse_subagent_json_terminal_handles_fenced_block():
    """Test 12 (REVIEW #2): _parse_subagent_json_terminal extracts JSON from a fenced
    ```json``` code block (the canonical LLM output format prompted by CR-06)."""
    mod = _reload_contract_review()
    _parse_subagent_json_terminal = mod._parse_subagent_json_terminal

    # Canonical form: fenced ```json``` block with prose around it
    text = (
        "Sure.\n\n"
        "```json\n"
        '{"clause_index": 0, "clause_category": "Liability", "clause_heading": "1.",'
        ' "risk_grade": "RED", "rationale": "Materially adverse to buyer position here.",'
        ' "alternative_language": null, "grounding_doc_ids": []}\n'
        "```\n"
        "That completes my analysis."
    )
    parsed = _parse_subagent_json_terminal(text)
    assert parsed is not None, "REVIEW #2: must parse JSON from ```json``` fenced block"
    assert parsed["risk_grade"] == "RED"
    assert parsed["clause_index"] == 0
    assert parsed["clause_category"] == "Liability"


def test_parse_subagent_json_terminal_returns_none_on_garbage():
    """Test 12 cont. (REVIEW #2): _parse_subagent_json_terminal returns None on unparseable input."""
    mod = _reload_contract_review()
    _parse_subagent_json_terminal = mod._parse_subagent_json_terminal

    assert _parse_subagent_json_terminal("just plain text no json") is None
    assert _parse_subagent_json_terminal("") is None
    assert _parse_subagent_json_terminal(None) is None  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Test 13: (REVIEW #2) filter executor parses canonical merge shape, keeps YELLOW/RED
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_filter_executor_parses_terminal_text_keeps_yellow_red():
    """Test 13 (REVIEW #2): filter MUST extract JSON from result.terminal.text (the full
    LLM response string), NOT from a pre-parsed result.terminal.risk_grade key
    (which doesn't exist in the canonical merge shape).

    Canonical engine merge shape (harness_engine.py:1164-1171):
      {"item_index": int, "status": "ok"|"failed",
       "result": {"text": str, "terminal": {"text": <full LLM response>}}}
    """
    mod = _reload_contract_review()
    _phase_filter_redline_candidates = mod._phase_filter_redline_candidates

    # Engine's CANONICAL merge shape — terminal.text is full LLM text with ```json``` block
    risk_rows = [
        {
            "item_index": 0, "status": "ok",
            "result": {
                "text": "...",
                "terminal": {
                    "text": (
                        "Some preamble.\n"
                        "```json\n"
                        '{"clause_index": 0, "clause_category": "Liability",'
                        ' "clause_heading": "1.", "risk_grade": "RED",'
                        ' "rationale": "Materially adverse to buyer position here.",'
                        ' "alternative_language": "Cap raised to USD 1M.", "grounding_doc_ids": []}'
                        "\n```"
                    ),
                },
            },
        },
        {
            "item_index": 1, "status": "ok",
            "result": {
                "text": "...",
                "terminal": {
                    "text": (
                        "```json\n"
                        '{"clause_index": 1, "clause_category": "Confidentiality",'
                        ' "clause_heading": "2.", "risk_grade": "GREEN",'
                        ' "rationale": "Standard NDA terms; matches playbook expectations exactly.",'
                        ' "alternative_language": null, "grounding_doc_ids": []}'
                        "\n```"
                    ),
                },
            },
        },
        {
            "item_index": 2, "status": "ok",
            "result": {
                "text": "...",
                "terminal": {
                    "text": (
                        "```json\n"
                        '{"clause_index": 2, "clause_category": "Payment",'
                        ' "clause_heading": "3.", "risk_grade": "YELLOW",'
                        ' "rationale": "30 day payment terms acceptable but late-fee unusually high.",'
                        ' "alternative_language": "1% per month interest cap.", "grounding_doc_ids": []}'
                        "\n```"
                    ),
                },
            },
        },
    ]
    clauses_arr = [
        {"category": "Liability", "heading": "1.", "text": "Each party's liability...", "position": 0},
        {"category": "Confidentiality", "heading": "2.", "text": "Each party shall hold...", "position": 200},
        {"category": "Payment", "heading": "3.", "text": "Customer shall pay within 30 days...", "position": 400},
    ]

    result = await _phase_filter_redline_candidates(
        inputs={
            "risk-analysis.json": json.dumps(risk_rows),
            "clauses.json": json.dumps(clauses_arr),
        },
        token="t",
        thread_id="thr",
        harness_run_id="run",
    )

    assert "error" not in result, f"Filter executor returned error: {result}"
    candidates = json.loads(result["content"])

    # Should keep RED (idx 0) and YELLOW (idx 2), drop GREEN (idx 1)
    assert len(candidates) == 2, (
        f"REVIEW #2: filter must keep exactly 2 candidates (RED + YELLOW); got {len(candidates)}"
    )
    assert {c["risk_grade"] for c in candidates} == {"RED", "YELLOW"}, (
        f"Expected {{RED, YELLOW}}; got {{{', '.join(c['risk_grade'] for c in candidates)}}}"
    )
    assert result["skipped_green"] == 1, "GREEN clause must be counted in skipped_green"

    # REVIEW #3: each candidate has original_text JOINED from clauses.json
    cand_by_idx = {c["clause_index"]: c for c in candidates}
    assert cand_by_idx[0]["original_text"] == "Each party's liability...", (
        "REVIEW #3: original_text for clause_index=0 must be joined from clauses.json"
    )
    assert cand_by_idx[2]["original_text"] == "Customer shall pay within 30 days...", (
        "REVIEW #3: original_text for clause_index=2 must be joined from clauses.json"
    )


# ---------------------------------------------------------------------------
# Test 14: (REVIEW #3) original_text joined from clauses.json
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_filter_joins_original_text_from_clauses_json():
    """Test 14 (REVIEW #3): given a YELLOW row with clause_index=0 and clauses.json
    containing [{text: 'Each party...'}], the resulting candidate row has
    original_text='Each party...' (joined by position/array-index, NOT a key lookup)."""
    mod = _reload_contract_review()
    _phase_filter_redline_candidates = mod._phase_filter_redline_candidates

    risk_rows = [
        {
            "item_index": 0, "status": "ok",
            "result": {
                "text": "",
                "terminal": {
                    "text": (
                        "```json\n"
                        '{"clause_index": 0, "clause_category": "IP",'
                        ' "clause_heading": "IP Ownership", "risk_grade": "YELLOW",'
                        ' "rationale": "IP assignment scope exceeds standard commercial practice.",'
                        ' "alternative_language": "Limit to work product only.", "grounding_doc_ids": []}'
                        "\n```"
                    ),
                },
            },
        },
    ]
    clauses_arr = [
        {
            "category": "IP",
            "heading": "IP Ownership",
            "text": "Each party retains all pre-existing intellectual property rights.",
            "position": 150,
        },
    ]

    result = await _phase_filter_redline_candidates(
        inputs={
            "risk-analysis.json": json.dumps(risk_rows),
            "clauses.json": json.dumps(clauses_arr),
        },
        token="t",
        thread_id="thr",
        harness_run_id="run",
    )

    assert "error" not in result
    candidates = json.loads(result["content"])
    assert len(candidates) == 1
    assert candidates[0]["original_text"] == (
        "Each party retains all pre-existing intellectual property rights."
    ), "REVIEW #3: original_text must be joined from clauses.json by clause_index"
    assert candidates[0]["risk_grade"] == "YELLOW"


# ---------------------------------------------------------------------------
# Test 15: (REVIEW #3) clause_index mismatch — row is DROPPED, not forwarded empty
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_filter_drops_row_when_clause_index_has_no_match():
    """Test 15 (REVIEW #3): if clause_index from CR-06 doesn't match any row in
    clauses.json (i.e. the LLM hallucinated an out-of-range index), the row is DROPPED
    (skipped_no_clause_match incremented). Empty original_text NEVER reaches CR-07."""
    mod = _reload_contract_review()
    _phase_filter_redline_candidates = mod._phase_filter_redline_candidates

    risk_rows = [
        {
            "item_index": 0, "status": "ok",
            "result": {
                "text": "",
                "terminal": {
                    "text": (
                        "```json\n"
                        '{"clause_index": 99, "clause_category": "Liability",'
                        ' "clause_heading": "x", "risk_grade": "RED",'
                        ' "rationale": "Not real but should be dropped here due to index.",'
                        ' "alternative_language": null, "grounding_doc_ids": []}'
                        "\n```"
                    ),
                },
            },
        },
    ]
    clauses_arr = [
        {"category": "Liability", "heading": "1.", "text": "Real clause body.", "position": 0},
    ]

    result = await _phase_filter_redline_candidates(
        inputs={
            "risk-analysis.json": json.dumps(risk_rows),
            "clauses.json": json.dumps(clauses_arr),
        },
        token="t",
        thread_id="thr",
        harness_run_id="run",
    )

    assert result["skipped_no_clause_match"] == 1, (
        "REVIEW #3: row with unmatched clause_index=99 must be counted in skipped_no_clause_match"
    )
    candidates = json.loads(result["content"])
    assert len(candidates) == 0, (
        "REVIEW #3: no candidates must reach CR-07 when clause_index has no match in clauses.json"
    )
    # Verify no empty original_text slipped through
    for c in candidates:
        assert c.get("original_text"), "REVIEW #3: original_text must never be empty/None in output"
