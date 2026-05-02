"""Phase 13: Unified Tool Registry & tool_search Meta-Tool — registry foundation.

Plan 13-01 (TOOL-04, TOOL-06; D-P13-01..D-P13-06).
Plan 13-04 (TOOL-02, TOOL-03): tool_search meta-tool added at the bottom.

Single source of truth for native tools, skills (Phase 8), and MCP tools (future).
This module owns the in-process backing store and the system-prompt formatter
that chat.py (Plan 13-05) will switch over to when `settings.tool_registry_enabled`
is True. When the flag is False, neither chat.py nor tool_service.py imports
this module, preserving the TOOL-05 byte-identical pre-Phase-13 behavior.

Decisions enforced:
  - D-P13-01: native tools register via adapter wrap (Plan 13-02 calls
    `register(...)` for each entry in tool_service.TOOL_DEFINITIONS).
  - D-P13-02: skills register as first-class tools (Plan 13-03 calls
    `register(...)` per enabled skill with schema={} parameterless).
  - D-P13-03: single unified `## Available Tools` table with Tool / Source /
    Description columns. Cap 50 rows, alphabetical by name, 80-char description
    truncate, pipe-sanitized.
  - D-P13-04: `tool_search` is in `_REGISTRY` (Plan 13-04 self-registers it)
    but EXCLUDED from rendered rows — only the meta-callout line in
    `_CATALOG_HEADER` advertises it.
  - D-P13-05: tool_search matcher implementation lives in Plan 13-04.
  - D-P13-06: agent filter — skill bypass + tool_search always-on; native and
    mcp tools gated by name in `agent.tool_names`. Encoded both at the
    LLM-tools-array layer (`build_llm_tools`) and at the catalog-table layer
    (`_passes_agent_filter`).

First-write-wins on duplicate `register()` (PATTERNS.md "No Analog Found"):
later modules cannot clobber natives. Logged at WARNING for operator visibility.
"""
from __future__ import annotations

import logging
from typing import Awaitable, Callable

from app.models.tools import ToolDefinition
from app.services.tracing_service import traced

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Backing store
# ---------------------------------------------------------------------------

# Single in-process dict. O(1) lookup. Empty at import — Plan 13-02 (natives)
# and Plan 13-03 (skills) are responsible for populating it; Plan 13-04
# self-registers `tool_search`.
_REGISTRY: dict[str, ToolDefinition] = {}


# ---------------------------------------------------------------------------
# Catalog formatter constants
# ---------------------------------------------------------------------------

# D-P13-03 + D-P13-04: header includes meta-callout for `tool_search` (which is
# excluded from the rendered rows below).
_CATALOG_HEADER = (
    "\n\n## Available Tools\n"
    "Call `tool_search` with a keyword or regex query when you need a tool not listed below.\n"
    "Only call a tool when its description clearly matches the user's request.\n\n"
    "| Tool | Source | Description |\n"
    "|------|--------|-------------|"
)

# Discretion §Catalog overflow: bound prompt cost regardless of registry size.
_DESC_MAX = 80
_CATALOG_CAP = 50

_TRUNCATION_FOOTER_TEMPLATE = (
    "\nShowing {cap} of {total} tools. Call tool_search with a keyword to find more."
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def register(
    name: str,
    description: str,
    schema: dict,
    source: str,
    loading: str,
    executor: Callable[..., Awaitable[dict | str]],
) -> None:
    """Register a tool in the unified registry.

    First-write-wins on duplicate name: a later `register("foo", ...)` is
    logged at WARNING and ignored. This prevents skills or MCP tools from
    silently shadowing a native of the same name.

    Args:
        name: tool identifier surfaced to the LLM. Must be unique.
        description: human-readable summary (rendered into system prompt).
        schema: OpenAI tool-call schema dict (the `{type:"function",function:{...}}`
            shape, or skill parameterless `{}`).
        source: 'native' | 'skill' | 'mcp'.
        loading: 'immediate' (always in LLM tools array) | 'deferred'
            (only in array when in the per-request active set).
        executor: async callable invoked at tool-dispatch time. Native
            executors delegate back into ToolService.execute_tool (D-P13-01);
            skill executors delegate into the Phase 8 load_skill flow.
    """
    if name in _REGISTRY:
        logger.warning(
            "tool_registry: duplicate name=%s source=%s — ignored (first-write-wins)",
            name,
            source,
        )
        return
    _REGISTRY[name] = ToolDefinition(
        name=name,
        description=description,
        schema=schema,
        source=source,  # type: ignore[arg-type]
        loading=loading,  # type: ignore[arg-type]
        executor=executor,
    )


def make_active_set() -> set[str]:
    """Return a fresh empty `set[str]` for one chat request.

    Per-request active-set storage per CONTEXT.md §Discretion §Active-set storage.
    Lifetime = SSE event_generator. Each call returns a NEW set; there is no
    shared state between requests.
    """
    return set()


def _passes_agent_filter(
    tool: ToolDefinition,
    agent_allowed_tools: list[str] | None,
) -> bool:
    """D-P13-06: skill bypass + tool_search always-on; native/mcp gated by name.

    Reused by both `build_llm_tools` (LLM-tools-array layer) and
    `build_catalog_block` (catalog-table layer) so the policy lives in one place.
    Plan 13-04's `tool_search` matcher also reuses this predicate when filtering
    candidates against the calling agent.
    """
    if agent_allowed_tools is None:
        return True
    if tool.source == "skill":
        return True
    if tool.name == "tool_search":
        return True
    return tool.name in agent_allowed_tools


def _is_disabled_by_toggle(
    tool: ToolDefinition,
    *,
    web_search_enabled: bool,
    sandbox_enabled: bool,
) -> bool:
    """Mirror tool_service.get_available_tools per-feature toggles."""
    if tool.name == "web_search" and not web_search_enabled:
        return True
    if tool.name == "execute_code" and not sandbox_enabled:
        return True
    return False


@traced(name="build_llm_tools")
def build_llm_tools(
    *,
    active_set: set[str],
    web_search_enabled: bool,
    sandbox_enabled: bool,
    agent_allowed_tools: list[str] | None,
) -> list[dict]:
    """Return the OpenAI tool-call schemas for the current request.

    A tool is INCLUDED when:
      - it is `loading="immediate"` (always-on after registration), OR
      - its name is in `active_set` (deferred tool added by tool_search this
        request).

    Then the per-feature toggles (web_search_enabled, sandbox_enabled) and the
    D-P13-06 agent filter are applied.

    Returns the list of `tool.schema` dicts in registry-iteration order
    (insertion order is preserved by Python's dict). Plan 13-05 passes this
    directly to the OpenRouter chat-completions call.
    """
    out: list[dict] = []
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
    return out


def _format_table_row(name: str, source: str, description: str) -> str:
    """Render one catalog table row with pipe + newline sanitization.

    Mirrors skill_catalog_service._format_table_row widened to 3 columns.
    Description truncates to 80 visible chars (79 + U+2026 ellipsis) per
    Discretion §Catalog overflow. f-string braces never contain backslashes
    (str escapes computed first).
    """
    desc = (description or "").replace("|", "\\|").replace("\n", " ").strip()
    if len(desc) > _DESC_MAX:
        desc = desc[: _DESC_MAX - 1] + "…"
    safe_name = (name or "").replace("|", "\\|").strip()
    safe_source = (source or "").replace("|", "\\|").strip()
    return f"| {safe_name} | {safe_source} | {desc} |"


@traced(name="build_catalog_block")
async def build_catalog_block(
    *,
    agent_allowed_tools: list[str] | None = None,
) -> str:
    """Return the '## Available Tools' system-prompt block, or '' when empty.

    D-P13-03: single unified table with Tool | Source | Description columns.
    D-P13-04: tool_search is excluded from rendered rows — appears in the
              meta-callout line in `_CATALOG_HEADER` only.
    D-P13-06: agent_allowed_tools filters native/mcp tools (skill bypass).

    This function does NOT register skills itself — the caller (chat.py
    splice in Plan 13-05) is responsible for calling
    `skill_catalog_service.register_user_skills(...)` before invoking this.
    Keeping the registry layer free of DB calls and Supabase imports preserves
    its testability and zero-IO contract.
    """
    tools = [
        t
        for t in _REGISTRY.values()
        if t.name != "tool_search"
        and t.available  # Phase 15 (D-P15-11): skip unavailable MCP server tools
        and _passes_agent_filter(t, agent_allowed_tools)
    ]
    if not tools:
        return ""

    tools.sort(key=lambda t: t.name.lower())
    total = len(tools)
    rows = [
        _format_table_row(t.name, t.source, t.description)
        for t in tools[:_CATALOG_CAP]
    ]
    body = _CATALOG_HEADER + "\n" + "\n".join(rows)
    if total > _CATALOG_CAP:
        body += _TRUNCATION_FOOTER_TEMPLATE.format(cap=_CATALOG_CAP, total=total)
    return body


# ---------------------------------------------------------------------------
# Test helpers (TEST-ONLY)
# ---------------------------------------------------------------------------


def _clear_for_tests() -> None:  # pragma: no cover
    """TEST-ONLY — never call from production. Resets registry to a clean state.

    After Plan 13-04 lands, the production registry always contains
    `tool_search` at module load (self-registration). To match production
    state between tests, we re-register tool_search after clearing. Tests
    that want a truly empty registry can call `_REGISTRY.clear()` directly.

    A leak into production would break the first-write-wins guarantee that
    natives cannot be clobbered by later registrations.
    """
    _REGISTRY.clear()
    _register_tool_search()


# ---------------------------------------------------------------------------
# Phase 13 Plan 04 — tool_search meta-tool (TOOL-02, TOOL-03; D-P13-05).
#
# tool_search lets the LLM discover deferred-loading tools by keyword (case-
# insensitive substring) or regex (re.search, IGNORECASE). Matched tools are
# added to the per-request active_set so they appear in the LLM tools array
# for the rest of the turn (D-P13-04 invariant — set is caller-owned and
# ephemeral; tool_search never persists state across requests).
# ---------------------------------------------------------------------------

import re

_REGEX_MAX_LEN = 200  # Catastrophic-backtracking guard.
_SEARCH_RESULT_CAP = 10  # CONTEXT.md §Discretion §tool_search result cap.


def _score_match(
    tool: ToolDefinition, query: str, *, is_regex: bool
) -> tuple[int, int, str]:
    """Rank a match. Returned tuple is consumed by sort:
       (match_class, neg_span_len, name_lower).

    match_class: 2 = matched in name, 1 = matched only in description, 0 = no match.
    neg_span_len: -span_length so longer spans sort first under ascending sort.
    name_lower: alphabetical tiebreaker.

    Caller filters out (0, ...) entries before returning matches.
    """
    name = tool.name
    desc = tool.description or ""
    name_lc = name.lower()
    desc_lc = desc.lower()
    if is_regex:
        try:
            pattern = re.compile(query, re.IGNORECASE)
        except re.error:
            return (0, 0, name_lc)
        m_name = pattern.search(name)
        m_desc = pattern.search(desc)
        name_match = m_name is not None
        desc_match = m_desc is not None
        if m_name:
            span_len = m_name.end() - m_name.start()
        elif m_desc:
            span_len = m_desc.end() - m_desc.start()
        else:
            span_len = 0
    else:
        q = query.lower()
        name_match = q in name_lc
        desc_match = q in desc_lc
        span_len = len(q) if (name_match or desc_match) else 0
    if name_match:
        return (2, -span_len, name_lc)
    if desc_match:
        return (1, -span_len, name_lc)
    return (0, 0, name_lc)


@traced(name="tool_search")
async def tool_search(
    *,
    keyword: str | None = None,
    regex: str | None = None,
    active_set: set[str] | None = None,
    agent_allowed_tools: list[str] | None = None,
) -> dict:
    """D-P13-05: discover registry tools by keyword (substring) or regex.

    Both null → structured error. Both passed → regex wins (logged via `hint`).
    Returns {"matches": [<full openai schema>...], "hint": str|None, "error": str|None}.
    Side effect: matched tool names added to `active_set` (mutate by reference).

    Self-exclusion: tool_search never includes itself in matches (D-P13-04).
    Agent filter: D-P13-06 — skill bypass + tool_search always-on (irrelevant
    here because tool_search excludes itself); native/mcp gated by agent.tool_names.
    Regex safety: pattern length capped at _REGEX_MAX_LEN; re.compile errors
    return as a structured error rather than raising.
    """
    if keyword is None and regex is None:
        return {
            "matches": [],
            "hint": None,
            "error": "either keyword or regex required",
        }

    hint: str | None = None
    if keyword is not None and regex is not None:
        hint = "regex wins when both keyword and regex are passed"

    is_regex = regex is not None
    query = regex if is_regex else keyword
    assert query is not None  # for type-checker; both-null returns early above

    if is_regex:
        if len(query) > _REGEX_MAX_LEN:
            return {
                "matches": [],
                "hint": hint,
                "error": f"regex pattern too long (max {_REGEX_MAX_LEN} chars)",
            }
        try:
            re.compile(query)
        except re.error as e:
            return {"matches": [], "hint": hint, "error": f"invalid regex: {e}"}

    candidates: list[tuple[tuple[int, int, str], ToolDefinition]] = []
    for tool in _REGISTRY.values():
        if tool.name == "tool_search":
            continue  # self-exclusion (D-P13-04)
        if not _passes_agent_filter(tool, agent_allowed_tools):
            continue
        score = _score_match(tool, query, is_regex=is_regex)
        if score[0] == 0:
            continue
        # Negate match_class so higher class sorts first; span_len already negative.
        candidates.append(((-score[0], score[1], score[2]), tool))

    candidates.sort(key=lambda x: x[0])
    top = candidates[:_SEARCH_RESULT_CAP]

    matches = [tool.schema for _, tool in top]
    if active_set is not None:
        for _, tool in top:
            active_set.add(tool.name)

    return {"matches": matches, "hint": hint, "error": None}


# ---------------------------------------------------------------------------
# tool_search self-registration (D-P13-04 always-on).
# ---------------------------------------------------------------------------

_TOOL_SEARCH_SCHEMA = {
    "type": "function",
    "function": {
        "name": "tool_search",
        "description": (
            "Find tools in the registry by keyword (case-insensitive substring) "
            "or regex (Python re.search, IGNORECASE). Returns matching tools' "
            "OpenAI schemas and adds them to the active set for the rest of the "
            "current request."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": ["string", "null"],
                    "description": "Plain substring; case-insensitive. Use for casual searches.",
                },
                "regex": {
                    "type": ["string", "null"],
                    "description": (
                        "Python re.search pattern; case-insensitive. Patterns longer "
                        "than 200 characters are rejected. Examples: '^kb_', 'search$'."
                    ),
                },
            },
            "required": [],
        },
    },
}


def _register_tool_search() -> None:
    """Self-register tool_search as source='native', loading='immediate'.

    Always-on (D-P13-04): the chat.py wiring in 13-05 includes tool_search in
    the LLM tools array on every request when the flag is on, and the catalog
    formatter excludes it from rows so it appears only in the meta-callout
    line.

    The executor adapter forwards `arguments` (the LLM-supplied params) and
    reads `active_set` / `agent_allowed_tools` from the per-request `context`
    dict, which Plan 13-05's chat.py registry dispatcher populates.
    """

    async def _executor(
        arguments: dict,
        user_id: str,
        context: dict | None = None,
        **kwargs,
    ):
        ctx = context or {}
        return await tool_search(
            keyword=arguments.get("keyword"),
            regex=arguments.get("regex"),
            active_set=ctx.get("active_set"),
            agent_allowed_tools=ctx.get("agent_allowed_tools"),
        )

    register(
        name="tool_search",
        description=_TOOL_SEARCH_SCHEMA["function"]["description"],
        schema=_TOOL_SEARCH_SCHEMA,
        source="native",
        loading="immediate",
        executor=_executor,
    )


# ---------------------------------------------------------------------------
# Phase 15 — MCP server availability management (D-P15-11).
# ---------------------------------------------------------------------------


def mark_server_unavailable(server_name: str) -> int:
    """Mark all tools from `server_name` as unavailable (D-P15-11).

    Iterates _REGISTRY and sets available=False on every tool whose name
    starts with f"{server_name}__". Returns the count of tools marked.
    Called by MCPClientManager when a server disconnects.

    Uses model_copy(update={...}) for Pydantic v2 compatibility — ToolDefinition
    uses ConfigDict without frozen=True so direct assignment also works, but
    model_copy is the safer forward-compatible approach.
    """
    count = 0
    prefix = f"{server_name}__"
    for name, tool in list(_REGISTRY.items()):
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
    for name, tool in list(_REGISTRY.items()):
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


# Run self-registration at module load. The chat.py flag-off path never imports
# this module, so this is effectively gated by settings.tool_registry_enabled.
_register_tool_search()
