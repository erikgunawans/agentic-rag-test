# Phase 13: Unified Tool Registry & `tool_search` Meta-Tool — Pattern Map

**Mapped:** 2026-05-02
**Files analyzed:** 7 (1 NEW, 6 PATCH)
**Analogs found:** 7 / 7 — all targets have a strong, in-repo precedent.

## File Classification

| New/Modified File | Status | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|--------|------|-----------|----------------|---------------|
| `backend/app/services/tool_registry.py` | NEW | service (registry/dispatcher + prompt-block formatter) | request-response (table render) + in-process pub-sub (active set) | `backend/app/services/skill_catalog_service.py` (block render) + `backend/app/services/tool_service.py` (TOOL_DEFINITIONS + dispatch) | exact (composite — two analogs cover the two halves) |
| `backend/app/services/tool_service.py` | PATCH (additive only) | service | request-response | `backend/app/services/tool_service.py` itself (Phase 10 `execute_code` add — line 35 list extension + dispatch branch around line 387) | exact (precedent in same file) |
| `backend/app/routers/chat.py` | PATCH (flag-gated branches at L408 / L437 / L491) | controller (FastAPI router) | event-driven (SSE) + request-response | Phase 8 catalog-block injection at `chat.py:651` and `chat.py:722` (current `build_skill_catalog_block` call site) | exact |
| `backend/app/services/agent_service.py` | PATCH (add `should_filter_tool` helper) | service | request-response | `agent_service.get_agent_tools` (line 135-141) — current per-agent filter helper | exact |
| `backend/app/services/skill_catalog_service.py` | PATCH (no-op when flag on; legacy stays for flag-off) | service | request-response | itself — keep as-is for flag-off byte-identical fallback (TOOL-05) | exact (no rewrite — leave function body untouched) |
| `backend/app/config.py` | PATCH (one new field) | config | n/a | `pii_redaction_enabled` (removed, see comment line 95-97), `agents_enabled` (line 69), `sandbox_enabled` (line 74) — same single-line `bool = False` Pydantic Settings pattern | exact |
| `backend/app/models/tools.py` | PATCH (planner discretion — may add `ToolDefinition` here OR co-locate in `tool_registry.py`) | model | n/a | `ToolCallRecord` / `ToolCallSummary` shape (lines 16-66) | exact |

---

## Pattern Assignments

### `backend/app/services/tool_registry.py` (NEW — service, request-response)

**Composite analog:** `skill_catalog_service.py` for the catalog-block formatter half + `tool_service.py` for the registration/dispatch half. The two halves combine into one ~250-400 LOC module per CONTEXT.md §Domain.

#### Half A — module header + fail-soft pattern (analog: `skill_catalog_service.py:1-24`)

Copy the docstring discipline (decisions enforced + fail-soft note), the `from __future__ import annotations`, and the module-level logger.

```python
"""TOOL-01..06 / D-P13-01..06: unified tool registry + tool_search meta-tool.

Owns the in-process registry of native + skill + MCP tools, the
`tool_search(keyword, regex)` matcher, the `build_catalog_block(...)`
formatter that replaces Phase 8's `build_skill_catalog_block` when
TOOL_REGISTRY_ENABLED=true, and the per-request active-set state.

Decisions enforced:
  - D-P13-01: adapter wrap. Native executors delegate to ToolService.execute_tool.
  - D-P13-02: skills register as first-class tools.
  - D-P13-03: single unified ## Available Tools markdown table.
  - D-P13-04: tool_search elevated to meta-callout above the table.
  - D-P13-05: two-param schema {keyword: str | None, regex: str | None}.
  - D-P13-06: multi-agent filter (skill bypass, tool_search always-on).

Fail-soft: any DB exception during skill registration logs and continues
with the natives-only catalog (chat must never break on registry errors).
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)
```

#### Half B — `ToolDefinition` Pydantic model (analog: `models/tools.py:16-31` `ToolCallRecord`)

```python
# from app.models.tools.py:16-31 — copy this Pydantic model shape.
class ToolCallRecord(BaseModel):
    tool: str
    input: dict
    output: dict | str
    error: str | None = None
    tool_call_id: str | None = None
    status: Literal["success", "error", "timeout"] | None = None
```

Translate to the shape locked in CONTEXT.md §Decisions / Discretion:

```python
from typing import Awaitable, Callable, Literal
from pydantic import BaseModel, ConfigDict

class ToolDefinition(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)  # for Callable
    name: str
    description: str
    schema: dict   # OpenAI tool-call shape: {"type":"function", "function": {...}}
    source: Literal["native", "skill", "mcp"]
    loading: Literal["immediate", "deferred"]
    executor: Callable[..., Awaitable[dict | str]]
```

#### Half C — `register()` API + backing dict (no analog — first writer wins is new behavior, but follow the in-process singleton pattern from `tool_service.py:151` `tool_service = ToolService()`)

```python
# Backing store: single dict[str, ToolDefinition], first-write-wins on collision.
_REGISTRY: dict[str, "ToolDefinition"] = {}

def register(
    name: str,
    description: str,
    schema: dict,
    source: Literal["native", "skill", "mcp"],
    loading: Literal["immediate", "deferred"],
    executor: Callable,
) -> None:
    """Register a tool. Idempotent on (name, source) — duplicate logs warn + ignored."""
    if name in _REGISTRY:
        logger.warning("tool_registry: duplicate name=%s source=%s — ignored", name, source)
        return
    _REGISTRY[name] = ToolDefinition(
        name=name, description=description, schema=schema,
        source=source, loading=loading, executor=executor,
    )
```

#### Half D — `build_catalog_block(...)` formatter (analog: `skill_catalog_service.py:29-112`)

Reuse the pipe-sanitizing row formatter, the alphabetical sort, and the truncation footer pattern verbatim — only widen the columns.

**Header constant (analog: `skill_catalog_service.py:29-35`)**

```python
# skill_catalog_service.py:29-35 — pattern to copy and extend
_CATALOG_HEADER = (
    "\n\n## Your Skills\n"
    "Call `load_skill` with the skill name when the user's request clearly\n"
    "matches a skill. Only load a skill when there's a strong match.\n\n"
    "| Skill | Description |\n"
    "|-------|-------------|"
)
```

Phase 13 version (D-P13-03 + D-P13-04):

```python
_CATALOG_HEADER = (
    "\n\n## Available Tools\n"
    "Call `tool_search` with a keyword or regex query when you need a tool not listed below.\n"
    "Only call a tool when its description clearly matches the user's request.\n\n"
    "| Tool | Source | Description |\n"
    "|------|--------|-------------|"
)
```

**Pipe-sanitization row formatter (verbatim from `skill_catalog_service.py:45-51`)**

```python
def _format_table_row(name: str, description: str) -> str:
    safe_desc = (description or "").replace("|", "\\|").replace("\n", " ").strip()
    safe_name = (name or "").replace("|", "\\|").strip()
    return f"| {safe_name} | {safe_desc} |"
```

Phase 13 widens to three columns and adds D-P13-discretion 80-char description truncation:

```python
_DESC_MAX = 80  # Discretion: 80-char hard truncate, predictable ~25 tokens/row.

def _format_table_row(name: str, source: str, description: str) -> str:
    desc = (description or "").replace("|", "\\|").replace("\n", " ").strip()
    if len(desc) > _DESC_MAX:
        desc = desc[: _DESC_MAX - 1] + "…"  # U+2026 single ellipsis
    return f"| {name.replace('|', '\\|').strip()} | {source} | {desc} |"
```

**Truncation footer (analog: `skill_catalog_service.py:38-42`, D-P8-07)**

```python
# skill_catalog_service.py:38-42 — Discretion §Catalog overflow reuses this exact pattern.
_TRUNCATION_FOOTER = (
    "Showing 20 enabled skills. More are available — "
    "call load_skill with any skill name to load it directly."
)
```

Phase 13 version (cap = 50 per CONTEXT.md §Discretion):

```python
_CAP = 50
_TRUNCATION_FOOTER = (
    "Showing 50 of {n} tools. Call tool_search with a keyword to find more."
)
```

**Render function shape (analog: `skill_catalog_service.py:54-112`)**

```python
async def build_catalog_block(
    *,
    user_id: str,
    token: str,
    agent_allowed_tools: list[str] | None = None,
) -> str:
    """Return the '## Available Tools' system-prompt block, or '' when registry empty.

    D-P13-06: when agent_allowed_tools is provided, post-filter via the
    should_filter_tool predicate (skill bypass, tool_search always-on).
    Always-excludes tool_search from the rendered table (D-P13-04 — meta-callout
    appears in header line, never as a table row).
    """
    # 1. fail-soft skill registration (per-request DB query — Discretion §Skill timing)
    # 2. apply filter predicate
    # 3. alphabetical sort, cap at 50, render rows
    # 4. append truncation footer when N > 50
```

#### Half E — `tool_search(keyword, regex)` matcher (D-P13-05)

No direct analog in repo. Build from primitives. Schema construction mirrors `tool_service.TOOL_DEFINITIONS` entry shape (lines 35-72).

```python
import re

def tool_search(*, keyword: str | None = None, regex: str | None = None) -> dict:
    """D-P13-05: keyword (substring, case-insensitive) OR regex (re.search, IGNORECASE).

    Both null → error. Both passed → regex wins (logged as a hint).
    Returns: {"matches": [<full openai schema>...], "hint": str | None}
    Side effect: matched tools added to active set for the rest of the request.
    """
    if keyword is None and regex is None:
        return {"error": "either keyword or regex required"}
    hint = None
    if keyword is not None and regex is not None:
        hint = "regex wins when both keyword and regex are passed"
    # ... matcher loop, top-10 cap, ranking: name match outranks desc; longer span > shorter
```

#### Half F — Active-set state (Discretion §Active-set storage)

Closure variable scoped to `chat.py:event_generator()`. The registry exposes a small accessor; **NO `contextvars`**, **NO `RequestContext`**.

```python
# Convention: caller (chat.py) creates a per-request set; passes it into build_catalog_block
# and tool_search. Lifetime = until SSE stream closes.
def make_active_set() -> set[str]:
    """Construct an empty per-request active set. Caller owns lifetime."""
    return set()
```

#### Half G — `tool_search` self-registration at module load (always-on; D-P13-04)

```python
# At module bottom: register tool_search itself as source="native", loading="immediate".
register(
    name="tool_search",
    description="Search the registry for tools by keyword or regex.",
    schema={
        "type": "function",
        "function": {
            "name": "tool_search",
            "description": "Find tools by keyword (substring) or regex against name+description.",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": ["string", "null"], "description": "Plain substring; case-insensitive."},
                    "regex": {"type": ["string", "null"], "description": "Python re.search pattern; case-insensitive."},
                },
                "required": [],
            },
        },
    },
    source="native",
    loading="immediate",
    executor=lambda **kw: tool_search(**kw),  # synchronous, but wrap with async if needed
)
```

---

### `backend/app/services/tool_service.py` (PATCH — additive only)

**Analog: itself.** Phase 10 already demonstrated the additive splice pattern (Phase 10 commits `6162` and `6164` per session memory: "Added execute_code tool definition to TOOL_DEFINITIONS" and "execute_code dispatch branch wired into execute_tool() dispatch switch"). Phase 13 does **not** repeat that pattern — instead it wires a one-time bootstrap loop that wraps the existing list (D-P13-01 adapter wrap; existing 1,283 LOC stays untouched).

**Splice point: bootstrap hook at module bottom (after `ToolService` class, ~line 1283)**

```python
# Existing TOOL_DEFINITIONS list (line 35-360). DO NOT MODIFY.
TOOL_DEFINITIONS = [
    {"type": "function", "function": {"name": "search_documents", ...}},
    # ... 13 more entries, including Phase 8 load_skill / save_skill / read_skill_file
]

# Existing dispatch (line 387-920+). DO NOT MODIFY.
class ToolService:
    @traced(name="execute_tool")
    async def execute_tool(self, name, arguments, user_id, context=None, *,
                           registry=None, token=None, stream_callback=None) -> dict:
        if name == "search_documents":
            return await self._execute_search_documents(...)
        elif name == "query_database":
            ...
```

**ADD at the end of the module (or in a tiny startup hook in `app/main.py`):**

```python
# Phase 13 D-P13-01 adapter wrap: register every native tool exactly once.
# Gated by settings.tool_registry_enabled — when false, this block is a no-op
# (and chat.py never imports tool_registry, see TOOL-05 byte-identical fallback).
def _register_natives_with_registry() -> None:
    if not settings.tool_registry_enabled:
        return
    from app.services import tool_registry  # lazy import — flag-off skips entirely
    _svc = ToolService()  # the singleton already lives at chat.py:151; this is a fresh wrapper
    for tool in TOOL_DEFINITIONS:
        fn = tool["function"]
        name = fn["name"]
        # Closure captures the name so the executor calls the right dispatch branch.
        async def _executor(arguments, user_id, context, *, _name=name, **kw):
            return await _svc.execute_tool(_name, arguments, user_id, context, **kw)
        tool_registry.register(
            name=name,
            description=fn["description"],
            schema=tool,
            source="native",
            loading="immediate",
            executor=_executor,
        )

_register_natives_with_registry()
```

**Reference for the existing `get_available_tools` (no edit needed; chat.py replaces the call site, not this method):**

```python
# tool_service.py:391-413 — leave as-is. chat.py branches on settings.tool_registry_enabled
# and calls into tool_registry.* instead.
def get_available_tools(self, *, web_search_enabled: bool = True) -> list[dict]:
    tools = []
    for tool in TOOL_DEFINITIONS:
        name = tool["function"]["name"]
        if name == "web_search":
            if not web_search_enabled:
                continue
            if not settings.tavily_api_key:
                continue
        elif name == "execute_code":
            if not settings.sandbox_enabled:
                continue
        tools.append(tool)
    return tools
```

---

### `backend/app/routers/chat.py` (PATCH — three flag-gated branches)

**Analog: itself.** Three current call sites need an `if settings.tool_registry_enabled:` branch. The flag-off arm of every branch is byte-for-byte unchanged from today (TOOL-05 invariant).

#### Splice 1 — Catalog injection in MULTI-AGENT path (chat.py:649-656)

**Current shape (chat.py:648-656):**

```python
# Phase 8 D-P8-03: append the enabled-skills catalog. Returns "" when
# the user has 0 enabled skills (D-P8-02), so this is byte-identical
# to pre-Phase-8 behavior in that case.
skill_catalog = await build_skill_catalog_block(user["id"], user["token"])
messages = (
    [{"role": "system", "content": agent_def.system_prompt + skill_catalog}]
    + [{"role": m["role"], "content": m["content"]} for m in anonymized_history]
    + [{"role": "user", "content": anonymized_message}]
)
```

**Phase 13 patch shape:**

```python
if settings.tool_registry_enabled:
    from app.services import tool_registry  # lazy — flag-off never imports
    catalog_block = await tool_registry.build_catalog_block(
        user_id=user["id"],
        token=user["token"],
        agent_allowed_tools=agent_def.tool_names,  # D-P13-06 multi-agent filter
    )
else:
    catalog_block = await build_skill_catalog_block(user["id"], user["token"])
messages = (
    [{"role": "system", "content": agent_def.system_prompt + catalog_block}]
    + [{"role": m["role"], "content": m["content"]} for m in anonymized_history]
    + [{"role": "user", "content": anonymized_message}]
)
```

#### Splice 2 — Catalog injection in SINGLE-AGENT path (chat.py:719-727)

**Current shape (chat.py:719-727):**

```python
# Phase 8 D-P8-01: append enabled-skills catalog. Returns "" when
# the user has 0 enabled skills (D-P8-02 SC#5-style invariant —
# behavior identical to pre-Phase-8 when feature unused).
skill_catalog = await build_skill_catalog_block(user["id"], user["token"])
messages = (
    [{"role": "system", "content": SYSTEM_PROMPT + pii_guidance + skill_catalog}]
    + [{"role": m["role"], "content": m["content"]} for m in anonymized_history]
    + [{"role": "user", "content": anonymized_message}]
)
```

**Phase 13 patch:** same `if settings.tool_registry_enabled` split. Single-agent passes `agent_allowed_tools=None` so no filter is applied.

#### Splice 3 — Tools array passed to LLM (chat.py:617-623)

**Current shape (chat.py:617-623):**

```python
# ADR-0008: compute available tool catalog up front so it can be
# fed to the orchestrator classifier and the tool loop.
all_tools = (
    tool_service.get_available_tools(web_search_enabled=web_search_effective)
    if settings.tools_enabled else []
)
available_tool_names = [t["function"]["name"] for t in all_tools]
```

**Phase 13 patch:** when flag is on, build `all_tools` from `tool_registry` (immediate-loading natives + active-set), keeping the `web_search`/`execute_code` toggles applied. Active set is empty at request start; `tool_search` adds to it mid-loop.

```python
if settings.tools_enabled and settings.tool_registry_enabled:
    from app.services import tool_registry
    active_set = tool_registry.make_active_set()  # closure-scoped per request
    all_tools = tool_registry.build_llm_tools(
        active_set=active_set,
        web_search_enabled=web_search_effective,
        sandbox_enabled=settings.sandbox_enabled,
        agent_allowed_tools=None,  # set later inside multi-agent branch
    )
elif settings.tools_enabled:
    all_tools = tool_service.get_available_tools(web_search_enabled=web_search_effective)
else:
    all_tools = []
available_tool_names = [t["function"]["name"] for t in all_tools]
```

**Imports to add at top of chat.py (line 15 area):**

```python
# Existing line 15:
from app.services.skill_catalog_service import build_skill_catalog_block
# ADD (NOT replace — flag-off path still needs build_skill_catalog_block):
# tool_registry is imported lazily inside each branch (see splices above) so
# flag-off path doesn't import it at all (TOOL-05 byte-identical fallback).
```

---

### `backend/app/services/agent_service.py` (PATCH — add `should_filter_tool` helper)

**Analog: `agent_service.py:135-141` `get_agent_tools`** — same one-line list-comprehension filter pattern.

**Existing helper (lines 135-141):**

```python
@traced(name="get_agent_tools")
def get_agent_tools(agent: AgentDefinition, all_tools: list[dict]) -> list[dict]:
    """Filter tools to only those the agent is allowed to use."""
    return [
        t for t in all_tools
        if t["function"]["name"] in agent.tool_names
    ]
```

**Phase 13 addition (D-P13-06):** add a `should_filter_tool` predicate beside `get_agent_tools`. Reuses `agent.tool_names` (the existing `allowed_tools` analog field on `AgentDefinition`).

```python
@traced(name="should_filter_tool")
def should_filter_tool(tool_def, agent: AgentDefinition) -> bool:
    """D-P13-06: predicate for catalog + tool_search result filtering.

    Returns True when the tool MUST be retained (skill bypass, tool_search
    always-on, MCP/native gated by name). Returns False to filter out.
    """
    # Skill bypass: skills are user-scoped, not agent-scoped.
    if tool_def.source == "skill":
        return True
    # tool_search is always-on regardless of agent.
    if tool_def.name == "tool_search":
        return True
    # Native + MCP tools must be in the agent's allowed list.
    return tool_def.name in agent.tool_names
```

**Note:** CONTEXT.md uses `allowed_tools` as the prose name; the actual field on `AgentDefinition` (models/agents.py:8) is `tool_names`. Plans MUST refer to it as `agent.tool_names` — there is no rename in this phase.

---

### `backend/app/services/skill_catalog_service.py` (PATCH — leave function body untouched)

**Analog: itself.** Per CONTEXT.md §Specifics: "do NOT delete `skill_catalog_service.py`". Phase 13 leaves `build_skill_catalog_block` unmodified so flag-off path is byte-identical (TOOL-05).

**Optional addition** (CONTEXT.md §Specifics §Skill registration): a small registration helper that the registry's `build_catalog_block` calls per-request to push enabled skills into `_REGISTRY` as `source="skill"`. This sits next to the existing function:

```python
# skill_catalog_service.py — current lines 54-112: build_skill_catalog_block
# DO NOT MODIFY. Stays as the flag-off catalog builder.

# Phase 13 NEW helper (only called when settings.tool_registry_enabled=true)
async def register_user_skills(user_id: str, token: str) -> None:
    """D-P13-02: register each enabled skill as a first-class tool.

    Per-request DB query (CONTEXT.md §Discretion §Skill registration timing) —
    no caching. Skill executor wraps the existing Phase 8 load_skill flow.
    """
    if not token:
        return
    try:
        client = get_supabase_authed_client(token)
        result = (
            client.table("skills")
            .select("name, description")
            .eq("enabled", True)
            .order("name")
            .execute()
        )
        rows = result.data or []
    except Exception as e:
        logger.warning("register_user_skills failed for user_id=%s: %s", user_id, e)
        return
    from app.services import tool_registry
    for row in rows:
        # Build a parameterless schema (D-P13-02: skills register with schema={}).
        # Executor delegates to the existing _execute_load_skill path on tool_service.
        tool_registry.register(
            name=row["name"],
            description=row.get("description") or "",
            schema={"type": "function",
                    "function": {"name": row["name"],
                                 "description": row.get("description") or "",
                                 "parameters": {"type": "object", "properties": {}, "required": []}}},
            source="skill",
            loading="deferred",
            executor=_make_skill_executor(row["name"]),
        )
```

**Reuse the existing fail-soft pattern (skill_catalog_service.py:69-90):**

```python
if not token:
    return ""
try:
    client = get_supabase_authed_client(token)
    result = (
        client.table("skills")
        .select("name, description")
        .eq("enabled", True)
        .order("name")
        .limit(21)
        .execute()
    )
    rows = result.data or []
except Exception as e:
    logger.warning(
        "build_skill_catalog_block failed for user_id=%s: %s", user_id, e
    )
    return ""
```

---

### `backend/app/config.py` (PATCH — single new field)

**Analog: `agents_enabled`, `sandbox_enabled` (config.py:69, 74).** Phase 13 adds **one** field next to these flags.

**Existing pattern (config.py:69-74, 82):**

```python
# Sub-agents (Module 8)
agents_enabled: bool = False
agents_orchestrator_model: str = ""

# Phase 10: Code Execution Sandbox (SANDBOX-01..06, 08; D-P10-01..D-P10-17)
# SANDBOX-05 / D-P10: gate the execute_code tool. Default OFF — opt-in per Railway env.
sandbox_enabled: bool = False
```

**Phase 13 addition (place it grouped with `tools_enabled` at line 65 OR with the v1.2 phase-13 group — planner's call):**

```python
# Phase 13 (TOOL-01..06; D-P13-01..D-P13-06): Unified Tool Registry & tool_search.
# Default OFF — when False, chat.py + tool_service.py skip importing the registry
# entirely (TOOL-05 byte-identical fallback). Env var: TOOL_REGISTRY_ENABLED.
tool_registry_enabled: bool = False
```

**No model_validator needed** (unlike `_validate_local_embedding` at line 138 — that example is the pattern to copy ONLY if the planner adds dependent constraints; v1.2 has none).

---

### `backend/app/models/tools.py` (PATCH — possibly add `ToolDefinition`)

**Analog: same file, lines 16-66 (`ToolCallRecord`, `ToolCallSummary`).**

**Existing shape (tools.py:16-31):**

```python
class ToolCallRecord(BaseModel):
    """Persisted record of a single tool execution.

    Phase 11 additions (D-P11-08):
      - tool_call_id: OpenAI tool-call UUID — required for new rows; legacy
        rows have None and fall back to flat history reconstruction (D-P11-03).
      - status: success / error / timeout. Sandbox calls derive from
        Phase 10 tool_result error_type/exit_code; non-sandbox calls use
        success or error.
    """
    tool: str
    input: dict
    output: dict | str
    error: str | None = None
    tool_call_id: str | None = None
    status: Literal["success", "error", "timeout"] | None = None
```

**Discretion (CONTEXT.md):** planner picks ONE of:
- Place `ToolDefinition` here (more discoverable; consistent with `ToolCallRecord`/`ToolCallSummary`).
- Co-locate inside `tool_registry.py` (more cohesive — model + behavior together; CONTEXT.md notes "placing it in `models/tools.py` is more discoverable").

If co-located in `models/tools.py`, append:

```python
from typing import Awaitable, Callable, Literal

class ToolDefinition(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    name: str
    description: str
    schema: dict
    source: Literal["native", "skill", "mcp"]
    loading: Literal["immediate", "deferred"]
    executor: Callable[..., Awaitable[dict | str]]
```

---

## Shared Patterns

### A. Feature-flag gating with byte-identical fallback (TOOL-05 invariant)

**Source:** `config.py:69, 74` (`agents_enabled`, `sandbox_enabled`) + `chat.py:625` (`if settings.agents_enabled:` branch).

**Apply to:** every Phase-13 splice in `chat.py` and `tool_service.py`. The flag-off arm MUST be character-identical to today's behavior (no extra imports, no extra DB calls, no extra log lines).

```python
# chat.py:625 — pattern to copy.
if settings.agents_enabled:
    # --- Multi-agent path ---
else:
    # --- Single-agent path (Module 7 behavior) ---
```

**Phase 13 form:**

```python
if settings.tool_registry_enabled:
    from app.services import tool_registry  # lazy — flag-off never imports
    # ... new branch
else:
    # ... existing call (build_skill_catalog_block, tool_service.get_available_tools, ...)
```

The lazy `from app.services import tool_registry` inside the `if` block means the registry module is never imported when the flag is off — guaranteeing **zero startup overhead** for v1.1 deployments (CONTEXT.md §D-P13-01 explicit requirement).

### B. Pipe-sanitizing markdown row formatter

**Source:** `skill_catalog_service.py:45-51`.

**Apply to:** `tool_registry.build_catalog_block`, any future formatter that emits user-controlled strings into a markdown table.

```python
def _format_table_row(name: str, description: str) -> str:
    safe_desc = (description or "").replace("|", "\\|").replace("\n", " ").strip()
    safe_name = (name or "").replace("|", "\\|").strip()
    return f"| {safe_name} | {safe_desc} |"
```

### C. Per-request RLS-scoped DB query (no cache)

**Source:** `skill_catalog_service.py:73-83`.

**Apply to:** registry's per-request skill registration (`register_user_skills`). CONTEXT.md §Discretion §Skill registration timing locks this as the chosen pattern.

```python
client = get_supabase_authed_client(token)
result = (
    client.table("skills")
    .select("name, description")
    .eq("enabled", True)
    .order("name")
    .limit(21)  # registry version drops this limit; catalog cap = 50 done in formatter
    .execute()
)
rows = result.data or []
```

### D. Fail-soft on DB errors (chat must never break)

**Source:** `skill_catalog_service.py:85-90`.

**Apply to:** every `await client.table(...).execute()` inside the registry. Any exception logs at WARNING and continues with whatever was already registered.

```python
except Exception as e:
    logger.warning(
        "build_skill_catalog_block failed for user_id=%s: %s", user_id, e
    )
    return ""
```

### E. `@traced` decorator for service entry-points

**Source:** `tool_service.py:415` (`@traced(name="execute_tool")`), `agent_service.py:127, 144` (`@traced(name="get_agent")`, `@traced(name="classify_intent")`).

**Apply to:** `tool_registry.tool_search`, `tool_registry.build_catalog_block`, `agent_service.should_filter_tool`. Standard observability hook.

```python
from app.services.tracing_service import traced

@traced(name="tool_search")
async def tool_search(*, keyword=None, regex=None) -> dict:
    ...
```

### F. Pydantic Settings field with default-False (opt-in)

**Source:** `config.py:69, 74, 130` (`agents_enabled: bool = False`, `sandbox_enabled: bool = False`, `pii_missed_scan_enabled: bool = True`).

**Apply to:** `tool_registry_enabled: bool = False`. Convention: NEW v1.x features ship default-OFF; flip after one full milestone of in-prod observation.

### G. Egress filter respect (privacy invariant — NON-NEGOTIABLE)

**Source:** `backend/app/services/redaction/egress.py` + `chat.py:691-701, 1040-1058` (pre-flight egress filter on stream_response and tool calls).

**Apply to:** every registry executor that may eventually call a cloud LLM (skill executors, future MCP tools, hypothetical future `summarize_with_llm`). The native-adapter wrap inherits today's egress filter automatically because the executor calls back into `ToolService.execute_tool` which is already inside the `chat.py` egress-filtered envelope. Skill executors that talk to OpenRouter via `_llm_provider_client` inherit the same envelope. **Bridge calls (Phase 14) and MCP outgoing (Phase 15) MUST be added to egress.py separately.**

```python
# chat.py:691-701 — egress pattern. Registry executors are wrapped by this same envelope
# at the chat.py call site, so the registry itself does NOT need to import egress_filter.
if redaction_on:
    payload = json.dumps(messages, ensure_ascii=False)
    egress_result = egress_filter(payload, registry, None)
    if egress_result.tripped:
        logger.warning("egress_blocked event=egress_blocked feature=stream_response_branch_a ...")
        raise EgressBlockedAbort("branch A stream_response egress blocked")
```

### H. ToolCallRecord shape compatibility (Phase 11 D-P11-08)

**Source:** `models/tools.py:16-31`.

**Apply to:** every registry executor's return value. The 50 KB head-truncate validator on `output` runs automatically when `ToolCallRecord(...)` is constructed — registry executors must not pre-truncate or duplicate the marker. The chat.py `_run_tool_loop` (out-of-scope here) wraps every executor return into a `ToolCallRecord`, so registry executors can return `dict | str` directly and the truncation happens "for free".

---

## No Analog Found

| File / Concept | Why no analog | Recommendation |
|----------------|---------------|----------------|
| `tool_search()` ranking algorithm (name-match-outranks-description, longer-span-outranks-shorter) | No prior repo code does fuzzy/regex tool discovery | Follow CONTEXT.md §Discretion §`tool_search` result cap verbatim — top 10, name > desc, ties alphabetical. Implement as a simple scoring loop. |
| Per-request active-set lifecycle (closure-scoped to `event_generator`) | No prior repo code uses closure-scoped per-request state | CONTEXT.md §Discretion §Active-set storage explicitly rules out `contextvars` and `RequestContext`. Use a plain `set[str]` defined inside `event_generator`, passed by reference into `tool_registry.build_llm_tools` and `tool_registry.tool_search`. Lifetime = SSE stream close. |
| First-write-wins collision semantics on `register()` | New behavior | Log at WARNING and ignore the duplicate (CONTEXT.md §Deferred mentions source-prefixed names as a future collision-safety upgrade). |

---

## Metadata

**Analog search scope:**
- `backend/app/services/` (registry, dispatch, agent helpers)
- `backend/app/models/` (Pydantic shapes)
- `backend/app/routers/chat.py` (catalog injection points)
- `backend/app/config.py` (feature-flag pattern)
- `backend/app/services/redaction/egress.py` (privacy invariant — referenced, not edited)

**Files scanned:** 7 primary analogs (all read in full or via targeted offset/limit slices).

**Not scanned (out of scope, ruled out by CONTEXT.md):**
- `backend/app/services/sandbox_service.py` (Phase 14 territory — bridge stubs)
- MCP-related modules (Phase 15)
- `frontend/src/**` (backend-only phase per CONTEXT.md §Domain)

**Key insight:** the unique innovation in Phase 13 is the **registry data structure itself + `tool_search` matcher**. Every other concern (catalog rendering, feature flag gating, RLS scoping, fail-soft, `@traced`, ToolCallRecord shape) has a strong, recent precedent in the repo (Phases 8, 10, 11). Planner can copy patterns directly without inventing new conventions.

**Pattern extraction date:** 2026-05-02
