---
phase: 21-batched-parallel-sub-agents-human-in-the-loop
plan: 02
type: execute
wave: 2
depends_on: [01]
files_modified:
  - backend/app/services/harness_engine.py
  - backend/app/services/harness_runs_service.py
  - backend/tests/services/test_harness_engine_human_input.py
  - backend/tests/services/test_harness_runs_service_pause.py
autonomous: true
requirements:
  - HIL-01  # Informed-question generation via LLM, prior phase results inform it
  - HIL-02  # Question streams as delta events (chat bubble), NOT phase panel
  - HIL-03  # harness_runs.status transitions to 'paused' before SSE close
must_haves:
  truths:
    - "harness_runs_service.py exposes a NEW `async def pause(*, run_id, user_id, user_email, token) -> HarnessRunRecord | None` method that atomically transitions status='running' → 'paused' with transactional guard `.in_(\"status\", [\"running\"])`. Returns the updated row dict on success, None on guard rejection."
    - "harness_runs_service.py exposes a NEW `async def resume_from_pause(*, run_id, new_phase_index, phase_results_patch, user_id, user_email, token) -> HarnessRunRecord | None` method that atomically transitions status='paused' → 'running', sets current_phase=new_phase_index, and merges phase_results_patch into phase_results. Transactional guard `.in_(\"status\", [\"paused\"])`. Returns the updated row dict on success, None on guard rejection."
    - "Both new methods log via audit_service (action='harness_run_paused' / 'harness_run_resumed') for traceability (T-20-02-* analog)."
    - "run_harness_engine accepts new keyword-only parameter `start_phase_index: int = 0` with default 0 preserving byte-identical behavior for all existing callers."
    - "_run_harness_engine_inner phase loop skips phases whose index < start_phase_index — those are assumed already-complete from a prior run."
    - "EVT_BATCH_ITEM_START and EVT_BATCH_ITEM_COMPLETE constants are added to harness_engine.py module-level scope."
    - "PhaseType.LLM_HUMAN_INPUT branch in _dispatch_phase: (1) reads workspace_inputs via _read_workspace_files, (2) runs egress filter on outgoing payload (returns egress_blocked terminal if tripped), (3) makes one OpenRouter LLM call with response_format=json_schema against HumanInputQuestion Pydantic model, (4) yields delta events for the question text, (5) yields harness_human_input_required event with {type, question, workspace_output_path, harness_run_id}, (6) calls harness_runs_service.pause(...) BEFORE returning, (7) yields _terminal_phase_result with {paused: True, question} marker so the outer engine knows to halt."
    - "Outer _run_harness_engine_inner detects the `paused: True` terminal marker, yields a final harness_complete event with status='paused', then RETURNS (does NOT advance to next phase, does NOT call complete())."
    - "PHASE21_PENDING runtime stub for LLM_HUMAN_INPUT is REMOVED (the docstring mention at line 26 is unaffected); LLM_BATCH_AGENTS still has its PHASE21_PENDING runtime stub after this plan — Plan 21-03 finishes it."
    - "HumanInputQuestion Pydantic model exists with single field `question: str = Field(..., min_length=1, max_length=500)`."
    - "Egress filter pattern from LLM_SINGLE block (lines 503-514) is mirrored verbatim — no PII can reach the question-generation LLM call."
  artifacts:
    - path: "backend/app/services/harness_engine.py"
      provides: "LLM_HUMAN_INPUT dispatch branch + start_phase_index parameter + EVT_BATCH_ITEM_START/COMPLETE constants + HumanInputQuestion model + outer-loop paused-terminal handler"
      contains: "LLM_HUMAN_INPUT"
    - path: "backend/app/services/harness_runs_service.py"
      provides: "pause() + resume_from_pause() public methods (NEW — used by HIL flow in Plans 21-02 and 21-04)"
      contains: "async def pause"
    - path: "backend/tests/services/test_harness_runs_service_pause.py"
      provides: "Regression suite covering pause + resume_from_pause guards (5 cases)"
      contains: "test_pause_running_row_succeeds"
    - path: "backend/tests/services/test_harness_engine_human_input.py"
      provides: "6 test cases covering question generation, delta events, required event payload, paused-before-close, egress blocking, outer-loop terminal-paused handler"
      contains: "test_hil_question_generation_llm_call"
  key_links:
    - from: "_dispatch_phase LLM_HUMAN_INPUT branch"
      to: "harness_runs_service.pause"
      via: "DB pause transition before SSE close"
      pattern: "harness_runs_service\\.pause"
    - from: "_dispatch_phase LLM_HUMAN_INPUT branch"
      to: "egress_filter"
      via: "PII guard before outgoing LLM call"
      pattern: "egress_filter"
    - from: "_run_harness_engine_inner phase loop"
      to: "start_phase_index"
      via: "phase skip condition"
      pattern: "start_phase_index"
    - from: "_run_harness_engine_inner outer loop"
      to: "paused-terminal handler"
      via: "result.get('paused') branch yields harness_complete{status=paused} and returns"
      pattern: "result.get\\(\"paused\"\\)"
---

<objective>
Implement the `LLM_HUMAN_INPUT` phase dispatch branch in `harness_engine.py`, ship two new public methods (`pause` and `resume_from_pause`) on `harness_runs_service.py`, and extend `run_harness_engine` with the `start_phase_index` parameter that Plan 21-04's HIL resume branch passes. Replace the `PHASE21_PENDING` runtime stub for `LLM_HUMAN_INPUT` (the `LLM_BATCH_AGENTS` half stays stubbed; Plan 21-03 finishes it).

Purpose: This is the engine half of the HIL flow (HIL-01..03) plus the service-layer state machine extension that BOTH this plan (pause) AND Plan 21-04 (resume) require. The dispatcher runs an LLM call that produces an informed question from prior phase results, streams it as normal chat-bubble delta events, transitions the harness DB row to `paused` via the new `pause()` helper, and exits with a terminal marker that tells the outer loop "do not advance — wait for resume."
Output: Engine modifications + HumanInputQuestion Pydantic model + new pause/resume_from_pause service methods + regression tests for the new service methods + 6 unit tests covering all HIL-01..03 paths and the outer-loop paused handler.
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
@CLAUDE.md
@backend/app/services/harness_engine.py
@backend/app/services/harness_runs_service.py
@backend/app/services/workspace_service.py
@backend/app/harnesses/types.py
@backend/tests/services/test_harness_engine.py

<interfaces>
<!-- All interfaces extracted directly from existing code (verified during planning). -->

From backend/app/services/harness_engine.py:
```python
EVT_PHASE_START = "harness_phase_start"
EVT_PHASE_COMPLETE = "harness_phase_complete"
EVT_PHASE_ERROR = "harness_phase_error"
EVT_COMPLETE = "harness_complete"
EVT_BATCH_START = "harness_batch_start"            # line 84 — Phase 21
EVT_BATCH_COMPLETE = "harness_batch_complete"      # line 85 — Phase 21
EVT_HUMAN_INPUT_REQUIRED = "harness_human_input_required"  # line 86 — Phase 21

async def run_harness_engine(
    *,
    harness: HarnessDefinition,
    harness_run_id: str,
    thread_id: str,
    user_id: str,
    user_email: str,
    token: str,
    registry,
    cancellation_event: asyncio.Event,
) -> AsyncIterator[dict]:
    ...

# _run_harness_engine_inner: phase loop at line 201 — `for phase_index, phase in enumerate(harness.phases):`
# _dispatch_phase: PHASE21_PENDING runtime stub at lines 692-698 (line 697 is the `"code": "PHASE21_PENDING"` literal)
# PHASE21_PENDING docstring mention at line 26 (NOT a runtime stub — unaffected by edits in this plan)
# LLM_SINGLE egress filter pattern: lines 503-514
# LLM_SINGLE Pydantic schema pattern: lines 516-558
# Outer-loop terminal handling: lines 309-393 (`_terminal_phase_result` -> advance_phase -> next phase)
```

From backend/app/services/harness_runs_service.py (VERIFIED — only these public methods exist):
```python
ACTIVE_STATUSES: tuple[str, ...] = ("pending", "running", "paused")

# Existing public API (verified):
async def start_run(...) -> str
async def get_active_run(*, thread_id: str, token: str) -> HarnessRunRecord | None
async def get_run_by_id(*, run_id: str, token: str) -> HarnessRunRecord | None
async def get_latest_for_thread(*, thread_id: str, token: str) -> HarnessRunRecord | None
async def advance_phase(*, run_id, new_phase_index, phase_results_patch, token) -> bool
    # transactional guard at line 244: .in_("status", ["pending", "running"])
    # ⚠ This guard REJECTS rows in 'paused' status. HIL resume MUST use the new
    #   resume_from_pause() helper instead of advance_phase().
async def complete(*, run_id, user_id, user_email, token) -> bool
async def fail(*, run_id, user_id, user_email, error_detail, token) -> bool
async def cancel(*, run_id, user_id, user_email, token) -> bool

# NO `pause` method exists. NO `transition_status` method exists.
# This plan ADDS pause() and resume_from_pause() — the HIL flow's two missing pieces.
```

From backend/app/harnesses/types.py:
```python
class PhaseType(str, Enum):
    PROGRAMMATIC = "programmatic"
    LLM_SINGLE = "llm_single"
    LLM_AGENT = "llm_agent"
    LLM_BATCH_AGENTS = "llm_batch_agents"
    LLM_HUMAN_INPUT = "llm_human_input"

@dataclass(frozen=True, slots=True)
class PhaseDefinition:
    name: str
    description: str
    phase_type: PhaseType
    system_prompt_template: str
    tools: list[str] = field(default_factory=list)
    workspace_inputs: list[str] = field(default_factory=list)
    workspace_output: str = ""
    output_schema: type[BaseModel] | None = None
    batch_size: int = 5
    timeout_seconds: int = 120
    # ... post_execute, validator, etc.
```

From backend/app/services/redaction/egress.py:
```python
def egress_filter(payload: str, registry, _) -> EgressResult:
    """Returns object with .tripped boolean."""
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 0: Add pause() and resume_from_pause() helpers to harness_runs_service.py + 5 regression tests (RED → GREEN)</name>
  <files>backend/app/services/harness_runs_service.py, backend/tests/services/test_harness_runs_service_pause.py</files>
  <read_first>
    - backend/app/services/harness_runs_service.py — full file. Critical reference patterns: `cancel()` at lines 342-378 (transactional-guard analog — same shape: select-eq-id, .in_("status", [...]), .execute(), audit_service.log_action). `advance_phase()` at lines 194-254 (phase_results merge pattern — `merged = {**current_phase_results, **phase_results_patch}` is the model resume_from_pause MUST mirror).
    - backend/tests/services/test_harness_runs_service.py — read end-to-end. Reuse the supabase-client mocking style (MagicMock chained `.table().update().eq().in_().execute()`, return value's `.data` field).
  </read_first>
  <behavior>
    Tests in `backend/tests/services/test_harness_runs_service_pause.py`:

    - Test 1 `test_pause_running_row_succeeds`: mock supabase returns `result.data = [{"id": "x", "status": "paused", ...}]`; call `pause(run_id="x", ...)`; assert returned dict is non-None and has `status="paused"`. Assert `.update({"status": "paused"})` was called and the chained `.in_("status", ["running"])` guard was applied.
    - Test 2 `test_pause_pending_row_is_no_op`: mock supabase returns `result.data = []` (guard rejected); call `pause(...)`; assert returned None.
    - Test 3 `test_pause_paused_row_is_no_op`: mock returns empty data (already paused, guard `.in_(["running"])` rejects); assert returned None.
    - Test 4 `test_resume_from_pause_paused_row_succeeds`: mock returns `result.data = [{"id": "x", "status": "running", "current_phase": 3, "phase_results": {"2": {"answer": "..."}}}]`; call `resume_from_pause(run_id="x", new_phase_index=3, phase_results_patch={"2": {"answer": "the reply"}}, ...)`; assert returned dict has `status="running"` and `current_phase=3`. Assert the update payload merged the patch into existing phase_results (not overwritten). Assert the chained `.in_("status", ["paused"])` guard was applied.
    - Test 5 `test_resume_from_pause_running_row_is_no_op`: mock returns empty data (guard rejected — row is running, not paused); assert returned None.
  </behavior>
  <action>
    Edit `backend/app/services/harness_runs_service.py`. Append BOTH methods at the bottom of the file (after `cancel`).

    ```python
    async def pause(
        *,
        run_id: str,
        user_id: str,
        user_email: str,
        token: str,
    ) -> HarnessRunRecord | None:
        """Mark a harness run as paused.

        Phase 21 / HIL-03: called by harness_engine LLM_HUMAN_INPUT dispatcher
        before yielding harness_complete{status=paused}. Transactional guard
        .in_("status", ["running"]) ensures we only pause an actually-running row;
        attempting to pause a pending/paused/terminal row returns None (caller
        should treat as a no-op signal).

        Args:
            run_id:     UUID of the harness_runs row.
            user_id:    auth.users UUID for audit log.
            user_email: User's email for audit log.
            token:      JWT access token for RLS-scoped client.

        Returns:
            The updated HarnessRunRecord on success; None if guard rejected.
        """
        client = get_supabase_authed_client(token)
        result = (
            client.table("harness_runs")
            .update({"status": "paused"})
            .eq("id", run_id)
            .in_("status", ["running"])  # transactional guard — only running can pause
            .execute()
        )
        if not result.data:
            logger.warning(
                "pause affected 0 rows run_id=%s — possibly not running",
                run_id,
            )
            return None
        audit_service.log_action(
            user_id=user_id,
            user_email=user_email,
            action="harness_run_paused",
            resource_type="harness_runs",
            resource_id=run_id,
        )
        return result.data[0]


    async def resume_from_pause(
        *,
        run_id: str,
        new_phase_index: int,
        phase_results_patch: dict[str, Any],
        user_id: str,
        user_email: str,
        token: str,
    ) -> HarnessRunRecord | None:
        """Resume a paused harness run, advancing the phase and merging results.

        Phase 21 / HIL-04: called by chat.py HIL resume branch (Plan 21-04) after
        the user answers the paused question. Atomically transitions paused →
        running, sets current_phase = new_phase_index, and deep-merges
        phase_results_patch into existing phase_results JSONB.

        Transactional guard .in_("status", ["paused"]) ensures only paused rows
        can be resumed (defends against double-resume / status-drift races).

        Args:
            run_id:              UUID of the harness_runs row.
            new_phase_index:     Phase to resume FROM (typically pause_phase + 1).
            phase_results_patch: Dict to deep-merge into existing phase_results.
            user_id:             auth.users UUID for audit log.
            user_email:          User's email for audit log.
            token:               JWT access token for RLS-scoped client.

        Returns:
            The updated HarnessRunRecord on success; None if guard rejected.
        """
        client = get_supabase_authed_client(token)

        # Fetch current phase_results for merge (mirrors advance_phase:223-232)
        fetch_result = (
            client.table("harness_runs")
            .select("phase_results")
            .eq("id", run_id)
            .execute()
        )
        current_phase_results: dict[str, Any] = {}
        if fetch_result.data:
            current_phase_results = fetch_result.data[0].get("phase_results") or {}

        merged = {**current_phase_results, **phase_results_patch}

        result = (
            client.table("harness_runs")
            .update({
                "status": "running",
                "current_phase": new_phase_index,
                "phase_results": merged,
            })
            .eq("id", run_id)
            .in_("status", ["paused"])  # transactional guard — only paused can resume
            .execute()
        )
        if not result.data:
            logger.warning(
                "resume_from_pause affected 0 rows run_id=%s — possibly not paused",
                run_id,
            )
            return None
        audit_service.log_action(
            user_id=user_id,
            user_email=user_email,
            action="harness_run_resumed",
            resource_type="harness_runs",
            resource_id=run_id,
        )
        return result.data[0]
    ```

    Run order:
    1. RED: write 5 tests; `cd backend && source venv/bin/activate && pytest tests/services/test_harness_runs_service_pause.py -x`. ALL must fail (methods do not exist).
    2. GREEN: implement both methods; rerun. ALL must pass.
    3. Confirm no regression: `pytest backend/tests/services/test_harness_runs_service.py` exits 0.
    4. Commit: `gsd-sdk query commit "feat(21-02): harness_runs_service pause/resume_from_pause helpers" --files backend/app/services/harness_runs_service.py backend/tests/services/test_harness_runs_service_pause.py`.
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pytest tests/services/test_harness_runs_service_pause.py tests/services/test_harness_runs_service.py -v --tb=short</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "^async def pause" backend/app/services/harness_runs_service.py` returns 1.
    - `grep -c "^async def resume_from_pause" backend/app/services/harness_runs_service.py` returns 1.
    - `grep -c '\.in_("status", \["running"\])' backend/app/services/harness_runs_service.py` returns >= 1 (pause guard).
    - `grep -c '\.in_("status", \["paused"\])' backend/app/services/harness_runs_service.py` returns >= 1 (resume guard).
    - `grep -c "harness_run_paused\|harness_run_resumed" backend/app/services/harness_runs_service.py` returns >= 2.
    - `pytest backend/tests/services/test_harness_runs_service_pause.py` exits 0 with all 5 tests passing.
    - `pytest backend/tests/services/test_harness_runs_service.py` exits 0 (no regression).
  </acceptance_criteria>
  <done>
    `pause()` and `resume_from_pause()` are public methods on harness_runs_service with correct transactional guards and audit logging. 5 regression tests green. No regression in pre-existing harness_runs_service tests.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 1: Add start_phase_index to run_harness_engine signature + skip-loop logic + new SSE constants + HumanInputQuestion Pydantic model</name>
  <files>backend/app/services/harness_engine.py</files>
  <read_first>
    - backend/app/services/harness_engine.py — full file. Critical lines: 84-86 (existing Phase 21 SSE constants), 93-103 (run_harness_engine signature), 122-130 (inner forwarding call), 151-161 (_run_harness_engine_inner signature), 201 (phase loop start), 503-558 (LLM_SINGLE egress + Pydantic pattern to mirror).
    - .planning/phases/21-batched-parallel-sub-agents-human-in-the-loop/21-PATTERNS.md — sections "harness_engine.py — `run_harness_engine` signature extension (D-03)" (lines 149-178) and "Pydantic structured LLM output" (lines 838-841).
    - backend/app/harnesses/types.py — confirm `PhaseType.LLM_HUMAN_INPUT` enum value is `"llm_human_input"`.
  </read_first>
  <action>
    Edit `backend/app/services/harness_engine.py` in three localized blocks:

    **Block 1 — append two new SSE constants near lines 84-86**:
    ```python
    EVT_BATCH_ITEM_START = "harness_batch_item_start"      # Phase 21 D-08 — used by Plan 21-03
    EVT_BATCH_ITEM_COMPLETE = "harness_batch_item_complete"  # Phase 21 D-08 — used by Plan 21-03
    ```
    (These are added in Plan 21-02 because the constants live alongside EVT_BATCH_START/COMPLETE; Plan 21-03 consumes them.)

    **Block 2 — add HumanInputQuestion Pydantic model near top of file (after existing imports/dataclasses, before run_harness_engine)**:
    ```python
    from pydantic import BaseModel, Field

    class HumanInputQuestion(BaseModel):
        """Output schema for LLM_HUMAN_INPUT phase question generation (HIL-01)."""
        question: str = Field(..., min_length=1, max_length=500)
    ```

    **Block 3 — extend run_harness_engine signature with `start_phase_index: int = 0`**:

    At line 93, add the new keyword-only parameter:
    ```python
    async def run_harness_engine(
        *,
        harness: HarnessDefinition,
        harness_run_id: str,
        thread_id: str,
        user_id: str,
        user_email: str,
        token: str,
        registry,
        cancellation_event: asyncio.Event,
        start_phase_index: int = 0,   # Phase 21 D-03 — HIL resume passes current_phase + 1
    ) -> AsyncIterator[dict]:
    ```

    Forward to inner at line ~122:
    ```python
    async for event in _run_harness_engine_inner(
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
        yield event
    ```

    Extend `_run_harness_engine_inner` signature at line ~151 with the same parameter.

    **Block 4 — phase-skip logic in inner loop**:

    At line 201, before any per-phase processing:
    ```python
    for phase_index, phase in enumerate(harness.phases):
        if phase_index < start_phase_index:
            continue   # Phase 21 D-03 — already recorded in phase_results from prior run
        # ... existing logic unchanged
    ```

    Run a manual import smoke test:
    ```bash
    cd backend && source venv/bin/activate && python -c "
    from app.services.harness_engine import (
        run_harness_engine, EVT_BATCH_ITEM_START, EVT_BATCH_ITEM_COMPLETE, HumanInputQuestion
    )
    import inspect
    sig = inspect.signature(run_harness_engine)
    assert 'start_phase_index' in sig.parameters
    assert sig.parameters['start_phase_index'].default == 0
    assert HumanInputQuestion.model_fields['question'].is_required()
    print('OK')
    "
    ```
    Must print `OK`.
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && python -c "from app.services.harness_engine import run_harness_engine, EVT_BATCH_ITEM_START, EVT_BATCH_ITEM_COMPLETE, HumanInputQuestion; import inspect; sig = inspect.signature(run_harness_engine); assert 'start_phase_index' in sig.parameters and sig.parameters['start_phase_index'].default == 0; print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c 'EVT_BATCH_ITEM_START = "harness_batch_item_start"' backend/app/services/harness_engine.py` returns 1.
    - `grep -c 'EVT_BATCH_ITEM_COMPLETE = "harness_batch_item_complete"' backend/app/services/harness_engine.py` returns 1.
    - `grep -c "class HumanInputQuestion" backend/app/services/harness_engine.py` returns 1.
    - `grep -c "start_phase_index: int = 0" backend/app/services/harness_engine.py` returns >= 2 (run_harness_engine + _run_harness_engine_inner signatures).
    - `grep -c "if phase_index < start_phase_index" backend/app/services/harness_engine.py` returns 1.
    - The smoke import command above prints `OK`.
    - Existing test suite still green: `pytest backend/tests/services/test_harness_engine.py` exits 0.
  </acceptance_criteria>
  <done>
    Engine signature extended, SSE constants and Pydantic model added, phase-skip logic in place, no regression in existing harness_engine tests.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Implement LLM_HUMAN_INPUT dispatch branch + outer-loop paused-terminal handler + 6 pytest cases (RED → GREEN)</name>
  <files>backend/app/services/harness_engine.py, backend/tests/services/test_harness_engine_human_input.py</files>
  <read_first>
    - backend/app/services/harness_engine.py lines 503-558 — LLM_SINGLE block: egress filter (503-514) and Pydantic structured-output pattern (516-558). The HIL dispatcher mirrors these patterns verbatim.
    - backend/app/services/harness_engine.py lines 678-690 — terminal marker pattern (`yield {"_terminal_phase_result": output}`).
    - backend/app/services/harness_engine.py lines 309-393 — the existing outer-loop terminal-handling block. The HIL paused branch must be inserted INSIDE this region (before the existing advance_phase / next-phase code path). After this branch yields harness_complete{status=paused} it MUST `return` — preventing any advance_phase call.
    - backend/app/services/harness_engine.py line 697 — the existing `"code": "PHASE21_PENDING"` runtime literal. After Task 2's edits, ONE such literal remains (the LLM_BATCH_AGENTS branch); the LLM_HUMAN_INPUT half is gone. The docstring mention at line 26 is unaffected.
    - backend/app/services/harness_runs_service.py — the new `pause()` helper (added in Task 0). HIL dispatcher MUST call this, not `advance_phase` and not the non-existent `transition_status`.
    - backend/tests/services/test_harness_engine.py — full file. Read MOCK_BASES dict (lines 82-90), `_collect` helper, fixture pattern. Mirror EXACTLY in the new test file.
    - .planning/phases/21-batched-parallel-sub-agents-human-in-the-loop/21-PATTERNS.md — sections "harness_engine.py — replace lines 692-698 PHASE21_PENDING stubs" (lines 33-145) and "test_harness_engine_human_input.py" (lines 657-665).
    - .planning/phases/21-batched-parallel-sub-agents-human-in-the-loop/21-CONTEXT.md — D-04 (HIL SSE event sequence: delta → harness_human_input_required → done), D-21 (paused-before-SSE-close ordering).
  </read_first>
  <behavior>
    Tests in `backend/tests/services/test_harness_engine_human_input.py`:

    - Test 1 `test_hil_question_generation_llm_call`: mock `or_svc.complete_with_tools` returns `{"content": '{"question": "What label?"}'}`. Run a 1-phase harness with phase_type=LLM_HUMAN_INPUT. Assert `complete_with_tools` was called once with `response_format` containing `json_schema` and the schema for HumanInputQuestion.
    - Test 2 `test_hil_delta_events_emitted_before_required`: collect events; assert at least one `delta` event appears in order, followed by exactly one event with `type == EVT_HUMAN_INPUT_REQUIRED`.
    - Test 3 `test_hil_required_event_payload`: assert the `harness_human_input_required` event has keys `{type, question, workspace_output_path, harness_run_id}`, with `question == "What label?"`, `workspace_output_path == phase.workspace_output`.
    - Test 4 `test_hil_db_paused_before_sse_close`: patch `harness_runs_service.pause` (the new helper from Task 0) as a recording AsyncMock; record call order via a `MagicMock`. Assert it was called once with `run_id=harness_run_id` BEFORE the final harness_complete yield.
    - Test 5 `test_hil_egress_filter_blocks_pii_question`: registry mock with `egress_filter` patched to return `tripped=True`. Assert the dispatcher yields `_terminal_phase_result` with `error == "egress_blocked"` and `code == "PII_EGRESS_BLOCKED"`, and NO LLM call was made (egress runs BEFORE the LLM call), and `harness_runs_service.pause` was NOT called.
    - Test 6 `test_hil_phase_yields_paused_terminal_and_stops`: drive the engine through a harness with TWO phases — phase[0]=LLM_HUMAN_INPUT, phase[1]=LLM_SINGLE. Mock `complete_with_tools` to return the question for phase[0]. Patch `harness_runs_service.advance_phase` and `harness_runs_service.complete` as AsyncMocks. Collect all events; assert: (a) exactly ONE `EVT_COMPLETE` event with `status='paused'`, (b) ZERO `EVT_PHASE_COMPLETE` events for phase[0] (paused does NOT count as a phase_complete — this is per D-04), (c) ZERO calls to `advance_phase`, (d) ZERO calls to `complete()` (paused is not terminal-completed), (e) phase[1] is NEVER dispatched (no phase_start event for index 1).
  </behavior>
  <action>
    Replace the `PHASE21_PENDING` runtime stub at lines 692-701 of `backend/app/services/harness_engine.py`. The current stub catches BOTH `LLM_BATCH_AGENTS` and `LLM_HUMAN_INPUT`. Split into two branches: implement HIL fully here; leave LLM_BATCH_AGENTS still returning PHASE21_PENDING (Plan 21-03 will replace).

    **Concrete replacement — insert ABOVE the current `if phase.phase_type in (PhaseType.LLM_BATCH_AGENTS, PhaseType.LLM_HUMAN_INPUT):` line:**

    ```python
    # Phase 21 / HIL-01..03: LLM_HUMAN_INPUT dispatch.
    if phase.phase_type == PhaseType.LLM_HUMAN_INPUT:
        # 1. Read prior-phase context files (D-08 sub-agent inline pattern)
        inputs = await _read_workspace_files(thread_id, phase.workspace_inputs, token)
        if isinstance(inputs, dict) and inputs.get("error"):
            yield {"_terminal_phase_result": inputs}
            return

        # 2. Build messages — system prompt = phase template asks for ONE question;
        #    user content = prior-phase context blobs.
        messages = _build_llm_single_messages(phase, inputs)

        # 3. Egress filter (SEC-04) — mirror LLM_SINGLE pattern at lines 503-514
        if registry is not None:
            payload = json.dumps(messages, ensure_ascii=False)
            er = egress_filter(payload, registry, None)
            if er.tripped:
                yield {
                    "_terminal_phase_result": {
                        "error": "egress_blocked",
                        "code": "PII_EGRESS_BLOCKED",
                        "detail": "PII detected in llm_human_input payload",
                    }
                }
                return

        # 4. LLM call with json_schema response_format against HumanInputQuestion
        schema = HumanInputQuestion.model_json_schema()
        try:
            llm_result = await or_svc.complete_with_tools(
                messages=messages,
                tools=None,
                model=None,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "HumanInputQuestion",
                        "schema": schema,
                        "strict": True,
                    },
                },
            )
        except Exception as exc:
            logger.error(
                "_dispatch_phase: HIL LLM call failed phase=%s: %s", phase.name, exc
            )
            yield {
                "_terminal_phase_result": {
                    "error": "hil_llm_failed",
                    "code": "HIL_LLM_FAILED",
                    "detail": str(exc)[:500],
                }
            }
            return

        # 5. Validate via Pydantic
        try:
            parsed = HumanInputQuestion.model_validate_json(llm_result.get("content", ""))
        except Exception as exc:
            yield {
                "_terminal_phase_result": {
                    "error": "hil_invalid_question",
                    "code": "HIL_VALIDATION_FAILED",
                    "detail": str(exc)[:500],
                }
            }
            return

        question_text = parsed.question

        # 6. Stream the question as delta events (HIL-02 — chat-bubble, NOT phase panel)
        for chunk in _chunk_for_delta(question_text):
            yield {"type": "delta", "content": chunk, "harness_run_id": harness_run_id}

        # 7. Emit harness_human_input_required event (D-04 sequence)
        yield {
            "type": EVT_HUMAN_INPUT_REQUIRED,
            "question": question_text,
            "workspace_output_path": phase.workspace_output,
            "harness_run_id": harness_run_id,
        }

        # 8. DB transition to 'paused' BEFORE returning (HIL-03, D-21 ordering).
        #    Uses Task 0's new harness_runs_service.pause() helper — NOT advance_phase
        #    (which has a guard that REJECTS the paused transition) and NOT
        #    transition_status (which does not exist).
        try:
            await harness_runs_service.pause(
                run_id=harness_run_id,
                user_id=user_id,
                user_email=user_email,
                token=token,
            )
        except Exception as exc:
            logger.warning(
                "_dispatch_phase: HIL pause transition failed run=%s: %s",
                harness_run_id, exc
            )

        # 9. Special HIL terminal marker — outer loop must NOT advance to next phase
        yield {"_terminal_phase_result": {"paused": True, "question": question_text}}
        return
    ```

    Add a tiny helper near `_summarize_output`:
    ```python
    def _chunk_for_delta(text: str, chunk_size: int = 32) -> list[str]:
        """Split a question into 32-char chunks for delta streaming (HIL-02)."""
        return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]
    ```

    Update the surviving `PHASE21_PENDING` stub so it ONLY catches LLM_BATCH_AGENTS:
    ```python
    if phase.phase_type == PhaseType.LLM_BATCH_AGENTS:
        yield {
            "_terminal_phase_result": {
                "error": "phase_type_not_implemented",
                "code": "PHASE21_PENDING",
                "detail": "LLM_BATCH_AGENTS reserved for Plan 21-03",
            }
        }
        return
    ```

    **Outer loop change** — `_run_harness_engine_inner` must detect the `paused: True` marker after `_dispatch_phase` returns its terminal. Locate the existing terminal-handling block (search for `_terminal_phase_result` between lines 309-393). Insert this branch BEFORE the existing advance_phase / EVT_PHASE_COMPLETE code path:

    ```python
    # Phase 21 HIL-03: paused terminal short-circuits the entire engine.
    # Do NOT yield EVT_PHASE_COMPLETE, do NOT call advance_phase, do NOT call complete().
    # The harness_runs row was already transitioned to 'paused' by the dispatcher.
    if isinstance(result, dict) and result.get("paused"):
        yield {
            "type": EVT_COMPLETE,
            "harness_run_id": harness_run_id,
            "status": "paused",
        }
        return
    ```

    (Substitute `result` with whatever the local variable holding the dispatched terminal payload is — verify by reading lines 309-393 at execution time.)

    **Tests** — create `backend/tests/services/test_harness_engine_human_input.py`. Mirror the import/mock pattern from `backend/tests/services/test_harness_engine.py` (lines 1-90 + MOCK_BASES dict). Add the 6 tests from the `<behavior>` block. Use `_collect(gen)` async helper to drain events into a list.

    For Test 6 specifically (the BLOCKER-4 regression test), the test MUST cover all 5 sub-assertions:
    - exactly one EVT_COMPLETE with status='paused'
    - zero EVT_PHASE_COMPLETE for phase[0]
    - zero advance_phase calls
    - zero complete() calls
    - phase[1] is never dispatched

    Run order:
    1. RED: write the 6 tests; run `cd backend && source venv/bin/activate && pytest tests/services/test_harness_engine_human_input.py -x`. ALL must fail.
    2. GREEN: implement the dispatcher branch + outer paused-handler. Rerun. ALL must pass.
    3. Confirm no regression: `pytest backend/tests/services/test_harness_engine.py` exits 0.
    4. Atomic commit: `gsd-sdk query commit "feat(21-02): implement LLM_HUMAN_INPUT dispatch + start_phase_index" --files backend/app/services/harness_engine.py backend/tests/services/test_harness_engine_human_input.py`.
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pytest tests/services/test_harness_engine_human_input.py tests/services/test_harness_engine.py -v --tb=short</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "if phase.phase_type == PhaseType.LLM_HUMAN_INPUT" backend/app/services/harness_engine.py` returns 1.
    - `grep -c 'EVT_HUMAN_INPUT_REQUIRED' backend/app/services/harness_engine.py` returns >= 2 (declaration + emit site).
    - `grep -c '"PII_EGRESS_BLOCKED"' backend/app/services/harness_engine.py` returns >= 2 (LLM_SINGLE existing + new HIL site).
    - `grep -c '"paused": True' backend/app/services/harness_engine.py` returns >= 1 (dispatcher terminal marker).
    - `grep -c 'result.get("paused")' backend/app/services/harness_engine.py` returns >= 1 (outer-loop paused-terminal handler — BLOCKER-4 fix). Substitute the local-variable name found during execution if it differs from `result`; the acceptance grep MUST match the chosen name.
    - `grep -c '"code": "PHASE21_PENDING"' backend/app/services/harness_engine.py` returns exactly 1 (only the LLM_BATCH_AGENTS runtime stub remains; HIL stub removed; the docstring at line 26 does NOT contain this exact literal so it is not counted — BLOCKER-3 fix).
    - `grep -c "harness_runs_service\.pause" backend/app/services/harness_engine.py` returns >= 1 (HIL dispatcher uses the new pause helper — BLOCKER-1 fix; no transition_status reference).
    - `grep -c "transition_status" backend/app/services/harness_engine.py` returns 0 (the non-existent helper is NOT referenced anywhere).
    - `pytest backend/tests/services/test_harness_engine_human_input.py` exits 0 with all 6 tests passing (including Test 6 covering the outer-loop paused handler).
    - `pytest backend/tests/services/test_harness_engine.py` exits 0 (no regression).
  </acceptance_criteria>
  <done>
    LLM_HUMAN_INPUT dispatch branch implemented end-to-end; outer-loop paused-terminal handler in place; 6 unit tests green; existing harness_engine tests green; PHASE21_PENDING runtime literal now appears exactly once (LLM_BATCH_AGENTS); HIL terminal marker correctly halts outer loop with `harness_complete{status=paused}` (no advance_phase, no complete).
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| HIL question LLM call → cloud OpenRouter | egress boundary; PII must be filtered (SEC-04) |
| dispatcher → harness_runs Postgres row | RLS-scoped DB write under user JWT (SEC-02) |
| LLM-generated question → user UI delta | output is HumanInputQuestion-validated (length-capped 500 chars) |
| pause()/resume_from_pause() service helpers | RLS-scoped; transactional guards prevent illegal state transitions |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-21-02-01 | Information Disclosure | Outgoing question payload contains workspace inputs (could include real PII) | mitigate | egress_filter run on serialized messages BEFORE LLM call; tripped → yield egress_blocked terminal, no LLM round-trip. Mirrors LLM_SINGLE pattern at lines 503-514. |
| T-21-02-02 | Tampering | LLM returns malicious oversized question | mitigate | HumanInputQuestion Pydantic enforces `max_length=500`; validation failure yields hil_invalid_question terminal. |
| T-21-02-03 | Elevation | start_phase_index could be set by attacker to skip critical security phases | accept | Caller provides start_phase_index from authenticated harness_runs row's current_phase (no user input path); HIL resume branch in Plan 21-04 reads paused_run["current_phase"] from RLS-scoped DB query — attacker cannot forge a paused run for another user's thread. |
| T-21-02-04 | Denial of Service | repeated HIL phases pause infinitely | accept | Single HIL phase per run is sequential; `harness_runs.status='paused'` partial unique index ensures only one active+paused run per thread. User cancel button (Phase 20 D-03) terminates a stuck run. |
| T-21-02-05 | Repudiation | who paused this harness? | mitigate | New harness_runs_service.pause() / resume_from_pause() log audit_service entries with user_id/user_email; OBS-02 thread_id correlation logging in place. |
| T-21-02-06 | State drift | double-pause or pause-of-non-running row | mitigate | pause() guards `.in_("status", ["running"])` — non-running rows return None silently (no-op). resume_from_pause() guards `.in_("status", ["paused"])` — non-paused rows return None. Caller in Plan 21-04 checks the return value. |
</threat_model>

<verification>
- 5 pause/resume regression tests pass (Task 0).
- 6 HIL engine tests pass (Task 2).
- 15 existing harness_engine tests still pass.
- 8+ existing harness_runs_service tests still pass.
- `from app.services.harness_engine import run_harness_engine, HumanInputQuestion, EVT_BATCH_ITEM_START, EVT_BATCH_ITEM_COMPLETE` imports clean.
- `from app.services.harness_runs_service import pause, resume_from_pause` imports clean.
- Atomic commits `feat(21-02): harness_runs_service pause/resume_from_pause helpers` + `feat(21-02): implement LLM_HUMAN_INPUT dispatch + start_phase_index` landed.
</verification>

<success_criteria>
LLM_HUMAN_INPUT phase type fully dispatchable: generates informed question via egress-filtered LLM call, streams as delta events, emits harness_human_input_required, transitions DB to paused via the new pause() helper, halts engine with `harness_complete{status=paused}` (no advance_phase, no complete). Engine signature accepts `start_phase_index` for resume support. harness_runs_service exposes pause() and resume_from_pause() public helpers usable by Plan 21-04. No regression in pre-existing harness tests.
</success_criteria>

<output>
After completion, create `.planning/phases/21-batched-parallel-sub-agents-human-in-the-loop/21-02-SUMMARY.md`
</output>
</content>
</invoke>