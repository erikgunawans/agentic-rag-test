---
phase: 15-mcp-client-integration
plan: 03
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/app/config.py
  - backend/app/main.py
  - backend/requirements.txt
  - backend/.env.example
autonomous: true
requirements:
  - MCP-01
  - MCP-02
must_haves:
  truths:
    - "backend/app/config.py Settings class has field 'mcp_servers: str = \"\"' with comment explaining MCP_SERVERS env var format"
    - "backend/requirements.txt contains 'mcp' package entry under a '# MCP Client (Phase 15)' comment section"
    - "backend/app/main.py lifespan hook calls get_mcp_client_manager().startup() after get_redaction_service() warmup, gated by 'if settings.tool_registry_enabled and settings.mcp_servers.strip()'"
    - "backend/app/main.py lifespan hook calls get_mcp_client_manager().shutdown() after yield in the finally/cleanup section"
    - "MCP startup in lifespan is wrapped in try/except Exception with logger.warning on failure (non-critical startup failure pattern)"
    - "With settings.tool_registry_enabled=False or settings.mcp_servers empty, the startup() call is never reached — no import at module level"
    - "backend/.env.example has MCP_SERVERS= entry with format comment"
  artifacts:
    - path: "backend/app/config.py"
      provides: "mcp_servers: str = '' Settings field"
      contains: "mcp_servers"
    - path: "backend/requirements.txt"
      provides: "mcp package dependency"
      contains: "^mcp"
    - path: "backend/app/main.py"
      provides: "MCPClientManager startup/shutdown in lifespan hook"
      contains: "mcp_client_manager"
    - path: "backend/.env.example"
      provides: "MCP_SERVERS documentation"
      contains: "MCP_SERVERS"
  key_links:
    - from: "backend/app/main.py"
      to: "backend/app/services/mcp_client_manager.py"
      via: "get_mcp_client_manager() imported conditionally inside lifespan"
      pattern: "get_mcp_client_manager"
    - from: "backend/app/config.py"
      to: "backend/app/main.py"
      via: "settings.mcp_servers and settings.tool_registry_enabled gate the startup call"
      pattern: "mcp_servers"
---

<objective>
Wire the MCP subsystem into the application's configuration and startup lifecycle:

1. **`backend/app/config.py`** — add `mcp_servers: str = ""` Pydantic Settings field (reads `MCP_SERVERS` env var).
2. **`backend/requirements.txt`** — add `mcp` Python SDK dependency.
3. **`backend/app/main.py`** — add `MCPClientManager.startup()` call in the `lifespan` hook (after `get_redaction_service()` warmup), wrapped in `try/except`, gated by flag + env var. Add `MCPClientManager.shutdown()` after `yield`.
4. **`backend/.env.example`** — add `MCP_SERVERS=` documentation entry.

This plan is Wave 1 and can run in parallel with 15-01 (registry availability) and 15-02 (MCPClientManager core). However, to avoid import errors at smoke-test time, Plan 15-02 must complete first so `mcp_client_manager.py` exists when `main.py` is imported. In practice, wave 1 plans run sequentially in the executor — the ordering within wave 1 is: 15-01, 15-02, then 15-03 (though they have no explicit `depends_on`).

MCP-05 (SC #5): with empty `MCP_SERVERS` or `TOOL_REGISTRY_ENABLED=false`, the gate in main.py ensures `startup()` is never reached and no processes are spawned.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/phases/15-mcp-client-integration/15-CONTEXT.md
@backend/app/config.py
@backend/app/main.py
@backend/requirements.txt
</context>

<tasks>

<task id="1">
<name>Add mcp_servers field to backend/app/config.py</name>
<read_first>
- backend/app/config.py (full file — find sandbox_enabled and tool_registry_enabled fields, insert after)
</read_first>
<action>
In `backend/app/config.py`, find the block containing `tool_registry_enabled: bool = False` (Phase 13 addition). After that block, add the `mcp_servers` field:

```python
    # Phase 15 (MCP-01): MCP server connection config.
    # Format: 'name:command:args' (split on first 2 colons; args is shlex-split).
    # Multiple servers: comma-separated. Empty = no MCP servers, zero startup cost (MCP-05).
    # Example: 'github:npx:-y @modelcontextprotocol/server-github'
    # Example (multi): 'github:npx:-y @modelcontextprotocol/server-github,postgres:python:server.py'
    mcp_servers: str = ""
```

The field should be added INSIDE the `Settings` class, after `tool_registry_enabled: bool = False`.
</action>
<acceptance_criteria>
- `grep -n "mcp_servers" backend/app/config.py` returns a match
- `cd backend && source venv/bin/activate && python -c "from app.config import get_settings; s = get_settings.__wrapped__(); print(s.mcp_servers)"` prints an empty string (default)
- `cd backend && source venv/bin/activate && python -c "from app.config import Settings; s = Settings(mcp_servers='test:cmd:arg', supabase_url='x', supabase_anon_key='x', supabase_service_role_key='x', openai_api_key='x'); print(s.mcp_servers)"` prints `test:cmd:arg`
- `cd backend && source venv/bin/activate && python -c "from app.main import app; print('OK')"` prints `OK`
</acceptance_criteria>
</task>

<task id="2">
<name>Add mcp SDK to backend/requirements.txt</name>
<read_first>
- backend/requirements.txt (end of file — find the last section, add after it)
</read_first>
<action>
In `backend/requirements.txt`, add a new section at the end of the file:

```
# MCP Client (Phase 15 — MCP-01..06)
mcp
```

The `mcp` package installs the official Python MCP SDK. No version pin initially — use the latest stable (the SDK is still evolving rapidly and version pinning causes more churn than value at this stage).
</action>
<acceptance_criteria>
- `grep -n "^mcp$" backend/requirements.txt` returns a match (bare `mcp` package name on its own line)
- `grep -n "MCP Client" backend/requirements.txt` returns a match (the comment line)
</acceptance_criteria>
</task>

<task id="3">
<name>Add MCPClientManager startup/shutdown to backend/app/main.py lifespan</name>
<read_first>
- backend/app/main.py (full file — examine lifespan structure and imports)
- backend/app/services/mcp_client_manager.py (get_mcp_client_manager signature)
</read_first>
<action>
In `backend/app/main.py`, make two targeted changes:

**Change 1 — Import:** Add the import for `get_mcp_client_manager` at the top of the file, after the existing service imports. Use a conditional pattern so the import is always present but the actual startup is flag-gated:

Add this import near the top (with the other service imports):
```python
from app.services.mcp_client_manager import get_mcp_client_manager
```

**Change 2 — Lifespan hook:** Modify the `lifespan` async context manager to:
1. Add MCP startup AFTER the `get_redaction_service()` warmup block
2. Add MCP shutdown AFTER the `yield`

The updated `lifespan` function should look like:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_tracing()
    # PERF-01 / D-15: eager warm-up so the first chat request doesn't pay
    # the Presidio + spaCy model load. Wrapped in try/except matching the
    # existing supabase-recovery pattern — if the warm-up trips on Railway
    # (e.g. a model-download blip), we log a warning and let boot continue
    # rather than block the whole API. I15: use logger.warning, not print.
    try:
        get_redaction_service()
    except Exception:
        logger.warning(
            "get_redaction_service() warm-up failed", exc_info=True
        )
    # Phase 15 (MCP-01..06 / D-P15-01): start MCP client manager if configured.
    # Non-critical: failure logs a warning and boot continues (MCP is additive).
    # Gate: only runs when TOOL_REGISTRY_ENABLED=true AND MCP_SERVERS is non-empty.
    if settings.tool_registry_enabled and settings.mcp_servers.strip():
        try:
            await get_mcp_client_manager().startup()
        except Exception:
            logger.warning(
                "MCPClientManager startup failed — MCP tools unavailable", exc_info=True
            )
    # Recover any docs stalled in 'processing' from a previous crash
    try:
        get_supabase_client().table("documents").update(
            {"status": "pending"}
        ).eq("status", "processing").execute()
    except Exception:
        pass
    yield
    # Phase 15 (D-P15-02): clean up MCP connections on shutdown.
    if settings.tool_registry_enabled and settings.mcp_servers.strip():
        try:
            await get_mcp_client_manager().shutdown()
        except Exception:
            logger.warning("MCPClientManager shutdown failed", exc_info=True)
```

Note: `settings` is already assigned as a module-level variable (`settings = get_settings()`) in `main.py` — use that existing variable in the gate condition.
</action>
<acceptance_criteria>
- `grep -n "get_mcp_client_manager" backend/app/main.py` returns at least 3 matches (import + startup call + shutdown call)
- `grep -n "MCPClientManager startup" backend/app/main.py` returns a match in the lifespan function
- `grep -n "MCPClientManager shutdown" backend/app/main.py` returns a match after the yield
- `grep -n "settings.tool_registry_enabled and settings.mcp_servers" backend/app/main.py` returns at least 2 matches (startup gate + shutdown gate)
- `cd backend && source venv/bin/activate && python -c "from app.main import app; print('OK')"` prints `OK` (app import smoke test)
</acceptance_criteria>
</task>

<task id="4">
<name>Add MCP_SERVERS to backend/.env.example</name>
<read_first>
- backend/.env.example (current content — find MCP-related or find TOOL_REGISTRY_ENABLED entry)
</read_first>
<action>
In `backend/.env.example`, find the line with `TOOL_REGISTRY_ENABLED` (or near the bottom if not present). Add the `MCP_SERVERS` variable directly after it:

```
# Phase 15: MCP server configuration (empty = no MCP servers, zero startup cost)
# Format: name:command:args (first two colons are delimiters; args uses shell splitting)
# Multiple servers: comma-separated
# Example: github:npx:-y @modelcontextprotocol/server-github
MCP_SERVERS=
```

If `TOOL_REGISTRY_ENABLED` is not in `.env.example`, add both:
```
# Phase 13: Unified Tool Registry (set to true to enable tool_search and MCP integration)
TOOL_REGISTRY_ENABLED=false

# Phase 15: MCP server configuration (empty = no MCP servers, zero startup cost)
# Format: name:command:args (first two colons are delimiters; args uses shell splitting)
# Multiple servers: comma-separated
# Example: github:npx:-y @modelcontextprotocol/server-github
MCP_SERVERS=
```
</action>
<acceptance_criteria>
- `grep -n "MCP_SERVERS" backend/.env.example` returns a match
- `grep -n "MCP_SERVERS=" backend/.env.example` returns a match with an empty value (documentation default)
</acceptance_criteria>
</task>

</tasks>

<verification>
Plan 15-03 is complete when:
1. `backend/app/config.py` has `mcp_servers: str = ""` inside `Settings` class
2. `backend/requirements.txt` has `mcp` as a dependency
3. `backend/app/main.py` imports `get_mcp_client_manager` and has startup/shutdown calls in `lifespan`, both gated by `settings.tool_registry_enabled and settings.mcp_servers.strip()`
4. `backend/.env.example` has `MCP_SERVERS=` documented
5. App import smoke test passes: `python -c "from app.main import app; print('OK')"` → `OK`
6. MCP-05 (zero startup cost): with `TOOL_REGISTRY_ENABLED=false` or `MCP_SERVERS=''`, no `startup()` call is made
</verification>
