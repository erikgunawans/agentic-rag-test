---
phase: 13-unified-tool-registry-tool-search-meta-tool
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/app/services/tool_registry.py
  - backend/app/config.py
  - backend/app/models/tools.py
  - backend/tests/unit/test_tool_registry.py
autonomous: true
requirements:
  - TOOL-04
  - TOOL-06
must_haves:
  truths:
    - "tool_registry module is importable; ToolDefinition is a Pydantic model with fields name, description, schema, source, loading, executor"
    - "register(name, description, schema, source, loading, executor) inserts into a single dict[str, ToolDefinition] backing store; lookups are O(1) dict access"
    - "Duplicate name on register() logs WARNING and is ignored (first-write-wins)"
    - "settings.tool_registry_enabled defaults to False and reads env var TOOL_REGISTRY_ENABLED"
    - "build_catalog_block() returns a '## Available Tools' markdown block with the tool_search meta-callout above the table; tool_search itself is excluded from rows"
    - "Catalog rows are alphabetically sorted; description column hard-truncates at 80 chars with U+2026 ellipsis; pipe characters in name/description are escaped"
    - "make_active_set() returns an empty set[str] each call (no shared state between calls)"
  artifacts:
    - path: "backend/app/services/tool_registry.py"
      provides: "ToolDefinition model, _REGISTRY dict, register(), build_catalog_block(), make_active_set(), build_llm_tools()"
      contains: "class ToolDefinition"
    - path: "backend/app/config.py"
      provides: "tool_registry_enabled: bool = False Pydantic Settings field"
      contains: "tool_registry_enabled"
    - path: "backend/app/models/tools.py"
      provides: "ToolDefinition Pydantic model (co-located with ToolCallRecord)"
      contains: "class ToolDefinition"
    - path: "backend/tests/unit/test_tool_registry.py"
      provides: "Unit tests for register, dedup, catalog block, active-set, agent filter"
  key_links:
    - from: "backend/app/services/tool_registry.py"
      to: "backend/app/models/tools.py"
      via: "from app.models.tools import ToolDefinition"
      pattern: "from app\\.models\\.tools import ToolDefinition"
    - from: "backend/app/config.py"
      to: "settings.tool_registry_enabled"
      via: "Pydantic Settings field with env var TOOL_REGISTRY_ENABLED"
      pattern: "tool_registry_enabled\\s*:\\s*bool\\s*=\\s*False"
---

<objective>
Build the foundation for Phase 13's unified tool registry: NEW module `backend/app/services/tool_registry.py` containing the `ToolDefinition` Pydantic model, the `_REGISTRY: dict[str, ToolDefinition]` backing store, the `register()` API, the `build_catalog_block()` markdown formatter, the per-request `make_active_set()` helper, and the `build_llm_tools()` helper that downstream `chat.py` will use. Add the `tool_registry_enabled` flag to `backend/app/config.py`. No native registration, no skill registration, no `tool_search` matcher in this plan — those are Wave 2 (13-02, 13-03, 13-04).

Purpose: Wave 2 plans (13-02 native adapter, 13-03 skills, 13-04 tool_search) all depend on these primitives existing. By isolating the core data structures + formatter + flag in Wave 1, Wave 2 can run in parallel.

Output: A new ~250-300 LOC module + one new config field + one new Pydantic model + a unit test suite covering register/lookup/catalog rendering/active-set lifecycle. No `chat.py` or `tool_service.py` integration yet (those are Plan 13-02 and 13-05).
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/13-unified-tool-registry-tool-search-meta-tool/13-CONTEXT.md
@.planning/phases/13-unified-tool-registry-tool-search-meta-tool/13-PATTERNS.md
@backend/app/services/skill_catalog_service.py
@backend/app/models/tools.py
@backend/app/config.py

<interfaces>
<!-- Existing analog: skill_catalog_service.build_skill_catalog_block (the row formatter to widen). Existing analog: ToolCallRecord (the Pydantic shape to mirror). -->

From backend/app/models/tools.py (existing — DO NOT modify, only append):
```python
from typing import Literal
from pydantic import BaseModel

class ToolCallRecord(BaseModel):
    tool: str
    input: dict
    output: dict | str
    error: str | None = None
    tool_call_id: str | None = None
    status: Literal["success", "error", "timeout"] | None = None
```

From backend/app/services/skill_catalog_service.py (existing — DO NOT modify here, leave for flag-off byte-identical fallback):
```python
async def build_skill_catalog_block(user_id: str, token: str) -> str:
    """Returns '## Your Skills' table or '' on error/empty."""
```

From backend/app/config.py (existing pattern at lines 65, 69, 74):
```python
class Settings(BaseSettings):
    tools_enabled: bool = True            # line 65
    agents_enabled: bool = False          # line 69
    sandbox_enabled: bool = False         # line 74
    # Phase 13 ADD here:
    # tool_registry_enabled: bool = False
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add ToolDefinition Pydantic model + tool_registry_enabled config flag</name>
  <files>backend/app/models/tools.py, backend/app/config.py, backend/tests/unit/test_tool_registry.py</files>
  <read_first>
    - backend/app/models/tools.py (entire file — append-only, do not edit existing models)
    - backend/app/config.py (lines 60-100 — see existing tools_enabled/agents_enabled/sandbox_enabled pattern)
    - .planning/phases/13-unified-tool-registry-tool-search-meta-tool/13-PATTERNS.md (Half B for ToolDefinition shape; "config.py PATCH" section for flag pattern)
  </read_first>
  <behavior>
    - Test 1: `from app.models.tools import ToolDefinition` succeeds.
    - Test 2: `ToolDefinition(name="x", description="d", schema={}, source="native", loading="immediate", executor=async_callable)` constructs successfully.
    - Test 3: `ToolDefinition` rejects `source="other"` (Literal validation error).
    - Test 4: `ToolDefinition` rejects `loading="lazy"` (Literal validation error).
    - Test 5: `from app.config import settings; assert settings.tool_registry_enabled is False` (default).
    - Test 6: `monkeypatch.setenv("TOOL_REGISTRY_ENABLED", "true"); reload(config); assert settings.tool_registry_enabled is True` — env var override works.
  </behavior>
  <action>
    1. Append to `backend/app/models/tools.py` (after the existing `ToolCallSummary` class — do not modify any existing class):
       ```python
       from typing import Awaitable, Callable, Literal
       from pydantic import BaseModel, ConfigDict


       class ToolDefinition(BaseModel):
           """Phase 13 (TOOL-04, TOOL-06): registry entry for native, skill, or MCP tools.

           D-P13-01: native tools register via adapter wrap (executor delegates to ToolService.execute_tool).
           D-P13-02: skills register as first-class tools with schema={} (parameterless).
           Loading: 'immediate' = registered at startup; 'deferred' = registered per-request or per-connect.
           """
           model_config = ConfigDict(arbitrary_types_allowed=True)
           name: str
           description: str
           schema: dict
           source: Literal["native", "skill", "mcp"]
           loading: Literal["immediate", "deferred"]
           executor: Callable[..., Awaitable[dict | str]]
       ```
       Reuse imports already at top of the file; only add `Awaitable`, `Callable`, `ConfigDict` if not present.

    2. In `backend/app/config.py`, find the existing `sandbox_enabled: bool = False` field (line 74) and add the new field IMMEDIATELY AFTER it, with a docstring comment. Do not change any other lines:
       ```python
       # Phase 13 (TOOL-01..06; D-P13-01..D-P13-06): Unified Tool Registry & tool_search.
       # Default OFF — when False, chat.py + tool_service.py skip importing the registry
       # entirely (TOOL-05 byte-identical fallback). Env var: TOOL_REGISTRY_ENABLED.
       tool_registry_enabled: bool = False
       ```
       Pydantic Settings auto-binds the env var TOOL_REGISTRY_ENABLED (uppercase of field name).

    3. Create `backend/tests/unit/test_tool_registry.py` with the 6 behavior tests above. Use `pytest`, `pytest.MonkeyPatch`, and `importlib.reload` for the env-var test. Mark the file's first test as the foundation smoke test.

    4. Imports for the test file:
       ```python
       import asyncio
       import importlib
       import pytest
       from app.models.tools import ToolDefinition
       ```

    5. The async executor used in test fixtures must be a real coroutine, e.g.:
       ```python
       async def _noop_executor(arguments: dict, user_id: str, context: dict | None = None) -> dict:
           return {"ok": True}
       ```
  </action>
  <verify>
    <automated>cd backend &amp;&amp; source venv/bin/activate &amp;&amp; pytest tests/unit/test_tool_registry.py -x -k "test_tool_definition or test_settings_flag" -v</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "class ToolDefinition" backend/app/models/tools.py` returns exactly 1 match.
    - `grep -n "tool_registry_enabled" backend/app/config.py` returns exactly 1 match showing `tool_registry_enabled: bool = False`.
    - `cd backend && source venv/bin/activate && python -c "from app.models.tools import ToolDefinition; from app.config import settings; assert settings.tool_registry_enabled is False; print('OK')"` prints OK.
    - `pytest backend/tests/unit/test_tool_registry.py -k "test_tool_definition or test_settings_flag" -v` shows 6 PASSED.
    - No existing test in `backend/tests/` is removed or broken (run full suite after: `pytest backend/tests/ --tb=short -q` shows no NEW failures).
  </acceptance_criteria>
  <done>ToolDefinition model exists, tool_registry_enabled flag exists with default False, 6 behavior tests pass, no regressions to the existing suite.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Create tool_registry module — register API + backing dict + active-set + build_llm_tools</name>
  <files>backend/app/services/tool_registry.py, backend/tests/unit/test_tool_registry.py</files>
  <read_first>
    - backend/app/services/skill_catalog_service.py (entire 112 LOC — analog for module header, fail-soft, pipe sanitization)
    - backend/app/services/tool_service.py lines 1-50 (TOOL_DEFINITIONS schema shape — for reference, NOT for registration here)
    - .planning/phases/13-unified-tool-registry-tool-search-meta-tool/13-PATTERNS.md sections "Half C", "Half F", "Shared Patterns A and F"
    - backend/app/services/tracing_service.py (signature of @traced — needed for async helpers)
  </read_first>
  <behavior>
    - Test 7: `from app.services import tool_registry` succeeds; `tool_registry._REGISTRY == {}` at module load (empty by default — no auto-register here).
    - Test 8: `tool_registry.register("foo", "Foo desc", schema, "native", "immediate", executor)` populates `_REGISTRY["foo"]`; subsequent lookup `tool_registry._REGISTRY["foo"].source == "native"`.
    - Test 9: Duplicate `register("foo", ...)` logs WARNING (capture via `caplog`) and does NOT overwrite the original entry.
    - Test 10: `tool_registry.make_active_set()` returns a fresh `set[str]` each call (two calls return distinct objects).
    - Test 11: `tool_registry.build_llm_tools(active_set=set(), web_search_enabled=True, sandbox_enabled=True, agent_allowed_tools=None)` returns `[]` when registry is empty.
    - Test 12: After registering 3 tools (sources: 1 native immediate, 1 skill deferred, 1 native deferred), `build_llm_tools(active_set=set(), web_search_enabled=True, sandbox_enabled=True, agent_allowed_tools=None)` returns ONLY the immediate-loading tools' schemas (the deferred ones are not in the LLM tools array unless added to active_set).
    - Test 13: After registering an immediate tool "search_documents" and adding "deferred_tool" to active_set, `build_llm_tools(active_set={"deferred_tool"}, ...)` returns BOTH schemas.
    - Test 14: `build_llm_tools(...)` excludes a tool whose name is "web_search" when `web_search_enabled=False`.
    - Test 15: `build_llm_tools(...)` excludes a tool whose name is "execute_code" when `sandbox_enabled=False`.
    - Test 16: With `agent_allowed_tools=["search_documents"]` plus a registered skill "legal_review", `build_llm_tools(...)` returns BOTH schemas (skills bypass agent filter per D-P13-06).
    - Test 16b (plan-checker warning A — tool_search always-on under restrictive agent filter): Register an immediate native "tool_search" plus an immediate native "restricted_tool". With `agent_allowed_tools=["search_documents"]` (note: "tool_search" is NOT in this list), `build_llm_tools(active_set=set(), web_search_enabled=True, sandbox_enabled=True, agent_allowed_tools=["search_documents"])` returns the schema for `tool_search` (always-on per D-P13-06) and EXCLUDES `restricted_tool`. Locks the always-on rule at the LLM-tools-array layer; Task 3's `_passes_agent_filter` covers the catalog-table layer.
  </behavior>
  <action>
    1. Create `backend/app/services/tool_registry.py` with:
       - Module docstring referencing TOOL-01..06 and D-P13-01..06 (mirror skill_catalog_service.py:1-24 style — copy the doc-discipline verbatim with Phase 13 specifics from PATTERNS.md Half A).
       - `from __future__ import annotations`, `import logging`, `from typing import Iterable`.
       - `from app.models.tools import ToolDefinition`.
       - `logger = logging.getLogger(__name__)`.
       - Module-level backing store: `_REGISTRY: dict[str, ToolDefinition] = {}`.

    2. Implement `register(name, description, schema, source, loading, executor) -> None`:
       - If `name in _REGISTRY`: `logger.warning("tool_registry: duplicate name=%s source=%s — ignored", name, source)` then `return` (first-write-wins per PATTERNS.md "No Analog Found").
       - Otherwise: `_REGISTRY[name] = ToolDefinition(name=name, description=description, schema=schema, source=source, loading=loading, executor=executor)`.
       - Type signature must use `Literal["native", "skill", "mcp"]` and `Literal["immediate", "deferred"]` for source/loading.

    3. Implement `make_active_set() -> set[str]`:
       - Return `set()` (empty mutable set, fresh each call). One-liner.
       - Docstring: per-request active set per CONTEXT.md §Discretion §Active-set storage; lifetime = SSE event_generator.

    4. Implement `build_llm_tools(*, active_set: set[str], web_search_enabled: bool, sandbox_enabled: bool, agent_allowed_tools: list[str] | None) -> list[dict]`:
       - Iterate `_REGISTRY.values()`.
       - Include a tool when EITHER (`tool.loading == "immediate"`) OR (`tool.name in active_set`).
       - Apply existing toggles (mirror `tool_service.get_available_tools` lines 391-413):
         * If `tool.name == "web_search"` and not `web_search_enabled`: skip.
         * If `tool.name == "execute_code"` and not `sandbox_enabled`: skip.
       - Apply D-P13-06 agent filter when `agent_allowed_tools is not None`:
         * Always-keep when `tool.source == "skill"` (skill bypass).
         * Always-keep when `tool.name == "tool_search"` (always-on).
         * Otherwise: keep only if `tool.name in agent_allowed_tools`.
       - Return `[tool.schema for tool in <kept>]` (the OpenAI tool-call dicts).
       - Decorate with `@traced(name="build_llm_tools")` from `tracing_service`.

    5. Add a `_clear_for_tests()` helper at the bottom that empties `_REGISTRY` — call from test fixtures via `pytest.fixture(autouse=True)`. Mark with `# pragma: no cover` and a comment "TEST-ONLY — never call from production".

    6. Append the 10 new behavior tests (7-16) to `backend/tests/unit/test_tool_registry.py`. Use an autouse fixture that calls `_clear_for_tests()` between every test:
       ```python
       @pytest.fixture(autouse=True)
       def _reset_registry():
           from app.services import tool_registry
           tool_registry._clear_for_tests()
           yield
           tool_registry._clear_for_tests()
       ```

    7. Module size budget: ~80-120 LOC for the registry primitives in this task (catalog formatter is Task 3; tool_search matcher is Plan 13-04).
  </action>
  <verify>
    <automated>cd backend &amp;&amp; source venv/bin/activate &amp;&amp; pytest tests/unit/test_tool_registry.py -x -v</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "^def register\|^def make_active_set\|^async def build_llm_tools\|^def build_llm_tools" backend/app/services/tool_registry.py | grep -v '^#' | wc -l` returns 3 (register, make_active_set, build_llm_tools).
    - `grep -c "_REGISTRY: dict\[str, ToolDefinition\]" backend/app/services/tool_registry.py` returns at least 1.
    - `grep -c "first-write-wins\|duplicate name=" backend/app/services/tool_registry.py` returns at least 1.
    - `pytest backend/tests/unit/test_tool_registry.py -v 2>&1 | grep -E "passed|failed"` shows all 10 new tests passing (16 total in file with Task 1's 6).
    - `cd backend && source venv/bin/activate && python -c "from app.services import tool_registry; assert tool_registry._REGISTRY == {}; print('OK')"` prints OK (registry empty at import — no auto-register in this plan).
    - `cd backend && source venv/bin/activate && python -c "from app.main import app; print('OK')"` prints OK (no import-time crash).
  </acceptance_criteria>
  <done>tool_registry module imports cleanly with empty registry; register/make_active_set/build_llm_tools APIs work per behaviors; 10 new tests pass; full app import still succeeds.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Implement build_catalog_block formatter (markdown table + cap + filter)</name>
  <files>backend/app/services/tool_registry.py, backend/tests/unit/test_tool_registry.py</files>
  <read_first>
    - backend/app/services/skill_catalog_service.py lines 29-112 (full body — the analog formatter)
    - .planning/phases/13-unified-tool-registry-tool-search-meta-tool/13-PATTERNS.md "Half D", "Shared Pattern B"
    - .planning/phases/13-unified-tool-registry-tool-search-meta-tool/13-CONTEXT.md §D-P13-03 (table format), §D-P13-04 (tool_search meta-callout exclusion), §Discretion (cap=50, desc truncate=80)
  </read_first>
  <behavior>
    - Test 17: `build_catalog_block(agent_allowed_tools=None)` with empty registry returns `""` (no header, byte-equivalent to skill_catalog returning "" today).
    - Test 18: With 1 native tool registered, returns a string starting with `\n\n## Available Tools\n` and containing the tool_search meta-callout line `Call \`tool_search\` with a keyword or regex query when you need a tool not listed below.`
    - Test 19: With 3 tools registered (mixed sources), the table has columns `| Tool | Source | Description |` with a separator `|------|--------|-------------|` and 3 data rows sorted alphabetically by name.
    - Test 20: A tool with description containing pipe `|` and newline `\n` renders with both escaped (`\|` and stripped/normalized).
    - Test 21: A tool with 100-char description truncates to 79 chars + U+2026 ellipsis (total visible = 80 chars).
    - Test 22: Registering 51 tools renders 50 rows + the truncation footer line `Showing 50 of 51 tools. Call tool_search with a keyword to find more.`
    - Test 23: A tool registered with `name="tool_search"` (source=native) is EXCLUDED from rendered rows (D-P13-04 — meta-callout only).
    - Test 24: With `agent_allowed_tools=["search_documents"]` and 3 registered (search_documents native, legal_review skill, tool_search native), the output table contains rows for `search_documents` and `legal_review` but NOT `tool_search` (skill bypass + tool_search excluded from rows).
    - Test 25: With `agent_allowed_tools=["search_documents"]` and a registered native NOT in the agent's allowed list (e.g. "query_database"), that native is filtered OUT of the table.
  </behavior>
  <action>
    1. In `backend/app/services/tool_registry.py`, append:
       - Module-level constants:
         ```python
         _CATALOG_HEADER = (
             "\n\n## Available Tools\n"
             "Call `tool_search` with a keyword or regex query when you need a tool not listed below.\n"
             "Only call a tool when its description clearly matches the user's request.\n\n"
             "| Tool | Source | Description |\n"
             "|------|--------|-------------|"
         )
         _DESC_MAX = 80
         _CATALOG_CAP = 50
         _TRUNCATION_FOOTER_TEMPLATE = "\nShowing {cap} of {total} tools. Call tool_search with a keyword to find more."
         ```

       - Pipe-sanitizing row formatter (analog: skill_catalog_service.py:45-51, widened to 3 columns):
         ```python
         def _format_table_row(name: str, source: str, description: str) -> str:
             desc = (description or "").replace("|", "\\|").replace("\n", " ").strip()
             if len(desc) > _DESC_MAX:
                 desc = desc[: _DESC_MAX - 1] + "…"
             safe_name = (name or "").replace("|", "\\|").strip()
             safe_source = (source or "").replace("|", "\\|").strip()
             return f"| {safe_name} | {safe_source} | {desc} |"
         ```
         IMPORTANT: place the f-string OUTSIDE any backslash escape sequence — i.e. compute `safe_name`, `safe_source`, `desc` first (no backslashes inside f-string braces).

       - The agent-filter predicate (mirroring D-P13-06; same logic as `build_llm_tools` agent gating but as a standalone predicate so `tool_search` matcher in 13-04 can reuse it):
         ```python
         def _passes_agent_filter(tool: ToolDefinition, agent_allowed_tools: list[str] | None) -> bool:
             """D-P13-06: skill bypass + tool_search always-on; native/mcp gated by name."""
             if agent_allowed_tools is None:
                 return True
             if tool.source == "skill":
                 return True
             if tool.name == "tool_search":
                 return True
             return tool.name in agent_allowed_tools
         ```

       - Main formatter:
         ```python
         from app.services.tracing_service import traced

         @traced(name="build_catalog_block")
         async def build_catalog_block(
             *,
             agent_allowed_tools: list[str] | None = None,
         ) -> str:
             """Return the '## Available Tools' system-prompt block, or '' when registry empty.

             D-P13-03: single unified table with Tool | Source | Description columns.
             D-P13-04: tool_search is registered but EXCLUDED from rows — appears in the
                       meta-callout line in _CATALOG_HEADER only.
             D-P13-06: agent_allowed_tools filters native/mcp tools (skill bypass).

             Note: this function does NOT register skills itself — the caller (chat.py
             splice in 13-05) is responsible for calling skill_catalog_service.register_user_skills(...)
             before invoking this. This keeps the registry layer free of DB calls and Supabase imports.
             """
             tools = [
                 t for t in _REGISTRY.values()
                 if t.name != "tool_search"
                 and _passes_agent_filter(t, agent_allowed_tools)
             ]
             if not tools:
                 return ""
             tools.sort(key=lambda t: t.name.lower())
             total = len(tools)
             rows = [_format_table_row(t.name, t.source, t.description) for t in tools[:_CATALOG_CAP]]
             body = _CATALOG_HEADER + "\n" + "\n".join(rows)
             if total > _CATALOG_CAP:
                 body += _TRUNCATION_FOOTER_TEMPLATE.format(cap=_CATALOG_CAP, total=total)
             return body
         ```

    2. Append behavior tests 17-25 to `backend/tests/unit/test_tool_registry.py`. Use the `_reset_registry` autouse fixture from Task 2 (already present). Each test registers a fixed set of tools, calls `await tool_registry.build_catalog_block(...)`, and asserts on the exact string output.

    3. The test for the 50-of-51 cap MUST register tools named with zero-padded indices (`tool_00`...`tool_50`) so alphabetical ordering is deterministic and the assertion can pin the exact omitted name.

    4. The test for D-P13-04 exclusion must register `tool_search` source=native immediate AND another native `search_documents`, then assert `"| tool_search |" not in catalog` while `"| search_documents |" in catalog`.
  </action>
  <verify>
    <automated>cd backend &amp;&amp; source venv/bin/activate &amp;&amp; pytest tests/unit/test_tool_registry.py -x -v</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "build_catalog_block" backend/app/services/tool_registry.py` returns at least 2 (definition + docstring reference).
    - `grep -c "## Available Tools" backend/app/services/tool_registry.py` returns at least 1.
    - `grep -c "tool_search\` with a keyword" backend/app/services/tool_registry.py` returns 1.
    - `grep -c "Showing.*of.*tools" backend/app/services/tool_registry.py` returns 1.
    - `pytest backend/tests/unit/test_tool_registry.py -v 2>&1 | grep "passed"` shows all 25 tests passing (Task 1's 6 + Task 2's 10 + Task 3's 9).
    - `cd backend && source venv/bin/activate && python -c "import asyncio; from app.services import tool_registry; print(asyncio.run(tool_registry.build_catalog_block(agent_allowed_tools=None)))"` prints exactly `` (empty string — registry has no tools at clean import).
    - `cd backend && source venv/bin/activate && python -c "from app.main import app; print('OK')"` prints OK.
  </acceptance_criteria>
  <done>build_catalog_block renders a unified `## Available Tools` table with Source column, alphabetical sort, 50-cap with footer, 80-char description truncation, pipe escaping, tool_search excluded from rows, agent_allowed_tools filter (skill bypass) — verified by 9 unit tests.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| LLM → registry (catalog injection) | Tool name + description strings are rendered into the system prompt. Untrusted skill rows (user-created) flow into the LLM's prompt. |
| Test fixtures → _REGISTRY mutation | _clear_for_tests is test-only but a leak would let tests pollute production state. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-13-01-01 | Tampering | `_format_table_row` description column | mitigate | Pipe-sanitize: replace `|` with `\|` and `\n` with space (verbatim from skill_catalog_service.py:45-51, proven mitigation since Phase 8). Truncate at 80 chars to bound prompt-injection payload size. |
| T-13-01-02 | Information Disclosure | `_REGISTRY` cross-test pollution | mitigate | `_clear_for_tests()` helper marked TEST-ONLY with `# pragma: no cover`; autouse pytest fixture clears registry before/after every test. No production code path may call this helper. |
| T-13-01-03 | Tampering | Skill name field rendering | mitigate | Same pipe-sanitization applied to `safe_name`. Tool author cannot inject row-break or column-break syntax into the markdown table. |
| T-13-01-04 | Denial of Service | Catalog overflow (e.g. 10,000 tools registered) | mitigate | Hard cap at 50 rows in `build_catalog_block` (D-P13-03 / Discretion §Catalog overflow). Worst-case prompt cost stays bounded at ~500 tokens regardless of registry size. |
| T-13-01-05 | Repudiation | Duplicate `register()` silently dropping a tool | accept | Logged at WARNING with name and source — operators can grep logs. First-write-wins is intentional per PATTERNS.md "No Analog Found"; alternative (last-write-wins) would let later modules clobber natives. |
| T-13-01-06 | Spoofing | Unprivileged `register()` calls registering a native named "search_documents" | accept | Registry is in-process Python — any module that imports it can register. Defense-in-depth lives at the source-prefixed name layer (deferred per CONTEXT.md). For v1.2 only `tool_service.py` (Plan 13-02) and `skill_catalog_service.py` (Plan 13-03) call `register()`; both are first-party code reviewed in this milestone. |
</threat_model>

<verification>
- `pytest backend/tests/unit/test_tool_registry.py -v` shows 25 PASSED, 0 FAILED.
- `cd backend && source venv/bin/activate && python -c "from app.main import app; print('OK')"` (full app import) prints OK.
- `cd backend && source venv/bin/activate && python -c "from app.config import settings; assert settings.tool_registry_enabled is False; print('default OK')"` prints `default OK`.
- `cd frontend && npx tsc --noEmit` passes (no frontend changes, sanity check).
- `git diff --stat backend/app/services/tool_registry.py backend/app/models/tools.py backend/app/config.py backend/tests/unit/test_tool_registry.py` shows only new lines / new files, no deletions outside the test file.
</verification>

<success_criteria>
- `backend/app/services/tool_registry.py` exists with `register`, `make_active_set`, `build_llm_tools`, `build_catalog_block`, `_passes_agent_filter`, `_format_table_row`, `_clear_for_tests` (test-only).
- `backend/app/models/tools.py` has `class ToolDefinition` (Pydantic, 6 fields).
- `backend/app/config.py` has `tool_registry_enabled: bool = False`.
- `backend/tests/unit/test_tool_registry.py` has 25 passing tests covering ToolDefinition, settings flag, register/dedup, active-set freshness, build_llm_tools immediate/deferred/active-set/agent-filter logic, build_catalog_block empty/header/sort/escape/truncate/cap-footer/tool_search-exclusion/agent-filter scenarios.
- `_REGISTRY` is empty at clean module import — no native or skill registration happens in this plan (those are 13-02 and 13-03).
- `from app.main import app` still succeeds; existing tests pass.
- TOOL-04 partially satisfied (registry data structure ready for native/skill/MCP entries).
- TOOL-06 fully satisfied (`register(name, description, schema, source, loading, executor)` API exists with single signature).
</success_criteria>

<output>
After completion, create `.planning/phases/13-unified-tool-registry-tool-search-meta-tool/13-01-SUMMARY.md` summarizing:
- Files created/modified
- Test count (25 unit tests)
- Public API surface (register, make_active_set, build_llm_tools, build_catalog_block — signatures)
- What is intentionally NOT done in this plan (native registration → 13-02, skill registration → 13-03, tool_search matcher → 13-04, chat.py wiring → 13-05)
</output>
