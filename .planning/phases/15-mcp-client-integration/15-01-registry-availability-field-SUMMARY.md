---
plan: 15-01
phase: 15-mcp-client-integration
status: complete
wave: 1
completed: 2026-05-03
commit: 6419bf7
---

## Summary

Added `available: bool = True` field to `ToolDefinition` in `backend/app/models/tools.py` (backward-compatible default; existing native/skill tools are always available). Updated `build_catalog_block()` and `build_llm_tools()` in `tool_registry.py` to skip tools where `available=False`. Exposed `mark_server_unavailable(server_name)` and `mark_server_available(server_name)` public functions that iterate `_REGISTRY` and flip `available` on all tools whose name starts with `"{server_name}__"`.

## Key Files

- `backend/app/models/tools.py` — `ToolDefinition.available: bool = True` added
- `backend/app/services/tool_registry.py` — availability filter in `build_llm_tools`, `build_catalog_block`; `mark_server_unavailable`, `mark_server_available` functions added

## Self-Check: PASSED

- `ToolDefinition.available` defaults to `True` ✓
- `build_catalog_block` excludes `available=False` tools ✓
- `build_llm_tools` excludes `available=False` tools ✓
- `mark_server_unavailable` / `mark_server_available` return correct counts ✓
- All 26 Phase 13 tests still pass ✓
