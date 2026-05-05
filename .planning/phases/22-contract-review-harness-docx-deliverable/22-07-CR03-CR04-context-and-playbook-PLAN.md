---
phase: 22-contract-review-harness-docx-deliverable
plan: 07
type: execute
wave: 3
depends_on: ["22-02", "22-06"]
files_modified:
  - backend/app/harnesses/contract_review.py
  - backend/tests/harnesses/test_contract_review_cr03_cr04.py
autonomous: true
requirements: [CR-03, CR-04]
must_haves:
  truths:
    - "CR-03 (gather-context) generates ONE combined free-form question via llm_human_input — single HIL pause (D-22-09)"
    - "CR-03 persists user reply VERBATIM to review-context.md — no parser, no extraction (D-22-10, D-22-11)"
    - "CR-04 (load-playbook) is an LLM_AGENT phase, max 10 rounds"
    - "REVIEW #1: CR-04's curated tools are now phase_tools=['list_playbook_documents', 'search_documents', 'search_documents_by_doc_ids'] — `analyze_document` does NOT exist in the codebase (verified `grep -c analyze_document backend/app/services/tool_service.py` returns 0)"
    - "CR-04 sub-agent uses `list_playbook_documents` (plan 22-02) to enumerate doc_ids+titles+summaries, then optionally `search_documents_by_doc_ids` for per-doc deep-dive"
    - "CR-04 prompt embeds D-22-05 filter_tags=['playbook'] guidance for any plain `search_documents` calls + D-22-06 mapping from clause categories to playbook doc_ids"
    - "CR-04 sets context_quality='unfounded' in playbook-context.md JSON when zero playbook docs returned by list_playbook_documents (D-22-07 empty-playbook fallback)"
    - "CR-04 prompt orders authority hierarchy: user-workspace > regulatory_intel > 3rd-party (D-22-08)"
  artifacts:
    - path: "backend/app/harnesses/contract_review.py"
      provides: "CR-03 + CR-04 phase prompts populated; PlaybookContext Pydantic schema added; phase_tools updated to use list_playbook_documents (REVIEW #1)"
      contains: "list_playbook_documents"
    - path: "backend/tests/harnesses/test_contract_review_cr03_cr04.py"
      provides: "Tests for CR-03 prompt shape, CR-04 tools curation (no analyze_document references), JSON output schema"
  key_links:
    - from: "CR-04 sub-agent's first tool call"
      to: "list_playbook_documents() → [{doc_id, title, summary}]"
      via: "playbook discovery surface (plan 22-02 Task 1)"
      pattern: "list_playbook_documents"
    - from: "CR-04 sub-agent search_documents calls"
      to: "playbook-tagged documents"
      via: "filter_tags=['playbook'] (D-22-05) — for chunk-level RAG grounding"
      pattern: "filter_tags.*playbook"
---

<objective>
Replace the CR-03 (gather-context) and CR-04 (load-playbook) stubs in `backend/app/harnesses/contract_review.py` with real prompts. CR-03 leverages the Phase 21 LLM_HUMAN_INPUT dispatcher (already wired). CR-04 is an LLM_AGENT phase exercising the Phase 19/20 sub-agent loop with curated RAG tools.

**REVIEW #1 anchor:** the previous version of this plan listed `tools=["search_documents", "analyze_document"]`. `analyze_document` does NOT exist in this codebase (`grep -c "analyze_document" backend/app/services/tool_service.py` returns 0). Plan 22-02 introduces `list_playbook_documents` which is the actual playbook-discovery surface. This plan switches CR-04's tool list to use the real tools.

Output: Two phase prompts populated, PlaybookContext schema, tests with REVIEW #1 anti-regression guards.
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
@backend/app/harnesses/smoke_echo.py
</context>

<interfaces>
<!-- Plan 22-06 already defined the 9-phase HarnessDefinition with stubs. -->
<!-- This plan replaces phases[2] (CR-03) and phases[3] (CR-04) prompts. -->

CR-04 D-22-06 output JSON shape (plan 22-09 reads this back):
```python
class PlaybookContext(BaseModel):
    playbook_docs: list[PlaybookDoc] = Field(default_factory=list)
    clause_category_to_playbook: dict[str, list[str]] = Field(default_factory=dict)
    context_quality: str = Field(default="founded", description="'founded' or 'unfounded' (D-22-07)")
    notes: str = Field(default="", description="Free-form summary for human readers")
```

The 13 clause categories (CR-05 spec — keep verbatim):
`["Liability", "Indemnification", "IP", "Data Protection", "Confidentiality", "Warranties", "Term/Termination", "Governing Law", "Insurance", "Assignment", "Force Majeure", "Payment", "Other"]`

REVIEW #1 fix: tools list for CR-04 is now THREE tools, all from plan 22-02 + existing search_documents:
```python
tools = [
    "list_playbook_documents",        # NEW from plan 22-02 — playbook enumeration
    "search_documents",               # existing — chunk-level RAG with filter_tags
    "search_documents_by_doc_ids",    # NEW from plan 22-02 — doc-id-restricted RAG
]
```
NO `analyze_document`. NO references to it anywhere in this plan or the test file.
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Populate CR-03 prompt and CR-04 prompt + PlaybookContext schema (REVIEW #1: drop analyze_document)</name>
  <files>backend/app/harnesses/contract_review.py</files>
  <read_first>
    - backend/app/harnesses/contract_review.py (post-Plan-22-06 state — find stub system_prompt_template="STUB" entries for "gather-context" and "load-playbook")
    - backend/app/harnesses/smoke_echo.py (lines 159-172 — LLM_HUMAN_INPUT prompt analog; lines 110-120 — LLM_AGENT analog)
    - .planning/phases/22-contract-review-harness-docx-deliverable/22-CONTEXT.md (D-22-05..09 — locked decisions)
    - .planning/phases/22-contract-review-harness-docx-deliverable/22-REVIEWS.md (review finding #1)
  </read_first>
  <behavior>
    - Test 1: CR-03 prompt non-empty, contains `"Which party are you"`, instructs ONE combined question (D-22-09).
    - Test 2: CR-03 prompt does NOT mention parsing the response (D-22-10).
    - Test 3: CR-04 prompt contains `"list_playbook_documents"`, instructs max 10 rounds, mentions all 13 clause categories.
    - Test 4: CR-04 prompt instructs `"context_quality": "unfounded"` when no playbook docs found (D-22-07).
    - Test 5: CR-04 prompt instructs authority ordering (D-22-08).
    - Test 6: `CONTRACT_REVIEW.phases[3].tools == ["list_playbook_documents", "search_documents", "search_documents_by_doc_ids"]` (REVIEW #1 fix — exact list, no `analyze_document`).
    - Test 7: PlaybookContext schema accepts the empty-playbook case.
    - Test 8 (REVIEW #1 anti-regression): the entire `backend/app/harnesses/contract_review.py` file must NOT contain the string `analyze_document` (anywhere — prompt, comments, anything).
  </behavior>
  <action>
    Edit `backend/app/harnesses/contract_review.py`.

    **A) Add PlaybookContext + PlaybookDoc Pydantic models** below the existing `ContractClassification` schema:
    ```python
    # ---------------------------------------------------------------------------
    # CR-04 — Playbook Context output schema (D-22-06)
    # ---------------------------------------------------------------------------

    CLAUSE_CATEGORIES = [
        "Liability", "Indemnification", "IP", "Data Protection", "Confidentiality",
        "Warranties", "Term/Termination", "Governing Law", "Insurance",
        "Assignment", "Force Majeure", "Payment", "Other",
    ]


    class PlaybookDoc(BaseModel):
        id: str = Field(..., min_length=1, description="Document UUID from list_playbook_documents results")
        title: str = Field(..., min_length=1, max_length=300)
        summary: str = Field(..., min_length=0, max_length=300, description="<=300 char summary")
        source_priority: int = Field(default=2, ge=1, le=3,
            description="D-22-08 authority order: 1=user-workspace, 2=regulatory_intel, 3=3rd-party")


    class PlaybookContext(BaseModel):
        """CR-04 structured output written to playbook-context.md (D-22-06)."""
        playbook_docs: list[PlaybookDoc] = Field(default_factory=list)
        clause_category_to_playbook: dict[str, list[str]] = Field(default_factory=dict)
        context_quality: str = Field(default="founded",
            description="'founded' (>=1 doc) or 'unfounded' (D-22-07)")
        notes: str = Field(default="", max_length=2000)
    ```

    **B) Replace CR-03 (`gather-context`) PhaseDefinition's `system_prompt_template`** (D-22-09 single combined question, D-22-10 raw persistence) — verbatim:
    ```python
    system_prompt_template=(
        "You are gathering review context for a Contract Review run. The user just uploaded "
        "a contract and we have already classified it (see workspace input classification.md).\n\n"
        "Generate ONE combined free-form question (single paragraph, plain language) asking "
        "the user about all four topics in one breath:\n"
        "  1. Which party are you in this contract? (e.g. 'we are the buyer/customer/licensee')\n"
        "  2. Is there a deadline or pressure on this review?\n"
        "  3. Which clauses or risks should we focus on?\n"
        "  4. What's the broader deal context?\n\n"
        "Be conversational and concise (under 80 words). Acknowledge the user can answer "
        "any subset — minimal answers like 'just go' or '...' are fully valid. Respond as a JSON "
        "object {\"question\": \"<the single combined paragraph>\"}.\n"
    ),
    ```

    **C) Replace CR-04 (`load-playbook`) PhaseDefinition's `system_prompt_template`** with the REVIEW #1-corrected text (uses `list_playbook_documents` instead of nonexistent `analyze_document`):
    ```python
    system_prompt_template=(
        "You are the playbook loader for a Contract Review run. Your job: discover playbook "
        "materials in the knowledge base and produce a structured JSON map from clause categories "
        "to relevant playbook document IDs.\n\n"
        "INPUTS (workspace files):\n"
        "  - classification.md : the contract type, parties, governing law, jurisdiction\n"
        "  - review-context.md : the user's stated perspective, deadline, focus areas\n\n"
        "TOOLS (curated for CR-04):\n"
        "  - list_playbook_documents(limit=50): START HERE. Returns all documents tagged 'playbook'\n"
        "    in the user's knowledge base as [{doc_id, title, summary}, ...]. Use this once at\n"
        "    the start to know what playbook surface exists.\n"
        "  - search_documents(query, filter_tags=['playbook'], top_k=8): D-22-05 — chunk-level\n"
        "    RAG inside the playbook scope. Use when you need passage-level grounding.\n"
        "  - search_documents_by_doc_ids(query, doc_ids, top_k=8): D-22-06 — chunk-level RAG\n"
        "    restricted to specific doc_ids returned by list_playbook_documents. Use sparingly\n"
        "    in CR-04; CR-06/CR-07 will rely on it heavily.\n\n"
        "PROCEDURE (max 10 rounds):\n"
        "  1. Call list_playbook_documents() ONCE to enumerate the playbook surface.\n"
        "     Skim each doc's summary; ignore docs that are clearly off-topic for this contract type.\n"
        "  2. For each of the 13 clause categories below, decide which subset of the listed playbook\n"
        "     docs cover that category. Use search_documents(filter_tags=['playbook']) sparingly when\n"
        "     a doc summary is ambiguous and you need a passage to verify category relevance.\n"
        "  3. AUTHORITY HIERARCHY (D-22-08): when multiple docs match, weight in order —\n"
        "     (a) user-workspace uploads first, (b) regulatory_intel docs second,\n"
        "     (c) general document library third. Use source_priority=1, 2, or 3 accordingly.\n"
        "  4. Build a clause_category_to_playbook dict. EVERY category must have a list (use\n"
        "     [] if no doc covers that category). All 13 categories must appear as keys.\n\n"
        "CLAUSE CATEGORIES (use exactly these strings as JSON keys):\n"
        "  Liability, Indemnification, IP, Data Protection, Confidentiality, Warranties,\n"
        "  Term/Termination, Governing Law, Insurance, Assignment, Force Majeure, Payment, Other\n\n"
        "EMPTY PLAYBOOK FALLBACK (D-22-07): if list_playbook_documents returns ZERO documents,\n"
        "set context_quality='unfounded' and emit empty playbook_docs [] + all 13 categories\n"
        "mapping to []. Add a notes field explaining the absence.\n\n"
        "OUTPUT: write a markdown file with header + JSON code block + prose summary, e.g.:\n"
        "  # Playbook Context\n"
        "  ```json\n"
        "  {\"playbook_docs\": [...], \"clause_category_to_playbook\": {...},\n"
        "   \"context_quality\": \"founded\", \"notes\": \"...\"}\n"
        "  ```\n"
        "  ## Notes\n"
        "  <free-form 2-3 sentences for downstream humans + sub-agents>\n\n"
        "Do NOT include the contract content in playbook-context.md. Only references to playbook docs."
    ),
    ```

    Set `tools=["list_playbook_documents", "search_documents", "search_documents_by_doc_ids"]` on phases[3] (REVIEW #1: replaces the previous `["search_documents", "analyze_document"]` which referenced a nonexistent tool).

    **D) DO NOT** wire `output_schema` on CR-04 (LLM_AGENT does not enforce structured output; validation happens read-time at CR-06/07).

    **E) ANTI-REGRESSION:** verify the file does NOT contain the string `analyze_document` anywhere. If grep finds it (in a comment, an old prompt remnant, anything), DELETE that occurrence.
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pytest tests/harnesses/test_contract_review_cr03_cr04.py -v --tb=short && python -c "from app.harnesses.contract_review import PlaybookContext; print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "Which party are you" backend/app/harnesses/contract_review.py` returns `>= 1`
    - `grep -c "list_playbook_documents" backend/app/harnesses/contract_review.py` returns `>= 2` (prompt + tools list)
    - `grep -c "search_documents_by_doc_ids" backend/app/harnesses/contract_review.py` returns `>= 2` (prompt + tools list)
    - `grep -c "AUTHORITY HIERARCHY" backend/app/harnesses/contract_review.py` returns `1`
    - `grep -c "context_quality='unfounded'\|context_quality=\"unfounded\"" backend/app/harnesses/contract_review.py` returns `>= 1`
    - **`grep -c "analyze_document" backend/app/harnesses/contract_review.py` returns `0`** (REVIEW #1 anti-regression — tool does not exist)
    - `python -c "from app.harnesses.contract_review import PlaybookContext, PlaybookDoc; pc = PlaybookContext(); print('OK')"` prints `OK`
    - `python -c "from app.harnesses.contract_review import CONTRACT_REVIEW; p = CONTRACT_REVIEW.phases[3]; assert p.system_prompt_template != 'STUB'; assert p.tools == ['list_playbook_documents', 'search_documents', 'search_documents_by_doc_ids']; print('OK')"` prints `OK`
  </acceptance_criteria>
  <done>CR-03/CR-04 prompts populated; PlaybookContext schema; tools list updated to real tools (no analyze_document anywhere).</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: CR-03 + CR-04 tests (with REVIEW #1 anti-regression)</name>
  <files>backend/tests/harnesses/test_contract_review_cr03_cr04.py</files>
  <read_first>
    - backend/app/harnesses/contract_review.py (post-Task-1 state)
    - backend/tests/harnesses/test_contract_review_skeleton.py (analog from plan 22-06)
    - .planning/phases/22-contract-review-harness-docx-deliverable/22-REVIEWS.md (review finding #1)
  </read_first>
  <behavior>
    See behaviors 1-8 in Task 1.
  </behavior>
  <action>
    Create `backend/tests/harnesses/test_contract_review_cr03_cr04.py`. 8 tests with one-liner assertions on `CONTRACT_REVIEW.phases[2]` (CR-03) and `phases[3]` (CR-04).

    Concrete test 8 (REVIEW #1 anti-regression):
    ```python
    def test_no_analyze_document_references_anywhere():
        """REVIEW #1 hard guard: `analyze_document` does NOT exist as a tool in this codebase
        (verified `grep -c "analyze_document" backend/app/services/tool_service.py` returns 0).
        Plan 22-07 must not reference it. Future regressions caught here."""
        import pathlib
        text = pathlib.Path("backend/app/harnesses/contract_review.py").read_text()
        assert "analyze_document" not in text, (
            "REGRESSION: contract_review.py references the nonexistent `analyze_document` tool. "
            "Use `list_playbook_documents` (plan 22-02) and `search_documents_by_doc_ids` instead. "
            "See review finding #1 in 22-REVIEWS.md."
        )
    ```

    Concrete test 6:
    ```python
    def test_cr04_tools_list_uses_real_tools_only():
        from app.harnesses.contract_review import CONTRACT_REVIEW
        tools = CONTRACT_REVIEW.phases[3].tools
        assert tools == [
            "list_playbook_documents",
            "search_documents",
            "search_documents_by_doc_ids",
        ], f"REVIEW #1: CR-04 tools must use real tools only, got {tools}"
        assert "analyze_document" not in tools, "analyze_document does not exist in this codebase"
    ```
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pytest tests/harnesses/test_contract_review_cr03_cr04.py -v --tb=short</automated>
  </verify>
  <acceptance_criteria>
    - `pytest backend/tests/harnesses/test_contract_review_cr03_cr04.py -v` exits 0 with 8 tests passing
    - `grep -c "analyze_document" backend/tests/harnesses/test_contract_review_cr03_cr04.py` returns `>= 2` (assertion + comment in anti-regression test)
    - `grep -c "list_playbook_documents" backend/tests/harnesses/test_contract_review_cr03_cr04.py` returns `>= 1`
    - `grep -c "REVIEW #1" backend/tests/harnesses/test_contract_review_cr03_cr04.py` returns `>= 1`
  </acceptance_criteria>
  <done>8 tests pass — CR-03/04 prompts and schema locked in; REVIEW #1 anti-regression in place.</done>
</task>

</tasks>

<truths>
- D-22-05 (filter_tags=['playbook']) — embedded in CR-04 prompt for chunk-level RAG.
- D-22-06 (JSON-structured per-category mapping) — PlaybookContext schema + 13 categories listed.
- D-22-07 (empty-playbook fallback) — context_quality='unfounded' explicit.
- D-22-08 (authority hierarchy) — explicit ordering in prompt.
- D-22-09 (single combined HIL question) — CR-03 prompt structure.
- D-22-10 (raw text persistence) — engine writes user reply verbatim, no parse pass.
- D-22-11 (skip-tolerant) — prompt explicitly invites minimal answers.
- B4 single-registry (SEC-04): CR-04's sub-agent runs through sub_agent_loop.py which already wraps egress filter.
- PANEL-03: write_todos/read_todos already stripped via PANEL_LOCKED_EXCLUDED_TOOLS.
- REVIEW #1 closed: no `analyze_document` references — that tool does not exist. Use `list_playbook_documents` from plan 22-02.
- depends_on now includes 22-02 (was previously implicit; the new tool list requires it).
</truths>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| User HIL reply (CR-03) → review-context.md → CR-04..08 LLM payloads | User reply is raw text; routed through existing egress filter wrap |
| CR-04 sub-agent list_playbook_documents → user's documents table | RLS enforces user_id scoping |
| CR-04 sub-agent search_documents → playbook RAG | filter_tags='playbook' restricts retrieval scope |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-22-07-01 | Information Disclosure | User HIL reply containing PII reaching cloud LLM | mitigate | Existing SEC-04 egress filter wrap on every CR-04..08 LLM call |
| T-22-07-02 | Tampering | Sub-agent omitting one of 13 clause categories | mitigate | Plan 22-09 (CR-06) read-time validation will assert all 13 keys present |
| T-22-07-03 | DoS | CR-04 sub-agent runs >10 rounds | mitigate | LLM_AGENT timeout enforced + MAX_SUB_AGENT_ROUNDS env cap |
| T-22-07-04 | Tampering | LLM hallucinates a doc_id not from list_playbook_documents | accept | search_documents_by_doc_ids returns no results for nonexistent IDs; bounded cost |
</threat_model>

<verification>
1. `pytest backend/tests/harnesses/test_contract_review_cr03_cr04.py -v` exits 0
2. `pytest backend/tests/harnesses/test_contract_review_skeleton.py -v` exits 0 (regression)
3. `python -c "from app.main import app; print('OK')"` prints `OK`
4. `grep -c "analyze_document" backend/app/harnesses/contract_review.py` returns `0` (REVIEW #1 anti-regression)
</verification>

<success_criteria>
- CR-03 single combined HIL question prompt populated
- CR-04 LLM_AGENT prompt populated with all 13 categories + filter_tags + authority hierarchy + empty fallback
- CR-04 tools list uses real tools (`list_playbook_documents`, `search_documents`, `search_documents_by_doc_ids`)
- NO references to nonexistent `analyze_document` tool anywhere
- PlaybookContext schema available for plan 22-09 read-time validation
</success_criteria>

<output>
After completion, create `.planning/phases/22-contract-review-harness-docx-deliverable/22-07-SUMMARY.md`.
</output>
