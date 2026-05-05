---
phase: 22
plan: "04"
subsystem: gatekeeper
tags: [gatekeeper, workspace, few-shots, pii, cr-21-08]
dependency_graph:
  requires:
    - 22-01 (workspace upload + harness type definitions)
    - 20-XX (gatekeeper engine core — WorkspaceService, HarnessDefinition types)
  provides:
    - workspace-aware gatekeeper system prompt (D-22-01)
    - intent-match few-shots with dynamic display_name (D-22-03)
    - graceful list_files error fallback (D-22-15)
  affects:
    - backend/app/services/gatekeeper.py
    - backend/tests/services/test_gatekeeper.py
tech_stack:
  added: []
  patterns:
    - WorkspaceService.list_files per-turn for ground-truth workspace state
    - try/except around WorkspaceService instantiation for graceful degradation
    - few-shots before workspace block for KV-cache friendliness
key_files:
  modified:
    - backend/app/services/gatekeeper.py
    - backend/tests/services/test_gatekeeper.py
decisions:
  - D-22-01: workspace-aware gatekeeper — root-cause fix for CR-21-08 trigger reliability
  - D-22-02: filename + size only (no content peek) — minimal token cost, no PII leak path
  - D-22-03: intent-match few-shots using harness.display_name — works for all future harnesses
  - D-22-15: graceful error handling — list_files failure falls back to empty list with WARNING log
  - impl: WorkspaceService instantiation inside try/except so invalid test tokens fall through gracefully
metrics:
  duration_minutes: 3
  completed_date: "2026-05-05"
  tasks_completed: 2
  files_modified: 2
---

# Phase 22 Plan 04: Gatekeeper Workspace Prompt Summary

Extended `build_system_prompt` with per-turn workspace block + intent-match few-shots to fix CR-21-08 gatekeeper trigger reliability, and `run_gatekeeper` now calls `WorkspaceService.list_files` per turn with graceful fallback.

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| 1 (RED) | Failing tests for workspace block + few-shots + list_files fallback (tests 13-17) | 4396b87 |
| 1+2 (GREEN) | Implement extended `build_system_prompt` + workspace-aware `run_gatekeeper` | 670bc89 |

## What Was Built

**`backend/app/services/gatekeeper.py`:**

- `build_system_prompt` signature extended: `workspace_files: list[dict] | None = None`
- Non-empty workspace: formats `Workspace: filename (X KB), ...` block per turn
- Empty/None workspace: `Workspace: (empty -- user has not uploaded yet)`
- Intent-match few-shots with `harness.display_name` interpolation (5 examples)
- Few-shots placed BEFORE workspace block for KV-cache stability
- `WorkspaceService` imported at module level; instantiation + `list_files` call wrapped in try/except — invalid tokens fall through to empty list with WARNING log
- All pre-existing guidance/sentinel/egress logic unchanged

**`backend/tests/services/test_gatekeeper.py`:**

- Header updated: 17 tests (was 11)
- 5 new tests added (tests 13-17):
  - 13: `test_build_system_prompt_empty_workspace_block`
  - 14: `test_build_system_prompt_non_empty_workspace_lists_filenames_and_sizes`
  - 15: `test_build_system_prompt_few_shot_uses_display_name`
  - 16: `test_build_system_prompt_few_shots_before_workspace_block_for_kv_cache`
  - 17: `test_run_gatekeeper_list_files_failure_falls_back_to_empty_workspace`

## Test Results

`pytest backend/tests/services/test_gatekeeper.py -v` → **17 passed**, 0 failed, 1 warning (gotrue deprecation, unrelated)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] WorkspaceService instantiation inside try/except for test compatibility**

- **Found during:** GREEN phase — 9 of 12 existing tests failed after adding the `WorkspaceService(token=token)` call
- **Issue:** Existing tests pass a fake token `"tok"` which triggers a Supabase `set_session` error inside `WorkspaceService.__init__`, before any mock context is applied. The plan's patch placed `ws = WorkspaceService(token=token)` before the try/except, meaning instantiation errors were not caught.
- **Fix:** Moved `ws = WorkspaceService(token=token)` inside the try/except block so both instantiation failures and `list_files` failures fall through to the empty-list fallback. This also satisfies D-22-15 more completely (any failure path gracefully degrades).
- **Files modified:** `backend/app/services/gatekeeper.py`
- **Commit:** 670bc89

### Notes

- The plan specified `grep -c "Workspace: "` should return `>= 2`. We got exactly 2 (one in the non-empty branch, one in the empty branch). Acceptance criteria met.
- `grep -c "list_files"` returns 3 (import comment `list_files`, method call `ws.list_files`, warning log message). Plan required `>= 1`. Met.
- The plan mentioned checking for circular imports before using a top-level import. Checked: `workspace_service.py` has no imports from `gatekeeper.py`. Top-level import is safe.

## Known Stubs

None. All workspace block content is dynamically built from real `list_files` data.

## Threat Flags

None new. The plan's threat model already covered:
- T-22-04-01: PII in filenames — existing egress filter at gatekeeper.py:~230 covers this
- T-22-04-02: Malicious filename as trigger — accepted, worst case is benign false trigger
- T-22-04-03: list_files DB call DoS — mitigated by try/except fallback

## ISSUE-12 Operational Gate

Per plan success_criteria: before merging to master, run `python -m scripts.eval_gatekeeper_live --base-url http://localhost:8000 --token $JWT` (Plan 22-05 deliverable) and confirm ≥14/15 phrasings pass. This is a NECESSARY but NOT SUFFICIENT CI gate — gpt-4o-mini real-world behavior may diverge from mocked stubs. **Score not yet available** — pending Plan 22-05 execution.

## Self-Check: PASSED

- `backend/app/services/gatekeeper.py`: FOUND
- `backend/tests/services/test_gatekeeper.py`: FOUND
- commit 4396b87 (RED): FOUND
- commit 670bc89 (GREEN): FOUND
- `grep -c "workspace_files: list\[dict\] | None = None" backend/app/services/gatekeeper.py` → 1
- `grep -c "EXAMPLES (intent-match" backend/app/services/gatekeeper.py` → 1
- `pytest tests/services/test_gatekeeper.py` → 17 passed
