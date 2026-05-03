---
phase: 19-sub-agent-delegation-ask-user-status-recovery
plan: "08"
subsystem: api
tags: [deep-mode, system-prompt, llm, task-tool, ask-user, error-recovery, kv-cache]

# Dependency graph
requires:
  - phase: 19-04
    provides: task tool registration in tool_service + sub-agent executor logic
  - phase: 19-05
    provides: ask_user pause/resume flow in chat.py
provides:
  - "Real Phase 19 guidance in deep_mode_prompt.py: task(), ask_user(), Error Recovery sections"
  - "5-section deterministic DEEP_MODE_SECTIONS replacing 4-section Phase 17 stubs"
  - "6 unit tests covering determinism, no volatile data, task guidance, ask_user guidance, error recovery, TASK-06 coexistence"
affects:
  - phase-20-harness-engine
  - any future phase that modifies deep_mode_prompt.py

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "TDD RED-GREEN cycle: test file committed first (failing), then implementation commit makes all pass"
    - "Test 6 TASK-06 coexistence pattern: use ast.parse + subprocess git diff to verify file unchanged without live imports"
    - "Minimal env-var patching for unit tests that import app modules with module-level DB calls"

key-files:
  created:
    - backend/tests/services/test_deep_mode_prompt.py
  modified:
    - backend/app/services/deep_mode_prompt.py

key-decisions:
  - "Test 6 uses subprocess git diff + AST inspection rather than live module import — agent_service.py has module-level get_system_settings() DB call that cannot be patched before first import"
  - "DEEP_MODE_SECTIONS grows from 4 sections (Phase 17) to 5 sections (Phase 19) — section count change is fine, content stability is what matters for KV-cache"
  - "No automatic retry wording verbatim in prompt: 'There is no automatic retry' satisfies D-20 assertion"

patterns-established:
  - "Deep-mode prompt sections: add new Phase content as new sections, never mutate existing section text"
  - "KV-cache stability: determinism test asserts same-in == same-out; volatile-data test asserts no year/uuid/thread-id shapes"

requirements-completed: [TASK-06, STATUS-03]

# Metrics
duration: 15min
completed: "2026-05-03"
---

# Phase 19 Plan 08: Deep Mode Prompt — Phase 19 Guidance Summary

**Replaced Phase 17 stub sections in deep_mode_prompt.py with real task(), ask_user(), and Error Recovery guidance; 6 unit tests pass including TASK-06 coexistence assertion**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-05-03T07:00:00Z
- **Completed:** 2026-05-03T07:15:00Z
- **Tasks:** 2 (TDD RED + GREEN)
- **Files modified:** 2

## Accomplishments

- Replaced Phase 17 Sub-Agent Delegation stub with real `task(description, context_files)` semantics — 15-round limit, isolation model, no recursive task calls
- Replaced Phase 17 Asking the User stub with real `ask_user(question)` semantics — pause sentinel, verbatim reply delivery, no rhetorical use
- Added new Error Recovery section: structured error result format, LLM-driven retry/alternative/escalate decision, no automatic retry (D-20)
- Updated module docstring: 4 sections -> 5 sections
- Function signature `build_deep_mode_system_prompt(base_prompt: str) -> str` unchanged (D-09 KV-cache invariant)
- 6 unit tests: determinism, no volatile data, task guidance, ask_user guidance, error recovery, TASK-06 coexistence

## DEEP_MODE_SECTIONS Line Count

- **Before (Phase 17):** 22 lines of prompt content (4 sections, two with stubs)
- **After (Phase 19):** 37 lines of prompt content (5 sections, all real guidance)
- Total file: 53 lines (Phase 17) → 67 lines (Phase 19)

## Test Results

```
6/6 passed
- test_build_deep_mode_system_prompt_is_deterministic         PASSED
- test_build_deep_mode_system_prompt_no_timestamp_or_volatile_data  PASSED
- test_deep_mode_prompt_contains_task_guidance                PASSED
- test_deep_mode_prompt_contains_ask_user_guidance            PASSED
- test_deep_mode_prompt_contains_error_recovery_no_auto_retry PASSED
- test_agent_service_classify_intent_unchanged                PASSED
```

## Determinism Confirmation

`build_deep_mode_system_prompt("base") == build_deep_mode_system_prompt("base")` verified via python assertion and Test 1.

## TASK-06 Coexistence Confirmation

`agent_service.py` unmodified — confirmed via `git diff --stat` (no output) and AST inspection of `classify_intent` signature (all v1.0 params intact: message, history, openrouter_service, model, registry, available_tool_names).

## Task Commits

1. **Task 1: Write failing test_deep_mode_prompt.py (RED)** - `349011e` (test)
2. **Task 2: Replace stubs in deep_mode_prompt.py (GREEN)** - `ede6654` (feat)

## Files Created/Modified

- `backend/app/services/deep_mode_prompt.py` — DEEP_MODE_SECTIONS stubs replaced with real Phase 19 guidance; module docstring updated 4->5 sections
- `backend/tests/services/test_deep_mode_prompt.py` — 6 unit tests for determinism, no volatile data, task/ask_user/error-recovery section presence, TASK-06 coexistence

## Decisions Made

- Test 6 uses subprocess `git diff` + `ast.parse` instead of live module import. `agent_service.py` has a module-level `get_system_settings()` DB call (line 24) that fires before any test fixture can patch it, making reliable import-based testing impossible without heavy conftest setup. The git diff + AST approach is simpler, faster, and directly verifies the TASK-06 invariant (file unmodified).
- DEEP_MODE_SECTIONS section count changed from 4 to 5. The KV-cache concern is content stability (deterministic output), not section count. Docstring updated accordingly.

## Deviations from Plan

None - plan executed exactly as written.

The only minor adjustment was Test 6 implementation: the plan suggested "Or simpler: assert git diff against agent_service.py is empty" as the preferred approach, and that is exactly what was implemented (subprocess git diff + AST signature check). No behavioral deviation from plan intent.

## Issues Encountered

- `agent_service.py` calls `get_system_settings()` at module-level (line 24), which fires a Supabase DB connection before any test patch can intercept it. Resolved by using subprocess git diff + ast.parse for Test 6 rather than live module import — directly aligned with the plan's stated preferred approach.

## Known Stubs

None — this plan's entire purpose was to eliminate Phase 17 stubs. Verified: `grep -c "STUB\|stub" backend/app/services/deep_mode_prompt.py` returns 0.

## Threat Flags

None — this plan modifies only a static string constant and its test. No new network endpoints, auth paths, or schema changes introduced.

## Next Phase Readiness

- Deep-mode system prompt now correctly describes all Phase 19 tools to the LLM
- LLM will see proper guidance when deep mode is active: how to call `task`, when to call `ask_user`, how to handle tool errors without expecting automatic retries
- Ready for Phase 20 Harness Engine Core which builds on Phase 19 foundations

---
*Phase: 19-sub-agent-delegation-ask-user-status-recovery*
*Completed: 2026-05-03*
