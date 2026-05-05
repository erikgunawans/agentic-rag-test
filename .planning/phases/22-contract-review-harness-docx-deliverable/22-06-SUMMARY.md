---
phase: 22-contract-review-harness-docx-deliverable
plan: "06"
subsystem: harness-contract-review
tags: [harness, contract-review, pii, docx, pdf, tdd, feature-flag, dark-launch]
dependency_graph:
  requires: ["22-01", "22-03"]
  provides: [contract-review-harness-skeleton, CR-01-intake, CR-02-classification, read_binary_file]
  affects: [harness_engine.py, harness_registry, plan-22-07-context, plan-22-08-clauses, plan-22-09-risk, plan-22-10-docx]
tech_stack:
  added:
    - httpx (already in venv; used for read_binary_file signed-URL download)
    - python-docx (pre-installed plan 22-01; used in CR-01 DOCX extraction)
    - PyPDF2 (pre-installed plan 22-01; used in CR-01 PDF extraction)
  patterns:
    - "TDD RED/GREEN for both WorkspaceService.read_binary_file and contract_review.py skeleton"
    - "D-16 dark-launch: contract_review_enabled=False (default) = byte-identical to pre-Phase-22"
    - "ISSUE-09 guard: RuntimeError at import if contract_review_enabled=True + tool_registry_enabled=False"
    - "ISSUE-14 deploy-order comment: all 5 plans (22-06..22-10) must land before enabling"
    - "CR-21-01 circular-import lesson: lazy imports inside executor functions + from __future__ import annotations"
    - "Stub fail-closed pattern: _phase_stub_not_implemented returns STUB error dict"
key_files:
  created:
    - backend/app/harnesses/contract_review.py
    - backend/tests/harnesses/test_contract_review_skeleton.py
    - backend/tests/services/test_workspace_read_binary.py
  modified:
    - backend/app/config.py
    - backend/app/services/workspace_service.py
decisions:
  - "read_binary_file delegates to read_file for path validation + DB lookup, then fetches bytes via httpx signed URL — no duplicate storage logic"
  - "CR-01 uses lazy import (from docx import Document inside function) to preserve CR-21-01 circular-import lesson"
  - "Stub phases use a single shared _phase_stub_not_implemented executor — fail-closed, STUB code, clear error message"
  - "ISSUE-09 raises RuntimeError at module import time (not registration time) so startup fails loudly before any request"
  - "ContractClassification min_length=2 on parties list enforces ROADMAP success criterion 5.1"
metrics:
  duration: "~6 minutes"
  completed_date: "2026-05-05"
  tasks_completed: 4
  files_modified: 5
---

# Phase 22 Plan 06: Contract Review Harness Skeleton (CR-01, CR-02) Summary

9-phase Contract Review HarnessDefinition with functional CR-01 DOCX/PDF text extraction + ContractClassification Pydantic schema, all 18 tests passing, gated behind dual feature flags.

## Completed Tasks

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 0 (RED) | Failing tests for WorkspaceService.read_binary_file | c92e7de | backend/tests/services/test_workspace_read_binary.py |
| 0 (GREEN) | Implement WorkspaceService.read_binary_file | 7005337 | backend/app/services/workspace_service.py |
| 1 | Add contract_review_enabled feature flag | 7c599e5 | backend/app/config.py |
| 2+3 (RED) | Failing skeleton tests (14 tests) | 867f1aa | backend/tests/harnesses/test_contract_review_skeleton.py |
| 2+3 (GREEN) | Implement contract_review.py skeleton | 5f6a2ca | backend/app/harnesses/contract_review.py |

## What Was Built

### WorkspaceService.read_binary_file (ISSUE-02)

New async method added to `backend/app/services/workspace_service.py` after `read_file`:

- Delegates to `read_file` for path validation + DB lookup
- Rejects text rows with `not_a_binary_file` error dict
- Downloads binary content via `httpx.AsyncClient.get(signed_url)` with 30s timeout
- Returns `bytes` on success or structured error dict on failure — never raises

4 tests cover: happy-path round-trip, missing file, text row, invalid path.

### contract_review_enabled Feature Flag (config.py)

Added after `harness_smoke_enabled` with matching comment block:

```python
# Phase 22 / v1.3 (CR-*, DOCX-*; D-16): Contract Review harness flag.
contract_review_enabled: bool = False
```

Default `False` — D-16 dark-launch invariant. Mirrors `harness_smoke_enabled` pattern.

### Contract Review HarnessDefinition (contract_review.py)

9-phase scaffold (8 user-visible CR-XX + 1 programmatic filter):

| # | Phase name | Type | Status |
|---|-----------|------|--------|
| 1 | intake | PROGRAMMATIC | Functional (CR-01) |
| 2 | classify | LLM_SINGLE | Functional (CR-02 schema) |
| 3 | gather-context | LLM_HUMAN_INPUT | Stub (plan 22-07) |
| 4 | load-playbook | LLM_AGENT | Stub (plan 22-07) |
| 5 | extract-clauses | PROGRAMMATIC | Stub (plan 22-08) |
| 6 | risk-analysis | LLM_BATCH_AGENTS | Stub (plan 22-09) |
| 7 | filter-redline-candidates | PROGRAMMATIC | Stub (plan 22-09) |
| 8 | redline-generation | LLM_BATCH_AGENTS | Stub (plan 22-09) |
| 9 | executive-summary | LLM_SINGLE | Stub (plan 22-10) |

**CR-01 executor** (`_phase1_intake`): reads upload via `ws.read_binary_file`, extracts text using `python-docx` for DOCX or `PyPDF2` for PDF (lazy imports), writes markdown to `contract-text.md`. Returns `{"content": ..., "page_count": N, "char_count": M, "source_file": path}`.

**CR-02 schema** (`ContractClassification`): enforces `parties` min_length=2 (ROADMAP 5.1), `contract_type` min_length=1, `governing_law` + `jurisdiction` required, optional dates, 20-1000 char `summary`.

**Stub phases**: use `_phase_stub_not_implemented` which returns `{"error": "phase_not_implemented", "code": "STUB", ...}` — fails closed so partial completion is detectable.

**ISSUE-09 guard**: If `contract_review_enabled=True` but `tool_registry_enabled=False`, raises `RuntimeError("ISSUE-09: ...")` at import time before registration.

**ISSUE-14 deploy-order**: Documented in module docstring — flag must stay False until all 5 plans (22-06..22-10) land.

### Test Coverage

18 tests total (14 skeleton + 4 read_binary):
- Flag gating (4 parametrized cases covering all flag combinations)
- 9-phase shape + phase type/executor/schema assertions
- CR-01 happy path with synthetic DOCX (Acme Corp + Beta Inc paragraph)
- CR-01 no-upload error path
- ContractClassification: rejects empty list, rejects single party, accepts valid
- ISSUE-09: RuntimeError on tool_registry_enabled=False
- ISSUE-14: deploy-order constraint in source

## Deviations from Plan

None — plan executed exactly as written.

The `_reload_contract_review` test helper patches `app.config.get_settings` at module-level and uses `sys.modules.pop` for clean reimport, matching the smoke-echo test pattern. The test count ended at 14 (plan said 12; the parametrized flag-gating test with 3 params became 3 individual test cases + 1 both-true case = 4 flag tests vs. planned 2). All behaviors from the plan's behavior block are covered.

## Known Stubs

Intentional stubs (expected by design — subsequent plans populate them):

| File | Phase | Stub Type | Resolved In |
|------|-------|-----------|-------------|
| backend/app/harnesses/contract_review.py | gather-context (CR-03) | `system_prompt_template="STUB"` | Plan 22-07 |
| backend/app/harnesses/contract_review.py | load-playbook (CR-04) | `system_prompt_template="STUB"` | Plan 22-07 |
| backend/app/harnesses/contract_review.py | extract-clauses (CR-05) | `_phase_stub_not_implemented` executor | Plan 22-08 |
| backend/app/harnesses/contract_review.py | risk-analysis (CR-06) | `system_prompt_template="STUB"` | Plan 22-09 |
| backend/app/harnesses/contract_review.py | filter-redline-candidates | `_phase_stub_not_implemented` executor | Plan 22-09 |
| backend/app/harnesses/contract_review.py | redline-generation (CR-07) | `system_prompt_template="STUB"` | Plan 22-09 |
| backend/app/harnesses/contract_review.py | executive-summary (CR-08) | `system_prompt_template="STUB"`, `post_execute=None` | Plan 22-10 |

These stubs are intentional and required by the plan. Contract Review flag remains `False` until all stubs are resolved.

## Threat Surface

T-22-06 mitigations implemented as planned:
- T-22-06-02 (DoS zip-bomb): UPL-02 25 MB cap upstream + try/except on extraction
- T-22-06-03 (stack trace leak): `str(exc)[:500]` cap + `logger.error` (not user-facing)
- T-22-06-01 (PII in CR-02 payload): existing SEC-04 egress filter in harness_engine.py handles LLM_SINGLE dispatch

No new threat surface beyond the plan's threat model.

## Self-Check: PASSED

- FOUND: backend/app/harnesses/contract_review.py
- FOUND: backend/tests/harnesses/test_contract_review_skeleton.py
- FOUND: backend/tests/services/test_workspace_read_binary.py
- FOUND: backend/app/config.py (contract_review_enabled flag)
- FOUND: backend/app/services/workspace_service.py (read_binary_file method)
- FOUND commit: c92e7de (RED test for read_binary_file)
- FOUND commit: 7005337 (GREEN read_binary_file impl)
- FOUND commit: 7c599e5 (feature flag)
- FOUND commit: 867f1aa (RED skeleton tests)
- FOUND commit: 5f6a2ca (GREEN contract_review.py)
- `pytest tests/harnesses/test_contract_review_skeleton.py tests/services/test_workspace_read_binary.py` → 18 passed
- `python -c "from app.main import app; print('OK')"` → OK
- `python -c "from app.harnesses.contract_review import CONTRACT_REVIEW; print(len(CONTRACT_REVIEW.phases))"` → 9
