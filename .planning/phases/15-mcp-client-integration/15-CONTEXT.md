# Phase 15: MCP Client Integration - Context

**Gathered:** 2026-05-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Implement `MCPClientManager` — a service that reads `MCP_SERVERS` from config at startup, spawns each configured server as a child process via the `mcp` Python SDK's stdio transport, calls `list_tools()` to discover available tools, converts MCP JSON Schema to OpenAI function-calling format eagerly, and registers each tool in the unified registry (`tool_registry.py`) as `source="mcp"`, `loading="deferred"`. Disconnected servers are marked unavailable and reconnected with exponential backoff. When `TOOL_REGISTRY_ENABLED=false` or `MCP_SERVERS=""`, zero processes are spawned and startup cost is zero.

**Deliverables:**
1. `backend/app/services/mcp_client_manager.py` — NEW module. Owns `MCPClientManager` class: parse `MCP_SERVERS`, spawn stdio clients, `list_tools()` → schema conversion → `tool_registry.register()`, `call_tool()` executor, reconnect-with-backoff loop, `mark_unavailable()` for disconnected servers.
2. `backend/app/config.py` patch — add `mcp_servers: str = ""` field (env var `MCP_SERVERS`).
3. `backend/app/main.py` patch — in the `lifespan` hook, after `get_redaction_service()` warmup, call `await mcp_client_manager.startup()` when `settings.tool_registry_enabled and settings.mcp_servers`. Wrap in `try/except` (matching existing lifespan pattern) so MCP failures don't crash app startup.
4. `backend/requirements.txt` patch — add `mcp` (Python MCP SDK).
5. Tests — `backend/tests/unit/test_mcp_client_manager.py` covering: env parse, schema conversion, registration, call_tool routing, disconnect/backoff logic.

**Out of scope (explicitly deferred):**
- Frontend UI for MCP server status (future milestone).
- Admin UI for managing MCP server config at runtime (future; env-var only for v1.2).
- MCP over SSE transport (stdio only for v1.2).
- Per-agent MCP allowlisting UI (MCP tools gated by existing `agent.tool_names` mechanism from D-P13-06).
- MCP tool Python stub generation for sandbox bridge (Phase 14 owns bridge stubs; Phase 15 only registers tools in registry so bridge can discover them via `tool_search`).

</domain>

<decisions>
## Implementation Decisions

### Startup Sequencing (MCP-02)

- **D-P15-01:** `MCPClientManager.startup()` is called in the FastAPI `lifespan` hook in `backend/app/main.py`, after `get_redaction_service()` warmup, wrapped in `try/except Exception`. If startup fails (e.g., `npx` not found, network issue), a `logger.warning(...)` is emitted and boot continues — MCP is non-critical infrastructure. Gate: `if settings.tool_registry_enabled and settings.mcp_servers.strip()`. When either flag is off or `MCP_SERVERS` is empty, the `if` short-circuits and no import of `mcp_client_manager` occurs in the hot path.

- **D-P15-02:** `MCPClientManager` is a module-level singleton (same pattern as `get_redaction_service()` lazy init). `mcp_client_manager.startup()` is idempotent — calling it twice is a no-op if already running. Teardown via `yield` in lifespan: `await mcp_client_manager.shutdown()` after `yield` to cleanly terminate child processes.

### MCP_SERVERS Parsing (MCP-01)

- **D-P15-03:** Format is `name:command:args` where the split is **first-colon and second-colon only** — everything after the second colon is the full args string (may contain additional colons). Examples:
  - `github:npx:-y @modelcontextprotocol/server-github` → name=`github`, command=`npx`, args=`-y @modelcontextprotocol/server-github`
  - `postgres:python:server.py --port 5432` → name=`postgres`, command=`python`, args=`server.py --port 5432`
  - Multiple servers: comma-separated entries (CSV split, then per-entry parse). Whitespace stripped around commas and entries.
  - Empty string or whitespace-only → zero servers, no processes.
  - Malformed entry (fewer than 2 colons) → logged at WARNING, entry skipped, remaining entries still processed.
  - Args string is split on whitespace for `subprocess`/stdio invocation (standard shell-like split via `shlex.split`).

### Schema Conversion (MCP-03)

- **D-P15-04:** Conversion is **eager at connect time** — runs inside `MCPClientManager.startup()` for every tool returned by `list_tools()`. Per-tool error isolation: a tool whose `inputSchema` is malformed or can't be converted is **skipped** (logged at WARNING), while the server and its other tools remain available. The server itself is NOT disconnected due to per-tool conversion failure.

- **D-P15-05:** Edge case handling for schema conversion:
  - Tool with no `inputSchema` → converted to `{"type": "object", "properties": {}}` (permissive passthrough matching OpenAI schema for parameterless tools).
  - Tool with `inputSchema` present → map `inputSchema` directly to OpenAI `parameters` field (MCP JSON Schema ≈ OpenAI parameters; both use JSON Schema draft 7-compatible format). No deep transformation needed for common cases.
  - Tool with no `description` → use empty string `""` for description (OpenAI function schema allows it; catalog truncation handles display).
  - Nested `$ref` schemas → pass through as-is (OpenAI accepts them; if they cause issues at call time, that's the MCP server's responsibility).
  - Final OpenAI schema shape: `{"type": "function", "function": {"name": f"{server_name}__{tool_name}", "description": tool.description or "", "parameters": tool.inputSchema or {"type":"object","properties":{}}}}`.
  - Tool name namespacing: `{server_name}__{tool_name}` (double underscore) to avoid collisions between servers with tools of the same name. Registry key = same namespaced name.

- **D-P15-06:** `call_tool()` executor strips the `{server_name}__` prefix before forwarding `tool_name` to `mcp_client.call_tool(server_name, original_tool_name, args)`. The namespace prefix is purely a registry artifact — the MCP server receives the original tool name.

### Registration (MCP-04)

- **D-P15-07:** Each MCP tool is registered via `tool_registry.register(name=namespaced_name, description=..., schema=openai_schema, source="mcp", loading="deferred", executor=call_tool_closure)`. The `executor` closure captures `server_name` and `original_tool_name` at connect time (not at call time) — no dynamic dispatch lookup needed.

- **D-P15-08:** Tools registered as `loading="deferred"` per MCP-04 / D-P13-03 design — they appear in the catalog table (with `source=mcp`) but are NOT injected into the LLM tools array unless the LLM calls `tool_search` to activate them first (D-P13-03 / TOOL-03). This keeps MCP tools discoverable without bloating the per-request tools array.

- **D-P15-09:** MCP tools appear in the catalog table (`build_catalog_block`) with source column showing `mcp`. Per D-P13-06, MCP tools are gated by `agent.tool_names` (unlike skills which bypass the filter). MCP tool names (namespaced) must be added to `agent.tool_names` for agents that should use them. For the default (no-agent) path, all registry tools pass the filter (D-P13-06: `agent_allowed_tools=None` → all pass).

### Reconnect / Resilience (MCP-05)

- **D-P15-10:** Exponential backoff parameters: delays of `[1, 2, 4, 8, 16, 32]` seconds (max 32s cap). After **5 consecutive failures**, log at `ERROR` level and stop retrying until next app restart. While a server is disconnecting/reconnecting, its tools are **marked unavailable** (not removed from `_REGISTRY`) via a `server_available: bool` flag on the manager's per-server state dict. `build_catalog_block` and `build_llm_tools` in `tool_registry.py` will skip tools whose server is unavailable via a filter hook on `ToolDefinition.metadata` or via the registry's existing disabled-flag support.

- **D-P15-11:** Unavailability signaling mechanism: `ToolDefinition` gets an optional `available: bool = True` field (Phase 15 adds it). `tool_registry.register()` sets `available=True` by default. `MCPClientManager.mark_unavailable(server_name)` iterates `_REGISTRY` and sets `available=False` on all tools with matching server prefix. `build_catalog_block` and `build_llm_tools` skip `available=False` tools. This keeps the registry append-only (no deletes) while supporting availability state — consistent with first-write-wins design.

- **D-P15-12:** Reconnect loop runs as a background `asyncio.Task` per server (spawned inside `lifespan`, cancelled in `shutdown()`). Each reconnect re-calls `list_tools()` and re-registers discovered tools (skip if already in `_REGISTRY` — first-write-wins). After successful reconnect, `mark_available(server_name)` re-enables the tools.

### Privacy / Egress Integration (MCP-06)

- **D-P15-13:** MCP `call_tool()` calls go to external MCP **servers** (not cloud LLMs). The egress filter at `backend/app/services/redaction/egress.py` guards against PII leaking to **cloud-LLM endpoints** — MCP servers are not cloud LLMs, so MCP tool arguments are NOT filtered through `egress.py` pre-flight.

- **D-P15-14:** MCP tool **results** (the returned content from the MCP server) flow back into `chat.py`'s `_run_tool_loop` as `tool_result` SSE events — same path as native tool results. The existing Phase 5 redaction path (`de-anonymize tool results`) applies to MCP tool results automatically, since it operates on all tool output in the chat loop. No special handling needed in `MCPClientManager`.

- **D-P15-15:** MCP tool **arguments** sent from the LLM contain only surrogates (not real PII) because the user message was anonymized upstream before reaching the LLM (Phase 5 BUFFER-01..03). So MCP servers receive already-anonymized arguments — same guarantee as native tools. No extra anonymization step in `MCPClientManager`.

### Claude's Discretion (planner-handled)

- **Module location** — `backend/app/services/mcp_client_manager.py` (new file). A `backend/app/mcp/` package is premature for v1.2 with a single class.
- **`mcp` SDK async API** — Use `mcp.ClientSession` with `stdio_client()` context manager from the `mcp` Python SDK. The SDK handles subprocess lifecycle; `MCPClientManager` owns the reconnect loop around it.
- **Per-server state struct** — `dict[str, ServerState]` where `ServerState` is a simple `@dataclass` with `name, command, args, session, available, fail_count, reconnect_task`. Dataclass (not Pydantic) — internal implementation detail, not user-facing.
- **Catalog availability display** — `(unavailable)` suffix appended to description in catalog rows for `available=False` tools, so operators can see which MCP tools are down without reading logs.
- **`available` field addition to `ToolDefinition`** — add as `available: bool = True` to `backend/app/models/tools.py` `ToolDefinition`. Backward-compatible (default True means existing native/skill tools are unaffected).
- **Test strategy** — Mock `mcp.ClientSession` and `stdio_client` at unit test layer. Integration test with a real stdio MCP server (e.g., a minimal echo server) gated behind a `MCP_TEST=1` env var to avoid requiring `npx` in CI.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Primary Specification

- `docs/superpowers/PRD-advanced-tool-calling.md` §Feature 5 (MCP Client Integration) — What it does, how it works, schema conversion notes, LLM visibility contract, resilience requirements.
- `docs/superpowers/PRD-advanced-tool-calling.md` §Cross-Cutting Concerns §Feature Flags — `TOOL_REGISTRY_ENABLED` gates the entire MCP subsystem; `MCP_SERVERS` format documented.
- `docs/superpowers/PRD-advanced-tool-calling.md` §Dependencies — `mcp` Python SDK is the only new dependency.

### Requirements & Roadmap

- `.planning/REQUIREMENTS.md` §MCP-01..06 — Six locked requirements, each with a clear success criterion. Especially MCP-05 (disconnect marking + backoff) and MCP-06 (indistinguishable from native tools to LLM).
- `.planning/REQUIREMENTS.md` §Out of Scope — "MCP tools without `inputSchema`" is a hard constraint: fail-fast (skip tool, log) not fail-at-call.
- `.planning/REQUIREMENTS.md` §New Configuration Surface — `MCP_SERVERS` env var format, `TOOL_REGISTRY_ENABLED` flag.
- `.planning/REQUIREMENTS.md` §New Dependencies — `mcp` Python SDK only.
- `.planning/ROADMAP.md` §Phase 15 — 5 success criteria (authoritative scope anchor), especially SC #3 (indistinguishable from native) and SC #5 (zero startup cost when disabled).

### Prior Phase Decisions (binding — carry forward)

- `.planning/phases/13-unified-tool-registry-tool-search-meta-tool/13-CONTEXT.md` §decisions — ALL D-P13-* decisions are binding for Phase 15:
  - D-P13-01: adapter wrap pattern (Phase 15 follows same registration API).
  - D-P13-02: skill first-class tool pattern (MCP follows parallel pattern with `source="mcp"`).
  - D-P13-03: unified `## Available Tools` table (MCP tools appear here with `source=mcp` column).
  - D-P13-04: `tool_search` meta-callout (MCP deferred tools discovered the same way).
  - D-P13-05: `tool_search` two-param schema (MCP tools match same way as native/skill).
  - D-P13-06: agent filter — MCP tools gated by `agent.tool_names` (not bypassed like skills).
- `.planning/phases/13-unified-tool-registry-tool-search-meta-tool/13-CONTEXT.md` §code_context — `tool_registry.register()` API, `ToolDefinition` shape, `_passes_agent_filter` predicate, `build_llm_tools` / `build_catalog_block` callers.

### Codebase Integration Points (must read before implementing)

- `backend/app/services/tool_registry.py` — Phase 13 registry. Phase 15 calls `register()` from `MCPClientManager.startup()`. Also needs `ToolDefinition.available` field added (D-P15-11).
- `backend/app/models/tools.py` — `ToolDefinition` model. Phase 15 adds `available: bool = True` field.
- `backend/app/main.py` — `lifespan` hook. Phase 15 adds `MCPClientManager.startup()` call after `get_redaction_service()`, and `MCPClientManager.shutdown()` after `yield`.
- `backend/app/config.py` — `Settings` class. Phase 15 adds `mcp_servers: str = ""` field.
- `backend/requirements.txt` — Phase 15 adds `mcp` package.
- `backend/app/services/redaction/egress.py` — Privacy invariant reference. MCP calls do NOT route through egress (they aren't cloud-LLM calls) — but MCP results go through the existing chat-loop de-anonymization path automatically.
- `backend/app/routers/chat.py` — `_run_tool_loop` (the tool dispatch loop). Phase 15 does NOT modify `chat.py` — MCP tools are dispatched through `tool_registry` executor callables exactly like native tools, so `chat.py` is already wired from Phase 13.

### Privacy Invariant

- `backend/app/services/redaction/egress.py` — egress filter guards cloud-LLM calls. MCP servers are NOT cloud LLMs; MCP call arguments bypass egress. MCP results de-anonymized by existing chat loop path (BUFFER-01..03 from Phase 5).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`tool_registry.register(name, description, schema, source, loading, executor)`** — Phase 13's public API. Phase 15 calls this for each MCP tool. The `executor` closure pattern (capturing context at registration time) is already established by Phase 13's native tool registration.
- **`lifespan` async context manager (`backend/app/main.py`)** — Existing pattern for startup hooks: `try: <warmup> except Exception: logger.warning(...)`. Phase 15 follows this pattern exactly for `mcp_client_manager.startup()`.
- **`get_settings()` + Pydantic Settings (`backend/app/config.py`)** — Adding `mcp_servers: str = ""` follows the same pattern as `sandbox_enabled`, `tool_registry_enabled`. Env var name = uppercase field name = `MCP_SERVERS`.
- **`ToolDefinition` Pydantic model (`backend/app/models/tools.py`)** — Phase 15 adds `available: bool = True`. Backward-compatible default. `build_catalog_block` and `build_llm_tools` in `tool_registry.py` need a 1-line filter: `if not tool.available: continue`.
- **`_passes_agent_filter(tool, agent_allowed_tools)`** — Phase 13's agent filter predicate in `tool_registry.py`. Phase 15 reuses it unchanged; MCP tools are gated by `agent.tool_names` (not bypassed).
- **`_is_disabled_by_toggle(tool, ...)`** — Phase 13 toggle-disable pattern. Phase 15 doesn't add a new toggle — availability is tracked at the server level via `available` field on `ToolDefinition`.

### Established Patterns

- **Feature-flagged startup hooks** — `pii_redaction_enabled`, `sandbox_enabled`, `tool_registry_enabled` all follow `if settings.flag: <init>` pattern. MCP follows `if settings.tool_registry_enabled and settings.mcp_servers.strip()`.
- **Background `asyncio.Task` for long-running services** — Phase 10 sandbox service uses background tasks for session management. Phase 15 reconnect loop follows the same pattern: `asyncio.create_task(self._reconnect_loop(server_name))` in `startup()`, cancelled in `shutdown()`.
- **Try/except with logger.warning for non-critical failures** — Used throughout `lifespan`, document processing, and retrieval. Phase 15's startup is non-critical (MCP tools are additive enhancements, not core CLM functionality).
- **First-write-wins on registry** — Phase 13's `register()` returns silently if name already exists. Phase 15's reconnect logic exploits this: after reconnect, `register()` is called again but skips tools already in `_REGISTRY` (first-write-wins means re-registration is a safe no-op). The `available` flag is updated separately via `mark_available()`.
- **`shlex.split(args_string)`** — Python standard library; safe arg splitting. Matches how the existing sandbox subprocess args are split in Phase 10.

### Integration Points

- **`backend/app/services/mcp_client_manager.py`** — NEW file. `MCPClientManager` class + module-level singleton instance. `startup()`, `shutdown()`, `call_tool(server_name, tool_name, args)`, `mark_unavailable(server_name)`, `mark_available(server_name)`. ~250-350 LOC expected.
- **`backend/app/models/tools.py`** — Add `available: bool = True` to `ToolDefinition`. 1-line change.
- **`backend/app/services/tool_registry.py`** — Add `available` filter to `build_catalog_block` and `build_llm_tools` (2 x 1 line). Add `(unavailable)` suffix to description for display in catalog when `available=False`.
- **`backend/app/main.py`** — Add import + startup/shutdown calls in `lifespan` (~6 lines).
- **`backend/app/config.py`** — Add `mcp_servers: str = ""` field (~2 lines with comment).
- **`backend/requirements.txt`** — Add `mcp` line under a `# MCP Client (Phase 15)` comment.
- **`backend/tests/unit/test_mcp_client_manager.py`** — NEW test file. Mock `mcp` SDK; test parse, convert, register, call, disconnect/reconnect logic.

</code_context>

<specifics>
## Specific Ideas

- **Tool name namespacing** — `{server_name}__{tool_name}` (double underscore separator). Clean, unambiguous, reversible. Executor strips prefix before forwarding to MCP SDK.
- **Catalog unavailability display** — `(unavailable)` appended to description in catalog rows when `available=False`. Operator-visible without log diving.
- **Backoff sequence** — `[1, 2, 4, 8, 16, 32]` seconds max 32s cap, 5 failures → stop. Conservative: matches production retry patterns for external services.
- **`shlex.split` for args parsing** — Handles quoted args with spaces correctly. No custom arg parser needed.
- **`mcp` SDK async pattern** — `async with stdio_client(StdioServerParameters(command=cmd, args=args_list)) as (read, write):` then `async with ClientSession(read, write) as session:` — standard SDK usage pattern.

</specifics>

<deferred>
## Deferred Ideas

- **Frontend MCP server status panel** — Show which MCP servers are connected / reconnecting in an admin UI. Deferred to future milestone; operators use logs for now.
- **Runtime MCP server config via `system_settings`** — Admin UI to add/remove MCP servers without Railway restart. Deferred: env-var-only for v1.2 (same posture as `TOOL_REGISTRY_ENABLED`).
- **MCP over SSE transport** — Stdio only for v1.2. SSE transport needed for remote MCP servers (e.g., cloud-hosted).
- **Per-agent MCP allowlisting UI** — Manual `agent.tool_names` update for now. Future: admin UI to add `server_name__*` patterns to agent tool lists.
- **MCP Python stub generation for sandbox bridge** — Phase 14 owns the bridge and its stubs. Phase 15 only registers MCP tools in the registry; bridge stub generation for MCP tools is a Phase 14 / future enhancement.
- **`$ref` schema resolution** — Nested `$ref` in MCP `inputSchema` passed through as-is. Deep resolution (for OpenAI compatibility) is a future enhancement if a real MCP server triggers it.

None of these appeared during discussion — all are architectural foresight captures for future milestone planning.

</deferred>

---

*Phase: 15-mcp-client-integration*
*Context gathered: 2026-05-02*
