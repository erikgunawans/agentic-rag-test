"""ADR-0008: web_search excluded from tool list when effective toggle off."""
from app.services.tool_service import ToolService


def _tool_names(tools: list[dict]) -> list[str]:
    return [t["function"]["name"] for t in tools]


def test_web_search_excluded_when_disabled():
    svc = ToolService()
    tools = svc.get_available_tools(web_search_enabled=False)
    assert "web_search" not in _tool_names(tools)
    # other tools unaffected
    assert "search_documents" in _tool_names(tools)


def test_web_search_included_when_enabled():
    svc = ToolService()
    tools = svc.get_available_tools(web_search_enabled=True)
    # only present if tavily key configured (existing behaviour preserved)
    names = _tool_names(tools)
    assert "search_documents" in names
    # If tavily key is set in env, web_search should appear:
    from app.config import get_settings
    if get_settings().tavily_api_key:
        assert "web_search" in names


def test_default_behaviour_preserved_for_existing_callers():
    """No-arg call should default to web_search_enabled=True for backward compat."""
    svc = ToolService()
    tools = svc.get_available_tools()
    names = _tool_names(tools)
    assert "search_documents" in names
