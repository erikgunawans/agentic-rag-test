# Phase 15: MCP Client Integration - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-02
**Phase:** 15-mcp-client-integration
**Mode:** --auto (fully autonomous, no AskUserQuestion)
**Areas discussed:** Startup Sequencing, MCP_SERVERS Parsing, Schema Conversion, Reconnect / Resilience, Privacy / Egress Integration

---

## Startup Sequencing

| Option | Description | Selected |
|--------|-------------|----------|
| Lifespan hook (recommended) | After `get_redaction_service()` warmup in `lifespan`, wrapped in try/except | ✓ |
| First-chat lazy init | Deferred to first chat request — avoids startup latency | |
| Separate background thread | Spawn in thread outside asyncio event loop | |

**Auto-selected:** Lifespan hook — matches existing patterns (`get_redaction_service`, document recovery). Non-critical wrap (try/except) means MCP failures never crash app startup.
**Notes:** Shutdown via `yield` cleanup in lifespan (`await mcp_client_manager.shutdown()`). Pattern identical to Phase 10 sandbox service teardown.

---

## MCP_SERVERS Parsing

| Option | Description | Selected |
|--------|-------------|----------|
| First-two-colons split (recommended) | `name:command:args` where args is everything after second colon | ✓ |
| JSON config string | `MCP_SERVERS={"github":{"command":"npx","args":[...]}}` | |
| Separate env vars per server | `MCP_SERVER_1_NAME`, `MCP_SERVER_1_CMD`, etc. | |

**Auto-selected:** First-two-colons split — matches REQUIREMENTS.md format exactly (`github:npx:-y @modelcontextprotocol/server-github`). Simplest to configure. Args split with `shlex.split` for quoted-arg support. Multiple servers comma-separated.
**Notes:** Malformed entries (fewer than 2 colons) → WARNING log + skip. Empty `MCP_SERVERS` → no processes spawned (zero startup cost, MCP-05 guard).

---

## Schema Conversion

| Option | Description | Selected |
|--------|-------------|----------|
| Eager, per-tool isolation (recommended) | Convert all tools at connect time; skip malformed tools (not whole server) | ✓ |
| Eager, per-server isolation | Skip entire server if any tool conversion fails | |
| Lazy conversion | Convert at first call time | |

**Auto-selected:** Eager per-tool isolation — matches MCP-03 requirement ("fail fast on incompatible tools") and OUT OF SCOPE note ("MCP tools without `inputSchema` skip with logged error"). Server stays connected with partial tool set.
**Notes:** Tool name namespacing: `{server_name}__{tool_name}` (double underscore). Executor strips prefix before SDK call. Empty `inputSchema` → `{"type":"object","properties":{}}` permissive passthrough. Missing `description` → empty string.

---

## Reconnect / Resilience

| Option | Description | Selected |
|--------|-------------|----------|
| Exponential backoff with stop (recommended) | 1→2→4→8→16→32s; stop after 5 failures | ✓ |
| Fixed interval retry | Retry every 30s forever | |
| Immediate reconnect with jitter | Jitter ± 50%, infinite retries | |

**Auto-selected:** Exponential backoff with stop — conservative, operator-visible (ERROR log after 5 failures), matches production patterns for external services. Tools marked unavailable (not removed) to preserve catalog stability.
**Notes:** `available: bool = True` added to `ToolDefinition`. `mark_unavailable()` / `mark_available()` iterate registry by server prefix. Catalog shows `(unavailable)` suffix on disconnected server's tools. Reconnect re-registers tools (first-write-wins means safe no-op for duplicates; `available` flag updated separately).

---

## Privacy / Egress Integration

| Option | Description | Selected |
|--------|-------------|----------|
| No egress filter on MCP args (recommended) | MCP servers are not cloud LLMs; existing chat-loop de-anon covers results | ✓ |
| Apply egress filter to MCP args | Pre-flight PII check before each `call_tool()` | |
| Full anonymize/de-anonymize pipeline in MCPClientManager | Mirror redaction_service in MCP layer | |

**Auto-selected:** No egress filter — MCP servers receive already-anonymized arguments (LLM only sees surrogates from Phase 5 upstream anonymization). MCP tool results flow through existing chat-loop de-anonymization path (BUFFER-01..03) automatically. Zero changes to redaction or egress modules.
**Notes:** Privacy invariant preserved: real PII never reaches cloud-LLM payloads (egress.py gates cloud-LLM calls). MCP servers are external services, not cloud LLMs — different trust boundary; same pre-anonymized data guarantee applies.

---

## Claude's Discretion

- **Module location** — `backend/app/services/mcp_client_manager.py` (new single file, ~250-350 LOC). Package premature for v1.2 single-class scope.
- **`ServerState` struct** — `@dataclass` (not Pydantic) — internal implementation detail.
- **Reconnect background task** — `asyncio.create_task(self._reconnect_loop(server_name))` per server.
- **`mcp` SDK async pattern** — `async with stdio_client(StdioServerParameters(...)) as (read, write):` + `async with ClientSession(read, write) as session:`.
- **Test mocking** — Mock `mcp.ClientSession` and `stdio_client` at unit layer. Real-server integration test gated behind `MCP_TEST=1` env var.

## Deferred Ideas

- Frontend MCP server status panel — future milestone
- Runtime MCP server config via `system_settings` DB toggle — future milestone
- MCP over SSE transport — future (remote/cloud-hosted servers)
- Per-agent MCP allowlisting UI — future
- MCP Python stub generation for sandbox bridge — Phase 14 scope / future
- `$ref` schema deep resolution — future if triggered by real MCP server
