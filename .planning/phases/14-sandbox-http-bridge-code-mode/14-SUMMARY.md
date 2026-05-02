---
phase: 14-sandbox-http-bridge-code-mode
status: completed
completed: 2026-05-03
plans: 5
requirements_covered:
  - BRIDGE-01
  - BRIDGE-02
  - BRIDGE-03
  - BRIDGE-04
  - BRIDGE-05
  - BRIDGE-06
  - BRIDGE-07
---

# Phase 14 Summary — Sandbox HTTP Bridge (Code Mode)

## Phase Goal

LLM-generated Python in the sandbox can call platform tools through a host-side HTTP bridge with typed stubs, collapsing N tool round-trips into one sandbox execution while keeping credentials on the host.

## What Was Shipped

### New Files

| File | Purpose |
|------|---------|
| `backend/sandbox/tool_client.py` | Pre-baked `ToolClient` class using stdlib `urllib.request` only; reads `BRIDGE_URL`/`BRIDGE_TOKEN` from env |
| `backend/app/services/sandbox_bridge_service.py` | Host-side bridge: stub generation, token management, dangerous-import scan |
| `backend/app/routers/bridge.py` | `/bridge/call`, `/bridge/catalog`, `/bridge/health` endpoints (flag-gated) |
| `backend/tests/unit/test_sandbox_bridge_service.py` | Unit tests for bridge service |
| `backend/tests/unit/test_bridge_byte_identical.py` | Byte-identical fallback tests (18 tests, TOOL-05 invariant) |
| `backend/tests/integration/test_bridge_integration.py` | E2E bridge test (Docker-gated) |

### Patched Files

| File | Change |
|------|--------|
| `backend/app/config.py` | Added `bridge_port: int = 8002`, `BRIDGE_PORT` env var |
| `backend/sandbox/Dockerfile` | Copies `tool_client.py` into sandbox image |
| `backend/app/services/sandbox_service.py` | Injects `BRIDGE_URL`/`BRIDGE_TOKEN` env into container; prepends `from stubs import *` when both flags on |
| `backend/app/routers/chat.py` | Emits `code_mode_start` SSE event listing available tools; mounts bridge router when flags on |
| `backend/app/main.py` | Mounts `/bridge` router conditionally |

### Key Invariants Preserved

- **Adapter-wrap invariant**: `tool_service.py` lines 1-1283 are byte-identical to pre-Phase-14
- **TOOL-05 fallback**: When `SANDBOX_ENABLED=False` OR `TOOL_REGISTRY_ENABLED=False`, no `/bridge/*` routes exist, no stubs prepended, zero bridge module import at startup
- **Credential isolation**: Service-role keys, API keys, MCP connections never enter the sandbox container — bridge dispatches on the host side

## Requirements Coverage

| Req | Status | Evidence |
|-----|--------|---------|
| BRIDGE-01 | ✅ | `sandbox/tool_client.py` pre-baked with stdlib-only `ToolClient` |
| BRIDGE-02 | ✅ | `routers/bridge.py` exposes `/bridge/call`, `/bridge/catalog`, `/bridge/health` |
| BRIDGE-03 | ✅ | Token validation + user ownership check on every `/bridge/call` |
| BRIDGE-04 | ✅ | `generate_stubs()` in `sandbox_bridge_service.py` → injected via `_execute_code()` |
| BRIDGE-05 | ✅ | Container env only sets `BRIDGE_URL`/`BRIDGE_TOKEN`; no Supabase/OpenAI keys |
| BRIDGE-06 | ✅ | `code_mode_start` SSE event emitted in `chat.py` |
| BRIDGE-07 | ✅ | Dangerous-import block list enforced; bridge errors return structured dicts |

## Decisions Made

- **D-P14-01**: `ToolClient` uses `urllib.request` (stdlib only) — no extra pip deps in sandbox image
- **D-P14-02**: Stubs are plain Python functions with type annotations, not `dataclasses` — simpler for LLM to read
- **D-P14-03**: Bridge token = short-lived JWT signed by the host per execution, not the user's auth token — avoids token leakage
- **D-P14-04**: `from stubs import *` prepended to submitted code (not injected via `exec` globals) — matches LLM-expected import pattern

## Test Results

- 18/18 byte-identical unit tests ✅
- All prior pytest suites unaffected (no regressions) ✅
