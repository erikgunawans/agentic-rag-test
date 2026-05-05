---
phase: 22-contract-review-harness-docx-deliverable
plan: 09
type: execute
wave: 5
depends_on: ["22-02", "22-07", "22-08"]
files_modified:
  - backend/app/harnesses/contract_review.py
  - backend/tests/harnesses/test_contract_review_cr06_cr07.py
autonomous: true
requirements: [CR-06, CR-07]
must_haves:
  truths:
    - "CR-06 (risk-analysis, phases[5]) is LLM_BATCH_AGENTS, batch_size=5"
    - "REVIEW #2 closed: batch row's `result.terminal.text` is the sub-agent's full LLM text response — NOT a parsed dict. CR-06's filter step extracts JSON from result.terminal.text via _parse_subagent_json_terminal helper, validates against ClauseRisk, then keeps YELLOW/RED."
    - "REVIEW #3 closed: filter step joins risk-analysis rows back to clauses.json by clause_index to recover original_text BEFORE writing redline-candidates.json. CR-07 sub-agent receives {clause_index, original_text, risk_grade, ...} so it has the verbatim clause body to rewrite."
    - "CR-06 sub-agent uses search_documents_by_doc_ids (plan 22-02) restricted to playbook_context.clause_category_to_playbook[clause.category]"
    - "CR-07 (redline-generation, phases[7]) is LLM_BATCH_AGENTS, batch_size=5; processes ONLY YELLOW/RED clauses (pre-filtered)"
    - "Empty playbook (context_quality='unfounded') triggers generic legal-knowledge mode (D-22-07)"
    - "Tool curation: phase_tools=['search_documents_by_doc_ids'] only (REVIEW #1: no analyze_document)"
  artifacts:
    - path: "backend/app/harnesses/contract_review.py"
      provides: "CR-06 + CR-07 prompts; ClauseRisk + Redline + RiskGrade; filter executor that parses sub-agent terminal text + joins to clauses.json (REVIEW #2 + #3)"
      contains: "_parse_subagent_json_terminal"
    - path: "backend/tests/harnesses/test_contract_review_cr06_cr07.py"
      provides: "Tests for prompt content + schema validation + filter parses terminal text + clause-text join"
  key_links:
    - from: "Filter executor (phases[6])"
      to: "redline-candidates.json with original_text joined from clauses.json"
      via: "REVIEW #2 parse + REVIEW #3 join"
      pattern: "original_text"
    - from: "CR-07 sub-agent prompt"
      to: "redline-candidates.json (pre-filtered + original_text included)"
      via: "verbatim clause body for rewriting"
      pattern: "original_text"
---

<objective>
Replace CR-06 + CR-07 stubs and the filter executor stub. Two HIGH-severity review findings drive this plan's structure:

1. **REVIEW #2 (batch structured output):** `run_sub_agent_loop()` yields `{"_terminal_result": {"text": full_response}}`. The engine's batch merge wraps that as `result.terminal = {"text": <full LLM text>}`. There is NO parsed `risk_grade` field on `result.terminal` — the previous plan's filter step (`row["result"]["terminal"]["risk_grade"]`) would always KeyError. **Fix:** filter executor must EXTRACT JSON from the sub-agent's terminal text (the LLM was prompted to return a JSON object), validate against `ClauseRisk`, then route on `risk_grade`.

2. **REVIEW #3 (`original_text` propagation):** `ClauseRisk` doesn't carry `original_text`. The redline phase needs the verbatim clause body. **Fix:** filter executor reads `clauses.json` (sibling written by CR-05 per plan 22-08) and joins by `clause_index` to splice the original clause text into each row of `redline-candidates.json`.

Output: prompts + schemas + corrected filter executor + tests with explicit anti-regression guards.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@.planning/phases/22-contract-review-harness-docx-deliverable/22-CONTEXT.md
@.planning/phases/22-contract-review-harness-docx-deliverable/22-PATTERNS.md
@.planning/phases/22-contract-review-harness-docx-deliverable/22-REVIEWS.md
@backend/app/harnesses/contract_review.py
</context>

<interfaces>
<!-- VERIFIED CANONICAL merge shape (harness_engine.py:1015-1033) -->
<!-- For each batch item, the JSONL row written is: -->
<!--   {"item_index": int, "status": "ok"|"failed", "result": {"text": str, "terminal": {"text": str}}} -->
<!-- where result.terminal is the dict yielded by run_sub_agent_loop, which is {"text": full_response}. -->

<!-- run_sub_agent_loop terminal (sub_agent_loop.py:414): -->
<!--   yield {"_terminal_result": {"text": full_response}} -->
<!-- result.terminal.text IS the LLM's full text response (includes whatever JSON the prompt asked for). -->

<!-- REVIEW #2 + #3 strategy: -->
<!--   Filter executor must: -->
<!--   1. Read risk-analysis.json (the engine's merged batch output) -->
<!--   2. For each row: parse JSON from row.result.terminal.text via _parse_subagent_json_terminal -->
<!--   3. Validate parsed JSON against ClauseRisk Pydantic schema -->
<!--   4. Skip rows with risk_grade='GREEN' -->
<!--   5. Read clauses.json (sibling from CR-05 — plan 22-08 writes it) -->
<!--   6. JOIN by clause_index: splice original_text into each YELLOW/RED row -->
<!--   7. Write redline-candidates.json -->

```python
class RiskGrade(str, Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"


class ClauseRisk(BaseModel):
    clause_index: int = Field(..., ge=0)
    clause_category: str
    clause_heading: str
    risk_grade: RiskGrade
    rationale: str = Field(..., min_length=20, max_length=2000)
    alternative_language: str | None = Field(None, max_length=4000)
    grounding_doc_ids: list[str] = Field(default_factory=list)


class RedlineCandidate(BaseModel):
    """REVIEW #3: extends ClauseRisk with original_text joined from clauses.json."""
    clause_index: int = Field(..., ge=0)
    clause_category: str
    clause_heading: str
    original_text: str = Field(..., min_length=1)        # JOINED from clauses.json
    risk_grade: RiskGrade
    rationale: str
    alternative_language: str | None = None
    grounding_doc_ids: list[str] = Field(default_factory=list)


class Redline(BaseModel):
    clause_index: int = Field(..., ge=0)
    clause_category: str
    original_text: str = Field(..., min_length=1, max_length=10_000)
    proposed_text: str = Field(..., min_length=1, max_length=10_000)
    rationale: str = Field(..., min_length=20, max_length=2000)
    fallback_positions: list[str] = Field(default_factory=list, max_length=5)
```
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: CR-06 + CR-07 prompts + schemas + corrected filter executor (REVIEW #2 + #3)</name>
  <files>backend/app/harnesses/contract_review.py</files>
  <read_first>
    - backend/app/harnesses/contract_review.py (post-Plan-22-08 state — find phases[5] "risk-analysis", phases[6] "filter-redline-candidates" stub, phases[7] "redline-generation" stubs)
    - backend/app/services/harness_engine.py (lines 1015-1033 — verify CANONICAL merge shape)
    - backend/app/services/sub_agent_loop.py (line 414 — verify terminal shape `{"text": full_response}`)
    - .planning/phases/22-contract-review-harness-docx-deliverable/22-REVIEWS.md (review findings #2 + #3)
  </read_first>
  <behavior>
    - Test 1: CR-06 prompt contains `GREEN`, `YELLOW`, `RED`.
    - Test 2: CR-06 prompt instructs sub-agent to call `search_documents_by_doc_ids` with `doc_ids=playbook_context.clause_category_to_playbook[clause.category]`.
    - Test 3: CR-06 prompt mentions empty-playbook fallback (`context_quality == 'unfounded'`).
    - Test 4: CR-06 phase has `tools=["search_documents_by_doc_ids"]` (REVIEW #1: NO analyze_document).
    - Test 5: CR-06 has `batch_size=5`.
    - Test 6: CR-07 prompt explicitly says it processes ONLY YELLOW/RED.
    - Test 7: CR-07 prompt instructs original/proposed_text/rationale/fallback_positions JSON output AND mentions that `original_text` is provided in the input row (REVIEW #3).
    - Test 8: CR-07 phase has `batch_size=5`.
    - Test 9: ClauseRisk schema validates RiskGrade enum, requires rationale >=20 chars.
    - Test 10: Redline schema validates non-empty original_text + proposed_text.
    - Test 11: filter phase (phases[6]) is PROGRAMMATIC, name == "filter-redline-candidates", `executor is _phase_filter_redline_candidates`.
    - Test 12 (REVIEW #2): `_parse_subagent_json_terminal` extracts a JSON object from `{"text": "Some preamble.\n\n```json\n{\"risk_grade\": \"RED\", ...}\n```\nSome closing."}` correctly. Falls back to whole-text json.loads. Returns None on unparseable input.
    - Test 13 (REVIEW #2): the filter executor's input is the engine's CANONICAL merge shape `[{item_index, status, result: {text, terminal: {text: <LLM JSON>}}}, ...]` — given that input, filter parses each row's `result.terminal.text` for the ClauseRisk JSON, validates, and keeps only YELLOW/RED.
    - Test 14 (REVIEW #3): given a YELLOW row with `clause_index=0` and a clauses.json containing `[{clause_index: 0, ..., text: "Each party..."}]`, the resulting redline-candidates.json row contains `original_text="Each party..."` (joined).
    - Test 15 (REVIEW #3): when clause_index doesn't match any clause in clauses.json, that row is dropped (with logged warning) — DO NOT pass empty original_text to CR-07.
  </behavior>
  <action>
    Edit `backend/app/harnesses/contract_review.py`:

    **A) Add `RiskGrade` + `ClauseRisk` + `RedlineCandidate` + `Redline` schemas** below ClauseExtractionResult:
    ```python
    class RiskGrade(str, Enum):
        GREEN = "GREEN"
        YELLOW = "YELLOW"
        RED = "RED"


    class ClauseRisk(BaseModel):
        clause_index: int = Field(..., ge=0)
        clause_category: str
        clause_heading: str
        risk_grade: RiskGrade
        rationale: str = Field(..., min_length=20, max_length=2000)
        alternative_language: str | None = Field(None, max_length=4000)
        grounding_doc_ids: list[str] = Field(default_factory=list, max_length=10)


    class RedlineCandidate(BaseModel):
        """REVIEW #3: ClauseRisk + original_text joined from clauses.json by clause_index.
        CR-07 sub-agent receives this shape so it has the verbatim clause body to rewrite."""
        clause_index: int = Field(..., ge=0)
        clause_category: str
        clause_heading: str
        original_text: str = Field(..., min_length=1, max_length=10_000)
        risk_grade: RiskGrade
        rationale: str
        alternative_language: str | None = None
        grounding_doc_ids: list[str] = Field(default_factory=list, max_length=10)


    class Redline(BaseModel):
        clause_index: int = Field(..., ge=0)
        clause_category: str
        original_text: str = Field(..., min_length=1, max_length=10_000)
        proposed_text: str = Field(..., min_length=1, max_length=10_000)
        rationale: str = Field(..., min_length=20, max_length=2000)
        fallback_positions: list[str] = Field(default_factory=list, max_length=5)
    ```
    Add `from enum import Enum` to imports if not present.

    **B) Replace CR-06 (`risk-analysis`, phases[5]) `system_prompt_template`:**
    ```python
    system_prompt_template=(
        "You are assessing a single contract clause for risk against the user's playbook.\n\n"
        "INPUTS PER SUB-AGENT (one clause per agent):\n"
        "  - clause: the JSON object {clause_index, category, heading, text, position}\n"
        "  - playbook-context.md (workspace): includes clause_category_to_playbook map and\n"
        "    context_quality flag ('founded' or 'unfounded' per D-22-07).\n"
        "  - review-context.md (workspace): user's stated perspective, deadline, focus areas.\n\n"
        "TOOLS (curated):\n"
        "  - search_documents_by_doc_ids(query, doc_ids, top_k=8): D-22-06 — call this with\n"
        "    query=<clause.text> and doc_ids=<playbook_context.clause_category_to_playbook[clause.category]>\n"
        "    to retrieve precise grounding from the playbook docs that cover THIS category.\n\n"
        "EMPTY-PLAYBOOK FALLBACK (D-22-07):\n"
        "  If context_quality == 'unfounded' or doc_ids is empty for this clause's category:\n"
        "  assess against industry-standard legal expectations for the contract type.\n"
        "  Set grounding_doc_ids=[] and explicitly say 'unfounded — generic standards' in the rationale.\n\n"
        "GRADING RUBRIC:\n"
        "  GREEN  — clause matches playbook expectations or is benign for this party.\n"
        "  YELLOW — acceptable with caveats, or deviates from playbook but is negotiable.\n"
        "  RED    — materially adverse, conflicts with firm-line playbook position, or creates exposure.\n\n"
        "OUTPUT: respond with ONLY a JSON object inside a ```json``` code block (no prose around it).\n"
        "  ```json\n"
        "  {\"clause_index\": <int>, \"clause_category\": \"<one of 13>\", \"clause_heading\": \"<str>\",\n"
        "   \"risk_grade\": \"GREEN\"|\"YELLOW\"|\"RED\",\n"
        "   \"rationale\": \"<>=20 char explanation citing the playbook doc id(s) you grounded against>\",\n"
        "   \"alternative_language\": \"<for YELLOW/RED: a paragraph of suggested replacement; for GREEN: null>\",\n"
        "   \"grounding_doc_ids\": [\"<uuid-1>\", ...]}\n"
        "  ```\n"
        "Stay focused: ONE clause per sub-agent, ONE JSON object out, no surrounding prose."
    ),
    ```
    Set phases[5]: `tools=["search_documents_by_doc_ids"]`, `batch_size=5`.

    **C) Replace CR-07 (`redline-generation`, phases[7]) `system_prompt_template`:**
    ```python
    system_prompt_template=(
        "You are drafting a precise redline for ONE problematic clause from the contract.\n\n"
        "FILTER: this phase processes ONLY redline candidates (YELLOW + RED, pre-filtered by\n"
        "the filter-redline-candidates PROGRAMMATIC step at phases[6]). GREEN clauses are\n"
        "already excluded.\n\n"
        "INPUTS PER SUB-AGENT (RedlineCandidate JSON object — REVIEW #3):\n"
        "  {clause_index, clause_category, clause_heading, original_text, risk_grade,\n"
        "   rationale, alternative_language, grounding_doc_ids}\n"
        "  Note: `original_text` is the VERBATIM clause body, joined from clauses.json by the\n"
        "  filter step. Use it directly — do NOT re-fetch clauses.\n\n"
        "  Plus workspace files:\n"
        "  - playbook-context.md\n"
        "  - review-context.md\n\n"
        "TOOLS:\n"
        "  - search_documents_by_doc_ids — for re-grounding if alternative_language hint needs refinement.\n\n"
        "PROCEDURE:\n"
        "  1. Read original_text + risk_grade + alternative_language hint.\n"
        "  2. Draft a CONCRETE redline: original (echo input verbatim), proposed (precise replacement), rationale (>=20 chars).\n"
        "  3. Provide UP TO 5 fallback_positions: ordered list of progressively-weaker concessions.\n"
        "  4. Style: plain English; preserve jurisdiction-appropriate legal phrasing.\n\n"
        "OUTPUT: ONLY a JSON object inside a ```json``` code block:\n"
        "  ```json\n"
        "  {\"clause_index\": <int>, \"clause_category\": \"<str>\",\n"
        "   \"original_text\": \"<verbatim from input>\",\n"
        "   \"proposed_text\": \"<verbatim replacement>\",\n"
        "   \"rationale\": \"<>=20 chars>\",\n"
        "   \"fallback_positions\": [\"<position 1>\", \"<position 2>\", ...]}\n"
        "  ```"
    ),
    ```
    Set phases[7]: `tools=["search_documents_by_doc_ids"]`, `batch_size=5`, `workspace_inputs=["redline-candidates.json", "playbook-context.md", "review-context.md"]`.

    **D) Add `_parse_subagent_json_terminal` helper (REVIEW #2):**
    ```python
    def _parse_subagent_json_terminal(terminal_text: str) -> dict | None:
        """REVIEW #2: extract a JSON object from a sub-agent's full LLM text terminal.

        run_sub_agent_loop yields {"_terminal_result": {"text": full_response}} where
        full_response is the LLM's entire text output. The CR-06 prompt asks for JSON inside
        a ```json``` code block; CR-07 likewise. This helper extracts that JSON.

        Returns None on unparseable input. Caller decides how to handle None (typically
        treat as a failed item and skip).
        """
        if not isinstance(terminal_text, str) or not terminal_text.strip():
            return None
        # Try fenced ```json``` code block first
        import re as _re
        m = _re.search(r"```json\s*(\{.*?\})\s*```", terminal_text, _re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                pass
        # Try fenced ``` (no language tag)
        m2 = _re.search(r"```\s*(\{.*?\})\s*```", terminal_text, _re.DOTALL)
        if m2:
            try:
                return json.loads(m2.group(1))
            except Exception:
                pass
        # Last resort: find the first balanced { ... } JSON object in the text
        first = terminal_text.find("{")
        last = terminal_text.rfind("}")
        if first != -1 and last > first:
            try:
                return json.loads(terminal_text[first:last + 1])
            except Exception:
                pass
        # Final fallback: attempt full-text parse (in case it was bare JSON)
        try:
            return json.loads(terminal_text)
        except Exception:
            return None
    ```

    **E) Define `_phase_filter_redline_candidates` (REVIEW #2 parse + REVIEW #3 join):**
    ```python
    async def _phase_filter_redline_candidates(
        *,
        inputs: dict[str, str],
        token: str,
        thread_id: str,
        harness_run_id: str,
        **_,  # forward-compat for engine kwargs (registry, system_settings, etc.)
    ) -> dict:
        """REVIEW #2 + #3: parse risk-analysis.json (engine's batch merge of ClauseRisk JSONs in
        sub-agent terminal text), validate, keep YELLOW/RED, and JOIN to clauses.json by
        clause_index to splice original_text into each row.
        """
        risk_text = (inputs or {}).get("risk-analysis.json", "")
        clauses_text = (inputs or {}).get("clauses.json", "")
        if not risk_text.strip():
            return {"error": "risk_analysis_missing", "code": "NO_RISK",
                    "detail": "risk-analysis.json is empty"}
        if not clauses_text.strip():
            return {"error": "clauses_missing", "code": "NO_CLAUSES",
                    "detail": "clauses.json is empty (CR-05 sibling write must have run)"}

        try:
            risk_rows = json.loads(risk_text)
            clauses_arr = json.loads(clauses_text)
        except Exception as exc:
            return {"error": "filter_parse_failed", "code": "PARSE",
                    "detail": str(exc)[:500]}
        if not isinstance(risk_rows, list) or not isinstance(clauses_arr, list):
            return {"error": "shape_invalid", "code": "SHAPE",
                    "detail": "risk_rows and clauses must both be JSON arrays"}

        # Build clause_index → original_text lookup from CR-05's clauses.json
        # CR-05 clauses don't carry an explicit clause_index field; the array index IS the index.
        clauses_by_idx: dict[int, dict] = {}
        for i, c in enumerate(clauses_arr):
            if isinstance(c, dict):
                clauses_by_idx[i] = c

        candidates: list[dict] = []
        skipped_unparseable = 0
        skipped_no_clause_match = 0
        skipped_green = 0

        # REVIEW #2: each row is the engine's merge shape — parse terminal.text for the JSON
        for row in risk_rows:
            if not isinstance(row, dict) or row.get("status") != "ok":
                continue
            result = row.get("result") or {}
            terminal = result.get("terminal") or {}
            terminal_text = terminal.get("text", "") if isinstance(terminal, dict) else ""

            parsed_dict = _parse_subagent_json_terminal(terminal_text)
            if parsed_dict is None:
                skipped_unparseable += 1
                logger.warning(
                    "CR-06 filter: failed to parse sub-agent terminal text item=%s harness_run=%s",
                    row.get("item_index"), harness_run_id,
                )
                continue

            try:
                cr = ClauseRisk.model_validate(parsed_dict)
            except Exception as exc:
                skipped_unparseable += 1
                logger.warning(
                    "CR-06 filter: ClauseRisk validation failed item=%s: %s",
                    row.get("item_index"), exc,
                )
                continue

            # Keep YELLOW + RED only
            if cr.risk_grade == RiskGrade.GREEN:
                skipped_green += 1
                continue

            # REVIEW #3: JOIN clause_index → original_text from clauses.json
            clause_match = clauses_by_idx.get(cr.clause_index)
            if not clause_match or not clause_match.get("text"):
                skipped_no_clause_match += 1
                logger.warning(
                    "CR-06 filter: no clauses.json row matches clause_index=%d (REVIEW #3 — original_text join failed); skipping row",
                    cr.clause_index,
                )
                continue

            candidate = {
                "clause_index": cr.clause_index,
                "clause_category": cr.clause_category,
                "clause_heading": cr.clause_heading,
                "original_text": clause_match["text"],         # REVIEW #3 — joined verbatim text
                "risk_grade": cr.risk_grade.value,
                "rationale": cr.rationale,
                "alternative_language": cr.alternative_language,
                "grounding_doc_ids": cr.grounding_doc_ids,
            }
            # Validate the assembled RedlineCandidate shape
            try:
                RedlineCandidate.model_validate(candidate)
            except Exception as exc:
                logger.warning("CR-06 filter: RedlineCandidate validation failed clause_index=%d: %s",
                               cr.clause_index, exc)
                continue

            candidates.append(candidate)

        return {
            "content": json.dumps(candidates, ensure_ascii=False, indent=2),
            "candidate_count": len(candidates),
            "total_risks": len(risk_rows),
            "skipped_green": skipped_green,
            "skipped_unparseable": skipped_unparseable,
            "skipped_no_clause_match": skipped_no_clause_match,
        }
    ```

    **F) Wire phases[6]:**
    ```python
    # ISSUE-06: replace plan 22-06's stub at phases[6] with the real filter executor.
    CONTRACT_REVIEW.phases[6].executor = _phase_filter_redline_candidates
    # REVIEW #3: filter needs BOTH risk-analysis.json AND clauses.json to join on clause_index
    CONTRACT_REVIEW.phases[6].workspace_inputs = ["risk-analysis.json", "clauses.json"]
    ```
    (Plan 22-06 may have set workspace_inputs=["risk-analysis.json"] only; this plan ensures clauses.json is also read.)

    **G) DROP the redundant clauses.json sibling-write patch.** Plan 22-08 now writes clauses.json inside `_phase5_extract_clauses` itself. Plan 22-09 does NOT need to patch CR-05 — only this plan's filter executor reads both files.
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pytest tests/harnesses/test_contract_review_cr06_cr07.py -v --tb=short && python -c "from app.harnesses.contract_review import ClauseRisk, Redline, RiskGrade, RedlineCandidate, _parse_subagent_json_terminal, _phase_filter_redline_candidates; print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "_parse_subagent_json_terminal" backend/app/harnesses/contract_review.py` returns `>= 3` (def + filter usage + test reference)
    - `grep -c "RedlineCandidate" backend/app/harnesses/contract_review.py` returns `>= 2`
    - `grep -c "REVIEW #2\|REVIEW #3" backend/app/harnesses/contract_review.py` returns `>= 4`
    - `grep -c "original_text" backend/app/harnesses/contract_review.py` returns `>= 4`
    - `grep -c "search_documents_by_doc_ids" backend/app/harnesses/contract_review.py` returns `>= 4` (CR-06 + CR-07 prompts + tools lists)
    - `grep -c "analyze_document" backend/app/harnesses/contract_review.py` returns `0` (REVIEW #1 anti-regression — no analyze_document anywhere)
    - `python -c "from app.harnesses.contract_review import CONTRACT_REVIEW; assert CONTRACT_REVIEW.phases[5].batch_size == 5; assert CONTRACT_REVIEW.phases[7].batch_size == 5; assert CONTRACT_REVIEW.phases[6].name == 'filter-redline-candidates'; print('OK')"` prints `OK`
    - `python -c "from app.harnesses.contract_review import CONTRACT_REVIEW; assert CONTRACT_REVIEW.phases[5].tools == ['search_documents_by_doc_ids']; print('OK')"` prints `OK`
    - `python -c "from app.harnesses.contract_review import CONTRACT_REVIEW; assert 'risk-analysis.json' in CONTRACT_REVIEW.phases[6].workspace_inputs and 'clauses.json' in CONTRACT_REVIEW.phases[6].workspace_inputs; print('OK')"` prints `OK`
  </acceptance_criteria>
  <done>CR-06/CR-07 prompts populated; filter executor parses terminal text + joins original_text; schemas added.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Tests for CR-06/CR-07 + filter parse + clause-text join (REVIEW #2 + #3)</name>
  <files>backend/tests/harnesses/test_contract_review_cr06_cr07.py</files>
  <read_first>
    - backend/app/harnesses/contract_review.py (post-Task-1 state)
    - backend/tests/harnesses/test_contract_review_cr03_cr04.py (analog test patterns)
  </read_first>
  <behavior>
    See behaviors 1-15 in Task 1.
  </behavior>
  <action>
    Create `backend/tests/harnesses/test_contract_review_cr06_cr07.py` with 15 tests.

    Concrete test 12 (REVIEW #2 — parser):
    ```python
    def test_parse_subagent_json_terminal_handles_fenced_block():
        from app.harnesses.contract_review import _parse_subagent_json_terminal
        text = (
            "Sure, here's my analysis.\n\n"
            "```json\n"
            '{"clause_index": 0, "risk_grade": "RED", "rationale": "x" * 25}\n'
            "```\n"
            "Done."
        )
        # Need real text not "x" * 25 in the JSON, fix:
        text = (
            "Sure.\n\n"
            "```json\n"
            '{"clause_index": 0, "clause_category": "Liability", "clause_heading": "1.",'
            ' "risk_grade": "RED", "rationale": "Materially adverse to buyer.",'
            ' "alternative_language": null, "grounding_doc_ids": []}\n'
            "```\n"
        )
        parsed = _parse_subagent_json_terminal(text)
        assert parsed is not None
        assert parsed["risk_grade"] == "RED"
        assert parsed["clause_index"] == 0


    def test_parse_subagent_json_terminal_returns_none_on_garbage():
        from app.harnesses.contract_review import _parse_subagent_json_terminal
        assert _parse_subagent_json_terminal("just plain text no json") is None
        assert _parse_subagent_json_terminal("") is None
        assert _parse_subagent_json_terminal(None) is None
    ```

    Concrete test 13 (REVIEW #2 — full filter executor with canonical merge shape):
    ```python
    @pytest.mark.asyncio
    async def test_filter_executor_parses_terminal_text_keeps_yellow_red():
        """REVIEW #2: filter MUST extract JSON from result.terminal.text (full LLM response),
        NOT expect a parsed result.terminal.risk_grade key (which doesn't exist)."""
        from app.harnesses.contract_review import _phase_filter_redline_candidates
        # Engine's CANONICAL merge shape — terminal.text is full LLM text including ```json``` block
        risk_rows = [
            {"item_index": 0, "status": "ok", "result": {"text": "...", "terminal": {"text":
                'Some preamble.\n```json\n{"clause_index": 0, "clause_category": "Liability",'
                ' "clause_heading": "1.", "risk_grade": "RED",'
                ' "rationale": "Materially adverse to buyer position here.",'
                ' "alternative_language": "Cap raised to USD 1M.", "grounding_doc_ids": []}\n```'
            }}},
            {"item_index": 1, "status": "ok", "result": {"text": "...", "terminal": {"text":
                '```json\n{"clause_index": 1, "clause_category": "Confidentiality",'
                ' "clause_heading": "2.", "risk_grade": "GREEN",'
                ' "rationale": "Standard NDA terms; matches playbook expectations exactly.",'
                ' "alternative_language": null, "grounding_doc_ids": []}\n```'
            }}},
            {"item_index": 2, "status": "ok", "result": {"text": "...", "terminal": {"text":
                '```json\n{"clause_index": 2, "clause_category": "Payment",'
                ' "clause_heading": "3.", "risk_grade": "YELLOW",'
                ' "rationale": "30 day payment terms acceptable but late-fee unusually high.",'
                ' "alternative_language": "1% per month interest cap.", "grounding_doc_ids": []}\n```'
            }}},
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
            token="t", thread_id="thr", harness_run_id="run",
        )
        candidates = json.loads(result["content"])
        # Should keep RED (idx 0) and YELLOW (idx 2), drop GREEN (idx 1)
        assert len(candidates) == 2
        assert {c["risk_grade"] for c in candidates} == {"RED", "YELLOW"}
        # REVIEW #3: each candidate has original_text JOINED from clauses.json
        cand_by_idx = {c["clause_index"]: c for c in candidates}
        assert cand_by_idx[0]["original_text"] == "Each party's liability..."
        assert cand_by_idx[2]["original_text"] == "Customer shall pay within 30 days..."
        assert result["skipped_green"] == 1
    ```

    Concrete test 15 (REVIEW #3 — clause_index mismatch dropped):
    ```python
    @pytest.mark.asyncio
    async def test_filter_drops_row_when_clause_index_has_no_match():
        """REVIEW #3: if clause_index from CR-06 doesn't match any clauses.json row, the row
        is DROPPED (not passed forward with empty original_text). Logs a warning."""
        from app.harnesses.contract_review import _phase_filter_redline_candidates
        risk_rows = [{
            "item_index": 0, "status": "ok", "result": {"text": "...", "terminal": {"text":
                '```json\n{"clause_index": 99, "clause_category": "Liability", "clause_heading": "x",'
                ' "risk_grade": "RED", "rationale": "Not real but should be dropped here.",'
                ' "alternative_language": null, "grounding_doc_ids": []}\n```'
            }}}
        ]
        clauses_arr = [
            {"category": "Liability", "heading": "1.", "text": "Real clause.", "position": 0},
        ]
        result = await _phase_filter_redline_candidates(
            inputs={
                "risk-analysis.json": json.dumps(risk_rows),
                "clauses.json": json.dumps(clauses_arr),
            },
            token="t", thread_id="thr", harness_run_id="run",
        )
        assert result["skipped_no_clause_match"] == 1
        candidates = json.loads(result["content"])
        assert len(candidates) == 0
    ```
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pytest tests/harnesses/test_contract_review_cr06_cr07.py -v --tb=short</automated>
  </verify>
  <acceptance_criteria>
    - `pytest backend/tests/harnesses/test_contract_review_cr06_cr07.py -v` exits 0 with 15 tests passing
    - `grep -c "REVIEW #2\|REVIEW #3" backend/tests/harnesses/test_contract_review_cr06_cr07.py` returns `>= 4`
    - `grep -c "_parse_subagent_json_terminal" backend/tests/harnesses/test_contract_review_cr06_cr07.py` returns `>= 2`
    - `grep -c "original_text" backend/tests/harnesses/test_contract_review_cr06_cr07.py` returns `>= 3`
    - `grep -c "result.*terminal.*text" backend/tests/harnesses/test_contract_review_cr06_cr07.py` returns `>= 1` (canonical merge shape used in test fixture)
  </acceptance_criteria>
  <done>15 tests pass — REVIEW #2 + #3 anti-regression locked in.</done>
</task>

</tasks>

<truths>
- D-22-06 — CR-06/07 use search_documents_by_doc_ids from plan 22-02.
- D-22-07 — empty-playbook fallback explicit in CR-06 prompt.
- D-22-08 — authority hierarchy implicit via CR-04's playbook-context.md ordering.
- BATCH-01..07 (Phase 21 batch dispatcher) reused unchanged.
- B4 single-registry (SEC-04): each batch sub-agent's LLM call goes through sub_agent_loop.py which inherits the parent's egress_filter wrap.
- REVIEW #1 closed (no analyze_document references).
- REVIEW #2 closed: filter parses sub-agent terminal text via _parse_subagent_json_terminal — handles ```json``` fenced block, bare ```, and bare JSON fallbacks. CANONICAL merge shape `{item_index, status, result: {text, terminal: {text}}}` is parsed correctly.
- REVIEW #3 closed: filter joins clauses.json by clause_index to splice original_text. Rows with no match are dropped (logged), not passed forward empty.
- ISSUE-06 wiring: phases[6] is PROGRAMMATIC, executor swapped post-CONTRACT_REVIEW assignment.
- Plan 22-08 owns the clauses.json sibling write (moved out of this plan); this plan only consumes both files.
</truths>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Sub-agent LLM JSON in terminal text → filter parser | Untrusted JSON; _parse_subagent_json_terminal handles malformed input gracefully |
| Filter output → CR-07 sub-agents | RedlineCandidate validated post-join; rows lacking original_text dropped before forwarding |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-22-09-01 | Information Disclosure | Clause PII in CR-06 LLM payload | mitigate | SEC-04 egress filter wrap in sub_agent_loop |
| T-22-09-02 | Tampering | Sub-agent emits malformed JSON in terminal | mitigate | _parse_subagent_json_terminal returns None on unparseable; counted, skipped |
| T-22-09-03 | Tampering | LLM hallucinates clause_index outside clauses.json range | mitigate | REVIEW #3 — filter drops rows with no clauses.json match |
| T-22-09-04 | DoS | 200-clause contract * 5 sub-agents | accept | Phase timeout + MAX_SUB_AGENT_ROUNDS env cap |
| T-22-09-05 | Repudiation | Risk grades not auditable | mitigate | LangSmith tracing covers sub-agent calls |
</threat_model>

<verification>
1. `pytest backend/tests/harnesses/test_contract_review_cr06_cr07.py -v` exits 0
2. `pytest backend/tests/harnesses/ -v` exits 0 (regression including plan 22-07/08 tests)
3. `python -c "from app.main import app; print('OK')"` prints `OK`
</verification>

<success_criteria>
- CR-06 + CR-07 prompts populated; emit JSON inside ```json``` fences
- ClauseRisk + RedlineCandidate + Redline schemas available
- filter-redline-candidates phase parses terminal text (REVIEW #2) + joins original_text (REVIEW #3)
- Phase 21 batch dispatcher reused without modification
- Tool curation: only `search_documents_by_doc_ids` reaches sub-agents (no analyze_document)
</success_criteria>

<output>
After completion, create `.planning/phases/22-contract-review-harness-docx-deliverable/22-09-SUMMARY.md`.
</output>
