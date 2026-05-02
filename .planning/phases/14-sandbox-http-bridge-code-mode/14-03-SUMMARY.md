---
plan: 14-03
phase: 14-sandbox-http-bridge-code-mode
status: complete
completed: 2026-05-03
commit: a563bdf
requirements_covered:
  - BRIDGE-02
  - BRIDGE-03
---

# Summary: Plan 14-03 — Bridge Router

## What Was Built

Created `backend/app/routers/bridge.py` with three endpoints:

1. **`GET /bridge/health`** — no auth required; returns `{"status": "ok"}`. Used by ToolClient to verify connectivity before tool calls.

2. **`GET /bridge/catalog`** — requires JWT (outer) + session_token (inner). Lists available tools from `tool_registry._REGISTRY`, sorted by name, excluding `tool_search` meta-tool. Returns `BridgeCatalogResponse(tools=[...])`.

3. **`POST /bridge/call`** — requires JWT + session_token. Validates both layers, looks up `tool_name` in registry (404 if missing), dispatches to `tool_def.executor(arguments, ctx)`, normalizes result to dict. Executor exceptions caught and returned as `{"error": "tool_execution_error", "message": ...}` (BRIDGE-07).

**Two-layer auth** (D-P14-09): outer JWT via `get_current_user`, inner `validate_token(session_token, user_id)` via `sandbox_bridge_service`. Mismatch returns HTTP 401.

**TOOL-05 compliance**: `tool_registry` imported lazily inside handlers (not at module level). The router itself can be imported without triggering registry load.

## Key Files Created

- `backend/app/routers/bridge.py` (new — ~160 LOC)
- `backend/tests/unit/test_bridge_router.py` (new — 8 tests)

## Test Results

```
8 passed in 0.57s
```

## Deviations

Router not yet mounted in `main.py` — that wiring is Plan 14-04 as specified.

## Self-Check: PASSED

- [x] `router = APIRouter(prefix='/bridge', tags=['Bridge'])` confirmed
- [x] All 3 endpoints exist
- [x] Two-layer auth implemented
- [x] HTTP 401 on token mismatch, 404 on missing tool
- [x] BRIDGE-07: executor exceptions return structured dicts
- [x] Import smoke test passes
- [x] 8/8 unit tests pass
