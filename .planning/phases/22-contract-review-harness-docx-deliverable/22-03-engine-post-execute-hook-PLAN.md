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
requirements: [DOCX-08, CR-08]
must_haves:
  truths:
    - "harness_engine.py invokes phase.post_execute(...) between EVT_PHASE_COMPLETE yield and _append_progress, wrapped in try/except (D-22-15 non-fatal)"
    - "When phase.post_execute is None, the engine codepath is byte-identical to pre-Phase-22 (smoke_echo's 4 phases all have post_execute=None)"
    - "If post_execute returns an error dict {error, code, detail, fallback_message}, engine logs but does NOT mark harness_runs.status=failed"
    - "If post_execute raises an exception, engine logs the traceback (≤500 chars) and continues; harness_runs.status remains completed"
    - "REVIEW #7: after a successful post_execute that wrote a binary file, the engine ALSO emits a workspace_updated event so the WorkspacePanel auto-refreshes (existing chat router pattern at chat.py:1004-1005, 1779-1780)"
    - "REVIEW #8: harness_artifact event payload includes harness_run_id (already does) AND harness_mode='contract-review' (NEW) so the frontend can correlate the artifact with the post-harness assistant message even before summary_complete fires"
  artifacts:
    - path: "backend/app/services/harness_engine.py"
      provides: "post_execute invocation site between phase complete and progress append (~lines 423-425) + workspace_updated emission for binary writes + harness_mode in event"
      contains: "phase.post_execute"
    - path: "backend/tests/services/test_harness_engine_post_execute.py"
      provides: "7 tests covering None / success / error-dict / exception / ordering / workspace_updated / harness_mode propagation"
  key_links:
    - from: "harness_engine.py per-phase loop"
      to: "PhaseDefinition.post_execute callable (types.py:67)"
      via: "await phase.post_execute(harness_run_id=..., thread_id=..., user_id=..., user_email=..., token=..., phase_results=..., workspace=..., harness_name=...)"
      pattern: "phase\\.post_execute"
    - from: "post_execute success → harness_artifact event"
      to: "frontend useChatState reducer (plan 22-11)"
      via: "harness_run_id + harness_mode='contract-review' for correlation"
      pattern: "harness_mode"
    - from: "post_execute success that wrote a binary"
      to: "WorkspacePanel auto-refresh"
      via: "engine emits workspace_updated SSE event after artifact event"
      pattern: "workspace_updated"
---

<objective>
Wire `post_execute` into the engine and address REVIEW #7 + #8 directly:

1. **REVIEW #7 (workspace_updated emission):** when post_execute reports a successful binary write (e.g., the DOCX in plan 22-10), the engine MUST emit a `workspace_updated` SSE event so the Workspace Panel re-renders. Existing chat router code paths emit this for sandbox writes (chat.py:1004, 1779, 2483); the engine path was missing it.

2. **REVIEW #8 (correlation anchors):** the `harness_artifact` event must carry both `harness_run_id` AND `harness_mode` (the harness name, e.g. `contract-review`). The frontend reducer needs deterministic correlation to attach the artifact to the post-harness assistant message — not heuristic timing matching.

Output: post_execute invocation + workspace_updated chaining + harness_mode propagation + 7 unit tests.
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
@backend/app/harnesses/types.py
</context>

<interfaces>
<!-- PhaseDefinition.post_execute signature (types.py:67) -->
```python
post_execute: Callable[..., Awaitable[Any]] | None = None
```

<!-- Plan 22-03's post_execute contract (consumed by plan 22-10): -->
```python
async def post_execute(
    *,
    harness_run_id: str,
    thread_id: str,
    user_id: str,
    user_email: str,
    token: str,
    phase_results: dict,
    workspace: WorkspaceService,
    harness_name: str,        # NEW (REVIEW #8) — passes harness.name for downstream propagation
) -> dict | None:
    # Returns:
    #   None                                 -> no-op
    #   {"ok": True, "docx_path": ..., "signed_url": ..., "wrote_binary": True}
    #     ^^^ wrote_binary=True signals engine to emit workspace_updated AFTER harness_artifact
    #   {"error": str, "code": str, "detail": str, "fallback_message": str}
    # MUST NOT raise — engine catches anyway.
```

<!-- Existing workspace_updated event shape (chat.py:1004-1010): -->
```python
yield "workspace_updated", {
    "type": "workspace_updated",
    "thread_id": thread_id,
    "file_path": "<the file>",
    "operation": "create" | "update",
    "source": "harness",
    "size_bytes": int,
}
```
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Insert post_execute invocation + workspace_updated chaining + harness_mode propagation</name>
  <files>backend/app/services/harness_engine.py</files>
  <read_first>
    - backend/app/services/harness_engine.py (lines 405-450 — exact insertion site between phase_complete_evt yield and _append_progress call)
    - backend/app/harnesses/types.py (lines 50-72 — PhaseDefinition shape, especially post_execute and executor field semantics)
    - backend/app/routers/chat.py (lines 1000-1015 — workspace_updated emission shape; lines 1775-1785 — second emission point for reference)
    - .planning/phases/22-contract-review-harness-docx-deliverable/22-REVIEWS.md (review findings #7 and #8)
  </read_first>
  <behavior>
    - Test 1: `test_post_execute_none_is_noop` — phase with `post_execute=None`, engine completes byte-identical to pre-Phase-22.
    - Test 2: `test_post_execute_success_yielded_as_artifact_event` — `post_execute` returns `{"ok": True, "docx_path": "x.docx", "signed_url": "..."}`; engine yields a `harness_artifact` event with those fields PLUS `harness_run_id` AND `harness_mode` (REVIEW #8).
    - Test 3: `test_post_execute_error_dict_logged_no_status_change` — error dict path yields `harness_artifact ok=false`; harness_runs.status stays `completed`.
    - Test 4: `test_post_execute_exception_caught_no_status_change` — exception caught, yields error artifact, status stays `completed`.
    - Test 5: `test_post_execute_runs_after_last_phase_before_engine_complete` — yield order: `phase_complete` → `harness_artifact` → (if wrote_binary=True) `workspace_updated` → `_append_progress` → `harness_complete`.
    - Test 6 (REVIEW #7): `test_post_execute_emits_workspace_updated_when_wrote_binary` — when post_execute returns `{"ok": True, "docx_path": "x.docx", "wrote_binary": True}`, engine ALSO emits a `workspace_updated` event with `file_path="x.docx"`, `source="harness"`, AFTER the harness_artifact event.
    - Test 7 (REVIEW #8): `test_harness_artifact_event_carries_correlation_fields` — every harness_artifact event has `harness_run_id` AND `harness_mode` (the harness name).
  </behavior>
  <action>
    In `backend/app/services/harness_engine.py`, insert code immediately AFTER `yield phase_complete_evt` (line ~423) and BEFORE `await _append_progress(...)` (line ~425).

    The block:

    ```python
    # Phase 22 / DOCX-08 / D-22-15 / REVIEW #7 + #8: invoke phase.post_execute hook if defined.
    # - REVIEW #8: emit harness_run_id AND harness_mode for frontend correlation.
    # - REVIEW #7: if post_execute wrote a binary, also emit workspace_updated so the
    #   Workspace Panel auto-refreshes (matches chat.py:1004 pattern for sandbox writes).
    if phase.post_execute is not None:
        artifact_evt: dict = {
            "type": "harness_artifact",
            "harness_run_id": harness_run_id,
            "harness_mode": harness.name,           # REVIEW #8 — correlation anchor
            "phase_index": phase_index,
            "phase_name": phase.name,
        }
        pe_result: dict | None = None
        try:
            pe_result = await phase.post_execute(
                harness_run_id=harness_run_id,
                thread_id=thread_id,
                user_id=user_id,
                user_email=user_email,
                token=token,
                phase_results=phase_results,
                workspace=ws,
                harness_name=harness.name,           # REVIEW #8 propagation
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
                    **{k: pe_result.get(k) for k in
                       ("error", "code", "detail", "fallback_message") if k in pe_result},
                })
                yield artifact_evt
            elif isinstance(pe_result, dict):
                artifact_evt.update({"ok": True, **{
                    k: v for k, v in pe_result.items() if k != "wrote_binary"
                }})
                yield artifact_evt

                # REVIEW #7: emit workspace_updated AFTER artifact event when post_execute
                # wrote a binary. The Workspace Panel listens for this and re-fetches.
                # Mirrors chat.py:1004 pattern. Only fires when post_execute opt-in via
                # `wrote_binary=True` (so e.g. a no-op success doesn't spam the panel).
                if pe_result.get("wrote_binary") and pe_result.get("docx_path"):
                    yield {
                        "type": "workspace_updated",
                        "harness_run_id": harness_run_id,
                        "thread_id": thread_id,
                        "file_path": pe_result["docx_path"],
                        "operation": "create",
                        "source": "harness",
                        "size_bytes": int(pe_result.get("size_bytes") or 0),
                    }
            # If pe_result is None → no-op, no yield (matches default semantics)
    ```

    **ISSUE-16 PINNED — pre-conditions verified via direct read of harness_engine.py:**

    1. `ws` (WorkspaceService instance) IS in scope (declared line 204, assigned line 206). Check `if ws is None: ws = WorkspaceService(token=token)` immediately before post_execute call site.

    2. `phase_results` accumulator does NOT exist as a local. Add it to `_run_harness_engine_inner` right after the WorkspaceService init (~line 218):
    ```python
    # ISSUE-16: per-engine-run accumulator for phase outputs. Used by post_execute callbacks
    # (Phase 22 / DOCX-08). Memory bound: each result dict is summarized to cap memory.
    phase_results: dict[str, dict] = {}
    ```

    Then at line ~404 (right after `await harness_runs_service.advance_phase(...)`):
    ```python
    summary_payload = result if not isinstance(result, dict) else {
        k: (v if not isinstance(v, str) or len(v) <= 10_000 else v[:10_000] + "...[truncated]")
        for k, v in result.items()
    }
    phase_results[phase.name] = summary_payload
    ```

    3. `harness` (HarnessDefinition) variable name in this function: confirm by reading line ~200-220; it's typically `harness` or `harness_def`. Use whatever the actual variable name is — `harness.name` is the harness identifier (e.g. `"contract-review"`).

    Add `harness_artifact` and `workspace_updated` to the SSE event docstring near line 12-25 (header block listing engine-emitted events).

    **DO NOT** modify the EVT_COMPLETE branch — `harness_runs.status` stays `completed` even if post_execute fails. D-22-15 invariant.
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pytest tests/services/test_harness_engine_post_execute.py -v --tb=short && python -c "from app.main import app; print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "phase.post_execute" backend/app/services/harness_engine.py` returns `>= 2`
    - `grep -c "harness_artifact" backend/app/services/harness_engine.py` returns `>= 3`
    - `grep -c "harness_mode" backend/app/services/harness_engine.py` returns `>= 1` (REVIEW #8 propagation)
    - `grep -c "workspace_updated" backend/app/services/harness_engine.py` returns `>= 1` (REVIEW #7 emission — increment from existing log mentions)
    - `grep -c "wrote_binary" backend/app/services/harness_engine.py` returns `>= 1` (REVIEW #7 gate)
    - `grep -c "POST_EXEC_EXC" backend/app/services/harness_engine.py` returns `>= 1`
    - `python -c "from app.services.harness_engine import run_harness_engine; print('OK')"` prints `OK`
    - All existing harness_engine tests still pass: `pytest backend/tests/services/test_harness_engine* -v` exits 0
  </acceptance_criteria>
  <done>post_execute invocation present + workspace_updated chained + harness_mode propagated + 6+ tests pass.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: 7 unit tests covering post_execute contract + REVIEW #7 + REVIEW #8</name>
  <files>backend/tests/services/test_harness_engine_post_execute.py</files>
  <read_first>
    - backend/app/services/harness_engine.py (post-Task-1 state)
    - backend/tests/services/test_gatekeeper.py (AsyncMock + parametrize patterns)
    - backend/app/harnesses/types.py (PhaseDefinition.post_execute signature)
  </read_first>
  <behavior>
    See behaviors 1-7 in Task 1.
  </behavior>
  <action>
    Create `backend/tests/services/test_harness_engine_post_execute.py`. Header should list the 7 tests including REVIEW #7 + #8 anchors.

    Concrete test 6 body (REVIEW #7):
    ```python
    @pytest.mark.asyncio
    async def test_post_execute_emits_workspace_updated_when_wrote_binary():
        """REVIEW #7: post_execute that wrote a binary file MUST trigger
        a workspace_updated event so the Workspace Panel re-renders."""
        # Build minimal one-phase harness with success post_execute reporting wrote_binary=True
        post_execute_mock = AsyncMock(return_value={
            "ok": True,
            "docx_path": "contract-review-abc12345.docx",
            "signed_url": "https://example.com/x.docx",
            "wrote_binary": True,
            "size_bytes": 9876,
        })

        # ... build harness with one PROGRAMMATIC phase whose post_execute is the mock ...
        events = [ev async for ev in run_harness_engine(harness_run_id="test", ...)]

        # Find the harness_artifact and workspace_updated events
        artifact_idx = next(i for i, e in enumerate(events) if e.get("type") == "harness_artifact")
        ws_idx = next(i for i, e in enumerate(events) if e.get("type") == "workspace_updated")

        assert artifact_idx < ws_idx, "workspace_updated must follow harness_artifact"
        assert events[ws_idx]["file_path"] == "contract-review-abc12345.docx"
        assert events[ws_idx]["source"] == "harness"
        assert events[ws_idx]["size_bytes"] == 9876
    ```

    Concrete test 7 body (REVIEW #8):
    ```python
    @pytest.mark.asyncio
    async def test_harness_artifact_event_carries_correlation_fields():
        """REVIEW #8: harness_artifact event must include harness_run_id AND harness_mode
        (the harness name) so the frontend reducer can correlate without heuristics."""
        # ... build harness with name='contract-review' ...
        post_execute_mock = AsyncMock(return_value={"ok": True, "docx_path": "x.docx"})
        events = [ev async for ev in run_harness_engine(harness_run_id="run-42", ...)]
        artifact = next(e for e in events if e.get("type") == "harness_artifact")
        assert artifact["harness_run_id"] == "run-42"
        assert artifact["harness_mode"] == "contract-review"
    ```

    Each test mocks `harness_runs_service.start_run / complete / advance_phase`, `WorkspaceService.list_files / write_text_file / read_file`. Use `pytest.mark.asyncio`.
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pytest tests/services/test_harness_engine_post_execute.py -v --tb=short</automated>
  </verify>
  <acceptance_criteria>
    - `pytest backend/tests/services/test_harness_engine_post_execute.py -v` exits 0 with 7 tests passing
    - `grep -c "harness_artifact" backend/tests/services/test_harness_engine_post_execute.py` returns `>= 5`
    - `grep -c "workspace_updated" backend/tests/services/test_harness_engine_post_execute.py` returns `>= 1` (REVIEW #7)
    - `grep -c "harness_mode" backend/tests/services/test_harness_engine_post_execute.py` returns `>= 1` (REVIEW #8)
    - `grep -c "POST_EXEC_EXC" backend/tests/services/test_harness_engine_post_execute.py` returns `>= 1`
    - `grep -c "REVIEW #7\|REVIEW #8" backend/tests/services/test_harness_engine_post_execute.py` returns `>= 2`
  </acceptance_criteria>
  <done>7 tests pass, locking the post_execute contract + REVIEW #7 + #8 anchors for plan 22-10.</done>
</task>

</tasks>

<truths>
- D-22-15 (DOCX-08 non-fatal fallback): harness_runs.status MUST stay `completed` even when post_execute fails.
- types.py:67 declares post_execute; harness_engine.py never invokes it pre-Phase-22.
- D-16 OFF-mode invariant preserved: smoke_echo (post_execute=None) byte-identical.
- REVIEW #7: workspace_updated emission was missing from the engine path. The chat router emits it for sandbox writes (chat.py:1004); the engine path needed parity.
- REVIEW #8: harness_run_id was already in the proposed event; harness_mode is added so frontend reducer (plan 22-11) can correlate without timing heuristics.
- Insertion site between `yield phase_complete_evt` (line 423) and `await _append_progress(...)` (line 425) chosen so:
  1. progress.md captures phase as "completed" before any post_execute work
  2. UI sees `harness_phase_complete` before any artifact/workspace event (no UX racing)
- workspace_updated yields LAST in the trio (artifact → workspace_updated → progress) so frontend processes the artifact attachment before re-fetching workspace files.
</truths>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| post_execute callable → engine | Untrusted return value (might be invalid dict, might raise) — engine wraps in try/except + isinstance check |
| harness_artifact + workspace_updated → frontend | Backend-controlled SSE events; signed_url is authoritative |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-22-03-01 | Denial of Service | post_execute hangs indefinitely | accept | Engine's per-phase timeout wraps the entire phase including post_execute |
| T-22-03-02 | Tampering | post_execute returns malformed dict | mitigate | isinstance(dict) guard + selective key extraction |
| T-22-03-03 | Information Disclosure | exception detail leaks stack trace | mitigate | `str(exc)[:500]` cap matches D-19 sanitization invariant |
| T-22-03-04 | Tampering | wrote_binary=True with bogus docx_path triggers spurious workspace_updated | accept | Workspace Panel re-fetches on the event; bogus path simply doesn't appear in the file list |
</threat_model>

<verification>
1. `pytest backend/tests/services/test_harness_engine_post_execute.py -v` exits 0
2. `pytest backend/tests/services/test_harness_engine* -v` exits 0 (regression suite still green)
3. `pytest backend/tests/harnesses/ -v` exits 0 (smoke_echo's 4 phases all use post_execute=None — must be byte-identical)
4. `python -c "from app.main import app; print('OK')"` prints `OK`
</verification>

<success_criteria>
- Engine invokes post_execute when defined
- Default (None) codepath byte-identical to pre-Phase-22
- Failures degrade gracefully; harness_runs.status stays `completed`
- REVIEW #7: workspace_updated chained after binary writes
- REVIEW #8: harness_artifact carries harness_run_id + harness_mode for frontend correlation
- Plan 22-10's DOCX callable will fire on CR-08 phase boundary AND its file write will refresh the Workspace Panel
</success_criteria>

<output>
After completion, create `.planning/phases/22-contract-review-harness-docx-deliverable/22-03-SUMMARY.md`.
</output>
