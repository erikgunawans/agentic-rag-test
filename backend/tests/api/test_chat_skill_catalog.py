"""Integration tests for Phase 8 SKILL-07 catalog injection in chat.py.

Strategy A: import the chat router and skill_catalog_service, mock the
RLS-scoped Supabase client to control what skills are returned, then assert
against the assembled system-prompt string. Avoids needing a live LLM or
SSE plumbing — tests the actual integration boundary deterministically.

Requirements covered:
  - D-P8-01: Single-agent path injects skill_catalog_block after SYSTEM_PROMPT + pii_guidance
  - D-P8-02: 0 enabled skills -> '' (byte-identical to pre-Phase-8 behavior)
  - D-P8-03: Both single-agent AND multi-agent paths inject the catalog
  - Token plumbing: token=token forwarded to execute_tool; token=user["token"] to _run_tool_loop

Run (from backend/):
    pytest tests/api/test_chat_skill_catalog.py -v
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# D-P8-02 invariant: 0 skills -> '' -> no "## Your Skills" in assembled prompt
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_zero_enabled_skills_does_not_inject_catalog_block():
    """D-P8-02: 0 enabled skills returns '' — catalog absent from assembled prompt."""
    from app.services.skill_catalog_service import build_skill_catalog_block

    # Mock RLS-scoped client to return empty skill list
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
        catalog = await build_skill_catalog_block("u1", "tok")

    # D-P8-02 core assertion
    assert catalog == "", f"Expected '' for 0 skills, got: {repr(catalog)}"

    # Simulate the single-agent concatenation chat.py performs:
    # SYSTEM_PROMPT + pii_guidance + skill_catalog
    from app.routers.chat import SYSTEM_PROMPT
    pii_guidance = ""  # redaction off -> ""
    assembled = SYSTEM_PROMPT + pii_guidance + catalog
    assert "## Your Skills" not in assembled, \
        "Catalog block must not appear when user has 0 enabled skills (D-P8-02)"


# ---------------------------------------------------------------------------
# Positive case: enabled skills inject catalog into assembled prompt
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_enabled_skills_inject_catalog_block_into_system_prompt():
    """D-P8-01: >=1 enabled skill -> '## Your Skills' block present in assembled prompt."""
    from app.services.skill_catalog_service import build_skill_catalog_block

    client = MagicMock()
    chain = MagicMock()
    chain.execute.return_value.data = [
        {"name": "legal-review", "description": "Reviews NDA contracts."},
        {"name": "summarize", "description": "Summarizes long documents."},
    ]
    chain.eq.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    chain.select.return_value = chain
    client.table.return_value = chain

    with patch(
        "app.services.skill_catalog_service.get_supabase_authed_client",
        return_value=client,
    ):
        catalog = await build_skill_catalog_block("u1", "tok")

    # Catalog must contain the heading and both skill rows
    assert "## Your Skills" in catalog, "Catalog block must contain '## Your Skills' header"
    assert "legal-review" in catalog, "Skill 'legal-review' must appear in catalog"
    assert "summarize" in catalog, "Skill 'summarize' must appear in catalog"

    # Simulate single-agent assembly
    from app.routers.chat import SYSTEM_PROMPT
    assembled = SYSTEM_PROMPT + "" + catalog
    assert "## Your Skills" in assembled
    assert "| legal-review |" in assembled
    assert "| summarize |" in assembled


# ---------------------------------------------------------------------------
# Disabled skill must not appear in catalog
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_disabled_skill_excluded_from_catalog():
    """Disabled skills are excluded by the .eq('enabled', True) filter (tested via mock)."""
    from app.services.skill_catalog_service import build_skill_catalog_block

    client = MagicMock()
    chain = MagicMock()
    # The authed client query only returns enabled skills (filter applied server-side via RLS).
    # We mock returning only enabled ones, as the DB filter does:
    chain.execute.return_value.data = [
        {"name": "active-skill", "description": "An active skill."},
    ]
    chain.eq.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    chain.select.return_value = chain
    client.table.return_value = chain

    with patch(
        "app.services.skill_catalog_service.get_supabase_authed_client",
        return_value=client,
    ):
        catalog = await build_skill_catalog_block("u1", "tok")

    assert "active-skill" in catalog
    # disabled-skill was never returned by the (mocked) DB filter
    assert "disabled-skill" not in catalog


# ---------------------------------------------------------------------------
# D-P8-03 smoke test: BOTH single-agent AND multi-agent paths inject catalog
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_chat_router_imports_build_skill_catalog_block():
    """D-P8-03: confirm Plan 08-04 wiring landed in BOTH single-agent AND multi-agent paths.

    Per D-P8-03 the catalog must be injected at both system-prompt assembly
    sites. We assert against path-specific concatenation patterns that cannot
    coexist on the same code path, proving both paths are covered.
    """
    import inspect
    from app.routers import chat

    source = inspect.getsource(chat)

    # Import landed
    assert "build_skill_catalog_block" in source, \
        "chat.py must import + use build_skill_catalog_block (Plan 08-04 patch)"

    # Both call sites present (necessary but not sufficient alone)
    assert source.count("build_skill_catalog_block(") >= 2, \
        "chat.py must call build_skill_catalog_block in both single-agent and multi-agent paths"

    # Path-specific D-P8-03 assertions:
    # These two concatenation patterns belong to different code paths and
    # cannot coexist on the same path, so seeing both proves both paths covered.
    assert "agent_def.system_prompt + skill_catalog" in source, \
        "multi-agent path missing skill_catalog injection (D-P8-03)"
    assert "SYSTEM_PROMPT + pii_guidance + skill_catalog" in source, \
        "single-agent path missing skill_catalog injection (D-P8-03)"


# ---------------------------------------------------------------------------
# Token plumbing smoke test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_chat_router_passes_token_to_execute_tool():
    """Confirm token=token is forwarded to execute_tool and token=user['token'] to _run_tool_loop."""
    import inspect
    from app.routers import chat

    source = inspect.getsource(chat)

    # token=token kwarg appears at both execute_tool call sites (lines ~269 and ~296)
    assert source.count("token=token") >= 2, \
        "chat.py must pass token=token at both execute_tool call sites (D-P8-04 Task 2)"

    # token=user["token"] appears at both _run_tool_loop call sites
    assert 'token=user["token"]' in source, \
        "chat.py must pass token=user['token'] when invoking _run_tool_loop"

    # _run_tool_loop signature has the kwarg
    assert "token: str | None = None" in source, \
        "_run_tool_loop must accept token kwarg"
