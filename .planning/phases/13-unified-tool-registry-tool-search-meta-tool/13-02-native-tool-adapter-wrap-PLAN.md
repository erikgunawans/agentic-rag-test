---
phase: 13-unified-tool-registry-tool-search-meta-tool
plan: 02
type: execute
wave: 2
depends_on:
  - 13-01
files_modified:
  - backend/app/services/tool_service.py
  - backend/tests/unit/test_tool_registry_natives.py
autonomous: true
requirements:
  - TOOL-04
  - TOOL-05
must_haves:
  truths:
    - "When TOOL_REGISTRY_ENABLED=true, every entry in TOOL_DEFINITIONS is registered with the registry exactly once with source='native', loading='immediate'"
    - "When TOOL_REGISTRY_ENABLED=false, the registry module is NOT imported by tool_service.py — zero startup overhead (TOOL-05 invariant)"
    - "Native executor closure delegates to ToolService.execute_tool(name, arguments, user_id, context, ...) — no re-implementation of tool logic"
    - "Existing TOOL_DEFINITIONS list (lines 35-360) and ToolService.execute_tool dispatch (line 416+) remain byte-identical — only an additive bootstrap function and one call to it are added at the end of the module"
    - "ToolService.get_available_tools (lines 391-413) is NOT modified — chat.py keeps using it on the flag-off path"
  artifacts:
    - path: "backend/app/services/tool_service.py"
      provides: "_register_natives_with_registry() bootstrap function called at module bottom"
      contains: "_register_natives_with_registry"
    - path: "backend/tests/unit/test_tool_registry_natives.py"
      provides: "Tests asserting registration count == len(TOOL_DEFINITIONS), executor closure dispatches correctly, flag-off skips entirely"
  key_links:
    - from: "backend/app/services/tool_service.py"
      to: "backend/app/services/tool_registry.py"
      via: "lazy import inside _register_natives_with_registry (gated by settings.tool_registry_enabled)"
      pattern: "from app\\.services import tool_registry"
    - from: "_register_natives_with_registry"
      to: "ToolService.execute_tool"
      via: "executor closure that captures `_name=name` and dispatches via ToolService instance"
      pattern: "_svc\\.execute_tool\\(_name"
---

<objective>
Wrap the existing 14 native tools (`TOOL_DEFINITIONS` list at `tool_service.py:35`) with the registry via the D-P13-01 adapter pattern: a single bootstrap function `_register_natives_with_registry()` enumerates `TOOL_DEFINITIONS`, registers each entry with `source="native"`, `loading="immediate"`, and an executor closure that delegates back into `ToolService.execute_tool(name, arguments, user_id, context, ...)`. The existing 1,283 LOC of `tool_service.py` stays untouched — adapter wrap only.

Purpose: TOOL-04 native-source registration without rewriting the dispatch switch (preserves multi-agent, RAG eval, document_tool consumers). TOOL-05 byte-identical fallback: when `TOOL_REGISTRY_ENABLED=false`, the bootstrap is a no-op AND `tool_registry` is never imported.

Output: ~30-50 LOC additive splice at the bottom of `tool_service.py` + a unit test that verifies registration count, executor delegation, and flag-off skip.

This plan can run in parallel with 13-03 (skills) and 13-04 (tool_search) — all three depend only on 13-01.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/phases/13-unified-tool-registry-tool-search-meta-tool/13-CONTEXT.md
@.planning/phases/13-unified-tool-registry-tool-search-meta-tool/13-PATTERNS.md
@.planning/phases/13-unified-tool-registry-tool-search-meta-tool/13-01-tool-registry-foundation-PLAN.md
@backend/app/services/tool_service.py

<interfaces>
<!-- From 13-01 (Wave 1): the registry primitives this plan depends on. -->

From backend/app/services/tool_registry.py (created by 13-01):
```python
def register(
    name: str,
    description: str,
    schema: dict,
    source: Literal["native", "skill", "mcp"],
    loading: Literal["immediate", "deferred"],
    executor: Callable[..., Awaitable[dict | str]],
) -> None: ...
```

From backend/app/services/tool_service.py (existing — DO NOT modify the body):
```python
# Line 35 — list of 14 native tools, each entry shape:
# {"type": "function", "function": {"name": str, "description": str, "parameters": dict}}
TOOL_DEFINITIONS: list[dict] = [...]

# Line 387 — class
class ToolService:
    @traced(name="execute_tool")
    async def execute_tool(
        self,
        name: str,
        arguments: dict,
        user_id: str,
        context: dict | None = None,
        *,
        registry=None,
        token: str | None = None,
        stream_callback=None,
    ) -> dict: ...

# Module-level singleton instance (existing — chat.py imports this)
tool_service = ToolService()
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add _register_natives_with_registry bootstrap + tests for registration count and executor delegation</name>
  <files>backend/app/services/tool_service.py, backend/tests/unit/test_tool_registry_natives.py</files>
  <read_first>
    - backend/app/services/tool_service.py lines 1-50 (TOOL_DEFINITIONS shape)
    - backend/app/services/tool_service.py lines 380-420 (class ToolService, get_available_tools, execute_tool signature)
    - backend/app/services/tool_service.py last 30 lines (where to splice the bootstrap)
    - .planning/phases/13-unified-tool-registry-tool-search-meta-tool/13-PATTERNS.md "tool_service.py PATCH" section (lines starting with "Splice point: bootstrap hook at module bottom")
    - backend/app/services/tool_registry.py (created by 13-01 — confirm `register()` signature)
  </read_first>
  <behavior>
    - Test 1: With `settings.tool_registry_enabled=False`, importing `tool_service` does NOT import `tool_registry` (verifiable via `sys.modules` introspection — `app.services.tool_registry` is absent after a fresh import).
    - Test 2 (plan-checker warning C fix — resilient to 13-04 tool_search registration): With `settings.tool_registry_enabled=True` and `_register_natives_with_registry()` invoked, every TOOL_DEFINITIONS entry's `function.name` is present in `tool_registry._REGISTRY`. Concretely: `assert {entry["function"]["name"] for entry in TOOL_DEFINITIONS} <= set(tool_registry._REGISTRY.keys())` (subset check). This avoids the prior count-equality assertion `len(_REGISTRY) == len(TOOL_DEFINITIONS)`, which becomes false after Plan 13-04 self-registers `tool_search` (registry would contain natives + tool_search). Also assert no native is registered twice: each `entry["function"]["name"]` appears exactly once in `_REGISTRY` after `_register_natives_with_registry()` runs.
    - Test 3: With `settings.tool_registry_enabled=True`, every entry in `tool_registry._REGISTRY.values()` has `source == "native"` and `loading == "immediate"`.
    - Test 4: Every native tool's `description` and `schema` in the registry match the corresponding `TOOL_DEFINITIONS` entry's `function.description` and the full top-level dict.
    - Test 5: Calling a registered native's executor (e.g. `await tool_registry._REGISTRY["search_documents"].executor(arguments={...}, user_id="u1", context={})`) invokes `ToolService.execute_tool` with the captured tool name (verified via mock or by patching `ToolService.execute_tool` to record calls).
    - Test 6: Re-running `_register_natives_with_registry()` (e.g. after `tool_registry._clear_for_tests()`) does NOT raise on the duplicate path — still registers exactly `len(TOOL_DEFINITIONS)` entries (idempotent on a clean registry).
  </behavior>
  <action>
    1. Open `backend/app/services/tool_service.py`. Locate the very end of the file (after the `tool_service = ToolService()` singleton instantiation, which is the last existing executable statement). Append:

       ```python
       # ---------------------------------------------------------------------------
       # Phase 13 D-P13-01 adapter wrap (TOOL-04, TOOL-05).
       #
       # Register every native TOOL_DEFINITIONS entry with the unified registry as
       # source="native", loading="immediate". The executor is a thin closure that
       # delegates back into ToolService.execute_tool — no logic is re-implemented
       # here. When settings.tool_registry_enabled is False, this function is a
       # no-op AND tool_registry is never imported (TOOL-05 byte-identical fallback).
       # ---------------------------------------------------------------------------
       def _register_natives_with_registry() -> None:
           """D-P13-01: enumerate TOOL_DEFINITIONS once and register each as a native tool.

           Idempotent on a clean registry. If the registry already has an entry for
           a given name, register() logs a WARNING and skips (first-write-wins).
           Gated by settings.tool_registry_enabled — early return when False so
           neither the registry module nor the closures are instantiated on flag-off
           deployments (TOOL-05 invariant).
           """
           if not settings.tool_registry_enabled:
               return
           # Lazy import: the registry module must NOT be imported when the flag is
           # off (TOOL-05 byte-identical fallback). Verified by test_no_import_when_flag_off.
           from app.services import tool_registry

           for tool in TOOL_DEFINITIONS:
               fn = tool["function"]
               name = fn["name"]
               description = fn.get("description", "")

               # Closure captures `name` via default-arg binding so each closure
               # holds its own tool name (avoids late-binding bug on the loop var).
               async def _executor(
                   arguments: dict,
                   user_id: str,
                   context: dict | None = None,
                   *,
                   _name: str = name,
                   **kwargs,
               ) -> dict | str:
                   return await tool_service.execute_tool(
                       _name, arguments, user_id, context, **kwargs
                   )

               tool_registry.register(
                   name=name,
                   description=description,
                   schema=tool,  # full top-level dict, includes type=function
                   source="native",
                   loading="immediate",
                   executor=_executor,
               )


       # Run the adapter wrap at module load. No-op when flag is off.
       _register_natives_with_registry()
       ```

    2. Confirm the splice did NOT modify any line above the new block. Run `git diff backend/app/services/tool_service.py | head -5` — the diff should show ONLY additions at the bottom (no `-` lines).

    3. Create `backend/tests/unit/test_tool_registry_natives.py` with the 6 behavior tests:
       - Use `pytest`, `monkeypatch`, `importlib.reload`, and `sys.modules` introspection.
       - Use the `_clear_for_tests()` autouse fixture pattern from 13-01 to reset the registry between tests.
       - For Test 1 (no-import flag-off): `monkeypatch.setattr("app.config.settings.tool_registry_enabled", False)`, then call `_register_natives_with_registry()` from a fresh subprocess via `subprocess.run([sys.executable, "-c", "..."])` to truly verify import-time behavior. Assert `app.services.tool_registry` not in the subprocess's stdout list of `sys.modules`. Alternative: import `tool_service` fresh, then check `"app.services.tool_registry" not in sys.modules`. Use whichever is more reliable in pytest.
       - For Test 5 (executor delegation): use `unittest.mock.AsyncMock` to patch `ToolService.execute_tool`, register natives, retrieve the closure for "search_documents", call it with sample args, and assert the mock was awaited with `("search_documents", {...args...}, "u1", {})`.

    4. Subprocess test sketch for Test 1:
       ```python
       import subprocess, sys, json
       def test_no_import_when_flag_off():
           code = (
               "import os; os.environ['TOOL_REGISTRY_ENABLED']='false'; "
               "import app.services.tool_service; "
               "import sys, json; "
               "print(json.dumps('app.services.tool_registry' in sys.modules))"
           )
           result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True, cwd="backend")
           assert result.stdout.strip() == "false"
       ```
       Adjust the working directory or `PYTHONPATH` to whatever the existing test suite uses (check existing test files for the pattern).

    5. Test 4 implementation: iterate `TOOL_DEFINITIONS` and assert for each entry that `tool_registry._REGISTRY[entry["function"]["name"]].schema == entry`.
  </action>
  <verify>
    <automated>cd backend &amp;&amp; source venv/bin/activate &amp;&amp; pytest tests/unit/test_tool_registry_natives.py -x -v</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "_register_natives_with_registry" backend/app/services/tool_service.py` returns 2 (definition + call).
    - `grep -c "from app.services import tool_registry" backend/app/services/tool_service.py` returns 1 (lazy import inside the function only — NOT at module top).
    - `grep -B2 -A2 "from app.services import tool_registry" backend/app/services/tool_service.py | grep -c "if not settings.tool_registry_enabled"` returns 1 (the import is gated by the flag check).
    - `git diff backend/app/services/tool_service.py | grep -c "^-[^-]"` returns 0 (no deletions in the diff — additive only).
    - `pytest backend/tests/unit/test_tool_registry_natives.py -v` shows all 6 PASSED.
    - With `TOOL_REGISTRY_ENABLED=false`: `cd backend && source venv/bin/activate && TOOL_REGISTRY_ENABLED=false python -c "import app.services.tool_service; import sys; print('app.services.tool_registry' in sys.modules)"` prints `False`.
    - With `TOOL_REGISTRY_ENABLED=true`: `cd backend && source venv/bin/activate && TOOL_REGISTRY_ENABLED=true python -c "from app.services import tool_service, tool_registry; print(len(tool_registry._REGISTRY))"` prints a positive integer ≥ 14.
    - `cd backend && source venv/bin/activate && python -c "from app.main import app; print('OK')"` prints OK (full app import passes; PostToolUse hook will run this automatically).
    - All existing tests still pass: `pytest backend/tests/unit/ -x --tb=short -q` shows no NEW failures (compare against pre-change baseline).
  </acceptance_criteria>
  <done>14 natives register exactly once with source=native, loading=immediate; flag-off skip is verified by an absence-of-module test; executor closures delegate to ToolService.execute_tool with correct tool name capture (no late-binding bug); 1,283 LOC of pre-existing tool_service.py body is unchanged.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Module load → bootstrap call | `_register_natives_with_registry()` runs at import time. Must not crash the app even on registry errors. |
| Closure → ToolService dispatch | Native executor delegates to ToolService.execute_tool — relies on existing auth + RLS path. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-13-02-01 | Denial of Service | `_register_natives_with_registry()` raising during import | mitigate | Function is gated by `if not settings.tool_registry_enabled: return`. With flag off (default), import is byte-identical to v1.1. Bootstrap only runs when an operator opted in via env var. If a future native has a malformed entry, the registry's first-write-wins logs a WARNING — does not raise. |
| T-13-02-02 | Elevation of Privilege | Native executor closure called from registry path bypasses `get_current_user` | accept | Executor delegates to `ToolService.execute_tool(user_id, ...)` — the same dispatch path used today. The user_id flows from chat.py's `get_current_user` (Plan 13-05); the registry layer never invents a user_id. Existing RLS-scoped client guards (`get_supabase_authed_client(token)`) still gate every read. |
| T-13-02-03 | Tampering | SQL-write guard regex (_WRITE_KEYWORDS in tool_service.py) bypassed via registry | accept | The closure delegates to `ToolService.execute_tool` — the existing SQL-write guard (intercepts in `_execute_query_database`) executes on the same code path. No bypass introduced. |
| T-13-02-04 | Information Disclosure | Closure leaks user_id across requests via late-binding bug | mitigate | Closure captures `name` via default-arg `_name: str = name` (idiomatic Python late-binding fix). user_id is passed explicitly per-call from chat.py — never captured in the closure. Test 5 verifies this. |
| T-13-02-05 | Spoofing | Tampered TOOL_DEFINITIONS could register a different schema | accept | TOOL_DEFINITIONS is in-tree code reviewed via PR. No supply-chain mitigation needed for v1.2; future MCP integration (Phase 15) will add server-name prefixing for collision safety. |
</threat_model>

<verification>
- All 6 unit tests in `test_tool_registry_natives.py` pass.
- All 25 tests in `test_tool_registry.py` (from 13-01) still pass.
- Subprocess flag-off test confirms `app.services.tool_registry` is NOT in `sys.modules` after importing `tool_service` with the flag off.
- Full app import passes: `python -c "from app.main import app; print('OK')"`.
- `git diff backend/app/services/tool_service.py` shows only additions at the bottom of the file (no edits to lines 1-1283).
</verification>

<success_criteria>
- 14 native tools (whatever `len(TOOL_DEFINITIONS)` is) register with the registry exactly once when `TOOL_REGISTRY_ENABLED=true`.
- Each registered native has `source="native"`, `loading="immediate"`, schema = the original TOOL_DEFINITIONS entry, executor = closure that calls `ToolService.execute_tool(name, ...)`.
- Flag-off path (`TOOL_REGISTRY_ENABLED=false`): `app.services.tool_registry` is NOT imported, the bootstrap function returns immediately, and `tool_service.py` behaves byte-identically to v1.1.
- Existing `tool_service.py` body (TOOL_DEFINITIONS list, `class ToolService`, `execute_tool`, `get_available_tools`, helpers) is byte-identical — only additive splice at module bottom.
- TOOL-04 native source: ✓ (this plan).
- TOOL-05 byte-identical fallback: ✓ verified by subprocess no-import test.
</success_criteria>

<output>
After completion, create `.planning/phases/13-unified-tool-registry-tool-search-meta-tool/13-02-SUMMARY.md` summarizing:
- Number of native tools registered (= `len(TOOL_DEFINITIONS)` at the time of the plan)
- Bootstrap function signature
- Test count and notable assertions (subprocess flag-off, executor delegation via mock, late-binding fix)
- Confirmation that no production line in tool_service.py:1-1283 was modified
</output>
