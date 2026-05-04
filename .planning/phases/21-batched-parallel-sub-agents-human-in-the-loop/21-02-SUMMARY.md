---
phase: 21-batched-parallel-sub-agents-human-in-the-loop
plan: 02
subsystem: harness-engine
tags: [hil, harness, sse, pii, egress, pydantic, audit]
requires:
  - 21-01  # workspace JSONL append helper (independent — not consumed here, but Wave 1 dependency)
  - 20-*   # Phase 20 harness_engine + harness_runs_service foundation
provides:
  - "harness_runs_service.pause(run_id, user_id, user_email, token) -> HarnessRunRecord | None"
  - "harness_runs_service.resume_from_pause(run_id, new_phase_index, phase_results_patch, user_id, user_email, token) -> HarnessRunRecord | None"
  - "run_harness_engine(..., start_phase_index: int = 0)  # signature extension D-03"
  - "EVT_BATCH_ITEM_START / EVT_BATCH_ITEM_COMPLETE module-level SSE constants (used by Plan 21-03)"
  - "HumanInputQuestion Pydantic model (question: str, min_length=1, max_length=500)"
  - "LLM_HUMAN_INPUT dispatch branch in _dispatch_phase (HIL-01..03 fully implemented)"
  - "Outer-loop paused-terminal handler — emits harness_complete{status=paused}, halts engine without advance_phase / complete()"
affects:
  - backend/app/services/harness_engine.py
  - backend/app/services/harness_runs_service.py
tech-stack:
  added: []
  patterns:
    - "json_schema response_format with Pydantic strict validation (mirrors LLM_SINGLE block lines 503-558)"
    - "egress_filter pre-LLM-call guard (T-21-02-01 / SEC-04)"
    - "Transactional guard `.in_(\"status\", [...])` on UPDATE for state-machine integrity (mirrors advance_phase/cancel pattern)"
    - "delta-event chunking for typewriter chat-bubble UX (HIL-02)"
key-files:
  created:
    - backend/tests/services/test_harness_runs_service_pause.py    # 5 service tests
    - backend/tests/services/test_harness_engine_human_input.py    # 6 engine tests
  modified:
    - backend/app/services/harness_runs_service.py                 # +pause + resume_from_pause
    - backend/app/services/harness_engine.py                       # HIL dispatch + start_phase_index + outer paused handler
decisions:
  - "Dispatcher's HIL terminal marker uses {paused: True, question: ...} so outer loop can short-circuit without inspecting phase_type. The outer-loop branch (`if result.get(\"paused\")`) is the BLOCKER-4 fix that prevents accidental advance_phase / complete() calls after a HIL pause."
  - "pause() and resume_from_pause() are NEW public methods (not extensions to advance_phase/cancel). advance_phase's existing guard `.in_(\"status\", [\"pending\", \"running\"])` would REJECT paused→running transitions, so a separate resume_from_pause helper with `.in_(\"status\", [\"paused\"])` guard is required."
  - "Question chunking uses 32-char hard split (no word-boundary heuristic). The frontend already concatenates consecutive deltas; chunk-size only affects perceived typing speed, not correctness."
  - "Egress filter runs BEFORE the LLM call AND BEFORE harness_runs_service.pause() — a tripped egress yields the egress_blocked terminal directly, so no DB write happens for failed PII gates (avoids stuck paused rows when the question generation never reached the user)."
metrics:
  start: "2026-05-04T07:25:00Z"   # approximate
  end: "2026-05-04T07:36:33Z"
  duration_seconds: 700
  tasks_completed: 3
  files_modified: 4
  files_created: 2
  tests_added: 11    # 5 + 6
  tests_pre_existing: 28  # 12 harness_runs_service + 16 harness_engine
  tests_total_green: 39
---

# Phase 21 Plan 02: HIL Dispatcher and Engine Signature — Summary

LLM_HUMAN_INPUT phase dispatch is now end-to-end implemented: an egress-filtered LLM call generates a length-capped question (Pydantic-validated), streams it as `delta` events into a chat bubble, emits `harness_human_input_required`, transitions the harness DB row to `paused` via the new `harness_runs_service.pause()` helper, and the outer engine loop short-circuits with `harness_complete{status=paused}` (no `advance_phase`, no `complete()`). Plan 21-04 will resume from this paused state via the new `resume_from_pause()` helper and the `start_phase_index` engine parameter added here.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 0 | `harness_runs_service.pause` + `resume_from_pause` helpers + 5 regression tests | `2c87bc9` | `harness_runs_service.py`, `test_harness_runs_service_pause.py` |
| 1 | `start_phase_index` engine signature + `EVT_BATCH_ITEM_*` constants + `HumanInputQuestion` Pydantic model | `24f5dbe` | `harness_engine.py` |
| 2 | `LLM_HUMAN_INPUT` dispatch branch + outer-loop paused-terminal handler + 6 unit tests | `36ce403` | `harness_engine.py`, `test_harness_engine_human_input.py` |

## Verification

```
cd backend && pytest tests/services/test_harness_runs_service.py \
  tests/services/test_harness_runs_service_pause.py \
  tests/services/test_harness_engine.py \
  tests/services/test_harness_engine_human_input.py
```

Result: **39 passed** (12 existing harness_runs_service + 5 new pause/resume + 16 existing engine + 6 new HIL).

Backend import smoke test: `python -c "from app.main import app; print('OK')"` → OK.

### Engine signature smoke test
```python
from app.services.harness_engine import (
    run_harness_engine, EVT_BATCH_ITEM_START, EVT_BATCH_ITEM_COMPLETE, HumanInputQuestion
)
import inspect
sig = inspect.signature(run_harness_engine)
assert 'start_phase_index' in sig.parameters
assert sig.parameters['start_phase_index'].default == 0
assert HumanInputQuestion.model_fields['question'].is_required()
```
Output: `OK`.

## Acceptance-Criteria Grep

| Pattern | Expected | Got |
|---------|----------|-----|
| `^async def pause` in `harness_runs_service.py` | 1 | 1 |
| `^async def resume_from_pause` in `harness_runs_service.py` | 1 | 1 |
| `.in_("status", ["running"])` guard | ≥1 | 2 (docstring + code) |
| `.in_("status", ["paused"])` guard | ≥1 | 2 (docstring + code) |
| `harness_run_paused\|harness_run_resumed` audit actions | ≥2 | 2 |
| `EVT_BATCH_ITEM_START = "harness_batch_item_start"` | 1 | 1 |
| `EVT_BATCH_ITEM_COMPLETE = "harness_batch_item_complete"` | 1 | 1 |
| `class HumanInputQuestion` | 1 | 1 |
| `start_phase_index: int = 0` (signatures) | ≥2 | 2 |
| `if phase_index < start_phase_index` (skip logic) | 1 | 1 |
| `if phase.phase_type == PhaseType.LLM_HUMAN_INPUT` | 1 | 1 |
| `EVT_HUMAN_INPUT_REQUIRED` references | ≥2 | 2 |
| `"PII_EGRESS_BLOCKED"` literal | ≥2 | 2 |
| `"paused": True` (dispatcher terminal marker) | ≥1 | 1 |
| `result.get("paused")` (outer-loop handler — BLOCKER-4) | ≥1 | 1 |
| `"code": "PHASE21_PENDING"` runtime literal | exactly 1 | 1 |
| `harness_runs_service.pause` reference | ≥1 | 2 |
| `transition_status` reference (BLOCKER-1 — must NOT exist) | 0 | 0 |

## SSE Event Contract — LLM_HUMAN_INPUT phase

```
harness_phase_start (phase_index=N, phase_type='llm_human_input')
todos_updated
delta { content, harness_run_id }     ← N≥1 chunks of the question
harness_human_input_required {
  type, question, workspace_output_path, harness_run_id
}
harness_complete { status: 'paused', harness_run_id }
```

Notable absences after a HIL pause:
- NO `harness_phase_complete` for the HIL phase (the phase is suspended, not done).
- NO `advance_phase` DB write.
- NO `complete()` DB write — the run row stays in `paused` until Plan 21-04's resume branch transitions it back to `running`.

## Threat-Model Mitigations Implemented

| Threat ID | Disposition | Implementation |
|-----------|-------------|----------------|
| T-21-02-01 (Information Disclosure — PII in question payload) | mitigate | `egress_filter(json.dumps(messages), registry, None)` runs BEFORE the LLM call. Tripped → `egress_blocked` terminal, no LLM round-trip, no `pause()` DB write. |
| T-21-02-02 (Tampering — oversized question) | mitigate | `HumanInputQuestion(question: str = Field(..., min_length=1, max_length=500))` Pydantic strict validation; failure yields `HIL_VALIDATION_FAILED` terminal. |
| T-21-02-03 (Elevation — start_phase_index forged) | accept | start_phase_index has no user-input path; Plan 21-04 will read it from the RLS-scoped paused harness_runs row's `current_phase`. Documented in plan threat register. |
| T-21-02-05 (Repudiation — who paused/resumed?) | mitigate | Both `pause()` and `resume_from_pause()` emit `audit_service.log_action` with `action='harness_run_paused'` / `'harness_run_resumed'`, `user_id`, `user_email`, `resource_id`. |
| T-21-02-06 (State drift — double-pause / pause-of-non-running) | mitigate | `pause()` guards `.in_("status", ["running"])`; `resume_from_pause()` guards `.in_("status", ["paused"])`. Both return `None` on guard rejection (no audit log emitted). 5 service-level tests cover all guard branches. |

## Deviations from Plan

None — all three tasks executed exactly as planned. The plan's literal counts in acceptance criteria already accounted for docstring matches (e.g., guard literals appear in both docstrings and code), so the grep targets matched cleanly without adjustment.

### Auto-fixed Issues
None.

### Authentication Gates
None.

## Known Stubs

- **`LLM_BATCH_AGENTS` PHASE21_PENDING runtime stub remains** in `_dispatch_phase`. This is intentional and documented in the plan — Plan 21-03 (Wave 3) replaces this branch with the asyncio.Queue fan-in batch dispatcher. Test `test_phase21_events_are_documented_but_unimplemented` in `test_harness_engine.py` continues to assert this stub for `LLM_BATCH_AGENTS` only.

## Threat Flags

None — no new security-relevant surface introduced beyond the threat register entries above. The HIL LLM call extends an existing pattern (LLM_SINGLE) with the same egress-filter guard; the new service helpers reuse the existing audit/RLS conventions.

## Self-Check: PASSED

- File `backend/app/services/harness_runs_service.py`: FOUND, contains `pause` and `resume_from_pause`.
- File `backend/app/services/harness_engine.py`: FOUND, contains `LLM_HUMAN_INPUT` dispatch branch + `start_phase_index` parameter + `HumanInputQuestion` model + outer paused handler.
- File `backend/tests/services/test_harness_runs_service_pause.py`: FOUND, 5 tests passing.
- File `backend/tests/services/test_harness_engine_human_input.py`: FOUND, 6 tests passing.
- Commit `2c87bc9`: FOUND in `git log`.
- Commit `24f5dbe`: FOUND in `git log`.
- Commit `36ce403`: FOUND in `git log`.
