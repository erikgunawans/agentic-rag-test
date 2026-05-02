# Phase 14: Sandbox HTTP Bridge — Pattern Map

**Generated:** 2026-05-02
**Phase:** 14 - Sandbox HTTP Bridge (Code Mode)

## Files To Create/Modify

| File | Role | Change Type |
|------|------|-------------|
| `backend/app/routers/bridge.py` | HTTP router (POST /bridge/call, GET /bridge/catalog, GET /bridge/health) | NEW |
| `backend/app/services/sandbox_bridge_service.py` | Token store, stub generation, stub injection | NEW |
| `backend/sandbox/Dockerfile` | Custom sandbox Docker image with ToolClient pre-baked | NEW |
| `backend/sandbox/tool_client.py` | ToolClient class using urllib.request | NEW |
| `backend/app/services/sandbox_service.py` | Add _check_dangerous_imports(), bridge_token field, env injection | MODIFY |
| `backend/app/config.py` | Add bridge_port: int = 8002 | MODIFY |
| `backend/app/main.py` | Conditional bridge router mount | MODIFY |
| `backend/app/routers/chat.py` | Emit code_mode_start SSE event | MODIFY |
| `backend/app/services/tool_service.py` | Prepend `from stubs import *\n` to code when bridge active | MODIFY |

---

## Analog Patterns

### 1. NEW: `backend/app/routers/bridge.py`

**Closest analog:** `backend/app/routers/code_execution.py`

**Pattern:**
```python
# backend/app/routers/code_execution.py (lines 1-30)
"""Code Execution router — Phase 10 / D-P10-17."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from app.dependencies import get_current_user
from app.database import get_supabase_authed_client, get_supabase_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/code-executions", tags=["code_executions"])

class CodeExecutionResponse(BaseModel):
    id: str
    user_id: str
    ...
```

**Apply to bridge.py:**
- Same import pattern: `APIRouter`, `Depends`, `HTTPException`, Pydantic models, `get_current_user`
- `router = APIRouter(prefix="/bridge", tags=["Bridge"])`
- Request/response Pydantic models: `BridgeCallRequest`, `BridgeCallResponse`, `BridgeCatalogResponse`
- Two-layer auth: outer `get_current_user` dependency (JWT) + inner `validate_token(session_token, user_id)` call to sandbox_bridge_service
- Thin router: all logic delegated to `sandbox_bridge_service`

---

### 2. NEW: `backend/app/services/sandbox_bridge_service.py`

**Closest analog:** `backend/app/services/sandbox_service.py` (module-level dict store + singleton pattern)

**Pattern (token store):**
```python
# backend/app/services/sandbox_service.py (lines ~57-70)
@dataclass
class SandboxSession:
    """Per-thread sandbox state."""
    container: object
    last_used: datetime
    thread_id: str

class SandboxService:
    def __init__(self) -> None:
        self._sessions: dict[str, SandboxSession] = {}
        self._cleanup_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()
```

**Apply to sandbox_bridge_service.py:**
```python
@dataclass
class BridgeTokenEntry:
    token: str
    user_id: str
    thread_id: str
    created_at: datetime

_TOKEN_STORE: dict[str, BridgeTokenEntry] = {}  # keyed by thread_id

def create_bridge_token(thread_id: str, user_id: str) -> str:
    token = str(uuid.uuid4())
    _TOKEN_STORE[thread_id] = BridgeTokenEntry(token=token, user_id=user_id, thread_id=thread_id, created_at=datetime.utcnow())
    return token

def validate_token(session_token: str, user_id: str) -> bool:
    entry = next((e for e in _TOKEN_STORE.values() if e.token == session_token), None)
    if entry is None:
        return False
    return entry.user_id == user_id

def revoke_token(thread_id: str) -> None:
    _TOKEN_STORE.pop(thread_id, None)
```

**Pattern (stub generation):**
```python
# backend/app/services/skill_catalog_service.py pattern (D-P8-05 — build a text block from tool data)
def _generate_stubs(active_tools: list[ToolDefinition]) -> str:
    lines = ["# Auto-generated tool stubs — do not edit"]
    lines.append("from tool_client import ToolClient as _TC")
    lines.append("_client = _TC()")
    for tool in active_tools:
        # extract params from tool.schema["function"]["parameters"]["properties"]
        # generate typed function stub
        ...
    return "\n".join(lines)
```

**Pattern (inject stubs):**
```python
# backend/app/services/sandbox_service.py execute_command pattern
# session.container.execute_command("ls /sandbox/output/")
async def inject_stubs(session: SandboxSession, active_tools: list) -> None:
    stub_code = _generate_stubs(active_tools)
    session.container.execute_command(
        f"python3 -c \"import sys; open('/sandbox/stubs.py','w').write(sys.stdin.read())\""
    )  # or loop-write approach if stdin not supported
```

---

### 3. NEW: `backend/sandbox/Dockerfile`

**Closest analog:** `backend/Dockerfile` (base Python image pattern)

**Pattern:**
```dockerfile
# backend/Dockerfile
FROM python:3.12-slim
RUN addgroup --system app && adduser --system --ingroup app app
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
...
```

**Apply to backend/sandbox/Dockerfile:**
```dockerfile
# Extends lexcore-sandbox:latest with ToolClient pre-baked
FROM python:3.12-slim
WORKDIR /sandbox
COPY tool_client.py /sandbox/tool_client.py
RUN mkdir -p /sandbox/output
# No extra pip installs — ToolClient uses stdlib urllib.request only
```

---

### 4. MODIFY: `backend/app/services/sandbox_service.py`

**Pattern for `_check_dangerous_imports`:**
```python
# backend/app/services/tool_service.py _WRITE_KEYWORDS pattern
_WRITE_KEYWORDS = re.compile(
    r'\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|REPLACE|MERGE)\b',
    re.IGNORECASE
)

# Apply same pattern in sandbox_service.py:
_DANGEROUS_IMPORT_PATTERNS = re.compile(
    r"import\s+subprocess|from\s+subprocess|"
    r"os\.(popen)|"
    r"import\s+socket|from\s+socket|"
    r"__import__",
    re.IGNORECASE,
)

def _check_dangerous_imports(code: str) -> str | None:
    m = _DANGEROUS_IMPORT_PATTERNS.search(code)
    return m.group(0) if m else None
```

**Pattern for env injection in `_create_container`:**
```python
# sandbox_service.py _create_container (lines ~135-162)
def _create_container(self) -> object:
    settings = get_settings()
    os.environ.setdefault("DOCKER_HOST", settings.sandbox_docker_host)
    container = SandboxSession(
        backend=SandboxBackend.DOCKER,
        lang=SupportedLanguage.PYTHON,
        image=settings.sandbox_image,
        keep_template=True,
        verbose=False,
        # ADD: environment=env_vars when bridge active
    )
    container.open()
    return container
```

**Pattern for bridge_token field on dataclass:**
```python
# Current SandboxSession dataclass:
@dataclass
class SandboxSession:
    container: object
    last_used: datetime
    thread_id: str
    # ADD:
    bridge_token: str | None = None
```

---

### 5. MODIFY: `backend/app/config.py`

**Pattern:**
```python
# backend/app/config.py (existing entries)
sandbox_enabled: bool = False
tool_registry_enabled: bool = False
sandbox_image: str = "lexcore-sandbox:latest"
sandbox_docker_host: str = "unix:///var/run/docker.sock"
# ADD:
bridge_port: int = 8002  # env var: BRIDGE_PORT
```

---

### 6. MODIFY: `backend/app/main.py`

**Pattern for conditional router mount:**
```python
# backend/app/main.py (existing unconditional mounts)
app.include_router(code_execution.router)

# Phase 14 pattern — conditional:
settings = get_settings()
if settings.sandbox_enabled and settings.tool_registry_enabled:
    from app.routers import bridge as bridge_router
    app.include_router(bridge_router.router)
```

---

### 7. MODIFY: `backend/app/routers/chat.py`

**Pattern for SSE event emission:**
```python
# backend/app/routers/chat.py (existing SSE event pattern)
yield f"data: {json.dumps({'type': 'agent_start', 'agent': agent_name, 'display_name': display_name})}\n\n"
# Also: code_stdout, code_stderr events

# Phase 14 adds:
if bridge_active and is_first_execute_code_call:
    yield f"data: {json.dumps({'type': 'code_mode_start', 'tools': available_tool_names})}\n\n"
```

---

### 8. MODIFY: `backend/app/services/tool_service.py`

**Pattern for code prepend:**
```python
# backend/app/services/tool_service.py _execute_code (lines ~1179+)
async def _execute_code(self, *, code: str, ...) -> dict:
    if not code:
        return {"error": "missing_code", ...}
    
    # Phase 14 ADD: prepend stubs import when bridge active
    settings = get_settings()
    if settings.sandbox_enabled and settings.tool_registry_enabled:
        code = "from stubs import *\n" + code
    
    result = await get_sandbox_service().execute(code=code, ...)
```

---

## Key Constraints from Codebase

1. **`SandboxSession` is a DATACLASS** (`@dataclass`), not a Pydantic model — `bridge_token: str | None = None` uses dataclass field syntax with default, not `Field(default=None)`.

2. **`_create_container` is synchronous** (`def`, not `async def`) — it uses `os.environ.setdefault` directly. Bridge token creation must also be synchronous; no `await` in `_create_container`.

3. **`get_sandbox_service()` uses `@lru_cache`** — it's a module-level singleton. `sandbox_bridge_service` should follow the same pattern: `_TOKEN_STORE` at module level (not on a class), accessed via module-scoped functions.

4. **Router registration in `main.py` uses bare `from app.routers import X`** — the conditional bridge mount must use a local import inside the `if` block to avoid importing the bridge module when flags are off (TOOL-05 lazy import invariant).

5. **All routers use `get_current_user` from `app.dependencies`** — not session-based auth. Bridge router follows same dependency injection pattern.

6. **SSE events use `json.dumps({"type": "...", ...})`** — flat dict, no nested envelope. `code_mode_start` follows the same format.

7. **`tool_service.py` uses `_WRITE_KEYWORDS = re.compile(...)`** as module-level compiled regex — `_DANGEROUS_IMPORT_PATTERNS` in `sandbox_service.py` follows the same pattern (compiled at import time, not per-call).

## PATTERN MAPPING COMPLETE
