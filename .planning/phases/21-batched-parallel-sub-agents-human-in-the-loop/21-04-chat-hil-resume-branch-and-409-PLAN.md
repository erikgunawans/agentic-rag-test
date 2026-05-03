---
phase: 21-batched-parallel-sub-agents-human-in-the-loop
plan: 04
type: execute
wave: 4
depends_on: [02]
files_modified:
  - backend/app/routers/chat.py
  - backend/tests/routers/test_chat_hil_resume.py
autonomous: true
requirements:
  - HIL-04  # User response captured → workspace write → phase advance → harness resume
must_haves:
  truths:
    - "chat.py 409 block at lines ~366-388 only triggers when active_harness.status IN ('pending','running'). Status 'paused' falls through (D-01)."
    - "A new HIL resume detection branch is inserted BEFORE the 409 block (and after the Phase 19 ask_user resume branch). When harness_runs_service.get_active_run returns a row with status='paused', this branch handles the message instead of falling through to gatekeeper or standard dispatch."
    - "HIL resume branch (D-02 sequence): (1) loads harness from registry by paused_run.harness_type; (2) reads paused_run.current_phase to identify which phase's workspace_output should receive the answer; (3) writes body.message to that workspace_output via WorkspaceService.write_text_file with source='harness'; (4) persists the user's message to messages table with harness_mode=harness.name; (5) calls harness_runs_service.resume_from_pause (Plan 21-02 Task 0 helper) with new_phase_index=current_phase+1 and phase_results_patch storing the answer summary; (6) checks the return is non-None (RLS or stale-state guard); (7) returns StreamingResponse from a NEW _resume_harness_engine_sse helper that calls run_harness_engine(start_phase_index=current_phase+1, ...) with a registry loaded via the EXISTING _get_or_build_conversation_registry helper at chat.py:1695."
    - "BLOCKER-5 fix — exact symbol bindings (verified in chat.py during planning): (a) the existing registry-loader helper is `_get_or_build_conversation_registry(thread_id, sys_settings)` at chat.py:1695 (NOT `_load_parent_registry` and NOT `_load_conversation_registry` — both placeholder names from earlier drafts of this plan). The HIL resume branch MUST call this exact symbol. (b) the resume SSE helper is NEW: `async def _resume_harness_engine_sse(...)` defined in chat.py near `_gatekeeper_stream_wrapper` (line 1724). It is a thin wrapper that loads the registry once via _get_or_build_conversation_registry, then iterates run_harness_engine(start_phase_index=N+1, ...) and emits `data: {...}\\n\\n` SSE wire frames identical to _gatekeeper_stream_wrapper's output."
    - "BLOCKER-2 fix — the resume branch calls `harness_runs_service.resume_from_pause(...)` (NOT `advance_phase` — its `.in_(\"status\", [\"pending\", \"running\"])` guard at line 244 silently rejects paused rows). The branch checks `if updated_row is None: return JSONResponse(500, {\"error\": \"hil_resume_state_invalid\"})` to surface the rare race where the row was cancelled or terminal'd between get_active_run and resume_from_pause."
    - "Resume branch is gated by settings.harness_enabled (mirrors D-02 entry guard)."
    - "All 7 router tests pass: paused-detection, workspace write target, resume_from_pause invocation, _resume_harness_engine_sse signature with start_phase_index, harness_mode message tagging, 409 only blocks pending/running, stale-state guard surfaces 500."
  artifacts:
    - path: "backend/app/routers/chat.py"
      provides: "HIL resume branch at stream_chat entry + 409 condition fix + new _resume_harness_engine_sse helper"
      contains: "_resume_harness_engine_sse"
    - path: "backend/tests/routers/test_chat_hil_resume.py"
      provides: "7 router-level FastAPI TestClient tests covering HIL resume flow + 409 condition fix + stale-state guard"
      contains: "test_hil_resume_detects_paused_status"
  key_links:
    - from: "stream_chat entry"
      to: "HIL resume branch (NEW)"
      via: "ordered check before 409 block"
      pattern: "paused_run.*status.*paused"
    - from: "HIL resume branch"
      to: "_resume_harness_engine_sse (NEW helper, near chat.py:1724)"
      via: "StreamingResponse with start_phase_index=current_phase+1"
      pattern: "_resume_harness_engine_sse"
    - from: "_resume_harness_engine_sse"
      to: "_get_or_build_conversation_registry (chat.py:1695)"
      via: "single-registry helper REUSE — B4 invariant"
      pattern: "_get_or_build_conversation_registry"
    - from: "HIL resume branch"
      to: "WorkspaceService.write_text_file"
      via: "answer write to phase.workspace_output"
      pattern: "write_text_file"
    - from: "HIL resume branch"
      to: "harness_runs_service.resume_from_pause"
      via: "atomic paused → running transition with phase_results merge"
      pattern: "resume_from_pause"
    - from: "409 block"
      to: "active_harness.status check"
      via: "exclude 'paused' from blocking statuses"
      pattern: 'active_harness\.get\("status"\) in \("pending", "running"\)'
---

<objective>
Wire the HIL resume flow at the chat router entry. Three surgical edits to `chat.py`: (1) change the existing 409-conflict block to only block `pending` and `running` (not `paused`); (2) add a new `_resume_harness_engine_sse` helper near `_gatekeeper_stream_wrapper` (line 1724) that wraps `run_harness_engine(start_phase_index=...)` with SSE serialization and reuses the existing `_get_or_build_conversation_registry` (line 1695) for the registry; (3) insert a NEW HIL resume branch before that 409 block that drives the user's reply through workspace write → resume_from_pause → _resume_harness_engine_sse.

Purpose: This is the only chat-side touchpoint to make HIL-04 observable end-to-end. Without this branch, a paused harness sees the user's reply but the engine never resumes — the run sits forever at status='paused'.
Output: chat.py edits (3 localized) + 7 FastAPI TestClient router tests.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/STATE.md
@.planning/phases/21-batched-parallel-sub-agents-human-in-the-loop/21-CONTEXT.md
@.planning/phases/21-batched-parallel-sub-agents-human-in-the-loop/21-PATTERNS.md
@.planning/phases/21-batched-parallel-sub-agents-human-in-the-loop/21-02-hil-dispatcher-and-engine-signature-PLAN.md
@CLAUDE.md
@backend/app/routers/chat.py
@backend/app/services/harness_runs_service.py
@backend/app/services/workspace_service.py
@backend/app/services/harness_engine.py
@backend/app/harnesses/registry.py
@backend/tests/routers/test_chat_harness_routing.py

<interfaces>
<!-- All interfaces extracted from existing code (verified during planning). -->

From backend/app/routers/chat.py — current 409 block (lines 366-388):
```python
if settings.harness_enabled:
    active_harness = await harness_runs_service.get_active_run(
        thread_id=body.thread_id, token=user["token"]
    )
    if active_harness is not None:
        phase_idx = active_harness.get("current_phase", 0)
        phase_name = "—"
        try:
            h = harness_registry.get_harness(active_harness["harness_type"])
            if h and phase_idx < len(h.phases):
                phase_name = h.phases[phase_idx].name
        except Exception:
            phase_name = "—"
        return JSONResponse(
            status_code=409,
            content={
                "error": "harness_in_progress",
                "harness_type": active_harness["harness_type"],
                "current_phase": phase_idx,
                "phase_name": phase_name,
                "phase_count": len(h.phases) if h else 0,
            },
        )
```

From backend/app/routers/chat.py — VERIFIED helper symbols:
```python
# Line 1695 — REUSE this for the resume branch's registry load:
async def _get_or_build_conversation_registry(
    thread_id: str,
    sys_settings: dict | None = None,
):
    """Returns ConversationRegistry instance when pii_redaction_enabled is True;
    None otherwise. B4 invariant — call this ONCE per request."""

# Line 1724 — existing harness SSE wrapper (the structural analog for the new
# _resume_harness_engine_sse helper):
async def _gatekeeper_stream_wrapper(
    *, harness, thread_id, user_id, user_email, token, sys_settings, ...
):
    ...

# Phase 19 ask_user resume branch (lines 270-360) — the structural analog for
# the HIL resume branch shape (transition + history reload + StreamingResponse).
```

NOTE on bindings (BLOCKER-5 / WARNING-4 fix): the symbols `_load_conversation_registry`
and `_load_parent_registry` do NOT exist in chat.py. Earlier drafts of this plan
referenced them as placeholders — they are corrected to the actual symbol name
`_get_or_build_conversation_registry` (line 1695). The resume SSE helper is also
NEW (no analog wrapper named `_run_harness_engine_sse` exists today); this plan
ships the helper alongside the resume branch.

From backend/app/services/harness_runs_service.py (post Plan 21-02 Task 0):
```python
ACTIVE_STATUSES: tuple[str, ...] = ("pending", "running", "paused")

async def get_active_run(*, thread_id: str, token: str) -> HarnessRunRecord | None: ...

# NEW — added by Plan 21-02 Task 0. HIL resume MUST call this, NOT advance_phase
# (which guards .in_("status", ["pending", "running"]) — would silently reject paused):
async def resume_from_pause(
    *, run_id: str, new_phase_index: int,
    phase_results_patch: dict[str, Any],
    user_id: str, user_email: str, token: str,
) -> HarnessRunRecord | None: ...
```

From backend/app/services/harness_engine.py (post Plan 21-02):
```python
async def run_harness_engine(
    *,
    harness, harness_run_id, thread_id, user_id, user_email,
    token, registry, cancellation_event,
    start_phase_index: int = 0,
) -> AsyncIterator[dict]: ...
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add _resume_harness_engine_sse helper + HIL resume branch in stream_chat + change 409 condition to exclude 'paused' + 7 FastAPI TestClient tests (RED → GREEN)</name>
  <files>backend/app/routers/chat.py, backend/tests/routers/test_chat_hil_resume.py</files>
  <read_first>
    - backend/app/routers/chat.py — full read of `stream_chat` function. Critical regions: lines 270-360 (Phase 19 ask_user resume branch — the structural analog), lines 362-388 (D-02 409 block — surgical edit target), the imports section (top of file — confirm `harness_runs_service`, `harness_registry`, `WorkspaceService`, `run_harness_engine`, `settings`, `get_supabase_authed_client` are already imported).
    - backend/app/routers/chat.py line 1695 — `_get_or_build_conversation_registry` definition. The HIL resume branch MUST reuse THIS symbol (NOT a placeholder named `_load_conversation_registry` or `_load_parent_registry`).
    - backend/app/routers/chat.py line 1724 — `_gatekeeper_stream_wrapper`. The new `_resume_harness_engine_sse` helper is added immediately AFTER this function and mirrors its SSE serialization shape (`yield f"data: {json.dumps(evt)}\\n\\n"`).
    - backend/app/services/harness_runs_service.py — confirm `resume_from_pause` (added by Plan 21-02 Task 0) is callable; signature: `(*, run_id, new_phase_index, phase_results_patch, user_id, user_email, token)` returning `HarnessRunRecord | None`. The advance_phase guard at line 244 confirms why we MUST use resume_from_pause for paused rows (BLOCKER-2).
    - backend/app/harnesses/registry.py (or wherever `harness_registry` lives) — confirm `harness_registry.get_harness(name)` returns a HarnessDefinition with `.phases: list[PhaseDefinition]`.
    - backend/tests/routers/test_chat_harness_routing.py — full file. Re-use the `_make_prereqs` helper (lines 17-49), the FastAPI TestClient + dependency-override pattern, and the harness fixture style.
    - .planning/phases/21-batched-parallel-sub-agents-human-in-the-loop/21-PATTERNS.md — sections "chat.py — D-01 / D-02 HIL resume branch (NEW, before 409 block)" (lines 226-326) and "chat.py — D-01 409 block change" (lines 330-352) and "test_chat_hil_resume.py" (lines 668-700).
    - .planning/phases/21-batched-parallel-sub-agents-human-in-the-loop/21-CONTEXT.md — D-01 (409 condition change), D-02 (HIL resume branch sequence), D-03 (start_phase_index = current_phase + 1).
  </read_first>
  <behavior>
    Tests in `backend/tests/routers/test_chat_hil_resume.py`. Mirror the import + fixture pattern from `backend/tests/routers/test_chat_harness_routing.py`.

    - Test 1 `test_hil_resume_detects_paused_status`: mock `harness_runs_service.get_active_run` returns `{id, status: "paused", harness_type: "smoke-echo", current_phase: 2}`; mock `resume_from_pause` returns the updated row; POST a chat message; assert 200 (not 409); assert content-type starts with `text/event-stream`; assert `harness_runs_service.resume_from_pause` was awaited (not advance_phase).
    - Test 2 `test_hil_resume_writes_answer_to_workspace`: mock `WorkspaceService.write_text_file` as recording AsyncMock; resume flow with body.message = "Test answer 123" and current phase having workspace_output = "test-answer.md"; assert call recorded with file_path="test-answer.md", content="Test answer 123", source="harness".
    - Test 3 `test_hil_resume_calls_resume_from_pause_with_next_index`: assert `harness_runs_service.resume_from_pause` called once with kwargs `new_phase_index=3` (current_phase 2 + 1) and `phase_results_patch` containing key "2" with the answer summary; assert advance_phase was NOT called (BLOCKER-2 regression).
    - Test 4 `test_hil_resume_calls_run_harness_engine_with_start_phase_index`: patch `run_harness_engine` to a MagicMock async generator; assert it was awaited with kwarg `start_phase_index=3` (current_phase 2 + 1).
    - Test 5 `test_hil_resume_persists_user_message_with_harness_mode`: mock supabase client's `.table("messages").insert(...).execute()`; capture the dict argument; assert it has `role="user"`, `content="Test answer 123"`, `harness_mode="smoke-echo"`.
    - Test 6 `test_409_only_blocks_pending_running`: parametrize over (`status="pending"` → expect 409, `status="running"` → expect 409, `status="paused"` → expect 200 SSE, `status=None` (no active run) → expect 200 normal flow).
    - Test 7 `test_hil_resume_returns_500_when_resume_from_pause_returns_none` (BLOCKER-2 regression): mock `resume_from_pause` to return None (simulating row that was cancelled or completed between get_active_run and resume_from_pause). Assert 500 response with body `{"error": "hil_resume_state_invalid", ...}`. Assert run_harness_engine was NOT invoked.
  </behavior>
  <action>
    **Edit 1: 409 condition change (lines 366-388 of chat.py)**

    Find the existing block:
    ```python
    if settings.harness_enabled:
        active_harness = await harness_runs_service.get_active_run(
            thread_id=body.thread_id, token=user["token"]
        )
        if active_harness is not None:
            ...
            return JSONResponse(status_code=409, ...)
    ```

    Change the inner condition to exclude paused — write the EXACT condition string used in the acceptance grep:
    ```python
    if settings.harness_enabled:
        active_harness = await harness_runs_service.get_active_run(
            thread_id=body.thread_id, token=user["token"]
        )
        if active_harness is not None and active_harness.get("status") in ("pending", "running"):
            phase_idx = active_harness.get("current_phase", 0)
            ...   # rest unchanged
            return JSONResponse(status_code=409, ...)
    ```

    **Edit 2: New helper `_resume_harness_engine_sse` (insert near chat.py:1724, immediately after `_gatekeeper_stream_wrapper`).**

    ```python
    # ---------------------------------------------------------------------------
    # Phase 21 / HIL-04 — Resume harness engine SSE wrapper
    # Mirrors _gatekeeper_stream_wrapper's SSE serialization shape but skips the
    # gatekeeper LLM round-trip (we already know we're resuming an existing run).
    # Reuses _get_or_build_conversation_registry (line 1695) — B4 invariant: never
    # mint a fresh registry on resume.
    # ---------------------------------------------------------------------------

    async def _resume_harness_engine_sse(
        *,
        harness,
        harness_run_id: str,
        thread_id: str,
        user_id: str,
        user_email: str,
        token: str,
        sys_settings: dict,
        start_phase_index: int,
        cancellation_event: asyncio.Event,
    ):
        """Yields SSE-encoded events from run_harness_engine resumed at start_phase_index."""
        registry = await _get_or_build_conversation_registry(thread_id, sys_settings)
        async for evt in run_harness_engine(
            harness=harness,
            harness_run_id=harness_run_id,
            thread_id=thread_id,
            user_id=user_id,
            user_email=user_email,
            token=token,
            registry=registry,
            cancellation_event=cancellation_event,
            start_phase_index=start_phase_index,
        ):
            yield f"data: {json.dumps(evt)}\n\n"
    ```

    **Edit 3: Insert HIL resume branch BEFORE the 409 block.**

    The branch MUST be placed:
    - AFTER the Phase 19 ask_user resume branch (lines ~283-360)
    - BEFORE the 409 block (line ~366)

    Insert:
    ```python
    # Phase 21 / D-01, D-02: HIL resume detection.
    # When a harness is paused on an llm_human_input phase, treat the next user
    # message as the HIL answer: write to phase.workspace_output, advance phase
    # via resume_from_pause (NOT advance_phase — its guard rejects paused rows),
    # then resume run_harness_engine from current_phase + 1.
    if settings.harness_enabled:
        paused_run = await harness_runs_service.get_active_run(
            thread_id=body.thread_id, token=user["token"]
        )
        if paused_run is not None and paused_run.get("status") == "paused":
            harness_type = paused_run["harness_type"]
            current_phase_idx = paused_run["current_phase"]
            try:
                h = harness_registry.get_harness(harness_type)
            except Exception as exc:
                logger.warning(
                    "HIL resume: harness lookup failed type=%s: %s", harness_type, exc
                )
                h = None
            if h is not None and 0 <= current_phase_idx < len(h.phases):
                current_phase = h.phases[current_phase_idx]

                # 1. Write user's answer to phase.workspace_output
                ws = WorkspaceService(token=user["token"])
                try:
                    await ws.write_text_file(
                        body.thread_id,
                        current_phase.workspace_output,
                        body.message,
                        source="harness",
                    )
                except Exception as exc:
                    logger.warning(
                        "HIL resume: workspace write failed phase=%s: %s",
                        current_phase.name, exc,
                    )

                # 2. Persist user's message with harness_mode tag
                client = get_supabase_authed_client(user["token"])
                try:
                    client.table("messages").insert({
                        "thread_id": body.thread_id,
                        "user_id": user["id"],
                        "role": "user",
                        "content": body.message,
                        "harness_mode": harness_type,
                        "parent_message_id": getattr(body, "parent_message_id", None),
                    }).execute()
                except Exception as exc:
                    logger.warning("HIL resume: messages insert failed: %s", exc)

                # 3. Advance harness phase via resume_from_pause (BLOCKER-2 fix —
                #    advance_phase's transactional guard rejects paused rows).
                try:
                    updated_row = await harness_runs_service.resume_from_pause(
                        run_id=paused_run["id"],
                        new_phase_index=current_phase_idx + 1,
                        phase_results_patch={
                            str(current_phase_idx): {
                                "phase_name": current_phase.name,
                                "output": {"answer": body.message[:500]},
                            }
                        },
                        user_id=user["id"],
                        user_email=user.get("email", ""),
                        token=user["token"],
                    )
                except Exception as exc:
                    logger.error(
                        "HIL resume: resume_from_pause failed run=%s: %s",
                        paused_run["id"], exc,
                    )
                    return JSONResponse(
                        status_code=500,
                        content={"error": "hil_resume_advance_failed", "detail": str(exc)[:300]},
                    )

                # 3b. Stale-state guard — None means the row was no longer paused
                #     (cancelled/completed/failed in a parallel request).
                if updated_row is None:
                    logger.warning(
                        "HIL resume: resume_from_pause returned None run=%s — row no longer paused",
                        paused_run["id"],
                    )
                    return JSONResponse(
                        status_code=500,
                        content={
                            "error": "hil_resume_state_invalid",
                            "detail": "harness run is no longer paused (cancelled or terminal)",
                        },
                    )

                # 4. Resume the engine from the next phase via the new
                #    _resume_harness_engine_sse wrapper. The wrapper internally
                #    reuses _get_or_build_conversation_registry (chat.py:1695) —
                #    B4 invariant: never mint a fresh registry on resume.
                cancellation_event = asyncio.Event()
                sys_settings = get_system_settings()
                return StreamingResponse(
                    _resume_harness_engine_sse(
                        harness=h,
                        harness_run_id=paused_run["id"],
                        thread_id=body.thread_id,
                        user_id=user["id"],
                        user_email=user.get("email", ""),
                        token=user["token"],
                        sys_settings=sys_settings,
                        start_phase_index=current_phase_idx + 1,
                        cancellation_event=cancellation_event,
                    ),
                    media_type="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
                )
    ```

    **Tests** — `backend/tests/routers/test_chat_hil_resume.py`. Mirror imports + fixtures from `test_chat_harness_routing.py`. Use FastAPI `TestClient` and dependency-override for `get_current_user` and the supabase client. Patch:
    - `app.routers.chat.harness_runs_service.get_active_run` (AsyncMock with parametrized return)
    - `app.routers.chat.harness_runs_service.resume_from_pause` (AsyncMock recording calls — RETURNS the updated row dict by default; for Test 7 returns None)
    - `app.routers.chat.harness_runs_service.advance_phase` (AsyncMock — assert it is NEVER called in any HIL test, BLOCKER-2 regression)
    - `app.routers.chat.harness_registry.get_harness` (returns a fake HarnessDefinition with phases[2].workspace_output="test-answer.md", phases[2].name="ask-label")
    - `app.routers.chat.WorkspaceService.write_text_file` (AsyncMock recording calls)
    - `app.routers.chat.run_harness_engine` (replaced with MagicMock async generator yielding `{"type": "harness_complete", "status": "completed"}`)
    - the supabase client returned by `get_supabase_authed_client` (MagicMock recording `.table().insert().execute()` calls)

    For test 6 (parametrized): use `pytest.mark.parametrize("status,expected_code", [("pending", 409), ("running", 409), ("paused", 200), (None, 200)])`.

    Run order:
    1. RED: write all 7 tests; run `cd backend && source venv/bin/activate && pytest tests/routers/test_chat_hil_resume.py -x`. ALL must fail.
    2. GREEN: implement chat.py edits (3 of them — 409 condition, _resume_harness_engine_sse helper, HIL resume branch). Rerun. ALL must pass.
    3. Confirm no regression: `pytest backend/tests/routers/test_chat_harness_routing.py` exits 0 (existing 409 path still works for pending/running).
    4. Manual smoke: `cd backend && python -c "from app.main import app; print('OK')"` prints `OK` (PostToolUse hook will run automatically too).
    5. Atomic commit: `gsd-sdk query commit "feat(21-04): chat.py HIL resume branch + 409 condition change + _resume_harness_engine_sse helper" --files backend/app/routers/chat.py backend/tests/routers/test_chat_hil_resume.py`.
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pytest tests/routers/test_chat_hil_resume.py tests/routers/test_chat_harness_routing.py -v --tb=short</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "Phase 21 / D-01, D-02: HIL resume detection" backend/app/routers/chat.py` returns 1.
    - `grep -c 'paused_run.get("status") == "paused"' backend/app/routers/chat.py` returns 1.
    - `grep -c 'active_harness.get("status") in ("pending", "running")' backend/app/routers/chat.py` returns 1 (WARNING-5 fix — replaces brittle awk pipeline with positive grep on the exact 409 condition).
    - `grep -c "def _resume_harness_engine_sse" backend/app/routers/chat.py` returns 1 (BLOCKER-5 fix — the NEW resume SSE helper exists).
    - `grep -c "_resume_harness_engine_sse" backend/app/routers/chat.py` returns >= 2 (definition + invocation in resume branch).
    - `grep -c "_get_or_build_conversation_registry" backend/app/routers/chat.py` returns >= 2 (existing definition at line 1695 + new use inside _resume_harness_engine_sse — WARNING-4 fix replacing the placeholder _load_conversation_registry / _load_parent_registry).
    - `grep -c "_load_conversation_registry\|_load_parent_registry" backend/app/routers/chat.py` returns 0 (no placeholder symbols leak through).
    - `grep -c 'harness_runs_service\.resume_from_pause' backend/app/routers/chat.py` returns >= 1 (BLOCKER-2 fix — uses resume_from_pause, not advance_phase).
    - `grep -c "hil_resume_state_invalid" backend/app/routers/chat.py` returns >= 1 (stale-state guard).
    - `grep -c "start_phase_index=current_phase_idx + 1" backend/app/routers/chat.py` returns 1.
    - `grep -c '"harness_mode": harness_type' backend/app/routers/chat.py` returns >= 1.
    - `pytest backend/tests/routers/test_chat_hil_resume.py` exits 0 with all 7 tests passing.
    - `pytest backend/tests/routers/test_chat_harness_routing.py` exits 0 (no regression on 409 path).
    - `cd backend && python -c "from app.main import app; print('OK')"` prints `OK`.
  </acceptance_criteria>
  <done>
    HIL resume branch detects paused harness runs, writes the answer to workspace, persists tagged user message, calls resume_from_pause (not advance_phase) and checks the return value, then resumes engine via the NEW _resume_harness_engine_sse helper which reuses _get_or_build_conversation_registry. 409 block correctly excludes paused. All 7 tests green; no regression in pre-existing chat-harness routing tests.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| user message body → workspace file content | trusted within RLS scope (user owns the thread); content cap enforced by WorkspaceService |
| HIL branch → run_harness_engine | parent JWT inherited (SEC-02) |
| paused_run lookup → harness_runs DB | RLS-scoped; user can only see their own thread's runs |
| resume registry load | reuses _get_or_build_conversation_registry (B4 invariant); no fresh egress filter on resume |
| resume_from_pause stale state | None return value triggers 500 — race-safe |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-21-04-01 | Spoofing | non-owner user resumes someone else's paused run | mitigate | get_active_run is RLS-scoped (.eq thread_id only matches threads the JWT can read); user_id implicit via the JWT. Forged thread_ids return None. |
| T-21-04-02 | Tampering | path traversal via phase.workspace_output (developer-defined) | mitigate | WorkspaceService.write_text_file calls validate_workspace_path before write; rejects ../ traversal. |
| T-21-04-03 | DoS / spam | user spams paused thread to retrigger resume | mitigate | The first resume call advances current_phase from N to N+1 and changes status to 'running' via resume_from_pause's transactional guard. A second message arrives after status='running' and falls into the 409 block (or normal flow if engine finishes fast). resume_from_pause's `.in_("status", ["paused"])` guard rejects double-resume. No infinite resume loop. |
| T-21-04-04 | Repudiation | which user replied? | mitigate | messages insert records user_id from JWT; harness_mode=harness.name; resume_from_pause logs an audit_service entry; full audit trail. |
| T-21-04-05 | Information Disclosure | egress filter bypass on resume LLM calls | mitigate | _resume_harness_engine_sse calls _get_or_build_conversation_registry (line 1695) — the same single-registry helper used by gatekeeper. The egress filter wraps all subsequent LLM calls in run_harness_engine. B4 invariant preserved. |
| T-21-04-06 | Elevation | start_phase_index attacker control | accept | start_phase_index = current_phase_idx + 1 derived from the RLS-scoped paused_run row. Attacker would need to forge a paused row in another user's thread, which RLS prevents. |
| T-21-04-07 | Race | resume_from_pause races with cancel/timeout | mitigate | resume_from_pause's transactional guard `.in_("status", ["paused"])` returns None when row is no longer paused; the resume branch checks the return and surfaces 500 with hil_resume_state_invalid (Test 7 covers). |
</threat_model>

<verification>
- 7 HIL resume tests pass (including BLOCKER-2 stale-state guard regression).
- Pre-existing chat-harness routing tests still pass.
- `from app.main import app` imports clean.
- 409 block now excludes paused; HIL resume branch correctly inserted before 409; new _resume_harness_engine_sse helper present near line 1724.
- Atomic commit landed.
</verification>

<success_criteria>
A user reply to a paused HIL harness produces an SSE stream that resumes the engine from the next phase, with the answer persisted in both workspace and messages table, partial results in phase_results, and the registry loaded once via _get_or_build_conversation_registry. 409 conflict still blocks pending/running runs but no longer blocks paused. Race-safe via resume_from_pause return-value check.
</success_criteria>

<output>
After completion, create `.planning/phases/21-batched-parallel-sub-agents-human-in-the-loop/21-04-SUMMARY.md`
</output>
</content>
</invoke>