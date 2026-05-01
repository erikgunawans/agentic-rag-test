---
phase: 10-code-execution-sandbox-backend
plan: "03"
subsystem: sandbox-service
tags: [service, docker, sandbox, llm-sandbox, async, ttl, streaming, storage]
dependency_graph:
  requires:
    - 10-01  # migration 036 (code_executions table + sandbox-outputs bucket)
    - 10-02  # SandboxDockerfile + config.py settings
  provides:
    - sandbox_service.SandboxService
    - sandbox_service.SandboxSession
    - sandbox_service.get_sandbox_service
  affects:
    - 10-04  # tool_service._execute_code will call get_sandbox_service().execute()
    - 10-05  # chat.py threading of stream_callback
tech_stack:
  added:
    - llm-sandbox==0.3.39 (PyPI: llm-sandbox[docker])
    - asyncio.wait_for + run_in_executor (sync-to-async bridge)
  patterns:
    - singleton via @lru_cache
    - asyncio.create_task background cleanup loop (first-execute lazy start)
    - sync llm-sandbox callbacks bridged to async via run_coroutine_threadsafe
    - Supabase Storage upload + create_signed_url (1-hour TTL)
key_files:
  created:
    - backend/app/services/sandbox_service.py (399 lines)
    - backend/tests/services/test_sandbox_service.py (439 lines)
  modified:
    - backend/pyproject.toml (added docker pytest marker)
decisions:
  - "llm-sandbox v0.3.39: SandboxSession is a factory alias for create_session(); run() is synchronous — bridged via run_in_executor"
  - "StreamCallback is Callable[[str], None] (sync) — async stream_callback bridged via asyncio.run_coroutine_threadsafe"
  - "Magic numbers extracted to module-level constants: _CLEANUP_INTERVAL_SECONDS=60, _SESSION_IDLE_TTL_MINUTES=30, _SIGNED_URL_TTL_SECONDS=3600"
  - "File listing uses execute_command('ls /sandbox/output/') + copy_from_runtime() — no recursion to prevent path injection"
metrics:
  duration: "~15 minutes"
  completed: "2026-05-01"
  tasks_completed: 1
  tasks_total: 1
  files_created: 3
  files_modified: 1
---

# Phase 10 Plan 03: SandboxService Implementation Summary

Implemented `SandboxService` — the llm-sandbox wrapper that manages per-thread Docker container
sessions, 30-min TTL cleanup, per-call execution timeout, real-time streaming, and file upload to
Supabase Storage with 1-hour signed URLs.

## What Was Built

`backend/app/services/sandbox_service.py` (399 lines) exports:
- `SandboxSession` dataclass — `{container, last_used, thread_id}`
- `SandboxService` class — full lifecycle with all D-P10 contracts
- `get_sandbox_service()` — `@lru_cache` singleton accessor

### Key Implementation Details

**llm-sandbox import path resolved:**
```python
from llm_sandbox import SandboxBackend, SandboxSession, SupportedLanguage
```
Package: `llm-sandbox==0.3.39`. `SandboxSession` is a factory alias for `create_session()`.

**Sync-to-async bridge (critical deviation from plan stub):**
The plan's pseudo-code called `session.container.run()` as if it were async.
In practice, `run()` is synchronous (runs in a worker thread per llm-sandbox threading model).
The real implementation bridges it:
```python
result = await asyncio.wait_for(
    asyncio.get_event_loop().run_in_executor(
        None,
        lambda: session.container.run(code, on_stdout=on_stdout_sync, on_stderr=on_stderr_sync),
    ),
    timeout=settings.sandbox_max_exec_seconds,
)
```

**StreamCallback bridge:**
`StreamCallback = Callable[[str], None]` in llm-sandbox (synchronous). Our `stream_callback`
parameter is `Callable[[str, str], Awaitable[None]]` (async). Bridge:
```python
def on_stdout_sync(chunk: str) -> None:
    asyncio.run_coroutine_threadsafe(stream_callback("code_stdout", chunk), loop)
```

**Module-level constants (REFACTOR step):**
```python
_CLEANUP_INTERVAL_SECONDS = 60      # D-P10-10
_SESSION_IDLE_TTL_MINUTES = 30      # D-P10-10
_SIGNED_URL_TTL_SECONDS = 3600      # D-P10-14
```
These replace the literal magic numbers specified in the plan — semantic equivalence preserved.

**File listing for output upload:**
`_list_output_files()` uses `execute_command("ls /sandbox/output/")` to enumerate files,
then `copy_from_runtime(container_path, dest_path)` per file. No recursion (T-10-19 security).
Files with `/` in name are skipped to prevent storage path injection.

## Test Results

8 tests, 8 passed, 1 deselected (docker test):

| Test | Coverage |
|------|---------|
| TestConstructor | No I/O on init; empty _sessions; _cleanup_task=None |
| TestSessionReuse | Same thread_id reuses session dict identity (D-P10-04) |
| TestVariablePersistence | @pytest.mark.docker — skipped in CI |
| TestTimeout | exit_code=-1, error_type="timeout", stderr contains "timed out" (D-P10-12) |
| TestStreamCallback | async callback called >= 2 times for 2 print lines (D-P10-05) |
| TestCleanupLoop | 31-min stale session removed; fresh session kept (D-P10-10) |
| TestFileUpload | Correct 4-segment path, TTL=3600, signedURL returned (D-P10-13/14) |
| TestSingleton | get_sandbox_service() returns same instance across calls |
| TestReturnShape | All required keys present in execute() return dict |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Implementation Detail] sync-to-async bridge for run()**
- **Found during:** Task 1 (GREEN phase)
- **Issue:** The plan's pseudo-code showed `await session.container.run(...)` as if async. Actual llm-sandbox v0.3.39 `run()` is synchronous and blocks the calling thread.
- **Fix:** Wrapped in `asyncio.get_event_loop().run_in_executor(None, lambda: ...)` so `asyncio.wait_for` can enforce the timeout without blocking the event loop.
- **Files modified:** `backend/app/services/sandbox_service.py`

**2. [Rule 1 - Implementation Detail] StreamCallback sync/async mismatch**
- **Found during:** Task 1 (GREEN phase)
- **Issue:** `StreamCallback = Callable[[str], None]` in llm-sandbox is synchronous. Plan assumed async callbacks were passed directly.
- **Fix:** Sync bridge via `asyncio.run_coroutine_threadsafe(stream_callback(...), loop)` in the sync `on_stdout_sync`/`on_stderr_sync` callbacks.
- **Files modified:** `backend/app/services/sandbox_service.py`

**3. [Rule 3 - REFACTOR] Extracted magic numbers to module constants**
- **Trigger:** Plan step 3 (REFACTOR) explicitly requested extracting 60s, 30min, 3600s into constants
- **Applied during:** Implementation (combined with GREEN phase)
- **Files modified:** `backend/app/services/sandbox_service.py`

## Known Stubs

None. All required functionality is implemented. Plan 04 (`tool_service._execute_code`) can now import and call:
```python
from app.services.sandbox_service import get_sandbox_service

result = await get_sandbox_service().execute(
    code=arguments["code"],
    thread_id=context["thread_id"],
    user_id=user_id,
    stream_callback=stream_callback,
)
```

## Known Limitations

- **Live-Docker tests skipped in CI**: `TestVariablePersistence` is `@pytest.mark.docker` — requires a running Docker daemon and the `lexcore-sandbox:latest` image. Excluded from CI with `pytest -m "not docker"`.
- **Nested output directories**: Files in subdirectories of `/sandbox/output/` are not supported in v1. `_list_output_files()` uses flat `ls` listing; files with `/` in their name are skipped (T-10-19 security note documented in code).
- **No per-user container cap**: D-P10-11 decision — acceptable for LexCore's bounded user base.
- **Session eviction on restart**: D-P10-09 — container sessions are in-memory only. Railway restart clears all sessions.

## Threat Surface Scan

No new threat surface beyond what is documented in the plan's `<threat_model>` (T-10-12 through T-10-19). All mitigations are implemented:
- T-10-14 (DoS via infinite loop): `asyncio.wait_for` with `sandbox_max_exec_seconds` timeout
- T-10-18 (memory leak from never-closed sessions): 30-min TTL cleanup (Test 6)
- T-10-19 (filename path injection): flat listing + skip filenames containing `/`

## Self-Check: PASSED

- [x] `backend/app/services/sandbox_service.py` exists (399 lines)
- [x] `backend/tests/services/test_sandbox_service.py` exists (439 lines, 9 test cases)
- [x] All 8 non-docker tests pass: `pytest -m "not docker"` exits 0
- [x] Backend imports cleanly: `python -c "from app.main import app; print('OK')"` → OK
- [x] `get_sandbox_service()` returns same instance: verified via `assert svc1 is svc2`
- [x] Commit `40e01e9` (RED tests) exists
- [x] Commit `87c40f5` (GREEN implementation) exists
