---
phase: 22-contract-review-harness-docx-deliverable
plan: 14
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/app/services/harness_engine.py
  - backend/tests/services/test_harness_engine_todos.py
autonomous: true
gap_closure: true
requirements: [CR-01, CR-02, CR-03, CR-04, CR-05, CR-06, CR-07, CR-08]
must_haves:
  truths:
    - "All 4 write_todos call sites in harness_engine.py pass (thread_id, user_id, user_email, token, todos) in this exact order"
    - "Phase state transitions (init/in_progress/completed/error) all succeed against the real write_todos signature"
    - "A regression test exists that fails on the broken signature and passes on the fix"
  artifacts:
    - path: "backend/app/services/harness_engine.py"
      provides: "Inner engine loop with correct write_todos call signature on all 4 call sites"
      contains: "write_todos(thread_id, user_id, user_email, token, todos)"
    - path: "backend/tests/services/test_harness_engine_todos.py"
      provides: "Regression test that asserts write_todos receives 5 positional args in correct order through a full phase transition cycle"
      contains: "test_write_todos_signature_propagation"
  key_links:
    - from: "harness_engine._run_harness_engine_inner"
      to: "agent_todos_service.write_todos"
      via: "5 positional args: thread_id, user_id, user_email, token, todos"
      pattern: "write_todos\\(thread_id, user_id, user_email, token, todos\\)"
---

<objective>
Close UAT Gap 2 (BLOCKER): all 4 `write_todos()` call sites in `harness_engine.py` pass 3 args in the WRONG order — `(thread_id, todos, token)` — but the actual signature requires 5 positional args: `(thread_id, user_id, user_email, token, todos)`. Python raises `TypeError: write_todos() missing 2 required positional arguments: 'token' and 'todos'`. The error handler ITSELF crashes with the same error, so harness failure is silent — Plan Panel renders 9 empty phases, no progression, no DOCX, /harness/active returns null.

Purpose: Fix all 4 call sites and add a regression test that uses a real (non-mocked-at-the-call-boundary) write_todos invocation so signature drift is caught in CI before merge. CLAUDE.md mandates "Every bug fix gets a regression test. Write the test first."
Output: harness_engine.py with 4 corrected call sites + a new regression test file.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/22-contract-review-harness-docx-deliverable/22-HUMAN-UAT.md
@CLAUDE.md
@backend/app/services/agent_todos_service.py
@backend/app/services/harness_engine.py
@backend/tests/services/test_harness_engine.py

<interfaces>
<!-- Authoritative source: backend/app/services/agent_todos_service.py:66-90 -->
Real write_todos signature (5 required positional args, ORDER MATTERS):
```python
async def write_todos(
    thread_id: str,
    user_id: str,
    user_email: str,
    token: str,
    todos: list[TodoInput],
) -> list[TodoRecord]:
```

<!-- Authoritative source: backend/app/services/harness_engine.py:182-187 -->
The inner engine function _run_harness_engine_inner ALREADY accepts user_id and user_email as keyword-only parameters:
```python
async def _run_harness_engine_inner(
    *,
    harness: HarnessDefinition,
    harness_run_id: str,
    thread_id: str,
    user_id: str,
    user_email: str,
    token: str,
    registry,
    cancellation_event: asyncio.Event,
    start_phase_index: int = 0,
) -> AsyncIterator[dict]:
```

<!-- Confirmed in code: 4 broken call sites in harness_engine.py -->
Current broken call sites (3 args in wrong order):
- Line 201 (init):       `await agent_todos_service.write_todos(thread_id, todos, token)`
- Line 289 (in_progress): `await agent_todos_service.write_todos(thread_id, todos, token)`
- Line 361 (error):       `await agent_todos_service.write_todos(thread_id, todos, token)`
- Line 428 (completed):   `await agent_todos_service.write_todos(thread_id, todos, token)`

NB: The Read tool returned the EXACT current source above; line numbers are 100% accurate as of HEAD.

<!-- Authoritative source: backend/tests/services/test_harness_engine.py:66-75 -->
Canonical pattern for registering a programmatic executor in tests — it is a
regular Pydantic field passed to PhaseDefinition's constructor (NOT a post-hoc
attribute assignment). Executor signature is `(inputs, token, thread_id, harness_run_id)`:
```python
def _make_programmatic_phase(name: str = "echo", timeout_seconds: int = 60) -> PhaseDefinition:
    async def _executor(inputs, token, thread_id, harness_run_id):
        return {"result": "ok", "text": "echo done"}

    return PhaseDefinition(
        name=name,
        phase_type=PhaseType.PROGRAMMATIC,
        executor=_executor,
        timeout_seconds=timeout_seconds,
    )
```

Existing test mocking pattern (test_harness_engine.py:83): patches the call boundary with AsyncMock, so signature drift is INVISIBLE to existing tests. The new regression test must NOT mock at the call boundary; it must invoke the real signature.
</interfaces>

<invariants>
- CLAUDE.md: "Every bug fix gets a regression test. Write the test first." — task ordering reflects this (Task 1 = test, Task 2 = fix).
- CLAUDE.md: "Tool Registry adapter-wrap invariant" — `head -n 1283 backend/app/services/tool_service.py | shasum -a 256` MUST still match `cb63cf3e60d5f6380e2e41f63b1fe9122f58ab4648808b0f2114e452cd45ddb2` after this plan. This plan does NOT touch tool_service.py.
- CLAUDE.md: PostToolUse hook auto-runs py_compile + import check on every .py edit; both files must import cleanly.
- D-22 (parent token): the `token` value is the parent JWT — never re-mint. This is preserved (we just reorder args).
- D-16 dark-launch byte-identical OFF-mode: write_todos is only invoked when the engine actually runs a harness, so OFF-mode (`harness_enabled=False` or `contract_review_enabled=False`) is unchanged.
</invariants>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Write regression test FIRST that asserts write_todos receives 5 args in correct order</name>
  <read_first>
    - backend/app/services/agent_todos_service.py (lines 66-90: real signature)
    - backend/app/services/harness_engine.py (lines 177-200, 280-292, 355-365, 415-431: the 4 call sites in context)
    - backend/tests/services/test_harness_engine.py (existing fixture style — _make_programmatic_phase at lines 66-75 is the canonical executor-registration pattern; do NOT copy the call-boundary AsyncMock for write_todos in this test)
  </read_first>
  <files>backend/tests/services/test_harness_engine_todos.py</files>
  <action>
Create a NEW test file `backend/tests/services/test_harness_engine_todos.py`. The test MUST capture the actual positional args passed to `write_todos` and assert they are in the correct order WITHOUT replacing write_todos with a no-op AsyncMock that hides signature drift.

Strategy: replace `agent_todos_service.write_todos` with a side-effect function that:
1. Accepts the EXACT same signature (`thread_id, user_id, user_email, token, todos`).
2. Records each call's positional args into a list.
3. Returns an empty list (the engine ignores the return value).

Then drive the inner engine through one programmatic phase that succeeds, so we hit at least 3 of the 4 call sites (init → in_progress → completed). Assert:
- write_todos was called >= 3 times.
- Every recorded call has `args[0]` == thread_id, `args[1]` == user_id, `args[2]` == user_email, `args[3]` == token, `args[4]` is a list of dicts each with keys `{content, status, position}`.

Test name (load-bearing for downstream `acceptance_criteria` grep):
`test_write_todos_signature_propagation`

CANONICAL EXECUTOR REGISTRATION PATTERN (verified against test_harness_engine.py:66-75): pass the executor function directly to `PhaseDefinition(...)` as the `executor` keyword argument. Do NOT assign it post-hoc with `harness.phases[0].executor = fn`. The executor function signature is `(inputs, token, thread_id, harness_run_id)` — these are positional parameters the engine will pass at dispatch time.

Use this test file template (copy verbatim — the executor registration is the verified canonical pattern from the existing test suite):

```python
"""Phase 22 / UAT Gap 2 — regression test for write_todos signature propagation.

Catches the bug discovered in live UAT 2026-05-06 where harness_engine.py called
write_todos(thread_id, todos, token) — 3 args in wrong order — but the real
signature is (thread_id, user_id, user_email, token, todos). The error handler
itself crashed with the same TypeError, so harness failure was silent.

This test must NOT mock write_todos at the call boundary with a no-op AsyncMock
(the existing tests do that, which is why signature drift was invisible).
Instead it captures positional args and asserts the order matches the real
signature.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.harnesses.types import (
    HarnessDefinition,
    HarnessPrerequisites,
    PhaseDefinition,
    PhaseType,
)
from app.services.harness_engine import _run_harness_engine_inner


# Canonical executor signature (matches test_harness_engine.py:67):
#   async def _executor(inputs, token, thread_id, harness_run_id) -> dict: ...
async def _ok_executor(inputs, token, thread_id, harness_run_id):
    return {"result": "ok", "text": "echo done"}


async def _crashing_executor(inputs, token, thread_id, harness_run_id):
    # Returning an error dict drives the engine through the error branch
    # (matches the failure-event contract used by other harness tests).
    raise RuntimeError("intentional failure for error-path coverage")


def _make_harness(executor) -> HarnessDefinition:
    """Build a one-phase programmatic harness with the canonical executor pattern."""
    return HarnessDefinition(
        name="smoke-echo",
        display_name="Smoke Echo",
        prerequisites=HarnessPrerequisites(harness_intro="x"),
        phases=[
            PhaseDefinition(
                name="echo",
                phase_type=PhaseType.PROGRAMMATIC,
                executor=executor,
                timeout_seconds=5,
            ),
        ],
    )


@pytest.mark.asyncio
async def test_write_todos_signature_propagation():
    """Engine must call write_todos with (thread_id, user_id, user_email, token, todos).

    Failure mode pre-fix: TypeError: write_todos() missing 2 required positional
    arguments: 'token' and 'todos'.
    """
    captured: list[tuple] = []

    async def capturing_write_todos(thread_id, user_id, user_email, token, todos):
        # Mirror real signature; capture in order.
        captured.append((thread_id, user_id, user_email, token, list(todos)))
        return []

    harness = _make_harness(_ok_executor)

    with patch(
        "app.services.harness_engine.agent_todos_service.write_todos",
        side_effect=capturing_write_todos,
    ), patch(
        "app.services.harness_engine.WorkspaceService"
    ) as mock_ws_cls, patch(
        "app.services.harness_engine.harness_runs_service.get_run_by_id",
        new_callable=AsyncMock,
        return_value={"status": "running"},
    ), patch(
        "app.services.harness_engine.harness_runs_service.advance_phase",
        new_callable=AsyncMock,
        return_value=True,
    ), patch(
        "app.services.harness_engine.harness_runs_service.complete",
        new_callable=AsyncMock,
        return_value=True,
    ):
        mock_ws = MagicMock()
        mock_ws.write_text_file = AsyncMock(return_value={"ok": True})
        mock_ws.read_file = AsyncMock(return_value={"ok": True, "content": "# Harness Progress\n"})
        mock_ws_cls.return_value = mock_ws

        events = []
        async for ev in _run_harness_engine_inner(
            harness=harness,
            harness_run_id="run-1",
            thread_id="thread-1",
            user_id="user-1",
            user_email="user@test.com",
            token="tok",
            registry=None,
            cancellation_event=asyncio.Event(),
            start_phase_index=0,
        ):
            events.append(ev)

    # At minimum: init + in_progress + completed = 3 write_todos calls per
    # successful programmatic phase. The error path (call site 4) is exercised
    # in the companion failure test below.
    assert len(captured) >= 3, (
        f"Expected >=3 write_todos calls (init/in_progress/completed); "
        f"got {len(captured)}"
    )

    for idx, args in enumerate(captured):
        assert args[0] == "thread-1", f"call {idx}: arg 0 (thread_id) wrong: {args[0]!r}"
        assert args[1] == "user-1", f"call {idx}: arg 1 (user_id) wrong: {args[1]!r}"
        assert args[2] == "user@test.com", f"call {idx}: arg 2 (user_email) wrong: {args[2]!r}"
        assert args[3] == "tok", f"call {idx}: arg 3 (token) wrong: {args[3]!r}"
        todos = args[4]
        assert isinstance(todos, list), f"call {idx}: arg 4 (todos) not list"
        for t in todos:
            assert "content" in t and "status" in t and "position" in t, (
                f"call {idx}: todo missing required keys: {t!r}"
            )


@pytest.mark.asyncio
async def test_write_todos_signature_propagation_error_path():
    """The error-path call site (line ~361 pre-fix) must also use the right signature.

    Drives a phase whose executor raises, which routes the engine through the
    'error' branch where write_todos is called once more.
    """
    captured: list[tuple] = []

    async def capturing_write_todos(thread_id, user_id, user_email, token, todos):
        captured.append((thread_id, user_id, user_email, token, list(todos)))
        return []

    harness = _make_harness(_crashing_executor)

    with patch(
        "app.services.harness_engine.agent_todos_service.write_todos",
        side_effect=capturing_write_todos,
    ), patch(
        "app.services.harness_engine.WorkspaceService"
    ) as mock_ws_cls, patch(
        "app.services.harness_engine.harness_runs_service.get_run_by_id",
        new_callable=AsyncMock,
        return_value={"status": "running"},
    ), patch(
        "app.services.harness_engine.harness_runs_service.fail",
        new_callable=AsyncMock,
        return_value=True,
    ), patch(
        "app.services.harness_engine.harness_runs_service.advance_phase",
        new_callable=AsyncMock,
        return_value=True,
    ):
        mock_ws = MagicMock()
        mock_ws.write_text_file = AsyncMock(return_value={"ok": True})
        mock_ws.read_file = AsyncMock(return_value={"ok": True, "content": "# Harness Progress\n"})
        mock_ws_cls.return_value = mock_ws

        async for _ in _run_harness_engine_inner(
            harness=harness,
            harness_run_id="run-2",
            thread_id="thread-2",
            user_id="user-2",
            user_email="u2@test.com",
            token="tok2",
            registry=None,
            cancellation_event=asyncio.Event(),
            start_phase_index=0,
        ):
            pass

    # init + in_progress + error = 3 calls minimum on failure path.
    assert len(captured) >= 3, f"Expected >=3 write_todos calls on error path; got {len(captured)}"
    for args in captured:
        assert args[0] == "thread-2"
        assert args[1] == "user-2"
        assert args[2] == "u2@test.com"
        assert args[3] == "tok2"
        assert isinstance(args[4], list)
```

Run the test ONCE before applying the fix in Task 2 — it MUST FAIL with `TypeError: write_todos() missing 2 required positional arguments` (or analogous TypeError). Capture the failure output for the SUMMARY. This is the RED step.
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pytest tests/services/test_harness_engine_todos.py::test_write_todos_signature_propagation -x 2>&1 | grep -E "TypeError|FAILED" || echo "RED-STEP-NOT-CAPTURED"</automated>
  </verify>
  <acceptance_criteria>
    - File `backend/tests/services/test_harness_engine_todos.py` exists.
    - File contains `def test_write_todos_signature_propagation` (load-bearing test name).
    - File contains `def test_write_todos_signature_propagation_error_path`.
    - The test asserts positional arg order: thread_id, user_id, user_email, token, todos.
    - The executor is registered via `PhaseDefinition(..., executor=fn, timeout_seconds=5)` constructor argument (NOT post-hoc attribute assignment), matching the canonical pattern in test_harness_engine.py:66-75.
    - Running the test BEFORE Task 2 fix produces a TypeError or FAILED line (RED step). Capture this output in the SUMMARY.
    - The test does NOT use `AsyncMock(return_value=None)` as the write_todos replacement — it uses a `side_effect` function with the real signature so signature drift is detected.
  </acceptance_criteria>
  <done>RED test exists, fails on current broken code, and captures the exact positional args order required by the real write_todos signature.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Fix all 4 write_todos call sites in harness_engine.py to use correct signature</name>
  <read_first>
    - backend/app/services/harness_engine.py (full file; the 4 call sites at lines 201, 289, 361, 428 must all change)
    - backend/app/services/agent_todos_service.py (lines 66-90: confirm signature one more time before editing)
    - backend/tests/services/test_harness_engine_todos.py (the RED test from Task 1)
  </read_first>
  <files>backend/app/services/harness_engine.py</files>
  <action>
Edit `backend/app/services/harness_engine.py` and replace the 4 broken call sites. Each replacement is mechanical:

OLD (appears 4 times):
```python
await agent_todos_service.write_todos(thread_id, todos, token)
```

NEW (must appear exactly 4 times after the edit):
```python
await agent_todos_service.write_todos(thread_id, user_id, user_email, token, todos)
```

EXACT call sites to replace (line numbers per current HEAD; the inner-loop kwargs `user_id` and `user_email` are already in scope at all 4 sites — verified in Read above):

1. Line 201 (init block, after `try:`):
   ```python
   await agent_todos_service.write_todos(thread_id, user_id, user_email, token, todos)
   ```

2. Line 289 (in_progress mark, inside the phase loop after the cancellation checks):
   ```python
   await agent_todos_service.write_todos(thread_id, user_id, user_email, token, todos)
   ```

3. Line 361 (error branch, after `todos[phase_index]["status"] = "completed"` on failure):
   ```python
   await agent_todos_service.write_todos(thread_id, user_id, user_email, token, todos)
   ```

4. Line 428 (completed branch, after the success-path `todos[phase_index]["status"] = "completed"`):
   ```python
   await agent_todos_service.write_todos(thread_id, user_id, user_email, token, todos)
   ```

Do NOT change argument names anywhere else in the function. Do NOT touch the `_dispatch_phase` call (that one already passes user_id/user_email correctly via kwargs). Do NOT alter the surrounding `try/except` blocks — only the call line itself changes.

After the edit, run the regression test from Task 1 — it MUST now PASS (GREEN step). Also re-run the existing harness engine test suite to confirm no regressions:

```
cd backend && source venv/bin/activate && \
  pytest tests/services/test_harness_engine.py tests/services/test_harness_engine_todos.py tests/services/test_harness_engine_post_execute.py tests/services/test_harness_engine_smoke_phase21.py -v
```

Expected: all tests green. The PostToolUse hook will additionally run py_compile + import-check on harness_engine.py — must pass.
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && python -c "from app.services.harness_engine import _run_harness_engine_inner; print('IMPORT_OK')" && [ "$(grep -c 'write_todos(thread_id, user_id, user_email, token, todos)' app/services/harness_engine.py)" = "4" ] && [ "$(grep -c 'write_todos(thread_id, todos, token)' app/services/harness_engine.py)" = "0" ] && pytest tests/services/test_harness_engine_todos.py -v</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "write_todos(thread_id, user_id, user_email, token, todos)" backend/app/services/harness_engine.py` returns exactly `4`.
    - `grep -c "write_todos(thread_id, todos, token)" backend/app/services/harness_engine.py` returns exactly `0` (no broken call sites left).
    - `python -c "from app.services.harness_engine import _run_harness_engine_inner"` succeeds (no SyntaxError, no ImportError).
    - `pytest backend/tests/services/test_harness_engine_todos.py -v` reports both `test_write_todos_signature_propagation` and `test_write_todos_signature_propagation_error_path` PASSED.
    - `pytest backend/tests/services/test_harness_engine.py backend/tests/services/test_harness_engine_post_execute.py backend/tests/services/test_harness_engine_smoke_phase21.py` all green (no new failures).
    - tool_service.py frozen-range SHA still matches `cb63cf3e60d5f6380e2e41f63b1fe9122f58ab4648808b0f2114e452cd45ddb2` (run `head -n 1283 backend/app/services/tool_service.py | shasum -a 256`).
  </acceptance_criteria>
  <done>Engine compiles, regression tests pass, no broken call signatures remain, no other tests regressed, tool_service.py frozen range untouched.</done>
</task>

</tasks>

<verification>
After both tasks:
- 4 fixed call sites — verified via grep counts above.
- Regression test exists and is GREEN.
- Existing 84+ harness tests still GREEN.
- harness_engine.py imports cleanly.
- tool_service.py frozen range unchanged.
</verification>

<success_criteria>
- [ ] backend/tests/services/test_harness_engine_todos.py created with the 2 named tests
- [ ] RED step captured (test fails before fix; output saved in SUMMARY)
- [ ] All 4 call sites in harness_engine.py use 5-arg correct order
- [ ] Zero call sites use the old 3-arg form
- [ ] GREEN step: regression tests pass
- [ ] No regression in existing harness_engine tests
- [ ] tool_service.py SHA invariant preserved
</success_criteria>

<output>
After completion, write `.planning/phases/22-contract-review-harness-docx-deliverable/22-14-SUMMARY.md` documenting:
- The captured RED-step failure output (TypeError text)
- The diff of harness_engine.py (4 lines changed)
- Pytest GREEN summary (count of tests run + 0 failures)
- tool_service.py SHA verification result
</output>
</output>
