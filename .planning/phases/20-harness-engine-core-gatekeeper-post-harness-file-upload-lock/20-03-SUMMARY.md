---
phase: 20-harness-engine-core-gatekeeper-post-harness-file-upload-lock
plan: "03"
subsystem: harness-engine
tags: [harness, engine, registry, types, phase-dispatch, cancellation, sse, pydantic, panel]
dependency_graph:
  requires: [20-02]
  provides: [run_harness_engine, HarnessRegistry, HarnessDefinition, PhaseType, harness_enabled]
  affects: [20-04, 20-05, 20-07, 20-08, 20-09, 20-11]
tech_stack:
  added: [asyncio.timeout (Python 3.11+), pkgutil.iter_modules auto-import barrel]
  patterns: [async-generator state machine, dual-layer cancellation, first-write-wins registry, dark-launch feature flag]
key_files:
  created:
    - backend/app/config.py (harness_enabled + harness_smoke_enabled fields added)
    - backend/app/harnesses/types.py
    - backend/app/harnesses/__init__.py
    - backend/app/services/harness_registry.py
    - backend/app/services/harness_engine.py
    - backend/tests/services/test_harness_registry.py
    - backend/tests/services/test_harness_engine.py
  modified:
    - backend/app/services/harness_runs_service.py (added get_run_by_id)
decisions:
  - "asyncio.timeout() used instead of asyncio.wait_for for async generator timeout (Python 3.11+)"
  - "OpenRouterService instantiated locally inside _dispatch_phase for llm_single/llm_agent (avoids circular import)"
  - "get_run_by_id added to harness_runs_service as Rule 2 deviation (required by B3 cross-request cancel)"
  - "harness_engine wraps sub_agent_loop without duplicating its logic (reuse D-09/Phase 19)"
metrics:
  duration: "~8 minutes"
  completed: "2026-05-03"
  tasks_completed: 4
  files_count: 8
---

# Phase 20 Plan 03: Harness Engine Core Summary

Harness engine core shipped — types, registry, auto-import barrel, engine dispatcher, and 20 new tests covering all HARN-02..10, PANEL-01/03, OBS-01 requirements.

## What Was Built

### 5 new/extended modules

**`backend/app/config.py`** — Added `harness_enabled: bool = False` and `harness_smoke_enabled: bool = False` Pydantic Settings fields immediately after `sub_agent_enabled`. Both dark-launch OFF by default, matching the SUB_AGENT_ENABLED/WORKSPACE_ENABLED/DEEP_MODE_ENABLED precedent. When both are False, the codebase is byte-identical to pre-Phase-20 (D-16 invariant).

**`backend/app/harnesses/types.py`** — All 4 dataclasses + 2 constants:
- `PhaseType(str, Enum)`: PROGRAMMATIC, LLM_SINGLE, LLM_AGENT + Phase 21 reserved members (LLM_BATCH_AGENTS, LLM_HUMAN_INPUT)
- `HarnessPrerequisites(BaseModel)`: gatekeeper shape (requires_upload, accepted_mime_types, harness_intro, etc.)
- `PhaseDefinition(BaseModel)`: full phase definition including executor callable, output_schema Pydantic class, validator, workspace_inputs/output
- `HarnessDefinition(BaseModel)`: registry entry (name, display_name, prerequisites, phases)
- `DEFAULT_TIMEOUT_SECONDS`: dict keyed by PhaseType (60/120/300/600/86400)
- `PANEL_LOCKED_EXCLUDED_TOOLS`: frozenset({"write_todos", "read_todos"}) — PANEL-03

**`backend/app/services/harness_registry.py`** — Module-level `_REGISTRY: dict[str, HarnessDefinition]`, `register()` (first-write-wins), `get_harness()`, `list_harnesses()`, `_reset_for_tests()`. Mirrors tool_registry.py.

**`backend/app/harnesses/__init__.py`** — Auto-import barrel gated on `settings.harness_enabled`. Uses `pkgutil.iter_modules` to iterate all `.py` files alphabetically, skipping names starting with `_`. When harness_enabled=False, logs the byte-identical-mode message and does nothing.

**`backend/app/services/harness_engine.py`** (~460 LOC) — Full dispatcher:
- Public surface: `run_harness_engine()` async generator (D-12 failure-isolation wrapper)
- Inner loop: PANEL-01 todos init, OBS-01 initial progress.md write, phase loop with B3 dual-layer cancel
- `_dispatch_phase()` per-PhaseType dispatch
- 6 Phase-20 SSE event constants + 3 Phase-21-deferred constants (all 9 HARN-09 events documented)
- PROGRESS_PATH = "progress.md"

### Public API surface (for downstream plans)

```python
# Plan 20-04 (gatekeeper + chat.py) uses:
from app.services.harness_engine import run_harness_engine
async for event in run_harness_engine(
    harness=harness,
    harness_run_id=run_id,
    thread_id=thread_id,
    user_id=user_id,
    user_email=user_email,
    token=token,
    registry=conversation_registry,
    cancellation_event=cancellation_event,
):
    ...

# Plan 20-07 (smoke harness) uses:
from app.services.harness_registry import register
from app.harnesses.types import HarnessDefinition, PhaseDefinition, PhaseType, HarnessPrerequisites

# Plan 20-08/09 (frontend) consumes SSE events:
# harness_phase_start, harness_phase_complete, harness_phase_error,
# harness_complete, harness_sub_agent_start, harness_sub_agent_complete
```

### B1 sub-agent event suite

`harness_sub_agent_start` emitted BEFORE `run_sub_agent_loop` drain. `harness_sub_agent_complete` emitted in `finally:` block (guaranteed even on exception). Both carry `harness_run_id`, `phase_index`, `phase_name`, `task_id`. `harness_sub_agent_complete` carries `status` ('completed'/'failed') and `result_summary` (str ≤200 chars).

### B3 dual-layer cancellation

Layer 1 (in-process): `cancellation_event.is_set()` checked at top of each phase iteration. Layer 2 (cross-request): `harness_runs_service.get_run_by_id()` called before each phase, exits cleanly with `harness_phase_error{reason='cancelled_by_user'}` when status='cancelled'. The cancel endpoint (Plan 20-04) sets the DB row; the engine polls at each phase boundary — cost is 1 row read per phase (~5 for smoke run = trivial).

## Test Coverage

**`test_harness_registry.py`** — 5 tests: register/get, first-write-wins duplicate, unknown returns None, list all, reset.

**`test_harness_engine.py`** — 15 tests:
1. Happy path emits phase_start + phase_complete + harness_complete
2. PANEL-01 todos init with `[Display] Phase Name` content prefix
3. OBS-01 write_text_file called for progress.md
4. HARN-06 timeout → TIMEOUT code
5. HARN-07 in-process cancellation between phases
6. HARN-05 Pydantic validation failure → INVALID_OUTPUT
7. llm_single missing output_schema → MISSING_SCHEMA
8. LLM_AGENT invokes sub_agent_loop (PANEL-03 tool filtering)
9. SEC-04 egress_filter trips → PII_EGRESS_BLOCKED
10. Phase 21 reserved types → PHASE21_PENDING
11. Phase failure stops engine (no subsequent phase dispatch — STATUS-03)
12. advance_phase called with correct new_phase_index; complete called once
13. (B1) sub_agent_start/complete event ordering + required fields verified
14. (B1) Phase 21 constants exported; LLM_BATCH_AGENTS dispatch does NOT emit batch events
15. (B3) DB status='cancelled' halts engine at next phase boundary before phase executor

**Total: 20 tests, 20 passed.**

## Deviations from Plan

### Auto-added: get_run_by_id to harness_runs_service [Rule 2 - Missing Critical Functionality]

**Found during:** Task 4 pre-implementation review

**Issue:** `harness_runs_service` (Plan 20-02) did not include `get_run_by_id()`, which is required by the engine's B3 cross-request cancel poll (HARN-07 Layer 2).

**Fix:** Added `get_run_by_id(*, run_id: str, token: str) -> HarnessRunRecord | None` to harness_runs_service.py. Single SELECT by primary key, same RLS-scoped client pattern.

**Files modified:** `backend/app/services/harness_runs_service.py`

**Commit:** 7e7cdf5

### Implementation note: asyncio.timeout() vs asyncio.wait_for()

The plan's pseudocode showed `asyncio.wait_for` which cannot directly wrap an async generator drain. Used `asyncio.timeout()` context manager (Python 3.11+, confirmed available) instead — it cleanly raises `asyncio.TimeoutError` from within `async with asyncio.timeout(N):` block wrapping the `async for` dispatch drain.

### Implementation note: OpenRouterService instantiation

The plan referenced `openrouter_service` as a module-level import singleton but `openrouter_service.py` only exports `OpenRouterService` class without a module-level instance. Instantiated locally inside `_dispatch_phase` for llm_single and llm_agent phases — avoids circular imports and matches the chat.py pattern (line 220: `openrouter_service = OpenRouterService()`).

## Threat Surface Scan

No new network endpoints added (engine is internal service). All LLM calls in LLM_SINGLE and LLM_AGENT phases wrapped with `egress_filter` using parent ConversationRegistry (SEC-04 satisfied). PANEL_LOCKED_EXCLUDED_TOOLS enforced in `_dispatch_phase` for LLM_AGENT phases (PANEL-03 satisfied). Sub-agent JWT inheritance via `parent_token=token` (SEC-02, no new JWT minted).

## Self-Check

### Created files exist
- `backend/app/harnesses/types.py` FOUND
- `backend/app/harnesses/__init__.py` FOUND
- `backend/app/services/harness_registry.py` FOUND
- `backend/app/services/harness_engine.py` FOUND
- `backend/tests/services/test_harness_registry.py` FOUND
- `backend/tests/services/test_harness_engine.py` FOUND

### Commits exist
- d8213f5: feat(20-03): add HARNESS_ENABLED + HARNESS_SMOKE_ENABLED feature flags
- e0d37b8: feat(20-03): create harnesses/types.py
- 7e7cdf5: feat(20-03): create harness_registry + harnesses/__init__ barrel + registry tests
- 881b986: feat(20-03): implement HarnessEngine + 15 pytest tests

### Test results
- test_harness_registry.py: 5 passed
- test_harness_engine.py: 15 passed
- Total: 20 passed, 0 failed

## Self-Check: PASSED
