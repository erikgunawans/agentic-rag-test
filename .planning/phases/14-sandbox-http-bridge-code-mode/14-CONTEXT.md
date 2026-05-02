# Phase 14: Sandbox HTTP Bridge (Code Mode) - Context

**Gathered:** 2026-05-02
**Status:** Ready for planning
**Mode:** --auto (all gray areas auto-decided)

<domain>
## Phase Boundary

Extend the existing per-thread Docker sandbox (Phase 10) so that LLM-generated Python code can call platform tools through a host-side HTTP bridge. The sandbox container gets a pre-baked `ToolClient` module (stdlib `urllib.request`, no new dependencies) that reads `BRIDGE_URL` and `BRIDGE_TOKEN` from its environment. At runtime, typed Python stubs for every active tool are generated and injected into the container. Bridge validation, tool dispatch, credential isolation, and security enforcement live entirely on the host; the container never sees credentials.

**Deliverables:**
1. `backend/app/routers/bridge.py` — NEW FastAPI router with three endpoints: `POST /bridge/call`, `GET /bridge/catalog`, `GET /bridge/health`. Mounted only when both `SANDBOX_ENABLED=true` AND `TOOL_REGISTRY_ENABLED=true`.
2. `backend/app/services/sandbox_bridge_service.py` — NEW service owning: session token store (thread_id → token UUID), token validation/cross-checking, stub generation (`_generate_stubs(active_tools) -> str`), and stub injection (`inject_stubs(session, active_tools)` via `execute_command`). Delegates tool dispatch to `tool_registry.execute()`.
3. `backend/app/services/sandbox_service.py` patch — Add `_check_dangerous_imports(code)` function before `container.run()`. Add `bridge_token: str | None` to `SandboxSession` dataclass. Inject `BRIDGE_URL` + `BRIDGE_TOKEN` env vars into container at session creation when bridge is active.
4. Sandbox Docker image extension — `backend/sandbox/Dockerfile` (NEW) extends or rebuilds the sandbox image to pre-install `/sandbox/tool_client.py` (the `ToolClient` class using `urllib.request`).
5. `backend/app/config.py` patch — Add `bridge_port: int = 8002` (env var `BRIDGE_PORT`). `BRIDGE_URL` and `BRIDGE_TOKEN` are injected per-session dynamically; they are NOT global config values.
6. `backend/app/routers/chat.py` patch — Emit `code_mode_start` SSE event listing available tools before the first `execute_code` call in a session where bridge is active (BRIDGE-06). Call `sandbox_bridge_service.inject_stubs()` when creating a new sandbox session with bridge active.

**Out of scope (explicitly deferred):**
- MCP tool registration in the bridge — Phase 15 (MCP-*).
- Per-user bridge enable/disable toggle — single on/off via dual flag contract.
- Admin UI for bridge configuration — future milestone.
- Bridge over TLS — localhost/Docker-internal only; TLS termination at Railway proxy handles external traffic.
- Stub caching across sessions — stubs are re-generated and re-injected per new container session (container reuse across calls uses existing stub from prior inject).

</domain>

<decisions>
## Implementation Decisions

### Bridge Port & Networking (BRIDGE-05)

- **D-P14-01: Fixed configurable port via `bridge_port: int = 8002` (env var `BRIDGE_PORT`).** The bridge FastAPI app runs on the host at `0.0.0.0:{bridge_port}`. The sandbox container's network is configured to reach the host via `host.docker.internal:{bridge_port}`. Bridge URL injected into container as `BRIDGE_URL=http://host.docker.internal:{bridge_port}`. The default port 8002 follows PRD §Infrastructure; Railway must expose this port internally.

  [auto] Bridge port selection — Q: "Dynamic ephemeral port or fixed configurable port?" → Selected: "Fixed configurable port via `BRIDGE_PORT` env var (default 8002)" (recommended per PRD §Infrastructure; dynamic ephemeral port adds lifecycle complexity incompatible with the existing single-container-per-thread model)

- **D-P14-02: Network isolation via llm-sandbox `SandboxSession` environment injection.** `SandboxSession` is created with `environment={"BRIDGE_URL": url, "BRIDGE_TOKEN": token}` (llm-sandbox v0.3.39 supports env injection at session creation via `SandboxSession(... , environment={...})`). The container's network access is not explicitly restricted at the Docker level by this phase — full network restriction (allow-only-bridge) is a hardening future step. The PRD credential isolation goal is achieved by:
  - Container has NO service-role keys, Supabase URLs, OpenAI keys, or MCP connection data — so even if it could reach the internet, it has nothing useful.
  - The bridge validates every call against token + user_id — the container cannot impersonate another user.
  - BRIDGE-05 network restriction: planner should investigate whether llm-sandbox exposes Docker run network config (`--add-host=host.docker.internal:host-gateway`). If available, use it. If not, document as a Railway-level infra hardening task.

### Session Token Lifecycle (BRIDGE-03)

- **D-P14-03: One UUID token per SandboxSession (thread-scoped), same lifetime as the 30-min idle TTL.** When `_create_container()` is called, `sandbox_bridge_service.create_bridge_token(thread_id, user_id)` generates a `uuid.uuid4()` string, stores it in a module-level `dict[str, BridgeTokenEntry]` (keyed by thread_id), and returns it. `BridgeTokenEntry` holds `{token: str, user_id: str, created_at: datetime}`. The token is stored in `SandboxSession.bridge_token` field (new field on the dataclass).

  Token validation on `POST /bridge/call`: look up by `session_token` value, verify `user_id` matches the calling user via `get_current_user` (the bridge router uses the same auth dependency), return 401 if missing or mismatched.

  Token expiry: when `_cleanup_loop()` evicts a session, `sandbox_bridge_service.revoke_token(thread_id)` is called to remove the entry. No Redis; no DB persistence — tokens live only in process memory (consistent with sandbox session lifecycle being in-memory per D-P10-09).

  [auto] Session token lifecycle — Q: "Token scoped to thread or to sandbox container session?" → Selected: "Token scoped to SandboxSession (one UUID per container, same lifetime as 30-min idle TTL)" (maps directly to existing per-thread session model in sandbox_service.py; avoids introducing a separate token store lifecycle)

### Stub Injection Strategy (BRIDGE-04)

- **D-P14-04: One-time stub file write per container session via `execute_command`.** When a new container is created and bridge is active, `sandbox_bridge_service.inject_stubs(session, active_tools)` is called immediately after `container.open()`. It:
  1. Calls `_generate_stubs(active_tools)` which produces a Python string defining one typed function per tool, each wrapping `ToolClient().call("tool_name", **kwargs)`.
  2. Writes the stub string to `/sandbox/stubs.py` in the container via `container.execute_command(...)`. The planner must verify the exact llm-sandbox `execute_command` API for writing files; fallback: use `container.run("python3 -c \"import sys; open('/sandbox/stubs.py','w').write(sys.stdin.read())\"")` pattern.
  3. Every subsequent user code submission has `from stubs import *\n` prepended (via `_execute_code` in `tool_service.py`).

  Stub function signature format: `def search_documents(query: str, filter_tags: list[str] | None = None, ...) -> dict: ...`. Parameter types and defaults extracted from the OpenAI function schema (`parameters.properties`, `required` list). Return type is always `dict`.

  [auto] Stub injection strategy — Q: "Write stub file to disk in container or prefix it inline at each run()?" → Selected: "Write to `/sandbox/stubs.py` via execute_command at session creation, then `from stubs import *` prepended to submitted code" (one-time inject per 30-min session avoids repeating multi-KB stub text on every code execution; aligns with existing `execute_command` usage in `sandbox_service.py`)

### Feature Flag Interaction (BRIDGE-05, TOOL-05, SANDBOX-05)

- **D-P14-05: Bridge is active ONLY when BOTH `SANDBOX_ENABLED=true` AND `TOOL_REGISTRY_ENABLED=true`.** Three tiers of behavior:
  - **Both true:** Bridge router mounted in `main.py`, `SandboxService._create_container()` injects env vars, stubs are injected at session creation, `code_mode_start` SSE event emitted.
  - **`SANDBOX_ENABLED=true`, `TOOL_REGISTRY_ENABLED=false`:** Existing v1.1 sandbox behavior unchanged. No bridge router, no token store, no stub injection. `execute_code` works identically to v1.1.
  - **`SANDBOX_ENABLED=false`:** No sandbox at all (existing v1.1 behavior). No bridge.

  Guard pattern in `sandbox_service._create_container()`:
  ```python
  settings = get_settings()
  bridge_active = settings.sandbox_enabled and settings.tool_registry_enabled
  env = {}
  if bridge_active:
      token = sandbox_bridge_service.create_bridge_token(thread_id, user_id)
      env = {"BRIDGE_URL": f"http://host.docker.internal:{settings.bridge_port}", "BRIDGE_TOKEN": token}
  ```

  [auto] Feature flag interaction — Q: "When `SANDBOX_ENABLED=true` but `TOOL_REGISTRY_ENABLED=false`, what happens?" → Selected: "Bridge only active when BOTH flags true; if either false, existing sandbox behavior byte-identical to v1.1" (cleanest no-regression path; consistent with D-P13-01 TOOL-05 invariant)

### Dangerous Import Scanning (BRIDGE-07)

- **D-P14-06: Add `_check_dangerous_imports(code: str) -> str | None` to `sandbox_service.py`.** Returns the matched dangerous pattern string if found, else `None`. Called at the start of `SandboxService.execute()` before dispatching to `container.run()`. If a dangerous pattern is found, returns `{"error": "security_violation", "pattern": pattern, "message": "Dangerous import blocked."}` without running the code.

  PRD §Security references "existing security policy blocks dangerous imports" — this pattern does NOT currently exist in the codebase (confirmed via grep across all backend files). Phase 14 adds it to satisfy BRIDGE-07. The regex must cover: `subprocess` module, raw socket I/O, process-spawning builtins (e.g. `__import__` with those names). Planner should define the exact pattern set; it must NOT flag `urllib.request` or `urllib.parse` (used by the bridge client stubs).

  [auto] Dangerous import block enforcement — Q: "Where does the import scanner live?" → Selected: "In `sandbox_service.py` as `_check_dangerous_imports()` called before container.run(), using regex consistent with tool_service.py's `_WRITE_KEYWORDS` pattern" (co-locates security check with execution; no new module needed)

### `code_mode_start` SSE Event (BRIDGE-06)

- **D-P14-07: Emit `code_mode_start` SSE event from chat.py when bridge is active and `execute_code` is about to be called.** Event shape:
  ```json
  {"type": "code_mode_start", "tools": ["search_documents", "query_database", "web_search"]}
  ```
  Emitted once per sandbox session creation (not per code execution call). Guard: only emit when `bridge_active` is true. This event is ephemeral (not persisted to `tool_calls` JSONB) — it signals session setup, not a tool result.

### ToolClient Module (BRIDGE-01)

- **D-P14-08: `ToolClient` uses stdlib `urllib.request` only; pre-baked into the sandbox Docker image at `/sandbox/tool_client.py`.** Class API:
  ```python
  class ToolClient:
      def call(self, tool_name: str, **kwargs) -> dict: ...
  ```
  Reads `BRIDGE_URL` and `BRIDGE_TOKEN` from `os.environ` at call time (not at import time, so the module can be imported before env vars are set during testing). Returns structured dict on success or `{"error": "bridge_error", "message": "..."}` on failure — exceptions are caught, never leaked. HTTP timeout: 30 seconds (configurable via `BRIDGE_TIMEOUT` env var, default 30).

  The sandbox Dockerfile lives at `backend/sandbox/Dockerfile` (new file). It `FROM`s the same base Python image used by the existing sandbox and adds the `ToolClient` module. The build artifact is tagged `lexcore-sandbox:latest` (matching `settings.sandbox_image` default).

### Bridge Router Auth Pattern (BRIDGE-03)

- **D-P14-09: Bridge endpoints use the same `get_current_user` FastAPI dependency as all other routers for the outer JWT auth check.** The inner auth check validates the `session_token` body field against `sandbox_bridge_service.validate_token(session_token, user_id)`. This two-layer check ensures:
  1. Caller has a valid Supabase JWT (outer — reuses existing infrastructure).
  2. Caller's `user_id` matches the token's registered `user_id` (inner — prevents token reuse across users).

  No new auth middleware needed. Bridge router is registered in `main.py` under the conditional import block (only when both flags are true).

### Claude's Discretion (planner-handled)

- **Bridge router file** — `backend/app/routers/bridge.py` (new file, ~80-120 LOC). Thin router; all logic in `sandbox_bridge_service.py`.
- **`sandbox_bridge_service.py` location** — `backend/app/services/sandbox_bridge_service.py` (new file, ~150-200 LOC). Owns token store, validation, stub generation, and stub injection.
- **Stub generation approach for complex schemas** — for tools with `anyOf`/`oneOf` in their schema properties, simplify to `Any` type in the stub rather than attempting to model union types. Keep stubs readable; runtime validation happens on the host side anyway.
- **`execute_command` stdin approach** — if llm-sandbox `execute_command` does not support stdin, fall back to a `container.run(...)` call with inline Python that writes the stub file as a one-time setup call before the first user code run.
- **Token store data structure** — `dict[str, BridgeTokenEntry]` at module level in `sandbox_bridge_service.py`. No async lock needed (token creation is already under `sandbox_service.py`'s `self._lock` via `_get_or_create_session`).
- **`host.docker.internal` on Linux/Railway** — standard on macOS/Windows Docker Desktop; on Linux requires `--add-host=host.docker.internal:host-gateway` in the Docker run command. Planner should investigate llm-sandbox API for passing extra Docker run args; if unavailable, document as a Railway config step.
- **Bridge route prefix** — `/bridge` (no versioning prefix, consistent with all other routers: `/chat`, `/documents`, `/skills`).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Primary Specification

- `docs/superpowers/PRD-advanced-tool-calling.md` §Feature 4 (lines 130-180) — Sandbox HTTP Bridge. Locks: ToolClient stdlib only, `/bridge/call` + `/bridge/catalog` + `/bridge/health` endpoints, typed stubs via `execute_command`, credential isolation, `code_mode_start` SSE event, network limited to bridge endpoint.
- `docs/superpowers/PRD-advanced-tool-calling.md` §New Configuration — `SANDBOX_ENABLED`, `BRIDGE_PORT`, `BRIDGE_URL`, `BRIDGE_TOKEN` definitions.
- `docs/superpowers/PRD-advanced-tool-calling.md` §New SSE Events — `code_mode_start` event definition.
- `docs/superpowers/PRD-advanced-tool-calling.md` §Security table (line ~157) — Session tokens, bridge auth, network isolation, code scanning, error handling requirements.

### Requirements & Roadmap

- `.planning/REQUIREMENTS.md` §BRIDGE-01..07 — All 7 locked requirements for this phase.
- `.planning/REQUIREMENTS.md` §Out of Scope — "Separate Code Mode tool" explicitly excluded; single sandbox model, every session gets bridge access by default.
- `.planning/REQUIREMENTS.md` §Infrastructure Requirements — Docker `host.docker.internal` and port 8002 availability.
- `.planning/ROADMAP.md` §Phase 14 — 5 success criteria (authoritative scope anchor).

### Prior Phase Decisions (binding)

- `.planning/phases/13-unified-tool-registry-tool-search-meta-tool/13-CONTEXT.md` — Full Phase 13 context. Binding for Phase 14:
  - D-P13-01: adapter wrap — `tool_registry` (and transitively `ToolService.execute_tool()`) is the dispatch surface for `/bridge/call`.
  - D-P13-03: unified catalog format — `/bridge/catalog` returns same format as system-prompt catalog.
  - D-P13-05: `tool_search` two-param schema — stub for `tool_search` must match `{keyword: str | None, regex: str | None}`.
  - D-P13-06: agent filter — bridge dispatches only tools the current agent is allowed to call.

- Phase 10 context (if present at `.planning/phases/10-code-execution-sandbox-backend/10-CONTEXT.md`) — Key binding decisions: D-P10-01 (Docker backend), D-P10-04 (one container per thread), D-P10-09 (in-memory sessions), D-P10-10 (30-min idle TTL + 60s cleanup loop), D-P10-12 (per-call timeout).

### Codebase Integration Points (must read)

- `backend/app/services/sandbox_service.py` — Full service. Phase 14 adds: `_check_dangerous_imports()`, `bridge_token` field on `SandboxSession`, env injection in `_create_container()`, `inject_stubs()` call after `container.open()`. Token revocation in `_cleanup_loop()`.
- `backend/app/services/tool_registry.py` — Phase 13 registry. Bridge router calls `tool_registry` execute for dispatch.
- `backend/app/services/tool_service.py` — `_execute_code()`: patch to prepend `from stubs import *\n` to code before `container.run()` when bridge is active.
- `backend/app/routers/chat.py` — `code_mode_start` SSE event emission point; import bridge router conditionally.
- `backend/app/config.py` — Add `bridge_port: int = 8002`.
- `backend/app/main.py` — Conditional router mounting when both flags are true.
- `backend/app/services/redaction/egress.py` — Privacy invariant: bridge tool dispatch delegates to executor callables from Phase 13 which already respect the egress filter via `ToolService.execute_tool()`.

### Architecture & Conventions

- `.planning/codebase/ARCHITECTURE.md` §Flow 1 — SSE event sequence; `code_mode_start` event inserts before the `execute_code` tool_start event.
- `.planning/codebase/CONVENTIONS.md` — Pydantic models, async service patterns, router structure.
- `CLAUDE.md` — "No LangChain, no LangGraph. Raw SDK calls only." `SANDBOX_ENABLED` defaults `false`. `TOOL_REGISTRY_ENABLED` defaults `false`. Both must be true for bridge.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `backend/app/services/sandbox_service.py` — `SandboxService` singleton with `execute()` async method, `_get_or_create_session()` lifecycle, `_cleanup_loop()` TTL eviction, and `session.container.execute_command()` API for container interaction. Phase 14 adds bridge token + dangerous import scan here.
- `backend/app/services/tool_registry.py` — Phase 13 registry. `build_catalog_block()` reused by `sandbox_bridge_service.get_catalog_for_session()` for `/bridge/catalog` response.
- `backend/app/services/tool_service.py` — `_WRITE_KEYWORDS` regex pattern (model for `_check_dangerous_imports` pattern design). `_execute_code()` is the injection point for the stub prepend.
- `backend/app/dependencies.py` — `get_current_user` dependency (reused by bridge router for outer JWT validation).
- `backend/app/services/audit_service.py` — `log_action()` for bridge call audit trail (consistent with Phase 10 execute_code audit).

### Established Patterns

- **Dual-flag gate:** `settings.sandbox_enabled and settings.tool_registry_enabled` — use this exact pattern for all bridge conditionals.
- **In-memory session store:** `dict[str, T]` at module level (from `sandbox_service.py`). Token store follows same pattern.
- **Lazy import (TOOL-05 invariant):** bridge router imported only when both flags are true (mirrors Phase 13 lazy import of `tool_registry` in `chat.py`).
- **Router registration:** `app.include_router(router, prefix="/bridge", tags=["Bridge"])` in `main.py`.
- **SSE event shape:** `json.dumps({"type": "event_name", **payload})` — consistent with all existing SSE events.
- **`execute_command` for container interaction:** `session.container.execute_command(cmd)` used in Phase 10 for `ls /sandbox/output/`. Same API available for stub injection.

### Integration Points

- `sandbox_service.py:_create_container()` → add env var injection + token creation when bridge active.
- `sandbox_service.py:_cleanup_loop()` → add token revocation when session evicted.
- `tool_service.py:_execute_code()` → prepend `from stubs import *\n` to `code` before dispatch when bridge active.
- `chat.py` → emit `code_mode_start` SSE event; conditionally import bridge router.
- `main.py` → conditionally mount bridge router.
- `config.py` → add `bridge_port: int = 8002`.

</code_context>

<specifics>
## Specific Ideas

- The `ToolClient` pre-baked into the Docker image at `/sandbox/tool_client.py` uses `urllib.request` (zero extra dependencies). This is explicitly required by BRIDGE-01.
- The bridge Dockerfile lives at `backend/sandbox/Dockerfile` (new directory). The existing backend `Dockerfile` (at `backend/Dockerfile`) is NOT changed — it's the Railway production image. The sandbox image is built separately and tagged `lexcore-sandbox:latest` matching `settings.sandbox_image`.
- Bridge errors from the container side (network failure, token expired, tool not found) are returned as structured dicts by the `ToolClient.call()` method — exceptions are caught inside the client, never leaked to user code. This is a hard requirement (BRIDGE-07).
- The `/bridge/catalog` endpoint returns the same tool list format as the system-prompt catalog so LLM-generated code can introspect available tools programmatically.

</specifics>

<deferred>
## Deferred Ideas

- **Docker `--network` full isolation** — enforcing allow-only-bridge at the Docker runtime level. Depends on llm-sandbox API exposure of Docker run args. Deferred as a Railway infra hardening step after Phase 14 ships.
- **Bridge TLS** — not needed for localhost/Docker-internal transport.
- **Token store DB persistence** — bridge tokens are in-memory only, consistent with D-P10-09. Persistence deferred.
- **`BRIDGE_TIMEOUT` as a `system_settings` admin knob** — env var only for v1.2. Future admin UI enhancement.
- **MCP tools via bridge** — MCP tool executors will be callable via the bridge in Phase 15 (registered as `source="mcp"` in unified registry; bridge dispatch is source-agnostic).
- **Per-user bridge access control** — all users with sandbox access get bridge access. Fine-grained control deferred to future RBAC milestone.

</deferred>

---

*Phase: 14-sandbox-http-bridge-code-mode*
*Context gathered: 2026-05-02*
