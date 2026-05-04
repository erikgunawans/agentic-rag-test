---
phase: 22-contract-review-harness-docx-deliverable
plan: 07
type: execute
wave: 3
depends_on: ["22-06"]
files_modified:
  - backend/app/harnesses/contract_review.py
  - backend/tests/harnesses/test_contract_review_cr03_cr04.py
autonomous: true
requirements: [CR-03, CR-04]
must_haves:
  truths:
    - "CR-03 (gather-context) generates ONE combined free-form question via llm_human_input — single HIL pause (D-22-09)"
    - "CR-03 persists user reply VERBATIM to review-context.md — no parser, no extraction (D-22-10, D-22-11)"
    - "CR-04 (load-playbook) is an LLM_AGENT phase, max 10 rounds, with phase_tools=['search_documents', 'analyze_document'] curated"
    - "CR-04 sub-agent prompt embeds filter_tags=['playbook'] guidance (D-22-05) and emits playbook-context.md per the D-22-06 JSON shape"
    - "CR-04 sets context_quality='unfounded' in playbook-context.md JSON when zero playbook docs found (D-22-07 empty-playbook fallback)"
    - "CR-04 prompt orders authority hierarchy: user-workspace > regulatory_intel > 3rd-party (D-22-08)"
    - "Tool curation propagates: sub-agent only sees the listed tools (PANEL_LOCKED_EXCLUDED_TOOLS already strips write_todos/read_todos)"
  artifacts:
    - path: "backend/app/harnesses/contract_review.py"
      provides: "CR-03 + CR-04 phase prompts populated; PlaybookContext Pydantic schema added"
      contains: "playbook-context.md"
    - path: "backend/tests/harnesses/test_contract_review_cr03_cr04.py"
      provides: "Tests for CR-03 prompt shape, CR-04 tools curation, JSON output schema"
  key_links:
    - from: "CR-03 system_prompt_template"
      to: "review-context.md"
      via: "engine LLM_HUMAN_INPUT writes user reply verbatim (Phase 21 dispatcher)"
      pattern: "review-context\\.md"
    - from: "CR-04 sub-agent search_documents calls"
      to: "playbook-tagged documents"
      via: "filter_tags=['playbook']"
      pattern: "filter_tags.*playbook"
---

<objective>
Replace the CR-03 (gather-context) and CR-04 (load-playbook) stubs in `backend/app/harnesses/contract_review.py` with real prompts. CR-03 leverages the Phase 21 LLM_HUMAN_INPUT dispatcher (already wired) — only the prompt and Pydantic stub change. CR-04 is an LLM_AGENT phase exercising the Phase 19/20 sub-agent loop with curated RAG tools.

Purpose: After CR-02 classifies the contract, we need to know the user's perspective (which side, deadline, focus) AND the playbook docs to grade against. Both feed CR-06/07 batch scorers downstream.
Output: Two phase prompts populated, schema for playbook output, tests.
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
@backend/app/harnesses/smoke_echo.py
</context>

<interfaces>
<!-- Plan 22-06 already defined the 8-phase HarnessDefinition with stubs. -->
<!-- This plan replaces phases[2] (CR-03) and phases[3] (CR-04) prompts. -->

CR-04 D-22-06 output JSON shape (plan 22-09 reads this back):
```python
class PlaybookContext(BaseModel):
    playbook_docs: list[PlaybookDoc] = Field(default_factory=list)
    clause_category_to_playbook: dict[str, list[str]] = Field(default_factory=dict)
    context_quality: str = Field(default="founded", description="'founded' or 'unfounded' (D-22-07)")
    notes: str = Field(default="", description="Free-form summary for human readers")
```

The 13 clause categories (CR-05 spec — keep names verbatim):
`["Liability", "Indemnification", "IP", "Data Protection", "Confidentiality", "Warranties", "Term/Termination", "Governing Law", "Insurance", "Assignment", "Force Majeure", "Payment", "Other"]`
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Populate CR-03 prompt and CR-04 prompt + add PlaybookContext schema</name>
  <files>backend/app/harnesses/contract_review.py</files>
  <read_first>
    - backend/app/harnesses/contract_review.py (post-Plan-22-06 state — find the stub system_prompt_template="STUB" entries for "gather-context" and "load-playbook")
    - backend/app/harnesses/smoke_echo.py (lines 159-172 — LLM_HUMAN_INPUT prompt analog for "ask-label" phase)
    - .planning/phases/22-contract-review-harness-docx-deliverable/22-CONTEXT.md (D-22-05..09 — locked decisions)
    - .planning/phases/22-contract-review-harness-docx-deliverable/22-PATTERNS.md (lines 540-557 — phase_tools curation pattern)
  </read_first>
  <behavior>
    - Test 1: `CONTRACT_REVIEW.phases[2].system_prompt_template` (gather-context) is non-empty, contains the literal substring `"Which party are you"` and instructs ONE combined question (D-22-09).
    - Test 2: gather-context prompt does NOT mention parsing the response — engine writes raw text to review-context.md (D-22-10).
    - Test 3: `CONTRACT_REVIEW.phases[3].system_prompt_template` (load-playbook) contains `"filter_tags=['playbook']"`, instructs max 10 rounds, mentions all 13 clause categories.
    - Test 4: load-playbook prompt instructs the sub-agent to set `"context_quality": "unfounded"` when no playbook docs found (D-22-07).
    - Test 5: load-playbook prompt instructs authority ordering "user-workspace uploads first, regulatory_intel second, general document library third" (D-22-08).
    - Test 6: `CONTRACT_REVIEW.phases[3].tools == ["search_documents", "analyze_document"]` (curated tool set).
    - Test 7: `PlaybookContext` schema imports cleanly and accepts the empty-playbook case `PlaybookContext(playbook_docs=[], clause_category_to_playbook={}, context_quality="unfounded")`.
  </behavior>
  <action>
    Edit `backend/app/harnesses/contract_review.py` (post-Plan-22-06 state).

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
        id: str = Field(..., min_length=1, description="Document UUID from search_documents results")
        title: str = Field(..., min_length=1, max_length=300)
        summary: str = Field(..., min_length=1, max_length=300, description="<=200 char summary")
        source_priority: int = Field(default=2, ge=1, le=3,
            description="D-22-08 authority order: 1=user-workspace, 2=regulatory_intel, 3=3rd-party")


    class PlaybookContext(BaseModel):
        """CR-04 structured output written to playbook-context.md (D-22-06)."""
        playbook_docs: list[PlaybookDoc] = Field(default_factory=list)
        clause_category_to_playbook: dict[str, list[str]] = Field(default_factory=dict,
            description="Map of {category: [doc_id, ...]} for each of the 13 categories")
        context_quality: str = Field(default="founded",
            description="'founded' (>=1 doc) or 'unfounded' (no playbook docs found, D-22-07)")
        notes: str = Field(default="", max_length=2000,
            description="Free-form prose summary for downstream humans + sub-agents")
    ```

    **B) Replace CR-03 (`gather-context`) PhaseDefinition's `system_prompt_template`** with this exact text (D-22-09 single combined question, D-22-10 raw persistence):
    ```python
    system_prompt_template=(
        "You are gathering review context for a Contract Review run. The user just uploaded "
        "a contract and we have already classified it (see workspace input classification.md).\n\n"
        "Generate ONE combined free-form question (single paragraph, plain language) asking "
        "the user about all four topics in one breath:\n"
        "  1. Which party are you in this contract? (e.g. 'we are the buyer/customer/licensee')\n"
        "  2. Is there a deadline or pressure on this review? (e.g. 'sign by Friday')\n"
        "  3. Which clauses or risks should we focus on? (e.g. 'IP, indemnity, data protection')\n"
        "  4. What's the broader deal context? (e.g. 'this is part of an M&A integration')\n\n"
        "Be conversational and concise (under 80 words total). Acknowledge the user can answer "
        "any subset — minimal answers like 'just go' or '...' are fully valid. Respond as a JSON "
        "object {\"question\": \"<the single combined paragraph>\"}.\n"
    ),
    ```

    **C) Replace CR-04 (`load-playbook`) PhaseDefinition's `system_prompt_template`** with this exact text (D-22-05..08 stack):
    ```python
    system_prompt_template=(
        "You are the playbook loader for a Contract Review run. Your job: discover playbook "
        "materials in the knowledge base and produce a structured JSON map from clause categories "
        "to relevant playbook document IDs.\n\n"
        "INPUTS (workspace files):\n"
        "  - classification.md : the contract type, parties, governing law, jurisdiction\n"
        "  - review-context.md : the user's stated perspective, deadline, focus areas\n\n"
        "TOOLS:\n"
        "  - search_documents(query, filter_tags=['playbook'], top_k=8) — D-22-05: ALWAYS pass\n"
        "    filter_tags=['playbook'] so you only see playbook materials, not the user's contract.\n"
        "  - analyze_document(doc_id, question) — read a single playbook doc to confirm relevance.\n\n"
        "PROCEDURE (max 10 rounds):\n"
        "  1. For each of the 13 clause categories below, search the playbook with the contract\n"
        "     classification + clause category as the query. Skim summaries; pick docs that look\n"
        "     authoritative for that category.\n"
        "  2. AUTHORITY HIERARCHY (D-22-08): when multiple docs match, weight in this order —\n"
        "     (a) user-workspace uploads first, (b) regulatory_intel docs second,\n"
        "     (c) general document library third. Use source_priority=1, 2, or 3 accordingly.\n"
        "  3. Build a clause_category_to_playbook dict. EVERY category must have a list (use\n"
        "     [] if no doc covers that category). All 13 categories must appear as keys.\n\n"
        "CLAUSE CATEGORIES (use exactly these strings as JSON keys):\n"
        "  Liability, Indemnification, IP, Data Protection, Confidentiality, Warranties,\n"
        "  Term/Termination, Governing Law, Insurance, Assignment, Force Majeure, Payment, Other\n\n"
        "EMPTY PLAYBOOK FALLBACK (D-22-07): if your search returns ZERO playbook documents\n"
        "across all categories, set context_quality='unfounded' and emit empty playbook_docs []\n"
        "+ all 13 categories mapping to []. Add a notes field explaining the absence.\n\n"
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

    Keep `tools=["search_documents", "analyze_document"]` from Plan 22-06 unchanged. Do NOT add `search_documents_by_doc_ids` here — CR-04 uses the broad `filter_tags` form; the doc-id-restricted variant is for CR-06/07 (plan 22-09).

    **D) Set CR-08's output_schema=None for now** (Plan 22-10 sets ExecutiveSummary). Do NOT touch.

    **E) DO NOT** wire `output_schema` on CR-04. The engine's LLM_AGENT dispatcher does NOT enforce structured output (only LLM_SINGLE does — HARN-05). Validation of CR-04's output happens at CR-06's READ time when sub-agents parse playbook-context.md. Mention this in a comment above CR-04's PhaseDefinition: `# CR-04 is LLM_AGENT (multi-round); structured-output enforcement is read-time at CR-06/07 not write-time here.`
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pytest tests/harnesses/test_contract_review_cr03_cr04.py -v --tb=short && python -c "from app.harnesses.contract_review import PlaybookContext; print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "Which party are you" backend/app/harnesses/contract_review.py` returns `>= 1`
    - `grep -c "filter_tags=\['playbook'\]" backend/app/harnesses/contract_review.py` returns `>= 1`
    - `grep -c "AUTHORITY HIERARCHY" backend/app/harnesses/contract_review.py` returns `1`
    - `grep -c "context_quality='unfounded'\|context_quality=\"unfounded\"" backend/app/harnesses/contract_review.py` returns `>= 1`
    - `grep -c "CLAUSE_CATEGORIES" backend/app/harnesses/contract_review.py` returns `>= 1`
    - `python -c "from app.harnesses.contract_review import PlaybookContext, PlaybookDoc; pc = PlaybookContext(); print('OK')"` prints `OK`
    - `python -c "from app.harnesses.contract_review import CONTRACT_REVIEW; p = CONTRACT_REVIEW.phases[2]; assert p.system_prompt_template != 'STUB'; print('OK')"` prints `OK`
    - `python -c "from app.harnesses.contract_review import CONTRACT_REVIEW; p = CONTRACT_REVIEW.phases[3]; assert p.system_prompt_template != 'STUB'; assert p.tools == ['search_documents', 'analyze_document']; print('OK')"` prints `OK`
  </acceptance_criteria>
  <done>CR-03 prompt + CR-04 prompt populated; PlaybookContext schema added; flag-gated registration unchanged.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Add CR-03 + CR-04 tests</name>
  <files>backend/tests/harnesses/test_contract_review_cr03_cr04.py</files>
  <read_first>
    - backend/app/harnesses/contract_review.py (post-Task-1 state)
    - backend/tests/harnesses/test_contract_review_skeleton.py (analog from plan 22-06)
  </read_first>
  <behavior>
    See behaviors 1-7 in Task 1.
  </behavior>
  <action>
    Create `backend/tests/harnesses/test_contract_review_cr03_cr04.py`. 7 tests with one-liner assertions on `CONTRACT_REVIEW.phases[2]` (CR-03) and `phases[3]` (CR-04). No async needed — these are pure shape tests.

    Concrete test 5 (D-22-08 authority hierarchy):
    ```python
    def test_cr04_prompt_orders_authority_user_workspace_first():
        from app.harnesses.contract_review import CONTRACT_REVIEW
        prompt = CONTRACT_REVIEW.phases[3].system_prompt_template
        # Authority hierarchy: user-workspace must appear BEFORE regulatory_intel which must appear BEFORE 3rd-party
        assert prompt.index("user-workspace") < prompt.index("regulatory_intel")
        assert prompt.index("regulatory_intel") < prompt.index("3rd-party")
    ```

    Concrete test 7 (PlaybookContext empty case):
    ```python
    def test_playbook_context_accepts_empty_unfounded():
        from app.harnesses.contract_review import PlaybookContext
        pc = PlaybookContext(
            playbook_docs=[],
            clause_category_to_playbook={},
            context_quality="unfounded",
        )
        assert pc.context_quality == "unfounded"
        assert pc.playbook_docs == []
    ```
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pytest tests/harnesses/test_contract_review_cr03_cr04.py -v --tb=short</automated>
  </verify>
  <acceptance_criteria>
    - `pytest backend/tests/harnesses/test_contract_review_cr03_cr04.py -v` exits 0 with 7 tests passing
    - `grep -c "user-workspace.*regulatory_intel\|playbook" backend/tests/harnesses/test_contract_review_cr03_cr04.py` returns `>= 1`
  </acceptance_criteria>
  <done>7 tests pass — CR-03/04 prompts and schema locked in.</done>
</task>

</tasks>

<truths>
- D-22-05 (filter_tags=['playbook'] auto-add) — embedded in CR-04 prompt instruction.
- D-22-06 (JSON-structured per-category mapping) — PlaybookContext schema + 13 clause categories listed in prompt.
- D-22-07 (empty-playbook fallback) — context_quality='unfounded' explicit branch in prompt.
- D-22-08 (authority hierarchy) — explicit ordering in prompt.
- D-22-09 (single combined HIL question) — CR-03 prompt structure.
- D-22-10 (raw text persistence) — engine writes user reply verbatim, no LLM-parse pass.
- D-22-11 (skip-tolerant) — prompt explicitly invites minimal answers.
- B4 single-registry (SEC-04): CR-04's sub-agent runs through `sub_agent_loop.py` which already wraps egress filter. No new LLM call site introduced.
- PANEL-03: write_todos/read_todos already stripped from harness phases by engine via PANEL_LOCKED_EXCLUDED_TOOLS.
</truths>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| User HIL reply (CR-03) → review-context.md → CR-04..08 LLM payloads | User reply is raw user text; might contain PII; routed through existing egress filter wrap |
| CR-04 sub-agent search_documents → playbook RAG | filter_tags='playbook' restricts retrieval scope; results are document summaries (not full PII content) |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-22-07-01 | Information Disclosure | User HIL reply containing PII reaching cloud LLM | mitigate | Existing SEC-04 egress filter wrap on every CR-04..08 LLM call (B4 single-registry); review-context.md content filtered at egress boundary |
| T-22-07-02 | Tampering | Sub-agent omitting one of 13 clause categories | mitigate | Plan 22-09 (CR-06) read-time validation will assert all 13 keys present in clause_category_to_playbook; CR-04 prompt enforces this |
| T-22-07-03 | DoS | CR-04 sub-agent runs >10 rounds | mitigate | LLM_AGENT timeout already enforced (600s in plan 22-06); MAX_SUB_AGENT_ROUNDS env cap (CONF-03) |
</threat_model>

<verification>
1. `pytest backend/tests/harnesses/test_contract_review_cr03_cr04.py -v` exits 0
2. `pytest backend/tests/harnesses/test_contract_review_skeleton.py -v` exits 0 (regression — plan 22-06 tests unchanged)
3. `python -c "from app.main import app; print('OK')"` prints `OK`
</verification>

<success_criteria>
- CR-03 single combined HIL question prompt populated
- CR-04 LLM_AGENT prompt populated with all 13 categories + filter_tags + authority hierarchy + empty fallback
- PlaybookContext schema available for plan 22-09 read-time validation
- Tool curation list verified
</success_criteria>

<output>
After completion, create `.planning/phases/22-contract-review-harness-docx-deliverable/22-07-SUMMARY.md`.
</output>
