---
phase: 10-code-execution-sandbox-backend
plan: "04"
subsystem: tool-integration
tags: [tool-integration, sandbox, llm, audit, execute-code, tdd]
dependency_graph:
  requires:
    - 10-03  # sandbox_service.py SandboxService built in Plan 03
  provides:
    - execute_code tool in LLM catalog
    - stream_callback kwarg on execute_tool()
    - code_executions DB persistence on each invocation
    - audit log on execute_code calls
  affects:
    - backend/app/services/tool_service.py
    - chat.py (Plan 05 unblocked: thread stream_callback through tool loop)
tech_stack:
  added: []
  patterns:
    - TDD (RED/GREEN/REFACTOR)
    - Four-part tool extension: TOOL_DEFINITIONS + get_available_tools gate + execute_tool dispatch + _execute_<name> handler
    - Feature-flag gate (SANDBOX-05): mirror TAVILY_API_KEY pattern
    - Fire-and-forget audit (try/except: pass) per chat.py line 327 pattern
    - Service-role INSERT for code_executions (bypass RLS on backend-side log)
key_files:
  modified:
    - backend/app/services/tool_service.py
  created:
    - backend/tests/services/test_tool_service_execute_code.py
decisions:
  - "TOOL_DEFINITIONS count: was 10 (Phase 8), now 11 after adding execute_code"
  - "stream_callback placed as last keyword-only param after token (Phase 8 pattern)"
  - "thread_id early-return guard (T-10-25): missing thread_id returns error dict without inserting orphan rows"
  - "_execute_code maps error_type to status: timeout->timeout, non-zero exit->error, else success"
metrics:
  duration_seconds: 321
  completed_date: "2026-05-01T08:35:44Z"
  tasks_completed: 1
  tasks_total: 1
  files_modified: 1
  files_created: 1
---

# Phase 10 Plan 04: execute_code Tool Integration Summary

**One-liner:** Wire `execute_code` into `ToolService` with SANDBOX-05 feature flag gate, `stream_callback` kwarg plumbing, `code_executions` DB persistence, and fire-and-forget audit log — 8/8 TDD tests pass.

## What Was Built

Extended `backend/app/services/tool_service.py` with four surgical edits:

1. **Import**: Added `from app.services.sandbox_service import get_sandbox_service` and `Callable` to typing imports.

2. **TOOL_DEFINITIONS** (Edit B): Appended `execute_code` entry with `required=['code']`, optional `description` field, and descriptive docstring about Docker sandbox, variable persistence, and file generation.

3. **get_available_tools gate** (Edit C): Added `elif name == "execute_code": if not settings.sandbox_enabled: continue` block, mirroring the existing TAVILY_API_KEY pattern. SANDBOX-05 invariant: when `SANDBOX_ENABLED=false` (default), `execute_code` is absent from the tool catalog the LLM sees.

4. **execute_tool signature** (Edit D): Appended `stream_callback: Callable | None = None` as the last keyword-only parameter. Other tools accept and silently ignore it per D-P10-05.

5. **Dispatch case** (Edit E): Added `elif name == "execute_code":` branch calling `_execute_code(code, description, user_id, thread_id, stream_callback)`.

6. **_execute_code handler** (Edit F): Full handler appended at end of file:
   - Input validation: missing `code` or `thread_id` returns error dict (T-10-25 guard)
   - Calls `get_sandbox_service().execute(code, thread_id, user_id, stream_callback)` (D-P10-05)
   - Maps sandbox output to status: `timeout` / `error` / `success`
   - Inserts 1 row to `code_executions` via service-role client (SANDBOX-06)
   - Calls `log_action(action="execute_code", resource_type="code_execution")` in `try/except: pass` (fire-and-forget)
   - Returns `{execution_id, stdout, stderr, exit_code, error_type, execution_ms, files, status}` per D-P10-07

## TDD Gate Compliance

- **RED phase**: 8 tests written and confirmed failing (7 failed, 1 accidentally passing — test 2 excluded execute_code trivially since it wasn't in TOOL_DEFINITIONS yet)
- **GREEN phase**: All 4 edits applied; `pytest tests/services/test_tool_service_execute_code.py -v` → **8/8 PASSED**
- **REFACTOR**: Not required — code is clean and follows established patterns

## Test Results

```
tests/services/test_tool_service_execute_code.py::TestToolDefinitionsSchema::test_execute_code_in_tool_definitions PASSED
tests/services/test_tool_service_execute_code.py::TestGetAvailableToolsGateOff::test_excludes_execute_code_when_disabled PASSED
tests/services/test_tool_service_execute_code.py::TestGetAvailableToolsGateOn::test_includes_execute_code_when_enabled PASSED
tests/services/test_tool_service_execute_code.py::TestExecuteToolSignature::test_stream_callback_parameter_exists PASSED
tests/services/test_tool_service_execute_code.py::TestStreamCallbackSilentIgnore::test_stream_callback_not_invoked_for_other_tools PASSED
tests/services/test_tool_service_execute_code.py::TestExecuteCodeDispatch::test_dispatches_to_sandbox_service PASSED
tests/services/test_tool_service_execute_code.py::TestCodeExecutionsPersistence::test_inserts_one_row_to_code_executions PASSED
tests/services/test_tool_service_execute_code.py::TestAuditLog::test_log_action_called_with_correct_params PASSED
```

Regression: `pytest tests/services/ -m "not docker"` → 29 passed, 1 failed (pre-existing PERF-02 latency test on dev hardware — documented in STATE.md Deferred Items, not caused by this plan).

## SANDBOX-05 Gate Verified

```
$ python -c "
from app.services.tool_service import ToolService
from app.config import get_settings
s = get_settings()
assert s.sandbox_enabled is False
ts = ToolService()
names = [t['function']['name'] for t in ts.get_available_tools()]
assert 'execute_code' not in names, 'SANDBOX-05 gate broken'
print('SANDBOX-05 gate OK')
"
SANDBOX-05 gate OK
```

## TOOL_DEFINITIONS Count

- **Before (Phase 8)**: 10 tools (search_documents, query_database, web_search, kb_list_files, kb_tree, kb_grep, kb_glob, kb_read, load_skill, save_skill, read_skill_file = 11 — plan doc stated 11)
- **After (Phase 10 Plan 04)**: 11 entries in the list (execute_code added at the end)

## Verification Checklist

- [x] `execute_code` entry in TOOL_DEFINITIONS with required=['code'] and properties {code, description}
- [x] `get_available_tools()` excludes execute_code when `settings.sandbox_enabled=False`
- [x] `get_available_tools()` includes execute_code when `settings.sandbox_enabled=True`
- [x] `execute_tool` signature has `stream_callback: Callable | None = None`
- [x] `execute_tool` has `elif name == "execute_code":` dispatch branch
- [x] `_execute_code` calls `get_sandbox_service().execute(code, thread_id, user_id, stream_callback)`
- [x] `_execute_code` INSERTs into `code_executions` (11 columns: id, user_id, thread_id, code, description, stdout, stderr, exit_code, execution_ms, status, files)
- [x] `_execute_code` calls `log_action(action="execute_code", resource_type="code_execution")`
- [x] Returns dict with: execution_id, stdout, stderr, exit_code, error_type, execution_ms, files, status
- [x] 8/8 unit tests pass
- [x] No regression in services test suite (pre-existing PERF-02 failure excluded)
- [x] `python -c "from app.main import app; print('OK')"` returns OK

## Plan 05 Unblocked

Plan 05 (chat.py) can now thread `stream_callback` through the tool loop:
```python
result = await tool_service.execute_tool(
    func_name, real_args, user_id, tool_context,
    registry=registry,
    token=token,
    stream_callback=sandbox_stream_callback if func_name == "execute_code" else None,
)
```

## Deviations from Plan

None — plan executed exactly as written. All four edits (A-F) applied as specified.

## Known Stubs

None — `execute_code` wires through to real SandboxService (built in Plan 03); all return values sourced from live execution result dict.

## Threat Flags

None — no new network endpoints, auth paths, or trust boundaries introduced. Threat register items T-10-20 through T-10-25 are all mitigated as designed.

## Self-Check: PASSED
