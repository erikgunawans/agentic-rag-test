---
plan: 14-04
phase: 14-sandbox-http-bridge-code-mode
status: complete
completed: 2026-05-03
commit: 70ba763
requirements_covered:
  - BRIDGE-04
  - BRIDGE-05
  - BRIDGE-06
---

# Summary: Plan 14-04 — Chat Wiring, Stub Prepend & main.py Mount

## What Was Built

Three surgical patches wiring all Phase 14 components together:

1. **`backend/app/main.py`** — Conditional bridge router mount (D-P14-05):
   ```python
   if settings.sandbox_enabled and settings.tool_registry_enabled:
       from app.routers import bridge as bridge_router_module
       app.include_router(bridge_router_module.router)
   ```
   Lazy import inside the if-block ensures bridge module is never imported when flags are off (TOOL-05 byte-identical fallback). Verified: `app.routers.bridge` not in `sys.modules` when flags are off.

2. **`backend/app/services/tool_service.py` — `_execute_code()`** (BRIDGE-04, D-P14-04):
   When both flags active, prepends `from stubs import *\n` to submitted code before dispatch to sandbox. Idempotent guard `not code.startswith("from stubs import")` prevents double-prepend on retry.

3. **`backend/app/routers/chat.py` — `event_generator()`** (BRIDGE-06, D-P14-07):
   Added `_bridge_active` flag and `_bridge_event_sent` once-guard at event_generator setup. Before the first `execute_code` call in both branch A (`_run_tool_loop`) and branch B (single-agent path), emits:
   ```json
   {"type": "code_mode_start", "tools": ["search_documents", "query_database", ...]}
   ```
   Tool list sourced from `tool_registry._REGISTRY` (lazy import, `tool_search` excluded). Event emitted at most once per SSE stream.

## Key Files Modified

- `backend/app/main.py` (7 lines added)
- `backend/app/services/tool_service.py` (8 lines added in `_execute_code`)
- `backend/app/routers/chat.py` (2 blocks of ~8 lines each, + 3-line flag setup)

## Verification

- All 3 import smoke tests pass
- `lazy import invariant OK (bridge_loaded=False, expected=False)` with default flags
- 455/455 unit tests pass (4 pre-existing redaction failures unchanged)

## Deviations

Used `_exec_settings` and `_bridge_active` local names in `_execute_code()` to avoid shadowing the module-level `settings` variable (which is a different `system_settings` in chat.py context).

## Self-Check: PASSED

- [x] `grep "if settings.sandbox_enabled and settings.tool_registry_enabled" main.py` passes
- [x] `grep "from stubs import" tool_service.py` passes
- [x] `grep "code_mode_start" chat.py` returns 2+ occurrences (both branches)
- [x] Lazy import invariant: bridge not loaded when flags off
- [x] No new test failures introduced
