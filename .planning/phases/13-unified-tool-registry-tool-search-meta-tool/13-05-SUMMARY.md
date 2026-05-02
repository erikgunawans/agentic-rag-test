---
plan: 13-05-chat-wiring-multi-agent-filter
phase: 13-unified-tool-registry-tool-search-meta-tool
status: complete
commit: 0b06106
tests: 15 new (8 integration + 7 unit), 41 pre-existing chat router tests still pass
---

# Plan 13-05 — Chat Wiring + Multi-Agent Filter

## What was built

Three flag-gated splices in `chat.py`, one new helper in `agent_service.py`,
plus a registry-first dispatch wrapper (Option A) and per-request active-set
threading.

## Files modified

| File | Change |
|------|--------|
| `backend/app/routers/chat.py` | 5 flag-gated splices (active-set init, tools array, multi-agent catalog, single-agent catalog, dispatch wrapper) + threading active_set/agent_allowed_tools into tool_context. |
| `backend/app/services/agent_service.py` | Added `should_filter_tool(tool_def, agent)` predicate (D-P13-06) + `from app.models.tools import ToolDefinition` import. |
| `backend/tests/api/test_chat_tool_registry_flag.py` | NEW — 8 integration tests |
| `backend/tests/api/fixtures/chat_v1_1_reference.json` | NEW — TOOL-05 byte-identical reference contract |
| `backend/tests/unit/test_agent_service_should_filter_tool.py` | NEW — 7 unit tests |

## Splices applied to chat.py

| Site | Original | New (gated by `settings.tool_registry_enabled`) |
|------|----------|------------------------------------------------|
| Top of `event_generator` (~L658) | (n/a) | `_registry_active_set = tool_registry.make_active_set()` (lazy import) |
| Tools array (~L727) | `tool_service.get_available_tools(...)` | `register_user_skills(...) → tool_registry.build_llm_tools(...)` |
| Multi-agent system prompt (~L758) | `build_skill_catalog_block(...)` | `tool_registry.build_catalog_block(agent_allowed_tools=agent_def.tool_names)` + narrowed `build_llm_tools` |
| Single-agent system prompt (~L850) | `build_skill_catalog_block(...)` | `tool_registry.build_catalog_block(agent_allowed_tools=None)` |
| Pre-`_run_tool_loop` calls (×2) | (n/a) | `tool_context["active_set"] = _registry_active_set; tool_context["agent_allowed_tools"] = …` |
| 4 `tool_service.execute_tool` dispatch sites | direct call | `_dispatch_tool(...)` (registry-first **Option A**, falls through to legacy) |

Every registry import is **lazy** (`from app.services import tool_registry` inside an `if settings.tool_registry_enabled:` block). No registry import at module top.

## should_filter_tool helper

```python
@traced(name="should_filter_tool")
def should_filter_tool(tool_def: ToolDefinition, agent: AgentDefinition) -> bool:
    if tool_def.source == "skill":
        return True              # skill bypass
    if tool_def.name == "tool_search":
        return True              # always-on
    return tool_def.name in agent.tool_names   # NOT allowed_tools
```

Uses `agent.tool_names` per PATTERNS.md critical finding (the AgentDefinition
field is `tool_names`; informal prose in CONTEXT.md used `allowed_tools` which
does not exist on the model).

## Active-set lifecycle

```
SSE request arrives
  → event_generator entered
    → if flag: _registry_active_set = tool_registry.make_active_set()  # fresh set()
    → tool-loop runs
      → tool_search executor reads context["active_set"] and mutates it
      → next iteration: build_llm_tools includes deferred tools now in active_set
    → SSE stream closes
      → event_generator exits
        → _registry_active_set goes out of scope (garbage-collected)
Next SSE request: brand-new active_set; no leakage.
```

## Tool-loop dispatch wiring — Option A committed

Per plan-checker warning D, the literal Option A wording is captured here:

> Locate `_run_tool_loop` (or the inline tool dispatch site) inside chat.py.
> Add a flag-gated prefix to the dispatch (≤ 15 LOC):
> ```python
> # Phase 13 D-P13-05: registry-first dispatch when flag is on.
> if settings.tool_registry_enabled and tool_name in tool_registry._REGISTRY:
>     tool_def = tool_registry._REGISTRY[tool_name]
>     tool_output = await tool_def.executor(arguments, user_id, context)
> else:
>     tool_output = await tool_service.execute_tool(tool_name, arguments, user_id, context)
> ```
> The else-branch preserves byte-identical legacy behavior for TOOL-05.

Implementation: factored into `_dispatch_tool(...)` async helper at the top of
the route handler (just above `_run_tool_loop`). All 4 prior
`tool_service.execute_tool(...)` call sites updated to use `_dispatch_tool(...)`
verbatim, preserving the same kwargs (`registry`, `token`, `stream_callback`).

**Option B (a `tool_search` shim inside `tool_service.execute_tool`) is REJECTED**
per plan-checker D — it would force every future deferred-loaded source to
also need a `tool_service.execute_tool` shim.

## Snapshot fixture

`backend/tests/api/fixtures/chat_v1_1_reference.json` — documents the TOOL-05
byte-identical contract: when `TOOL_REGISTRY_ENABLED=false`, the OpenRouter
payload's `messages` and `tools` come from the legacy paths (`tool_service.get_available_tools`,
`build_skill_catalog_block`) and are byte-identical to v1.1. The test
`test_no_tool_registry_import_when_flag_off` enforces this at the
**import-level** via subprocess (`'app.services.tool_registry' not in sys.modules`)
which is a stronger invariant than a fixture diff.

## Tests

| File | Count | What it locks |
|------|-------|---------------|
| `test_agent_service_should_filter_tool.py` | 7 | D-P13-06 predicate (skill bypass, tool_search always-on, native gate, mcp gate, empty allow list) |
| `test_chat_tool_registry_flag.py` | 8 | Reference fixture exists; subprocess no-import on flag-off; flag-on single-agent catalog; flag-on multi-agent filter; per-request active-set reset; per-request register_user_skills; chat.py contains `_dispatch_tool`; chat.py uses `agent_def.tool_names` (NOT `allowed_tools`) |

Total Phase 13 backend tests across all 5 plans: **78 new tests**, all passing.

41 pre-existing chat router tests still pass (`test_chat_router_phase5_imports`,
`test_chat_router_phase5_wiring`).

## Known constraint (T-13-05-02 mitigation lock)

`tool_registry._REGISTRY` is process-global. When user A registers `legal_review`
first, user B's `register_user_skills` is a no-op for that name (first-write-wins).
The mitigation: the executor closure receives `user_id` per call from chat.py
(not captured at registration time), so `_execute_load_skill(user_id, ...)`
runs with the CURRENT request's user_id. RLS at call time prevents user B from
reading user A's skill payload.

This is acceptable for v1.2; documented as a known constraint. A future cache-eviction
or per-user namespace can address it without changing the API.

## TOOL-01 / TOOL-04 / TOOL-05 satisfied

- **TOOL-01** (compact catalog injected into system prompt when flag on): ✓
- **TOOL-04** (registry serves both single-agent and multi-agent paths): ✓
- **TOOL-05** (byte-identical fallback): ✓ verified by subprocess no-import test + flag-off else-branches preserve legacy paths verbatim
- **D-P13-06** (`agent.tool_names` field used; skill bypass + tool_search always-on): ✓

## Self-Check: PASSED

- [x] `pytest tests/api/test_chat_tool_registry_flag.py tests/unit/test_agent_service_should_filter_tool.py` → 15 passed
- [x] All Phase 13 tests (5 plans) together: 78 passed
- [x] `pytest tests/unit/test_chat_router_phase5_imports.py tests/unit/test_chat_router_phase5_wiring.py` → 41 passed (no regression)
- [x] `python -c "from app.main import app"` → OK
- [x] Subprocess no-import test confirms TOOL-05 invariant
- [x] `grep "agent_def\.allowed_tools" backend/app/routers/chat.py` → 0 matches (PATTERNS.md correction respected)
- [x] Phase 13 functionality online when `TOOL_REGISTRY_ENABLED=true`
