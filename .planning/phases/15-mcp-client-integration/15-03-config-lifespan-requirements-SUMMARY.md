---
plan: 15-03
phase: 15-mcp-client-integration
status: complete
wave: 1
completed: 2026-05-03
commit: af49f7b
---

## Summary

Wired MCP subsystem into the app's configuration and startup lifecycle. Added `mcp_servers: str = ""` to `Settings` class in `config.py`. Added `mcp` package to `requirements.txt` under `# MCP Client (Phase 15)` comment. Added `get_mcp_client_manager().startup()` and `.shutdown()` calls to the FastAPI `lifespan` hook in `main.py`, both gated by `settings.tool_registry_enabled and settings.mcp_servers.strip()` and wrapped in `try/except`. Added `TOOL_REGISTRY_ENABLED` and `MCP_SERVERS=` documentation to `.env.example`.

## Key Files

- `backend/app/config.py` — `mcp_servers: str = ""` field added
- `backend/requirements.txt` — `mcp` package added
- `backend/app/main.py` — import + lifespan startup/shutdown calls
- `backend/.env.example` — MCP_SERVERS documented

## Self-Check: PASSED

- `mcp_servers` field in Settings, default empty string ✓
- `requirements.txt` has `mcp` on its own line ✓
- `main.py` has 3 `get_mcp_client_manager` references (import + startup + shutdown) ✓
- Gate `settings.tool_registry_enabled and settings.mcp_servers.strip()` in both places ✓
- App import smoke test: `OK` ✓
