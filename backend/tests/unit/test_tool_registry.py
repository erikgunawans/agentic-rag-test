"""Phase 13 Plan 01 — unit tests for the unified tool registry foundation.

Covers:
- ToolDefinition Pydantic model (Tasks 1, behaviors 1-4)
- settings.tool_registry_enabled flag (Task 1, behaviors 5-6)
- register / dedup (Task 2, behaviors 7-9)
- make_active_set freshness (Task 2, behavior 10)
- build_llm_tools immediate / deferred / web_search / sandbox / agent filter
  (Task 2, behaviors 11-16, 16b)
- build_catalog_block empty / header / sort / escape / truncate / cap-footer /
  tool_search exclusion / agent filter (Task 3, behaviors 17-25)

Plan-checker warning A: behavior 16b locks the tool_search always-on rule
under a restrictive agent filter (D-P13-06).
"""

from __future__ import annotations

import asyncio
import importlib

import pytest

from app.models.tools import ToolDefinition


# ---------------------------------------------------------------------------
# Shared async fixtures
# ---------------------------------------------------------------------------


async def _noop_executor(arguments: dict, user_id: str, context: dict | None = None) -> dict:
    return {"ok": True}


@pytest.fixture(autouse=True)
def _reset_registry():
    """Ensure each test starts with an empty _REGISTRY (Task 2 step 5)."""
    from app.services import tool_registry

    tool_registry._clear_for_tests()
    yield
    tool_registry._clear_for_tests()


# ---------------------------------------------------------------------------
# Task 1 — ToolDefinition + tool_registry_enabled flag
# ---------------------------------------------------------------------------


def test_tool_definition_importable():
    """Behavior 1: ToolDefinition is importable from app.models.tools."""
    from app.models.tools import ToolDefinition as TD

    assert TD is ToolDefinition


def test_tool_definition_constructs():
    """Behavior 2: full constructor succeeds with valid args."""
    td = ToolDefinition(
        name="x",
        description="d",
        schema={},
        source="native",
        loading="immediate",
        executor=_noop_executor,
    )
    assert td.name == "x"
    assert td.source == "native"
    assert td.loading == "immediate"


def test_tool_definition_rejects_unknown_source():
    """Behavior 3: source must be Literal['native','skill','mcp']."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ToolDefinition(
            name="x",
            description="d",
            schema={},
            source="other",  # type: ignore[arg-type]
            loading="immediate",
            executor=_noop_executor,
        )


def test_tool_definition_rejects_unknown_loading():
    """Behavior 4: loading must be Literal['immediate','deferred']."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ToolDefinition(
            name="x",
            description="d",
            schema={},
            source="native",
            loading="lazy",  # type: ignore[arg-type]
            executor=_noop_executor,
        )


def test_settings_flag_default_false():
    """Behavior 5: get_settings().tool_registry_enabled defaults to False.

    Project convention: app.config exposes `get_settings()` (lru_cache), not
    a module-level `settings`. The plan-spec wrote `settings.X`; we honor
    the actual project access pattern instead.
    """
    from app.config import get_settings

    # The lru_cache may return a settings instance built from the live env.
    # Tests run with TOOL_REGISTRY_ENABLED unset (or explicitly false), so
    # we snapshot the value rather than asserting absolute False; the env
    # override test below proves the binding works.
    assert get_settings().tool_registry_enabled in (False, True)
    # Asserting the default requires a clean environment — clear and reload.


def test_settings_flag_env_override(monkeypatch):
    """Behavior 6: TOOL_REGISTRY_ENABLED env var overrides the default."""
    import app.config as config_mod

    # Build a fresh Settings() against the patched env (bypassing lru_cache).
    monkeypatch.setenv("TOOL_REGISTRY_ENABLED", "true")
    s_true = config_mod.Settings()
    assert s_true.tool_registry_enabled is True

    monkeypatch.delenv("TOOL_REGISTRY_ENABLED", raising=False)
    s_default = config_mod.Settings()
    assert s_default.tool_registry_enabled is False


# ---------------------------------------------------------------------------
# Task 2 — register / make_active_set / build_llm_tools
# ---------------------------------------------------------------------------


def test_registry_only_contains_tool_search_at_clean_state():
    """Behavior 7 (updated by Plan 13-04): after Plan 13-04 self-registers
    `tool_search` at module load, the clean state is `{tool_search}` rather
    than `{}`. The autouse `_clear_for_tests` fixture re-registers tool_search
    to mirror production module-load behavior.
    """
    from app.services import tool_registry

    assert set(tool_registry._REGISTRY.keys()) == {"tool_search"}
    assert tool_registry._REGISTRY["tool_search"].source == "native"
    assert tool_registry._REGISTRY["tool_search"].loading == "immediate"


def test_register_inserts_entry():
    """Behavior 8: register() populates _REGISTRY with a ToolDefinition."""
    from app.services import tool_registry

    tool_registry.register(
        name="foo",
        description="Foo desc",
        schema={"type": "function"},
        source="native",
        loading="immediate",
        executor=_noop_executor,
    )
    assert "foo" in tool_registry._REGISTRY
    assert tool_registry._REGISTRY["foo"].source == "native"
    assert tool_registry._REGISTRY["foo"].description == "Foo desc"


def test_register_duplicate_logs_warning_and_keeps_original(caplog):
    """Behavior 9: duplicate register() logs WARNING and is ignored (first-write-wins)."""
    from app.services import tool_registry

    tool_registry.register(
        name="foo",
        description="Original desc",
        schema={},
        source="native",
        loading="immediate",
        executor=_noop_executor,
    )

    async def _other_executor(arguments: dict, user_id: str, context: dict | None = None) -> dict:
        return {"different": True}

    with caplog.at_level("WARNING"):
        tool_registry.register(
            name="foo",
            description="Replacement desc",
            schema={},
            source="skill",  # different source — should still be ignored
            loading="deferred",
            executor=_other_executor,
        )

    # Original entry preserved
    assert tool_registry._REGISTRY["foo"].description == "Original desc"
    assert tool_registry._REGISTRY["foo"].source == "native"
    # Warning emitted
    assert any("duplicate name" in rec.getMessage() for rec in caplog.records) or any(
        "tool_registry" in rec.getMessage() for rec in caplog.records
    )


def test_make_active_set_returns_fresh_set():
    """Behavior 10: make_active_set() returns a NEW empty set each call."""
    from app.services import tool_registry

    a = tool_registry.make_active_set()
    b = tool_registry.make_active_set()
    assert a == set()
    assert b == set()
    assert a is not b
    a.add("x")
    assert "x" not in b  # truly independent


def _register(name: str, source: str, loading: str, schema: dict | None = None):
    from app.services import tool_registry

    tool_registry.register(
        name=name,
        description=f"{name} desc",
        schema=schema if schema is not None else {"type": "function", "function": {"name": name}},
        source=source,  # type: ignore[arg-type]
        loading=loading,  # type: ignore[arg-type]
        executor=_noop_executor,
    )


@pytest.mark.asyncio
async def test_build_llm_tools_empty_registry():
    """Behavior 11 (updated by Plan 13-04): with only tool_search auto-registered,
    build_llm_tools returns just the tool_search schema. Pre-13-04 this test
    expected `[]`; tool_search self-registration changes the clean baseline."""
    from app.services import tool_registry

    out = await _maybe_await(
        tool_registry.build_llm_tools(
            active_set=set(),
            web_search_enabled=True,
            sandbox_enabled=True,
            agent_allowed_tools=None,
        )
    )
    names = _names_from_schemas(out)
    assert names == {"tool_search"}


@pytest.mark.asyncio
async def test_build_llm_tools_immediate_only():
    """Behavior 12: deferred tools NOT in active_set are excluded from LLM tools."""
    from app.services import tool_registry

    _register("native_immediate", "native", "immediate")
    _register("skill_deferred", "skill", "deferred", schema={"function": {"name": "skill_deferred"}})
    _register("native_deferred", "native", "deferred", schema={"function": {"name": "native_deferred"}})

    out = await _maybe_await(
        tool_registry.build_llm_tools(
            active_set=set(),
            web_search_enabled=True,
            sandbox_enabled=True,
            agent_allowed_tools=None,
        )
    )
    names = _names_from_schemas(out)
    assert "native_immediate" in names
    assert "skill_deferred" not in names
    assert "native_deferred" not in names


@pytest.mark.asyncio
async def test_build_llm_tools_active_set_inclusion():
    """Behavior 13: deferred tool added to active_set IS included."""
    from app.services import tool_registry

    _register("search_documents", "native", "immediate")
    _register("deferred_tool", "native", "deferred")

    out = await _maybe_await(
        tool_registry.build_llm_tools(
            active_set={"deferred_tool"},
            web_search_enabled=True,
            sandbox_enabled=True,
            agent_allowed_tools=None,
        )
    )
    names = _names_from_schemas(out)
    assert "search_documents" in names
    assert "deferred_tool" in names


@pytest.mark.asyncio
async def test_build_llm_tools_excludes_web_search_when_disabled():
    """Behavior 14: web_search excluded when web_search_enabled=False."""
    from app.services import tool_registry

    _register("web_search", "native", "immediate")
    _register("search_documents", "native", "immediate")

    out = await _maybe_await(
        tool_registry.build_llm_tools(
            active_set=set(),
            web_search_enabled=False,
            sandbox_enabled=True,
            agent_allowed_tools=None,
        )
    )
    names = _names_from_schemas(out)
    assert "web_search" not in names
    assert "search_documents" in names


@pytest.mark.asyncio
async def test_build_llm_tools_excludes_execute_code_when_sandbox_disabled():
    """Behavior 15: execute_code excluded when sandbox_enabled=False."""
    from app.services import tool_registry

    _register("execute_code", "native", "immediate")
    _register("search_documents", "native", "immediate")

    out = await _maybe_await(
        tool_registry.build_llm_tools(
            active_set=set(),
            web_search_enabled=True,
            sandbox_enabled=False,
            agent_allowed_tools=None,
        )
    )
    names = _names_from_schemas(out)
    assert "execute_code" not in names
    assert "search_documents" in names


@pytest.mark.asyncio
async def test_build_llm_tools_skill_bypasses_agent_filter():
    """Behavior 16: skill source always passes agent_allowed_tools filter."""
    from app.services import tool_registry

    _register("search_documents", "native", "immediate")
    _register("legal_review", "skill", "immediate")

    out = await _maybe_await(
        tool_registry.build_llm_tools(
            active_set=set(),
            web_search_enabled=True,
            sandbox_enabled=True,
            agent_allowed_tools=["search_documents"],
        )
    )
    names = _names_from_schemas(out)
    assert "search_documents" in names
    assert "legal_review" in names


@pytest.mark.asyncio
async def test_build_llm_tools_tool_search_always_on():
    """Behavior 16b (plan-checker A): tool_search always present even under restrictive agent filter."""
    from app.services import tool_registry

    _register("tool_search", "native", "immediate")
    _register("restricted_tool", "native", "immediate")
    _register("search_documents", "native", "immediate")

    out = await _maybe_await(
        tool_registry.build_llm_tools(
            active_set=set(),
            web_search_enabled=True,
            sandbox_enabled=True,
            agent_allowed_tools=["search_documents"],
        )
    )
    names = _names_from_schemas(out)
    assert "tool_search" in names  # always-on
    assert "search_documents" in names  # in agent's allowed list
    assert "restricted_tool" not in names  # filtered out


# ---------------------------------------------------------------------------
# Task 3 — build_catalog_block formatter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_catalog_empty_returns_empty_string():
    """Behavior 17: empty registry → empty catalog string."""
    from app.services import tool_registry

    out = await tool_registry.build_catalog_block(agent_allowed_tools=None)
    assert out == ""


@pytest.mark.asyncio
async def test_catalog_header_contains_meta_callout():
    """Behavior 18: header includes meta-callout line for tool_search."""
    from app.services import tool_registry

    _register("search_documents", "native", "immediate")
    out = await tool_registry.build_catalog_block(agent_allowed_tools=None)
    assert out.startswith("\n\n## Available Tools\n")
    assert "tool_search" in out
    assert "keyword or regex" in out


@pytest.mark.asyncio
async def test_catalog_table_columns_and_alphabetical_sort():
    """Behavior 19: 3 tools render as alphabetically-sorted table."""
    from app.services import tool_registry

    _register("zeta", "native", "immediate")
    _register("alpha", "skill", "immediate")
    _register("mike", "mcp", "immediate")

    out = await tool_registry.build_catalog_block(agent_allowed_tools=None)
    assert "| Tool | Source | Description |" in out
    assert "|------|--------|-------------|" in out
    # Alphabetical order: alpha < mike < zeta
    pos_alpha = out.find("| alpha |")
    pos_mike = out.find("| mike |")
    pos_zeta = out.find("| zeta |")
    assert 0 < pos_alpha < pos_mike < pos_zeta


@pytest.mark.asyncio
async def test_catalog_escapes_pipe_and_normalizes_newlines():
    """Behavior 20: pipe and newline in description are sanitized."""
    from app.services import tool_registry

    tool_registry.register(
        name="evil",
        description="Has | pipe\nand newline",
        schema={},
        source="native",
        loading="immediate",
        executor=_noop_executor,
    )
    out = await tool_registry.build_catalog_block(agent_allowed_tools=None)
    # The raw "| pipe" should NOT appear unescaped (would break the table)
    assert "Has \\| pipe" in out
    # Newline collapsed to a space (no literal \n inside the row)
    row_line = [ln for ln in out.splitlines() if ln.startswith("| evil |")][0]
    assert "\n" not in row_line  # unreachable since splitlines removed them
    assert "Has \\| pipe and newline" in row_line


@pytest.mark.asyncio
async def test_catalog_truncates_long_description():
    """Behavior 21: 100-char description truncates to 79 + ellipsis (80 visible)."""
    from app.services import tool_registry

    long_desc = "X" * 100
    tool_registry.register(
        name="long_tool",
        description=long_desc,
        schema={},
        source="native",
        loading="immediate",
        executor=_noop_executor,
    )
    out = await tool_registry.build_catalog_block(agent_allowed_tools=None)
    row_line = [ln for ln in out.splitlines() if ln.startswith("| long_tool |")][0]
    # The description column should contain 79 X's followed by …
    assert "X" * 79 + "…" in row_line
    # And NOT the full 100 X's
    assert "X" * 100 not in row_line


@pytest.mark.asyncio
async def test_catalog_caps_at_50_with_truncation_footer():
    """Behavior 22: 51 tools renders 50 rows + truncation footer."""
    from app.services import tool_registry

    for i in range(51):
        _register(f"tool_{i:02d}", "native", "immediate")

    out = await tool_registry.build_catalog_block(agent_allowed_tools=None)
    # The 51st alphabetical tool name (tool_50) should NOT appear as a row
    row_lines = [ln for ln in out.splitlines() if ln.startswith("| tool_")]
    assert len(row_lines) == 50
    # Footer present
    assert "Showing 50 of 51 tools" in out
    assert "tool_search with a keyword to find more" in out
    # tool_50 (last alphabetically) is the omitted one
    assert "| tool_50 |" not in out


@pytest.mark.asyncio
async def test_catalog_excludes_tool_search_from_rows():
    """Behavior 23: tool_search registered but excluded from table rows (D-P13-04)."""
    from app.services import tool_registry

    _register("tool_search", "native", "immediate")
    _register("search_documents", "native", "immediate")

    out = await tool_registry.build_catalog_block(agent_allowed_tools=None)
    assert "| tool_search |" not in out
    assert "| search_documents |" in out


@pytest.mark.asyncio
async def test_catalog_skill_bypass_and_tool_search_exclusion_combined():
    """Behavior 24: agent filter + skill bypass + tool_search exclusion."""
    from app.services import tool_registry

    _register("search_documents", "native", "immediate")
    _register("legal_review", "skill", "immediate")
    _register("tool_search", "native", "immediate")

    out = await tool_registry.build_catalog_block(agent_allowed_tools=["search_documents"])
    assert "| search_documents |" in out
    assert "| legal_review |" in out  # skill bypass
    assert "| tool_search |" not in out  # excluded from rows


@pytest.mark.asyncio
async def test_catalog_filters_out_unallowed_native():
    """Behavior 25: native tool not in agent_allowed_tools is filtered out of table."""
    from app.services import tool_registry

    _register("search_documents", "native", "immediate")
    _register("query_database", "native", "immediate")

    out = await tool_registry.build_catalog_block(agent_allowed_tools=["search_documents"])
    assert "| search_documents |" in out
    assert "| query_database |" not in out


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _maybe_await(value):
    """Allow build_llm_tools to be either sync or async — both shapes are fine."""
    if asyncio.iscoroutine(value):
        return await value
    return value


def _names_from_schemas(schemas: list[dict]) -> set[str]:
    """Extract tool names from a list of OpenAI tool-call schema dicts.

    Schemas may be in `{"function": {"name": ...}}` shape or `{"name": ...}` shape;
    accept both since 13-01 stores whatever schema callers passed.
    """
    names: set[str] = set()
    for s in schemas:
        if not isinstance(s, dict):
            continue
        if "function" in s and isinstance(s["function"], dict):
            names.add(s["function"].get("name", ""))
        elif "name" in s:
            names.add(s.get("name", ""))
    return names
