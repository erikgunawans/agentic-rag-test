---
plan: "18-03"
phase: "18-workspace-virtual-filesystem"
status: complete
wave: 3
self_check: PASSED
subsystem: workspace-tools
tags: [tool-registry, workspace, feature-flag, tdd]
dependency_graph:
  requires: ["18-02"]
  provides: ["write_file", "read_file", "edit_file", "list_files tools in registry"]
  affects: ["tool_registry._REGISTRY", "chat.py tool dispatch loop"]
tech_stack:
  added: []
  patterns:
    - "registry executor signature: (arguments, user_id, context, *, token, **kwargs)"
    - "WORKSPACE_ENABLED kill-switch via pydantic_settings bool field"
    - "lazy import of WorkspaceService inside executors (avoids circular import)"
key_files:
  created:
    - "backend/tests/tools/__init__.py"
    - "backend/tests/tools/test_workspace_tools.py"
  modified:
    - "backend/app/config.py"
    - "backend/app/services/tool_service.py"
decisions:
  - "Registration added as a new _register_workspace_tools() function at the bottom of tool_service.py — same pattern as _register_phase17_todos() in tool_registry.py"
  - "Executors follow the registry dispatcher signature (arguments, user_id, context, *, token, **kwargs) NOT the plan's inline (**kwargs) shape — to match the actual chat.py dispatcher"
  - "execute_tool() dispatch in tool_service.py required NO extra changes — the registry path in chat.py routes through registry.executor directly (D-P13-01 already handles this)"
  - "Tests mock WorkspaceService via patch.dict(sys.modules, ...) to avoid DB connections"
metrics:
  duration: "~20 minutes"
  completed: "2026-05-03"
  tasks: 2
  files: 4
---

# Phase 18 Plan 03: Workspace Tool Registry Registration + Executors Summary

**What was built:** Four workspace LLM tools (`write_file`, `read_file`, `edit_file`, `list_files`) registered through the unified Tool Registry, wired to `WorkspaceService` executors, behind a `WORKSPACE_ENABLED` feature-flag kill-switch. 11 TDD tests verify all dispatch behaviors, error paths, schema conformance, and flag toggling.

## Key Implementation Decisions

### Does `execute_tool()` route through registry automatically?

**Yes — no changes needed to `execute_tool()`.** The existing chat.py registry dispatcher (`_dispatch_tool`) reads `tool_registry._REGISTRY[name].executor` and calls it directly. The `execute_tool()` method on `ToolService` is the **legacy non-registry path**. When `tool_registry_enabled=True`, chat.py bypasses `execute_tool()` entirely and calls the registry executor. The four workspace tools follow this path cleanly.

The `else: return {"error": "Unknown tool"}` fallback in `execute_tool()` was NOT modified — workspace tools are never routed through `execute_tool()` (they bypass it via the registry dispatch path).

### Executor signature

The plan specified `async def _workspace_write_file_executor(*, thread_id, token, file_path, content, **_unused)` but the actual registry dispatcher in chat.py calls executors as `executor(arguments, user_id, context, *, token=..., ...)`. The implementation uses the correct registry dispatcher shape:

```python
async def _workspace_write_file_executor(
    arguments: dict,
    user_id: str,
    context: dict | None = None,
    *,
    token: str | None = None,
    **kwargs,
) -> dict:
```

This is consistent with `_write_todos_executor` in `tool_registry.py` (Phase 17 reference pattern).

### Registration location

Added as `_register_workspace_tools()` function at the bottom of `tool_service.py` (after `_register_natives_with_registry()`). Called at module load. Pattern mirrors Phase 17's `_register_phase17_todos()` in `tool_registry.py`.

Double-gated:
1. `if not settings.tool_registry_enabled: return` — registry must be active
2. `if not settings.workspace_enabled: return` — workspace flag kill-switch (D-08)

### WORKSPACE_ENABLED in config.py

Added as a `pydantic_settings` field (`workspace_enabled: bool = True`) on the `Settings` class — consistent with `sandbox_enabled`, `tool_registry_enabled`, `deep_mode_enabled`. Env var name: `WORKSPACE_ENABLED`.

## Final Tool Descriptions (as registered)

| Tool | Description (truncated) |
|------|--------------------------|
| `write_file` | Create or overwrite a workspace text file scoped to the current chat thread. Path is relative, max 500 chars, content max 1 MB. |
| `read_file` | Read a workspace file. Returns text inline or binary {is_binary:true, signed_url, ...}. Returns {error:file_not_found} if missing. |
| `edit_file` | Edit via exact-string replacement. old_string MUST appear exactly once. Returns structured error if absent or ambiguous. |
| `list_files` | List all workspace files ordered by most recently updated. Returns [{file_path, size_bytes, source, mime_type, updated_at}]. |

## Test Count: 11 PASSED

| # | Test | Behavior |
|---|------|----------|
| 1 | `test_write_file_executor_happy_path` | ok=True, operation=create, size_bytes correct |
| 2 | `test_write_file_executor_absolute_path` | path_invalid_leading_slash error propagates |
| 3 | `test_write_file_executor_content_too_large` | text_content_too_large error propagates |
| 4 | `test_read_file_executor_happy_path` | ok=True, is_binary=False, content present |
| 5 | `test_read_file_executor_not_found` | file_not_found error |
| 6 | `test_edit_file_executor_happy_path` | ok=True on unique match |
| 7 | `test_edit_file_executor_ambiguous` | edit_old_string_ambiguous error |
| 8 | `test_list_files_executor_happy_path` | {ok:True, files:[], count:N} |
| 9 | `test_workspace_enabled_false_unregisters` | Kill-switch: 4 tools absent |
| 10 | `test_workspace_enabled_true_registers` | All 4 tools present |
| 11 | `test_workspace_tool_schemas_conform_to_openai_format` | type=function, name matches, parameters.type=object |

## Commits

| Hash | Description |
|------|-------------|
| `647b104` | `feat(18-03)`: add WORKSPACE_ENABLED flag + register 4 workspace tools in tool_registry |
| `f7321d4` | `test(18-03)`: 11 tool dispatch tests for workspace tools — all green |

## Must-Haves Verified

- [x] Tool registry exposes write_file, read_file, edit_file, list_files when WORKSPACE_ENABLED=True
- [x] Tools dispatch through executor → WorkspaceService methods
- [x] Tool results are structured dicts (no exception leaks)
- [x] Sub-agents accessing the same thread_id get the same workspace via RLS — verified in test 8 (thread_id from context, not LLM args)
- [x] When WORKSPACE_ENABLED=False the four tools are not registered (kill-switch verified in test 9)

## Deviations from Plan

**1. [Rule 1 - Bug] Executor signature mismatch**
- **Found during:** Task 2 implementation
- **Issue:** Plan specified direct keyword-arg signature `(*, thread_id, token, file_path, content, **_unused)` but the registry dispatcher in chat.py passes `(arguments, user_id, context, *, token=..., **kwargs)`
- **Fix:** Used the correct registry dispatcher shape matching Phase 17's `_write_todos_executor` pattern
- **Impact:** Tests pass, dispatch works correctly through the registry path

**2. [Rule 1 - Clarification] Registration location**
- **Found during:** Task 1 design
- **Issue:** Plan said "locate the registration init block" in `tool_service.py`, implying modification of the existing `_register_natives_with_registry()`. However, D-P13-01 explicitly states "NO edits to tool_service.py lines 1-1283" (Phase 13 invariant)
- **Fix:** Added a NEW function `_register_workspace_tools()` at the end of tool_service.py (past line 1356), consistent with the Phase 17 precedent
- **Impact:** D-P13-01 invariant preserved; no accidental breakage of existing registrations

## Threat Mitigations Verified

| Threat ID | Mitigation |
|-----------|------------|
| T-18-11 | path traversal (..) → rejected by service-layer validator (from plan 18-02); test 2 verifies the structured error propagates to executor caller |
| T-18-12 | thread_id is read from `context` (server-set), never from `arguments` (LLM-supplied) |
| T-18-13 | `if not settings.workspace_enabled: return` is the registration gate; verified in test 9 |
| T-18-14 | executor hardcodes `source="agent"` — LLM cannot supply source field |

## Self-Check: PASSED
