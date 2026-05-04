---
phase: 22-contract-review-harness-docx-deliverable
plan: 03
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/app/services/harness_engine.py
  - backend/tests/services/test_harness_engine_post_execute.py
autonomous: true
requirements: [DOCX-08]
must_haves:
  truths:
    - "harness_engine.py invokes phase.post_execute(...) between EVT_PHASE_COMPLETE yield and _append_progress, wrapped in try/except (D-22-15 non-fatal)"
    - "When phase.post_execute is None, the engine codepath is byte-identical to pre-Phase-22 (smoke_echo's 4 phases all have post_execute=None)"
    - "If post_execute returns an error dict {error, code, detail, fallback_message}, engine logs but does NOT mark harness_runs.status=failed"
    - "If post_execute raises an exception, engine logs the traceback (≤500 chars) and continues; harness_runs.status remains completed"
  artifacts:
    - path: "backend/app/services/harness_engine.py"
      provides: "post_execute invocation site between phase complete and progress append (~lines 423-425)"
      contains: "phase.post_execute"
    - path: "backend/tests/services/test_harness_engine_post_execute.py"
      provides: "5 tests covering None, success, error-dict, exception, last-phase-of-harness shapes"
  key_links:
    - from: "harness_engine.py per-phase loop (line ~423)"
      to: "PhaseDefinition.post_execute callable (types.py:67)"
      via: "await phase.post_execute(harness_run_id=..., thread_id=..., user_id=..., user_email=..., token=..., phase_results=...)"
      pattern: "phase\\.post_execute"
---

<objective>
Wire the `post_execute` hook into `harness_engine.py`. The field has been declared on `PhaseDefinition` since Phase 20 (types.py:67) but is NEVER called by the engine. Plan 22-10 (CR-08 + DOCX) needs it.

Purpose: DOCX-01..08 hangs off CR-08's `post_execute`. Without this invocation site, plan 22-10's callable is dead code.
Output: One try/except wrapped invocation site in `harness_engine.py`'s per-phase loop + 5 unit tests covering the contract.
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
@backend/app/harnesses/types.py
</context>

<interfaces>
<!-- PhaseDefinition.post_execute signature (types.py:67) -->
<!-- Callable[..., Awaitable[Any]] | None — engine MUST pass kwargs by name -->

From backend/app/harnesses/types.py:67:
```python
post_execute: Callable[..., Awaitable[Any]] | None = None
```

The contract Plan 22-03 establishes (then Plan 22-10 implements):
```python
async def post_execute(
    *,
    harness_run_id: str,
    thread_id: str,
    user_id: str,
    user_email: str,
    token: str,
    phase_results: dict,        # accumulated phase outputs so far
    workspace: WorkspaceService, # reuse the engine's workspace client
) -> dict | None:
    # Returns None on no-op, or:
    #   {"ok": True, ...}            -> success, engine yields harness_artifact event
    #   {"error": str, "code": str,
    #    "detail": str,
    #    "fallback_message": str}    -> non-fatal failure (D-22-15)
    # MUST NOT raise — engine catches anyway, but the dict-return contract is preferred.
```
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Insert post_execute invocation between phase_complete yield and progress append</name>
  <files>backend/app/services/harness_engine.py</files>
  <read_first>
    - backend/app/services/harness_engine.py (lines 405-450 — exact insertion site between phase_complete_evt yield and _append_progress call)
    - backend/app/harnesses/types.py (lines 50-72 — PhaseDefinition shape, especially post_execute and executor field semantics)
    - backend/app/harnesses/smoke_echo.py (lines 60-66 — error-dict shape pattern; post_execute uses same shape)
    - .planning/phases/22-contract-review-harness-docx-deliverable/22-PATTERNS.md (lines 145-155 — exact insertion site recommended)
  </read_first>
  <behavior>
    - Test 1: `test_post_execute_none_is_noop` — phase with `post_execute=None`, engine completes byte-identical to pre-Phase-22 (no extra yields, no extra DB writes).
    - Test 2: `test_post_execute_success_dict_yielded_as_artifact_event` — phase's `post_execute` returns `{"ok": True, "docx_path": "x.docx", "signed_url": "https://..."}`; engine yields a `harness_artifact` SSE event with those fields.
    - Test 3: `test_post_execute_error_dict_logged_no_status_change` — `post_execute` returns `{"error": "docx_failed", "code": "DOCX_FAILED", "detail": "...", "fallback_message": "..."}`; engine yields `harness_artifact` with `error=true` AND continues, harness_runs.status remains `completed` (D-22-15).
    - Test 4: `test_post_execute_exception_caught_no_status_change` — `post_execute` raises; engine catches, logs (≤500 chars detail), yields `harness_artifact` with error fields, continues normally.
    - Test 5: `test_post_execute_runs_after_last_phase_before_engine_complete` — verify ordering: yield order is `phase_complete` → `harness_artifact` (from post_execute) → `_append_progress` → `harness_complete`.
    - Test 6 (ISSUE-16 memory bound): 8-phase harness, each phase result dict has a 50KB string field; after engine completion, the per-engine-run `phase_results` accumulator total size is bounded to ~80KB (10KB cap × 8 phases). Assert via sys.getsizeof or len-of-content sum.
  </behavior>
  <action>
    In `backend/app/services/harness_engine.py`, INSERT code immediately AFTER `yield phase_complete_evt` (line 423) and BEFORE `await _append_progress(...)` (line 425). Add the following block:

    ```python
        # Phase 22 / DOCX-08 (D-22-15 non-fatal): invoke phase.post_execute hook if defined.
        # Contract: callable receives kwargs (harness_run_id, thread_id, user_id, user_email,
        # token, phase_results, workspace). Returns dict or None. Failures are NEVER fatal —
        # missing DOCX is a degradation, not a harness failure.
        if phase.post_execute is not None:
            artifact_evt: dict = {
                "type": "harness_artifact",
                "harness_run_id": harness_run_id,
                "phase_index": phase_index,
                "phase_name": phase.name,
            }
            try:
                pe_result = await phase.post_execute(
                    harness_run_id=harness_run_id,
                    thread_id=thread_id,
                    user_id=user_id,
                    user_email=user_email,
                    token=token,
                    phase_results=phase_results,
                    workspace=ws,
                )
            except Exception as exc:
                logger.warning(
                    "harness_engine post_execute raised harness_run=%s phase=%s: %s",
                    harness_run_id, phase.name, exc, exc_info=True,
                )
                artifact_evt.update({
                    "ok": False,
                    "error": "post_execute_raised",
                    "code": "POST_EXEC_EXC",
                    "detail": str(exc)[:500],
                    "fallback_message": (
                        "Post-phase artifact generation failed — see chat for the markdown summary."
                    ),
                })
                yield artifact_evt
            else:
                if isinstance(pe_result, dict) and pe_result.get("error"):
                    logger.warning(
                        "harness_engine post_execute returned error harness_run=%s phase=%s code=%s",
                        harness_run_id, phase.name, pe_result.get("code"),
                    )
                    artifact_evt.update({
                        "ok": False,
                        **{k: pe_result.get(k) for k in ("error", "code", "detail", "fallback_message") if k in pe_result},
                    })
                    yield artifact_evt
                elif isinstance(pe_result, dict):
                    artifact_evt.update({"ok": True, **pe_result})
                    yield artifact_evt
                # If pe_result is None → no-op, no yield (matches default semantics)
    ```

    **ISSUE-16 PINNED — pre-conditions verified via direct read of harness_engine.py:**

    1. `ws` (WorkspaceService instance) IS in scope. Declared at line 204 (`ws: WorkspaceService | None = None`) and assigned at line 206 (`ws = WorkspaceService(token=token)`). Reuse it directly. (Note: it may be `None` if the initial `WorkspaceService(token=token)` constructor raised — check `if ws is None: ws = WorkspaceService(token=token)` immediately before the post_execute call site.)

    2. `phase_results` accumulator does NOT exist as a local variable in the engine. The engine writes per-phase results via `harness_runs_service.advance_phase(phase_results_patch={...})` (line 386-396) which patches the DB row. There is NO local accumulator dict.

    **Fix:** declare a local accumulator at the top of `_run_harness_engine_inner` (right after the WorkspaceService init at line ~218), with a memory bound:
    ```python
    # ISSUE-16: per-engine-run accumulator for phase outputs. Used by post_execute callbacks
    # (Phase 22 / DOCX-08). Memory bound: each result dict is summarized for storage to
    # avoid keeping full LLM_BATCH_AGENTS payloads in memory across long runs.
    phase_results: dict[str, dict] = {}
    ```

    Then at line ~404 (right after `await harness_runs_service.advance_phase(...)`), append:
    ```python
    # Add to in-memory accumulator (post_execute hook reads this dict).
    # Bound: store at most a 10KB summary per phase to cap memory for 8-phase * N-clauses runs.
    summary_payload = result if not isinstance(result, dict) else {
        k: (v if not isinstance(v, str) or len(v) <= 10_000 else v[:10_000] + "...[truncated]")
        for k, v in result.items()
    }
    phase_results[phase.name] = summary_payload
    ```

    This is a pure-additive accumulator. Existing code paths and tests are unaffected; the variable is unused unless `phase.post_execute is not None`.

    **Files modified by this plan must include the harness_engine.py phase_results declaration** (it's already in `<files_modified>` — no change needed).

    **Add to test count for memory bound:**
    - Test 6 (NEW — ISSUE-16 memory bound): run engine with 8 phases each producing a 50KB result dict; assert peak `phase_results` memory at end is bounded to ~80KB (10KB × 8), not 400KB. Use `sys.getsizeof` snapshots before and after.

    **DO NOT** modify the EVT_COMPLETE branch at line 450 — `harness_runs.status` stays `completed` even if post_execute fails. D-22-15 invariant.

    Add `harness_artifact` to the SSE event docstring near line 12-25 (header comment block listing all engine-emitted events).
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pytest tests/services/test_harness_engine_post_execute.py -v --tb=short && python -c "from app.main import app; print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "phase.post_execute" backend/app/services/harness_engine.py` returns `>= 2` (the `is not None` check + the `await` call)
    - `grep -c "harness_artifact" backend/app/services/harness_engine.py` returns `>= 3` (event type literal in 3+ places: success branch, error-dict branch, exception branch)
    - `grep -nE "yield phase_complete_evt|await _append_progress" backend/app/services/harness_engine.py` returns the post_execute block lies BETWEEN those two lines (verify by reading the file)
    - `grep -c "POST_EXEC_EXC" backend/app/services/harness_engine.py` returns `>= 1`
    - `python -c "from app.services.harness_engine import run_harness_engine; print('OK')"` prints `OK`
    - All existing harness_engine tests still pass: `pytest backend/tests/services/test_harness_engine* -v` exits 0
  </acceptance_criteria>
  <done>post_execute invocation present, wrapped in try/except, emits structured `harness_artifact` SSE event, never marks the run as failed.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Add 5 unit tests covering post_execute contract</name>
  <files>backend/tests/services/test_harness_engine_post_execute.py</files>
  <read_first>
    - backend/app/services/harness_engine.py (post-Task-1 state)
    - backend/tests/services/test_gatekeeper.py (for AsyncMock + parametrize patterns)
    - backend/app/harnesses/types.py (PhaseDefinition.post_execute signature)
    - .planning/phases/22-contract-review-harness-docx-deliverable/22-PATTERNS.md (lines 300-329 — non-fatal fallback shape)
  </read_first>
  <behavior>
    See Task 1 behavior block — five named tests covering: None default, success dict, error dict, raised exception, ordering.
  </behavior>
  <action>
    Create `backend/tests/services/test_harness_engine_post_execute.py`. Mirror header style of `test_gatekeeper.py:1-19`.

    Each test:
    - Builds a minimal one-phase HarnessDefinition (PROGRAMMATIC type with a no-op executor returning `{"content": "ok"}`)
    - Test 1: `post_execute=None`
    - Test 2: `post_execute=AsyncMock(return_value={"ok": True, "docx_path": "x.docx", "signed_url": "https://example.com/x.docx"})`
    - Test 3: `post_execute=AsyncMock(return_value={"error": "docx_failed", "code": "DOCX_FAILED", "detail": "boom", "fallback_message": "Retry by re-running."})`
    - Test 4: `post_execute=AsyncMock(side_effect=RuntimeError("boom"))`
    - Test 5: 2-phase harness, phase 1 has `post_execute=None`, phase 2 has success post_execute → asserts the yield order

    For each, use `pytest-asyncio` and consume the async generator into a list:
    ```python
    events = [ev async for ev in run_harness_engine(harness_run_id="test-run", ...)]
    ```

    Then assert:
    - Test 1: NO event with `type=="harness_artifact"` exists
    - Test 2: Exactly one `harness_artifact` event with `ok=True`, `docx_path="x.docx"`, `signed_url="https://example.com/x.docx"`
    - Test 3: One `harness_artifact` with `ok=False`, `error="docx_failed"`, `code="DOCX_FAILED"`, `fallback_message="Retry by re-running."`; harness_runs.status mock NOT called with `"failed"` (use AsyncMock spy on `harness_runs_service.complete` and assert call args contain status `completed` or no explicit status)
    - Test 4: One `harness_artifact` with `ok=False`, `code="POST_EXEC_EXC"`, `detail` non-empty (≤500 chars), no exception bubbles to the test
    - Test 5: Walk through the events list and find indexes of `harness_phase_complete` (phase 2), `harness_artifact`, `harness_complete`. Assert `phase_complete_idx < artifact_idx < complete_idx`. Phase 1 must have NO artifact event between its complete and the next phase start.

    Mock dependencies via `unittest.mock.patch`: `harness_runs_service.start_run`, `harness_runs_service.complete`, `harness_runs_service.advance_phase`, `WorkspaceService.list_files`, `WorkspaceService.write_text_file`, `WorkspaceService.read_file` (return `{"content": "echo content"}`). Use `pytest.mark.asyncio` decorator on each test.
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pytest tests/services/test_harness_engine_post_execute.py -v --tb=short</automated>
  </verify>
  <acceptance_criteria>
    - `pytest backend/tests/services/test_harness_engine_post_execute.py -v` exits 0 with 6 tests passing
    - `grep -c "harness_artifact" backend/tests/services/test_harness_engine_post_execute.py` returns `>= 5` (one per test minimum)
    - `grep -c "POST_EXEC_EXC" backend/tests/services/test_harness_engine_post_execute.py` returns `>= 1` (Test 4 asserts the exception code literal)
    - `grep -c "ok=True\|\"ok\": True" backend/tests/services/test_harness_engine_post_execute.py` returns `>= 1`
  </acceptance_criteria>
  <done>6 tests pass, locking the post_execute contract + ISSUE-16 memory bound for Plan 22-10's DOCX implementation.</done>
</task>

</tasks>

<truths>
- D-22-15 (DOCX-08 non-fatal fallback): harness_runs.status MUST stay `completed` even when post_execute fails.
- types.py:67 declares the field; harness_engine.py never invokes it pre-Phase-22 (PATTERNS.md L150-152 confirms).
- D-16 OFF-mode invariant preserved: smoke_echo (and any harness with `post_execute=None`) is byte-identical to pre-Phase-22 behavior.
- The new `harness_artifact` SSE event needs a frontend slot (Plan 22-11 frontend work).
- Insertion site between `yield phase_complete_evt` (line 423) and `await _append_progress(...)` (line 425) was chosen so:
  1. progress.md captures the phase as "completed" before any post_execute-side work
  2. UI sees `harness_phase_complete` before any artifact event (no UX racing)
</truths>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| post_execute callable → engine | Untrusted return value (might be invalid dict, might raise) — engine wraps in try/except + isinstance check |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-22-03-01 | Denial of Service | post_execute hangs indefinitely | accept | Engine's existing per-phase timeout wraps the entire phase including post_execute (HARN-06 contract) — long-running post_execute is the implementer's bug, not engine's |
| T-22-03-02 | Tampering | post_execute returns malformed dict | mitigate | isinstance(dict) guard + selective key extraction prevents stray fields polluting SSE event |
| T-22-03-03 | Information Disclosure | exception detail leaks stack trace | mitigate | `str(exc)[:500]` cap matches the project's D-19 sanitization invariant (harness_engine.py:159) |
</threat_model>

<verification>
1. `pytest backend/tests/services/test_harness_engine_post_execute.py -v` exits 0
2. `pytest backend/tests/services/test_harness_engine* -v` exits 0 (regression suite still green)
3. Smoke test: `pytest backend/tests/harnesses/ -v` exits 0 (smoke_echo's 4 phases all use `post_execute=None`, must be byte-identical)
4. `python -c "from app.main import app; print('OK')"` prints `OK`
</verification>

<success_criteria>
- Engine invokes `post_execute` when defined
- Default (None) codepath byte-identical to pre-Phase-22
- Failures degrade gracefully; harness_runs.status stays `completed`
- Plan 22-10's DOCX callable will fire on CR-08 phase boundary
</success_criteria>

<output>
After completion, create `.planning/phases/22-contract-review-harness-docx-deliverable/22-03-SUMMARY.md`.
</output>
