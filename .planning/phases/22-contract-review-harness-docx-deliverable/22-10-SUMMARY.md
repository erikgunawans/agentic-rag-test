---
phase: 22-contract-review-harness-docx-deliverable
plan: 10
subsystem: harnesses
tags: [cr-08, executive-summary, docx, post-execute, review-6, review-7, tdd]
dependency_graph:
  requires: [22-01, 22-03, 22-09]
  provides: [ExecutiveSummary, _render_summary_markdown, contract_review_docx, _generate_docx_post_execute]
  affects: [harness_engine, workspace_service, contract_review_harness]
tech_stack:
  added: [python-docx (sandbox), httpx (signed URL fetch)]
  patterns: [TDD RED/GREEN, lazy circular-import shim, D-22-15 non-fatal fallback, ISSUE-05 pinned sandbox API]
key_files:
  created:
    - backend/app/harnesses/contract_review_docx.py
    - backend/tests/harnesses/test_contract_review_docx.py
  modified:
    - backend/app/harnesses/contract_review.py
decisions:
  - "REVIEW #6: CR-08 writes executive-summary.json (raw JSON via LLM_SINGLE); _render_summary_markdown produces the actual markdown report — avoids raw JSON in a .md file"
  - "REVIEW #7: post_execute returns wrote_binary=True + size_bytes to trigger workspace_updated SSE event in plan 22-03 engine"
  - "D-22-15: post_execute never raises — error dict + fallback_message returned; harness_runs.status stays completed"
  - "ISSUE-05 PIN: SandboxService.execute(*, code, thread_id, user_id, token) — no files= kwarg, no timeout_seconds= kwarg"
  - "_docx_post_execute_shim lazy import preserves CR-21-01 circular-import guard"
  - "DOCX_GENERATION_SCRIPT_BODY runs inside sandbox Docker container with python-docx 1.1.2 (plan 22-01)"
metrics:
  duration: "~20 minutes"
  completed: "2026-05-05"
  tasks: 3
  files_created: 2
  files_modified: 1
---

# Phase 22 Plan 10: CR-08 Executive Summary + DOCX post_execute Summary

CR-08 LLM_SINGLE phase implemented with ExecutiveSummary Pydantic schema writing executive-summary.json (JSON), deterministic _render_summary_markdown rendering that into human-readable contract-review-report.md (REVIEW #6), and a sandbox-driven DOCX generation post_execute callback returning wrote_binary=True (REVIEW #7) for workspace_updated SSE re-emission.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Failing tests for CR-08 + DOCX post_execute | b9b9342 | backend/tests/harnesses/test_contract_review_docx.py |
| 2 (GREEN) | ExecutiveSummary schema + CR-08 phase + _render_summary_markdown + contract_review_docx.py | 10c4318 | backend/app/harnesses/contract_review.py, backend/app/harnesses/contract_review_docx.py |

## What Was Built

### backend/app/harnesses/contract_review.py

**ExecutiveSummary schema** (new, below Redline):
- `overall_risk: RiskGrade`
- `recommendation: str` (min 20, max 2000)
- `key_findings: list[str]` (min 1, max 10)
- `risk_breakdown: dict[str, int]`
- `next_steps: list[str]` (min 1, max 10)

**`_render_summary_markdown` helper** (new):
- REVIEW #6 invariant: produces markdown starting with `# Contract Review Report` — never raw JSON
- Sections: Contract metadata, Executive Summary, Risk Breakdown, Key Findings, Detailed Redline Analysis (table), Recommended Next Steps
- Writes to `contract-review-report.md` via `workspace.write_text_file()` (non-fatal if write fails)
- Returns the rendered markdown string for DOCX generation use

**`_docx_post_execute_shim`** (new):
- Lazy imports `_generate_docx_post_execute` from `contract_review_docx` at call time
- Preserves the CR-21-01 circular-import guard pattern

**CR-08 phase** (replaced stub):
- `workspace_output="executive-summary.json"` (REVIEW #6: JSON, not markdown)
- `output_schema=ExecutiveSummary`
- `post_execute=_docx_post_execute_shim`
- `system_prompt_template` references all 6 input files; includes D-22-07 unfounded-playbook conditional

### backend/app/harnesses/contract_review_docx.py (new module)

**`DOCX_GENERATION_SCRIPT_BODY`**: Python script that runs inside the sandbox Docker container:
- python-docx 1.1.2 (installed via plan 22-01 Dockerfile layer)
- Title page with `CONFIDENTIAL` in red (Pt 20, RGBColor CC0000)
- 7 sections: title page, executive summary, key findings, redline table with pastel color fills (E6F4EA/FEF7E0/FCE8E6 per D-22-13), GREEN clauses, next steps
- Writes to `/sandbox/output/contract-review.docx`

**`_generate_docx_post_execute`**:
1. Reads 6 workspace artifacts (classification.md, review-context.md, playbook-context.md, executive-summary.json, risk-analysis.json, redlines.json)
2. REVIEW #6: calls `_render_summary_markdown` → produces `contract-review-report.md` as real markdown
3. Calls `SandboxService.execute(code=..., thread_id=..., user_id=..., token=...)` (ISSUE-05 pinned API — no `files=`, no `timeout_seconds=`)
4. HTTP-GETs DOCX bytes from sandbox signed URL via httpx (60s timeout)
5. Calls `workspace.write_binary_file(thread_id=..., file_path=..., content_bytes=..., mime_type=..., user_id=..., source="harness")`
6. REVIEW #7: returns `{"ok": True, "docx_path": "contract-review-{run_id[:8]}.docx", "wrote_binary": True, "size_bytes": N}`
7. D-22-15: any exception caught → returns `{"error": ..., "code": "DOCX_FAILED", "fallback_message": ...}` — never raises
8. Audit logs `contract_review_docx_generated` on success, `contract_review_docx_failed` on failure

### backend/tests/harnesses/test_contract_review_docx.py (new)

24 tests — all passing:
- `TestExecutiveSummarySchema`: valid instance, empty key_findings rejection
- `TestCR08PhaseDefinition`: output_schema, workspace_output=executive-summary.json (REVIEW #6), 6 inputs, post_execute wired
- `TestRenderSummaryMarkdown`: 5 sections, writes report.md, starts with `# ` not `{` (REVIEW #6)
- `TestDocxGenerationScriptBody`: python-docx usage, hex codes, CONFIDENTIAL, ISSUE-05 PIN checks, no OpenRouter
- `test_post_execute_returns_wrote_binary_true_on_success` (REVIEW #7)
- `test_post_execute_reads_all_six_artifacts`
- `test_post_execute_calls_render_summary_markdown`
- `test_post_execute_writes_docx_to_workspace` (source='harness')
- `test_post_execute_returns_error_dict_on_sandbox_failure` (D-22-15)
- `test_post_execute_logs_audit_on_success_and_failure`
- `test_post_execute_writes_markdown_not_json_to_report_file` (REVIEW #6 anti-regression)
- `test_post_execute_writes_valid_docx_bytes_to_workspace` (PK magic bytes)
- `TestModuleAcceptanceCriteria`: CONFIDENTIAL + color codes, _render_summary_markdown called, wrote_binary, audit actions

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] DOCX_B64_BEGIN string appeared in module docstring**
- **Found during:** Test execution (test_pinned_api_no_forbidden_patterns FAILED)
- **Issue:** The module docstring mentioned "NO DOCX_B64_BEGIN" as a comment about forbidden patterns, which caused the test's `assert "DOCX_B64_BEGIN" not in source` to fail on the docstring text itself
- **Fix:** Rephrased the docstring comment to "NO base64 extraction patterns" — preserves intent without triggering the assert
- **Files modified:** `backend/app/harnesses/contract_review_docx.py`
- **Commit:** 10c4318 (within GREEN commit)

## Security / Threat Surface

No new endpoints or auth paths introduced. The post_execute callable:
- Makes no LLM calls (verified by test + source grep)
- Uses sandbox isolation for DOCX generation (T-22-10-02: JSON.dumps inputs)
- Caps redline cell text at 1500 chars in sandbox script (T-22-10-03 partial)
- Audit-logs both success and failure paths (T-22-10-05)
- File path uses `harness_run_id[:8]` hex prefix — no path traversal possible (T-22-10-01)

## Known Stubs

None. CR-08 is now fully implemented. The Contract Review harness has all 9 phases complete (CR-01..08 + filter). The harness is still gated behind `contract_review_enabled=False` per ISSUE-14 (deploy order: enable only after all plans 22-06..22-10 land in production).

## TDD Gate Compliance

- RED gate commit: `b9b9342` — `test(22-10): RED — 24 tests ...` (all 24 FAILED before implementation)
- GREEN gate commit: `10c4318` — `feat(22-10): GREEN — CR-08 ...` (all 24 PASSED)
- No REFACTOR gate needed — code was clean on first pass.

## Self-Check

Checking created files exist and commits are recorded.
