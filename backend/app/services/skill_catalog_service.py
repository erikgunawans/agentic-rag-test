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


# ---------------------------------------------------------------------------
# Phase 13 D-P13-02: register skills as first-class registry tools (TOOL-04).
#
# The legacy build_skill_catalog_block above is preserved verbatim and remains
# the catalog builder used when settings.tool_registry_enabled=False (TOOL-05
# byte-identical fallback). This new helper is invoked by chat.py only when
# the flag is True (Plan 13-05 wiring).
# ---------------------------------------------------------------------------


def _make_skill_executor(skill_name: str):
    """Return an async closure that loads the skill via ToolService.execute_tool.

    Per D-P13-02: skill executors delegate to the existing Phase 8 load_skill
    dispatch — no re-implementation of skill loading logic. The closure
    captures `skill_name` via a default-arg `_name: str = skill_name` to avoid
    the late-binding loop-variable bug (every iteration shares the same `_name`
    only if we don't re-bind, which Test 6 verifies).
    """
    async def _executor(
        arguments: dict,
        user_id: str,
        context: dict | None = None,
        *,
        _name: str = skill_name,
        **kwargs,
    ) -> dict | str:
        # Lazy import: avoid a circular import at module load (tool_service
        # imports skill_catalog_service via TOOL_DEFINITIONS dispatch chain).
        # Module-local ToolService instance — chat.py owns its own; we use a
        # private one here so registration works at request time even if
        # chat.py's instance has not been touched yet.
        from app.services.tool_service import ToolService

        _svc = ToolService()
        return await _svc.execute_tool(
            "load_skill",
            {"name": _name},
            user_id,
            context,
            **kwargs,
        )

    return _executor


async def register_user_skills(user_id: str, token: str) -> None:
    """D-P13-02: register every enabled skill for this user as a first-class tool.

    Per-request DB query (CONTEXT.md §Discretion §Skill registration timing):
    skills are re-registered fresh on every chat request from the user's
    RLS-scoped client. ~5-20ms latency is acceptable; avoids stale-skill
    and skill-mutation invalidation complexity.

    Fail-soft: any DB exception logs at WARNING and returns silently. The
    chat flow must never break because of registry skill registration errors.

    Args:
        user_id: caller's UUID. Used only for logging — RLS does the actual
            auth filter via the JWT token.
        token: caller's Supabase JWT. Used to construct an RLS-scoped client
            so SELECT auto-filters to (user_id = auth.uid() OR user_id IS NULL).
            Falsy token returns silently (defensive — should not happen in
            chat.py since user['token'] is always present after Depends).
    """
    if not token:
        return
    try:
        client = get_supabase_authed_client(token)
        result = (
            client.table("skills")
            .select("name, description")
            .eq("enabled", True)
            .order("name")
            .execute()
        )
        rows = result.data or []
    except Exception as e:  # noqa: BLE001 — fail-soft per CONTEXT.md
        logger.warning(
            "register_user_skills failed for user_id=%s: %s", user_id, e
        )
        return
    if not rows:
        return
    # Lazy import: avoid loading the registry module on flag-off code paths
    # that happen to import skill_catalog_service for build_skill_catalog_block.
    from app.services import tool_registry

    for row in rows:
        name = row.get("name")
        if not name:
            continue
        description = row.get("description") or ""
        schema = {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
        }
        tool_registry.register(
            name=name,
            description=description,
            schema=schema,
            source="skill",
            loading="deferred",
            executor=_make_skill_executor(name),
        )
