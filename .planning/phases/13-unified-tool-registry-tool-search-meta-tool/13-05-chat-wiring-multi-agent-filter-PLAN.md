---
phase: 13-unified-tool-registry-tool-search-meta-tool
plan: 05
type: execute
wave: 3
depends_on:
  - 13-01
  - 13-02
  - 13-03
  - 13-04
files_modified:
  - backend/app/routers/chat.py
  - backend/app/services/agent_service.py
  - backend/tests/api/test_chat_tool_registry_flag.py
  - backend/tests/unit/test_agent_service_should_filter_tool.py
autonomous: true
requirements:
  - TOOL-01
  - TOOL-04
  - TOOL-05
must_haves:
  truths:
    - "When TOOL_REGISTRY_ENABLED=true, the system prompt for both single-agent and multi-agent paths contains a '## Available Tools' block built by tool_registry.build_catalog_block(...)"
    - "When TOOL_REGISTRY_ENABLED=true, the LLM tools array passed to OpenRouter is built from tool_registry.build_llm_tools(...) and includes the tool_search meta-tool plus all immediate-loading natives"
    - "When TOOL_REGISTRY_ENABLED=false, chat.py imports tool_registry NOWHERE and behavior is byte-identical to v1.1 (TOOL-05 invariant — verified by snapshot test on system prompt + tools array)"
    - "Multi-agent path filters the catalog and tools array via agent.tool_names with skill bypass and tool_search always-on (D-P13-06)"
    - "Per-request active_set is created in event_generator via tool_registry.make_active_set(); passed to build_llm_tools and via context dict to the tool-loop so tool_search executor can mutate it"
    - "Active set resets between requests (TOOL-03 — verified by integration test sending two consecutive chat requests and asserting the second request's initial tools array does not include tools added by the first)"
    - "should_filter_tool helper exists on agent_service.py with signature should_filter_tool(tool_def, agent: AgentDefinition) -> bool — applies skill bypass + tool_search always-on + tool_names gate"
  artifacts:
    - path: "backend/app/routers/chat.py"
      provides: "Three flag-gated splices: tools array (L617-623), multi-agent catalog (L649-656), single-agent catalog (L719-727), active-set creation in event_generator"
      min_lines: 50
    - path: "backend/app/services/agent_service.py"
      provides: "should_filter_tool(tool_def, agent) helper"
      contains: "def should_filter_tool"
    - path: "backend/tests/api/test_chat_tool_registry_flag.py"
      provides: "Byte-identical snapshot test (flag-off vs v1.1 reference) + flag-on integration test for catalog injection + active-set per-request reset test"
    - path: "backend/tests/unit/test_agent_service_should_filter_tool.py"
      provides: "Unit tests for should_filter_tool predicate (skill bypass, tool_search always-on, native gated, mcp gated)"
  key_links:
    - from: "backend/app/routers/chat.py event_generator"
      to: "tool_registry.make_active_set + build_llm_tools + build_catalog_block + register_user_skills"
      via: "lazy import inside `if settings.tool_registry_enabled:` branches"
      pattern: "if settings\\.tool_registry_enabled:"
    - from: "tool-loop dispatch for tool_search"
      to: "active_set mutation"
      via: "context dict carrying active_set + agent_allowed_tools, consumed by tool_search executor (registered in 13-04)"
      pattern: "context\\[.active_set.\\]"
---

<objective>
Wire the registry into `chat.py` and add the multi-agent filter helper. Three flag-gated splices in `chat.py` (lines ~617-623, ~649-656, ~719-727) replace `tool_service.get_available_tools(...)` and `build_skill_catalog_block(...)` with `tool_registry.build_llm_tools(...)` and `tool_registry.build_catalog_block(...)` when `settings.tool_registry_enabled` is True. Active set is created per-request inside `event_generator` via `tool_registry.make_active_set()` and threaded through the existing tool-loop's `context` dict so the `tool_search` executor (registered in 13-04) can mutate it. A new `should_filter_tool(tool_def, agent)` helper on `agent_service.py` codifies D-P13-06.

Critical invariant TOOL-05: when `TOOL_REGISTRY_ENABLED=false`, `chat.py` does NOT import `tool_registry` and behavior is byte-identical to v1.1. The snapshot test in this plan locks that invariant.

Purpose: TOOL-01 (compact catalog injected into system prompt). TOOL-04 (registry serves both single-agent and multi-agent paths). TOOL-05 (byte-identical fallback verified end-to-end). D-P13-06 (multi-agent filter using `agent.tool_names`, NOT `allowed_tools` per PATTERNS.md critical finding).

Output: ~100-150 LOC of patches across chat.py + agent_service.py + 2 new test files. This is Wave 3 — final wiring after 13-01 through 13-04 land.
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
@.planning/phases/13-unified-tool-registry-tool-search-meta-tool/13-02-native-tool-adapter-wrap-PLAN.md
@.planning/phases/13-unified-tool-registry-tool-search-meta-tool/13-03-skills-as-first-class-tools-PLAN.md
@.planning/phases/13-unified-tool-registry-tool-search-meta-tool/13-04-tool-search-meta-tool-active-set-PLAN.md
@backend/app/routers/chat.py
@backend/app/services/agent_service.py
@backend/app/models/agents.py

<interfaces>
<!-- From Wave 1+2: registry primitives + native + skill + tool_search registrations. -->

From backend/app/services/tool_registry.py (after 13-01..04):
```python
def make_active_set() -> set[str]: ...

@traced(name="build_llm_tools")
def build_llm_tools(*, active_set: set[str], web_search_enabled: bool,
                   sandbox_enabled: bool, agent_allowed_tools: list[str] | None) -> list[dict]: ...

@traced(name="build_catalog_block")
async def build_catalog_block(*, agent_allowed_tools: list[str] | None = None) -> str: ...

@traced(name="tool_search")
async def tool_search(*, keyword: str | None = None, regex: str | None = None,
                     active_set: set[str] | None = None,
                     agent_allowed_tools: list[str] | None = None) -> dict: ...
```

From backend/app/services/skill_catalog_service.py (after 13-03):
```python
async def register_user_skills(user_id: str, token: str) -> None: ...
async def build_skill_catalog_block(user_id: str, token: str) -> str: ...  # legacy — flag-off only
```

From backend/app/models/agents.py:
```python
class AgentDefinition(BaseModel):
    name: str
    tool_names: list[str]   # <-- the actual field name (PATTERNS.md critical finding)
    system_prompt: str
    # ...
```

From backend/app/routers/chat.py (current splice points):
```python
# Line 15:
from app.services.skill_catalog_service import build_skill_catalog_block

# Line 617-623 (tools array):
all_tools = (
    tool_service.get_available_tools(web_search_enabled=web_search_effective)
    if settings.tools_enabled else []
)
available_tool_names = [t["function"]["name"] for t in all_tools]

# Line 649-656 (multi-agent catalog injection):
skill_catalog = await build_skill_catalog_block(user["id"], user["token"])
messages = (
    [{"role": "system", "content": agent_def.system_prompt + skill_catalog}]
    + [...]
)

# Line 719-727 (single-agent catalog injection):
skill_catalog = await build_skill_catalog_block(user["id"], user["token"])
messages = (
    [{"role": "system", "content": SYSTEM_PROMPT + pii_guidance + skill_catalog}]
    + [...]
)
```

From backend/app/services/agent_service.py:
```python
# Line 135-141 — existing pattern to mirror:
@traced(name="get_agent_tools")
def get_agent_tools(agent: AgentDefinition, all_tools: list[dict]) -> list[dict]:
    return [t for t in all_tools if t["function"]["name"] in agent.tool_names]
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add should_filter_tool helper on agent_service.py with full unit test coverage</name>
  <files>backend/app/services/agent_service.py, backend/tests/unit/test_agent_service_should_filter_tool.py</files>
  <read_first>
    - backend/app/services/agent_service.py lines 130-145 (existing get_agent_tools pattern + AgentDefinition import)
    - backend/app/models/agents.py (full file — confirm `tool_names` is the field name; PATTERNS.md called this out as a critical finding because CONTEXT.md prose used `allowed_tools`)
    - backend/app/models/tools.py (after 13-01 — confirm ToolDefinition shape)
    - .planning/phases/13-unified-tool-registry-tool-search-meta-tool/13-PATTERNS.md "agent_service.py PATCH" section
    - .planning/phases/13-unified-tool-registry-tool-search-meta-tool/13-CONTEXT.md §D-P13-06 (skill bypass, tool_search always-on, MCP gated)
  </read_first>
  <behavior>
    - Test 1: `should_filter_tool(skill_tool, agent_with_empty_tool_names)` returns True (skill bypass — `agent.tool_names == []` is irrelevant for skills).
    - Test 2: `should_filter_tool(tool_search_tool, agent_with_empty_tool_names)` returns True (tool_search always-on regardless of agent).
    - Test 3: `should_filter_tool(native_tool_search_documents, agent_with_tool_names=["search_documents"])` returns True.
    - Test 4: `should_filter_tool(native_tool_query_database, agent_with_tool_names=["search_documents"])` returns False (not in allow list).
    - Test 5: `should_filter_tool(mcp_tool_github_search, agent_with_tool_names=["github_search"])` returns True.
    - Test 6: `should_filter_tool(mcp_tool_github_search, agent_with_tool_names=["search_documents"])` returns False.
    - Test 7: For an agent with `tool_names=[]` (no whitelist), all native and mcp tools return False; only skills + tool_search return True.
  </behavior>
  <action>
    1. In `backend/app/services/agent_service.py`, locate the `get_agent_tools` function (around line 135). Add the new helper IMMEDIATELY AFTER it. Reuse the existing `@traced` import from this file:

       ```python
       from app.models.tools import ToolDefinition  # Add at top of file with the other imports.


       @traced(name="should_filter_tool")
       def should_filter_tool(tool_def: ToolDefinition, agent: AgentDefinition) -> bool:
           """D-P13-06: predicate for catalog + tool_search result filtering.

           Returns True when the tool MUST be retained for this agent.
           Returns False to filter the tool out.

           Rules (lock CONTEXT.md §D-P13-06):
             - Skills bypass agent filter (skills are user-scoped, not agent-scoped).
             - tool_search is always-on (every agent must be able to discover tools).
             - Native + MCP tools are gated by the agent's tool_names allow list.
           NOTE: AgentDefinition's allow-list field is `tool_names` — NOT `allowed_tools`
           (the latter is informal prose; the model field is `tool_names` per
           backend/app/models/agents.py:8).
           """
           if tool_def.source == "skill":
               return True
           if tool_def.name == "tool_search":
               return True
           return tool_def.name in agent.tool_names
       ```

    2. Create `backend/tests/unit/test_agent_service_should_filter_tool.py` with all 7 behavior tests. Use real `ToolDefinition` and `AgentDefinition` instances (no mocks) — this is pure-function logic.

    3. Test fixture for ToolDefinition:
       ```python
       async def _noop_executor(*args, **kwargs): return {}

       def _make_tool(name: str, source: str = "native", loading: str = "immediate"):
           return ToolDefinition(
               name=name, description=f"{name} desc", schema={"type": "function"},
               source=source, loading=loading, executor=_noop_executor,
           )
       ```

    4. Test fixture for AgentDefinition: import the existing model and instantiate with required fields. Look at the existing `test_agent_service_classify_intent_egress.py` for an example of how agents are constructed in tests (mirror that pattern to avoid breakage on AgentDefinition's other required fields).
  </action>
  <verify>
    <automated>cd backend &amp;&amp; source venv/bin/activate &amp;&amp; pytest tests/unit/test_agent_service_should_filter_tool.py -x -v</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "^def should_filter_tool" backend/app/services/agent_service.py` returns 1.
    - `grep -c "agent\.tool_names" backend/app/services/agent_service.py` returns at least 2 (existing get_agent_tools at line ~140 + new should_filter_tool).
    - `grep -c "agent\.allowed_tools" backend/app/services/agent_service.py` returns 0 (do NOT introduce that name — PATTERNS.md correction).
    - `pytest backend/tests/unit/test_agent_service_should_filter_tool.py -v` shows all 7 PASSED.
    - `pytest backend/tests/unit/test_agent_service_classify_intent_egress.py backend/tests/unit/test_agent_service_tool_awareness.py -v` shows no NEW failures.
    - `cd backend && source venv/bin/activate && python -c "from app.services.agent_service import should_filter_tool; print('OK')"` prints OK.
  </acceptance_criteria>
  <done>should_filter_tool implements D-P13-06 exactly using `agent.tool_names` (not `allowed_tools`); 7 unit tests pass; existing agent_service tests still pass.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Wire chat.py — three flag-gated splices + active-set creation + register_user_skills + byte-identical snapshot test</name>
  <files>backend/app/routers/chat.py, backend/tests/api/test_chat_tool_registry_flag.py</files>
  <read_first>
    - backend/app/routers/chat.py lines 1-30 (imports — check for existing tool_registry imports; should be none yet)
    - backend/app/routers/chat.py lines 600-730 (the three splice regions: tools array @617-623, multi-agent catalog @649-656, single-agent catalog @719-727)
    - backend/app/routers/chat.py lines 1000-1080 (the tool-loop dispatch — confirm where the `context` dict flows to tool execution; tool_search executor in 13-04 reads `context["active_set"]` and `context["agent_allowed_tools"]`)
    - .planning/phases/13-unified-tool-registry-tool-search-meta-tool/13-PATTERNS.md "chat.py PATCH" section (Splices 1, 2, 3) and "Shared Pattern A" (lazy import for byte-identical fallback)
    - .planning/phases/13-unified-tool-registry-tool-search-meta-tool/13-CONTEXT.md §D-P13-01 (when flag is False, `tool_registry` is NOT initialized at all)
    - backend/app/services/tool_registry.py (final form after Wave 2 — confirm signatures)
    - backend/app/services/skill_catalog_service.py (after 13-03 — confirm register_user_skills signature)
  </read_first>
  <behavior>
    - Test 1 (byte-identical fallback / TOOL-05): with `TOOL_REGISTRY_ENABLED=false` (default), the system prompt and tools array fed to OpenRouter for a fixed `(message, history, user_id, token, web_search_enabled, sandbox_enabled)` tuple are EQUAL to the v1.1 reference. Implementation: capture both via `unittest.mock.patch` on `openrouter_service.stream_chat` (or whatever the chat client wrapper is), record the `messages` and `tools` kwargs, run a chat request, then assert against a stored golden fixture. The golden fixture is captured in this test from a fresh run with the flag explicitly off and committed alongside the test.
    - Test 2 (flag-off no-import): subprocess test asserts `app.services.tool_registry not in sys.modules` after running a chat request with `TOOL_REGISTRY_ENABLED=false`. Same shape as Test 1 in 13-02 but applied to chat.py end-to-end. Run via `subprocess.run([...])` to get a clean Python process.
    - Test 3 (flag-on single-agent catalog): with `TOOL_REGISTRY_ENABLED=true` and `agents_enabled=false`, the system prompt fed to OpenRouter contains the substring `"## Available Tools"` and the meta-callout line `"Call \`tool_search\` with a keyword or regex query"`. The tools array contains `tool_search` and the 14 immediate-loading natives.
    - Test 4 (flag-on multi-agent filter): with `TOOL_REGISTRY_ENABLED=true` and `agents_enabled=true`, set up a research agent with `tool_names=["search_documents", "kb_search"]` (or whatever subset the test fixture uses). Assert the catalog block rendered for that agent includes `search_documents` and any registered skill but EXCLUDES non-allowed natives like `query_database`. Assert the tools array passed to OpenRouter mirrors that filter (skill bypass, tool_search always-on).
    - Test 5 (active-set per-request reset / TOOL-03): send two consecutive chat requests with `TOOL_REGISTRY_ENABLED=true`. In the first request, simulate a `tool_search(keyword="x")` matching some deferred tool. After the first request returns, send a second request and assert the initial tools array passed to OpenRouter for the second request does NOT include the deferred tool (it must be re-discovered via tool_search). This is the per-request reset invariant.
    - Test 6 (skill registration per-request): with `TOOL_REGISTRY_ENABLED=true`, mock the skills DB to return 2 enabled skills. Send a chat request; assert `register_user_skills(user["id"], user["token"])` was called exactly once for that request, and the catalog block contains both skill names. Send a second request after mutating the mocked skill list to 1 skill; the catalog block now contains only that 1 skill (proves no caching).
  </behavior>
  <action>
    1. In `backend/app/routers/chat.py`, do NOT modify the top-of-file imports. Specifically: do NOT add `from app.services import tool_registry` at module top. All registry imports happen inside `if settings.tool_registry_enabled:` branches as lazy imports per PATTERNS.md "Shared Pattern A".

    2. Identify the `event_generator` async generator function (the SSE stream handler — search for `async def event_generator` or the route handler that yields SSE chunks). At the start of the generator, BEFORE the existing tools-array computation block, add the active-set initialization (gated on the flag):

       ```python
       # Phase 13 D-P13-05: per-request active set for tool_search dynamic activation.
       # Owner of lifetime = this event_generator scope. Closes when SSE stream ends.
       _registry_active_set: set[str] | None = None
       if settings.tool_registry_enabled:
           from app.services import tool_registry  # lazy — flag-off never imports
           _registry_active_set = tool_registry.make_active_set()
       ```

       Place this immediately after the existing `user_id`/`token` extraction inside the SSE `event_generator` (around chat.py line ~600) and BEFORE the existing tools-array block at line 617 (plan-checker warning F fix — the prior wording "near the start of the generator scope" was ambiguous). When applying the Edit, anchor on the unique line `user_id = current_user["id"]` (or the line immediately following it inside the generator body) so the executor places the active-set initialization at a deterministic spot. The flag-off path leaves `_registry_active_set = None` and never imports `tool_registry`.

    3. Splice 1 — tools array @ chat.py:617-623. Replace the existing block:
       ```python
       # BEFORE (current — keep this branch byte-identical via the else):
       all_tools = (
           tool_service.get_available_tools(web_search_enabled=web_search_effective)
           if settings.tools_enabled else []
       )
       available_tool_names = [t["function"]["name"] for t in all_tools]
       ```
       with:
       ```python
       # Phase 13 (TOOL-04): tools array from registry when flag is on; legacy path otherwise.
       if settings.tools_enabled and settings.tool_registry_enabled:
           # _registry_active_set was initialized above; safe-deref via assert.
           assert _registry_active_set is not None
           # Note: skills must be registered BEFORE build_llm_tools so deferred-loading
           # skills can be added to the active_set later via tool_search. Single-agent
           # path uses agent_allowed_tools=None; multi-agent path overrides below.
           from app.services.skill_catalog_service import register_user_skills
           await register_user_skills(user["id"], user["token"])
           all_tools = tool_registry.build_llm_tools(
               active_set=_registry_active_set,
               web_search_enabled=web_search_effective,
               sandbox_enabled=settings.sandbox_enabled,
               agent_allowed_tools=None,  # multi-agent path narrows this below
           )
       elif settings.tools_enabled:
           all_tools = tool_service.get_available_tools(web_search_enabled=web_search_effective)
       else:
           all_tools = []
       available_tool_names = [t["function"]["name"] for t in all_tools]
       ```

    4. Splice 2 — multi-agent catalog @ chat.py:649-656. Replace:
       ```python
       skill_catalog = await build_skill_catalog_block(user["id"], user["token"])
       messages = (
           [{"role": "system", "content": agent_def.system_prompt + skill_catalog}]
           + [{"role": m["role"], "content": m["content"]} for m in anonymized_history]
           + [{"role": "user", "content": anonymized_message}]
       )
       ```
       with:
       ```python
       if settings.tool_registry_enabled:
           # Multi-agent: filter catalog by agent.tool_names (D-P13-06 — field is tool_names,
           # NOT allowed_tools). Skills bypass; tool_search always-on.
           catalog_block = await tool_registry.build_catalog_block(
               agent_allowed_tools=agent_def.tool_names,
           )
           # Also narrow the LLM tools array to this agent's filter.
           all_tools = tool_registry.build_llm_tools(
               active_set=_registry_active_set,
               web_search_enabled=web_search_effective,
               sandbox_enabled=settings.sandbox_enabled,
               agent_allowed_tools=agent_def.tool_names,
           )
           available_tool_names = [t["function"]["name"] for t in all_tools]
       else:
           catalog_block = await build_skill_catalog_block(user["id"], user["token"])
       messages = (
           [{"role": "system", "content": agent_def.system_prompt + catalog_block}]
           + [{"role": m["role"], "content": m["content"]} for m in anonymized_history]
           + [{"role": "user", "content": anonymized_message}]
       )
       ```

    5. Splice 3 — single-agent catalog @ chat.py:719-727. Replace:
       ```python
       skill_catalog = await build_skill_catalog_block(user["id"], user["token"])
       messages = (
           [{"role": "system", "content": SYSTEM_PROMPT + pii_guidance + skill_catalog}]
           + [...]
       )
       ```
       with:
       ```python
       if settings.tool_registry_enabled:
           catalog_block = await tool_registry.build_catalog_block(agent_allowed_tools=None)
       else:
           catalog_block = await build_skill_catalog_block(user["id"], user["token"])
       messages = (
           [{"role": "system", "content": SYSTEM_PROMPT + pii_guidance + catalog_block}]
           + [{"role": m["role"], "content": m["content"]} for m in anonymized_history]
           + [{"role": "user", "content": anonymized_message}]
       )
       ```

    6. Tool-loop dispatch wiring for tool_search executor: locate the existing tool-loop in chat.py (`_run_tool_loop` or inline tool dispatch around chat.py:1000-1080). The tool_search executor (registered in 13-04) reads `context["active_set"]` and `context["agent_allowed_tools"]` from the `context` dict passed to executors. Find the existing `context` construction (search for `context = {` or similar) and EXTEND it (gated by the flag):
       ```python
       # Phase 13 D-P13-05: thread the per-request active_set + agent filter to executors.
       if settings.tool_registry_enabled:
           context["active_set"] = _registry_active_set
           context["agent_allowed_tools"] = (
               agent_def.tool_names if (settings.agents_enabled and agent_def is not None) else None
           )
       ```
       Place this AFTER the existing `context` dict is constructed but BEFORE it's passed to any tool executor / `_run_tool_loop`. The flag-off path does NOT add these keys (preserves byte-identical context dict shape for TOOL-05).

       NOTE: chat.py may construct multiple `context` dicts for different tool-loop call sites. Inspect the file and apply the addition at every site that dispatches tool calls when `settings.tools_enabled` is True. Use grep to enumerate: `grep -n "context = {" backend/app/routers/chat.py | head`. Each site must be patched the same way.

       IMPORTANT (plan-checker warning D fix — Option A is COMMITTED, not optional): the legacy `_run_tool_loop` looks up tools by name; when the flag is on, the lookup MUST consult `tool_registry._REGISTRY` FIRST so the registry's executor abstraction (including `tool_search` and any future skill/MCP executors) drives dispatch. Implementation:

       1. Locate `_run_tool_loop` (or the inline tool dispatch site) inside chat.py — search for `tool_service.execute_tool(` to find the dispatch location(s).
       2. Add a flag-gated prefix to the dispatch (≤ 15 LOC):
          ```python
          # Phase 13 D-P13-05: registry-first dispatch when flag is on.
          if settings.tool_registry_enabled and tool_name in tool_registry._REGISTRY:
              tool_def = tool_registry._REGISTRY[tool_name]
              tool_output = await tool_def.executor(arguments, user_id, context)
          else:
              tool_output = await tool_service.execute_tool(tool_name, arguments, user_id, context)
          ```
       3. The else-branch preserves byte-identical legacy behavior for TOOL-05 (flag-off goes straight to `tool_service.execute_tool`; flag-on but tool not in registry — e.g., a future native not yet adapter-wrapped — also falls through to legacy).

       The previously-listed "Option B" (a `tool_search` dispatch branch inside `tool_service.execute_tool`) is REJECTED — it bypasses the registry's executor abstraction and would force every future deferred-loaded source (skill, MCP) to also need a `tool_service.execute_tool` shim. Option A is the only path. Document the literal Option-A wording in the per-plan SUMMARY for traceability.

    7. Create `backend/tests/api/test_chat_tool_registry_flag.py` with the 6 behavior tests:
       - For Test 1 (snapshot): use `unittest.mock.patch("app.routers.chat.openrouter_service.stream_chat", new_callable=AsyncMock)` (or whichever client is used) to capture call kwargs. Run a chat request via FastAPI TestClient. Snapshot the captured `messages` + `tools` to a fixture file under `backend/tests/api/fixtures/chat_v1_1_reference.json` on first run; subsequent runs compare. The fixture MUST be captured with `TOOL_REGISTRY_ENABLED=false` and committed.
       - For Test 2 (subprocess no-import): use `subprocess.run([sys.executable, "-c", "..."])` to start a fresh Python with `TOOL_REGISTRY_ENABLED=false`, execute a chat request via TestClient, then dump `'app.services.tool_registry' in sys.modules` to stdout. Assert the output is `False`.
       - For Tests 3-6: use TestClient with appropriate env vars / monkeypatch on settings, mock the skills DB, mock OpenRouter, capture calls, assert on the captured message + tools array.

    8. Imports for the test file:
       ```python
       import json, os, subprocess, sys
       from pathlib import Path
       import pytest
       from unittest.mock import AsyncMock, patch
       from fastapi.testclient import TestClient
       from app.main import app
       ```

    9. The flag-off snapshot golden file path: `backend/tests/api/fixtures/chat_v1_1_reference.json`. Format: `{"messages": [...], "tools": [...]}`. Generate on first run if missing (use `pytest --update-snapshots` style — implement a `--regen` flag via `pytest -k snapshot --update`). For simpler v1: capture inside the test by running with the flag off, then assert by JSON comparison.

    10. PII / sandbox / web_search interactions: Tests 3-6 must explicitly set `pii_redaction_enabled=False`, `sandbox_enabled=False`, `tools_enabled=True` (and `agents_enabled` per test) so the captured payloads aren't perturbed by orthogonal features. The fixture captures the v1.1 reference under the SAME flag matrix.
  </action>
  <verify>
    <automated>cd backend &amp;&amp; source venv/bin/activate &amp;&amp; pytest tests/api/test_chat_tool_registry_flag.py -x -v &amp;&amp; pytest tests/api/test_chat_skill_catalog.py -v</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "from app.services import tool_registry" backend/app/routers/chat.py` returns at least 1, and EVERY occurrence is inside an `if settings.tool_registry_enabled:` block (verify by `grep -B1 "from app.services import tool_registry" backend/app/routers/chat.py | grep -c "tool_registry_enabled"` returns at least the same number as the import count).
    - `grep -c "build_skill_catalog_block" backend/app/routers/chat.py` returns at least 2 (the two else-branches preserving the legacy fallback).
    - `grep -c "tool_registry\.build_catalog_block\|tool_registry\.build_llm_tools\|tool_registry\.make_active_set" backend/app/routers/chat.py` returns at least 4 (one make_active_set + one build_llm_tools each in single + multi + the @617 splice + at least one build_catalog_block).
    - `grep -c "agent_def\.tool_names" backend/app/routers/chat.py` returns at least 2 (multi-agent splice for catalog filter + multi-agent splice for tools array filter).
    - `grep -c "agent_def\.allowed_tools" backend/app/routers/chat.py` returns 0 (PATTERNS.md correction — never use that name).
    - `pytest backend/tests/api/test_chat_tool_registry_flag.py -v` shows all 6 PASSED.
    - `pytest backend/tests/api/test_chat_skill_catalog.py -v` shows all existing tests passing (legacy flag-off path preserved).
    - `pytest backend/tests/unit/test_chat_router_phase5_imports.py backend/tests/unit/test_chat_router_phase5_wiring.py -v` shows no NEW failures (Phase 5 PII redaction wiring still intact).
    - With `TOOL_REGISTRY_ENABLED=false`: a TestClient chat request produces an OpenRouter call whose `messages` + `tools` kwargs match the v1.1 golden fixture exactly (`json.dumps(captured, sort_keys=True) == json.dumps(reference, sort_keys=True)`).
    - With `TOOL_REGISTRY_ENABLED=true`: the captured `messages[0]["content"]` contains `"## Available Tools"` AND `"Call \`tool_search\`"`.
    - With `TOOL_REGISTRY_ENABLED=true` and `agents_enabled=true` for a research agent with `tool_names=["search_documents", "kb_search"]`: the captured tools array contains exactly `tool_search` + the agent's allowed natives + any registered skills (no `query_database`, no other natives).
    - Subprocess no-import test: `python -c "import os; os.environ['TOOL_REGISTRY_ENABLED']='false'; from app.routers import chat; from fastapi.testclient import TestClient; from app.main import app; ...; print('app.services.tool_registry' in sys.modules)"` prints `False`.
    - `cd backend && source venv/bin/activate && python -c "from app.main import app; print('OK')"` prints OK.
    - Full backend unit test suite: `pytest backend/tests/unit/ -x --tb=short -q` shows no NEW failures vs the pre-Phase-13 baseline.
    - Frontend type check still passes: `cd frontend && npx tsc --noEmit` exits 0 (no frontend changes; sanity check).
  </acceptance_criteria>
  <done>chat.py has three flag-gated splices; active-set is created in event_generator and threaded through context dict; multi-agent uses agent.tool_names (NOT allowed_tools); flag-off snapshot test locks byte-identical behavior; flag-on tests verify catalog injection, agent filter, per-request reset, and skill freshness; subprocess no-import test confirms TOOL-05 invariant at the import level.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| chat.py event_generator → tool_registry | Per-request bridging of user identity + active_set + agent filter into the registry layer. |
| Active-set scope | Mutated by tool_search executor across the request; must NEVER leak to subsequent requests. |
| Multi-agent filter | `agent.tool_names` controls which natives + MCP tools an agent sees. Wrong field name (`allowed_tools` instead of `tool_names`) silently produces an empty allow list. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-13-05-01 | Information Disclosure | Active set leaks across requests (one user's discovered tools available to next user) | mitigate | `_registry_active_set` is a closure variable inside `event_generator`. New event_generator invocation = new active_set (created via `tool_registry.make_active_set()` which returns a fresh `set()`). Test 5 explicitly verifies per-request reset via two consecutive requests. |
| T-13-05-02 | Information Disclosure | Skill cache leaks across users | mitigate | `register_user_skills(user["id"], user["token"])` is called per-request with the CURRENT user's RLS-scoped client. The registry's first-write-wins prevents user A's skills from being kept when user B's request runs — but only if the registry is cleared between users. CRITICAL: `tool_registry._REGISTRY` is process-global; user B's `register_user_skills` will be silently no-op'd for skills already registered by user A. **Mitigation lock**: in this plan we accept that natives + tool_search persist (they're user-agnostic), and we document that skills register first-write-wins per name; if user A and user B both have a skill named "legal_review", user B sees user A's executor closure (which carries user B's `user_id` because the executor receives `user_id` per call from chat.py — verified by 13-03 Test 6, where the executor delegates to `ToolService.execute_tool("load_skill", {"name": skill_name}, user_id, ...)` and the user_id flows from the call site). The skill instructions retrieved by `_execute_load_skill` use the user_id passed at call time — RLS protects the read. Acceptable for v1.2; documented as a known constraint in 13-05-SUMMARY. |
| T-13-05-03 | Tampering | LLM crafts agent.tool_names override via prompt injection | accept | `agent_def.tool_names` is read from `agent_service.get_agent(...)` server-side from the configured agent registry — the LLM cannot mutate it. Prompt injection cannot expand the agent's allow list. |
| T-13-05-04 | Privacy invariant | Egress filter bypass through registry executors | mitigate | All registry executors that touch outbound LLMs flow through `tool_service.execute_tool` (natives) or `_execute_load_skill` (skills) — both already wrapped by chat.py's egress filter at lines 691-701 and 1040-1058. tool_search executor is in-process pure Python (no outbound calls). Phase 14 bridge and Phase 15 MCP will add their own egress hooks per their threat models. |
| T-13-05-05 | Denial of Service | register_user_skills DB query stalls chat | mitigate | Fail-soft from 13-03 returns silently on exception. Acceptable per-request latency: 5-20ms typical. If profiling later shows P95 > 100ms, add an opt-in cache (deferred per CONTEXT.md). |
| T-13-05-06 | Repudiation | Operator cannot tell whether a chat used registry path or legacy path | mitigate | Add a structured log line at the start of the registry-path branch: `logger.info("chat: tool_registry_enabled=%s flag-on=%s", settings.tool_registry_enabled, True)`. Visible in Railway logs and LangSmith traces. |
</threat_model>

<verification>
- All tests in `test_chat_tool_registry_flag.py` (6) and `test_agent_service_should_filter_tool.py` (7) pass.
- All pre-existing chat tests pass: `test_chat_skill_catalog.py`, `test_chat_router_phase5_*`, `test_phase5_integration.py`.
- Subprocess no-import test confirms `app.services.tool_registry not in sys.modules` when `TOOL_REGISTRY_ENABLED=false`.
- Snapshot test (Test 1) compares captured OpenRouter `messages` + `tools` against committed v1.1 reference fixture under flag-off — exact equality.
- `python -c "from app.main import app; print('OK')"` succeeds.
- `cd frontend && npx tsc --noEmit` passes (sanity).
- Manual smoke (production-style):
  1. `TOOL_REGISTRY_ENABLED=false uvicorn app.main:app --port 8000` → POST /chat → response identical to v1.1.
  2. `TOOL_REGISTRY_ENABLED=true uvicorn app.main:app --port 8000` → POST /chat → response includes catalog injection (verifiable via LangSmith trace of system prompt).
</verification>

<success_criteria>
- Three flag-gated splices in chat.py (tools array, multi-agent catalog, single-agent catalog) all use lazy `from app.services import tool_registry` imports.
- `_registry_active_set = tool_registry.make_active_set()` created at start of event_generator (flag-on only), threaded through `context` dict to executors.
- Multi-agent path filters via `agent.tool_names` (NOT `allowed_tools`) per PATTERNS.md critical finding.
- `should_filter_tool(tool_def, agent)` predicate codifies D-P13-06 on agent_service.py.
- Byte-identical snapshot test locks TOOL-05 invariant: with flag off, system prompt and tools array exactly match v1.1 reference.
- Subprocess no-import test confirms `tool_registry` module is never imported when flag is off.
- Per-request active-set reset verified by integration test (TOOL-03).
- Per-request skill freshness verified by integration test (no caching).
- TOOL-01: ✓ catalog injected when flag on.
- TOOL-04: ✓ registry serves both single-agent and multi-agent paths.
- TOOL-05: ✓ byte-identical fallback verified at both unit (snapshot) and import (subprocess) levels.
- D-P13-06: ✓ `agent.tool_names` field used; skill bypass + tool_search always-on enforced.
- All pre-Phase-13 chat tests still pass.
</success_criteria>

<output>
After completion, create `.planning/phases/13-unified-tool-registry-tool-search-meta-tool/13-05-SUMMARY.md` summarizing:
- Splices applied in chat.py (line numbers + summary of each)
- New helper signature: `should_filter_tool(tool_def, agent)`
- Active-set lifecycle (create → mutate via tool_search → reset on next request)
- Tool-loop dispatch wiring choice (Option A: extend loop lookup vs Option B: shim in tool_service.execute_tool — record which was used and why)
- Snapshot fixture path and what it captures
- Test count: 6 integration + 7 unit
- Known constraint: skills register first-write-wins by name across users; mitigation = RLS at call time
- Final assertion: TOOL-01, TOOL-04, TOOL-05 all satisfied; full v1.2 Phase 13 functionality online when TOOL_REGISTRY_ENABLED=true
</output>
