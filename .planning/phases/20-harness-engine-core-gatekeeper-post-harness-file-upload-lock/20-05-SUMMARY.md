---
phase: 20-harness-engine-core-gatekeeper-post-harness-file-upload-lock
plan: "05"
subsystem: post-harness-summary
tags:
  - harness
  - post-harness
  - pii-egress
  - sse-streaming
  - tdd
dependency_graph:
  requires:
    - 20-03 (harness_runs_service + get_run_by_id)
    - 20-04 (_gatekeeper_stream_wrapper, _get_or_build_conversation_registry, run_harness_engine)
  provides:
    - post_harness.summarize_harness_run (async generator, inline SSE post-harness summary)
    - post_harness._truncate_phase_results (deterministic D-10 truncation helper)
    - chat.py module-level imports for run_gatekeeper, run_harness_engine, summarize_harness_run
  affects:
    - backend/app/routers/chat.py (_gatekeeper_stream_wrapper trailing-done replaced with summary handoff)
    - backend/tests/routers/test_chat_harness_routing.py (B4 test simplified after module-level refactor)
tech_stack:
  added:
    - backend/app/services/post_harness.py (new service, ~180 LOC)
  patterns:
    - D-09 inline post-harness SSE streaming (same response, after harness_complete)
    - D-10/POST-05 deterministic truncation (30k threshold, last-2-phases full)
    - SEC-04/B4 single ConversationRegistry instance across all 4 LLM call sites
    - W9 egress rigor: positive identity assertion + negative control test
key_files:
  created:
    - backend/app/services/post_harness.py
    - backend/tests/services/test_post_harness.py
    - backend/tests/routers/test_chat_post_harness_integration.py
  modified:
    - backend/app/routers/chat.py
    - backend/tests/routers/test_chat_harness_routing.py
decisions:
  - "Module-level imports for run_gatekeeper/run_harness_engine/summarize_harness_run in chat.py enable clean monkeypatching without sys.modules hacks"
  - "openrouter_service singleton at post_harness module level (same pattern as chat.py singleton) for testable patching"
  - "egress_filter skipped when registry=None (OFF-mode no-op contract preserved, byte-identical to pre-Phase-20)"
metrics:
  duration: "~15 minutes"
  completed: "2026-05-03T16:26:37Z"
  tasks_completed: 2
  files_changed: 5
---

# Phase 20 Plan 05: Post-Harness Summary Service Summary

**One-liner:** Inline SSE post-harness summary with deterministic 30k-char truncation, SEC-04 egress wrap using B4 single-registry invariant, and W9 rigorous identity-assertion tests.

## What Was Built

### Task 1: `backend/app/services/post_harness.py`

New service (~180 LOC) implementing the D-09 inline post-harness summary pattern:

**Public surface:**
- `summarize_harness_run(*, harness, harness_run, thread_id, user_id, user_email, token, registry)` — async generator yielding `{"type": "delta", "content": str}` and `{"type": "summary_complete", "assistant_message_id": str|None}` events
- `_truncate_phase_results(phase_results, max_chars=30_000)` — deterministic D-10 truncation helper

**Constants:**
- `PHASE_RESULTS_MAX_CHARS = 30_000`
- `PREVIEW_LEN = 200`
- `TRUNCATION_MARKER = "...[truncated, see workspace artifact]"`
- `SUMMARY_GUIDANCE` — soft 500-token system-prompt constraint ("Be concise — 3-5 short paragraphs. Reference workspace files by path.")

**Truncation algorithm (D-10/POST-05):**
1. Compute total size via `json.dumps(phase_results)` 
2. If `len(as_json) <= 30_000` → return full JSON unchanged
3. Else: sort phases by integer key; phases `0..N-2` → `## Phase N: name\n{first 200 chars}{TRUNCATION_MARKER}`; phases `N-1` and `N` (last two) → full content

**Egress flow (SEC-04/B4):**
- When `registry is not None`: call `egress_filter(json.dumps(messages), registry, None)` BEFORE the LLM call
- Tripped → yield generic refusal delta + `summary_complete(assistant_message_id=None)`, no LLM call, audit log written
- When `registry is None` (PII off): skip egress_filter entirely (OFF-mode no-op contract — byte-identical to pre-Phase-20)

**Persistence:** `_persist_summary` inserts `messages` row with `role="assistant"`, `harness_mode=harness.name` (POST-03/D-04)

### Task 2: `backend/app/routers/chat.py` updates

**Module-level import refactor:**
```python
from app.services.gatekeeper import run_gatekeeper
from app.services.harness_engine import run_harness_engine
from app.services.post_harness import summarize_harness_run
```
This replaces the previous `from app.services.X import Y` inside the function body, enabling clean monkeypatching at `app.routers.chat.*` without `sys.modules` hacks.

**`_gatekeeper_stream_wrapper` post-harness handoff (D-09/B4):**
```
harness_complete received from engine
→ get_run_by_id(run_id=harness_run_id, token=token)  # fetch refreshed row
→ if refreshed is not None:
    summarize_harness_run(..., registry=registry)       # B4: SAME registry object
→ done event
```

The `registry` variable is built ONCE at the top of the wrapper via `_get_or_build_conversation_registry`. The post-harness handoff reuses this SAME instance — not a second call — ensuring all 4 LLM call sites of the turn (gatekeeper, engine.llm_single, sub_agent_loop via llm_agent, post_harness) share one ConversationRegistry.

## B4 Single-Registry Invariant

The B4 invariant requires that all LLM call sites of a single harness turn use the SAME `ConversationRegistry` instance so egress state is consistent. This is verified by:

- **Unit test** (`test_summarize_harness_run_egress_filter_called_with_exact_parent_registry`): asserts `mock_egress.call_args[0][1] is parent_registry` — object identity, not equality
- **Integration test** (`test_post_harness_receives_same_registry_instance_as_engine`): drives the full `_gatekeeper_stream_wrapper` with a sentinel registry MagicMock; asserts both engine and post_harness received `is registry_sentinel`
- **Existing test** (Plan 20-04 `test_gatekeeper_stream_wrapper_passes_same_registry_to_gatekeeper_and_engine`): simplified to use module-level patch now that imports are at module scope

## W9 Egress Rigor Pattern

Test 6 uses an explicit identity check (not just "was called"):
```python
assert mock_egress.call_args[0][1] is parent_registry  # identity, not equality
```

Test 7 (negative control) pins OFF-mode behavior:
```python
# registry=None → egress_filter must NOT be called
assert not mock_egress.called
```

Both tests together make it impossible for a silent regression (e.g. someone accidentally passing `None` as registry when redaction is on) to go undetected.

## Tests

| File | Count | Coverage |
|------|-------|---------|
| `tests/services/test_post_harness.py` | 11 | Truncation (4), system-prompt shape, egress identity (W9+), egress-blocked path, happy-path streaming, persistence, guidance text |
| `tests/routers/test_chat_post_harness_integration.py` | 4 | Fires after engine, skipped when fetch returns None, SSE event order, B4 registry identity |
| **Total new** | **15** | |

All 15 new tests pass. Plan 20-04 regression (1 test) fixed by simplifying the B4 test after module-level import refactor.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Plan 20-04 B4 test broken by module-level import refactor**
- **Found during:** Task 2 — after moving `run_gatekeeper`/`run_harness_engine` imports to module level
- **Issue:** `test_gatekeeper_stream_wrapper_passes_same_registry_to_gatekeeper_and_engine` used `sys.modules` replacement hacks to patch locally-imported names inside the function body. After the refactor, the patching missed the module-level names and the real `run_gatekeeper` was called, hitting Supabase with a fake token.
- **Fix:** Replaced the entire 80-line `sys.modules` + nested `with patch(...)` block with a 15-line `with patch("app.routers.chat.run_gatekeeper", ...)` approach — equivalent semantics, cleaner, faster.
- **Files modified:** `backend/tests/routers/test_chat_harness_routing.py`
- **Commit:** `eaf3980`

## Self-Check: PASSED

- `backend/app/services/post_harness.py` exists: FOUND
- `backend/tests/services/test_post_harness.py` exists: FOUND
- `backend/tests/routers/test_chat_post_harness_integration.py` exists: FOUND
- Commit `9609eef` (RED): FOUND
- Commit `ccb5bb8` (GREEN): FOUND
- Commit `eaf3980` (Task 2 + fix): FOUND
- 15 tests pass: VERIFIED (`pytest tests/services/test_post_harness.py tests/routers/test_chat_post_harness_integration.py` → 15 passed)
- Import check: `python -c "from app.main import app; print('OK')"` → OK
