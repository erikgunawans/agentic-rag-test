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


# ===========================================================================
# Phase 13 Plan 03 — register_user_skills + _make_skill_executor
# ===========================================================================

from unittest.mock import AsyncMock


def _mock_client_v13(rows):
    """Phase 13 Supabase chain mock — no .limit() in register_user_skills.

    Chain: client.table('skills').select(...).eq(...).order(...).execute()
    """
    client = MagicMock()
    chain = MagicMock()
    chain.execute.return_value.data = rows
    chain.eq.return_value = chain
    chain.order.return_value = chain
    chain.select.return_value = chain
    client.table.return_value = chain
    return client


@pytest.fixture(autouse=False)
def _reset_registry():
    """Opt-in fixture to clear the tool_registry between Phase 13 tests."""
    from app.services import tool_registry

    tool_registry._clear_for_tests()
    yield
    tool_registry._clear_for_tests()


@pytest.mark.asyncio
async def test_register_user_skills_two_skills(_reset_registry):
    """Test 1: 2 enabled skills → 2 entries in _REGISTRY with source/loading set."""
    from app.services import tool_registry
    from app.services.skill_catalog_service import register_user_skills

    rows = [
        {"name": "legal_review", "description": "Reviews NDA contracts."},
        {"name": "compliance_check", "description": "Checks GDPR compliance."},
    ]
    client = _mock_client_v13(rows)
    with patch(
        "app.services.skill_catalog_service.get_supabase_authed_client",
        return_value=client,
    ):
        await register_user_skills("u1", "tok")

    # After Plan 13-04 lands, _clear_for_tests leaves tool_search registered
    # too — assert subset (skills present) rather than count-equality.
    skill_names = {"legal_review", "compliance_check"}
    assert skill_names <= set(tool_registry._REGISTRY.keys())
    for name in skill_names:
        td = tool_registry._REGISTRY[name]
        assert td.source == "skill"
        assert td.loading == "deferred"


@pytest.mark.asyncio
async def test_register_user_skills_parameterless_schema(_reset_registry):
    """Test 2: schema is the parameterless OpenAI shape with name + description."""
    from app.services import tool_registry
    from app.services.skill_catalog_service import register_user_skills

    rows = [{"name": "legal_review", "description": "Reviews NDA contracts."}]
    client = _mock_client_v13(rows)
    with patch(
        "app.services.skill_catalog_service.get_supabase_authed_client",
        return_value=client,
    ):
        await register_user_skills("u1", "tok")

    schema = tool_registry._REGISTRY["legal_review"].schema
    assert schema == {
        "type": "function",
        "function": {
            "name": "legal_review",
            "description": "Reviews NDA contracts.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    }


@pytest.mark.asyncio
async def test_register_user_skills_falsy_token_returns_silent(_reset_registry):
    """Test 3: empty/None token → no DB call, no registration."""
    from app.services import tool_registry
    from app.services.skill_catalog_service import register_user_skills

    with patch(
        "app.services.skill_catalog_service.get_supabase_authed_client"
    ) as mock_client_factory:
        await register_user_skills("u1", "")
        await register_user_skills("u1", None)  # type: ignore[arg-type]

    mock_client_factory.assert_not_called()
    # tool_search auto-registered (Plan 13-04); no skill names should be present.
    skill_names_present = {
        n for n, td in tool_registry._REGISTRY.items() if td.source == "skill"
    }
    assert skill_names_present == set()


@pytest.mark.asyncio
async def test_register_user_skills_db_error_fail_soft(_reset_registry, caplog):
    """Test 4: DB exception → WARNING logged, no propagation, no registration."""
    from app.services import tool_registry
    from app.services.skill_catalog_service import register_user_skills

    client = MagicMock()
    chain = MagicMock()
    chain.execute.side_effect = RuntimeError("boom")
    chain.eq.return_value = chain
    chain.order.return_value = chain
    chain.select.return_value = chain
    client.table.return_value = chain

    with patch(
        "app.services.skill_catalog_service.get_supabase_authed_client",
        return_value=client,
    ), caplog.at_level("WARNING"):
        # Must NOT raise
        await register_user_skills("u1", "tok")

    assert any(
        "register_user_skills failed" in rec.getMessage() for rec in caplog.records
    )
    skill_names_present = {
        n for n, td in tool_registry._REGISTRY.items() if td.source == "skill"
    }
    assert skill_names_present == set()


@pytest.mark.asyncio
async def test_register_user_skills_zero_rows_no_registration(_reset_registry):
    """Test 5: empty result set → no registration."""
    from app.services import tool_registry
    from app.services.skill_catalog_service import register_user_skills

    client = _mock_client_v13([])
    with patch(
        "app.services.skill_catalog_service.get_supabase_authed_client",
        return_value=client,
    ):
        await register_user_skills("u1", "tok")
    skill_names_present = {
        n for n, td in tool_registry._REGISTRY.items() if td.source == "skill"
    }
    assert skill_names_present == set()


@pytest.mark.asyncio
async def test_skill_executor_delegates_to_load_skill(_reset_registry):
    """Test 6: closure invokes ToolService.execute_tool('load_skill', {'name': <skill>})."""
    from app.services import tool_registry
    from app.services.skill_catalog_service import register_user_skills
    from app.services.tool_service import ToolService

    rows = [
        {"name": "legal_review", "description": "Reviews NDA contracts."},
        {"name": "compliance_check", "description": "Checks GDPR compliance."},
    ]
    client = _mock_client_v13(rows)

    with patch(
        "app.services.skill_catalog_service.get_supabase_authed_client",
        return_value=client,
    ), patch.object(
        ToolService,
        "execute_tool",
        new=AsyncMock(return_value={"instructions": "..."}),
    ) as mock_execute:
        await register_user_skills("u1", "tok")

        # Invoke each closure and verify the right name is passed
        for skill_name in ("legal_review", "compliance_check"):
            td = tool_registry._REGISTRY[skill_name]
            await td.executor(arguments={}, user_id="u1", context={})

        # Each closure called execute_tool with ("load_skill", {"name": skill_name}, ...)
        called = [(c.args[0], c.args[1]) for c in mock_execute.await_args_list]
        assert ("load_skill", {"name": "legal_review"}) in called
        assert ("load_skill", {"name": "compliance_check"}) in called


@pytest.mark.asyncio
async def test_register_user_skills_idempotent_first_write_wins(_reset_registry, caplog):
    """Test 7: re-registering the same skills logs WARNINGs but doesn't double-add."""
    from app.services import tool_registry
    from app.services.skill_catalog_service import register_user_skills

    rows = [
        {"name": "legal_review", "description": "Reviews NDA contracts."},
        {"name": "compliance_check", "description": "Checks GDPR compliance."},
    ]
    client = _mock_client_v13(rows)

    with patch(
        "app.services.skill_catalog_service.get_supabase_authed_client",
        return_value=client,
    ), caplog.at_level("WARNING"):
        await register_user_skills("u1", "tok")
        skill_count_first = sum(
            1 for td in tool_registry._REGISTRY.values() if td.source == "skill"
        )
        assert skill_count_first == 2
        await register_user_skills("u1", "tok")

    # Still 2 skills (first-write-wins)
    skill_count_second = sum(
        1 for td in tool_registry._REGISTRY.values() if td.source == "skill"
    )
    assert skill_count_second == 2
    # WARNINGs emitted for each duplicate
    duplicate_warnings = [
        r for r in caplog.records if "duplicate name" in r.getMessage()
    ]
    assert len(duplicate_warnings) >= 2
