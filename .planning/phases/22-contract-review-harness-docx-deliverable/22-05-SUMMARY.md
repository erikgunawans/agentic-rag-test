---
phase: 22
plan: "05"
subsystem: gatekeeper-eval
tags: [gatekeeper, eval, testing, pii, cr-21-08, d-22-04]
dependency_graph:
  requires:
    - 22-04 (workspace-aware gatekeeper system prompt + few-shots)
  provides:
    - gatekeeper_eval_set.json (15-phrasing corpus, D-22-04)
    - test_gatekeeper_eval.py (mocked-LLM CI parametrized pytest, GATE-01)
    - eval_gatekeeper_live.py (manual live-LLM check script, GATE-04)
  affects:
    - backend/tests/data/gatekeeper_eval_set.json
    - backend/tests/services/test_gatekeeper_eval.py
    - backend/scripts/eval_gatekeeper_live.py
tech_stack:
  added: []
  patterns:
    - pytest.mark.parametrize over JSON corpus (ids=[p["id"] for p in PHRASINGS])
    - Mocked LLM streaming via async iterator yielding TRIGGER_HARNESS conditionally
    - WorkspaceService.list_files stubbed per phrasing fixture
    - httpx.AsyncClient with SSE line-by-line parsing for live check
    - Synthetic minimal DOCX/PDF bytes for live upload stubs
key_files:
  created:
    - backend/tests/data/gatekeeper_eval_set.json
    - backend/tests/services/test_gatekeeper_eval.py
    - backend/scripts/eval_gatekeeper_live.py
decisions:
  - D-22-04: 15-phrasing eval set with 5/5/5 split (trigger/smoke-trigger/no-trigger)
  - mocked-LLM tests verify STRUCTURE not LLM intelligence (live script handles intelligence)
  - live script uses synthetic stub bytes; eval set size_bytes are LLM-prompt features only
  - token never logged in live script (T-22-05-01 mitigated)
metrics:
  duration_minutes: 8
  completed_date: "2026-05-05"
  tasks_completed: 3
  files_modified: 3
---

# Phase 22 Plan 05: Gatekeeper Eval Set Summary

15-phrasing JSON eval corpus + mocked-LLM parametrized pytest (CI) + standalone live-LLM check script, guarding CR-21-08 trigger reliability for both Contract Review and Smoke Echo harnesses.

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| 1 | Author 15-phrasing gatekeeper_eval_set.json (5/5/5 split) | 0069df8 |
| 2 | Parametrized pytest test_gatekeeper_eval.py (mocked LLM, 15 tests) | 33619c0 |
| 3 | Live-LLM eval_gatekeeper_live.py manual check script | 18e156e |

## What Was Built

**`backend/tests/data/gatekeeper_eval_set.json`:**

- Top-level: `version`, `phase`, `decision_id`, `harnesses` metadata, `phrasings` array
- 5 contract-review trigger phrasings (DOCX/PDF in workspace, including Indonesian cr-trigger-05)
- 5 smoke-echo trigger phrasings (Phase 21 regression guard for engine reliability)
- 5 should-not-trigger phrasings: empty workspace, off-topic, greeting in Indonesian with file (none-04)
- Each entry: `id`, `text`, `harness`, `workspace`, `expected_triggered`, `rationale`

**`backend/tests/services/test_gatekeeper_eval.py`:**

- Single parametrized test: `test_gatekeeper_trigger_matches_expected`
- Parametrize ids: `[cr-trigger-01]`, `[smoke-trigger-03]`, `[none-04]`, etc.
- Mock strategy: `OpenRouterService.client.chat.completions.create` returns async iterator yielding `[TRIGGER_HARNESS]` only if `expected_triggered=True`
- `WorkspaceService` patched to return `phrasing["workspace"]` verbatim
- Structural assertions: `triggered==expected`, display_name in system prompt, workspace block format correct
- 15/15 pass in CI without any real LLM calls

**`backend/scripts/eval_gatekeeper_live.py`:**

- argparse CLI: `--base-url`, `--token` (required), `--limit`
- Per-phrasing: creates fresh thread, uploads synthetic DOCX/PDF stub bytes, sends chat via SSE, parses `gatekeeper_complete.triggered`
- TTY-aware color output: green `[PASS]` / red `[FAIL]`
- Final summary line: `PASS: 13/15 (86.7%)  FAIL_IDS: cr-trigger-03, none-04`
- Exit code 0 = all pass, 1 = any fail (CI-pluggable)
- Token never echoed to output (T-22-05-01)

## Test Results

`pytest backend/tests/services/test_gatekeeper_eval.py -v` (run from main backend dir) -> **15 passed**, 0 failed

## Deviations from Plan

None -- plan executed exactly as written.

The TDD cycle note: tests were written first and pass immediately because the 22-04 implementation already has the correct structure. The RED artifact is the eval set JSON (Task 1, which didn't exist before), not a separate failing test commit.

## Known Stubs

None. The eval set JSON contains real phrasings with deterministic expected outcomes. The live script uses synthetic file bytes (minimal ZIP header for DOCX, minimal PDF for PDF) which are sufficient for workspace upload -- the actual content is not inspected by the gatekeeper LLM, only the filename and size shown in the workspace block prompt.

## Threat Flags

None new. Threat model from plan fully mitigated:
- T-22-05-01 (JWT logging): token passed via argv only, never included in any log/print output
- T-22-05-02 (eval set drift): JSON committed to git; changes visible in PR diffs

## Self-Check: PASSED

- `backend/tests/data/gatekeeper_eval_set.json`: FOUND
- `backend/tests/services/test_gatekeeper_eval.py`: FOUND
- `backend/scripts/eval_gatekeeper_live.py`: FOUND
- commit 0069df8 (eval set JSON): FOUND
- commit 33619c0 (pytest suite): FOUND
- commit 18e156e (live script): FOUND
- 15/15 parametrized tests pass
- `grep -c "EVAL_SET_PATH" test_gatekeeper_eval.py` = 2
- `grep -c "expected_triggered" test_gatekeeper_eval.py` = 7
- `grep -c "gatekeeper_eval_set.json" eval_gatekeeper_live.py` = 2
- `--help` exits 0 from worktree backend directory
