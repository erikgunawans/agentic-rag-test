---
plan: 14-01
phase: 14-sandbox-http-bridge-code-mode
status: complete
completed: 2026-05-03
commit: 9ea3af8
requirements_covered:
  - BRIDGE-01
  - BRIDGE-03
---

# Summary: Plan 14-01 — Bridge Config, ToolClient Docker Image & sandbox_bridge_service Foundation

## What Was Built

Laid the foundation for Phase 14's sandbox HTTP bridge:

1. **`backend/app/config.py`** — Added `bridge_port: int = 8002` field (env var `BRIDGE_PORT`, D-P14-01). Reads from environment at startup; default matches PRD §Infrastructure.

2. **`backend/sandbox/tool_client.py`** — Created `ToolClient` class using stdlib `urllib.request` only (BRIDGE-01, D-P14-08). Reads `BRIDGE_URL` and `BRIDGE_TOKEN` from `os.environ` at call time. `call()` returns a dict on success or `{"error": "bridge_error", "message": "..."}` on any failure — never raises.

3. **`backend/sandbox/Dockerfile`** — New sandbox Docker image that extends `python:3.12-slim`, creates `/sandbox/output/`, pre-bakes `ToolClient` at `/sandbox/tool_client.py`, and sets `chmod 777 /sandbox` for runtime stub injection.

4. **`backend/app/services/sandbox_bridge_service.py`** — Full bridge service (D-P14-03, D-P14-04):
   - `BridgeTokenEntry` dataclass (token, user_id, thread_id, created_at)
   - `_TOKEN_STORE: dict[str, BridgeTokenEntry]` module-level store
   - `create_bridge_token(thread_id, user_id) -> str` — generates UUID4, stores entry
   - `validate_token(session_token, user_id) -> bool` — checks token value AND user_id match
   - `revoke_token(thread_id) -> None` — no-op if missing
   - `_generate_stubs(active_tools) -> str` — produces typed Python stub code
   - `inject_stubs(session, active_tools) -> None` — writes `/sandbox/stubs.py` via `execute_command` with fallback to `run()`

5. **`backend/tests/unit/test_sandbox_bridge_service.py`** — 18 unit tests covering full token lifecycle, cross-user rejection, unknown token rejection, stub generation for typed params, anyOf→Any simplification, and empty tool list.

## Key Files Created

- `backend/app/config.py` (modified)
- `backend/sandbox/tool_client.py` (new)
- `backend/sandbox/Dockerfile` (new)
- `backend/app/services/sandbox_bridge_service.py` (new)
- `backend/tests/unit/test_sandbox_bridge_service.py` (new)

## Test Results

```
18 passed in 0.82s
```

All 18 tests pass. Import smoke test: `python -c "from app.main import app; print('OK')"` exits 0.

## Deviations

None. Implementation follows plan spec exactly. `_generate_stubs` uses `list` type hint (not `list[ToolDefinition]`) to avoid circular import at runtime while TYPE_CHECKING guards the import for type checkers.

## Self-Check: PASSED

- [x] `settings.bridge_port == 8002` verified
- [x] `ToolClient.call()` returns error dict when `BRIDGE_URL` unset (verified)
- [x] Token create/validate/revoke lifecycle all pass
- [x] `_generate_stubs` produces parseable Python with correct signatures
- [x] `inject_stubs` implemented with execute_command primary + run() fallback
- [x] All 5 artifacts exist on disk and contain expected strings
- [x] Import smoke test passes
- [x] 18/18 unit tests pass
