"""ADR-0008: classifier must respect available_tool_names.

When ``web_search`` is unavailable (admin toggle off), the intent classifier
MUST NOT pick the ``general`` agent because it would have no tools. We add
a keyword-only ``available_tool_names`` parameter to ``classify_intent``;
the function:

1. Computes ``eligible_agents`` = agents whose ``tool_names`` intersect with
   the available set (or have empty ``tool_names``).
2. Injects an AVAILABLE TOOLS / ELIGIBLE AGENTS constraint block into the
   classifier prompt so the LLM picks an eligible agent.
3. Defense-in-depth: if the LLM ignores the constraint, override to the
   first eligible agent (and prefix reasoning with ``[constraint-override]``).

Backward compatibility: when ``available_tool_names is None``, behavior is
identical to the prior baseline (SC#5 invariant — no prompt change, no
override).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.agent_service import AGENT_REGISTRY, classify_intent


@pytest.mark.asyncio
async def test_classifier_skips_general_when_web_search_unavailable():
    """When ``available_tool_names`` excludes web_search, classifier must pick
    research (or another eligible agent), never general."""
    fake_openrouter = MagicMock()
    # The (anonymized) LLM honors the constraint and picks research.
    fake_openrouter.complete_with_tools = AsyncMock(
        return_value={
            "content": '{"agent": "research", "reasoning": "internal-only constraint"}'
        }
    )

    result = await classify_intent(
        "What is the latest news on contract law in Indonesia?",
        [],
        fake_openrouter,
        "anthropic/claude-sonnet-4-6",
        available_tool_names=["search_documents", "query_database"],  # no web_search
    )

    assert result.agent == "research"


@pytest.mark.asyncio
async def test_classifier_overrides_when_llm_picks_ineligible_agent():
    """Defense in depth: if the LLM picks general despite the constraint,
    the function must override to the first eligible agent."""
    fake_openrouter = MagicMock()
    # LLM ignores the constraint and picks general (which needs web_search).
    fake_openrouter.complete_with_tools = AsyncMock(
        return_value={
            "content": '{"agent": "general", "reasoning": "I want web_search"}'
        }
    )

    result = await classify_intent(
        "latest news",
        [],
        fake_openrouter,
        "anthropic/claude-sonnet-4-6",
        available_tool_names=["search_documents"],
    )

    # Override should kick in — general is not eligible.
    assert result.agent != "general"
    # Should fall back to an eligible agent.
    available_set = {"search_documents"}
    eligible = [
        name
        for name, defn in AGENT_REGISTRY.items()
        if not defn.tool_names or any(t in available_set for t in defn.tool_names)
    ]
    assert result.agent in eligible
