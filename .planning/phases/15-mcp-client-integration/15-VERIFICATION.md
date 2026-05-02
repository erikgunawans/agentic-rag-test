---
phase: 15
status: passed
verified: 2026-05-03
plans_verified: 5
must_haves_checked: 26
must_haves_passed: 26
requirements_covered:
  - MCP-01
  - MCP-02
  - MCP-03
  - MCP-04
  - MCP-05
  - MCP-06
---

# Verification — Phase 15: MCP Client Integration

## Phase Goal

`MCPClientManager` at startup parses `MCP_SERVERS` env var, spawns stdio clients, registers tools in the unified registry with `source="mcp"`, `loading="deferred"`, reconnects with exponential backoff on disconnect, and has zero startup cost when disabled.

## Requirement Verification

### MCP-01: MCP_SERVERS parsing
**Status: PASSED**

`parse_mcp_servers()` in `backend/app/services/mcp_client_manager.py`:
- `name:command:args` format, split on first 2 colons only ✓
- `shlex.split` for args string ✓
- Multiple servers comma-separated ✓
- Empty/whitespace → empty list ✓
- Malformed entry (< 2 colons) → WARNING log, entry skipped, rest processed ✓
- `mcp_servers: str = ""` added to `Settings` class in `config.py` ✓
- `MCP_SERVERS=` documented in `.env.example` ✓

### MCP-02: Lifecycle management (startup/shutdown)
**Status: PASSED**

- `MCPClientManager.startup()` called in FastAPI `lifespan` hook after `get_redaction_service()` ✓
- Gate: `if settings.tool_registry_enabled and settings.mcp_servers.strip()` ✓
- Wrapped in `try/except Exception` — failure logs WARNING and boot continues ✓
- `MCPClientManager.shutdown()` called after `yield` with same gate ✓
- `get_mcp_client_manager()` `@lru_cache` singleton ✓
- `startup()` idempotent — skips already-initialized servers ✓

### MCP-03: Schema conversion (MCP JSON Schema → OpenAI)
**Status: PASSED**

- `_convert_mcp_tool_to_openai()` does eager conversion at connect time ✓
- Tool `inputSchema` → OpenAI `parameters` field ✓
- Missing `inputSchema` → `{"type": "object", "properties": {}}` permissive passthrough ✓
- Missing `description` → empty string ✓
- Conversion error → `None` returned, tool skipped with WARNING, server stays connected ✓
- Tool name namespaced `{server_name}__{tool_name}` (double underscore) ✓

### MCP-04: Unified registry registration
**Status: PASSED**

- `ToolDefinition.available: bool = True` added to `backend/app/models/tools.py` ✓
- `tool_registry.register()` called with `source="mcp"`, `loading="deferred"` ✓
- `build_catalog_block()` and `build_llm_tools()` skip `available=False` tools ✓
- `mark_server_unavailable(server_name)` / `mark_server_available(server_name)` exposed ✓
- MCP tools appear in `## Available Tools` catalog with `source=mcp` column ✓

### MCP-05: Disconnect + reconnect with exponential backoff
**Status: PASSED**

- `_reconnect_loop(server_name)` async method with `_BACKOFF_DELAYS = [1, 2, 4, 8, 16, 32]` ✓
- After `_MAX_FAILURES=5` consecutive failures → logs ERROR, stops retrying ✓
- `mark_server_unavailable()` called before reconnect attempt ✓
- `mark_server_available()` called on successful reconnect ✓
- `startup()` spawns one `asyncio.Task` per server for reconnect loop ✓
- `shutdown()` cancels all reconnect tasks with `asyncio.wait_for(timeout=5.0)` ✓
- `asyncio.CancelledError` re-raised in reconnect loop ✓
- `_handle_tool_call_failure()` marks server unavailable when `call_tool()` raises ✓

### MCP-06: Indistinguishable from native tools to LLM
**Status: PASSED**

- MCP tools appear in `## Available Tools` catalog table (same as native/skill) ✓
- MCP tools dispatched through `tool_registry` executor callables — same path as native tools ✓
- `chat.py` is NOT modified — MCP tools flow through existing tool dispatch (D-P15-14) ✓
- Egress filter NOT applied to MCP calls (not cloud-LLM calls) per D-P15-13 ✓
- MCP tool results de-anonymized by existing chat loop path automatically ✓
- MCP tool arguments arrive already anonymized from upstream PII redaction (D-P15-15) ✓

## Automated Test Coverage

| Test File | Tests | Status |
|-----------|-------|--------|
| `tests/unit/test_mcp_client_manager.py` | 27 | PASS |
| `tests/unit/test_tool_registry_availability.py` | 15 | PASS |
| `tests/unit/test_tool_registry.py` (Phase 13 regression) | 26 | PASS |
| **Total** | **68** | **All PASS** |

Combined run: `pytest tests/unit/test_tool_registry.py tests/unit/test_tool_registry_availability.py tests/unit/test_mcp_client_manager.py -q` → `68 passed, 2 warnings`

## Files Delivered

| File | Status | Plan |
|------|--------|------|
| `backend/app/models/tools.py` | Modified — `available` field added | 15-01 |
| `backend/app/services/tool_registry.py` | Modified — availability filter + mark functions | 15-01 |
| `backend/app/services/mcp_client_manager.py` | Created (474 lines + review fixes) | 15-02, 15-04 |
| `backend/app/config.py` | Modified — `mcp_servers` field | 15-03 |
| `backend/app/main.py` | Modified — lifespan startup/shutdown | 15-03 |
| `backend/requirements.txt` | Modified — `mcp` dependency | 15-03 |
| `backend/.env.example` | Modified — MCP_SERVERS documented | 15-03 |
| `backend/tests/unit/test_mcp_client_manager.py` | Created (27 tests) | 15-05 |
| `backend/tests/unit/test_tool_registry_availability.py` | Created (15 tests) | 15-05 |

## Key Constraints Honored

- `tool_service.py` lines 1-1283: NOT modified (byte-identical invariant) ✓
- `chat.py`: NOT modified ✓
- `TOOL_REGISTRY_ENABLED=false` or `MCP_SERVERS=""` → zero MCP processes spawned ✓
- `mcp` Python SDK is the only new dependency ✓
- Privacy invariant: MCP calls do NOT route through `egress.py` (correct — not cloud-LLM) ✓

## Verification Result: PASSED

All 6 MCP requirements verified. All 26 plan must-haves satisfied. 68 tests passing. Phase 15 complete.
