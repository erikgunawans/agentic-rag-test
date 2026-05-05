---
phase: 22-contract-review-harness-docx-deliverable
plan: "09"
subsystem: harness
tags: [harness, contract-review, batch-agents, risk-analysis, redlines, tdd, review-fixes]
dependency_graph:
  requires:
    - phase: 22-08
      provides: _phase5_extract_clauses writing clauses.json; REVIEW #4 PROGRAMMATIC executor contract
    - phase: 22-07
      provides: PlaybookContext schema + clause_category_to_playbook for CR-06 grounding
    - phase: 22-06
      provides: 9-phase skeleton with CR-06/filter/CR-07 as stubs
    - phase: 22-02
      provides: search_documents_by_doc_ids tool (curated for CR-06/07)
  provides:
    - _parse_subagent_json_terminal: extracts JSON from ```json``` fenced blocks in LLM terminal text (REVIEW #2)
    - _phase_filter_redline_candidates: parses risk-analysis.json canonical merge shape + JOIN original_text from clauses.json (REVIEW #2 + #3)
    - RiskGrade/ClauseRisk/RedlineCandidate/Redline Pydantic schemas
    - CR-06 prompt: GREEN/YELLOW/RED rubric + search_documents_by_doc_ids grounding
    - CR-07 prompt: verbatim original_text usage + fallback_positions output
    - phases[6] workspace_inputs extended to ["risk-analysis.json", "clauses.json"] (REVIEW #3)
  affects:
    - plan-22-10 (CR-08 executive summary reads redlines.json produced by CR-07)
    - plan-22-12 (E2E pytest — CR-06/07/filter are now real, not stubs)

tech-stack:
  added: []
  patterns:
    - "REVIEW #2 closed: filter executor reads result.terminal.text (full LLM response) from canonical engine merge shape {item_index, status, result: {text, terminal: {text}}} — NOT a fictional result.terminal.risk_grade key."
    - "_parse_subagent_json_terminal: 4-strategy JSON extraction (fenced ```json```, fenced ``` no-tag, first-balanced-brace, full-text) — returns None on unparseable."
    - "REVIEW #3 closed: filter joins clauses.json by array index (clause_index) to splice original_text into RedlineCandidate. Rows with unmatched clause_index are DROPPED (logged), never forwarded with empty original_text."
    - "REVIEW #1 invariant: tools=['search_documents_by_doc_ids'] only for CR-06 and CR-07; analyze_document never appears in any tools= list."
    - "Tool curation: curated_tools propagated to sub-agents via parent_tool_context={'phase_tools': ...} in harness_engine.py LLM_BATCH_AGENTS dispatcher."
    - "D-22-07 empty-playbook fallback: CR-06 prompt instructs context_quality=='unfounded' mode using generic legal standards, grounding_doc_ids=[], explicit rationale note."

key-files:
  created:
    - backend/tests/harnesses/test_contract_review_cr06_cr07.py
  modified:
    - backend/app/harnesses/contract_review.py

key-decisions:
  - "REVIEW #2 closed by _parse_subagent_json_terminal: sub-agent terminal text is the full LLM response (run_sub_agent_loop yields {'_terminal_result': {'text': full_response}}). Filter extracts JSON via regex on ```json``` fenced blocks — not from a pre-parsed key."
  - "REVIEW #3 closed by clause_index JOIN: clauses.json written by CR-05 (plan 22-08, ISSUE-25) is consumed as a lookup table; the array position is the clause_index. Unmatched rows are dropped to preserve original_text invariant."
  - "Comment references to 'no analyze_document' in CR-06 phase description strings are anti-pattern documentation, not actual tool use. All actual tools= lists contain only search_documents_by_doc_ids."
  - "TDD: 16 tests written RED first (commit d6a1b37), implementation GREEN second (commit 9a3c3a2). All 57 cumulative harness tests pass."

metrics:
  duration: ~8 minutes
  completed: "2026-05-05T11:39:39Z"
  tasks: 2 (Task 1 RED + GREEN for implementation + Task 2 tests created first as RED)
  files_modified: 2
---

# Phase 22 Plan 09: CR-06/CR-07 Batch Risk and Redlines Summary

**CR-06 (risk analysis, LLM_BATCH_AGENTS) + CR-07 (redline generation, LLM_BATCH_AGENTS) prompts and schemas implemented with corrected filter executor that parses sub-agent terminal text (REVIEW #2) and joins original_text from clauses.json by clause_index (REVIEW #3).**

## Performance

- **Duration:** ~8 minutes
- **Completed:** 2026-05-05T11:39:39Z
- **Tasks:** 2 (RED commit + GREEN commit following TDD)
- **Files modified:** 2

## Accomplishments

- Closed REVIEW #2: `_parse_subagent_json_terminal` helper extracts JSON from the LLM's full text terminal response (the `result.terminal.text` field in the engine's canonical batch merge shape), handling `\`\`\`json\`\`\`` fences, bare fences, first-balanced-brace, and full-text fallbacks. Returns None on unparseable input.
- Closed REVIEW #3: `_phase_filter_redline_candidates` joins each YELLOW/RED `ClauseRisk` row against `clauses.json` (written by CR-05 per plan 22-08) by array index to attach `original_text`. Rows where `clause_index` has no match in `clauses.json` are dropped (logged as warning) — empty `original_text` NEVER reaches CR-07.
- Added `RiskGrade`, `ClauseRisk`, `RedlineCandidate`, `Redline` Pydantic schemas with proper field constraints (rationale min_length=20, original_text min_length=1, fallback_positions max_length=5).
- Populated CR-06 system_prompt_template with full GREEN/YELLOW/RED rubric, `search_documents_by_doc_ids` grounding instructions, `clause_category_to_playbook` lookup guidance, and D-22-07 empty-playbook fallback.
- Populated CR-07 system_prompt_template with YELLOW/RED filter note, `original_text` verbatim usage instruction (REVIEW #3), `proposed_text`/`rationale`/`fallback_positions` output schema.
- Wired phases[6] (`filter-redline-candidates`) with `_phase_filter_redline_candidates` executor and `workspace_inputs=["risk-analysis.json", "clauses.json"]` (REVIEW #3 requires both).
- 16 new tests all GREEN; 57 cumulative harness tests pass (no regressions).

## Task Commits

1. **Task 1 (RED):** `d6a1b37` — test(22-09): RED — 16 CR-06/CR-07 tests for prompts, schemas, filter parse+join (REVIEW #2+#3)
2. **Task 2 (GREEN):** `9a3c3a2` — feat(22-09): GREEN — CR-06/CR-07 prompts + schemas + filter executor (REVIEW #2 + #3)

## Files Created/Modified

- `backend/app/harnesses/contract_review.py` — Added RiskGrade/ClauseRisk/RedlineCandidate/Redline schemas; added _parse_subagent_json_terminal helper; added _phase_filter_redline_candidates executor; populated CR-06/CR-07 system_prompt_template; wired phases[6] executor + workspace_inputs
- `backend/tests/harnesses/test_contract_review_cr06_cr07.py` — 16 tests covering all behaviors (Tests 1-15 from plan, split Test 12 into 2 functions = 16 total)

## Decisions Made

- REVIEW #2 parse strategy: `\`\`\`json\`\`\`` fenced block → `\`\`\`` bare fenced → first balanced `{...}` → full-text json.loads. None returned on failure. This handles all LLM output variations gracefully.
- REVIEW #3 join strategy: clauses.json is a plain JSON array; array index IS the clause_index (matches CR-05 write pattern). No explicit `clause_index` field in the Clause schema — array position is authoritative.
- Comment references to "no analyze_document" in phase description strings are anti-pattern documentation (helping future devs); they don't affect runtime behavior. All `tools=` lists contain only `search_documents_by_doc_ids`.
- TDD gate compliance: RED commit (d6a1b37) precedes GREEN commit (9a3c3a2). Both present in git log.

## Deviations from Plan

### None

Plan executed exactly as written. The only implementation detail resolved inline was:

**1. [Rule 2 - Missing critical] Test count 15 vs 16**
- **Found during:** Task 1 (RED phase)
- **Issue:** Plan specifies 15 tests but Test 12 logically covers two cases: (a) fenced block parsing and (b) None on garbage. Split into two test functions for clarity while staying within the plan's behavioral spec.
- **Fix:** `test_parse_subagent_json_terminal_handles_fenced_block` + `test_parse_subagent_json_terminal_returns_none_on_garbage` = 16 tests total.
- **Impact:** Minor. All 16 pass; plan's behavioral assertions covered.

## Known Stubs

Phases 8 (CR-08 executive summary + DOCX) remains as `_phase_stub_not_implemented`. Plan 22-10 fills it in.

## Threat Flags

No new network endpoints or auth paths. All threats in plan's STRIDE register are mitigated by implementation:

| Flag | File | Description |
|------|------|-------------|
| T-22-09-02 mitigated | contract_review.py | _parse_subagent_json_terminal returns None on malformed JSON; skipped + counted |
| T-22-09-03 mitigated | contract_review.py | Rows where clause_index has no clauses.json match are DROPPED (REVIEW #3 join) |

## TDD Gate Compliance

- RED gate: `test(22-09):` commit d6a1b37 (16 failing tests written first)
- GREEN gate: `feat(22-09):` commit 9a3c3a2 (implementation makes all 16 pass)
- REFACTOR: no refactor pass needed (implementation clean on first pass)

## Next Phase Readiness

- Plan 22-10 (CR-08 executive summary + DOCX): ready. redlines.json will be produced by CR-07 using the real prompt.
- Plan 22-12 (E2E pytest): CR-06/filter/CR-07 are no longer stubs — E2E tests can exercise the full pipeline with mocked LLM.

## Self-Check: PASSED

- FOUND: backend/app/harnesses/contract_review.py (modified)
- FOUND: backend/tests/harnesses/test_contract_review_cr06_cr07.py (created)
- FOUND commit d6a1b37 (RED — 16 tests)
- FOUND commit 9a3c3a2 (GREEN — implementation)
- tool_service.py lines 1-1283 sha256: cb63cf3e60d5f6380e2e41f63b1fe9122f58ab4648808b0f2114e452cd45ddb2 (UNCHANGED)
- All 57 cumulative harness tests: PASSED
- phases[5].batch_size == 5: VERIFIED
- phases[7].batch_size == 5: VERIFIED
- phases[6].name == 'filter-redline-candidates': VERIFIED
- phases[5].tools == ['search_documents_by_doc_ids']: VERIFIED
- phases[6].workspace_inputs contains both 'risk-analysis.json' and 'clauses.json': VERIFIED
