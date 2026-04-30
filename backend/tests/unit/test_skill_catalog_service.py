"""Unit tests for skill_catalog_service.build_skill_catalog_block.

Covers SKILL-07: catalog injection into LLM system prompt.
Decisions enforced: D-P8-02 (empty string when 0 skills),
D-P8-05 (markdown table format), D-P8-06 (cap 20 alphabetical),
D-P8-07 (truncation footer).
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest

from app.services.skill_catalog_service import build_skill_catalog_block


def _mock_client(rows):
    """Mock the Supabase client chain: client.table('skills').select(...).eq(...).order(...).limit(...).execute()"""
    client = MagicMock()
    chain = MagicMock()
    chain.execute.return_value.data = rows
    chain.eq.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    chain.select.return_value = chain
    client.table.return_value = chain
    return client


@pytest.mark.asyncio
async def test_zero_enabled_skills_returns_empty_string():
    """D-P8-02 invariant: chat path is byte-identical to current behavior when 0 skills."""
    client = _mock_client([])
    with patch(
        "app.services.skill_catalog_service.get_supabase_authed_client",
        return_value=client,
    ):
        result = await build_skill_catalog_block("u1", "tok")
    assert result == ""


@pytest.mark.asyncio
async def test_single_skill_returns_formatted_block():
    client = _mock_client([
        {"name": "legal-review", "description": "Reviews NDA contracts."}
    ])
    with patch(
        "app.services.skill_catalog_service.get_supabase_authed_client",
        return_value=client,
    ):
        result = await build_skill_catalog_block("u1", "tok")
    assert result.startswith("\n\n## Your Skills\n")
    assert "| Skill | Description |" in result
    assert "|-------|-------------|" in result
    assert "| legal-review | Reviews NDA contracts. |" in result
    # No truncation footer when <= 20 skills
    assert "Showing 20 enabled skills" not in result


@pytest.mark.asyncio
async def test_twenty_skills_no_truncation_footer():
    rows = [
        {"name": f"skill-{i:02d}", "description": f"Skill {i} description here."}
        for i in range(20)
    ]
    client = _mock_client(rows)
    with patch(
        "app.services.skill_catalog_service.get_supabase_authed_client",
        return_value=client,
    ):
        result = await build_skill_catalog_block("u1", "tok")
    # All 20 rows present
    for i in range(20):
        assert f"| skill-{i:02d} |" in result
    assert "Showing 20 enabled skills" not in result


@pytest.mark.asyncio
async def test_more_than_twenty_skills_caps_and_appends_footer():
    # The service queries with .limit(21) and trims; mock returns 21 rows
    rows = [
        {"name": f"skill-{i:02d}", "description": "d"}
        for i in range(21)
    ]
    client = _mock_client(rows)
    with patch(
        "app.services.skill_catalog_service.get_supabase_authed_client",
        return_value=client,
    ):
        result = await build_skill_catalog_block("u1", "tok")
    # First 20 rows visible; 21st (skill-20) is NOT in the table
    for i in range(20):
        assert f"| skill-{i:02d} |" in result
    assert "| skill-20 |" not in result
    # Footer present -- count-free phrasing (honest at any N > 20).
    assert (
        "Showing 20 enabled skills. More are available — "
        "call load_skill with any skill name to load it directly."
    ) in result


@pytest.mark.asyncio
async def test_alphabetical_ordering():
    # Service must call .order("name"); we verify the .order() call args
    client = MagicMock()
    chain = MagicMock()
    chain.execute.return_value.data = []
    chain.eq.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    chain.select.return_value = chain
    client.table.return_value = chain
    with patch(
        "app.services.skill_catalog_service.get_supabase_authed_client",
        return_value=client,
    ):
        await build_skill_catalog_block("u1", "tok")
    # The chain ought to have called .order("name") at least once
    order_calls = chain.order.call_args_list
    assert any(call.args == ("name",) or call.kwargs.get("column") == "name"
               for call in order_calls), \
        f"Expected .order('name') call, got: {order_calls}"


@pytest.mark.asyncio
async def test_filters_by_enabled_true():
    client = _mock_client([])
    chain = client.table.return_value
    with patch(
        "app.services.skill_catalog_service.get_supabase_authed_client",
        return_value=client,
    ):
        await build_skill_catalog_block("u1", "tok")
    # Verify .eq("enabled", True) is in the chain
    eq_calls = chain.eq.call_args_list
    assert any(
        call.args == ("enabled", True) for call in eq_calls
    ), f"Expected .eq('enabled', True), got: {eq_calls}"


@pytest.mark.asyncio
async def test_db_exception_returns_empty_string_fail_soft():
    """Per CONVENTIONS.md §Error Handling -- chat must not break because of catalog failure."""
    client = MagicMock()
    chain = MagicMock()
    chain.execute.side_effect = RuntimeError("boom")
    chain.eq.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    chain.select.return_value = chain
    client.table.return_value = chain
    with patch(
        "app.services.skill_catalog_service.get_supabase_authed_client",
        return_value=client,
    ):
        result = await build_skill_catalog_block("u1", "tok")
    assert result == ""


@pytest.mark.asyncio
async def test_empty_or_missing_token_returns_empty_string():
    """Defensive: don't crash if chat passes a falsy token."""
    result = await build_skill_catalog_block("u1", "")
    assert result == ""
    result = await build_skill_catalog_block("u1", None)  # type: ignore[arg-type]
    assert result == ""


@pytest.mark.asyncio
async def test_anti_speculation_guardrail_present():
    """D-P8-05: block must include the load_skill guardrail instruction."""
    client = _mock_client([{"name": "x-skill", "description": "d"}])
    with patch(
        "app.services.skill_catalog_service.get_supabase_authed_client",
        return_value=client,
    ):
        result = await build_skill_catalog_block("u1", "tok")
    assert "load_skill" in result
    assert "Only load a skill when there's a strong match" in result
