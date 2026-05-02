"""Phase 13 Plan 04 — tool_search meta-tool unit tests (TOOL-02, TOOL-03).

15 behavior tests covering:
  - Keyword vs regex matching
  - Both-null error / both-passed regex-wins hint
  - Case insensitivity
  - Top-10 cap with deterministic ordering
  - Ranking: name match > description match; longer span > shorter; alphabetical tiebreaker
  - Regex safety: 200-char length cap + compile-error handling
  - Plan-checker warning B fix: agent filter via regex='.' instead of vacuous keyword='.*'
  - Self-exclusion (tool_search never matches itself)
  - active_set mutation by reference; active_set=None safe
  - Self-registration: tool_search is source='native', loading='immediate' at module load
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _reset_registry():
    """Reset registry to clean state (just tool_search re-registered)."""
    from app.services import tool_registry

    tool_registry._clear_for_tests()
    yield
    tool_registry._clear_for_tests()


async def _noop_executor(arguments: dict, user_id: str, context: dict | None = None) -> dict:
    return {"ok": True}


def _register(name: str, source: str, loading: str, description: str = ""):
    from app.services import tool_registry

    tool_registry.register(
        name=name,
        description=description or f"{name} tool description",
        schema={"type": "function", "function": {"name": name, "description": description}},
        source=source,  # type: ignore[arg-type]
        loading=loading,  # type: ignore[arg-type]
        executor=_noop_executor,
    )


def _match_names(result: dict) -> list[str]:
    """Extract names from tool_search match schemas in returned order."""
    out = []
    for s in result.get("matches", []):
        fn = s.get("function") or {}
        if fn.get("name"):
            out.append(fn["name"])
    return out


# ---------------------------------------------------------------------------
# Test 1: keyword
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_keyword_match_substring():
    from app.services import tool_registry

    _register("search_documents", "native", "deferred", "Search internal docs")
    _register("query_database", "native", "deferred", "Query SQL database")
    _register("web_search", "native", "deferred", "Web search via Tavily")
    _register("legal_review", "skill", "deferred", "Reviews NDAs")
    _register("execute_code", "native", "deferred", "Sandbox execute")

    active = set()
    result = await tool_registry.tool_search(keyword="search", active_set=active)

    names = _match_names(result)
    assert "search_documents" in names
    assert "web_search" in names
    assert "query_database" not in names
    assert result["hint"] is None
    assert result["error"] is None
    assert "search_documents" in active
    assert "web_search" in active


# ---------------------------------------------------------------------------
# Test 2: regex
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_regex_match_anchored():
    from app.services import tool_registry

    _register("search_documents", "native", "deferred", "Search internal docs")
    _register("query_database", "native", "deferred", "Query SQL database")
    _register("web_search", "native", "deferred", "Web search via Tavily")

    active = set()
    result = await tool_registry.tool_search(regex="^search_", active_set=active)

    names = _match_names(result)
    assert names == ["search_documents"]
    assert result["hint"] is None
    assert result["error"] is None
    assert active == {"search_documents"}


# ---------------------------------------------------------------------------
# Test 3: both null
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_both_null_returns_error():
    from app.services import tool_registry

    _register("search_documents", "native", "deferred", "Search internal docs")
    active = set()
    result = await tool_registry.tool_search(active_set=active)

    assert result["error"] == "either keyword or regex required"
    assert result["matches"] == []
    assert active == set()  # no mutation


# ---------------------------------------------------------------------------
# Test 4: both passed → regex wins
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_both_passed_regex_wins_with_hint():
    from app.services import tool_registry

    _register("search_documents", "native", "deferred", "Search internal docs")
    _register("query_database", "native", "deferred", "Query database documents")

    active = set()
    # keyword would match both (both have "documents" in description), but
    # regex "^search_" only matches search_documents.
    result = await tool_registry.tool_search(
        keyword="documents", regex="^search_", active_set=active
    )

    names = _match_names(result)
    assert names == ["search_documents"]
    assert result["hint"] == "regex wins when both keyword and regex are passed"
    assert active == {"search_documents"}


# ---------------------------------------------------------------------------
# Test 5: case-insensitive
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_case_insensitive_keyword_and_regex():
    from app.services import tool_registry

    _register("legal_review", "skill", "deferred", "Reviews NDAs")

    r1 = await tool_registry.tool_search(keyword="LEGAL")
    assert "legal_review" in _match_names(r1)

    r2 = await tool_registry.tool_search(regex="LEGAL")
    assert "legal_review" in _match_names(r2)


# ---------------------------------------------------------------------------
# Test 6: top-10 cap
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_top_10_cap_alphabetical_omission():
    from app.services import tool_registry

    for i in range(15):
        _register(f"tool_{i:02d}", "native", "deferred", "generic")

    result = await tool_registry.tool_search(keyword="tool_", active_set=set())
    names = _match_names(result)
    assert len(names) == 10
    # Alphabetically, tool_00..tool_09 sort first; tool_10..tool_14 omitted.
    assert names[0] == "tool_00"
    assert "tool_10" not in names
    assert "tool_14" not in names


# ---------------------------------------------------------------------------
# Test 7: ranking — name match outranks description match
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ranking_name_outranks_description():
    from app.services import tool_registry

    _register("apple_search", "native", "deferred", "generic description")
    _register("banana", "native", "deferred", "this is a search tool")

    result = await tool_registry.tool_search(keyword="search", active_set=set())
    names = _match_names(result)
    assert names == ["apple_search", "banana"]


# ---------------------------------------------------------------------------
# Test 8: ranking — alphabetical tiebreaker
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ranking_alphabetical_tiebreaker_on_equal_class_and_span():
    from app.services import tool_registry

    # Both names match "search" → match_class=2 for both. span_len=6 for both.
    # Tiebreaker is alphabetical: "search" < "xy_search".
    _register("search", "native", "deferred", "")
    _register("xy_search", "native", "deferred", "")

    result = await tool_registry.tool_search(keyword="search", active_set=set())
    names = _match_names(result)
    assert names == ["search", "xy_search"]


# ---------------------------------------------------------------------------
# Test 9: regex length cap
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_regex_length_cap():
    from app.services import tool_registry

    _register("search_documents", "native", "deferred", "")
    long_pattern = "A" * 201
    result = await tool_registry.tool_search(regex=long_pattern, active_set=set())
    assert "too long" in result["error"]
    assert result["matches"] == []


# ---------------------------------------------------------------------------
# Test 10: invalid regex
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invalid_regex_returns_error():
    from app.services import tool_registry

    _register("search_documents", "native", "deferred", "")
    active = set()
    # "(?P<" is an unclosed named group — re.compile will raise re.error
    result = await tool_registry.tool_search(regex="(?P<", active_set=active)
    assert result["error"].startswith("invalid regex:")
    assert result["matches"] == []
    assert active == set()


# ---------------------------------------------------------------------------
# Test 11: agent filter (plan-checker warning B fix — regex="." not keyword=".*")
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_agent_filter_skill_bypass_and_native_gate():
    from app.services import tool_registry

    _register("search_documents", "native", "deferred", "")
    _register("legal_review", "skill", "deferred", "")
    _register("restricted_tool", "native", "deferred", "")
    # tool_search is auto-registered already (always-on) but excluded via self-exclusion.

    result = await tool_registry.tool_search(
        regex=".",  # matches every non-empty name (D-P13-05 universal-match form)
        active_set=set(),
        agent_allowed_tools=["search_documents"],
    )
    names = set(_match_names(result))
    assert "search_documents" in names  # in agent's allowed list
    assert "legal_review" in names  # skill bypass
    assert "restricted_tool" not in names  # native NOT in agent's allowed list
    assert "tool_search" not in names  # self-exclusion


# ---------------------------------------------------------------------------
# Test 12: self-exclusion
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_self_exclusion():
    from app.services import tool_registry

    # tool_search is auto-registered. A search for "tool_search" should NOT include itself.
    result = await tool_registry.tool_search(keyword="tool_search", active_set=set())
    names = _match_names(result)
    assert "tool_search" not in names


# ---------------------------------------------------------------------------
# Test 13: active_set mutation by reference
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_active_set_mutated_by_reference():
    from app.services import tool_registry

    _register("search_documents", "native", "deferred", "")
    s = set()
    await tool_registry.tool_search(keyword="search", active_set=s)
    assert "search_documents" in s


# ---------------------------------------------------------------------------
# Test 14: active_set=None is safe
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_active_set_none_is_safe():
    from app.services import tool_registry

    _register("search_documents", "native", "deferred", "")
    # Must not raise even when active_set is None.
    result = await tool_registry.tool_search(keyword="search", active_set=None)
    assert "search_documents" in _match_names(result)


# ---------------------------------------------------------------------------
# Test 15: self-registration at module load
# ---------------------------------------------------------------------------


def test_tool_search_self_registered():
    from app.services import tool_registry

    assert "tool_search" in tool_registry._REGISTRY
    td = tool_registry._REGISTRY["tool_search"]
    assert td.source == "native"
    assert td.loading == "immediate"

    schema_props = td.schema["function"]["parameters"]["properties"]
    assert schema_props["keyword"]["type"] == ["string", "null"]
    assert schema_props["regex"]["type"] == ["string", "null"]
    assert td.schema["function"]["parameters"]["required"] == []
