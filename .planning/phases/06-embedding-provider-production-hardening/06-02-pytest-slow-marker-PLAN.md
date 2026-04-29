---
plan_id: "06-02"
title: "Establish @pytest.mark.slow marker registration via backend/pyproject.toml"
phase: "06-embedding-provider-production-hardening"
plan: 2
type: execute
wave: 1
depends_on: []
autonomous: true
files_modified:
  - backend/pyproject.toml
requirements: [PERF-02]
must_haves:
  truths:
    - "`pytest --markers` lists `slow` as a registered marker (no PytestUnknownMarkWarning)"
    - "Default `pytest tests/unit -v` still discovers and runs all 195+ existing unit tests unchanged (slow marker is opt-in only)"
    - "The phrase `pytest -m 'not slow'` is documented as the default-CI invocation"
    - "Off-mode invariant preserved (this plan touches no production code)"
  artifacts:
    - path: "backend/pyproject.toml"
      provides: "[tool.pytest.ini_options] block with markers list including slow"
      contains: "slow:"
  key_links:
    - from: "backend/tests/services/redaction/test_perf_latency.py (Plan 06-08)"
      to: "@pytest.mark.slow decorator"
      via: "pytest marker resolution"
      pattern: "@pytest\\.mark\\.slow"
---

<objective>
Register the `slow` pytest marker in `backend/pyproject.toml` so Plan 06-08's PERF-02 latency regression test can be opt-in via `@pytest.mark.slow`.

Purpose: Per D-P6-07, the PERF-02 regression test is too expensive (real Presidio NER warm-up + 2000-token call + double assertion) for the default CI run. The `slow` marker excludes it from `pytest -m 'not slow'`. Without an `[tool.pytest.ini_options]` markers entry, pytest emits `PytestUnknownMarkWarning` on every collection and the marker has no canonical home.

Output: `backend/pyproject.toml` containing the `[tool.pytest.ini_options]` block with `markers = ["slow: marks tests as slow (deselect with '-m \"not slow\"')"]`.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/06-embedding-provider-production-hardening/06-CONTEXT.md
@CLAUDE.md

<interfaces>
<!-- Note: backend/ does NOT currently have a pyproject.toml or pytest.ini.
     This plan creates pyproject.toml with the minimum needed: a [tool.pytest.ini_options]
     block. We do NOT introduce build-system or project metadata (poetry/setuptools
     config) — the project still installs via requirements.txt. -->

```toml
# backend/pyproject.toml — minimal pytest config only
[tool.pytest.ini_options]
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
]
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create backend/pyproject.toml with [tool.pytest.ini_options] markers list</name>
  <read_first>
    - .planning/phases/06-embedding-provider-production-hardening/06-CONTEXT.md (D-P6-07 verbatim — slow marker established here, default CI uses `-m 'not slow'`)
    - CLAUDE.md (Code Quality and Testing sections — verify pytest invocation patterns; existing test suite uses `pytest tests/api/ -v --tb=short` without markers)
    - backend/ directory structure (`ls backend/` — confirm no pyproject.toml exists yet so we are CREATING, not editing)
    - backend/tests/conftest.py (verify it does not already register markers; line-count and content)
  </read_first>
  <files>backend/pyproject.toml</files>
  <action>
Create a new file at `backend/pyproject.toml` containing exactly this content:

```toml
# Pytest config only — the project still installs via requirements.txt.
# This file exists solely so `@pytest.mark.slow` is a registered marker (PERF-02 latency test).
# Phase 6 (Plan 06-02). Default CI uses `pytest -m 'not slow'`.
[tool.pytest.ini_options]
markers = [
    "slow: marks tests as slow / not run by default (deselect with '-m \"not slow\"')",
]
```

Do NOT add `[build-system]`, `[project]`, `[tool.poetry]`, or any other section — the project is installed from `requirements.txt` and adding metadata sections risks breaking Railway's Dockerfile-driven install. ONLY the `[tool.pytest.ini_options]` block is in scope.

Do NOT modify `backend/tests/conftest.py` — markers should come from the project-config file, not a per-test-tree conftest.
  </action>
  <verify>
    <automated>cd backend &amp;&amp; source venv/bin/activate &amp;&amp; pytest --markers 2>&amp;1 | grep -E "^@pytest\.mark\.slow:" | head -1</automated>
  </verify>
  <acceptance_criteria>
    - File `backend/pyproject.toml` exists (`test -f backend/pyproject.toml &amp;&amp; echo OK` prints `OK`)
    - `grep -n "tool.pytest.ini_options" backend/pyproject.toml` returns exactly 1 match
    - `grep -n '"slow:' backend/pyproject.toml` returns exactly 1 match
    - `grep -nE "build-system|^\[project\]|tool\.poetry" backend/pyproject.toml` returns 0 matches (we did NOT add unrelated metadata)
    - `cd backend &amp;&amp; source venv/bin/activate &amp;&amp; pytest --markers 2>&amp;1 | grep -E "^@pytest\.mark\.slow:"` returns exactly 1 match
    - `cd backend &amp;&amp; source venv/bin/activate &amp;&amp; pytest tests/unit -v --tb=short -q 2>&amp;1 | tail -3` shows the same passing-test count as pre-plan (the marker registration is opt-in only; existing suite unchanged)
  </acceptance_criteria>
  <done>`backend/pyproject.toml` exists with only the pytest markers block; `pytest --markers` shows `slow` as a registered marker; existing unit tests unaffected.</done>
</task>

</tasks>

<verification>
1. `cd backend && source venv/bin/activate && pytest --markers 2>&1 | grep "^@pytest.mark.slow:"` — confirms registration.
2. `cd backend && source venv/bin/activate && pytest tests/unit -m 'not slow' -v --tb=short -q 2>&1 | tail -5` — default CI invocation works (still passes the 195+ existing tests; nothing currently uses `slow` marker so no exclusions yet — Plan 06-08 introduces the first slow test).
3. `cd backend && python -c "from app.main import app; print('OK')"` — backend import-check unbroken (no app code modified).
</verification>

<success_criteria>
- `pyproject.toml` created at `backend/pyproject.toml` with only the markers block
- `pytest --markers` lists `slow`
- No new pytest warnings on any existing test collection
- No production code touched (off-mode invariant trivially preserved)
</success_criteria>

<output>
After completion, create `.planning/phases/06-embedding-provider-production-hardening/06-02-SUMMARY.md` documenting:
- The exact `pyproject.toml` content created (verbatim)
- Output of `pytest --markers | head -20`
- Confirmation that `pytest tests/unit -m 'not slow' -v` exit code = 0
</output>
