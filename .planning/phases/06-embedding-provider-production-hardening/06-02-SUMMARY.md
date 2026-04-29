---
plan_id: "06-02"
phase: "06-embedding-provider-production-hardening"
plan: 2
subsystem: "testing-infrastructure"
tags: ["pytest", "markers", "ci", "perf-02", "slow-tests"]
dependency_graph:
  requires: []
  provides: ["@pytest.mark.slow registration", "backend/pyproject.toml"]
  affects: ["backend/tests/services/redaction/test_perf_latency.py (Plan 06-08)"]
tech_stack:
  added: ["backend/pyproject.toml (pytest config)"]
  patterns: ["pyproject.toml [tool.pytest.ini_options] marker registration"]
key_files:
  created:
    - backend/pyproject.toml
  modified: []
decisions:
  - "D-P6-07: @pytest.mark.slow marker established here; default CI uses pytest -m 'not slow'"
  - "pyproject.toml contains only [tool.pytest.ini_options] — no [build-system], [project], or [tool.poetry] sections to avoid breaking Railway Dockerfile-driven install"
metrics:
  duration: "~3 minutes"
  completed: "2026-04-29"
  tasks_completed: 1
  tasks_total: 1
  files_changed: 1
---

# Phase 6 Plan 2: Establish @pytest.mark.slow Marker Registration via backend/pyproject.toml Summary

## One-Liner

Created `backend/pyproject.toml` with a minimal `[tool.pytest.ini_options]` markers block registering the `slow` marker so PERF-02's latency regression test (`Plan 06-08`) can be opt-in via `@pytest.mark.slow` without emitting `PytestUnknownMarkWarning`.

## What Was Built

A single-file change: `backend/pyproject.toml` containing exactly the `[tool.pytest.ini_options]` block required by D-P6-07. No production code was touched.

### Exact pyproject.toml Content Created

```toml
# Pytest config only — the project still installs via requirements.txt.
# This file exists solely so `@pytest.mark.slow` is a registered marker (PERF-02 latency test).
# Phase 6 (Plan 06-02). Default CI uses `pytest -m 'not slow'`.
[tool.pytest.ini_options]
markers = [
    "slow: marks tests as slow / not run by default (deselect with '-m \"not slow\"')",
]
```

### pytest --markers Output (first 4 entries)

```
@pytest.mark.slow: marks tests as slow / not run by default (deselect with '-m "not slow"')

@pytest.mark.anyio: mark the (coroutine function) test to be run asynchronously via anyio.

@pytest.mark.asyncio: mark the test as a coroutine, it will be run using an asyncio event loop
...
```

### Unit Test Suite Result

`pytest tests/unit -m 'not slow' -v --tb=short -q` exit code = 0:

```
256 passed, 557 warnings in 2.41s
```

All 256 existing tests pass unchanged. The slow marker is opt-in only — no tests currently use it (first slow test arrives in Plan 06-08).

## Decisions Made

- Created `backend/pyproject.toml` with ONLY `[tool.pytest.ini_options]` — no `[build-system]`, `[project]`, or `[tool.poetry]` sections to avoid any risk of breaking Railway's Dockerfile-driven `pip install -r requirements.txt` flow.
- Marker description follows the canonical format: `"slow: marks tests as slow / not run by default (deselect with '-m \"not slow\"')"` — matching the plan interface spec while adding the human-readable description of the default exclusion mechanism.
- Markers registered via `pyproject.toml` (not `conftest.py`) per pytest project-config best practice.

## Verification

1. `pytest --markers` lists `@pytest.mark.slow:` as the first entry — confirmed registered.
2. `pytest tests/unit -m 'not slow' -v --tb=short -q` — 256 passed, 0 failures, exit code 0.
3. `python -c "from app.main import app; print('OK')"` — backend imports clean (no production code modified).
4. `grep -nE "build-system|^\[project\]|tool\.poetry" backend/pyproject.toml` — exit 1 (no matches), confirming no unwanted metadata sections added.

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — this plan introduces no UI components or data paths; the marker registration is complete and functional.

## Threat Flags

None — this plan modifies no production code, no network endpoints, no auth paths, no schema. No new threat surface introduced.

## Self-Check

### Files Exist

- `backend/pyproject.toml` — FOUND

### Commits Exist

- `98fc89c` — chore(06-02): register @pytest.mark.slow marker in backend/pyproject.toml

## Self-Check: PASSED
