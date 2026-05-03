---
phase: 20-harness-engine-core-gatekeeper-post-harness-file-upload-lock
plan: "07"
subsystem: harness-engine
tags: [harness, smoke-test, programmatic-phase, llm-single, pydantic, feature-flag]
dependency_graph:
  requires: [20-03]   # HarnessDefinition types, HarnessRegistry
  provides: [smoke-echo harness registered in harness_registry when HARNESS_SMOKE_ENABLED=True]
  affects: [20-04, 20-11]  # gatekeeper resolves smoke-echo; E2E cross-cut tests run against it
tech_stack:
  added: []
  patterns: [HarnessDefinition with 2 PhaseDefinitions, EchoSummary Pydantic schema for LLM_SINGLE output validation, feature-flag-gated register() at module scope]
key_files:
  created:
    - backend/app/harnesses/smoke_echo.py
    - backend/tests/harnesses/__init__.py
    - backend/tests/harnesses/test_smoke_echo.py
  modified: []
decisions:
  - "EchoSummary Pydantic schema (echo_count: int, summary: str) kept minimal — exactly matches D-16 spec for a 2-field diagnostic output"
  - "Phase 1 executor filters workspace files by source=='upload' only — sandbox and workspace-generated files excluded from smoke echo"
  - "Registration gated at module scope (if get_settings().harness_smoke_enabled) matching the __init__.py auto-import pattern"
metrics:
  duration: "~3 minutes"
  completed: "2026-05-03T16:38:15Z"
  tasks_completed: 1
  tasks_total: 1
  files_created: 3
  files_modified: 0
---

# Phase 20 Plan 07: Smoke Echo Harness Summary

**One-liner:** 2-phase smoke-echo harness (programmatic metadata-echo + LLM_SINGLE Pydantic-validated summary) gated on HARNESS_SMOKE_ENABLED, providing an E2E exerciser for the harness engine before Phase 22 Contract Review lands.

## What Was Built

### `backend/app/harnesses/smoke_echo.py`

**EchoSummary Pydantic schema** (Phase 2 output):
```python
class EchoSummary(BaseModel):
    echo_count: int = Field(..., ge=0)
    summary: str = Field(..., min_length=1, max_length=2000)
```

**SMOKE_ECHO HarnessDefinition** shape:
- `name="smoke-echo"`, `display_name="Smoke Echo"`
- `prerequisites`: `requires_upload=True`, accepted_mime_types = `[application/pdf, application/vnd.openxmlformats-officedocument.wordprocessingml.document]`, `min_files=1`, `max_files=1`
- **Phase 0 ("echo")**: `PhaseType.PROGRAMMATIC`, `workspace_output="echo.md"`, `timeout_seconds=60`, executor=`_phase1_echo`
- **Phase 1 ("summarize")**: `PhaseType.LLM_SINGLE`, `workspace_inputs=["echo.md"]`, `workspace_output="summary.json"`, `output_schema=EchoSummary`, `timeout_seconds=120`

**`_phase1_echo` executor behavior**:
1. Calls `WorkspaceService(token=token).list_files(thread_id)`
2. Filters for `source == "upload"` entries only
3. Builds markdown content with total count + per-file metadata lines
4. Returns `{content: str, echo_count: int, files: list}` — engine writes `content` to `echo.md` via `PhaseDefinition.workspace_output`
5. On `WorkspaceService` failure: returns `{error: "list_files_failed", code: "WS_LIST_ERROR", detail: str(exc)[:500]}`

**Gated registration** at module scope:
```python
if get_settings().harness_smoke_enabled:
    register(SMOKE_ECHO)
```

### `backend/tests/harnesses/test_smoke_echo.py`

10 tests across 3 test classes:

| # | Test | Verifies |
|---|------|---------|
| 1 | `test_smoke_echo_definition_shape` | name, display_name, 2 phases |
| 2 | `test_smoke_echo_prerequisites_require_upload` | requires_upload=True, both MIME types |
| 3 | `test_smoke_echo_phase1_phase_type_is_programmatic` | phases[0].phase_type == PROGRAMMATIC |
| 4 | `test_smoke_echo_phase2_phase_type_is_llm_single` | phases[1].phase_type == LLM_SINGLE |
| 5 | `test_smoke_echo_phase2_has_pydantic_output_schema` | output_schema is EchoSummary |
| 6 | `test_smoke_echo_phase1_executor_writes_metadata` | 2 uploads → echo_count==2, content has both paths |
| 7 | `test_smoke_echo_phase1_executor_handles_no_uploads` | empty list → echo_count==0, placeholder text |
| 8 | `test_smoke_echo_phase1_executor_returns_error_on_ws_failure` | raises → error/code/detail dict |
| 9 | `test_smoke_echo_registers_when_smoke_flag_true` | monkeypatch True → registry has 'smoke-echo' |
| 10 | `test_smoke_echo_does_not_register_when_smoke_flag_false` | monkeypatch False → registry empty |

**All 10 tests pass** (`pytest tests/harnesses/test_smoke_echo.py -v` → `10 passed`).

## Deviations from Plan

None — plan executed exactly as written.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. The smoke harness module is a pure definition + in-process registration; all I/O goes through existing `WorkspaceService` and `harness_registry` (both already threat-modeled). The only surface from the plan's threat register:

| Flag | Component | Disposition |
|------|-----------|-------------|
| T-20-07-02 | Registration gating | Mitigated — `HARNESS_SMOKE_ENABLED=False` default enforced at module load; production stays smoke-free unless operator explicitly sets env var |

## Known Stubs

None — the harness module is fully wired. Phase 2 (LLM_SINGLE) will only execute when the harness engine dispatches it (Plan 20-03); the `output_schema=EchoSummary` is structurally complete for engine consumption.

## Commits

| Task | Commit | Files |
|------|--------|-------|
| 1: smoke_echo harness + tests | `17a281e` | `backend/app/harnesses/smoke_echo.py`, `backend/tests/harnesses/__init__.py`, `backend/tests/harnesses/test_smoke_echo.py` |

## Self-Check: PASSED

- `backend/app/harnesses/smoke_echo.py` — EXISTS
- `backend/tests/harnesses/test_smoke_echo.py` — EXISTS
- Commit `17a281e` — EXISTS in git log
- 10 tests pass — VERIFIED
