"""Phase 19 / v1.3 — Agent Runs service (TASK-04, ASK-04, STATUS-05).

Tracks paused/resumable agent runs per thread (D-03 schema, D-04 resume detection).
Partial-unique constraint enforces at-most-one active run per thread (working|waiting_for_user).

All operations audit-logged via audit_service.log_action (D-23):
  - start_run, transition_status, complete, error → resource_type='agent_runs'

Security:
  - Reads thread_id from server-set ctx, NOT from LLM params.
  - Uses get_supabase_authed_client(token) exclusively (RLS-scoped).
  - service-role client is never instantiated here

Plan 19-05 wires this into the deep-mode chat loop (resume-detection branch in
stream_chat entry; ask_user pause persistence inside run_deep_mode_loop).
"""

from __future__ import annotations

import logging
from typing import Literal, TypedDict

from app.database import get_supabase_authed_client
from app.services import audit_service

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Type helpers
# ---------------------------------------------------------------------------

RunStatus = Literal["working", "waiting_for_user", "complete", "error"]


class AgentRunRecord(TypedDict):
    id: str
    thread_id: str
    status: RunStatus
    pending_question: str | None
    last_round_index: int
    error_detail: str | None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def start_run(
    thread_id: str,
    user_id: str,
    user_email: str,
    token: str,
) -> AgentRunRecord:
    """Insert a new 'working' run for the given thread.

    The partial-unique index (WHERE status IN ('working','waiting_for_user'))
    enforces at-most-one active run per thread. A second call while a run is
    active will raise a unique-violation exception from Supabase.

    Args:
        thread_id:  UUID of the thread (server-set, not from LLM params).
        user_id:    auth.users UUID of the requesting user.
        user_email: User's email for audit log.
        token:      JWT access token — used exclusively for RLS-scoped client.

    Returns:
        The newly inserted AgentRunRecord with status='working'.
    """
    client = get_supabase_authed_client(token)
    result = (
        client.table("agent_runs")
        .insert({
            "thread_id": thread_id,
            "user_id": user_id,
            "status": "working",
            "last_round_index": 0,
        })
        .execute()
    )
    audit_service.log_action(
        user_id=user_id,
        user_email=user_email,
        action="agent_run_start",
        resource_type="agent_runs",
        resource_id=thread_id,
    )
    return result.data[0]


async def set_pending_question(
    run_id: str,
    question: str,
    last_round_index: int,
    token: str,
) -> None:
    """Transition an active run to 'waiting_for_user' with a pending question.

    Uses a transactional UPDATE WHERE status='working' to guard against the
    documented v1.3 single-process race window (T-19-RACE). If 0 rows are
    affected, the run was already transitioned (concurrent call or prior pause);
    logs a warning but does not raise.

    Args:
        run_id:            UUID of the agent_runs row to update.
        question:          The question string to store in pending_question.
        last_round_index:  Current loop iteration index to persist for resume.
        token:             JWT access token for RLS-scoped client.
    """
    client = get_supabase_authed_client(token)
    result = (
        client.table("agent_runs")
        .update({
            "status": "waiting_for_user",
            "pending_question": question,
            "last_round_index": last_round_index,
        })
        .eq("id", run_id)
        .eq("status", "working")  # transactional guard — race mitigation (T-19-RACE)
        .execute()
    )
    if not result.data:
        logger.warning(
            "set_pending_question affected 0 rows run_id=%s — possibly already paused",
            run_id,
        )


async def transition_status(
    run_id: str,
    new_status: RunStatus,
    token: str,
    *,
    error_detail: str | None = None,
    user_id: str | None = None,
    user_email: str | None = None,
) -> None:
    """Update the status of an agent run.

    For 'complete' status, also clears pending_question to satisfy the
    bidirectional CHECK invariant (status='waiting_for_user') = (pending_question IS NOT NULL).

    Args:
        run_id:       UUID of the agent_runs row.
        new_status:   Target status — one of 'working', 'waiting_for_user', 'complete', 'error'.
        token:        JWT access token for RLS-scoped client.
        error_detail: Optional error description (used when new_status='error').
        user_id:      auth.users UUID for audit log (optional for backward compat).
        user_email:   User's email for audit log (optional for backward compat).
    """
    client = get_supabase_authed_client(token)
    update_payload: dict = {"status": new_status}
    if new_status == "complete":
        update_payload["pending_question"] = None  # clear pending_question on complete
    if error_detail is not None:
        update_payload["error_detail"] = error_detail
    client.table("agent_runs").update(update_payload).eq("id", run_id).execute()

    audit_service.log_action(
        user_id=user_id,
        user_email=user_email,
        action=f"agent_run_transition_{new_status}",
        resource_type="agent_runs",
        resource_id=run_id,
    )


async def complete(
    run_id: str,
    token: str,
    user_id: str,
    user_email: str,
) -> None:
    """Mark an agent run as complete and emit an audit log entry.

    Args:
        run_id:     UUID of the agent_runs row.
        token:      JWT access token for RLS-scoped client.
        user_id:    auth.users UUID for audit log.
        user_email: User's email for audit log.
    """
    client = get_supabase_authed_client(token)
    client.table("agent_runs").update({
        "status": "complete",
        "pending_question": None,  # clear to satisfy CHECK invariant
    }).eq("id", run_id).execute()

    audit_service.log_action(
        user_id=user_id,
        user_email=user_email,
        action="agent_run_complete",
        resource_type="agent_runs",
        resource_id=run_id,
    )


async def error(
    run_id: str,
    token: str,
    user_id: str,
    user_email: str,
    *,
    error_detail: str,
) -> None:
    """Mark an agent run as errored and persist the error detail.

    error_detail is truncated to 500 chars (D-19 sanitized — no stack trace
    leakage to the DB).

    Args:
        run_id:       UUID of the agent_runs row.
        token:        JWT access token for RLS-scoped client.
        user_id:      auth.users UUID for audit log.
        user_email:   User's email for audit log.
        error_detail: Error description; truncated to 500 chars.
    """
    truncated = error_detail[:500]  # D-19 sanitization
    client = get_supabase_authed_client(token)
    client.table("agent_runs").update({
        "status": "error",
        "error_detail": truncated,
    }).eq("id", run_id).execute()

    audit_service.log_action(
        user_id=user_id,
        user_email=user_email,
        action="agent_run_error",
        resource_type="agent_runs",
        resource_id=run_id,
    )


async def get_active_run(thread_id: str, token: str) -> AgentRunRecord | None:
    """Return the active run for a thread, or None if no active run exists.

    'Active' means status IN ('working', 'waiting_for_user'). The partial
    unique index enforces at-most-one such row per thread, so this lookup
    always returns 0 or 1 rows.

    Used by the resume-detection branch in stream_chat (D-04) to detect
    paused runs awaiting a user reply.

    Args:
        thread_id: UUID of the thread to look up.
        token:     JWT access token for RLS-scoped client.

    Returns:
        AgentRunRecord if an active run exists; None otherwise.
    """
    client = get_supabase_authed_client(token)
    result = (
        client.table("agent_runs")
        .select("id, thread_id, status, pending_question, last_round_index, error_detail")
        .eq("thread_id", thread_id)
        .in_("status", ["working", "waiting_for_user"])
        .execute()
    )
    rows = result.data or []
    return rows[0] if rows else None
