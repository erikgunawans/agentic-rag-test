---
phase: 21-batched-parallel-sub-agents-human-in-the-loop
plan: 06
type: execute
wave: 5
depends_on: [02, 03, 04]
files_modified:
  - backend/app/harnesses/smoke_echo.py
  - backend/tests/services/test_harness_engine_smoke_phase21.py
autonomous: true
requirements:
  - BATCH-01  # E2E confirmation that items file is parsed
  - BATCH-02  # E2E confirmation of asyncio.gather concurrency
  - BATCH-03  # E2E confirmation of batch_size from PhaseDefinition
  - BATCH-04  # E2E confirmation of real-time SSE streaming
  - BATCH-05  # E2E confirmation of JSONL accumulation
  - BATCH-06  # E2E confirmation of item-level events
  - BATCH-07  # E2E confirmation of mid-batch resume
  - HIL-01    # E2E confirmation that informed question is generated
  - HIL-02    # E2E confirmation question streams as deltas
  - HIL-03    # E2E confirmation harness pauses
  - HIL-04    # E2E confirmation resume writes answer + advances + continues
must_haves:
  truths:
    - "smoke_echo.py extends from 2 phases to 4: existing Phase 1 'echo' (programmatic — UNCHANGED) + existing Phase 2 'summarize' (llm_single — UNCHANGED) + NEW Phase 3 'ask-label' (llm_human_input) + NEW Phase 4 'batch-process' (llm_batch_agents, batch_size=2)."
    - "Phase 1 'echo' programmatic executor is EXTENDED to ALSO write a synthetic 3-item JSON array to workspace at 'test-items.md' (so Phase 4 has input). Existing 'echo.md' write is preserved."
    - "Phase 3 'ask-label' uses system_prompt_template that asks the LLM to produce one short clarifying question; workspace_inputs=['echo.md']; workspace_output='test-answer.md'; timeout_seconds=86400 (24h pause budget)."
    - "Phase 4 'batch-process' uses tools=[]; system_prompt_template asks the sub-agent to echo back the item's label; workspace_inputs=['test-items.md']; workspace_output='test-batch.json'; batch_size=2 (3 items at batch_size=2 → 2 batches: [items 0,1] then [item 2]); timeout_seconds=600."
    - "smoke harness remains gated behind settings.harness_smoke_enabled (Phase 20 flag — no new flag in Phase 21)."
    - "End-to-end test runs the 4-phase smoke harness with mocked LLM + mocked sub_agent_loop and verifies the full SSE event sequence: phase_start(0)/_complete → phase_start(1)/_complete → phase_start(2) + delta+ + harness_human_input_required + harness_complete{status=paused} → (resume) phase_start(3) + batch_start + 3×item_start + 3×item_complete + batch_start + batch_complete + phase_complete + harness_complete{status=completed}."
    - "End-to-end test verifies WorkspaceService recorded writes: echo.md, summary.json, test-items.md (Phase 1 dual write), test-answer.md (HIL resume), test-batch.jsonl (3 lines), test-batch.json (sorted merge)."
    - "End-to-end test verifies harness_runs DB lifecycle: pending → running → paused (after Phase 3 yield) → running (after resume) → completed."
    - "Test 9 (WARNING-7 regression) drives the FULL HIL→batch flow through the chat router via FastAPI TestClient (NOT direct engine invocation): POSTs the user reply to /chat/stream against a paused harness and asserts the workspace write, resume_from_pause call, run_harness_engine resume invocation, and final harness_runs.status='completed' all happen via the actual chat.py code path from Plan 21-04."
  artifacts:
    - path: "backend/app/harnesses/smoke_echo.py"
      provides: "Extended 4-phase smoke harness exercising all 5 PhaseTypes (programmatic, llm_single, llm_human_input, llm_batch_agents — llm_agent is exercised in Phase 22)"
      contains: "batch-process"
    - path: "backend/tests/services/test_harness_engine_smoke_phase21.py"
      provides: "End-to-end pytest verifying full Phase 21 flow against the 4-phase smoke harness — includes Test 9 router-level TestClient pipeline"
      contains: "test_smoke_e2e_full_hil_resume_then_batch"
  key_links:
    - from: "smoke_echo SMOKE_ECHO definition"
      to: "phases list"
      via: "4 PhaseDefinition entries"
      pattern: "PhaseDefinition"
    - from: "Phase 1 _phase1_echo executor"
      to: "test-items.md workspace write"
      via: "synthetic 3-item JSON array generation"
      pattern: "test-items.md"
    - from: "smoke_echo registration"
      to: "settings.harness_smoke_enabled"
      via: "feature flag gate (Phase 20)"
      pattern: "harness_smoke_enabled"
    - from: "Test 9 (router-level pipeline)"
      to: "FastAPI TestClient POST /chat/stream"
      via: "exercises chat.py HIL resume branch from Plan 21-04 verbatim"
      pattern: "TestClient"
---

<objective>
Extend the Phase 20 smoke harness from 2 phases to 4 phases so the engine work in Plans 21-02 (HIL) and 21-03 (BATCH) can be E2E-validated without waiting for Phase 22's Contract Review harness. Add an end-to-end test that drives the full 4-phase flow including the chat.py HIL resume branch (Plan 21-04).

Purpose: Plan 21-02 unit-tested LLM_HUMAN_INPUT, Plan 21-03 unit-tested LLM_BATCH_AGENTS, Plan 21-04 unit-tested the chat router HIL branch — but no test currently exercises the FULL pause-resume-batch flow against a real harness definition. This plan ships that test plus the smoke harness extension that makes it possible. WARNING-7 also requires a router-level pipeline test (Test 9) that exercises the chat.py HIL branch via TestClient instead of direct engine invocation.
Output: smoke_echo.py extension + 1 E2E pytest module covering all 11 Phase 21 requirements end-to-end + 1 router-level TestClient pipeline test.
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
@.planning/phases/21-batched-parallel-sub-agents-human-in-the-loop/21-03-batch-dispatcher-asyncio-queue-PLAN.md
@.planning/phases/21-batched-parallel-sub-agents-human-in-the-loop/21-04-chat-hil-resume-branch-and-409-PLAN.md
@CLAUDE.md
@backend/app/harnesses/smoke_echo.py
@backend/app/harnesses/types.py
@backend/app/services/harness_engine.py
@backend/tests/services/test_harness_engine.py
@backend/tests/routers/test_chat_harness_routing.py

<interfaces>
<!-- Patterns extracted from existing smoke_echo.py and types.py. -->

From backend/app/harnesses/smoke_echo.py (existing 2-phase):
```python
async def _phase1_echo(
    *, inputs: dict[str, str], token: str, thread_id: str, harness_run_id: str
) -> dict:
    ws = WorkspaceService(token=token)
    files = await ws.list_files(thread_id)
    echo_content = "..."
    await ws.write_text_file(thread_id, "echo.md", echo_content, source="harness")
    return {"content": echo_content, "echo_count": ...}

class EchoSummary(BaseModel):
    echo_count: int
    summary: str

SMOKE_ECHO = HarnessDefinition(
    name="smoke-echo",
    display_name="Smoke Echo",
    prerequisites=HarnessPrerequisites(...),
    phases=[
        PhaseDefinition(
            name="echo",
            phase_type=PhaseType.PROGRAMMATIC,
            executor=_phase1_echo,
            workspace_output="echo.md",
            timeout_seconds=60,
        ),
        PhaseDefinition(
            name="summarize",
            phase_type=PhaseType.LLM_SINGLE,
            system_prompt_template="...",
            tools=[],
            workspace_inputs=["echo.md"],
            workspace_output="summary.json",
            output_schema=EchoSummary,
            timeout_seconds=120,
        ),
    ],
)

if settings.harness_smoke_enabled:
    harness_registry.register(SMOKE_ECHO)
```

From backend/app/harnesses/types.py:
```python
class PhaseType(str, Enum):
    PROGRAMMATIC = "programmatic"
    LLM_SINGLE = "llm_single"
    LLM_AGENT = "llm_agent"
    LLM_BATCH_AGENTS = "llm_batch_agents"
    LLM_HUMAN_INPUT = "llm_human_input"
```

From backend/tests/routers/test_chat_harness_routing.py (the analog for Test 9):
- TestClient pattern lines 17-49 (`_make_prereqs` helper).
- Dependency-override pattern: `app.dependency_overrides[get_current_user] = ...`.
- Mock supabase clients for messages insert + harness_runs queries.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Extend smoke_echo.py to 4 phases (HIL + batch) + extend Phase 1 to write synthetic items file + 9 E2E test cases including router-level TestClient pipeline (RED → GREEN)</name>
  <files>backend/app/harnesses/smoke_echo.py, backend/tests/services/test_harness_engine_smoke_phase21.py</files>
  <read_first>
    - backend/app/harnesses/smoke_echo.py — full file. Critical lines: 39-74 (_phase1_echo executor — extension target), 78-126 (SMOKE_ECHO definition with 2 phases), bottom (registration gated on harness_smoke_enabled).
    - backend/app/harnesses/types.py — confirm PhaseType.LLM_HUMAN_INPUT and PhaseType.LLM_BATCH_AGENTS values; confirm PhaseDefinition supports `batch_size` and `timeout_seconds`.
    - backend/app/services/harness_engine.py — confirm post-Plan-21-02 and 21-03 state: HumanInputQuestion model exists, EVT_BATCH_ITEM_START/COMPLETE constants exist, both dispatchers in place.
    - backend/tests/services/test_harness_engine.py — full file, especially mock pattern for run_harness_engine + WorkspaceService.
    - backend/tests/routers/test_chat_harness_routing.py — the canonical TestClient + dependency-override pattern Test 9 must mirror.
    - backend/tests/routers/test_chat_hil_resume.py (created by Plan 21-04) — Test 9 builds on the HIL resume fixtures defined here; confirm its mock-patching style for harness_runs_service.get_active_run / resume_from_pause.
    - .planning/phases/21-batched-parallel-sub-agents-human-in-the-loop/21-PATTERNS.md — section "harnesses/smoke_echo.py — extend 2 → 4 phases" (lines 388-440).
    - .planning/phases/21-batched-parallel-sub-agents-human-in-the-loop/21-CONTEXT.md — Specifics section: smoke harness Phase 3 + Phase 4 details.
  </read_first>
  <behavior>
    Tests in `backend/tests/services/test_harness_engine_smoke_phase21.py`:

    - Test 1 `test_smoke_harness_has_4_phases`: import SMOKE_ECHO; assert len(phases) == 4; assert phase_types == [PROGRAMMATIC, LLM_SINGLE, LLM_HUMAN_INPUT, LLM_BATCH_AGENTS].
    - Test 2 `test_phase1_echo_writes_synthetic_items_file`: invoke _phase1_echo with mock WorkspaceService; assert at least two write_text_file calls, one for "echo.md" AND one for "test-items.md" with content that JSON-parses to a list of length 3.
    - Test 3 `test_smoke_e2e_runs_through_phase_3_and_pauses`: with all backing services mocked (LLM returns {"question": "What label?"}, harness_runs_service.pause records call), drive run_harness_engine through phases 0-2; collect events; assert event sequence ends with EVT_HUMAN_INPUT_REQUIRED then EVT_COMPLETE with status="paused"; assert harness_runs_service.pause was called once.
    - Test 4 `test_smoke_e2e_resume_writes_answer`: simulate HIL resume by directly calling run_harness_engine with start_phase_index=3 (after writing test-answer.md to mock workspace); assert events include EVT_PHASE_START with phase_index=3 (NOT phase_index=0,1,2 which are skipped).
    - Test 5 `test_smoke_e2e_batch_phase_emits_2_batches`: run from start_phase_index=3; mock run_sub_agent_loop to yield per-item terminals; assert 2 EVT_BATCH_START events (batches [items 0,1] and [item 2]) AND 3 EVT_BATCH_ITEM_START + 3 EVT_BATCH_ITEM_COMPLETE.
    - Test 6 `test_smoke_e2e_batch_appends_3_jsonl_lines`: assert WorkspaceService.append_line called exactly 3 times against "test-batch.jsonl".
    - Test 7 `test_smoke_e2e_batch_writes_merged_json`: assert WorkspaceService.write_text_file called with file_path="test-batch.json" and content that JSON-parses to a 3-element sorted list.
    - Test 8 `test_smoke_e2e_full_hil_resume_then_batch`: full pipeline test (engine-direct) — drive engine to pause, then resume from phase 3, drain to terminal completed; assert final EVT_COMPLETE has status="completed" and the full set of 4 phase_complete events were emitted overall (combining both invocations).
    - Test 9 `test_router_pipeline_hil_resume_into_batch` (WARNING-7 regression): router-level pipeline via FastAPI TestClient.
      - Setup: a paused harness_runs row exists at current_phase=2 (the ask-label HIL phase). Mock `harness_runs_service.get_active_run` to return `{"id": "h-1", "status": "paused", "harness_type": "smoke-echo", "current_phase": 2}`. Mock `harness_runs_service.resume_from_pause` to return the updated row dict (status='running', current_phase=3). Mock `harness_registry.get_harness("smoke-echo")` to return the 4-phase SMOKE_ECHO. Mock `WorkspaceService.write_text_file`, `WorkspaceService.read_file`, `WorkspaceService.append_line` as recording AsyncMocks. Mock `run_sub_agent_loop` (or `app.services.harness_engine.run_sub_agent_loop`) to yield `{"_terminal_result": {"text": item["label"]}}` per call. Mock OpenRouterService client.
      - Action: TestClient POST `/chat/stream` with body `{thread_id: "t-1", message: "Test answer 123"}`.
      - Asserts:
        - Response 200, content-type text/event-stream.
        - `WorkspaceService.write_text_file` was called with `(thread_id="t-1", file_path="test-answer.md", content="Test answer 123", source="harness")`.
        - `harness_runs_service.resume_from_pause` was awaited once with `new_phase_index=3`.
        - `harness_runs_service.advance_phase` was NEVER called (BLOCKER-2 invariant).
        - At least one batch EVT_BATCH_START frame and 3 EVT_BATCH_ITEM_COMPLETE frames are observed in the streamed body.
        - The mocked `run_harness_engine` (or the real one if run inline) was driven with `start_phase_index=3`.
        - Final SSE frame is `data: {"type": "harness_complete", "status": "completed", ...}`.
      - This test exercises chat.py:`stream_chat` HIL resume branch + `_resume_harness_engine_sse` helper from Plan 21-04 VERBATIM, not by direct engine invocation.
  </behavior>
  <action>
    **Edit 1 — backend/app/harnesses/smoke_echo.py.**

    Extend `_phase1_echo` to also write `test-items.md`:

    ```python
    # Phase 21 / smoke harness — Phase 1 also seeds the items file Phase 4 will consume.
    SYNTHETIC_BATCH_ITEMS = [
        {"index": 0, "label": "alpha"},
        {"index": 1, "label": "beta"},
        {"index": 2, "label": "gamma"},
    ]

    async def _phase1_echo(
        *, inputs: dict[str, str], token: str, thread_id: str, harness_run_id: str
    ) -> dict:
        ws = WorkspaceService(token=token)
        # ... existing echo.md write (preserve verbatim) ...
        # NEW: write synthetic items file for Phase 4 batch consumer
        await ws.write_text_file(
            thread_id,
            "test-items.md",
            json.dumps(SYNTHETIC_BATCH_ITEMS, ensure_ascii=False),
            source="harness",
        )
        return {"content": echo_content, "echo_count": ..., "items_written": 3}
    ```

    Append two new PhaseDefinitions to `SMOKE_ECHO.phases`:

    ```python
    PhaseDefinition(
        name="ask-label",
        description="Ask the user what label to attach to the echo result.",
        phase_type=PhaseType.LLM_HUMAN_INPUT,
        system_prompt_template=(
            "You are a friendly assistant. Generate ONE short clarifying question "
            "(under 30 words) asking what label the user wants on the echo result. "
            "Respond as a JSON object {\"question\": \"...\"}."
        ),
        tools=[],
        workspace_inputs=["echo.md"],
        workspace_output="test-answer.md",
        timeout_seconds=86_400,   # 24h pause budget — HIL has no engine timeout, just a sane upper bound
    ),
    PhaseDefinition(
        name="batch-process",
        description="Process each synthetic item in parallel — echo back its label.",
        phase_type=PhaseType.LLM_BATCH_AGENTS,
        system_prompt_template=(
            "You are a focused worker. Echo back the item's label exactly as given. "
            "Respond with the label string only."
        ),
        tools=[],
        workspace_inputs=["test-items.md"],
        workspace_output="test-batch.json",
        batch_size=2,             # 3 items / batch_size=2 → 2 batches: [0,1] + [2]
        timeout_seconds=600,
    ),
    ```

    Confirm `if settings.harness_smoke_enabled: harness_registry.register(SMOKE_ECHO)` is unchanged.

    **Edit 2 — backend/tests/services/test_harness_engine_smoke_phase21.py.**

    Mirror the test mocking style from `test_harness_engine.py`. Key mocks:
    - `app.services.harness_engine.WorkspaceService` (MagicMock with stateful append_line and write_text_file recordings)
    - `app.services.harness_engine.harness_runs_service.pause` / `resume_from_pause` / `advance_phase` / `complete` (AsyncMocks)
    - `app.services.harness_engine.harness_runs_service.get_run_by_id` (AsyncMock returning {"status": "running"})
    - `app.services.harness_engine.or_svc.complete_with_tools` (AsyncMock returning {"content": '{"question": "What label?"}'} for HIL phase)
    - `app.services.harness_engine.run_sub_agent_loop` (AsyncMock yielding `{"_terminal_result": {"text": item["label"]}}` for each item)

    For Test 8 (full pipeline, engine-direct), the test invokes run_harness_engine TWICE:
    - First call: `start_phase_index=0`. Drives through Phases 1-3, ends with EVT_COMPLETE{status=paused}.
    - Between calls: simulate the HIL resume branch (Plan 21-04) by writing "test-answer.md" to the mock workspace.
    - Second call: `start_phase_index=3`. Drives through Phase 4 (batch). Ends with EVT_COMPLETE{status=completed}.

    Combine event lists from both calls; assert:
    - EVT_PHASE_START emitted for indices 0, 1, 2 in first call AND index 3 in second call (NOT 0, 1, 2 in second call — those are skipped via start_phase_index).
    - EVT_PHASE_COMPLETE emitted 4 times total.
    - EVT_HUMAN_INPUT_REQUIRED emitted exactly once.
    - EVT_BATCH_START emitted exactly twice (one per batch chunk).
    - EVT_BATCH_ITEM_START / EVT_BATCH_ITEM_COMPLETE each emitted exactly 3 times.

    For Test 9 (WARNING-7 regression — router-level pipeline):

    ```python
    from fastapi.testclient import TestClient
    from app.main import app
    from app.routers import chat as chat_router
    # ... reuse fixtures from test_chat_harness_routing.py and test_chat_hil_resume.py ...

    def test_router_pipeline_hil_resume_into_batch(monkeypatch):
        # 1. Mock dependency-override for get_current_user
        app.dependency_overrides[chat_router.get_current_user] = lambda: {
            "id": "u-1", "email": "u@example.com", "token": "tok-1", "role": "user",
        }

        # 2. Patch harness_runs_service to return a paused row
        get_active_run_mock = AsyncMock(return_value={
            "id": "h-1", "status": "paused", "harness_type": "smoke-echo", "current_phase": 2,
        })
        resume_from_pause_mock = AsyncMock(return_value={
            "id": "h-1", "status": "running", "harness_type": "smoke-echo", "current_phase": 3,
        })
        advance_phase_mock = AsyncMock()  # asserted to NEVER be called
        monkeypatch.setattr(chat_router.harness_runs_service, "get_active_run", get_active_run_mock)
        monkeypatch.setattr(chat_router.harness_runs_service, "resume_from_pause", resume_from_pause_mock)
        monkeypatch.setattr(chat_router.harness_runs_service, "advance_phase", advance_phase_mock)

        # 3. Patch harness_registry to return the 4-phase SMOKE_ECHO
        from app.harnesses.smoke_echo import SMOKE_ECHO
        monkeypatch.setattr(chat_router.harness_registry, "get_harness", lambda name: SMOKE_ECHO)

        # 4. Patch WorkspaceService methods
        write_text_file_mock = AsyncMock(return_value={"ok": True})
        read_file_mock = AsyncMock(side_effect=lambda thread_id, path: (
            {"content": json.dumps([{"index": i, "label": l} for i, l in enumerate(["alpha", "beta", "gamma"])])}
            if path == "test-items.md"
            else {"error": "file_not_found", "file_path": path}
        ))
        append_line_mock = AsyncMock(return_value={"ok": True})
        monkeypatch.setattr("app.routers.chat.WorkspaceService.write_text_file", write_text_file_mock)
        monkeypatch.setattr("app.services.harness_engine.WorkspaceService.read_file", read_file_mock)
        monkeypatch.setattr("app.services.harness_engine.WorkspaceService.append_line", append_line_mock)
        monkeypatch.setattr("app.services.harness_engine.WorkspaceService.write_text_file", AsyncMock(return_value={"ok": True}))

        # 5. Patch sub_agent_loop to yield per-item terminals
        async def fake_sub_agent_loop(*, description, **kwargs):
            yield {"_terminal_result": {"text": "echoed"}}
        monkeypatch.setattr("app.services.harness_engine.run_sub_agent_loop", fake_sub_agent_loop)

        # 6. POST to /chat/stream
        with TestClient(app) as client:
            response = client.post("/chat/stream", json={"thread_id": "t-1", "message": "Test answer 123"})
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")
            body = response.text

        # 7. Asserts
        write_text_file_mock.assert_any_call(
            "t-1", "test-answer.md", "Test answer 123", source="harness",
        )
        resume_from_pause_mock.assert_awaited_once()
        kwargs = resume_from_pause_mock.await_args.kwargs
        assert kwargs["new_phase_index"] == 3
        advance_phase_mock.assert_not_awaited()  # BLOCKER-2 invariant
        assert "harness_batch_start" in body
        assert body.count("harness_batch_item_complete") >= 3
        assert "harness_complete" in body
        assert '"status": "completed"' in body or "'status': 'completed'" in body

        app.dependency_overrides.clear()
    ```

    NOTE on test isolation: the `monkeypatch` calls target the symbol locations actually USED at runtime — verify these exact module paths during execution by reading chat.py imports + harness_engine.py imports. If `WorkspaceService` is imported at module top in chat.py, the monkeypatch path is `app.routers.chat.WorkspaceService.write_text_file`. If it is constructed via `from ... import` only inside harness_engine.py, patch the second location too. The test author MUST verify both binding sites.

    Run order:
    1. RED: write the 9 tests; `cd backend && source venv/bin/activate && pytest tests/services/test_harness_engine_smoke_phase21.py -x`. ALL must fail.
    2. GREEN: edit smoke_echo.py. Rerun. ALL must pass.
    3. Confirm no regression: `pytest backend/tests/services/test_harness_engine_smoke.py` (existing Phase 20 smoke test) exits 0; `pytest backend/tests/services/test_harness_engine.py backend/tests/services/test_harness_engine_human_input.py backend/tests/services/test_harness_engine_batch.py backend/tests/routers/test_chat_hil_resume.py` all exit 0.
    4. Manual import check: `cd backend && python -c "from app.harnesses.smoke_echo import SMOKE_ECHO; assert len(SMOKE_ECHO.phases) == 4; print('OK')"` prints `OK`.
    5. Atomic commit: `gsd-sdk query commit "test(21-06): extend smoke harness to 4 phases + E2E HIL+batch pipeline test + router TestClient regression" --files backend/app/harnesses/smoke_echo.py backend/tests/services/test_harness_engine_smoke_phase21.py`.
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pytest tests/services/test_harness_engine_smoke_phase21.py tests/services/test_harness_engine.py tests/services/test_harness_engine_human_input.py tests/services/test_harness_engine_batch.py tests/routers/test_chat_hil_resume.py -v --tb=short</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "PhaseType.LLM_HUMAN_INPUT" backend/app/harnesses/smoke_echo.py` returns 1.
    - `grep -c "PhaseType.LLM_BATCH_AGENTS" backend/app/harnesses/smoke_echo.py` returns 1.
    - `grep -c 'name="ask-label"' backend/app/harnesses/smoke_echo.py` returns 1.
    - `grep -c 'name="batch-process"' backend/app/harnesses/smoke_echo.py` returns 1.
    - `grep -c "test-items.md" backend/app/harnesses/smoke_echo.py` returns >= 2 (write call + workspace_inputs ref).
    - `grep -c "batch_size=2" backend/app/harnesses/smoke_echo.py` returns 1.
    - `grep -c "SYNTHETIC_BATCH_ITEMS" backend/app/harnesses/smoke_echo.py` returns >= 2 (declaration + use).
    - `grep -c "test_router_pipeline_hil_resume_into_batch" backend/tests/services/test_harness_engine_smoke_phase21.py` returns 1 (WARNING-7 fix — router-level TestClient pipeline test exists).
    - `grep -c "TestClient" backend/tests/services/test_harness_engine_smoke_phase21.py` returns >= 1 (Test 9 uses FastAPI TestClient, not direct engine invocation).
    - `cd backend && python -c "from app.harnesses.smoke_echo import SMOKE_ECHO; assert len(SMOKE_ECHO.phases) == 4; assert SMOKE_ECHO.phases[2].phase_type.value == 'llm_human_input'; assert SMOKE_ECHO.phases[3].phase_type.value == 'llm_batch_agents'; print('OK')"` prints `OK`.
    - `pytest backend/tests/services/test_harness_engine_smoke_phase21.py` exits 0 with all 9 tests passing.
    - `pytest backend/tests/services/test_harness_engine.py backend/tests/services/test_harness_engine_human_input.py backend/tests/services/test_harness_engine_batch.py backend/tests/routers/test_chat_hil_resume.py` exits 0 (no regression in any unit test).
    - `cd backend && python -c "from app.main import app; print('OK')"` prints `OK`.
  </acceptance_criteria>
  <done>
    smoke_echo registers a 4-phase harness covering all Phase 21 phase types. 9 E2E tests pass (8 engine-direct + 1 router-level TestClient pipeline); no regression in any prior test. The full Phase 21 pipeline (PROGRAMMATIC → LLM_SINGLE → LLM_HUMAN_INPUT pause → resume → LLM_BATCH_AGENTS) is verified end-to-end through BOTH the engine and the chat router code paths.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| smoke_echo registration → harness registry | gated on `settings.harness_smoke_enabled` (default False in production) |
| smoke harness LLM calls → cloud OpenRouter | egress filter applied identically to production harnesses (SEC-04) |
| Phase 1 synthetic items file → Phase 4 batch input | static developer-defined data; no user input path |
| Test 9 router-level pipeline → chat.py HIL branch | exercises the actual code path; no shortcut to the engine |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-21-06-01 | Elevation | smoke harness exposed in production | mitigate | `settings.harness_smoke_enabled` defaults to False; production env var controls visibility. Phase 20 D-16 invariant preserved. |
| T-21-06-02 | Information Disclosure | smoke harness LLM calls leak workspace context | mitigate | Egress filter is enforced at the dispatcher level (per Plans 21-02, 21-03 inheriting Phase 19 D-21). Smoke harness has no exception. |
| T-21-06-03 | Tampering | E2E test mocks could mask real bugs | mitigate | Test 9 (WARNING-7 fix) drives the chat router via TestClient — the actual chat.py HIL resume branch executes, only the outermost integration boundaries (LLM client, sub_agent_loop, supabase) are mocked. Phase 22 ships UAT coverage with real LLM. |
</threat_model>

<verification>
- 9 E2E smoke tests pass (8 engine-direct + 1 router-level TestClient).
- All prior Phase 21 unit tests still pass (Plans 21-01, 21-02, 21-03, 21-04 — no regression).
- Phase 20 smoke test (`test_harness_engine_smoke.py`) still passes — extension is additive.
- `from app.main import app` imports clean.
- Atomic commit landed.
</verification>

<success_criteria>
The 4-phase smoke harness drives a complete pipeline end-to-end: PROGRAMMATIC → LLM_SINGLE → LLM_HUMAN_INPUT (pause) → resume → LLM_BATCH_AGENTS (3 items in 2 batches). Test 9 specifically validates the chat router's HIL branch via FastAPI TestClient (not direct engine invocation). All 11 Phase 21 requirement IDs (BATCH-01..07, HIL-01..04) have at least one E2E observation in this test suite. Phase 21 is shippable.
</success_criteria>

<output>
After completion, create `.planning/phases/21-batched-parallel-sub-agents-human-in-the-loop/21-06-SUMMARY.md`
</output>
</content>
</invoke>