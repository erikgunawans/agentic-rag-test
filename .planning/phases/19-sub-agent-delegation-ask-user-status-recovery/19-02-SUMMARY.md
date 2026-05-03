---
phase: 19-sub-agent-delegation-ask-user-status-recovery
plan: 02
subsystem: backend-service
tags: [python, supabase, rls, tdd, agent_runs, state-machine, audit, phase19]

# Dependency graph
requires:
  - phase: 19-01
    provides: "agent_runs table (migration 040) live in production"
provides:
  - "agent_runs_service.py — full state-machine CRUD with RLS-scoped client and audit logging"
  - "test_agent_runs_service.py — 7 service-unit tests (all passing)"
affects:
  - 19-04 (sub_agent_loop.py uses agent_runs_service for status persistence)
  - 19-05 (chat.py resume-detection branch uses get_active_run)
  - 19-06 (ask_user tool dispatch uses set_pending_question)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "TDD RED/GREEN: 7 failing tests first, then implement to pass"
    - "RLS-scoped client exclusively (get_supabase_authed_client); no service-role client"
    - "Transactional UPDATE WHERE status='working' guard for race mitigation (T-19-RACE)"
    - "D-19 sanitization: error_detail truncated to 500 chars"
    - ".maybe_single() returns None when no rows match (Supabase Python client behavior) — use .execute() + rows[0] pattern instead"
    - "Audit log on every mutation with resource_type='agent_runs'"

key-files:
  created:
    - backend/app/services/agent_runs_service.py
    - backend/tests/services/test_agent_runs_service.py
  modified: []

key-decisions:
  - "Used .execute() + rows[0] pattern instead of .maybe_single() for get_active_run — .maybe_single() returns None (not an object with .data=None) when no rows match, causing AttributeError on result.data"
  - "transition_status clears pending_question when new_status='complete' to satisfy the bidirectional CHECK invariant: (status='waiting_for_user') = (pending_question IS NOT NULL)"
  - "Audit log user_id/user_email set to None for transition_status (generic path) since those callers don't always have user context; complete() and error() take explicit user_id/user_email"

patterns-established:
  - "agent_runs_service as the canonical state-machine for Phase 19 paused/resumable runs (TASK-04, ASK-04, STATUS-05)"
  - "Service-role client usage explicitly documented in module docstring as NOT used — mirrors agent_todos_service.py L14"

requirements-completed: [ASK-04, STATUS-05, STATUS-06]

# Metrics
duration: 3min
completed: 2026-05-03
---

# Phase 19 Plan 02: Agent Runs Service Summary

**agent_runs_service.py delivering full state-machine CRUD over the agent_runs table — RLS-scoped client, audit log on every mutation, transactional race guard, 7/7 tests green (TDD)**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-05-03T07:10:38Z
- **Completed:** 2026-05-03T07:13:00Z
- **Tasks:** 2 (TDD RED + GREEN)
- **Files created:** 2

## Accomplishments

- `backend/app/services/agent_runs_service.py` — 256-line service with full public API: `start_run`, `set_pending_question`, `transition_status`, `complete`, `error`, `get_active_run`
- `backend/tests/services/test_agent_runs_service.py` — 261-line TDD test suite: 7 async tests covering all state transitions, constraint enforcement, and resume-detection lookup
- All 7 tests pass against real Supabase production instance

## Public API Exported

```python
RunStatus = Literal["working", "waiting_for_user", "complete", "error"]

class AgentRunRecord(TypedDict):
    id: str
    thread_id: str
    status: RunStatus
    pending_question: str | None
    last_round_index: int
    error_detail: str | None

async def start_run(thread_id: str, user_id: str, user_email: str, token: str) -> AgentRunRecord
async def set_pending_question(run_id: str, question: str, last_round_index: int, token: str) -> None
async def transition_status(run_id: str, new_status: RunStatus, token: str, *, error_detail: str | None = None) -> None
async def complete(run_id: str, token: str, user_id: str, user_email: str) -> None
async def error(run_id: str, token: str, user_id: str, user_email: str, *, error_detail: str) -> None
async def get_active_run(thread_id: str, token: str) -> AgentRunRecord | None
```

## Test Results

7/7 passing:
1. `test_start_run_creates_working_row` — PASSED
2. `test_set_pending_question_transitions_to_waiting_for_user` — PASSED
3. `test_transition_status_completes_run` — PASSED
4. `test_error_run_records_error_detail` — PASSED
5. `test_get_active_run_returns_waiting_row` — PASSED
6. `test_get_active_run_returns_none_when_only_completed_rows_exist` — PASSED
7. `test_start_run_fails_when_active_run_already_exists` — PASSED

## Audit Log Action Types

| Function | action value | resource_type |
|----------|-------------|---------------|
| `start_run` | `agent_run_start` | `agent_runs` |
| `transition_status` | `agent_run_transition_{new_status}` | `agent_runs` |
| `complete` | `agent_run_complete` | `agent_runs` |
| `error` | `agent_run_error` | `agent_runs` |

## RLS-Scoped Client Confirmation

- `get_supabase_authed_client(token)` used 8 times (one per public function body)
- `get_supabase_client()` (service-role) is NOT imported or used anywhere in the module
- Module docstring explicitly states: "service-role client is never instantiated here"
- Grep gate passes: `grep -c "service_role\|service-role\|SUPABASE_SERVICE_ROLE_KEY" agent_runs_service.py` → 1 (documentation comment only, no code usage)

## Task Commits

1. **Task 1: Write failing tests (TDD RED)** — `3d20956` (test)
2. **Task 2: Implement agent_runs_service.py (TDD GREEN)** — `f903de7` (feat)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] .maybe_single() returns None for empty result sets**
- **Found during:** Task 2 (GREEN phase test run)
- **Issue:** 3 of 7 tests failed with `AttributeError: 'NoneType' object has no attribute 'data'` in `get_active_run`. The Supabase Python client's `.maybe_single()` method returns `None` (not an object with `.data = None`) when no rows match the query. Calling `result.data` on a `None` result raises AttributeError.
- **Fix:** Replaced `.maybe_single().execute()` with plain `.execute()` and added `rows = result.data or []` + `return rows[0] if rows else None` — semantically equivalent but handles the empty-result case correctly.
- **Files modified:** `backend/app/services/agent_runs_service.py`
- **Commit:** `f903de7` (same GREEN commit — discovered during first run, fixed before final commit)

**Total deviations:** 1 auto-fixed (Rule 1 — bug in Supabase client `.maybe_single()` usage)
**Impact:** No scope change. Semantics unchanged — returns first active row or None.

## Threat Mitigations

| Threat ID | Status |
|-----------|--------|
| T-19-PE (service-role bypass) | Mitigated — `get_supabase_authed_client` only; grep gate confirms no service-role client |
| T-19-RACE (concurrent set_pending_question) | Mitigated — `.eq("status", "working")` transactional guard in `set_pending_question` |
| T-19-AUDIT (audit gap) | Mitigated — 5 `audit_service.log_action` calls across all mutation paths |

## Known Stubs

None — all functions fully implemented and tested against real Supabase.

## Self-Check: PASSED

- `backend/app/services/agent_runs_service.py` — FOUND
- `backend/tests/services/test_agent_runs_service.py` — FOUND
- Commit `3d20956` (TDD RED) — FOUND
- Commit `f903de7` (TDD GREEN + bug fix) — FOUND
- 7/7 tests pass — VERIFIED

---
*Phase: 19-sub-agent-delegation-ask-user-status-recovery*
*Completed: 2026-05-03*
