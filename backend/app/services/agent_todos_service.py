"""Phase 17 / v1.3 — Agent Todos service (TODO-02, TODO-03, TODO-05).

Full-replacement write semantic per D-06 (CONTEXT.md):
  write_todos deletes ALL existing rows for thread_id then re-inserts the
  new full list. Avoids partial-update edge cases and matches PRD Feature 1.2.

50-item defensive truncation cap (D-29) with warning.

All operations audit-logged via audit_service.log_action (D-34):
  - write_todos: action="write_todos", resource_type="agent_todos"
  - read_todos:  action="read_todos",  resource_type="agent_todos"

Security (T-17-06, T-17-07):
  - handler reads thread_id from ctx (server-set), NOT from LLM params
  - get_supabase_authed_client(token) is used exclusively (RLS-scoped)
  - service-role client is never instantiated here

Privacy (D-32):
  - This service operates on post-anonymization data (all PII already
    stripped by the upstream egress filter in chat.py before reaching LLM).
  - write_todos receives content from the LLM tool-call response, which has
    already passed through the anonymization layer.

Plan 17-04 wires this into the deep-mode chat loop (thread_id, user_id,
user_email are passed from get_current_user in chat.py).
"""

from __future__ import annotations

import logging
from typing import Literal, TypedDict

from app.database import get_supabase_authed_client
from app.services import audit_service

logger = logging.getLogger(__name__)

# D-29: defensive cap — truncate with warning when exceeded, never raise.
MAX_TODOS_PER_THREAD = 50


# ---------------------------------------------------------------------------
# Type helpers
# ---------------------------------------------------------------------------

TodoStatus = Literal["pending", "in_progress", "completed"]


class TodoInput(TypedDict):
    content: str
    status: TodoStatus


class TodoRecord(TypedDict):
    id: str
    content: str
    status: TodoStatus
    position: int


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def write_todos(
    thread_id: str,
    user_id: str,
    user_email: str,
    token: str,
    todos: list[TodoInput],
) -> list[TodoRecord]:
    """Full-replacement write of the per-thread todo list.

    Steps:
    1. Truncate input to MAX_TODOS_PER_THREAD (D-29) with a warning if exceeded.
    2. Delete ALL existing agent_todos rows for thread_id (D-06 full-replacement).
    3. Insert the new list with positions 0..N-1 assigned by order.
    4. Audit-log the operation (D-34).
    5. Return the canonical state via read_todos(_audit=False).

    Args:
        thread_id: Supabase UUID of the thread (server-set, not from LLM params — T-17-06).
        user_id: Supabase auth.users UUID.
        user_email: User's email for audit log.
        token: JWT access token — passed to get_supabase_authed_client() for RLS scope.
        todos: Ordered list of {content, status} dicts. Position is auto-assigned.

    Returns:
        Current canonical todo list (after write) ordered by position ASC.
    """
    # --- D-29: Defensive truncation cap ---
    if len(todos) > MAX_TODOS_PER_THREAD:
        logger.warning(
            "write_todos truncating %d -> %d items (thread_id=%s, D-29 cap)",
            len(todos),
            MAX_TODOS_PER_THREAD,
            thread_id,
        )
        todos = todos[:MAX_TODOS_PER_THREAD]

    # --- T-17-07: RLS-scoped authed client (never service-role) ---
    client = get_supabase_authed_client(token)

    # --- D-06: Full-replacement — delete then insert ---
    # eq() provides defense-in-depth even though RLS already scopes to auth.uid().
    client.table("agent_todos").delete().eq("thread_id", thread_id).execute()

    if todos:
        rows = [
            {
                "thread_id": thread_id,
                "user_id": user_id,
                "content": t["content"],
                "status": t["status"],
                "position": idx,
            }
            for idx, t in enumerate(todos)
        ]
        client.table("agent_todos").insert(rows).execute()

    # --- D-34: Audit log ---
    audit_service.log_action(
        user_id=user_id,
        user_email=user_email,
        action="write_todos",
        resource_type="agent_todos",
        resource_id=thread_id,
    )

    # Return canonical state without double-audit
    return await read_todos(thread_id, user_id, user_email, token, _audit=False)


async def read_todos(
    thread_id: str,
    user_id: str,
    user_email: str,
    token: str,
    *,
    _audit: bool = True,
) -> list[TodoRecord]:
    """Return the current todo list for thread_id, ordered by position ASC.

    D-30: parameterless from the LLM's perspective (thread_id comes from ctx).
    D-34: audit-logged on every call (set _audit=False when called internally).

    Args:
        thread_id: Thread to query.
        user_id:   User's UUID (for audit log).
        user_email: User's email (for audit log).
        token:     JWT access token for RLS-scoped Supabase client.
        _audit:    Internal flag — set False when called from write_todos to
                   avoid a double audit entry.

    Returns:
        List of {id, content, status, position} dicts ordered by position.
    """
    client = get_supabase_authed_client(token)
    result = (
        client.table("agent_todos")
        .select("id, content, status, position")
        .eq("thread_id", thread_id)
        .order("position")
        .execute()
    )
    rows: list[TodoRecord] = result.data or []

    if _audit:
        audit_service.log_action(
            user_id=user_id,
            user_email=user_email,
            action="read_todos",
            resource_type="agent_todos",
            resource_id=thread_id,
        )

    return rows
