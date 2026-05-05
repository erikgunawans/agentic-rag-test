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
    - "CR-08 (executive-summary) is LLM_SINGLE; output_schema=ExecutiveSummary; engine writes the validated JSON to executive-summary.json"
    - "REVIEW #6 closed: a deterministic _render_summary_markdown step (run inside post_execute) reads executive-summary.json and writes contract-review-report.md as REAL markdown — not raw JSON in a .md file"
    - "post_execute=_docx_post_execute_shim wired on CR-08 (phases[8])"
    - "_generate_docx_post_execute (a) calls _render_summary_markdown to produce the markdown report, (b) reads 6 artifacts, (c) builds python-docx script, (d) runs in sandbox via SandboxService.execute(), (e) writes DOCX to workspace_files with source='harness'"
    - "post_execute return now includes wrote_binary=True + size_bytes so plan 22-03 engine wraps with workspace_updated event (REVIEW #7)"
    - "Filename pattern: contract-review-{harness_run_id[:8]}.docx (D-22-14)"
    - "D-22-15 non-fatal fallback: post_execute returns error dict on sandbox failure; harness_runs.status stays 'completed'"
    - "Sandbox API PINNED: SandboxService.execute(*, code, thread_id, user_id, token); DOCX bytes via auto-collected files[0].signed_url HTTP GET"
  artifacts:
    - path: "backend/app/harnesses/contract_review.py"
      provides: "ExecutiveSummary schema + CR-08 prompt + _render_summary_markdown helper + post_execute shim"
      contains: "_render_summary_markdown"
    - path: "backend/app/harnesses/contract_review_docx.py"
      provides: "_generate_docx_post_execute + DOCX_GENERATION_SCRIPT_BODY"
      contains: "DOCX_GENERATION_SCRIPT_BODY"
    - path: "backend/tests/harnesses/test_contract_review_docx.py"
      provides: "Tests for ExecutiveSummary, markdown render (REVIEW #6), post_execute success/fail (REVIEW #7 wrote_binary), DOCX structure"
  key_links:
    - from: "CR-08 LLM_SINGLE output (executive-summary.json)"
      to: "_render_summary_markdown writes contract-review-report.md"
      via: "deterministic markdown render (REVIEW #6)"
      pattern: "contract-review-report\\.md"
    - from: "_generate_docx_post_execute return"
      to: "engine workspace_updated emission (plan 22-03)"
      via: "wrote_binary=True flag (REVIEW #7)"
      pattern: "wrote_binary"
---

<objective>
Replace the CR-08 stub. Three review findings drive this plan's structure:

1. **REVIEW #6:** prior plan had CR-08's LLM_SINGLE write `contract-review-report.md` directly. But `LLM_SINGLE` writes raw JSON (verified at `harness_engine.py:615-623`). Fix: CR-08 writes `executive-summary.json` (JSON), and a NEW deterministic `_render_summary_markdown` step inside post_execute renders it into actual markdown at `contract-review-report.md`.

2. **REVIEW #7:** post_execute return must include `wrote_binary=True` + `size_bytes` so the engine (plan 22-03) emits `workspace_updated` after the DOCX write. Frontend Workspace Panel auto-refreshes.

3. **D-22-15 non-fatal fallback** preserved.

Output: ExecutiveSummary + CR-08 prompt + markdown render helper + DOCX post_execute callable + tests.
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
<!-- ISSUE-05 PIN: SandboxService.execute(*, code, thread_id, user_id, token) -->
<!--   Returns {stdout, stderr, exit_code, error_type, execution_ms, files, execution_id} -->
<!--   files[i] = {filename, size_bytes, signed_url, storage_path} (auto-collected /sandbox/output/*) -->
<!--   NO files= kwarg, NO timeout_seconds= kwarg, NO ok field. -->

ExecutiveSummary schema (REVIEW #6 — written as JSON, NOT markdown):
```python
class ExecutiveSummary(BaseModel):
    overall_risk: RiskGrade
    recommendation: str = Field(..., min_length=20, max_length=2000)
    key_findings: list[str] = Field(..., min_length=1, max_length=10)
    risk_breakdown: dict[str, int]
    next_steps: list[str] = Field(..., min_length=1, max_length=10)
```

CR-08 phase config (REVIEW #6):
```python
PhaseDefinition(
    name="executive-summary",
    phase_type=PhaseType.LLM_SINGLE,
    workspace_output="executive-summary.json",   # CHANGED — was contract-review-report.md
    output_schema=ExecutiveSummary,
    post_execute=_docx_post_execute_shim,
    ...
)
```

post_execute return shape (REVIEW #7 — engine emits workspace_updated):
```python
{
    "ok": True,
    "docx_path": "contract-review-{run_id_short}.docx",
    "signed_url": "<workspace signed url>",
    "wrote_binary": True,        # NEW (REVIEW #7) — triggers engine workspace_updated emission
    "size_bytes": int,           # NEW
}
```
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: ExecutiveSummary + CR-08 prompt + _render_summary_markdown helper (REVIEW #6)</name>
  <files>backend/app/harnesses/contract_review.py</files>
  <read_first>
    - backend/app/harnesses/contract_review.py (post-Plan-22-09 state — find CR-08 stub at phases[8])
    - backend/app/services/harness_engine.py (lines 615-623 — confirm LLM_SINGLE writes raw JSON, REVIEW #6 anchor)
    - .planning/phases/22-contract-review-harness-docx-deliverable/22-REVIEWS.md (review finding #6)
  </read_first>
  <behavior>
    - Test 1: ExecutiveSummary accepts a fully-populated valid instance.
    - Test 2: ExecutiveSummary rejects empty key_findings.
    - Test 3: CR-08 phase has `output_schema=ExecutiveSummary`.
    - Test 4 (REVIEW #6): CR-08 phase `workspace_output == "executive-summary.json"` — NOT `contract-review-report.md`.
    - Test 5: CR-08 prompt mentions reading the 6 input files.
    - Test 6: `_render_summary_markdown` produces markdown with `# Contract Review Report`, `## Executive Summary`, `## Risk Breakdown`, `## Key Findings`, `## Recommended Next Steps` sections.
    - Test 7: `_render_summary_markdown` writes `contract-review-report.md` to workspace via `write_text_file`.
    - Test 8 (REVIEW #6 anti-regression): rendered output starts with `# ` (markdown header) and is NOT raw JSON (does NOT start with `{`).
  </behavior>
  <action>
    Edit `backend/app/harnesses/contract_review.py`:

    **A) Add ExecutiveSummary schema** below ClauseRisk + Redline:
    ```python
    class ExecutiveSummary(BaseModel):
        overall_risk: RiskGrade
        recommendation: str = Field(..., min_length=20, max_length=2000)
        key_findings: list[str] = Field(..., min_length=1, max_length=10)
        risk_breakdown: dict[str, int]
        next_steps: list[str] = Field(..., min_length=1, max_length=10)
    ```

    **B) Replace CR-08 prompt + change workspace_output to executive-summary.json** (REVIEW #6):
    ```python
    PhaseDefinition(
        name="executive-summary",
        phase_type=PhaseType.LLM_SINGLE,
        system_prompt_template=(
            "You are writing the executive summary for a Contract Review run.\n\n"
            "INPUTS (workspace files):\n"
            "  - classification.md, review-context.md, playbook-context.md\n"
            "  - clauses.md, risk-analysis.json, redlines.json\n\n"
            "OUTPUT: a JSON object matching ExecutiveSummary schema. Return ONLY JSON, no prose.\n"
            "If playbook-context.md.context_quality == 'unfounded', BEGIN your recommendation with:\n"
            "  'No playbook materials found — risk grades reflect generic legal standards.'"
        ),
        workspace_inputs=["classification.md", "review-context.md", "playbook-context.md",
                          "clauses.md", "risk-analysis.json", "redlines.json"],
        workspace_output="executive-summary.json",       # REVIEW #6: JSON, not markdown
        output_schema=ExecutiveSummary,
        post_execute=_docx_post_execute_shim,
        timeout_seconds=180,
    )
    ```

    **C) Add `_render_summary_markdown` helper** below ExecutiveSummary:
    ```python
    async def _render_summary_markdown(
        *,
        executive_summary: dict,
        classification: dict,
        playbook: dict,
        risks: list,
        redlines: list,
        workspace,
        thread_id: str,
    ) -> str:
        """REVIEW #6: deterministic markdown render of executive-summary.json into
        contract-review-report.md. CR-08's LLM_SINGLE writes the JSON; this helper
        produces the human-readable markdown that users (and the DOCX) consume.

        Returns the rendered markdown string AND writes contract-review-report.md.
        """
        rb = executive_summary.get("risk_breakdown") or {}
        red_n = int(rb.get("RED", 0))
        yellow_n = int(rb.get("YELLOW", 0))
        green_n = int(rb.get("GREEN", 0))

        contract_type = classification.get("contract_type", "Unknown")
        parties = classification.get("parties") or []
        governing_law = classification.get("governing_law", "?")
        overall_risk = executive_summary.get("overall_risk", "?")
        recommendation = executive_summary.get("recommendation", "")
        key_findings = executive_summary.get("key_findings") or []
        next_steps = executive_summary.get("next_steps") or []

        lines: list[str] = []
        lines.append("# Contract Review Report")
        lines.append("")
        lines.append("**CONFIDENTIAL — Privileged Legal Analysis**")
        lines.append("")
        lines.append(f"- **Contract type:** {contract_type}")
        lines.append(f"- **Parties:** {', '.join(parties) if parties else '—'}")
        lines.append(f"- **Governing law:** {governing_law}")
        lines.append(f"- **Overall risk:** **{overall_risk}**")
        lines.append("")
        lines.append("## Executive Summary")
        lines.append("")
        lines.append(recommendation)
        lines.append("")
        lines.append("## Risk Breakdown")
        lines.append("")
        lines.append(f"- RED: **{red_n}**")
        lines.append(f"- YELLOW: **{yellow_n}**")
        lines.append(f"- GREEN: **{green_n}**")
        lines.append("")
        lines.append("## Key Findings")
        lines.append("")
        for i, f in enumerate(key_findings, 1):
            lines.append(f"{i}. {f}")
        lines.append("")
        lines.append("## Detailed Redline Analysis")
        lines.append("")
        if redlines:
            lines.append("| # | Clause | Original (truncated) | Proposed |")
            lines.append("|---|--------|----------------------|----------|")
            for r in (redlines or []):
                if not isinstance(r, dict):
                    continue
                idx = r.get("clause_index", "?")
                cat = r.get("clause_category", "")
                orig = (r.get("original_text") or "").replace("|", r"\|")[:120]
                prop = (r.get("proposed_text") or "").replace("|", r"\|")[:120]
                lines.append(f"| {idx} | {cat} | {orig} | {prop} |")
        else:
            lines.append("_No redlines proposed (all clauses GREEN, or filter found no candidates)._")
        lines.append("")
        lines.append("## Recommended Next Steps")
        lines.append("")
        for i, s in enumerate(next_steps, 1):
            lines.append(f"{i}. {s}")
        lines.append("")

        markdown = "\n".join(lines)

        try:
            await workspace.write_text_file(
                thread_id, "contract-review-report.md", markdown, source="harness",
            )
        except Exception as exc:
            logger.warning("REVIEW #6: contract-review-report.md write failed: %s", exc)

        return markdown
    ```

    **D) Wire post_execute via shim** (right after imports, breaks circular import):
    ```python
    async def _docx_post_execute_shim(**kwargs):
        from app.harnesses.contract_review_docx import _generate_docx_post_execute
        return await _generate_docx_post_execute(**kwargs)
    ```
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pytest tests/harnesses/test_contract_review_docx.py -v --tb=short -k "render_summary or executive_summary or cr08" && python -c "from app.harnesses.contract_review import ExecutiveSummary, _render_summary_markdown, CONTRACT_REVIEW; print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `python -c "from app.harnesses.contract_review import ExecutiveSummary; e = ExecutiveSummary(overall_risk='YELLOW', recommendation='Sign with redlines applied for two YELLOW clauses.', key_findings=['IP too broad','Liability too low'], risk_breakdown={'GREEN':5,'YELLOW':2,'RED':0}, next_steps=['Apply redlines 1-2']); print(e.overall_risk)"` prints `RiskGrade.YELLOW`
    - `grep -c "_render_summary_markdown" backend/app/harnesses/contract_review.py` returns `>= 2`
    - `grep -c "REVIEW #6" backend/app/harnesses/contract_review.py` returns `>= 2`
    - `grep -c "executive-summary.json" backend/app/harnesses/contract_review.py` returns `>= 2`
    - `python -c "from app.harnesses.contract_review import CONTRACT_REVIEW; assert CONTRACT_REVIEW.phases[8].workspace_output == 'executive-summary.json'; print('OK')"` prints `OK`
  </acceptance_criteria>
  <done>ExecutiveSummary schema + CR-08 prompt + workspace_output changed to JSON + _render_summary_markdown helper added.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: _generate_docx_post_execute with markdown render + REVIEW #7 wrote_binary flag</name>
  <files>backend/app/harnesses/contract_review_docx.py</files>
  <read_first>
    - backend/app/services/sandbox_service.py (lines 228-258 — `SandboxService.execute(*, code, thread_id, user_id, token)` PINNED signature)
    - backend/app/services/workspace_service.py (lines 511-660 — write_binary_file)
    - backend/app/harnesses/contract_review.py (post-Task-1 — for ClauseRisk, ExecutiveSummary, _render_summary_markdown imports)
    - backend/app/services/audit_service.py (find log_action)
    - .planning/phases/22-contract-review-harness-docx-deliverable/22-REVIEWS.md (findings #6 + #7)
  </read_first>
  <behavior>
    - Test 1: post_execute reads classification.md, review-context.md, playbook-context.md, executive-summary.json, risk-analysis.json, redlines.json from workspace.
    - Test 2: post_execute calls `_render_summary_markdown` → contract-review-report.md gets written (REVIEW #6).
    - Test 3: On sandbox success (exit_code=0, files=[{signed_url, ...}]), HTTP-GETs the signed URL, calls write_binary_file with `file_path="contract-review-{run_id[:8]}.docx"`, source="harness".
    - Test 4: Returns `{"ok": True, "docx_path": ..., "signed_url": ..., "wrote_binary": True, "size_bytes": N}` on success — REVIEW #7 wrote_binary flag is True.
    - Test 5: On sandbox non-zero exit_code, returns `{"error": ..., "code": "DOCX_FAILED", ..., "fallback_message": ...}` (does NOT raise; wrote_binary absent or False).
    - Test 6: Audit log fires `contract_review_docx_generated` on success, `contract_review_docx_failed` on fallback.
    - Test 7: DOCX_GENERATION_SCRIPT_BODY contains `from docx import Document`, `add_heading`, `add_table`, the three pastel hex codes (E6F4EA, FEF7E0, FCE8E6), and `CONFIDENTIAL`.
    - Test 8: post_execute does NOT make LLM calls (no OpenRouterService imports).
    - Test 9: PINNED API check — module text contains `.execute(` and `exit_code` and does NOT contain `execute_code`, `files=` kwarg, or `DOCX_B64_BEGIN`.
    - Test 10 (REVIEW #6 — markdown rendered, not JSON): when post_execute runs successfully, `contract-review-report.md` was written with content starting with `# Contract Review Report` (markdown header), not `{` (JSON brace).
  </behavior>
  <action>
    Create `backend/app/harnesses/contract_review_docx.py` with the following structure:

    ```python
    """Phase 22 / DOCX-01..08 — Sandbox-driven .docx generation post_execute callback.

    Called by harness_engine after CR-08 (executive-summary) completes its LLM_SINGLE call.

    REVIEW #6: this callback runs `_render_summary_markdown` first to produce the
    deterministic human-readable contract-review-report.md, THEN proceeds to DOCX.
    Without this rendering, `contract-review-report.md` would be raw JSON (LLM_SINGLE
    writes JSON to workspace_output).

    REVIEW #7: returns wrote_binary=True + size_bytes so the engine emits a
    workspace_updated event after the DOCX write — the frontend Workspace Panel
    auto-refreshes.

    D-22-15: NEVER raise — error dict + fallback_message on any failure.
    """
    from __future__ import annotations
    import json
    import logging
    from typing import Any

    import httpx

    from app.services import audit_service

    logger = logging.getLogger(__name__)


    class DocxGenerationError(RuntimeError):
        """Internal — caught in _generate_docx_post_execute and translated to D-22-15 fallback."""


    DOCX_GENERATION_SCRIPT_BODY = r'''
    import os
    from docx import Document
    from docx.shared import Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    data = INPUT_DATA  # noqa: F821 — defined by inputs_literal prefix at runtime
    classification = data['classification']
    review_context_text = data['review_context']
    playbook = data['playbook']
    risks = data['risks']
    redlines = data['redlines']
    exec_summary = data['executive_summary']

    # Pastel risk colors — D-22-13
    COLOR_GREEN_FILL  = 'E6F4EA'
    COLOR_YELLOW_FILL = 'FEF7E0'
    COLOR_RED_FILL    = 'FCE8E6'

    doc = Document()

    # Title page (DOCX-02)
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

    # Executive summary (DOCX-03)
    doc.add_heading('Executive Summary', level=1)
    doc.add_paragraph(exec_summary.get('recommendation', ''))
    breakdown = exec_summary.get('risk_breakdown', {})
    doc.add_paragraph(
        f"Risk breakdown — RED: {breakdown.get('RED', 0)}, "
        f"YELLOW: {breakdown.get('YELLOW', 0)}, GREEN: {breakdown.get('GREEN', 0)}"
    )

    # Numbered key findings (DOCX-04)
    doc.add_heading('Key Findings', level=1)
    for i, finding in enumerate(exec_summary.get('key_findings', []), 1):
        doc.add_paragraph(f"{i}. {finding}")

    # Color-coded redline table (DOCX-05)
    doc.add_heading('Detailed Redline Analysis', level=1)
    if risks:
        table = doc.add_table(rows=1, cols=4)
        table.style = 'Light Grid Accent 1'
        hdr = table.rows[0].cells
        hdr[0].text = 'Risk'
        hdr[1].text = 'Clause'
        hdr[2].text = 'Original'
        hdr[3].text = 'Proposed / Rationale'

        redline_by_idx = {r.get('clause_index'): r for r in (redlines or [])}

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

    # GREEN clauses (DOCX-06)
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

    # Recommended next steps (DOCX-07)
    doc.add_heading('Recommended Next Steps', level=1)
    for i, step in enumerate(exec_summary.get('next_steps', []), 1):
        doc.add_paragraph(f"{i}. {step}")

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
        workspace,
        harness_name: str = "contract-review",
        **_,  # forward-compat
    ) -> dict:
        """REVIEW #6 + #7 + D-22-15. NEVER raises."""
        from app.harnesses.contract_review import _render_summary_markdown

        run_id_short = (harness_run_id or "")[:8] or "unknown"
        out_path = f"contract-review-{run_id_short}.docx"

        try:
            # Read all artifacts
            classification_md = (await workspace.read_file(thread_id, "classification.md")).get("content", "")
            review_ctx = (await workspace.read_file(thread_id, "review-context.md")).get("content", "")
            playbook_md = (await workspace.read_file(thread_id, "playbook-context.md")).get("content", "")
            risks_md = (await workspace.read_file(thread_id, "risk-analysis.json")).get("content", "")
            redlines_md = (await workspace.read_file(thread_id, "redlines.json")).get("content", "")
            exec_summary_md = (await workspace.read_file(thread_id, "executive-summary.json")).get("content", "")

            classification = _extract_json_from_markdown(classification_md)
            playbook = _extract_json_from_markdown(playbook_md)
            risks = _extract_json_from_markdown(risks_md, default=[])
            redlines = _extract_json_from_markdown(redlines_md, default=[])
            executive_summary = _extract_json_from_markdown(exec_summary_md)

            # REVIEW #6: render the deterministic markdown report BEFORE DOCX generation
            await _render_summary_markdown(
                executive_summary=executive_summary if isinstance(executive_summary, dict) else {},
                classification=classification if isinstance(classification, dict) else {},
                playbook=playbook if isinstance(playbook, dict) else {},
                risks=risks if isinstance(risks, list) else [],
                redlines=redlines if isinstance(redlines, list) else [],
                workspace=workspace,
                thread_id=thread_id,
            )

            # Build sandbox inputs
            sandbox_inputs = {
                "classification": classification if isinstance(classification, dict) else {},
                "review_context": review_ctx,
                "playbook": playbook if isinstance(playbook, dict) else {},
                "risks": risks if isinstance(risks, list) else [],
                "redlines": redlines if isinstance(redlines, list) else [],
                "executive_summary": executive_summary if isinstance(executive_summary, dict) else {},
            }

            from app.services.sandbox_service import get_sandbox_service
            sb = get_sandbox_service()

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
                raise DocxGenerationError(f"sandbox exit_code={sb_result.get('exit_code')}: {stderr}")

            sb_files = sb_result.get("files") or []
            if not sb_files:
                raise DocxGenerationError("sandbox produced no output files")

            docx_meta = next(
                (f for f in sb_files if f.get("filename") == "contract-review.docx"),
                None,
            )
            if docx_meta is None:
                raise DocxGenerationError(f"contract-review.docx missing in sandbox files: {[f.get('filename') for f in sb_files]}")
            sandbox_signed_url = docx_meta.get("signed_url") or ""
            if not sandbox_signed_url:
                raise DocxGenerationError("sandbox file missing signed_url")

            async with httpx.AsyncClient(timeout=60) as hc:
                resp = await hc.get(sandbox_signed_url)
                resp.raise_for_status()
                docx_bytes = resp.content
            if not docx_bytes:
                raise DocxGenerationError("sandbox returned empty DOCX bytes")

            # Workspace write
            await workspace.write_binary_file(
                thread_id=thread_id,
                file_path=out_path,
                content_bytes=docx_bytes,
                mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                user_id=user_id,
                source="harness",
            )

            # Signed URL for chat chip
            signed_url = ""
            if hasattr(workspace, "get_signed_url"):
                try:
                    signed_url = await workspace.get_signed_url(thread_id, out_path) or ""
                except Exception as exc:
                    logger.warning("get_signed_url failed (non-fatal): %s", exc)

            try:
                audit_service.log_action(
                    user_id=user_id, user_email=user_email,
                    action="contract_review_docx_generated",
                    resource_type="harness_runs", resource_id=harness_run_id,
                )
            except Exception as exc:
                logger.warning("audit log failed (non-fatal): %s", exc)

            # REVIEW #7: wrote_binary=True signals plan 22-03 engine to emit workspace_updated
            return {
                "ok": True,
                "docx_path": out_path,
                "signed_url": signed_url,
                "wrote_binary": True,
                "size_bytes": len(docx_bytes),
            }

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
        if default is None:
            default = {}
        if not md_text:
            return default
        import re as _re
        m = _re.search(r"```json\s*(\{.*?\}|\[.*?\])\s*```", md_text, _re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                pass
        try:
            return json.loads(md_text)
        except Exception:
            pass
        return default
    ```
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pytest tests/harnesses/test_contract_review_docx.py -v --tb=short && python -c "from app.harnesses.contract_review_docx import _generate_docx_post_execute, DOCX_GENERATION_SCRIPT_BODY; print('OK' if 'CONFIDENTIAL' in DOCX_GENERATION_SCRIPT_BODY else 'FAIL')"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "CONFIDENTIAL\|E6F4EA\|FEF7E0\|FCE8E6" backend/app/harnesses/contract_review_docx.py` returns `>= 4`
    - `grep -c "_render_summary_markdown" backend/app/harnesses/contract_review_docx.py` returns `>= 1` (REVIEW #6 — called inside post_execute)
    - `grep -c "wrote_binary" backend/app/harnesses/contract_review_docx.py` returns `>= 1` (REVIEW #7)
    - `grep -c "OpenRouterService\|chat_completion" backend/app/harnesses/contract_review_docx.py` returns `0`
    - `grep -c "contract_review_docx_generated\|contract_review_docx_failed" backend/app/harnesses/contract_review_docx.py` returns `>= 2`
    - `grep -q "\.execute(" backend/app/harnesses/contract_review_docx.py && grep -q "exit_code" backend/app/harnesses/contract_review_docx.py` exits 0
    - `grep -c "execute_code\|DOCX_B64_BEGIN" backend/app/harnesses/contract_review_docx.py` returns `0`
  </acceptance_criteria>
  <done>post_execute callable + markdown render + wrote_binary flag + DOCX script body all in place.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: CR-08 + DOCX tests (REVIEW #6 + #7)</name>
  <files>backend/tests/harnesses/test_contract_review_docx.py</files>
  <read_first>
    - backend/app/harnesses/contract_review.py + contract_review_docx.py (post-Task-2 state)
    - backend/tests/services/test_harness_engine_post_execute.py (analog from plan 22-03)
  </read_first>
  <behavior>
    See behaviors 1-10 in Task 1 + 1-10 in Task 2. Total ~14 unit tests + 1 integration-gated.
  </behavior>
  <action>
    Create `backend/tests/harnesses/test_contract_review_docx.py` with ~15 tests.

    Concrete test 4 (REVIEW #7 — wrote_binary):
    ```python
    @pytest.mark.asyncio
    async def test_post_execute_returns_wrote_binary_true_on_success():
        """REVIEW #7: post_execute return must include wrote_binary=True + size_bytes
        so the engine (plan 22-03) emits workspace_updated."""
        from app.harnesses.contract_review_docx import _generate_docx_post_execute
        ws = MagicMock()
        ws.read_file = AsyncMock(return_value={"content": '{"overall_risk":"GREEN","recommendation":"x"*30,"key_findings":["a"],"risk_breakdown":{"GREEN":1},"next_steps":["b"]}'})
        ws.write_text_file = AsyncMock(return_value={"ok": True})
        ws.write_binary_file = AsyncMock(return_value={"ok": True})
        ws.get_signed_url = AsyncMock(return_value="https://example.com/signed")

        with patch("app.services.sandbox_service.get_sandbox_service") as gs:
            gs.return_value.execute = AsyncMock(return_value={
                "exit_code": 0, "stdout": "", "stderr": "",
                "files": [{"filename": "contract-review.docx", "size_bytes": 9876,
                           "signed_url": "https://sandbox.example/abc.docx"}],
            })
            with patch("httpx.AsyncClient") as hc_cls:
                hc_cls.return_value.__aenter__.return_value.get = AsyncMock(
                    return_value=MagicMock(content=b"FAKE_DOCX_BYTES", raise_for_status=lambda: None)
                )
                result = await _generate_docx_post_execute(
                    harness_run_id="abc12345", thread_id="thr", user_id="u",
                    user_email="e@x", token="tok", phase_results={}, workspace=ws,
                )

        assert result["ok"] is True
        assert result["wrote_binary"] is True, "REVIEW #7: must signal engine to emit workspace_updated"
        assert result["size_bytes"] == len(b"FAKE_DOCX_BYTES")
        assert result["docx_path"] == "contract-review-abc12345.docx"
    ```

    Concrete test 10 (REVIEW #6 — markdown rendered, not JSON):
    ```python
    @pytest.mark.asyncio
    async def test_post_execute_writes_markdown_not_json_to_report_file():
        """REVIEW #6: contract-review-report.md must be MARKDOWN (starts with '# '), NOT
        raw JSON in a .md file. The deterministic _render_summary_markdown step ensures this."""
        from app.harnesses.contract_review_docx import _generate_docx_post_execute
        captured_writes: dict[str, str] = {}
        ws = MagicMock()
        ws.read_file = AsyncMock(return_value={"content": json.dumps({
            "overall_risk": "RED",
            "recommendation": "Negotiate the liability cap upward before signing.",
            "key_findings": ["Liability cap too low"],
            "risk_breakdown": {"GREEN": 1, "YELLOW": 0, "RED": 1},
            "next_steps": ["Apply redline 1"],
        })})
        async def _wt(thread_id, file_path, content, source="agent"):
            captured_writes[file_path] = content
            return {"ok": True}
        ws.write_text_file = AsyncMock(side_effect=_wt)
        ws.write_binary_file = AsyncMock(return_value={"ok": True})
        ws.get_signed_url = AsyncMock(return_value="https://example.com/signed")

        with patch("app.services.sandbox_service.get_sandbox_service") as gs:
            gs.return_value.execute = AsyncMock(return_value={
                "exit_code": 0, "files": [{"filename": "contract-review.docx",
                                            "signed_url": "https://x.example/abc.docx"}],
            })
            with patch("httpx.AsyncClient") as hc_cls:
                hc_cls.return_value.__aenter__.return_value.get = AsyncMock(
                    return_value=MagicMock(content=b"docx", raise_for_status=lambda: None)
                )
                await _generate_docx_post_execute(
                    harness_run_id="r", thread_id="thr", user_id="u",
                    user_email="e@x", token="tok", phase_results={}, workspace=ws,
                )

        assert "contract-review-report.md" in captured_writes, "REVIEW #6: report.md must be written"
        report_md = captured_writes["contract-review-report.md"]
        assert report_md.lstrip().startswith("# Contract Review Report"), (
            "REVIEW #6: report must start with markdown header, NOT JSON"
        )
        assert not report_md.lstrip().startswith("{"), "Report must NOT be raw JSON"
    ```
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pytest tests/harnesses/test_contract_review_docx.py -v --tb=short</automated>
  </verify>
  <acceptance_criteria>
    - `pytest backend/tests/harnesses/test_contract_review_docx.py -v` exits 0 with ~15 tests
    - `grep -c "REVIEW #6\|REVIEW #7" backend/tests/harnesses/test_contract_review_docx.py` returns `>= 2`
    - `grep -c "wrote_binary" backend/tests/harnesses/test_contract_review_docx.py` returns `>= 1`
    - `grep -c "# Contract Review Report" backend/tests/harnesses/test_contract_review_docx.py` returns `>= 1`
    - `grep -c "DOCX_FAILED\|fallback_message" backend/tests/harnesses/test_contract_review_docx.py` returns `>= 2`
  </acceptance_criteria>
  <done>15 tests pass, REVIEW #6 + #7 anti-regression locked in.</done>
</task>

</tasks>

<truths>
- D-22-12 (programmatic generation, no template) — script as string, runs in sandbox.
- D-22-13 (pastel risk colors) — three exact hex codes.
- D-22-14 (filename pattern, source='harness', no auto-download).
- D-22-15 (non-fatal fallback) — error dict + fallback_message; harness_runs.status stays `completed`.
- REVIEW #6 closed: CR-08 LLM_SINGLE writes executive-summary.json (JSON); _render_summary_markdown produces contract-review-report.md as actual markdown.
- REVIEW #7 closed: post_execute returns wrote_binary=True + size_bytes; plan 22-03's engine wrapper emits workspace_updated downstream.
- ISSUE-05 PIN: SandboxService.execute() — NO files= kwarg, NO timeout_seconds= kwarg.
- CR-21-01 circular-import guard via _docx_post_execute_shim lazy import.
- CR-08 lives at phases[8] in 9-phase definition (filter at phases[6] shifts CR-07 to phases[7], CR-08 to phases[8]).
</truths>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Workspace artifact files → sandbox script | Files contain real PII; sandbox isolated |
| Sandbox auto-collected files → backend HTTP GET | Signed URL fetch bounded by httpx 60s timeout |
| DOCX bytes → workspace write_binary_file | RLS enforces thread-ownership |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-22-10-01 | Information Disclosure | DOCX file path traversal | mitigate | Filename `contract-review-{8-char-hex}.docx` is safe |
| T-22-10-02 | Tampering | INPUT_DATA literal escape via injected JSON | mitigate | json.dumps inputs; sandbox isolation |
| T-22-10-03 | DoS | Pathological input causing huge DOCX | mitigate | Sandbox config-level timeout; redline cell text capped |
| T-22-10-04 | Information Disclosure | DOCX containing PII reaching cloud LLM | n/a | post_execute makes NO LLM calls; deterministic serialization only |
| T-22-10-05 | Repudiation | DOCX generation untraceable | mitigate | audit_service.log_action for both generated + failed paths |
</threat_model>

<verification>
1. `pytest backend/tests/harnesses/test_contract_review_docx.py -v` exits 0
2. `pytest backend/tests/harnesses/ backend/tests/services/test_harness_engine_post_execute.py -v` exits 0
3. `python -c "from app.main import app; print('OK')"` prints `OK`
4. `python -c "from app.harnesses.contract_review import CONTRACT_REVIEW; assert CONTRACT_REVIEW.phases[8].workspace_output == 'executive-summary.json' and CONTRACT_REVIEW.phases[8].post_execute is not None; print('OK')"` prints `OK`
</verification>

<success_criteria>
- CR-08 LLM_SINGLE writes executive-summary.json (REVIEW #6: JSON, not pretending to be markdown)
- _render_summary_markdown produces real markdown contract-review-report.md
- post_execute generates polished .docx with all 7 sections
- post_execute returns wrote_binary=True (REVIEW #7) so engine emits workspace_updated
- D-22-15 fallback path tested
- PINNED SandboxService.execute() API used exclusively
- Off-mode invariant: when contract_review_enabled=False, harness not registered, post_execute callable is dead code
</success_criteria>

<output>
After completion, create `.planning/phases/22-contract-review-harness-docx-deliverable/22-10-SUMMARY.md`.
</output>
