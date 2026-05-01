---
phase: 10-code-execution-sandbox-backend
verified: 2026-05-01T09:00:00Z
status: human_needed
score: 8/8
overrides_applied: 0
human_verification:
  - test: "Run the backend with SANDBOX_ENABLED=true and Docker available, then send a chat message that triggers execute_code. Verify code_stdout/code_stderr SSE events appear in the browser network tab before tool_result arrives."
    expected: "Real-time line-by-line stdout/stderr events stream to frontend with shape {type, line, tool_call_id} during execution"
    why_human: "Requires live Docker daemon + running backend + frontend. asyncio.wait_for + run_in_executor bridge cannot be confirmed without a real container. Static analysis confirms the code path but not runtime SSE delivery."
  - test: "Confirm in Supabase dashboard that the code_executions table and sandbox-outputs bucket exist in project qedhulpfezucnfadlfiz. Run: SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='code_executions') AS table_exists, EXISTS(SELECT 1 FROM storage.buckets WHERE id='sandbox-outputs') AS bucket_exists;"
    expected: "Both table_exists and bucket_exists return TRUE"
    why_human: "The migration was applied via supabase db query -f (not the standard db push) due to duplicate 024 migration files. Production DB state is confirmed in 10-01-SUMMARY but cannot be re-verified programmatically without live Supabase credentials."
  - test: "Build the SandboxDockerfile and run it: docker build -f SandboxDockerfile -t lexcore-sandbox:test . && docker run --rm lexcore-sandbox:test python -c \"import pandas, matplotlib, pptx, jinja2, requests, bs4, numpy, openpyxl, scipy, IPython; print('all packages OK')\""
    expected: "All 10 D-P10-03 packages import successfully inside a non-root container"
    why_human: "Requires local Docker daemon to build and run the image. Static analysis of SandboxDockerfile confirms all packages are listed but cannot prove the build succeeds or that USER 1000:1000 has appropriate file permissions at runtime."
---

# Phase 10: Code Execution Sandbox Backend — Verification Report

**Phase Goal:** Build a Docker-based code-execution sandbox backend so the agent can run Python code (charts, document generation, scratch computation) in isolation, with one-container-per-thread variable persistence, real-time SSE streaming of stdout/stderr, automatic file uploads with signed URLs, RLS-enforced auditability, and a safe-off feature gate.

**Verified:** 2026-05-01T09:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `execute_code` tool executes Python in a Docker container and returns stdout/stderr | VERIFIED | `TOOL_DEFINITIONS` has `execute_code` entry; `_execute_code` handler dispatches to `get_sandbox_service().execute(code=..., thread_id=..., user_id=..., stream_callback=...)`; return dict includes `stdout`, `stderr`, `exit_code`. Runtime Docker execution needs human check (see Human Verification #1). |
| 2 | Variables persist across `run()` calls within a thread session (TTL 30min, auto-cleanup every 60s) | VERIFIED | `_sessions: dict[str, SandboxSession]` keyed by `thread_id`; `keep_template=True` on llm-sandbox `SandboxSession` preserves container between calls; `_cleanup_loop` runs `asyncio.sleep(60)` and evicts sessions where `last_used < datetime.utcnow() - timedelta(minutes=30)`. Unit test `test_stale_session_removed_by_cleanup` passes. |
| 3 | `code_stdout`/`code_stderr` SSE events stream to the frontend line-by-line during execution | VERIFIED (code path); human needed for runtime | Queue adapter pattern: `asyncio.Queue` created per `execute_code` call in `_run_tool_loop`; `sandbox_stream_callback` enqueues `{type, line, tool_call_id}` per chunk; drain loop yields `(event_type, evt)` while task runs. Both branches A and B in chat.py have `elif event_type in ("code_stdout", "code_stderr"):` special-case yielding live. 8/8 `test_chat_sandbox_streaming` tests pass. |
| 4 | Files written to `/sandbox/output/` are uploaded to Supabase Storage and returned as signed URLs | VERIFIED | `_list_output_files` uses `execute_command("ls /sandbox/output/")` + `copy_from_runtime`; `_collect_and_upload_files` constructs `{user_id}/{thread_id}/{execution_id}/{filename}` path and calls `storage.from_("sandbox-outputs").upload(...)` + `create_signed_url(path, 3600)`; test `test_file_uploaded_with_correct_path_and_ttl` passes with mocked Supabase client. |
| 5 | `execute_code` tool is absent from system prompt when `SANDBOX_ENABLED=false` | VERIFIED | `get_available_tools()` has `elif name == "execute_code": if not settings.sandbox_enabled: continue`; default `sandbox_enabled: bool = False` in config.py; live check: `assert 'execute_code' not in names` PASSES when `sandbox_enabled=False`. |
| 6 | All executions logged to `code_executions` table with exit code, timing, and status | VERIFIED | `_execute_code` handler does `client.table("code_executions").insert({id, user_id, thread_id, code, description, stdout, stderr, exit_code, execution_ms, status, files})` + `log_action(action="execute_code", resource_type="code_execution")`; both wrapped in `try/except` (fire-and-forget). 8/8 `test_tool_service_execute_code` tests pass (including insert assertion). |
| 7 | Custom Docker image pre-installs all D-P10-03 packages and runs non-root | VERIFIED (static) | `SandboxDockerfile` exists at repo root; `FROM python:3.11-slim`; all 10 packages (`pandas`, `matplotlib`, `python-pptx`, `jinja2`, `requests`, `beautifulsoup4`, `numpy`, `openpyxl`, `scipy`, `ipython`) confirmed present; `USER 1000:1000` on line 46 after all `RUN` commands (last RUN on line 43). Build + runtime needs human check. |
| 8 | `GET /code-executions?thread_id={id}` endpoint exists, RLS-scoped, with signed-URL refresh | VERIFIED | `code_execution.py` router: `APIRouter(prefix="/code-executions")`; `get_supabase_authed_client(user["token"])` for RLS; `_refresh_signed_urls` calls `create_signed_url(path, 3600)` per file; `{data: [...], count: N}` envelope; pagination `limit/offset`; registered in `main.py` (line 6 import + line 77 `include_router`); route `/code-executions` confirmed in `app.routes`. |

**Score:** 8/8 truths verified (3 require human runtime confirmation)

---

### Requirement ID Coverage

| Req-ID | Phase Plan | Description | Status | Evidence |
|--------|-----------|-------------|--------|----------|
| SANDBOX-01 | 10-02, 10-03, 10-04 | LLM can execute Python code in sandboxed Docker container via `execute_code` tool | VERIFIED | Tool registered in `TOOL_DEFINITIONS`, dispatches to `SandboxService` which uses llm-sandbox Docker backend |
| SANDBOX-02 | 10-03 | Python session persists variables across `run()` calls within a thread (30-min TTL, auto-cleanup) | VERIFIED | `_sessions` dict keyed by `thread_id`; `keep_template=True`; cleanup loop with 60s interval and 30-min idle cutoff |
| SANDBOX-03 | 10-05 | stdout/stderr stream to frontend via SSE events in real-time | VERIFIED (code); human needed runtime | Queue adapter pattern implemented; 8/8 streaming tests pass; 2 branch A/B special-case yields confirmed |
| SANDBOX-04 | 10-01, 10-03, 10-06 | Files in `/sandbox/output/` uploaded to Storage, returned as signed URLs | VERIFIED | Migration 036 creates bucket; `sandbox_service.py` uploads with 4-segment path; signed URLs with 1-hour TTL; router refreshes URLs at read time |
| SANDBOX-05 | 10-02, 10-04 | `execute_code` tool only registered when `SANDBOX_ENABLED=true` | VERIFIED | Gate confirmed live: `settings.sandbox_enabled` defaults `False`; `execute_code` absent from `get_available_tools()` output |
| SANDBOX-06 | 10-01, 10-04 | All executions logged in `code_executions` table | VERIFIED | `_execute_code` inserts row with all 11 columns + `log_action` audit; migration 036 creates table with RLS |
| SANDBOX-07 | (Phase 11 — deferred) | Chat shows inline Code Execution Panel | DEFERRED | Explicitly Phase 11 per CONTEXT.md and ROADMAP.md |
| SANDBOX-08 | 10-02 | Custom Docker image pre-installs common packages | VERIFIED (static) | `SandboxDockerfile` with all 10 D-P10-03 packages + non-root USER; human verification needed for actual build |

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `supabase/migrations/036_code_executions_and_sandbox_outputs.sql` | Migration with `code_executions` table + RLS + bucket + storage policies | VERIFIED | 100 lines; 12-column table; 2 table policies (SELECT+INSERT, no UPDATE/DELETE); bucket `sandbox-outputs` `public=false`; storage RLS on `[1]` not `[2]`; filename matches D-P10-16 exactly |
| `backend/requirements.txt` | Contains `llm-sandbox[docker]` | VERIFIED | Line 29: `llm-sandbox[docker]>=0.3.0` (pinned to `>=0.3.0` per project convention) |
| `SandboxDockerfile` | All 10 packages; USER 1000:1000 after RUN | VERIFIED | Exists at repo root; `FROM python:3.11-slim`; all 10 packages; `USER 1000:1000` line 46 after last `RUN` on line 43; no CMD |
| `backend/app/config.py` | 4 sandbox settings with correct defaults | VERIFIED | `sandbox_enabled=False`, `sandbox_image="lexcore-sandbox:latest"`, `sandbox_docker_host="unix:///var/run/docker.sock"`, `sandbox_max_exec_seconds=30`; confirmed by live `get_settings()` call |
| `backend/app/services/sandbox_service.py` | SandboxService class + singleton + SandboxSession dataclass | VERIFIED | 399 lines (>150 min); `SandboxSession` dataclass with `container/last_used/thread_id`; `get_sandbox_service()` singleton via `@lru_cache`; no `NotImplementedError` stubs; real llm-sandbox import on line 41 |
| `backend/app/services/tool_service.py` | execute_code in TOOL_DEFINITIONS; gate; stream_callback param; _execute_code handler | VERIFIED | Entry at line 336; gate at line 409-411; `stream_callback: Callable | None = None` at line 425; dispatch at line 520-527; `_execute_code` handler at line 1179 |
| `backend/app/routers/chat.py` | `thread_id` in `tool_context`; `asyncio.Queue`; `sandbox_stream_callback`; `code_stdout`/`code_stderr` events; 2 branch A/B special-cases | VERIFIED | `thread_id: body.thread_id` at line 179; `asyncio.Queue()` at line 255; `sandbox_stream_callback` at line 257; event shape `{type, line, tool_call_id}` at lines 283-285; 2 branch special-cases at lines 568 and 639 |
| `backend/app/routers/code_execution.py` | GET /code-executions; RLS; signed-URL refresh; {data, count} envelope | VERIFIED | 145 lines (>70 min); `APIRouter(prefix="/code-executions")`; `get_supabase_authed_client`; `_refresh_signed_urls` with `create_signed_url(path, 3600)`; `{data, count}` envelope |
| `backend/app/main.py` | `code_execution` router registered | VERIFIED | Line 6 import; line 77 `app.include_router(code_execution.router)`; confirmed via `app.routes` check |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `execute_code` tool definition | `TOOL_DEFINITIONS` list | Appended entry in `tool_service.py` | VERIFIED | `{"name": "execute_code", "required": ["code"], "properties": {code, description}}` |
| `get_available_tools()` | `settings.sandbox_enabled` | `elif name == "execute_code": if not settings.sandbox_enabled: continue` | VERIFIED | Gate confirmed working in live Python check |
| `execute_tool()` | `stream_callback` parameter | New `Callable | None = None` kwarg at signature | VERIFIED | All other tools receive `stream_callback=None` (4 call sites confirmed) |
| `_execute_code` | `SandboxService.execute` | `get_sandbox_service().execute(code=..., thread_id=..., user_id=..., stream_callback=...)` | VERIFIED | Direct call at line 1209 |
| `_execute_code` | `code_executions` table | `client.table("code_executions").insert({...})` | VERIFIED | 11 columns including `id`, `status`, `files`; service-role client |
| `_execute_code` | `audit_service.log_action` | `log_action(action="execute_code", resource_type="code_execution")` | VERIFIED | Try/except wrapped (fire-and-forget) at lines 1257-1271 |
| `SandboxService._collect_and_upload_files` | `sandbox-outputs` bucket | `storage.from_("sandbox-outputs").upload(path, content)` | VERIFIED | Path format `f"{user_id}/{thread_id}/{execution_id}/{filename}"` at line 326 |
| `SandboxService._collect_and_upload_files` | `create_signed_url` | `storage.from_("sandbox-outputs").create_signed_url(path, 3600)` | VERIFIED | Constant `_SIGNED_URL_TTL_SECONDS = 3600` |
| `chat.py sandbox_stream_callback` | `asyncio.Queue.put()` | `await sandbox_event_queue.put({"type": event_type, "line": emit_line, "tool_call_id": tc["id"]})` | VERIFIED | Two callback closures (redaction-on and test paths) |
| `chat.py drain loop` | SSE yield | `yield evt["type"], evt` while task runs; branch A/B special-case `yield f"data: {json.dumps(data)}\n\n"` | VERIFIED | 2 occurrences of `elif event_type in ("code_stdout", "code_stderr"):` confirmed |
| `GET /code-executions` | `code_executions` table | `get_supabase_authed_client(user["token"]).table("code_executions").select("*").eq("thread_id", thread_id)` | VERIFIED | RLS auto-filters by `user_id = auth.uid()` |
| `_refresh_signed_urls` | `sandbox-outputs` bucket | `get_supabase_client().storage.from_("sandbox-outputs").create_signed_url(path, 3600)` | VERIFIED | Service-role client used; stale-URL-kept on failure |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `chat.py` SSE stream | `code_stdout`/`code_stderr` events | `sandbox_stream_callback` enqueues chunks from `SandboxService.execute()` which bridges `on_stdout_sync`/`on_stderr_sync` callbacks to llm-sandbox `run(on_stdout=..., on_stderr=...)` | Yes — data flows from running container via llm-sandbox callbacks to queue to SSE; static verification confirmed | VERIFIED (static) |
| `tool_service._execute_code` | `result` dict | `get_sandbox_service().execute(...)` → llm-sandbox `session.container.run()` → stdout/stderr buffers | Yes — buffers populated by `on_stdout_sync`/`on_stderr_sync` during actual execution | VERIFIED (static) |
| `code_execution.py` list endpoint | `rows` | `client.table("code_executions").select("*").eq("thread_id", ...)` — RLS-scoped real DB query | Yes — real DB query, not hardcoded empty; `rows = result.data or []` with `_refresh_signed_urls` | VERIFIED |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Backend imports cleanly | `python -c "from app.main import app; print('OK')"` | OK | PASS |
| Sandbox config defaults correct | `get_settings()` assertions on all 4 fields | `sandbox_enabled=False, image=lexcore-sandbox:latest, host=unix:///var/run/docker.sock, max_exec=30s` | PASS |
| SANDBOX-05 gate: execute_code absent when disabled | `assert 'execute_code' not in get_available_tools()` | PASS — names: `['search_documents', 'query_database', 'web_search', ...]` | PASS |
| execute_code TOOL_DEFINITIONS schema | `required == ['code']`, `properties has code+description` | VERIFIED | PASS |
| `/code-executions` route registered | `[r.path for r in app.routes if 'code-executions' in r.path]` | `['/code-executions']` | PASS |
| SandboxService singleton | `get_sandbox_service() is get_sandbox_service()` | True | PASS |
| SandboxSession interface contract | `inspect.signature(SandboxService.execute)` — KEYWORD_ONLY params check | `contracts OK` | PASS |
| tool_service execute_code unit tests | `pytest tests/services/test_tool_service_execute_code.py` | `8 passed` | PASS |
| sandbox_service unit tests (no docker) | `pytest tests/services/test_sandbox_service.py -m "not docker"` | `8 passed, 1 deselected` | PASS |
| chat SSE streaming unit tests | `pytest tests/routers/test_chat_sandbox_streaming.py` | `8 passed` | PASS |

---

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| SANDBOX-01 | 10-02, 10-03, 10-04 | LLM executes Python via `execute_code` tool in Docker sandbox | SATISFIED | Tool registered, dispatched, SandboxService using llm-sandbox Docker backend |
| SANDBOX-02 | 10-03 | Variable persistence per thread, 30-min TTL, 60s cleanup | SATISFIED | `_sessions` dict + `keep_template=True` + cleanup loop verified |
| SANDBOX-03 | 10-05 | Stdout/stderr SSE events in real-time | SATISFIED (code; human needed for E2E) | Queue adapter + branch A/B special-case + 8 unit tests pass |
| SANDBOX-04 | 10-01, 10-03, 10-06 | Files → Storage signed URLs | SATISFIED | Migration 036 bucket + upload + sign in sandbox_service + router refresh |
| SANDBOX-05 | 10-02, 10-04 | `execute_code` gated by `SANDBOX_ENABLED` | SATISFIED | Gate verified live; default `False` confirmed |
| SANDBOX-06 | 10-01, 10-04 | All executions logged in `code_executions` | SATISFIED | Insert in `_execute_code` + `log_action` audit + immutable RLS |
| SANDBOX-07 | (Phase 11) | Code Execution Panel UI | DEFERRED | Explicitly out of Phase 10 scope (CONTEXT.md §Deferred) |
| SANDBOX-08 | 10-02 | Pre-built Docker image with packages | SATISFIED (static) | `SandboxDockerfile` with all 10 packages + non-root USER |

---

### D-P10 Decision Compliance

| Decision | Status | Evidence |
|----------|--------|---------|
| D-P10-01: llm-sandbox library, Docker backend | VERIFIED | `from llm_sandbox import SandboxBackend, SandboxSession, SupportedLanguage` line 41; `SandboxSession(backend=SandboxBackend.DOCKER, ...)` |
| D-P10-02: Docker socket mount via `DOCKER_HOST` env | VERIFIED | `os.environ.setdefault("DOCKER_HOST", settings.sandbox_docker_host)` in `_create_container` |
| D-P10-03: Docker Hub image `lexcore-sandbox:latest` with 10 packages | VERIFIED (static) | `sandbox_image: str = "lexcore-sandbox:latest"` default; all 10 packages in SandboxDockerfile |
| D-P10-04: One container per thread, reused | VERIFIED | `_sessions[thread_id]` lookup returns existing session; only creates new on miss |
| D-P10-05: `stream_callback` parameter on `execute_tool` | VERIFIED | `stream_callback: Callable | None = None` kwarg on both `execute_tool` and `_execute_code` |
| D-P10-06: `{type, line, tool_call_id}` SSE event shape | VERIFIED | `await sandbox_event_queue.put({"type": event_type, "line": emit_line, "tool_call_id": tc["id"]})` |
| D-P10-07: Full payload in `tool_result` | VERIFIED | `_execute_code` returns `{execution_id, stdout, stderr, exit_code, error_type, execution_ms, files, status}` |
| D-P10-08: Timeout/exceptions unify in stderr; exit_code distinguishes | VERIFIED | `TimeoutError` → `stderr_buf.append(f"Execution timed out after {N}s")`, `exit_code=-1`, `error_type="timeout"` |
| D-P10-09: In-memory sessions only | VERIFIED | `self._sessions: dict[str, SandboxSession] = {}` — no DB persistence |
| D-P10-10: 60s cleanup loop, 30-min TTL | VERIFIED | `asyncio.sleep(60)` + `timedelta(minutes=30)` confirmed in source + test |
| D-P10-11: No per-user concurrent cap | VERIFIED | No quota check in `_get_or_create_session` |
| D-P10-12: `asyncio.wait_for` timeout = `settings.sandbox_max_exec_seconds` (default 30) | VERIFIED | `asyncio.wait_for(..., timeout=settings.sandbox_max_exec_seconds)` in `execute()` |
| D-P10-13: Storage path `{user_id}/{thread_id}/{execution_id}/{filename}` | VERIFIED | `f"{user_id}/{thread_id}/{execution_id}/{filename}"` in both sandbox_service and migration RLS `[1]` gate |
| D-P10-14: Signed URL TTL = 3600s | VERIFIED | `_SIGNED_URL_TTL_SECONDS = 3600`; `create_signed_url(path, 3600)` in both sandbox_service and code_execution router |
| D-P10-15: SELECT own+super_admin; INSERT own; no UPDATE/DELETE | VERIFIED | Migration 036: exactly 2 policies on `code_executions`; `grep -E "FOR (UPDATE|DELETE).*code_executions"` returns 0 matches |
| D-P10-16: Migration filename `036_code_executions_and_sandbox_outputs.sql` | VERIFIED | File exists at exactly that path |
| D-P10-17: `GET /code-executions?thread_id={id}` endpoint in Phase 10 | VERIFIED | Router created and registered; route `/code-executions` confirmed in `app.routes` |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `sandbox_service.py` | 316, 319, 367, 370 | `return []` | Info | Error guard paths (except blocks); data-fetching runs before these; not stubs |
| `code_execution.py` | 77 | `return []` | Info | Exception handling in `_refresh_signed_urls`; non-blocking stale-URL fallback |
| `sandbox_service.py` | 199, 266 | `datetime.utcnow()` (deprecated in Python 3.12+) | Warning | Will generate `DeprecationWarning` on Python 3.14. Non-blocking — behavior is correct |

No blockers found. All `return []` are legitimate error-path guards with real data-fetching code above them.

---

### Human Verification Required

#### 1. E2E SSE Streaming During execute_code

**Test:** With Docker available and `SANDBOX_ENABLED=true` in `.env`, start the backend (`uvicorn app.main:app --reload --port 8000`), open the frontend, send a message that triggers `execute_code` (e.g., "run: print('hello')"). Inspect the browser DevTools Network tab → EventSource stream.

**Expected:** Before the `tool_result` event appears, one or more `data:` lines with `{"type": "code_stdout", "line": "hello\n", "tool_call_id": "..."}` should be visible.

**Why human:** Requires live Docker daemon, running backend, and frontend. The asyncio `run_in_executor` bridge between llm-sandbox's synchronous `run()` callbacks and the async queue cannot be confirmed without a real container. The queue drain loop's `asyncio.wait_for(queue.get(), timeout=0.1)` polling pattern needs runtime validation to confirm events are not dropped.

#### 2. Supabase Production DB State Verification

**Test:** Log into the Supabase dashboard for project `qedhulpfezucnfadlfiz` and run in the SQL editor:

```sql
SELECT
  EXISTS(SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'code_executions') AS table_exists,
  EXISTS(SELECT 1 FROM storage.buckets WHERE id = 'sandbox-outputs') AS bucket_exists;
```

Also verify RLS policies:

```sql
SELECT policyname, cmd FROM pg_policies WHERE tablename = 'code_executions';
-- Expected: code_executions_select (SELECT) and code_executions_insert (INSERT) — no UPDATE/DELETE
```

**Expected:** Both `table_exists` and `bucket_exists` return `TRUE`. Exactly 2 policies on `code_executions`.

**Why human:** Migration was applied via `supabase db query -f` workaround (documented in 10-01-SUMMARY due to duplicate `024_*.sql` file version conflict). Production DB state confirmed by plan executor but requires human re-confirmation since automated verification cannot access live Supabase credentials.

#### 3. SandboxDockerfile Build Smoke Test

**Test:** From the repo root, run:

```bash
docker build -f SandboxDockerfile -t lexcore-sandbox:test .
docker run --rm lexcore-sandbox:test python -c "import pandas, matplotlib, pptx, jinja2, requests, bs4, numpy, openpyxl, scipy, IPython; print('all packages OK')"
docker run --rm --user 1000:1000 lexcore-sandbox:test python -c "import os; print('uid:', os.getuid(), 'gid:', os.getgid())"
```

**Expected:** Build completes without error; first run prints `all packages OK`; second run prints `uid: 1000 gid: 1000`.

**Why human:** Requires local Docker daemon. Static analysis confirms correct Dockerfile content but cannot prove the build produces a working image with proper non-root runtime permissions.

---

### Gaps Summary

No gaps blocking goal achievement. All 8 ROADMAP success criteria are satisfied at the code level. 3 human verification items remain for runtime/infrastructure confirmation:

1. E2E SSE streaming requires live Docker + running server
2. Production Supabase DB state requires dashboard access
3. SandboxDockerfile build requires local Docker

These are infrastructure/runtime confirmations, not code deficiencies. The implementation is complete and all automated tests pass (24/24 unit tests across 3 test suites).

---

### Deferred Items

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | Code Execution Panel UI (SANDBOX-07) | Phase 11 | Phase 11 goal: "Surface sandbox results in the chat UI with a streaming Code Execution Panel"; REQUIREMENTS.md traceability: `SANDBOX-07 | Phase 11` |

---

_Verified: 2026-05-01T09:00:00Z_
_Verifier: Claude (gsd-verifier)_
