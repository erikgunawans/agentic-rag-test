---
phase: 17-deep-mode-foundation-planning-todos-plan-panel
plan: "02"
subsystem: config
tags: [pydantic, settings, env-vars, feature-flags, deep-mode, loop-caps]

# Dependency graph
requires: []
provides:
  - "Pydantic Settings fields: max_deep_rounds=50, max_tool_rounds=25, max_sub_agent_rounds=15, deep_mode_enabled=False"
  - "D-15 deprecated alias: TOOLS_MAX_ITERATIONS -> max_tool_rounds with DeprecationWarning"
  - ".env.example documentation for all four Phase 17 env vars"
affects:
  - "17-04-chat-loop-branch (consumes max_deep_rounds, max_tool_rounds, deep_mode_enabled)"
  - "17-05-rest-endpoint-todos (consumes deep_mode_enabled gate)"
  - "17-06-plan-panel-ui (consumes deep_mode_enabled for toggle visibility)"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "D-15 deprecated-alias model_validator: back-fill max_tool_rounds from TOOLS_MAX_ITERATIONS env with DeprecationWarning"
    - "D-16 dark-launch feature flag: deep_mode_enabled defaults False, mirrors TOOL_REGISTRY_ENABLED / SANDBOX_ENABLED"

key-files:
  created:
    - backend/tests/unit/test_config_deep_mode.py
  modified:
    - backend/app/config.py
    - backend/.env.example

key-decisions:
  - "D-14: Loop caps are deployment knobs (env-driven Pydantic Settings), NOT system_settings. Reason: Railway env, not admin-toggleable runtime settings."
  - "D-15: TOOLS_MAX_ITERATIONS preserved as one-milestone deprecated alias; back-fills max_tool_rounds + emits DeprecationWarning when no MAX_TOOL_ROUNDS env present."
  - "D-16: deep_mode_enabled defaults False for v1.3 dark-launch; mirrors TOOL_REGISTRY_ENABLED / SANDBOX_ENABLED precedent."

patterns-established:
  - "Phase 17 config block: clearly-marked comment section with D-* and CONF-* references inline"
  - "model_validator(mode='after') for deprecated env alias migration with warnings.warn(DeprecationWarning)"

requirements-completed: [CONF-01, CONF-02, CONF-03, DEEP-02]

# Metrics
duration: 2min
completed: "2026-05-02"
---

# Phase 17 Plan 02: Config Loop Caps and Feature Flag Summary

**Pydantic Settings extended with four Phase 17 env-driven deployment knobs: max_deep_rounds=50, max_tool_rounds=25, max_sub_agent_rounds=15, deep_mode_enabled=False; deprecated TOOLS_MAX_ITERATIONS alias with DeprecationWarning; 8-test TDD suite green**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-05-02T21:49:46Z
- **Completed:** 2026-05-02T21:51:51Z
- **Tasks:** 3 (TDD RED + GREEN + .env.example doc)
- **Files modified:** 3

## Accomplishments

- Added four new Pydantic Settings fields to `backend/app/config.py` (max_deep_rounds, max_tool_rounds, max_sub_agent_rounds, deep_mode_enabled) with env-var mapping and proper defaults per D-14/D-15/D-16.
- Implemented D-15 deprecated alias `_migrate_tools_max_iterations_alias` model_validator: when only `TOOLS_MAX_ITERATIONS` env is set (no `MAX_TOOL_ROUNDS`), back-fills `max_tool_rounds` and emits `DeprecationWarning`.
- Documented all four new env vars in `backend/.env.example` with default-value comments referencing CONF-01..03 and D-16 UAT instructions.
- 8-test TDD suite covering defaults, env overrides, alias back-fill with warning, and precedence — all passing.

## Task Commits

Each task was committed atomically:

1. **Task 1: Write failing unit tests for new Settings fields** - `52eeecd` (test)
2. **Task 2: Extend Settings with the four new fields + deprecated alias logic** - `22b3c7b` (feat)
3. **Task 3: Document new env vars in .env.example** - `86561b4` (docs)

_Note: TDD tasks have two commits (test RED then feat GREEN) as required by TDD flow._

## Files Created/Modified

- `backend/tests/unit/test_config_deep_mode.py` - 8 unit tests for new Settings fields (defaults, env overrides, D-15 alias, MAX_TOOL_ROUNDS precedence)
- `backend/app/config.py` - 4 new fields (max_deep_rounds, max_tool_rounds, max_sub_agent_rounds, deep_mode_enabled) + `_migrate_tools_max_iterations_alias` model_validator
- `backend/.env.example` - Phase 17 env var documentation block (MAX_DEEP_ROUNDS, MAX_TOOL_ROUNDS, MAX_SUB_AGENT_ROUNDS, DEEP_MODE_ENABLED)

## Decisions Made

- D-14: Loop caps placed in Pydantic Settings (env-driven) rather than `system_settings` table; these are deployment/infrastructure knobs, not admin-toggleable runtime settings. Matches `tools_max_iterations`, `llm_context_window` precedent.
- D-15: Kept `tools_max_iterations: int = 5` field untouched (for existing `chat.py` callers); added `max_tool_rounds` as the new canonical field. Plan 17-04 will switch `chat.py` to read `max_tool_rounds`.
- D-16: `deep_mode_enabled` defaults `False`. UI toggle hidden when off; `/chat` endpoint (Plan 17-04) rejects `deep_mode=true` payloads when off.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Worktree had no local `venv/` directory; resolved by using the main repo's venv with `PYTHONPATH` override for the worktree's source tree. Tests ran correctly against the worktree's config module.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. Only Pydantic Settings field additions — pure env-var configuration layer. T-17-05 (premature DEEP_MODE_ENABLED flag flip) mitigated by default `False` and explicit UAT guidance in `.env.example`.

## Known Stubs

None - this plan adds configuration fields only; no UI rendering or data pipelines.

## User Setup Required

New env vars available for operator use (all default-safe — no Railway env changes required to deploy this plan):

```bash
# Optional: override defaults in Railway environment
MAX_DEEP_ROUNDS=50
MAX_TOOL_ROUNDS=25
MAX_SUB_AGENT_ROUNDS=15
DEEP_MODE_ENABLED=false  # Flip to true after Phases 17+18+19 UAT
```

## Next Phase Readiness

- `backend/app/config.py` now exports `max_deep_rounds`, `max_tool_rounds`, `max_sub_agent_rounds`, `deep_mode_enabled` via `get_settings()`.
- Plan 17-04 (chat-loop branch) can immediately consume `settings.max_deep_rounds` and `settings.deep_mode_enabled` without any further config work.
- Plan 17-06 (Plan Panel UI) can read `deep_mode_enabled` flag to conditionally show the Deep Mode toggle.
- Existing `chat.py` callers of `settings.tools_max_iterations` remain unaffected until Plan 17-04 makes the switch.

## Self-Check

### Files Created/Modified Exist

- `backend/tests/unit/test_config_deep_mode.py` - FOUND (127 lines)
- `backend/app/config.py` - FOUND (modified with 4 new fields + validator)
- `backend/.env.example` - FOUND (Phase 17 block appended)

### Commits Exist

- `52eeecd` - FOUND (test: failing unit tests)
- `22b3c7b` - FOUND (feat: Settings extension)
- `86561b4` - FOUND (docs: .env.example)

### Verification

- `pytest tests/unit/test_config_deep_mode.py -v` → 8 passed
- `python -c "from app.main import app; print('OK')"` → OK
- `tools_max_iterations` field still present at line 73 (existing callers unaffected)

## Self-Check: PASSED

---
*Phase: 17-deep-mode-foundation-planning-todos-plan-panel*
*Completed: 2026-05-02*
