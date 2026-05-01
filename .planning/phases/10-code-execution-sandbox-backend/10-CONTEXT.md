# Phase 10: Code Execution Sandbox Backend - Context

**Gathered:** 2026-05-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Implement the Docker-based Python sandbox using the `llm-sandbox` library with a Docker backend, IPython session persistence per thread, real-time stdout/stderr SSE streaming via a callback mechanism, generated-file upload to Supabase Storage, the `SANDBOX_ENABLED` feature flag gate, execution logging to a new `code_executions` table, and a custom pre-built Docker image. This is a **backend-only** phase.

**Deliverables:**
1. `backend/app/services/sandbox_service.py` — llm-sandbox session management, container lifecycle, TTL cleanup task
2. `backend/app/services/tool_service.py` patch — add `execute_code` to TOOL_DEFINITIONS; add `stream_callback` parameter to `execute_tool()`; gate tool on `SANDBOX_ENABLED`
3. `backend/app/routers/chat.py` patch — thread `stream_callback` through the tool loop to yield `code_stdout`/`code_stderr` SSE events during execution
4. `SandboxDockerfile` — custom Docker image build file (pushed to Docker Hub as `lexcore-sandbox:latest`)
5. Migration 036: `code_executions` table + `sandbox-outputs` Supabase Storage bucket policy
6. `backend/app/routers/code_execution.py` — `GET /code-executions?thread_id={id}` endpoint
7. `backend/app/config.py` additions: `SANDBOX_ENABLED`, `SANDBOX_IMAGE`, `SANDBOX_DOCKER_HOST`, `SANDBOX_MAX_EXEC_SECONDS`

**Out of scope (explicitly Phase 11):**
- Code Execution Panel in chat UI (SANDBOX-07) — Phase 11
- File download cards in chat — Phase 11
- Persistent tool memory (MEM-01..03) — Phase 11

</domain>

<decisions>
## Implementation Decisions

### Sandbox Runtime Backend

- **D-P10-01:** Use the `llm-sandbox` PyPI library with its **Docker backend**. True container isolation — LLM-generated code runs in a separate Docker container from the backend process. Best for legal-platform data privacy: user code cannot access backend memory or environment variables.
- **D-P10-02:** Configure Docker access on Railway via **Docker socket mount**: add `DOCKER_HOST=unix:///var/run/docker.sock` as a Railway environment variable and mount the host socket. No privileged mode needed. Standard pattern for DinD. Railway supports it.
- **D-P10-03:** Custom sandbox Docker image hosted on **Docker Hub as a public image** (`lexcore-sandbox:latest`). Add a `SandboxDockerfile` to the repo for reproducibility. llm-sandbox pulls it by name. Packages to pre-install: `pandas`, `matplotlib`, `python-pptx`, `jinja2`, `requests`, `beautifulsoup4`, `numpy`, `openpyxl`, `scipy`, `IPython`. Update the image by rebuilding and pushing when packages change.
- **D-P10-04:** **One container per thread session**, reused across all `execute_code` calls within that thread. Container created on first call, destroyed after 30-min idle TTL. This is how SANDBOX-02 variable persistence works across calls.

### Real-time SSE Streaming

- **D-P10-05:** Thread streaming through a **callback parameter on `execute_tool()`**. Signature: `execute_tool(name, args, user_id, ctx, stream_callback=None)`. The chat loop passes an async callback that closes over the SSE yield function. Only the `execute_code` branch invokes the callback; all other tools ignore it. Minimal blast radius — only `chat.py` and `tool_service.py` change.
- **D-P10-06:** `code_stdout` and `code_stderr` SSE events carry: `{ "type": "code_stdout"|"code_stderr", "line": "...", "tool_call_id": "..." }`. The `tool_call_id` associates each output line with the specific `execute_code` invocation, enabling the Phase 11 Code Execution Panel to buffer lines per call.
- **D-P10-07:** After all streaming completes, the `tool_result` SSE event contains: full stdout + full stderr text + signed URLs for any files generated in `/sandbox/output/`. The LLM receives the complete output so it can reference specific values in its response.
- **D-P10-08:** Python exceptions and tracebacks stream through `code_stderr` (unified — no separate event type). The `tool_result` includes `exit_code` and `error_type` fields so the LLM and frontend can distinguish error executions from successful ones.

### IPython Session Model

- **D-P10-09:** Sessions are **ephemeral** — lost on Railway restart or redeploy. Acceptable: legal platform users run self-contained analysis scripts, not multi-day sessions. No persistence layer needed.
- **D-P10-10:** 30-min TTL cleanup runs via an **asyncio background task launched every 60s** (matches SANDBOX-02 spec). Started on the first `execute_code` call; iterates the session dict and closes containers idle longer than 30min.
- **D-P10-11:** **One session per thread, no user-level concurrent cap**. A user with multiple open threads can have multiple active containers. For LexCore's bounded legal-team user base, this is acceptable.
- **D-P10-12:** **30-second per-call execution timeout**, separate from the 30-min session TTL. On timeout: stream `code_stderr` line "Execution timed out after 30s", return `exit_code=-1`, `error_type="timeout"`. Session container stays alive for the next call.

### code_executions Table & File Storage

- **D-P10-13:** Generated files from `/sandbox/output/` upload to a **new private `sandbox-outputs` Supabase Storage bucket**. Storage path: `{user_id}/{thread_id}/{execution_id}/{filename}`. Dedicated bucket enables independent lifecycle/retention policy management in the future.
- **D-P10-14:** Signed download URLs for generated files have a **1-hour TTL**. Short-lived URLs reduce exposure on a legal platform; users can re-run code to regenerate files if needed.
- **D-P10-15:** `code_executions` table RLS: **users see only their own executions** (`user_id = auth.uid()`). No UPDATE or DELETE for users — execution logs are immutable audit records. `super_admin` can read all rows (same pattern as `audit_log`). INSERT allowed for own records.
- **D-P10-16:** Migration **036** covers: `code_executions` table + `sandbox-outputs` bucket storage policy. (Migration 035 was `skill_files` + storage bucket policy in Phase 7.)
- **D-P10-17:** Phase 10 includes the **`GET /code-executions?thread_id={id}` list endpoint** in a new `code_execution.py` router. Phase 11's Code Execution Panel needs this to display execution history. Router + migration belong in the same phase.

### Claude's Discretion

- `sandbox_service.py` internal API: how to wrap `llm-sandbox`'s `SandboxSession` object, what state to store per session (container reference, last_used timestamp, thread_id).
- Migration 036 column definitions: reasonable defaults are `id UUID PK`, `user_id UUID`, `thread_id UUID`, `code TEXT`, `stdout TEXT`, `stderr TEXT`, `exit_code INT`, `execution_ms INT`, `status TEXT` ('success'|'error'|'timeout'), `files JSONB` (array of {filename, size_bytes, signed_url}), `created_at TIMESTAMPTZ`.
- `execute_code` tool input schema: `{ code: str, description: str | None }`. Description lets the LLM annotate what the code is doing for the execution log.
- The `llm-sandbox` package name on PyPI and exact import path to use in `sandbox_service.py`.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` §SANDBOX-01..06, 08 — All 7 sandbox requirements for this phase (SANDBOX-07 is Phase 11)

### Roadmap
- `.planning/ROADMAP.md` §Phase 10 — 6 success criteria (authoritative scope anchor)

### Prior Phase Decisions (binding)
- `.planning/phases/07-skills-database-api-foundation/07-CONTEXT.md` — D-P7-07/D-P7-09: Supabase Storage path convention and bucket pattern (reference when creating sandbox-outputs bucket)
- `.planning/phases/08-llm-tool-integration-discovery/08-CONTEXT.md` — D-P8-01/D-P8-04: Tool registration pattern (unconditional vs. gated), execute_tool() dispatch structure, TOOL_DEFINITIONS extension pattern

### Codebase Conventions
- `.planning/codebase/CONVENTIONS.md` — Router skeleton, migration pattern, audit pattern, response format
- `backend/app/services/tool_service.py` — **Primary integration point**: `TOOL_DEFINITIONS` list (add `execute_code` here) and `execute_tool()` dispatch switch (add case + `stream_callback` parameter here). Check Phase 8's `load_skill`/`save_skill`/`read_skill_file` additions as most recent examples.
- `backend/app/routers/chat.py` — **Tool loop integration point**: tool_start/tool_result emission (~lines 108-161). `stream_callback` must be threaded through here to yield `code_stdout`/`code_stderr` events during sandbox execution.
- `backend/app/routers/skills.py:218-237` — Supabase Storage upload pattern: `storage.from_("bucket").upload(path, content)` + DB insert. Reuse for sandbox file uploads.
- `backend/app/config.py` — Feature flag env var pattern to follow (see `TAVILY_API_KEY` gate as analog for `SANDBOX_ENABLED`). Add `SANDBOX_ENABLED`, `SANDBOX_IMAGE`, `SANDBOX_DOCKER_HOST`, `SANDBOX_MAX_EXEC_SECONDS` here.
- `backend/app/main.py` — Router registration: add `from app.routers import code_execution` and `app.include_router(code_execution.router)`.
- `supabase/migrations/035_*.sql` — Most recent migration as format reference. Migration 036 follows same structure.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `tool_service.py` `TOOL_DEFINITIONS` + `execute_tool()` — Extend exactly. Phase 8 added `load_skill`, `save_skill`, `read_skill_file` as the most recent examples of this extension pattern.
- `chat.py` tool loop (lines 108-161) — The `stream_callback` parameter threads through here. `execute_tool()` call site is where the callback is injected. `tool_start`/`tool_result` emit pattern is the reference.
- `skills.py:218-237` — Storage upload pattern: service-role client + `storage.from_("bucket").upload(path, content)` + DB `skill_files` insert. Exact same pattern for `sandbox-outputs` bucket.
- `audit_service.log_action()` — Call on each `execute_code` invocation for the audit trail (consistent with all other mutating operations).
- `get_supabase_client()` — Service-role client for sandbox file uploads (backend uploads on behalf of user; user JWT not needed for Storage write).
- `get_supabase_authed_client(token)` — RLS-scoped client for `code_executions` table reads (user sees own rows).

### Established Patterns
- **Feature flag gate** (`TAVILY_API_KEY` → `web_search` filtered from tool list when absent): same pattern for `SANDBOX_ENABLED=false` → `execute_code` absent from `TOOL_DEFINITIONS` list.
- **SSE event sequence** in `chat.py`: `tool_start → {code_stdout/code_stderr lines} → tool_result`. New `code_stdout`/`code_stderr` events insert between `tool_start` and `tool_result` for sandbox calls only.
- **Router pattern** (`clause_library.py`, `skills.py`): `APIRouter(prefix="/code-executions", tags=["code_executions"])` + Pydantic response model + auth dependency. `GET /?thread_id=` returns `{"data": [...], "count": N}`.
- **Migration pattern**: `CREATE TABLE ... ENABLE ROW LEVEL SECURITY` + `CREATE POLICY` blocks. Reference `035_*.sql`.

### Integration Points
- `tool_service.execute_tool()` — New `stream_callback: Optional[Callable] = None` parameter. Only `execute_code` branch uses it.
- `chat.py` tool loop — Pass `stream_callback` when calling `execute_tool()` for `execute_code`. Emit `code_stdout`/`code_stderr` SSE events from inside the callback.
- `backend/app/main.py` — Register `code_execution.router` alongside the 22 existing routers.
- Railway environment — Add `SANDBOX_ENABLED=true`, `SANDBOX_IMAGE=lexcore-sandbox:latest`, `DOCKER_HOST=unix:///var/run/docker.sock` to Railway project environment variables.

</code_context>

<specifics>
## Specific Ideas

- **Docker socket mount on Railway**: Set `DOCKER_HOST=unix:///var/run/docker.sock` as Railway env var. The Railway host's Docker socket is mounted into the container automatically when this is configured. Document this as a required Railway setup step.
- **`SANDBOX_ENABLED` gate**: Mirror the `TAVILY_API_KEY` pattern — check `settings.sandbox_enabled` in `get_available_tools()` and conditionally include/exclude `execute_code` from the returned tool list.
- **SSE callback closure pattern** (in chat.py):
  ```python
  async def sandbox_stream_callback(event_type: str, line: str):
      data = {"type": event_type, "line": line, "tool_call_id": tool_call.id}
      yield f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
  result = await tool_service.execute_tool(
      name, args, user_id, ctx, stream_callback=sandbox_stream_callback
  )
  ```
- **Session dict structure**: `_sessions: dict[str, SandboxSession]` where `SandboxSession` holds `{container, last_used: datetime, thread_id}`. Cleanup task checks `datetime.utcnow() - last_used > timedelta(minutes=30)`.
- **Sandbox image name**: `lexcore-sandbox:latest` — short, memorable, clear provenance.
- **Migration 036 table name**: `code_executions` (snake_case, plural, no abbreviation).

</specifics>

<deferred>
## Deferred Ideas

- **Code Execution Panel (SANDBOX-07)** — Phase 11. The SSE events (`code_stdout`/`code_stderr`) and the `GET /code-executions?thread_id={id}` endpoint are ready; the UI to display them is Phase 11's scope.
- **Persistent tool memory (MEM-01..03)** — Phase 11.
- **Per-user sandbox resource limits** (max concurrent containers, max execution memory) — future milestone if Railway resource contention becomes an issue.
- **Sandbox network access** (controlled outbound for web scraping) — explicitly deferred in REQUIREMENTS.md §Future Requirements.

</deferred>

---

*Phase: 10-Code Execution Sandbox Backend*
*Context gathered: 2026-05-01*
