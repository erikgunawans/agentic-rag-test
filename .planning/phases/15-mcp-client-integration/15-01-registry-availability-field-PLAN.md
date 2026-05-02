---
phase: 15-mcp-client-integration
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/app/models/tools.py
  - backend/app/services/tool_registry.py
autonomous: true
requirements:
  - MCP-04
  - MCP-05
must_haves:
  truths:
    - "ToolDefinition Pydantic model in backend/app/models/tools.py has field 'available: bool = True' with backward-compatible default"
    - "tool_registry.build_catalog_block() skips tools where available=False (tools not included in the rendered markdown table)"
    - "tool_registry.build_llm_tools() skips tools where available=False (tools not included in LLM tools array)"
    - "Catalog rows for unavailable tools are excluded, not shown with a strike-through or warning marker inside the row"
    - "A standalone mark_server_available(server_name) and mark_server_unavailable(server_name) are exposed from tool_registry.py that set available=False/True on all tools with name starting with '{server_name}__'"
    - "Existing tests in backend/tests/unit/test_tool_registry.py continue passing after the available field is added (backward-compatible default True)"
  artifacts:
    - path: "backend/app/models/tools.py"
      provides: "ToolDefinition.available field (bool = True)"
      contains: "available: bool = True"
    - path: "backend/app/services/tool_registry.py"
      provides: "mark_server_available, mark_server_unavailable, availability filter in build_catalog_block and build_llm_tools"
      contains: "mark_server_available"
  key_links:
    - from: "backend/app/models/tools.py"
      to: "backend/app/services/tool_registry.py"
      via: "ToolDefinition.available used in build_catalog_block and build_llm_tools filters"
      pattern: "tool\\.available"
---

<objective>
Add the `available: bool = True` field to `ToolDefinition` in `backend/app/models/tools.py`, and update `backend/app/services/tool_registry.py` to:
1. Filter out `available=False` tools in `build_catalog_block()` and `build_llm_tools()`.
2. Expose `mark_server_available(server_name: str)` and `mark_server_unavailable(server_name: str)` functions that iterate `_REGISTRY` and flip `available` on all tools whose name starts with `"{server_name}__"`.

This is Wave 1 of Phase 15 — it runs in parallel with 15-02 (MCPClientManager core) and 15-03 (config/lifespan). The reconnect loop in 15-04 calls `mark_server_available` / `mark_server_unavailable` to signal server state changes.

Why this plan first: `tool_registry.py` and `ToolDefinition` are already complete from Phase 13. The availability extension is purely additive — a new field with a backward-compatible default (True) means every existing native and skill tool is unaffected.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/phases/15-mcp-client-integration/15-CONTEXT.md
@backend/app/models/tools.py
@backend/app/services/tool_registry.py
@backend/tests/unit/test_tool_registry.py
</context>

<tasks>

<task id="1">
<name>Add `available: bool = True` to ToolDefinition</name>
<read_first>
- backend/app/models/tools.py (current ToolDefinition class, lines 90+)
- backend/tests/unit/test_tool_registry.py (existing tests — verify none break)
</read_first>
<action>
In `backend/app/models/tools.py`, find the `ToolDefinition` class (already exists from Phase 13).
Add `available: bool = True` as a new field AFTER the `executor` field.

The final ToolDefinition class should look like:

```python
class ToolDefinition(BaseModel):
    """Phase 13 (TOOL-04, TOOL-06): registry entry for native, skill, or MCP tools.
    Phase 15 (MCP-04, MCP-05): adds `available` field for server-disconnection tracking.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True, protected_namespaces=())

    name: str
    description: str
    schema: dict
    source: Literal["native", "skill", "mcp"]
    loading: Literal["immediate", "deferred"]
    executor: Callable[..., Awaitable[dict | str]]
    # Phase 15 (D-P15-11): availability flag for MCP server disconnect tracking.
    # Default True: all existing native/skill tools are always available.
    # MCPClientManager.mark_server_unavailable() flips this to False on disconnect.
    available: bool = True
```

Do NOT change any other part of the file.
</action>
<acceptance_criteria>
- `grep -n "available: bool = True" backend/app/models/tools.py` returns a match inside the ToolDefinition class body
- `cd backend && source venv/bin/activate && python -c "from app.models.tools import ToolDefinition; t = ToolDefinition(name='x', description='', schema={}, source='native', loading='immediate', executor=lambda **kw: {}); print(t.available)"` prints `True`
- `cd backend && source venv/bin/activate && python -c "from app.models.tools import ToolDefinition; t = ToolDefinition(name='x', description='', schema={}, source='native', loading='immediate', executor=lambda **kw: {}, available=False); print(t.available)"` prints `False`
- `cd backend && source venv/bin/activate && python -m pytest tests/unit/test_tool_registry.py -x -q 2>&1 | tail -5` exits 0 with all tests passing (backward-compatible default means no existing test breaks)
</acceptance_criteria>
</task>

<task id="2">
<name>Filter `available=False` tools in build_catalog_block and build_llm_tools</name>
<read_first>
- backend/app/services/tool_registry.py (build_catalog_block at line ~130, build_llm_tools at line ~105)
- backend/app/models/tools.py (ToolDefinition after Task 1 edit)
</read_first>
<action>
In `backend/app/services/tool_registry.py`, add `available` filter in two places:

**In `build_llm_tools()`:** After the `loading` check and before the toggle check, add:
```python
if not tool.available:
    continue
```

The full loop body becomes:
```python
for tool in _REGISTRY.values():
    if tool.loading != "immediate" and tool.name not in active_set:
        continue
    if not tool.available:  # Phase 15 (D-P15-11): skip disconnected MCP server tools
        continue
    if _is_disabled_by_toggle(
        tool,
        web_search_enabled=web_search_enabled,
        sandbox_enabled=sandbox_enabled,
    ):
        continue
    if not _passes_agent_filter(tool, agent_allowed_tools):
        continue
    out.append(tool.schema)
```

**In `build_catalog_block()`:** The tools list comprehension already filters by `t.name != "tool_search"` and `_passes_agent_filter`. Add the `available` check:
```python
tools = [
    t
    for t in _REGISTRY.values()
    if t.name != "tool_search"
    and t.available  # Phase 15 (D-P15-11): skip unavailable MCP server tools
    and _passes_agent_filter(t, agent_allowed_tools)
]
```
</action>
<acceptance_criteria>
- `grep -n "t.available\|tool.available\|not tool.available" backend/app/services/tool_registry.py` returns at least 2 matches (one in build_llm_tools, one in build_catalog_block)
- `cd backend && source venv/bin/activate && python -c "
import asyncio
from app.services import tool_registry
tool_registry._clear_for_tests()

async def noop(**kw): return {}
tool_registry.register('myserver__mytool', 'my desc', {'type':'function','function':{'name':'myserver__mytool'}}, source='mcp', loading='immediate', executor=noop)
import app.services.tool_registry as tr
tr._REGISTRY['myserver__mytool'].available = False
catalog = asyncio.run(tool_registry.build_catalog_block())
assert 'myserver__mytool' not in catalog, 'unavailable tool should be absent from catalog'
print('PASS')
"` prints `PASS`
- `cd backend && source venv/bin/activate && python -m pytest tests/unit/test_tool_registry.py -x -q 2>&1 | tail -5` exits 0 with all tests passing
</acceptance_criteria>
</task>

<task id="3">
<name>Add mark_server_available and mark_server_unavailable to tool_registry</name>
<read_first>
- backend/app/services/tool_registry.py (end of file, after _register_tool_search)
</read_first>
<action>
In `backend/app/services/tool_registry.py`, add two new public functions at the bottom (before or after `_register_tool_search`, but before the `_register_tool_search()` call at the very end):

```python
# ---------------------------------------------------------------------------
# Phase 15 — MCP server availability management (D-P15-11).
# ---------------------------------------------------------------------------

def mark_server_unavailable(server_name: str) -> int:
    """Mark all tools from `server_name` as unavailable (D-P15-11).

    Iterates _REGISTRY and sets available=False on every tool whose name
    starts with f"{server_name}__". Returns the count of tools marked.
    Called by MCPClientManager when a server disconnects.

    Note: Pydantic models are immutable by default. ToolDefinition uses
    ConfigDict with no frozen=True, so direct field assignment works. If
    Pydantic v2 raises ValidationError, use model_copy(update={...}) instead
    and replace the dict entry.
    """
    count = 0
    prefix = f"{server_name}__"
    for name, tool in _REGISTRY.items():
        if name.startswith(prefix):
            try:
                tool.available = False
            except Exception:
                # Pydantic v2 frozen model fallback
                _REGISTRY[name] = tool.model_copy(update={"available": False})
            count += 1
    if count:
        logger.info(
            "tool_registry: marked %d tools unavailable for server=%s",
            count,
            server_name,
        )
    return count


def mark_server_available(server_name: str) -> int:
    """Mark all tools from `server_name` as available again (D-P15-12).

    Called by MCPClientManager after a successful reconnect.
    Returns the count of tools re-enabled.
    """
    count = 0
    prefix = f"{server_name}__"
    for name, tool in _REGISTRY.items():
        if name.startswith(prefix):
            try:
                tool.available = True
            except Exception:
                _REGISTRY[name] = tool.model_copy(update={"available": True})
            count += 1
    if count:
        logger.info(
            "tool_registry: marked %d tools available for server=%s",
            count,
            server_name,
        )
    return count
```
</action>
<acceptance_criteria>
- `grep -n "def mark_server_unavailable\|def mark_server_available" backend/app/services/tool_registry.py` returns exactly 2 matches
- `cd backend && source venv/bin/activate && python -c "
import asyncio
from app.services import tool_registry
tool_registry._clear_for_tests()

async def noop(**kw): return {}
tool_registry.register('myserver__tool1', 'desc1', {'type':'function','function':{'name':'myserver__tool1'}}, source='mcp', loading='immediate', executor=noop)
tool_registry.register('myserver__tool2', 'desc2', {'type':'function','function':{'name':'myserver__tool2'}}, source='mcp', loading='immediate', executor=noop)

# Mark unavailable
count = tool_registry.mark_server_unavailable('myserver')
assert count == 2, f'Expected 2, got {count}'
assert tool_registry._REGISTRY['myserver__tool1'].available == False
assert tool_registry._REGISTRY['myserver__tool2'].available == False

# Mark available again
count2 = tool_registry.mark_server_available('myserver')
assert count2 == 2, f'Expected 2, got {count2}'
assert tool_registry._REGISTRY['myserver__tool1'].available == True
print('PASS')
"` prints `PASS`
- `cd backend && source venv/bin/activate && python -m pytest tests/unit/test_tool_registry.py -x -q 2>&1 | tail -5` exits 0
- `cd backend && source venv/bin/activate && python -c "from app.main import app; print('OK')"` prints `OK` (import smoke test)
</acceptance_criteria>
</task>

</tasks>

<verification>
All three tasks complete when:
1. `ToolDefinition` in `backend/app/models/tools.py` has `available: bool = True`
2. `build_catalog_block` and `build_llm_tools` in `tool_registry.py` both skip `available=False` tools
3. `mark_server_unavailable` and `mark_server_available` are public functions in `tool_registry.py`
4. All existing Phase 13 tests (`tests/unit/test_tool_registry.py`) still pass
5. App import check passes: `python -c "from app.main import app; print('OK')"`
</verification>
