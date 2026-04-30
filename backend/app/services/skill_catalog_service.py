"""SKILL-07: enabled-skills catalog builder for the LLM system prompt.

Plan 08-02. Single source of truth for the '## Your Skills' block injected
by chat.py (Plan 08-04) into both single-agent and multi-agent system
prompts.

Decisions enforced:
  - D-P8-02: returns '' when the user has 0 enabled skills (chat path is
    byte-identical to current behavior when feature unused).
  - D-P8-05: markdown table format with anti-speculation guardrail.
  - D-P8-06: cap 20 enabled skills, alphabetical by name.
  - D-P8-07: count-free truncation footer when N > 20.

Fail-soft (CONVENTIONS.md §Error Handling): any DB exception returns ''
rather than propagating, so a transient skills-table issue cannot break
the chat request.
"""
from __future__ import annotations

import logging

from app.database import get_supabase_authed_client

logger = logging.getLogger(__name__)


# D-P8-05: anti-speculation guardrail + markdown table header.
# Imperative phrasing mirrors prompt_guidance.py D-82 convention.
_CATALOG_HEADER = (
    "\n\n## Your Skills\n"
    "Call `load_skill` with the skill name when the user's request clearly\n"
    "matches a skill. Only load a skill when there's a strong match.\n\n"
    "| Skill | Description |\n"
    "|-------|-------------|"
)

# D-P8-07: count-free truncation footer. Honest at any N > 20 without a
# separate COUNT query (we only fetch up to 21 rows to detect overflow).
_TRUNCATION_FOOTER = (
    "Showing 20 enabled skills. More are available — "
    "call load_skill with any skill name to load it directly."
)


def _format_table_row(name: str, description: str) -> str:
    # Sanitize pipes inside descriptions so the markdown table doesn't break.
    # Skills come from user input via Phase 7 endpoints, so we cannot trust
    # the absence of '|' or newline characters.
    safe_desc = (description or "").replace("|", "\\|").replace("\n", " ").strip()
    safe_name = (name or "").replace("|", "\\|").strip()
    return f"| {safe_name} | {safe_desc} |"


async def build_skill_catalog_block(user_id: str, token: str) -> str:
    """Return the '## Your Skills' system-prompt block, or '' if no enabled skills.

    Args:
        user_id: caller's UUID. Currently used only for logging — RLS does
            the actual auth filter via the JWT token.
        token: caller's Supabase JWT. Used to construct an RLS-scoped client
            so SELECT auto-filters to (user_id = auth.uid() OR user_id IS NULL).
            A falsy token returns '' (defensive — should not happen in chat.py
            since user['token'] is always present after Depends(get_current_user)).

    Returns:
        A markdown block ready to concatenate to the system prompt, or
        ''  when there are 0 enabled skills (D-P8-02).
    """
    if not token:
        return ""

    try:
        client = get_supabase_authed_client(token)
        # Fetch up to 21 to detect truncation per D-P8-07.
        # RLS auto-applies user_id = auth.uid() OR user_id IS NULL.
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
        # Fail-soft: chat must keep working even if the skills query breaks.
        logger.warning(
            "build_skill_catalog_block failed for user_id=%s: %s", user_id, e
        )
        return ""

    if not rows:
        return ""  # D-P8-02

    # D-P8-06: cap at 20. Build table rows from first 20 only.
    visible = rows[:20]
    table_rows = "\n".join(
        _format_table_row(r.get("name", ""), r.get("description", ""))
        for r in visible
    )

    block = f"{_CATALOG_HEADER}\n{table_rows}"

    # D-P8-07: append count-free truncation footer when more than 20 skills.
    # We fetched 21 rows; if len(rows) > 20 we know the user has more skills
    # available than we displayed, but we do NOT know the exact total
    # (avoiding a separate COUNT query). The footer phrasing is honest at
    # any N: "Showing 20 enabled skills. More are available — ..."
    if len(rows) > 20:
        block += f"\n\n{_TRUNCATION_FOOTER}"

    return block
