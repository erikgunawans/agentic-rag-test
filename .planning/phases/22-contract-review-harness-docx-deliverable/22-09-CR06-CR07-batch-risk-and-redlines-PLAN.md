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
    - "CR-06 (risk-analysis, phases[5]) is LLM_BATCH_AGENTS, batch_size=5; sub-agent assesses GREEN/YELLOW/RED per clause vs playbook"
    - "CR-06 sub-agent uses search_documents_by_doc_ids (plan 22-02) restricted to playbook_context.clause_category_to_playbook[clause.category]"
    - "Filter step (filter-redline-candidates, phases[6]) is PROGRAMMATIC (no batch_size, no system_prompt_template); inserted by plan 22-06 as a stub, replaced here by setting executor=_phase_filter_redline_candidates"
    - "CR-07 (redline-generation, phases[7]) is LLM_BATCH_AGENTS, batch_size=5; processes ONLY YELLOW/RED clauses (pre-filtered by phases[6]); outputs original/proposed/rationale/fallback"
    - "ISSUE-04: CR-06 reads clauses.json (raw JSON array sibling written by CR-05; clauses.md remains as markdown for human readability)"
    - "ISSUE-06: programmatic filter-redline-candidates phase already inserted at phases[6] by plan 22-06; this plan ONLY replaces the stub executor (does NOT add a new PhaseDefinition or call .insert())"
    - "Empty playbook (context_quality='unfounded') triggers generic legal-knowledge mode in sub-agent prompt (D-22-07)"
    - "ClauseRisk + Redline schemas validated post-batch via the JSONL output read"
    - "Tool curation: phase_tools=['search_documents_by_doc_ids', 'analyze_document'] only"
    - "Phase 21 batch dispatcher reused unchanged — JSONL append + asyncio.gather + mid-batch resume work out of the box"
  artifacts:
    - path: "backend/app/harnesses/contract_review.py"
      provides: "CR-06 + CR-07 system_prompt_template populated; ClauseRisk + Redline + RiskGrade enum + filter executor + sibling clauses.json sibling-write patch"
      contains: "ClauseRisk"
    - path: "backend/tests/harnesses/test_contract_review_cr06_cr07.py"
      provides: "Tests for prompt content + schema validation + tool curation + filter executor + clauses.json sibling write"
  key_links:
    - from: "CR-06 sub-agent prompt"
      to: "search_documents_by_doc_ids(query=clause.text, doc_ids=playbook_ids_for_category)"
      via: "filter_doc_ids parameter (plan 22-02 tool)"
      pattern: "search_documents_by_doc_ids"
    - from: "CR-07 sub-agent prompt"
      to: "redline-candidates.json (YELLOW/RED only, written by phases[6] filter)"
      via: "input filter — sub-agent receives only pre-filtered YELLOW/RED items"
      pattern: "redline-candidates\\.json"
---

<objective>
Replace CR-06 + CR-07 stubs with their real prompts. Both phases use the Phase 21 LLM_BATCH_AGENTS dispatcher (already wired) — we only specify prompts, tools, schemas, and batch_size=5. Also wire the executor for the programmatic filter-redline-candidates phase that was inserted as a stub by plan 22-06.

Per ROADMAP success criterion 4: GREEN/YELLOW/RED per clause + rationale + alternative language; redline outputs original / proposed replacement / rationale / fallback.

Purpose: This is the analytical heart of the harness. CR-06 grades, the filter step culls GREEN clauses, CR-07 drafts redlines for YELLOW/RED only, all feeding CR-08 (executive summary).
Output: Two phase prompts (CR-06, CR-07) + filter executor + risk/redline schemas + tests.
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
@backend/app/harnesses/contract_review.py
</context>

<interfaces>
<!-- ISSUE-04 PIN: harness_engine.py LLM_BATCH_AGENTS dispatcher (line 838-1099) — -->
<!--   Items source: phase.workspace_inputs[0] (line 858) -->
<!--   Items shape: JSON ARRAY OF DICTS (line 868: json.loads(content); validates list type) -->
<!--   Engine reads workspace file, parses as JSON array, fans out one sub-agent per item. -->
<!--   Each sub-agent receives item via system prompt suffix: "Item to process: <json>" (line 953). -->
<!--   Output: JSONL written to <stem>.jsonl (line 880), merged sorted to <stem>.json post-batch. -->

<!-- harness_engine.py:1060-1099 LLM_BATCH_AGENTS merge logic (CANONICAL output shape): -->
<!--   Reads <stem>.jsonl line-by-line, sorts by item_index, writes <stem>.json. -->
<!--   Output shape: JSON array of objects, each shaped: -->
<!--     {item_index: int, status: 'ok' | 'error', result: {text: str, terminal: dict | null}} -->
<!--   The `result.terminal` field is the Pydantic-validated terminal output (i.e., ClauseRisk dict). -->
<!--   This is the ONE shape — the filter executor parses ONLY this shape, no flexible fallbacks. -->

<!-- 9-phase index map (PINNED post plan 22-06): -->
<!--   phases[0] = intake (CR-01) -->
<!--   phases[1] = classify (CR-02) -->
<!--   phases[2] = gather-context (CR-03) -->
<!--   phases[3] = load-playbook (CR-04) -->
<!--   phases[4] = extract-clauses (CR-05) -->
<!--   phases[5] = risk-analysis (CR-06, LLM_BATCH_AGENTS, batch_size=5) -->
<!--   phases[6] = filter-redline-candidates (PROGRAMMATIC, no batch_size, no system_prompt_template) -->
<!--   phases[7] = redline-generation (CR-07, LLM_BATCH_AGENTS, batch_size=5) -->
<!--   phases[8] = executive-summary (CR-08, LLM_SINGLE, post_execute, output_schema=ExecutiveSummary) -->

<!-- For CR-06 (risk-analysis): workspace_inputs[0] = "clauses.json" (raw JSON array sibling written -->
<!-- by CR-05 — plan 22-08 patched in this plan to ALSO write a clauses.json sibling). -->

<!-- For CR-07 (redline-generation): workspace_inputs[0] = "redline-candidates.json" -->
<!-- (filtered subset of risk-analysis.json — written by the phases[6] filter executor). -->

<!-- Schemas plan 22-09 introduces: -->

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


class Redline(BaseModel):
    clause_index: int = Field(..., ge=0)
    original_text: str = Field(..., min_length=1)
    proposed_text: str = Field(..., min_length=1)
    rationale: str = Field(..., min_length=20)
    fallback_positions: list[str] = Field(default_factory=list, max_length=5)
```
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Populate CR-06 + CR-07 prompts; add ClauseRisk + Redline + RiskGrade; wire filter executor</name>
  <files>backend/app/harnesses/contract_review.py</files>
  <read_first>
    - backend/app/harnesses/contract_review.py (post-Plan-22-08 state — find phases[5] "risk-analysis", phases[6] "filter-redline-candidates" stub, phases[7] "redline-generation" stubs)
    - backend/app/services/harness_engine.py (lines 845-1099 — LLM_BATCH_AGENTS dispatcher and merge logic; confirm CANONICAL output shape is `{item_index, status, result: {text, terminal}}`)
    - backend/app/harnesses/smoke_echo.py (lines 173-187 — batch-process LLM_BATCH_AGENTS analog with batch_size, system_prompt_template format)
    - .planning/phases/22-contract-review-harness-docx-deliverable/22-CONTEXT.md (D-22-06, D-22-07, D-22-08, D-22-13)
    - .planning/phases/22-contract-review-harness-docx-deliverable/22-PATTERNS.md (lines 540-557 — phase_tools curation pattern)
  </read_first>
  <behavior>
    - Test 1: CR-06 prompt contains the literal `GREEN`, `YELLOW`, `RED`.
    - Test 2: CR-06 prompt instructs sub-agent to call `search_documents_by_doc_ids` with `doc_ids=playbook_context.clause_category_to_playbook[clause.category]`.
    - Test 3: CR-06 prompt mentions the empty-playbook fallback (`context_quality == 'unfounded'` → use generic legal knowledge).
    - Test 4: CR-06 phase (phases[5]) has `tools=["search_documents_by_doc_ids", "analyze_document"]` exactly (no `search_documents` — D-22-06 specifies the doc-id-restricted variant).
    - Test 5: CR-06 phase (phases[5]) has `batch_size=5`.
    - Test 6: CR-07 prompt explicitly says it processes ONLY YELLOW/RED clauses (pre-filtered by phases[6]).
    - Test 7: CR-07 prompt instructs sub-agent to output original/proposed_text/rationale/fallback_positions JSON.
    - Test 8: CR-07 phase (phases[7]) has `batch_size=5`.
    - Test 9: ClauseRisk schema validates RiskGrade enum, requires rationale >=20 chars.
    - Test 10: Redline schema validates non-empty original_text + proposed_text.
    - Test 11: filter-redline-candidates phase (phases[6]) has `name == "filter-redline-candidates"`, `batch_size is None` (PROGRAMMATIC, not batch), and `executor is _phase_filter_redline_candidates` (no longer the stub).
    - Test 12 (ISSUE-25): `_phase5_extract_clauses` (CR-05 in plan 22-08) writes BOTH clauses.md AND clauses.json. The two contents represent the same clause data (parse JSON from both, assert equal).
  </behavior>
  <action>
    Edit `backend/app/harnesses/contract_review.py`:

    **A) Add `RiskGrade` enum + `ClauseRisk` + `Redline` schemas** below ClauseExtractionResult (after Plan 22-08 left off):
    ```python
    # ---------------------------------------------------------------------------
    # CR-06 / CR-07 — Risk + Redline schemas
    # ---------------------------------------------------------------------------

    class RiskGrade(str, Enum):
        GREEN = "GREEN"
        YELLOW = "YELLOW"
        RED = "RED"


    class ClauseRisk(BaseModel):
        clause_index: int = Field(..., ge=0, description="Position in clauses.md JSON array")
        clause_category: str
        clause_heading: str
        risk_grade: RiskGrade
        rationale: str = Field(..., min_length=20, max_length=2000,
            description="Why this grade — must reference playbook docs OR generic standards if unfounded")
        alternative_language: str | None = Field(None, max_length=4000,
            description="Suggested replacement text (None for GREEN clauses)")
        grounding_doc_ids: list[str] = Field(default_factory=list, max_length=10,
            description="Playbook doc IDs that grounded this assessment; empty if context_quality='unfounded'")


    class Redline(BaseModel):
        clause_index: int = Field(..., ge=0)
        clause_category: str
        original_text: str = Field(..., min_length=1, max_length=10_000)
        proposed_text: str = Field(..., min_length=1, max_length=10_000)
        rationale: str = Field(..., min_length=20, max_length=2000)
        fallback_positions: list[str] = Field(default_factory=list, max_length=5,
            description="Acceptable lesser positions if proposed_text is rejected")
    ```

    Add `from enum import Enum` to the imports if not already present (smoke_echo.py uses Enum via PhaseType import; verify).

    **B) Replace CR-06 (`risk-analysis`, phases[5]) `system_prompt_template`** with this exact text:
    ```python
    system_prompt_template=(
        "You are assessing a single contract clause for risk against the user's playbook.\n\n"
        "INPUTS PROVIDED PER SUB-AGENT (one clause per agent):\n"
        "  - clause: the JSON object {clause_index, category, heading, text, position}\n"
        "  - playbook-context.md (workspace): includes clause_category_to_playbook map and\n"
        "    context_quality flag ('founded' or 'unfounded' per D-22-07).\n"
        "  - review-context.md (workspace): user's stated perspective, deadline, focus areas.\n\n"
        "TOOLS (curated):\n"
        "  - search_documents_by_doc_ids(query, doc_ids, top_k=8): D-22-06 — call this with\n"
        "    query=<clause.text> and doc_ids=<playbook_context.clause_category_to_playbook[clause.category]>\n"
        "    to retrieve precise grounding from the playbook docs that cover THIS category.\n"
        "  - analyze_document(doc_id, question): read a specific playbook doc more deeply.\n\n"
        "EMPTY-PLAYBOOK FALLBACK (D-22-07):\n"
        "  If context_quality == 'unfounded' or doc_ids is empty for this clause's category:\n"
        "  assess against industry-standard legal expectations for the contract type.\n"
        "  Set grounding_doc_ids=[] and explicitly say 'unfounded — generic standards' in the rationale.\n\n"
        "GRADING RUBRIC:\n"
        "  GREEN  — clause matches playbook expectations OR is benign for this party's perspective.\n"
        "  YELLOW — clause is acceptable with caveats, or deviates from playbook but is negotiable.\n"
        "  RED    — clause is materially adverse to this party, conflicts with playbook firm-line, or\n"
        "           creates compliance/regulatory exposure.\n\n"
        "OUTPUT: respond as a single JSON object matching ClauseRisk schema:\n"
        "  {\"clause_index\": <int>, \"clause_category\": \"<one of 13>\", \"clause_heading\": \"<str>\",\n"
        "   \"risk_grade\": \"GREEN\"|\"YELLOW\"|\"RED\",\n"
        "   \"rationale\": \"<>=20 char explanation citing the playbook doc id(s) you grounded against>\",\n"
        "   \"alternative_language\": \"<for YELLOW/RED: a paragraph of suggested replacement text;\n"
        "                                for GREEN: null>\",\n"
        "   \"grounding_doc_ids\": [\"<uuid-1>\", ...]}\n"
        "Do NOT cite the contract text verbatim in your rationale — just summarize the issue.\n"
        "Stay focused: ONE clause per sub-agent, ONE JSON object out, no prose around it."
    ),
    ```

    Update `phases[5]` (risk-analysis): ensure `tools=["search_documents_by_doc_ids", "analyze_document"]` and `batch_size=5`. Plan 22-06 set this already — verify, do not duplicate.

    **C) Replace CR-07 (`redline-generation`, phases[7]) `system_prompt_template`** with this exact text:
    ```python
    system_prompt_template=(
        "You are drafting a precise redline for ONE problematic clause from the contract.\n\n"
        "FILTER: this phase processes ONLY redline candidates (YELLOW + RED, pre-filtered by\n"
        "the filter-redline-candidates PROGRAMMATIC step at phases[6]). GREEN clauses are\n"
        "already excluded — your sub-agent will not see them.\n\n"
        "INPUTS PER SUB-AGENT:\n"
        "  - clause_risk: the JSON {clause_index, category, heading, original_text, risk_grade,\n"
        "    rationale, alternative_language, grounding_doc_ids}\n"
        "  - playbook-context.md: same as CR-06.\n"
        "  - review-context.md: same as CR-06.\n\n"
        "TOOLS:\n"
        "  - search_documents_by_doc_ids — for re-grounding if the alternative_language hint from CR-06\n"
        "    needs refinement; same doc_ids logic as CR-06.\n"
        "  - analyze_document — same usage.\n\n"
        "PROCEDURE:\n"
        "  1. Read the original clause text + CR-06's grade and alternative_language.\n"
        "  2. Draft a CONCRETE redline: original (verbatim), proposed (precise replacement text), rationale (>=20 chars).\n"
        "  3. Provide UP TO 5 fallback_positions: ordered list of progressively-weaker concessions,\n"
        "     so the negotiating attorney can decide which to accept.\n"
        "  4. Style: use plain English; preserve jurisdiction-appropriate legal phrasing where the\n"
        "     playbook docs use specific language (e.g. Indonesian KUH Perdata phrasing for Indonesian-law contracts).\n\n"
        "OUTPUT: a single JSON object matching Redline schema:\n"
        "  {\"clause_index\": <int>, \"clause_category\": \"<str>\",\n"
        "   \"original_text\": \"<verbatim>\",\n"
        "   \"proposed_text\": \"<verbatim replacement>\",\n"
        "   \"rationale\": \"<>=20 chars>\",\n"
        "   \"fallback_positions\": [\"<position 1, more aggressive>\", \"<position 2, milder>\", ...]}\n"
        "Stay focused: ONE clause, ONE JSON object, no prose around it."
    ),
    ```

    Set `phases[7]` (redline-generation): `tools=["search_documents_by_doc_ids", "analyze_document"]`, `batch_size=5`, `workspace_inputs=["redline-candidates.json", "playbook-context.md", "review-context.md"]` (FIRST item is the items source for the batch dispatcher).

    Add an inline comment above CR-07's PhaseDefinition (phases[7]): `# CR-07 (phases[7]): items pre-filtered to YELLOW/RED by phases[6] filter (ISSUE-06). No GREEN waste.`

    **D) ISSUE-06 wiring (DECIDED, no alternatives):**
    - Plan 22-06 already inserted a `filter-redline-candidates` PhaseDefinition at index [6] of CONTRACT_REVIEW.phases with executor=_phase_stub_not_implemented.
    - This plan REPLACES that stub by setting executor=_phase_filter_redline_candidates and adding the executor function below.
    - Do NOT add a new PhaseDefinition. Do NOT call CONTRACT_REVIEW.phases.insert(...). Only swap the .executor attribute on the existing phases[6].

    Implementation: define the filter executor, then swap the .executor on phases[6] in-place after CONTRACT_REVIEW is constructed:

    ```python
    async def _phase_filter_redline_candidates(
        *, inputs: dict[str, str], token: str, thread_id: str, harness_run_id: str
    ) -> dict:
        """ISSUE-06: filter risk-analysis.json to YELLOW/RED clauses for CR-07.

        Parses ONLY the canonical engine merge shape (interfaces section pin):
            [{item_index, status: 'ok'|'error', result: {text, terminal: <ClauseRisk dict>}}, ...]
        """
        risk_analysis_json_text = (inputs or {}).get("risk-analysis.json", "")
        if not risk_analysis_json_text.strip():
            return {"error": "risk_analysis_missing", "code": "NO_RISK",
                    "detail": "risk-analysis.json is empty"}
        try:
            data = json.loads(risk_analysis_json_text)
        except Exception as exc:
            return {"error": "risk_parse_failed", "code": "PARSE",
                    "detail": str(exc)[:500]}
        if not isinstance(data, list):
            return {"error": "risk_shape_invalid", "code": "SHAPE",
                    "detail": "expected JSON array of merge rows"}

        # Canonical merge shape ONLY — engine writes {item_index, status, result: {text, terminal}}.
        risky = [
            row["result"]["terminal"]
            for row in data
            if isinstance(row, dict)
            and row.get("status") == "ok"
            and isinstance(row.get("result"), dict)
            and isinstance(row["result"].get("terminal"), dict)
            and row["result"]["terminal"].get("risk_grade") in ("YELLOW", "RED")
        ]

        return {
            "content": json.dumps(risky, ensure_ascii=False, indent=2),
            "candidate_count": len(risky),
            "total_risks": len(data),
        }
    ```

    Then immediately after the `CONTRACT_REVIEW = HarnessDefinition(...)` literal, add (in plan 22-09 patch):
    ```python
    # ISSUE-06: replace plan 22-06's stub at phases[6] with the real filter executor.
    # Do NOT add a new PhaseDefinition; the slot is already in place.
    CONTRACT_REVIEW.phases[6].executor = _phase_filter_redline_candidates
    ```

    **E) ISSUE-04 + ISSUE-25 — CR-05 sibling clauses.json write (patch in plan 22-08's executor body):**

    LLM_BATCH_AGENTS dispatcher requires `workspace_inputs[0]` to be a clean JSON ARRAY OF DICTS. CR-05 writes clauses.md (markdown wrapper), so we ALSO write clauses.json (raw JSON array) for CR-06 to consume.

    In `_phase5_extract_clauses` (Plan 22-08), AFTER computing `deduped`, ALSO write a sibling raw-JSON file:
    ```python
    # ISSUE-04 / ISSUE-25: write a raw-JSON sibling for CR-06 LLM_BATCH_AGENTS consumption.
    clauses_json_array = [c.model_dump() for c in deduped]
    try:
        ws_inst = WorkspaceService(token=token)
        await ws_inst.write_text_file(
            thread_id, "clauses.json",
            json.dumps(clauses_json_array, ensure_ascii=False, indent=2),
            source="harness",
        )
    except Exception as exc:
        logger.warning("CR-05 sibling clauses.json write failed: %s", exc)
    ```

    CR-06 PhaseDefinition (phases[5]) `workspace_inputs` is set by plan 22-06 to `["clauses.json", "playbook-context.md", "review-context.md"]` already — clauses.json FIRST so engine reads it as items source.
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pytest tests/harnesses/test_contract_review_cr06_cr07.py -v --tb=short && python -c "from app.harnesses.contract_review import ClauseRisk, Redline, RiskGrade; print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "GREEN\|YELLOW\|RED" backend/app/harnesses/contract_review.py | head -1` returns line count `>= 6` (enum members + prompt content)
    - `grep -c "search_documents_by_doc_ids" backend/app/harnesses/contract_review.py` returns `>= 4` (CR-06 prompt + tools list, CR-07 prompt + tools list)
    - `grep -c "context_quality == 'unfounded'\|unfounded" backend/app/harnesses/contract_review.py` returns `>= 2`
    - `grep -c "fallback_positions" backend/app/harnesses/contract_review.py` returns `>= 2`
    - `python -c "from app.harnesses.contract_review import CONTRACT_REVIEW; assert CONTRACT_REVIEW.phases[5].batch_size == 5; assert CONTRACT_REVIEW.phases[7].batch_size == 5; print('OK')"` prints `OK`
    - `python -c "from app.harnesses.contract_review import CONTRACT_REVIEW; assert CONTRACT_REVIEW.phases[6].name == 'filter-redline-candidates'; assert CONTRACT_REVIEW.phases[6].batch_size is None; print('OK')"` prints `OK` (filter is PROGRAMMATIC, not batch)
    - `python -c "from app.harnesses.contract_review import CONTRACT_REVIEW, _phase_filter_redline_candidates; assert CONTRACT_REVIEW.phases[6].executor is _phase_filter_redline_candidates; print('OK')"` prints `OK`
    - `python -c "from app.harnesses.contract_review import CONTRACT_REVIEW; assert CONTRACT_REVIEW.phases[5].tools == ['search_documents_by_doc_ids', 'analyze_document']; print('OK')"` prints `OK`
    - `python -c "from app.harnesses.contract_review import CONTRACT_REVIEW; assert CONTRACT_REVIEW.phases[7].tools == ['search_documents_by_doc_ids', 'analyze_document']; print('OK')"` prints `OK`
    - `python -c "from app.harnesses.contract_review import ClauseRisk, RiskGrade; cr = ClauseRisk(clause_index=0, clause_category='Liability', clause_heading='X', risk_grade=RiskGrade.RED, rationale='because the clause is materially adverse to buyer'); print(cr.risk_grade)"` prints `RiskGrade.RED`
  </acceptance_criteria>
  <done>CR-06 + CR-07 prompts populated; schemas added; tools curated; batch_size set; phases[6] filter executor wired; clauses.json sibling write patched into CR-05.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Add CR-06 + CR-07 + filter + sibling-write tests</name>
  <files>backend/tests/harnesses/test_contract_review_cr06_cr07.py</files>
  <read_first>
    - backend/app/harnesses/contract_review.py (post-Task-1 state)
    - backend/tests/harnesses/test_contract_review_cr03_cr04.py (analog test patterns from plan 22-07)
  </read_first>
  <behavior>
    See behaviors 1-12 in Task 1.
  </behavior>
  <action>
    Create `backend/tests/harnesses/test_contract_review_cr06_cr07.py` with 12 tests. Pure shape + schema tests for tests 1-11. Async test for test 12 (CR-05 sibling write).

    Concrete test 6 (CR-07 YELLOW/RED only):
    ```python
    def test_cr07_prompt_skips_green_clauses():
        from app.harnesses.contract_review import CONTRACT_REVIEW
        prompt = CONTRACT_REVIEW.phases[7].system_prompt_template
        # Must explicitly mention skipping GREEN
        assert "ONLY redline candidates" in prompt or "ONLY YELLOW" in prompt
        assert "RED" in prompt
        assert "GREEN" in prompt and ("excluded" in prompt or "not see" in prompt or "skip" in prompt.lower())
    ```

    Concrete test 9 (ClauseRisk validation):
    ```python
    def test_clause_risk_requires_rationale_min_20_chars():
        from app.harnesses.contract_review import ClauseRisk, RiskGrade
        with pytest.raises(Exception):
            ClauseRisk(
                clause_index=0, clause_category="Liability", clause_heading="X",
                risk_grade=RiskGrade.GREEN, rationale="too short",
            )
    ```

    Concrete test 11 (filter phase):
    ```python
    def test_filter_phase_is_programmatic_at_index_6():
        from app.harnesses.contract_review import CONTRACT_REVIEW, _phase_filter_redline_candidates
        from app.harnesses.types import PhaseType
        assert CONTRACT_REVIEW.phases[6].name == "filter-redline-candidates"
        assert CONTRACT_REVIEW.phases[6].phase_type == PhaseType.PROGRAMMATIC
        assert CONTRACT_REVIEW.phases[6].batch_size is None
        assert CONTRACT_REVIEW.phases[6].executor is _phase_filter_redline_candidates
    ```

    Concrete test 12 (ISSUE-25 — clauses.md and clauses.json sibling write):
    ```python
    @pytest.mark.asyncio
    async def test_phase5_writes_both_clauses_md_and_clauses_json(monkeypatch):
        """ISSUE-25: CR-05 must write BOTH clauses.md (markdown) and clauses.json (raw array).
        The two contents must represent the same clause data."""
        from app.harnesses.contract_review import _phase5_extract_clauses
        # Mock LLM to return a canned clause-extraction response (single chunk)
        canned = json.dumps({
            "clauses": [
                {"category": "Liability", "heading": "1. LIABILITY",
                 "text": "Cap at USD 100k.", "position": 0},
            ],
            "chunk_index": 0, "total_chunks": 1,
        })
        # Patch the LLM call site + WorkspaceService.write_text_file
        ws_writes = {}  # filename -> content
        async def _write(thread_id, filename, content, source="agent"):
            ws_writes[filename] = content
            return {"ok": True}
        ws_mock = MagicMock()
        ws_mock.write_text_file = AsyncMock(side_effect=_write)
        ws_mock.read_file = AsyncMock(return_value={"content": "fake contract text"})
        with patch("app.harnesses.contract_review.WorkspaceService", return_value=ws_mock):
            with patch("app.harnesses.contract_review._llm_extract_clauses_chunk",
                       AsyncMock(return_value=json.loads(canned))):
                await _phase5_extract_clauses(
                    inputs={"contract-text.md": "fake contract text"},
                    token="tok", thread_id="thr", harness_run_id="run",
                )
        # Both files must have been written
        assert "clauses.md" in ws_writes, "CR-05 must write clauses.md"
        assert "clauses.json" in ws_writes, "CR-05 must write clauses.json sibling (ISSUE-25)"
        # The JSON content from clauses.json must parse to the same data as the JSON block in clauses.md
        json_array = json.loads(ws_writes["clauses.json"])
        # Extract the JSON block from the clauses.md markdown wrapper
        import re
        m = re.search(r"```json\s*(\[.*?\])\s*```", ws_writes["clauses.md"], re.DOTALL)
        assert m, "clauses.md must contain a ```json``` array code block"
        md_array = json.loads(m.group(1))
        # Compare by category + heading + text (the relevant fields)
        def _key(c): return (c.get("category"), c.get("heading"), c.get("text"))
        assert sorted(_key(c) for c in json_array) == sorted(_key(c) for c in md_array)
    ```
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pytest tests/harnesses/test_contract_review_cr06_cr07.py -v --tb=short</automated>
  </verify>
  <acceptance_criteria>
    - `pytest backend/tests/harnesses/test_contract_review_cr06_cr07.py -v` exits 0 with 12 tests passing
    - `grep -c "RiskGrade\|ClauseRisk\|Redline" backend/tests/harnesses/test_contract_review_cr06_cr07.py` returns `>= 6`
    - `grep -c "filter-redline-candidates\|_phase_filter_redline_candidates" backend/tests/harnesses/test_contract_review_cr06_cr07.py` returns `>= 2`
    - `grep -c "clauses.json" backend/tests/harnesses/test_contract_review_cr06_cr07.py` returns `>= 2`
  </acceptance_criteria>
  <done>12 tests pass — CR-06/07 prompt + schema + tooling + filter executor + clauses.json sibling write all locked in.</done>
</task>

</tasks>

<truths>
- D-22-06 (per-clause grounding via doc-id filter) — CR-06/07 prompts use `search_documents_by_doc_ids` from plan 22-02.
- D-22-07 (empty-playbook fallback) — explicit branch in CR-06 prompt; sub-agent emits `grounding_doc_ids=[]` + 'unfounded' marker in rationale.
- D-22-08 (authority hierarchy) — implicit through CR-04's playbook-context.md sort; CR-06 sub-agent inherits ordering by reading the file.
- BATCH-01..07 (Phase 21 batch dispatcher) reused unchanged — JSONL append, asyncio.gather, mid-batch resume work out of the box.
- B4 single-registry (SEC-04): each batch sub-agent's LLM call goes through `sub_agent_loop.py` which inherits the parent's egress_filter wrap.
- PANEL-03: write_todos/read_todos already stripped via PANEL_LOCKED_EXCLUDED_TOOLS — no need to specify.
- ISSUE-06 wiring decided: plan 22-06 already inserted phases[6] as a stub; this plan only swaps the .executor attribute. No insert(), no new PhaseDefinition.
- Engine merge shape is canonical: `{item_index, status, result: {text, terminal}}`. Filter executor parses only this shape — no defensive multi-shape fallbacks.
</truths>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Clause text → CR-06 sub-agent → cloud LLM | Real PII routes through SEC-04 egress filter wrap |
| Sub-agent → search_documents_by_doc_ids | LLM-supplied doc_ids list bounded to ≤ 50 (plan 22-02 validation) |
| Sub-agent JSON output → JSONL append → CR-08 | Untrusted JSON; Pydantic validate at engine accumulator boundary |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-22-09-01 | Information Disclosure | Clause PII in CR-06 LLM payload | mitigate | SEC-04 egress filter wrap on each sub-agent LLM call (existing sub_agent_loop wrap) |
| T-22-09-02 | Tampering | LLM hallucinates a doc_id outside the playbook | accept | search_documents_by_doc_ids returns no results for nonexistent doc_ids; bounded cost |
| T-22-09-03 | DoS | Pathological 200-clause contract * 5 sub-agents = many LLM calls | accept | Phase timeout 1800s + MAX_SUB_AGENT_ROUNDS env cap; user-controlled tradeoff |
| T-22-09-04 | Repudiation | Risk grades not auditable | mitigate | OBS-02 thread_id correlation logging; LangSmith tracing covers sub-agent calls (existing) |
</threat_model>

<verification>
1. `pytest backend/tests/harnesses/test_contract_review_cr06_cr07.py -v` exits 0
2. `pytest backend/tests/harnesses/test_contract_review_skeleton.py backend/tests/harnesses/test_contract_review_cr03_cr04.py backend/tests/harnesses/test_contract_review_cr05.py -v` exits 0 (regression)
3. `python -c "from app.main import app; print('OK')"` prints `OK`
</verification>

<success_criteria>
- CR-06 + CR-07 prompts populated with full grading rubric + tool guidance + empty-playbook fallback
- ClauseRisk + Redline schemas available for CR-08 (plan 22-10)
- filter-redline-candidates phase (phases[6]) executor wired (replacing plan 22-06's stub)
- CR-05 sibling clauses.json write patched in (ISSUE-04 + ISSUE-25)
- Phase 21 batch dispatcher reused without modification — D-05..D-07 invariants honored
- Tool curation: only `search_documents_by_doc_ids` + `analyze_document` reach sub-agents
</success_criteria>

<output>
After completion, create `.planning/phases/22-contract-review-harness-docx-deliverable/22-09-SUMMARY.md`.
</output>
