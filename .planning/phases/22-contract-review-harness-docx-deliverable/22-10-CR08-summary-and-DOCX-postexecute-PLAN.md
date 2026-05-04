---
phase: 22-contract-review-harness-docx-deliverable
plan: 10
type: execute
wave: 6
depends_on: ["22-01", "22-03", "22-09"]
files_modified:
  - backend/app/harnesses/contract_review.py
  - backend/app/harnesses/contract_review_docx.py
  - backend/tests/harnesses/test_contract_review_docx.py
autonomous: true
requirements: [CR-08, DOCX-01, DOCX-02, DOCX-03, DOCX-04, DOCX-05, DOCX-06, DOCX-07, DOCX-08]
must_haves:
  truths:
    - "CR-08 (executive-summary) is LLM_SINGLE; output_schema=ExecutiveSummary; writes contract-review-report.md"
    - "post_execute=_generate_docx_post_execute callable wired on CR-08 phase (phases[8] in the 9-phase HarnessDefinition)"
    - "_generate_docx_post_execute reads all 6 artifact files, builds python-docx script, runs in sandbox via SandboxService.execute(), writes DOCX to workspace_files with source='harness'"
    - "DOCX includes: title page (CONFIDENTIAL + risk badge), exec summary, key findings, color-coded redline table, GREEN section, recommended next steps"
    - "Pastel risk colors per D-22-13: GREEN=#E6F4EA, YELLOW=#FEF7E0, RED=#FCE8E6"
    - "Filename pattern: contract-review-{harness_run_id[:8]}.docx (D-22-14)"
    - "D-22-15 non-fatal fallback: post_execute returns error dict on sandbox failure; harness_runs.status stays 'completed'"
    - "post_execute does NOT make LLM calls — DOCX is purely deterministic python-docx serialization"
    - "Audit log: contract_review_docx_generated on success, contract_review_docx_failed on fallback"
    - "Sandbox API PINNED: SandboxService.execute(*, code, thread_id, user_id, token) returning dict with exit_code/files; NO files= kwarg, NO timeout_seconds= kwarg, NO ok field"
    - "DOCX bytes retrieved by HTTP GET on sb_result['files'][0]['signed_url'] (auto-collected /sandbox/output/contract-review.docx) — no base64 stdout exfiltration"
  artifacts:
    - path: "backend/app/harnesses/contract_review.py"
      provides: "ExecutiveSummary schema + CR-08 prompt populated + post_execute wired on phases[8]"
      contains: "_generate_docx_post_execute"
    - path: "backend/app/harnesses/contract_review_docx.py"
      provides: "_generate_docx_post_execute callable + DOCX_GENERATION_SCRIPT_BODY string constant"
      contains: "DOCX_GENERATION_SCRIPT_BODY"
    - path: "backend/tests/harnesses/test_contract_review_docx.py"
      provides: "Tests for ExecutiveSummary, post_execute success/fail, sandbox script structure, fallback contract"
  key_links:
    - from: "CR-08 phase (phases[8])"
      to: "_generate_docx_post_execute callable"
      via: "PhaseDefinition.post_execute field (Plan 22-03 invocation site)"
      pattern: "post_execute=_generate_docx_post_execute"
    - from: "_generate_docx_post_execute"
      to: "WorkspaceService.write_binary_file(thread_id, 'contract-review-{run_id_short}.docx', bytes, source='harness')"
      via: "SandboxService.execute() with DOCX_GENERATION_SCRIPT_BODY + INPUT_DATA literal prefix"
      pattern: "write_binary_file"
---

<objective>
Replace the CR-08 stub with the real LLM_SINGLE prompt + ExecutiveSummary Pydantic schema, AND wire the `_generate_docx_post_execute` callable that runs python-docx generation in the sandbox and writes the result to workspace_files.

Per ROADMAP success criterion 5: writes `contract-review-report.md` AND generates a CONFIDENTIAL-marked .docx with all 7 sections (DOCX-02..07). D-22-15 ensures non-fatal fallback.
Output: CR-08 prompt + schema, post_execute callable in a separate module, DOCX-generation script as a string constant for sandbox dispatch (per PATTERNS.md L28 recommendation).

CR-08 lives at `phases[8]` in the 9-phase HarnessDefinition (Plan 22-06's filter-redline-candidates phase at index 6 shifts CR-07 to index 7 and CR-08 to index 8).
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
<!-- ISSUE-05 PIN (CANONICAL): sandbox_service.SandboxService.execute() actual signature (sandbox_service.py:228-258) -->
<!-- -->
<!--   @traced(name="sandbox_execute") -->
<!--   async def execute(self, *, code: str, thread_id: str, user_id: str, -->
<!--                     token: str | None = None, -->
<!--                     stream_callback: Callable[[str, str], Awaitable[None]] | None = None, -->
<!--                     workspace_callback: Callable[[dict], None] | None = None) -> dict: -->
<!--   Returns: { -->
<!--     "stdout": str, "stderr": str, "exit_code": int, -->
<!--     "error_type": str | None,  # None | "timeout" | "exception" | "security_violation" -->
<!--     "execution_ms": int, -->
<!--     "files": list[dict],  # [{filename, size_bytes, signed_url, storage_path}] -->
<!--     "execution_id": str, -->
<!--   } -->
<!-- -->
<!-- KEY FACTS: -->
<!--   1. Method name is `execute`, NOT `execute_code`, NOT `run_code`, NOT `submit`. -->
<!--   2. NO `files=` kwarg. NO `timeout_seconds=` kwarg (timeout is enforced by service config). -->
<!--   3. The only way to pass input data: INLINE in the `code` string as a Python literal. -->
<!--   4. Result has `exit_code` (int) — success = exit_code == 0. NO `ok` field. -->
<!--   5. Files written to /sandbox/output/ are auto-collected and uploaded; signed URLs returned -->
<!--      in result["files"]. We use this auto-collect path: write to /sandbox/output/contract-review.docx, -->
<!--      then HTTP GET the bytes from result["files"][0]["signed_url"]. -->
<!--      NO base64 stdout exfiltration is used. -->
<!--   6. Singleton accessor: `from app.services.sandbox_service import get_sandbox_service` -->
<!-- -->
<!-- Therefore plan 22-10's call site is: -->
<!-- -->
<!--   sb = get_sandbox_service() -->
<!--   sb_result = await sb.execute( -->
<!--       code=code_with_inputs, -->
<!--       thread_id=thread_id, -->
<!--       user_id=user_id, -->
<!--       token=token, -->
<!--   ) -->
<!--   if sb_result.get("exit_code") != 0: -->
<!--       raise DocxGenerationError(f"sandbox exit_code={sb_result.get('exit_code')}: {(sb_result.get('stderr') or '')[:500]}") -->
<!-- -->
<!-- Inputs marshaling: prefix the script with a Python literal -->
<!--   inputs_literal = f"INPUT_DATA = {json.dumps(sandbox_inputs, ensure_ascii=False)}\n" -->
<!--   code_with_inputs = inputs_literal + DOCX_GENERATION_SCRIPT_BODY -->
<!-- where DOCX_GENERATION_SCRIPT_BODY references INPUT_DATA directly (no file reads). -->

<!-- ExecutiveSummary schema for CR-08 -->

```python
class ExecutiveSummary(BaseModel):
    overall_risk: RiskGrade = Field(..., description="Aggregated worst grade across all clauses")
    recommendation: str = Field(..., min_length=20, max_length=2000,
        description="One-paragraph: sign / sign-with-redlines / do-not-sign + key reason")
    key_findings: list[str] = Field(..., min_length=1, max_length=10,
        description="3-7 bullets summarizing the most important issues")
    risk_breakdown: dict[str, int] = Field(...,
        description="{'GREEN': N, 'YELLOW': M, 'RED': K} counts")
    next_steps: list[str] = Field(..., min_length=1, max_length=10,
        description="Recommended actions: 'request redline N', 'escalate to senior counsel', etc.")
```

<!-- _generate_docx_post_execute signature (matches plan 22-03 contract) -->
```python
async def _generate_docx_post_execute(
    *,
    harness_run_id: str,
    thread_id: str,
    user_id: str,
    user_email: str,
    token: str,
    phase_results: dict,
    workspace,
) -> dict:
    # Returns:
    #   {"ok": True, "docx_path": "<path>", "signed_url": "<url>"}    on success
    #   {"error": "...", "code": "...", "detail": "...",              on failure (D-22-15)
    #    "fallback_message": "..."}
    # NEVER raises.
```
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Populate CR-08 prompt + add ExecutiveSummary schema</name>
  <files>backend/app/harnesses/contract_review.py</files>
  <read_first>
    - backend/app/harnesses/contract_review.py (post-Plan-22-09 state — CR-08 stub at phases[8] in the 9-phase definition; CR-07 at phases[7]; filter at phases[6])
    - backend/app/harnesses/smoke_echo.py (lines 140-156 — LLM_SINGLE analog with output_schema)
    - .planning/phases/22-contract-review-harness-docx-deliverable/22-CONTEXT.md (D-22-12..15)
  </read_first>
  <behavior>
    - Test 1: ExecutiveSummary schema accepts a fully-populated valid instance.
    - Test 2: ExecutiveSummary rejects empty key_findings list (`min_length=1`).
    - Test 3: ExecutiveSummary rejects empty next_steps list.
    - Test 4: CR-08 phase (phases[8]) has `output_schema=ExecutiveSummary`.
    - Test 5: CR-08 phase prompt mentions reading classification.md + review-context.md + playbook-context.md + clauses.md + risk-analysis.json + redlines.json (all 6 input files).
    - Test 6: CR-08 phase has `post_execute=_docx_post_execute_shim` (set after plan 22-10 Task 2 lands; plan 22-10 Task 1 sets it to the imported callable).
  </behavior>
  <action>
    Edit `backend/app/harnesses/contract_review.py`:

    **A) Add ExecutiveSummary schema** below ClauseRisk + Redline:
    ```python
    # ---------------------------------------------------------------------------
    # CR-08 — Executive Summary schema
    # ---------------------------------------------------------------------------

    class ExecutiveSummary(BaseModel):
        overall_risk: RiskGrade = Field(..., description="Worst-case aggregate grade across clauses")
        recommendation: str = Field(..., min_length=20, max_length=2000,
            description="One paragraph: sign-as-is / sign-with-redlines / do-not-sign + key reason")
        key_findings: list[str] = Field(..., min_length=1, max_length=10,
            description="3-7 bullets summarizing most important issues")
        risk_breakdown: dict[str, int] = Field(...,
            description="{'GREEN': N, 'YELLOW': M, 'RED': K} clause counts")
        next_steps: list[str] = Field(..., min_length=1, max_length=10,
            description="Recommended actions for the user/legal team")
    ```

    **B) Replace CR-08 (`executive-summary`) `system_prompt_template`** with this exact text:
    ```python
    system_prompt_template=(
        "You are writing the executive summary for a Contract Review run.\n\n"
        "INPUTS (workspace files):\n"
        "  - classification.md: contract type, parties, dates, governing law, jurisdiction\n"
        "  - review-context.md: user's perspective, deadline, focus areas (raw user text)\n"
        "  - playbook-context.md: playbook docs + clause_category_to_playbook map + context_quality\n"
        "  - clauses.md: full extracted clauses array\n"
        "  - risk-analysis.json: ClauseRisk array (every clause graded GREEN/YELLOW/RED + rationale)\n"
        "  - redlines.json: Redline array (proposed replacements for YELLOW/RED clauses only)\n\n"
        "OUTPUT: a JSON object matching ExecutiveSummary schema:\n"
        "  - overall_risk: aggregate worst grade (any RED -> RED, else any YELLOW -> YELLOW, else GREEN)\n"
        "  - recommendation: one paragraph closing recommendation: sign / sign-with-redlines / do-not-sign\n"
        "  - key_findings: 3-7 bullets covering the most important issues across the contract\n"
        "  - risk_breakdown: counts {GREEN, YELLOW, RED} from risk-analysis.json\n"
        "  - next_steps: recommended actions (e.g. 'request redlines 3, 7, 12', 'escalate to senior counsel')\n\n"
        "If playbook-context.md.context_quality == 'unfounded', BEGIN your recommendation with:\n"
        "  'No playbook materials found — risk grades reflect generic legal standards.' (D-22-07)\n\n"
        "Return ONLY the JSON object — no prose."
    ),
    ```

    Set `phases[8].output_schema = ExecutiveSummary` (replace `output_schema=None` from plan 22-06 stub at phases[8]).

    **C) Wire post_execute** — add at top of file (right after the imports), to break a potential import cycle:
    ```python
    # Lazy-import (CR-21-01 circular guard): the DOCX module imports back into
    # this module for schemas; wrap the post_execute reference in a small shim.
    async def _docx_post_execute_shim(**kwargs):
        from app.harnesses.contract_review_docx import _generate_docx_post_execute
        return await _generate_docx_post_execute(**kwargs)
    ```

    Then in CR-08's PhaseDefinition (phases[8]): `post_execute=_docx_post_execute_shim`.

    Add inline comment: `# CR-08 (phases[8]) wires post_execute via shim to break circular import (CR-21-01 lesson).`
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pytest tests/harnesses/test_contract_review_docx.py::test_cr08_phase_has_post_execute_and_schema -v --tb=short || true && python -c "from app.harnesses.contract_review import ExecutiveSummary, CONTRACT_REVIEW; print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `python -c "from app.harnesses.contract_review import ExecutiveSummary; e = ExecutiveSummary(overall_risk='YELLOW', recommendation='Sign with the proposed redlines applied because two YELLOW clauses warrant negotiation.', key_findings=['IP assignment too broad', 'Liability cap too low'], risk_breakdown={'GREEN':5,'YELLOW':2,'RED':0}, next_steps=['Apply redlines 1-2']); print(e.overall_risk)"` prints `RiskGrade.YELLOW`
    - `grep -c "ExecutiveSummary" backend/app/harnesses/contract_review.py` returns `>= 3`
    - `grep -c "_docx_post_execute_shim\|_generate_docx_post_execute" backend/app/harnesses/contract_review.py` returns `>= 2`
    - `python -c "from app.harnesses.contract_review import CONTRACT_REVIEW; assert CONTRACT_REVIEW.phases[8].name == 'executive-summary'; assert CONTRACT_REVIEW.phases[8].output_schema.__name__ == 'ExecutiveSummary'; assert CONTRACT_REVIEW.phases[8].post_execute is not None; print('OK')"` prints `OK`
  </acceptance_criteria>
  <done>CR-08 prompt populated, ExecutiveSummary schema added, post_execute wired via shim on phases[8].</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Implement _generate_docx_post_execute in contract_review_docx.py</name>
  <files>backend/app/harnesses/contract_review_docx.py</files>
  <read_first>
    - backend/app/services/sandbox_service.py (lines 228-258 — `SandboxService.execute(*, code, thread_id, user_id, token)` PINNED signature; NO files= kwarg; returns {exit_code, stdout, stderr, files, ...})
    - backend/app/services/workspace_service.py (lines 511-660 — write_binary_file signature + storage path conventions)
    - .planning/phases/22-contract-review-harness-docx-deliverable/22-PATTERNS.md (lines 261-329 — sandbox invocation + non-fatal fallback shape; lines 100-110 — D-22-13 pastel colors + DOCX section list)
    - backend/app/harnesses/contract_review.py (post-Task-1 — for ClauseRisk, Redline, ExecutiveSummary, RiskGrade imports)
    - backend/app/services/audit_service.py (find log_action signature; PATTERNS.md L519-526)
  </read_first>
  <behavior>
    - Test 1: post_execute reads all 6 artifact files via workspace.read_file.
    - Test 2: On sandbox success (exit_code=0, files=[{signed_url, ...}]), HTTP-GETs the signed URL, then calls workspace.write_binary_file with `file_path` matching `f"contract-review-{harness_run_id[:8]}.docx"`, `source="harness"`.
    - Test 3: Returns `{"ok": True, "docx_path": "<the path>", "signed_url": "<...>"}` on success.
    - Test 4: On sandbox non-zero exit_code, returns `{"error": "docx_generation_failed", "code": "DOCX_FAILED", "detail": "...", "fallback_message": "..."}` and does NOT raise.
    - Test 5: Audit log fires `contract_review_docx_generated` on success, `contract_review_docx_failed` on fallback.
    - Test 6: DOCX_GENERATION_SCRIPT_BODY string contains `from docx import Document`, `add_heading`, `add_table`, the three pastel hex codes (`E6F4EA`, `FEF7E0`, `FCE8E6`), and the literal `CONFIDENTIAL` marker (per D-22-13).
    - Test 7: post_execute does NOT make LLM calls (assert no OpenRouterService import or call in this module).
    - Test 8 (ISSUE-11): `_extract_json_from_markdown` parses a JSONL stream (3 newline-separated JSON objects) into a list of 3 dicts. Also parses a single ```json``` code block correctly. Also parses a raw JSON array correctly.
    - Test 9: Sandbox call uses `SandboxService.execute(*, code, thread_id, user_id, token)` — NOT `execute_code(...files=...)`. Module text MUST contain `.execute(` and MUST NOT contain `.execute_code(` or `files=` kwarg or `timeout_seconds=` kwarg.
    - Test 10: Module text MUST contain `exit_code` (success check) and MUST NOT contain `DOCX_B64_BEGIN` (no base64 stdout exfiltration).
    - Test 11 (integration-gated, ISSUE-05): real-sandbox happy-path test marked `@pytest.mark.integration` and gated behind `os.getenv("RUN_SANDBOX_INTEGRATION_TESTS")`. Skipped by default in CI.
    - Tests 12-14: misc edge cases (empty workspace files, missing signed_url, httpx timeout) — all map to the D-22-15 fallback path.
  </behavior>
  <action>
    Create `backend/app/harnesses/contract_review_docx.py`. Per PATTERNS.md L28 recommendation, embed the python-docx generation logic as a STRING CONSTANT (`DOCX_GENERATION_SCRIPT_BODY`) sent to the sandbox at runtime (faster iteration than rebuilding the sandbox image).

    The PINNED API is `SandboxService.execute(*, code, thread_id, user_id, token)` (NO `files=` kwarg, NO `timeout_seconds=` kwarg, NO `ok` field in result). Inputs MUST be inlined as a Python literal at the top of the script string. DOCX bytes are retrieved via HTTP GET on the signed URL returned in `sb_result["files"]` — NO base64 stdout exfiltration.

    Module structure:
    ```python
    """Phase 22 / DOCX-01..08 — Sandbox-driven .docx generation post_execute callback.

    Called by harness_engine after CR-08 (executive-summary) completes. Reads all
    6 artifact files, builds a python-docx script, runs it in the sandbox via
    SandboxService.execute(), retrieves the auto-collected DOCX from
    sb_result["files"][0]["signed_url"], and writes it into workspace_files
    with source='harness'.

    D-22-12: pure programmatic generation, no template file.
    D-22-13: pastel risk colors GREEN=#E6F4EA YELLOW=#FEF7E0 RED=#FCE8E6.
    D-22-14: filename = contract-review-{harness_run_id[:8]}.docx, source='harness'.
    D-22-15: NEVER raise — error dict + fallback_message on any failure.

    ISSUE-05 PIN: SandboxService.execute() — NO files= kwarg, NO timeout_seconds= kwarg.
    Inputs inlined as INPUT_DATA Python literal prepended to DOCX_GENERATION_SCRIPT_BODY.
    DOCX bytes returned via auto-collected files list (not stdout base64).
    """
    from __future__ import annotations
    import base64  # only for module-level imports if needed elsewhere — NOT used for DOCX exfiltration
    import json
    import logging
    from typing import Any

    import httpx

    from app.services import audit_service

    logger = logging.getLogger(__name__)


    class DocxGenerationError(RuntimeError):
        """Internal exception raised when sandbox DOCX generation fails. Always caught
        in _generate_docx_post_execute and translated to D-22-15 fallback dict."""


    # The Python script that runs in the sandbox. Reads `INPUT_DATA` (a Python
    # literal prepended by the caller) and writes the .docx to /sandbox/output/.
    # The sandbox auto-collects /sandbox/output/* and uploads them; signed URLs
    # are returned in sb_result["files"].
    DOCX_GENERATION_SCRIPT_BODY = r'''
    import os
    from docx import Document
    from docx.shared import Pt, RGBColor, Inches
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    # Inputs supplied via prepended INPUT_DATA literal (no /sandbox/inputs.json read)
    data = INPUT_DATA  # noqa: F821 — defined by inputs_literal prefix at runtime

    classification = data['classification']      # dict
    review_context_text = data['review_context'] # str (raw)
    playbook = data['playbook']                  # dict (PlaybookContext)
    risks = data['risks']                        # list[ClauseRisk]
    redlines = data['redlines']                  # list[Redline]
    exec_summary = data['executive_summary']     # dict (ExecutiveSummary)

    # Pastel risk colors — D-22-13
    COLOR_GREEN_FILL  = 'E6F4EA'
    COLOR_YELLOW_FILL = 'FEF7E0'
    COLOR_RED_FILL    = 'FCE8E6'

    doc = Document()

    # ---- DOCX-02: Title page ----
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_run = title.add_run('CONFIDENTIAL')
    title_run.bold = True
    title_run.font.size = Pt(20)
    title_run.font.color.rgb = RGBColor(0xCC, 0x00, 0x00)

    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub.add_run('Contract Review Report').bold = True

    doc.add_paragraph(f"Contract type: {classification.get('contract_type', 'Unknown')}")
    doc.add_paragraph(f"Parties: {', '.join(classification.get('parties', []))}")
    doc.add_paragraph(f"Governing law: {classification.get('governing_law', '?')}")
    doc.add_paragraph(f"Overall risk: {exec_summary.get('overall_risk', '?')}")

    doc.add_page_break()

    # ---- DOCX-03: Executive summary section ----
    doc.add_heading('Executive Summary', level=1)
    doc.add_paragraph(exec_summary.get('recommendation', ''))
    breakdown = exec_summary.get('risk_breakdown', {})
    doc.add_paragraph(
        f"Risk breakdown — RED: {breakdown.get('RED', 0)}, "
        f"YELLOW: {breakdown.get('YELLOW', 0)}, GREEN: {breakdown.get('GREEN', 0)}"
    )

    # ---- DOCX-04: Numbered key findings ----
    doc.add_heading('Key Findings', level=1)
    for i, finding in enumerate(exec_summary.get('key_findings', []), 1):
        doc.add_paragraph(f"{i}. {finding}")

    # ---- DOCX-05: Color-coded redline table ----
    doc.add_heading('Detailed Redline Analysis', level=1)
    if risks:
        table = doc.add_table(rows=1, cols=4)
        table.style = 'Light Grid Accent 1'
        hdr = table.rows[0].cells
        hdr[0].text = 'Risk'
        hdr[1].text = 'Clause'
        hdr[2].text = 'Original'
        hdr[3].text = 'Proposed / Rationale'

        # Index redlines by clause_index for lookup
        redline_by_idx = {r.get('clause_index'): r for r in redlines}

        for risk in risks:
            row = table.add_row().cells
            row[0].text = risk.get('risk_grade', '')
            row[1].text = f"{risk.get('clause_category', '')}: {risk.get('clause_heading', '')}"
            rl = redline_by_idx.get(risk.get('clause_index'))
            if rl:
                row[2].text = (rl.get('original_text') or '')[:1500]
                row[3].text = (rl.get('proposed_text') or '') + '\n\n' + (rl.get('rationale') or '')
            else:
                row[2].text = '(no redline — see rationale)'
                row[3].text = risk.get('rationale', '')

            # Apply pastel fill on first cell per D-22-13
            grade = risk.get('risk_grade', '')
            if grade == 'GREEN':
                fill_color = COLOR_GREEN_FILL
            elif grade == 'YELLOW':
                fill_color = COLOR_YELLOW_FILL
            elif grade == 'RED':
                fill_color = COLOR_RED_FILL
            else:
                fill_color = None
            if fill_color:
                from docx.oxml.ns import qn
                from docx.oxml import OxmlElement
                shd = OxmlElement('w:shd')
                shd.set(qn('w:fill'), fill_color)
                row[0]._tc.get_or_add_tcPr().append(shd)

    # ---- DOCX-06: GREEN clauses (no changes recommended) ----
    doc.add_heading('Acceptable Clauses (GREEN)', level=1)
    greens = [r for r in risks if r.get('risk_grade') == 'GREEN']
    if greens:
        for r in greens:
            doc.add_paragraph(
                f"- {r.get('clause_category', '')}: {r.get('clause_heading', '')} — no changes recommended.",
                style='List Bullet',
            )
    else:
        doc.add_paragraph('None — every clause has at least YELLOW status.')

    # ---- DOCX-07: Recommended next steps ----
    doc.add_heading('Recommended Next Steps', level=1)
    for i, step in enumerate(exec_summary.get('next_steps', []), 1):
        doc.add_paragraph(f"{i}. {step}")

    # Persist to sandbox output dir — auto-collected by SandboxService and uploaded
    out_path = '/sandbox/output/contract-review.docx'
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    doc.save(out_path)
    '''


    async def _generate_docx_post_execute(
        *,
        harness_run_id: str,
        thread_id: str,
        user_id: str,
        user_email: str,
        token: str,
        phase_results: dict,
        workspace,                # WorkspaceService instance threaded by engine
    ) -> dict:
        """Read 6 artifacts, run python-docx in sandbox via SandboxService.execute(),
        retrieve auto-collected DOCX bytes, and write to workspace.

        ISSUE-05: sandbox API pinned to SandboxService.execute(); inputs inlined as
        Python literal; DOCX returned via auto-collected files list (not stdout base64).

        D-22-15 invariant: NEVER raise. All failure modes return error dicts.
        """
        run_id_short = (harness_run_id or "")[:8] or "unknown"
        out_path = f"contract-review-{run_id_short}.docx"

        try:
            # 1. Read all 6 artifact files from workspace
            classification_md = (await workspace.read_file(thread_id, "classification.md")).get("content", "")
            review_ctx = (await workspace.read_file(thread_id, "review-context.md")).get("content", "")
            playbook_md = (await workspace.read_file(thread_id, "playbook-context.md")).get("content", "")
            risks_md = (await workspace.read_file(thread_id, "risk-analysis.json")).get("content", "")
            redlines_md = (await workspace.read_file(thread_id, "redlines.json")).get("content", "")
            summary_md = (await workspace.read_file(thread_id, "contract-review-report.md")).get("content", "")

            # Parse classification + summary out of their markdown wrappers (LLM_SINGLE writes JSON)
            classification = _extract_json_from_markdown(classification_md)
            playbook = _extract_json_from_markdown(playbook_md)
            risks = _extract_json_from_markdown(risks_md, default=[])
            redlines = _extract_json_from_markdown(redlines_md, default=[])
            executive_summary = _extract_json_from_markdown(summary_md)

            sandbox_inputs = {
                "classification": classification,
                "review_context": review_ctx,
                "playbook": playbook,
                "risks": risks if isinstance(risks, list) else risks.get("clauses", []),
                "redlines": redlines if isinstance(redlines, list) else redlines.get("redlines", []),
                "executive_summary": executive_summary,
            }

            # 2. Submit to sandbox — PINNED API: SandboxService.execute()
            from app.services.sandbox_service import get_sandbox_service
            sb = get_sandbox_service()

            # Inputs inlined as Python literal at top of script (NO files= kwarg available)
            inputs_literal = f"INPUT_DATA = {json.dumps(sandbox_inputs, ensure_ascii=False)}\n"
            code_with_inputs = inputs_literal + DOCX_GENERATION_SCRIPT_BODY

            sb_result = await sb.execute(
                code=code_with_inputs,
                thread_id=thread_id,
                user_id=user_id,
                token=token,
            )
            if sb_result.get("exit_code") != 0:
                stderr = (sb_result.get("stderr") or "")[:500]
                raise DocxGenerationError(
                    f"sandbox exit_code={sb_result.get('exit_code')}: {stderr}"
                )

            # 3. Retrieve DOCX bytes from auto-collected files (NOT stdout base64)
            sb_files = sb_result.get("files") or []
            if not sb_files:
                raise DocxGenerationError(
                    "sandbox produced no output files (expected contract-review.docx)"
                )
            docx_meta = next(
                (f for f in sb_files if f.get("filename") == "contract-review.docx"),
                None,
            )
            if docx_meta is None:
                names = [f.get("filename") for f in sb_files]
                raise DocxGenerationError(
                    f"contract-review.docx missing in sandbox files: {names}"
                )
            sandbox_signed_url = docx_meta.get("signed_url") or ""
            if not sandbox_signed_url:
                raise DocxGenerationError("sandbox file missing signed_url")

            async with httpx.AsyncClient(timeout=60) as hc:
                resp = await hc.get(sandbox_signed_url)
                resp.raise_for_status()
                docx_bytes = resp.content
            if not docx_bytes:
                raise DocxGenerationError("sandbox returned empty DOCX bytes")

            # 4. Write binary to workspace
            await workspace.write_binary_file(
                thread_id=thread_id,
                file_path=out_path,
                content_bytes=docx_bytes,
                mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                user_id=user_id,
                source="harness",
            )

            # 5. Get a signed URL for the chat bubble link
            signed_url = (
                await workspace.get_signed_url(thread_id, out_path)
                if hasattr(workspace, "get_signed_url")
                else ""
            )

            # 6. Audit log
            try:
                audit_service.log_action(
                    user_id=user_id, user_email=user_email,
                    action="contract_review_docx_generated",
                    resource_type="harness_runs", resource_id=harness_run_id,
                )
            except Exception as exc:
                logger.warning("audit log failed (non-fatal): %s", exc)

            return {"ok": True, "docx_path": out_path, "signed_url": signed_url}

        except Exception as exc:
            logger.warning(
                "docx post_execute failed harness_run=%s: %s",
                harness_run_id, exc, exc_info=True,
            )
            try:
                audit_service.log_action(
                    user_id=user_id, user_email=user_email,
                    action="contract_review_docx_failed",
                    resource_type="harness_runs", resource_id=harness_run_id,
                )
            except Exception:
                pass
            return {
                "error": "docx_generation_failed",
                "code": "DOCX_FAILED",
                "detail": str(exc)[:500],
                "fallback_message": (
                    "DOCX export unavailable right now — the full markdown summary is above. "
                    "Retry by re-running the harness if needed."
                ),
            }


    def _extract_json_from_markdown(md_text: str, default: Any = None) -> Any:
        """LLM_SINGLE phases write markdown with a ```json``` code block; extract it.
        Also handles JSONL streams (one JSON object per line) and raw JSON arrays/objects."""
        if default is None:
            default = {}
        if not md_text:
            return default
        # Try to find a ```json code block
        import re as _re
        m = _re.search(r"```json\s*(\{.*?\}|\[.*?\])\s*```", md_text, _re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                pass
        # Fallback: try to parse the whole text as JSON
        try:
            return json.loads(md_text)
        except Exception:
            pass
        # JSONL fallback: one JSON object per non-empty line
        try:
            rows = []
            for line in md_text.strip().splitlines():
                line = line.strip()
                if not line:
                    continue
                rows.append(json.loads(line))
            if rows:
                return rows
        except Exception:
            pass
        return default
    ```

    Note the deliberate API choices:
    - `await sb.execute(code=..., thread_id=..., user_id=..., token=...)` — PINNED signature, no `files=` or `timeout_seconds=` kwargs.
    - Success check: `sb_result.get("exit_code") != 0` (NOT `sb_result.get("ok")`).
    - DOCX retrieval: HTTP GET on `sb_result["files"][0]["signed_url"]`. NO `DOCX_B64_BEGIN` markers, NO base64 stdout extraction.
    - Inputs marshaled via prepended `INPUT_DATA = {...}` Python literal — no /sandbox/inputs.json file read.
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pytest tests/harnesses/test_contract_review_docx.py -v --tb=short && python -c "from app.harnesses.contract_review_docx import _generate_docx_post_execute, DOCX_GENERATION_SCRIPT_BODY; print('OK' if 'CONFIDENTIAL' in DOCX_GENERATION_SCRIPT_BODY else 'FAIL')"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "CONFIDENTIAL\|E6F4EA\|FEF7E0\|FCE8E6" backend/app/harnesses/contract_review_docx.py` returns `>= 4`
    - `grep -c "_generate_docx_post_execute" backend/app/harnesses/contract_review_docx.py` returns `>= 2`
    - `grep -c "OpenRouterService\|chat_completion" backend/app/harnesses/contract_review_docx.py` returns `0` (no LLM calls in post_execute)
    - `grep -c "contract_review_docx_generated\|contract_review_docx_failed" backend/app/harnesses/contract_review_docx.py` returns `>= 2`
    - `grep -q "\.execute(" backend/app/harnesses/contract_review_docx.py && grep -q "exit_code" backend/app/harnesses/contract_review_docx.py` exits 0 (PINNED API present)
    - `grep -c "execute_code\|DOCX_B64_BEGIN\|/sandbox/inputs.json" backend/app/harnesses/contract_review_docx.py` returns `0` (old API removed)
    - `python -c "from app.harnesses.contract_review_docx import DOCX_GENERATION_SCRIPT_BODY; assert 'add_heading' in DOCX_GENERATION_SCRIPT_BODY and 'add_table' in DOCX_GENERATION_SCRIPT_BODY and 'CONFIDENTIAL' in DOCX_GENERATION_SCRIPT_BODY and '#FCE8E6' in DOCX_GENERATION_SCRIPT_BODY.replace('FCE8E6', '#FCE8E6'); print('OK')"` prints `OK` (pastel hex codes present per D-22-13)
  </acceptance_criteria>
  <done>post_execute callable + DOCX_GENERATION_SCRIPT_BODY string + audit logging + non-fatal fallback all in place; PINNED SandboxService.execute() API used exclusively.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Add CR-08 + DOCX tests</name>
  <files>backend/tests/harnesses/test_contract_review_docx.py</files>
  <read_first>
    - backend/app/harnesses/contract_review.py + backend/app/harnesses/contract_review_docx.py (post-Task-2 state)
    - backend/tests/services/test_harness_engine_post_execute.py (analog from plan 22-03)
  </read_first>
  <behavior>
    Combines behaviors from Task 1 (6 tests) and Task 2 (8 tests, including ISSUE-11 JSONL handling) for a total of 14 tests (13 unit + 1 integration-gated real-sandbox). The integration test is skipped unless `RUN_SANDBOX_INTEGRATION_TESTS=1`. See behavior blocks above.
  </behavior>
  <action>
    Create `backend/tests/harnesses/test_contract_review_docx.py` with 14 tests (13 unit, 1 integration-gated).

    For tests 2-5 of Task 2 (post_execute behavior), mock:
    - `WorkspaceService.read_file` returning canned markdown content for each of the 6 files
    - `WorkspaceService.write_binary_file` returning `{"ok": True, "size_bytes": 12345}`
    - `WorkspaceService.get_signed_url` returning `"https://example.com/signed"`
    - `sandbox_service.get_sandbox_service().execute` returning `{"exit_code": 0, "stdout": "", "stderr": "", "files": [{"filename": "contract-review.docx", "size_bytes": 12345, "signed_url": "https://sandbox.example/abc.docx", "storage_path": "..."}]}`
    - `httpx.AsyncClient.get` returning a response with `content=b"FAKE_DOCX_BYTES"` and `raise_for_status` no-op
    - `audit_service.log_action` (assert called with the right action strings)

    Concrete test 4 (sandbox failure → fallback):
    ```python
    @pytest.mark.asyncio
    async def test_post_execute_sandbox_failure_returns_error_dict():
        from app.harnesses.contract_review_docx import _generate_docx_post_execute
        ws = MagicMock()
        ws.read_file = AsyncMock(return_value={"content": '{"ok": true}'})

        with patch("app.services.sandbox_service.get_sandbox_service") as gs:
            gs.return_value.execute = AsyncMock(return_value={"exit_code": 1, "stderr": "boom", "files": []})
            result = await _generate_docx_post_execute(
                harness_run_id="abc12345",
                thread_id="thr",
                user_id="u",
                user_email="e@x",
                token="tok",
                phase_results={},
                workspace=ws,
            )
        assert result["error"] == "docx_generation_failed"
        assert result["code"] == "DOCX_FAILED"
        assert "fallback_message" in result
        # MUST NOT raise — pytest will fail if exception propagates
    ```

    Concrete test 6 (script structure — pastel colors and required sections per D-22-13):
    ```python
    def test_docx_script_body_has_required_sections_and_pastel_colors():
        from app.harnesses.contract_review_docx import DOCX_GENERATION_SCRIPT_BODY
        # Required python-docx primitives
        assert "add_heading" in DOCX_GENERATION_SCRIPT_BODY
        assert "add_table" in DOCX_GENERATION_SCRIPT_BODY
        # Required content marker (DOCX-02 title page)
        assert "CONFIDENTIAL" in DOCX_GENERATION_SCRIPT_BODY
        # Pastel risk colors per D-22-13
        assert "E6F4EA" in DOCX_GENERATION_SCRIPT_BODY  # GREEN
        assert "FEF7E0" in DOCX_GENERATION_SCRIPT_BODY  # YELLOW
        assert "FCE8E6" in DOCX_GENERATION_SCRIPT_BODY  # RED
    ```

    Concrete test 7 (no LLM calls — module-level static check):
    ```python
    def test_docx_module_makes_no_llm_calls():
        import pathlib
        text = pathlib.Path("backend/app/harnesses/contract_review_docx.py").read_text()
        assert "OpenRouterService" not in text
        assert "chat_completion" not in text
    ```

    Concrete test 9 (PINNED API check — no execute_code, no files= kwarg, no DOCX_B64_BEGIN):
    ```python
    def test_module_uses_pinned_sandbox_api_only():
        import pathlib
        text = pathlib.Path("backend/app/harnesses/contract_review_docx.py").read_text()
        assert ".execute(" in text, "must call SandboxService.execute()"
        assert "exit_code" in text, "must check exit_code (not 'ok')"
        assert "execute_code" not in text, "must NOT use legacy execute_code API"
        assert "DOCX_B64_BEGIN" not in text, "must NOT base64-exfiltrate via stdout"
        assert "/sandbox/inputs.json" not in text, "must inline INPUT_DATA, not file-read"
    ```

    Test 11 (integration-gated, ISSUE-05 — real sandbox):
    ```python
    @pytest.mark.integration
    @pytest.mark.skipif(not os.getenv("RUN_SANDBOX_INTEGRATION_TESTS"), reason="real sandbox gated")
    @pytest.mark.asyncio
    async def test_post_execute_real_sandbox_smoke():
        # Invokes _generate_docx_post_execute with real SandboxService (NOT stub).
        # Asserts non-empty DOCX bytes returned and write_binary_file called.
        ...
    ```
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pytest tests/harnesses/test_contract_review_docx.py -v --tb=short</automated>
  </verify>
  <acceptance_criteria>
    - `pytest backend/tests/harnesses/test_contract_review_docx.py -v` exits 0; 14 tests collected (13 unit + 1 integration-gated; integration test skipped unless RUN_SANDBOX_INTEGRATION_TESTS=1)
    - ISSUE-05 acceptance: a real-sandbox integration test exists, marked `@pytest.mark.integration` and gated behind `os.getenv("RUN_SANDBOX_INTEGRATION_TESTS")`. It invokes `_generate_docx_post_execute` with a real `SandboxService` (not stub) and asserts a non-empty DOCX returned. CI defaults to skipping (env unset) but the test MUST exist.
    - `grep -c "DOCX_FAILED\|fallback_message" backend/tests/harnesses/test_contract_review_docx.py` returns `>= 2`
    - `grep -q "\.execute(" backend/tests/harnesses/test_contract_review_docx.py && grep -q "exit_code" backend/tests/harnesses/test_contract_review_docx.py` exits 0
  </acceptance_criteria>
  <done>14 tests pass (13 unit + 1 integration-gated; integration test skipped unless RUN_SANDBOX_INTEGRATION_TESTS=1), locking in CR-08 + DOCX-01..08 contracts and the PINNED SandboxService.execute() API.</done>
</task>

</tasks>

<truths>
- D-22-12 (programmatic generation, no template) — script as string, runs in sandbox.
- D-22-13 (pastel risk colors) — three exact hex codes (#E6F4EA, #FEF7E0, #FCE8E6).
- D-22-14 (filename pattern, source='harness', no auto-download) — filename uses `harness_run_id[:8]`.
- D-22-15 (non-fatal fallback) — error dict + fallback_message; harness_runs.status stays `completed` (enforced by plan 22-03 invocation site).
- B4 single-registry NOT applicable here — post_execute does NOT call cloud LLMs (plan 22-09 covered all LLM call sites for CR-06/07; CR-08 LLM_SINGLE is the engine's normal LLM call before post_execute fires).
- SEC-04 NOT applicable — no LLM payload here.
- OBS-02: thread_id correlation logging via the existing logger.warning calls.
- Audit log: `contract_review_docx_generated` on success, `contract_review_docx_failed` on fallback (PATTERNS.md L527).
- CR-21-01 circular-import guard via `_docx_post_execute_shim` lazy import.
- ISSUE-05 PIN: SandboxService.execute() — NO files= kwarg, NO timeout_seconds= kwarg, NO ok field. Inputs inlined as INPUT_DATA literal; DOCX bytes via auto-collected files list (NOT base64 stdout).
- CR-08 lives at phases[8] in the 9-phase HarnessDefinition (filter-redline-candidates inserted at phases[6] shifts CR-07 to phases[7] and CR-08 to phases[8]).
</truths>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Workspace artifact files → sandbox script | Files contain real PII; sandbox is isolated container, not host |
| Sandbox auto-collected files → backend HTTP GET | Signed URL fetch bounded by httpx 60s timeout |
| DOCX bytes → workspace write_binary_file | RLS enforces thread-ownership; binary stored in Supabase Storage with metadata in workspace_files |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-22-10-01 | Information Disclosure | DOCX file path traversal | mitigate | Filename `contract-review-{8-char-hex}.docx` is safe; `validate_workspace_path` upstream rejects `..` `/` etc |
| T-22-10-02 | Tampering | INPUT_DATA literal escape via injected JSON | mitigate | All inputs json.dumps'd — no raw text concatenation; sandbox isolation prevents host impact |
| T-22-10-03 | DoS | Pathological input causing 5GB DOCX | mitigate | Sandbox config-level timeout; redline cell text capped at 1500 chars in script |
| T-22-10-04 | Information Disclosure | DOCX containing PII reaching cloud LLM | n/a | post_execute does NOT call any LLM (Test 7 enforces); DOCX is purely deterministic serialization |
| T-22-10-05 | Repudiation | DOCX generation untraceable | mitigate | audit_service.log_action with `contract_review_docx_generated` / `_failed`; existing LangSmith covers harness_engine |
</threat_model>

<verification>
1. `pytest backend/tests/harnesses/test_contract_review_docx.py -v` exits 0 with 14 tests collected (13 unit + 1 integration-gated)
2. `pytest backend/tests/harnesses/ backend/tests/services/test_harness_engine_post_execute.py -v` exits 0 (full regression)
3. `python -c "from app.main import app; print('OK')"` prints `OK`
4. `python -c "from app.harnesses.contract_review import CONTRACT_REVIEW; assert all(p.system_prompt_template != 'STUB' or p.executor for p in CONTRACT_REVIEW.phases); print('OK')"` prints `OK` — no remaining STUBs
5. `python -c "from app.harnesses.contract_review import CONTRACT_REVIEW; assert CONTRACT_REVIEW.phases[8].name == 'executive-summary' and CONTRACT_REVIEW.phases[8].post_execute is not None; print('OK')"` prints `OK`
</verification>

<success_criteria>
- CR-08 LLM_SINGLE writes contract-review-report.md with ExecutiveSummary
- post_execute generates a polished .docx with all 7 sections
- Pastel risk colors honored (D-22-13)
- D-22-15 fallback path tested
- PINNED SandboxService.execute() API used exclusively (no execute_code, no files= kwarg, no base64 stdout exfiltration)
- Off-mode invariant: when contract_review_enabled=False, the harness is not registered, post_execute callable is dead code
</success_criteria>

<output>
After completion, create `.planning/phases/22-contract-review-harness-docx-deliverable/22-10-SUMMARY.md`.
</output>
