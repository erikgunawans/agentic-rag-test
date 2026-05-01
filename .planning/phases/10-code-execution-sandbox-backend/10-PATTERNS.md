# Phase 10: Code Execution Sandbox Backend — Pattern Map

**Mapped:** 2026-05-01
**Files analyzed:** 9 (3 NEW, 6 MODIFY)
**Analogs found:** 9 / 9

## File Classification

| New/Modified File | Type | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|------|-----------|----------------|---------------|
| `backend/app/services/sandbox_service.py` | NEW | service | event-driven + container lifecycle | `backend/app/services/tool_service.py` (handler shape); `backend/app/services/redaction_service.py` (singleton + lifecycle) | role-match |
| `backend/app/services/tool_service.py` | MODIFY | service | request-response + stream-callback | Phase 8 `load_skill`/`save_skill`/`read_skill_file` extension (lines 245–331, 456–478, 874–1126) | exact (extension pattern) |
| `backend/app/routers/chat.py` | MODIFY | router | SSE streaming | Phase 5 `_run_tool_loop` skeleton emit (lines 180–365); Phase 8 token kwarg plumbing (line 274, 466, 532) | exact (extension pattern) |
| `SandboxDockerfile` | NEW | config | build artifact | `backend/Dockerfile` (existing pattern with RUN spaCy install pre-USER switch) | role-match |
| `supabase/migrations/036_*.sql` | NEW | migration | DDL + RLS + storage bucket | `supabase/migrations/035_skill_files_table_and_bucket.sql` | exact |
| `backend/app/routers/code_execution.py` | NEW | router | request-response (read-only) | `backend/app/routers/skills.py` (lines 20, 90, 278–318) | exact (router skeleton) |
| `backend/app/config.py` | MODIFY | config | settings | `tavily_api_key` + `tools_enabled` flag (lines 64–66); `embedding_provider` Literal pattern (lines 60–61) | exact |
| `backend/app/main.py` | MODIFY | bootstrap | router registration | Existing 22-router include block (lines 6, 55–76) | exact |
| `backend/requirements.txt` | MODIFY | config | dependency manifest | Existing requirements (no diff to extract — append-only) | n/a |

---

## Pattern Assignments

### `backend/app/services/sandbox_service.py` (NEW — service, event-driven + container lifecycle)

**Analogs:**
- **Tool handler shape** → `backend/app/services/tool_service.py` (Phase 8 handlers lines 874–1126)
- **Singleton pattern** → `backend/app/services/tool_service.py` line 359 (`class ToolService: def __init__(self): self.hybrid_service = HybridRetrievalService()`)
- **`@traced` instrumentation** → `tool_service.py` line 380 (`@traced(name="execute_tool")`)
- **D-P10-04 session-per-thread** → No exact analog — pattern derived from CONTEXT.md §Specific Ideas (`_sessions: dict[str, SandboxSession]`)

**Imports pattern** (mirror tool_service.py lines 1–13):
```python
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Callable, Awaitable

from app.services.tracing_service import traced
from app.config import get_settings
from app.database import get_supabase_client

logger = logging.getLogger(__name__)
settings = get_settings()
```

**Per-session state structure** (CONTEXT.md §Specific Ideas, line 133):
```python
@dataclass
class SandboxSession:
    container: object        # llm-sandbox SandboxSession opaque handle
    last_used: datetime
    thread_id: str

class SandboxService:
    def __init__(self):
        self._sessions: dict[str, SandboxSession] = {}
        self._cleanup_task: asyncio.Task | None = None
```

**Cleanup task launch pattern** (D-P10-10 — model after `main.py` lifespan warm-up at lines 15–28; defer cleanup task spawn to first `execute_code` call):
```python
async def _ensure_cleanup_task(self):
    if self._cleanup_task is None or self._cleanup_task.done():
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

async def _cleanup_loop(self):
    while True:
        await asyncio.sleep(60)  # SANDBOX-02 spec: every 60s
        cutoff = datetime.utcnow() - timedelta(minutes=30)
        stale = [tid for tid, s in self._sessions.items() if s.last_used < cutoff]
        for tid in stale:
            try:
                self._sessions[tid].container.close()
            except Exception:
                logger.warning("sandbox cleanup failed for thread=%s", tid, exc_info=True)
            self._sessions.pop(tid, None)
```

**Per-call execution + streaming pattern** (D-P10-05/06/08/12):
```python
async def execute(
    self,
    *,
    code: str,
    thread_id: str,
    user_id: str,
    stream_callback: Callable[[str, str], Awaitable[None]] | None = None,
) -> dict:
    """Returns {stdout, stderr, exit_code, error_type, files, execution_ms}."""
    await self._ensure_cleanup_task()
    session = self._get_or_create_session(thread_id)
    session.last_used = datetime.utcnow()
    started = datetime.utcnow()
    stdout_buf, stderr_buf = [], []

    async def on_stdout(line: str):
        stdout_buf.append(line)
        if stream_callback:
            await stream_callback("code_stdout", line)

    async def on_stderr(line: str):
        stderr_buf.append(line)
        if stream_callback:
            await stream_callback("code_stderr", line)

    try:
        result = await asyncio.wait_for(
            session.container.run(code, on_stdout=on_stdout, on_stderr=on_stderr),
            timeout=settings.sandbox_max_exec_seconds,
        )
        exit_code, error_type = result.exit_code, None
    except asyncio.TimeoutError:
        await on_stderr(f"Execution timed out after {settings.sandbox_max_exec_seconds}s")
        exit_code, error_type = -1, "timeout"
    # ... return dict
```

**Error handling pattern** (mirror `tool_service.py` lines 540–543):
```python
except Exception as e:
    logger.error("sandbox execute failed: %s", e)
    return {"error": str(e), "stdout": "", "stderr": str(e), "exit_code": -1}
```

**File upload pattern (skills.py lines 218–232 reuse)** — see Shared Patterns §Storage Upload below.

---

### `backend/app/services/tool_service.py` (MODIFY — service, request-response + stream-callback)

**Analog:** Phase 8 extension pattern — `load_skill`/`save_skill`/`read_skill_file` (lines 245–331, 456–478, 874–1126).

**TOOL_DEFINITIONS append** (mirror lines 245–331 — placement after `read_skill_file` at line 330):
```python
# ── Phase 10: Code Execution Sandbox tool (D-P10-05 gated) ─────────
{
    "type": "function",
    "function": {
        "name": "execute_code",
        "description": (
            "Execute Python code in a sandboxed Docker container. "
            "Variables persist across calls within the same conversation thread. "
            "Use for data analysis, calculations, file generation (write to /sandbox/output/), "
            "or any task requiring runtime computation."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code to execute. Use stdout for results.",
                },
                "description": {
                    "type": "string",
                    "description": "Brief description of what this code does (for execution log).",
                },
            },
            "required": ["code"],
        },
    },
},
```

**Feature-flag gate pattern** (extend `get_available_tools` lines 362–378 — same shape as Tavily check):
```python
def get_available_tools(self, *, web_search_enabled: bool = True) -> list[dict]:
    tools = []
    for tool in TOOL_DEFINITIONS:
        name = tool["function"]["name"]
        if name == "web_search":
            if not web_search_enabled:
                continue
            if not settings.tavily_api_key:
                continue
        elif name == "execute_code":
            if not settings.sandbox_enabled:   # D-P10 SANDBOX-05 gate
                continue
        tools.append(tool)
    return tools
```

**`execute_tool` signature extension** (mirror Phase 5 `registry` and Phase 8 `token` kwargs at lines 380–406):
```python
@traced(name="execute_tool")
async def execute_tool(
    self,
    name: str,
    arguments: dict,
    user_id: str,
    context: dict | None = None,
    *,
    registry: "ConversationRegistry | None" = None,  # Phase 5 D-86
    token: str | None = None,                        # Phase 8
    stream_callback: Callable | None = None,         # Phase 10 D-P10-05
) -> dict:
    """...
    Phase 10 D-P10-05: Accepts an optional ``stream_callback`` keyword arg
    used ONLY by the execute_code branch to emit code_stdout/code_stderr
    SSE events. Other tools ignore it (parameter received, never invoked).
    """
```

**Dispatch case append** (mirror lines 472–478 `read_skill_file` block — append before `else`):
```python
elif name == "execute_code":
    return await self._execute_code(
        code=arguments.get("code", ""),
        description=arguments.get("description"),
        user_id=user_id,
        thread_id=(context or {}).get("thread_id"),
        stream_callback=stream_callback,
    )
```

**Handler implementation pattern** (mirror `_execute_load_skill` lines 876–933):
- `@traced(name="tool_execute_code")` decorator
- Validate inputs → return `{"error": ...}` on missing
- Delegate to `sandbox_service.execute(...)`
- Persist row to `code_executions` via `get_supabase_client()`
- Call `log_action(...)` (mirror `_execute_save_skill` lines 1001–1011 audit emit)
- Return `{"stdout", "stderr", "exit_code", "files", "execution_id"}` for the LLM

---

### `backend/app/routers/chat.py` (MODIFY — router, SSE streaming)

**Analog:** Phase 5 `_run_tool_loop` (lines 180–365); Phase 8 token plumbing (lines 274, 466, 532).

**`stream_callback` injection inside tool loop** (modify the `execute_tool` call sites at lines 271–275 and 299–302). The closure pattern from CONTEXT.md §Specific Ideas:
```python
# Inside the per-tool-call branch in _run_tool_loop, BEFORE execute_tool:
async def sandbox_stream_callback(event_type: str, line: str):
    """D-P10-05/06: emit code_stdout/code_stderr SSE events tagged with tool_call_id."""
    data = {"type": event_type, "line": line, "tool_call_id": tc["id"]}
    # NOTE: the SSE yield happens via a queue-style buffer because _run_tool_loop
    # is itself an async generator; direct yield from inside this callback is not
    # valid. The implementation must use asyncio.Queue or similar adapter.
    await sandbox_event_queue.put(data)

# Pass through:
tool_output = await tool_service.execute_tool(
    func_name, real_args, user_id, tool_context,
    registry=registry,
    token=token,
    stream_callback=sandbox_stream_callback if func_name == "execute_code" else None,
)
```

**Important deviation note for the planner:** Because `_run_tool_loop` is an async generator (uses `yield`), the callback pattern shown in CONTEXT.md §Specific Ideas (which calls `yield f"event: ..."` directly inside the closure) is not directly compatible. The planner must choose between:
1. **Queue adapter**: spin up a side `asyncio.Queue` consumer task that drains queued events to `yield`s in the parent generator.
2. **Generator-yielded streaming**: refactor `_execute_code` to itself return an async generator, and have `_run_tool_loop` `yield from` it.

Either approach preserves the existing "yield event_type, data" contract that `event_generator()` consumes at lines 459–476 and 525–541.

**SSE event sequence** (existing pattern — see lines 237–243 `tool_start` and 344–351 `tool_result`):
```
tool_start → {0..N code_stdout/code_stderr lines} → tool_result
```

**`tool_context` augmentation** (lines 173–178 — add `thread_id` so handler can address the right session):
```python
tool_context = {
    "top_k": settings.rag_top_k,
    "threshold": settings.rag_similarity_threshold,
    "embedding_model": sys_settings.get("custom_embedding_model") or sys_settings["embedding_model"],
    "llm_model": llm_model,
    "thread_id": body.thread_id,   # Phase 10 D-P10-04: needed by execute_code handler
}
```

**Redaction-mode skeleton emit** (D-P10 must respect Phase 5 D-89 — see lines 236–243): the `code_stdout`/`code_stderr` events likely contain user code output that may include real PII when redaction is OFF. When `redaction_on=True`, planner should decide whether to emit skeleton-only `{type: code_stdout}` (no `line`) and buffer; or to anonymize each line via `anonymize_tool_output` before emit. CONTEXT.md does not address this — flag for planner decision.

---

### `SandboxDockerfile` (NEW — config, build artifact)

**Analog:** `backend/Dockerfile` (existing pattern — referenced in CLAUDE.md gotchas: spaCy `RUN python -m spacy download xx_ent_wiki_sm` BEFORE `USER app` switch).

**Pattern to copy:**
- `FROM python:3.11-slim` base
- `WORKDIR /sandbox`
- `RUN pip install --no-cache-dir <packages>` for D-P10-03 packages: `pandas matplotlib python-pptx jinja2 requests beautifulsoup4 numpy openpyxl scipy ipython`
- `RUN mkdir -p /sandbox/output && chmod 755 /sandbox/output`
- `USER 1000:1000` (non-root, matches the security posture of `backend/Dockerfile`)
- No `CMD` — llm-sandbox manages container exec

**Build/push** (manual, documented in plan):
```bash
docker build -f SandboxDockerfile -t lexcore-sandbox:latest .
docker tag lexcore-sandbox:latest <dockerhub-user>/lexcore-sandbox:latest
docker push <dockerhub-user>/lexcore-sandbox:latest
```

---

### `supabase/migrations/036_*.sql` (NEW — migration)

**Analog:** `supabase/migrations/035_skill_files_table_and_bucket.sql` (exact format — table + RLS + bucket + storage policies).

**Naming convention** (mirror 035): `036_code_executions_and_sandbox_outputs.sql`

**Header pattern** (mirror 035 lines 1–6):
```sql
-- Migration 036: code_executions table + sandbox-outputs storage bucket
-- Phase 10 / D-P10-13..D-P10-16 — foundation for SANDBOX-04, SANDBOX-06
-- Depends on: 035_skill_files_table_and_bucket.sql
-- All table DDL uses CREATE IF NOT EXISTS; bucket INSERT uses ON CONFLICT DO NOTHING.
```

**Table definition** (CONTEXT.md §Claude's Discretion line 62 — column list authoritative):
```sql
CREATE TABLE IF NOT EXISTS public.code_executions (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  thread_id     UUID NOT NULL REFERENCES public.threads(id) ON DELETE CASCADE,
  code          TEXT NOT NULL,
  description   TEXT,
  stdout        TEXT NOT NULL DEFAULT '',
  stderr        TEXT NOT NULL DEFAULT '',
  exit_code     INTEGER NOT NULL DEFAULT 0,
  execution_ms  INTEGER NOT NULL DEFAULT 0,
  status        TEXT NOT NULL CHECK (status IN ('success','error','timeout')),
  files         JSONB NOT NULL DEFAULT '[]'::jsonb,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_code_executions_thread
  ON public.code_executions(thread_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_code_executions_user
  ON public.code_executions(user_id, created_at DESC);
```

**RLS pattern** (D-P10-15 — adapt from 035 lines 51–97; SELECT for own rows OR super_admin; INSERT for own rows; no UPDATE/DELETE):
```sql
ALTER TABLE public.code_executions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "code_executions_select"
  ON public.code_executions
  FOR SELECT
  USING (
    user_id = auth.uid()
    OR (auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin'
  );

CREATE POLICY "code_executions_insert"
  ON public.code_executions
  FOR INSERT
  WITH CHECK (user_id = auth.uid());

-- No UPDATE / DELETE policies — execution log is immutable audit record (D-P10-15).
```

**Bucket creation** (mirror 035 lines 99–107):
```sql
INSERT INTO storage.buckets (id, name, public)
VALUES ('sandbox-outputs', 'sandbox-outputs', false)
ON CONFLICT (id) DO NOTHING;
```

**Storage RLS** (mirror 035 lines 119–174; path scheme `{user_id}/{thread_id}/{execution_id}/{filename}` per D-P10-13 — note 4-segment path differs from skills' 3-segment):
```sql
-- SELECT: readable iff first segment is auth.uid()
CREATE POLICY "sandbox-outputs SELECT"
  ON storage.objects
  FOR SELECT
  USING (
    bucket_id = 'sandbox-outputs'
    AND (storage.foldername(objects.name))[1] = auth.uid()::text
  );

-- INSERT: service-role uploads on behalf of user (CONTEXT.md line 102 reuses
-- get_supabase_client() pattern). With service-role bypass, INSERT policy
-- still gates direct user uploads — caller UID must match folder.
CREATE POLICY "sandbox-outputs INSERT"
  ON storage.objects
  FOR INSERT
  WITH CHECK (
    bucket_id = 'sandbox-outputs'
    AND (storage.foldername(objects.name))[1] = auth.uid()::text
  );

-- No DELETE policy — generated files are retention-managed at bucket level.
```

**Cycle-2 NEW-H1 / objects.name disambiguation lesson** (035 line 139–142): in any future EXISTS subquery against this bucket, use `storage.objects.name` not bare `name` to avoid ambiguous column resolution.

---

### `backend/app/routers/code_execution.py` (NEW — router, request-response read-only)

**Analog:** `backend/app/routers/skills.py` (lines 1–20 imports + router; lines 90, 278–318 endpoint shape).

**Imports + router declaration** (mirror skills.py lines 1–20):
```python
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from app.dependencies import get_current_user
from app.database import get_supabase_authed_client, get_supabase_client

router = APIRouter(prefix="/code-executions", tags=["code_executions"])
```

**Pydantic response model** (mirror skills.py SkillResponse at lines 67–82):
```python
class CodeExecutionResponse(BaseModel):
    id: str
    user_id: str
    thread_id: str
    code: str
    description: str | None
    stdout: str
    stderr: str
    exit_code: int
    execution_ms: int
    status: str  # 'success' | 'error' | 'timeout'
    files: list[dict]  # [{filename, size_bytes, signed_url}]
    created_at: datetime
```

**`GET /` list endpoint** (mirror skills.py `list_skills` lines 278–318):
```python
@router.get("", response_model=dict)
async def list_code_executions(
    thread_id: str = Query(...),  # D-P10-17 contract: thread_id REQUIRED
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
):
    client = get_supabase_authed_client(user["token"])
    # RLS auto-filters to user's own rows (D-P10-15)
    result = (
        client.table("code_executions")
        .select("*")
        .eq("thread_id", thread_id)
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    rows = [CodeExecutionResponse(**r) for r in (result.data or [])]
    # Refresh signed URLs at read time (1-hour TTL per D-P10-14)
    svc = get_supabase_client()
    for row in rows:
        for f in row.files:
            if "storage_path" in f:
                signed = svc.storage.from_("sandbox-outputs").create_signed_url(
                    f["storage_path"], 3600
                )
                f["signed_url"] = signed.get("signedURL")
    return {"data": [r.model_dump() for r in rows], "count": len(rows)}
```

**Response envelope** (matches Phase 7 convention from skills.py:318): `{"data": [...], "count": N}`.

---

### `backend/app/config.py` (MODIFY — config, settings)

**Analog:** Existing `tavily_api_key`/`tools_enabled` pair (lines 64–66) for the on/off feature gate; `embedding_provider` Literal (lines 60–61) for typed env vars.

**Append after line 71 (sub-agents block):**
```python
# Phase 10: Code Execution Sandbox (SANDBOX-01..06, 08; D-P10-01..D-P10-17)
sandbox_enabled: bool = False  # D-P10 SANDBOX-05: gate on/off, default OFF
sandbox_image: str = "lexcore-sandbox:latest"  # D-P10-03 Docker Hub image
sandbox_docker_host: str = "unix:///var/run/docker.sock"  # D-P10-02 Railway socket mount
sandbox_max_exec_seconds: int = 30  # D-P10-12 per-call execution timeout
```

**Note on validator**: no `@model_validator` needed — `sandbox_enabled=False` is a safe default. CONTEXT.md does not require a startup validation.

---

### `backend/app/main.py` (MODIFY — bootstrap, router registration)

**Analog:** Existing 22-router include block (lines 6, 55–76).

**Import addition** (modify line 6 — append `code_execution` to the existing tuple import):
```python
from app.routers import threads, chat, documents, document_tools, admin_settings, user_preferences, audit_trail, obligations, clause_library, document_templates, approvals, user_management, regulatory, notifications, dashboard, integrations, google_export, bjr, compliance_snapshots, pdp, folders, skills, code_execution
```

**Router registration** (append after line 76 — `app.include_router(skills.router)`):
```python
app.include_router(code_execution.router)
```

---

### `backend/requirements.txt` (MODIFY — config, dependency)

**No analog excerpt needed.** Append-only:
```
llm-sandbox[docker]
```

CONTEXT.md §Claude's Discretion (line 64): exact PyPI package name and import path is for the planner to verify against context7 / pypi.org during execution. The `[docker]` extra installs the Docker backend specifically.

---

## Shared Patterns

### Auth — `get_current_user` dependency
**Source:** `backend/app/dependencies.py` (used in skills.py:91, chat.py:93)
**Apply to:** `code_execution.py` (every endpoint), `tool_service.py` (already plumbed via `user_id` + `token`)
```python
from app.dependencies import get_current_user
@router.get("...")
async def handler(user: dict = Depends(get_current_user)):
    # user = {"id": str, "email": str, "token": str, "role": str}
```

### RLS-scoped DB access — `get_supabase_authed_client(token)`
**Source:** `backend/app/database.py` (used in skills.py:92, tool_service.py:888)
**Apply to:** `code_execution.py` list endpoint (RLS auto-filters by `user_id = auth.uid()`)
```python
from app.database import get_supabase_authed_client
client = get_supabase_authed_client(user["token"])
result = client.table("code_executions").select("*").eq("thread_id", thread_id).execute()
```

### Service-role DB/Storage access — `get_supabase_client()`
**Source:** `backend/app/database.py` (used in skills.py:573 for global file downloads)
**Apply to:**
- `sandbox_service.py` for uploading generated files to `sandbox-outputs` (CONTEXT.md line 102: backend uploads on behalf of user)
- `code_execution.py` for refreshing signed URLs (CONTEXT.md D-P10-14: 1-hour TTL)

### Storage upload pattern
**Source:** `backend/app/routers/skills.py` lines 218–232 (Phase 7 / D-P7-09)
**Apply to:** `sandbox_service.py` per-execution file upload
```python
# Path scheme per D-P10-13: {user_id}/{thread_id}/{execution_id}/{filename}
storage_path = f"{user_id}/{thread_id}/{execution_id}/{filename}"
client.storage.from_("sandbox-outputs").upload(
    storage_path,
    file_bytes,
    {"content-type": detected_mime},
)
```

### Signed URL generation — 1-hour TTL (D-P10-14)
**Source:** No exact analog in codebase (skills.py uses `download()` not `create_signed_url()`).
**Apply to:** `sandbox_service.py` (post-upload) and `code_execution.py` (refresh on list).
```python
signed = client.storage.from_("sandbox-outputs").create_signed_url(storage_path, 3600)
url = signed.get("signedURL") or signed.get("signed_url")
```
**Note for planner:** verify exact key name in supabase-py 2.7.4 response shape.

### Audit logging — `log_action(...)`
**Source:** `backend/app/services/audit_service.py` (used in skills.py:109, tool_service.py:1001)
**Apply to:** `tool_service._execute_code` after each invocation (mirror Phase 8 CR-01 fix pattern from `_execute_save_skill` lines 1001–1011)
```python
from app.services.audit_service import log_action
try:
    log_action(
        user_id=user_id,
        user_email=None,  # tool path has no user_email plumbing
        action="execute_code",
        resource_type="code_execution",
        resource_id=str(execution_id),
        details={"thread_id": thread_id, "exit_code": exit_code, "status": status},
    )
except Exception:
    pass  # audit is fire-and-forget per existing pattern (chat.py line 327)
```

### Feature-flag gate
**Source:** `backend/app/services/tool_service.py` lines 372–376 (Tavily gate)
**Apply to:** `tool_service.get_available_tools` — exclude `execute_code` from list when `not settings.sandbox_enabled` (D-P10 SANDBOX-05).

### `@traced` instrumentation
**Source:** `backend/app/services/tool_service.py` lines 380, 482, 545, 574, 608, 659, 698, 738, 790, 876, 935, 1059
**Apply to:** Every public method on `SandboxService` and the new `_execute_code` handler in `ToolService`. Naming convention: `tool_<name>` for tool handlers, plain name for service methods.
```python
from app.services.tracing_service import traced

@traced(name="tool_execute_code")
async def _execute_code(self, ...): ...

@traced(name="sandbox_execute")
async def execute(self, ...): ...
```

### Migration filename + header convention
**Source:** `supabase/migrations/035_skill_files_table_and_bucket.sql` (lines 1–6)
**Apply to:** `036_code_executions_and_sandbox_outputs.sql`
- Sequential 3-digit number with underscore + snake_case description
- Header lines: migration number + phase + plan + dependencies + idempotency note

### Pre-push checks (CLAUDE.md §Pre-Push Checks)
**Source:** Project-wide standard
**Apply to:** All MODIFY files
```bash
cd backend && python -c "from app.main import app; print('OK')"
```
PostToolUse hook auto-runs this on .py edits.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `SandboxDockerfile` | Docker build | n/a | `backend/Dockerfile` exists but is for the API service, not a sandbox image. The packages and posture differ. Use it as a structural reference (USER switch, RUN ordering) but the file content is novel. |
| `sandbox_service.py` (lifecycle/cleanup task) | service | event-driven background task | No existing `asyncio.create_task` background task pattern in services. `redaction_service.py` uses lru_cache singleton + lifespan warm-up but not a recurring background loop. Cleanup loop pattern derives from CONTEXT.md §Specific Ideas only. |
| `signed URL generation` | storage helper | request-response | skills.py uses `.download()` to materialize bytes; no codebase site calls `create_signed_url()`. Planner must verify supabase-py 2.7.4 method signature. |

---

## Key Patterns Identified

1. **Tool extension** is a four-part contract: append to `TOOL_DEFINITIONS`, add gate in `get_available_tools` (if conditional), add dispatch case in `execute_tool`, implement `_execute_<name>` handler with `@traced` + try/except + dict return shape.
2. **kwargs plumbing** (`registry`, `token`, now `stream_callback`) — every cross-cutting concern threads through `execute_tool` as a keyword-only optional. Other tools accept and silently ignore.
3. **Migration shape** (035) — table CREATE IF NOT EXISTS + indexes + ALTER TABLE ENABLE RLS + per-action POLICY blocks + bucket INSERT ON CONFLICT DO NOTHING + storage.objects POLICY blocks. RLS-immutable resources (audit, this case) skip UPDATE/DELETE policies.
4. **RLS-scoped vs service-role split** — user-facing reads use `get_supabase_authed_client(user["token"])` (RLS auto-filter). Admin operations and on-behalf-of uploads use `get_supabase_client()` (service-role). Both clients available in every handler.
5. **Audit fire-and-forget** — `log_action()` calls always wrapped in `try/except: pass` so audit failures never break business logic.
6. **SSE event sequence** — `tool_start → {progressive events} → tool_result → delta → done:true`. Phase 10 inserts `code_stdout`/`code_stderr` between `tool_start` and `tool_result` for sandbox calls only.

---

## Metadata

**Analog search scope:**
- `backend/app/services/` (tool_service.py, redaction_service.py reference)
- `backend/app/routers/` (chat.py, skills.py, code_execution.py target dir)
- `backend/app/` (config.py, main.py, dependencies.py)
- `supabase/migrations/` (035 as 036 template)

**Files scanned:** 9 directly read; cross-references verified through CONTEXT.md upstream pointers.

**Pattern extraction date:** 2026-05-01
