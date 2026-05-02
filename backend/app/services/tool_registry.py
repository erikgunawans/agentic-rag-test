"""Phase 13: Unified Tool Registry & tool_search Meta-Tool — registry foundation.

Plan 13-01 (TOOL-04, TOOL-06; D-P13-01..D-P13-06).

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
        if t.name != "tool_search" and _passes_agent_filter(t, agent_allowed_tools)
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
    """TEST-ONLY — never call from production. Empties the registry between tests.

    Exposed so the unit-test autouse fixture can guarantee per-test isolation.
    A leak into production would break the first-write-wins guarantee that
    natives cannot be clobbered by later registrations.
    """
    _REGISTRY.clear()
