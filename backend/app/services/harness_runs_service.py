"""Phase 20 / v1.3 — Harness Runs service (HARN-01, MIG-03, D-01).

Tracks harness execution state per thread (status pending/running/paused/completed/failed/cancelled).
Partial-unique constraint enforces at-most-one active run per thread (pending|running|paused).

Direct sibling of agent_runs_service.py (Phase 19 plan 19-02) — same shape, harness-specific columns.

Security:
  - Reads thread_id from caller-supplied ctx; never from LLM tool params.
  - Uses get_supabase_authed_client(token) exclusively (RLS-scoped).
  - Cross-tenant isolation enforced by RLS policy in migration 042.
"""
from __future__ import annotations

import logging
from typing import Any, Literal, TypedDict

from app.database import get_supabase_authed_client
from app.services import audit_service

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Type helpers
# ---------------------------------------------------------------------------

RunStatus = Literal["pending", "running", "paused", "completed", "failed", "cancelled"]

ACTIVE_STATUSES: tuple[str, ...] = ("pending", "running", "paused")
TERMINAL_STATUSES: tuple[str, ...] = ("completed", "failed", "cancelled")

_ERROR_DETAIL_MAX = 500


class HarnessRunRecord(TypedDict):
    id: str
    thread_id: str
    user_id: str
    harness_type: str
    status: RunStatus
    current_phase: int
    phase_results: dict[str, Any]
    input_file_ids: list[str]
    error_detail: str | None
    created_at: str
    updated_at: str


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def start_run(
    *,
    thread_id: str,
    user_id: str,
    user_email: str,
    harness_type: str,
    input_file_ids: list[str] | None,
    token: str,
) -> str:
    """Insert a new 'pending' harness run for the given thread.

    The partial-unique index (WHERE status IN ('pending','running','paused'))
    enforces at-most-one active run per thread. A second call while a run is
    active will raise a unique-violation exception from Supabase.

    Args:
        thread_id:      UUID of the thread (server-set, not from LLM params).
        user_id:        auth.users UUID of the requesting user.
        user_email:     User's email for audit log.
        harness_type:   Registered harness key (e.g. 'contract-review').
        input_file_ids: Optional list of workspace file UUIDs to feed as input.
        token:          JWT access token — used exclusively for RLS-scoped client.

    Returns:
        The new row's id (UUID string).
    """
    client = get_supabase_authed_client(token)
    result = (
        client.table("harness_runs")
        .insert({
            "thread_id": thread_id,
            "user_id": user_id,
            "harness_type": harness_type,
            "status": "pending",
            "current_phase": 0,
            "phase_results": {},
            "input_file_ids": input_file_ids or [],
        })
        .execute()
    )
    run_id: str = result.data[0]["id"]
    audit_service.log_action(
        user_id=user_id,
        user_email=user_email,
        action="harness_run_started",
        resource_type="harness_runs",
        resource_id=run_id,
    )
    return run_id


async def get_active_run(*, thread_id: str, token: str) -> HarnessRunRecord | None:
    """Return the active run for a thread, or None if no active run exists.

    'Active' means status IN ('pending', 'running', 'paused'). The partial
    unique index enforces at-most-one such row per thread, so this lookup
    always returns 0 or 1 rows.

    Used by D-02 gatekeeper to reject new harness start when one is already
    running, and by D-04 post-harness routing.

    Args:
        thread_id: UUID of the thread to look up.
        token:     JWT access token for RLS-scoped client.

    Returns:
        HarnessRunRecord if an active run exists; None otherwise.
    """
    client = get_supabase_authed_client(token)
    result = (
        client.table("harness_runs")
        .select(
            "id, thread_id, user_id, harness_type, status, current_phase, "
            "phase_results, input_file_ids, error_detail, created_at, updated_at"
        )
        .eq("thread_id", thread_id)
        .in_("status", list(ACTIVE_STATUSES))
        .execute()
    )
    rows = result.data or []
    return rows[0] if rows else None


async def get_run_by_id(*, run_id: str, token: str) -> HarnessRunRecord | None:
    """Return a harness run by its primary key, or None if not found.

    Used by the engine's B3 cross-request cancel poll: before each phase dispatch
    the engine calls this to check harness_runs.status == 'cancelled' set by a
    separate /cancel-harness POST on a different HTTP request.

    Args:
        run_id: UUID of the harness_runs row.
        token:  JWT access token for RLS-scoped client.

    Returns:
        HarnessRunRecord if found; None otherwise.
    """
    client = get_supabase_authed_client(token)
    result = (
        client.table("harness_runs")
        .select(
            "id, thread_id, user_id, harness_type, status, current_phase, "
            "phase_results, input_file_ids, error_detail, created_at, updated_at"
        )
        .eq("id", run_id)
        .execute()
    )
    rows = result.data or []
    return rows[0] if rows else None


async def get_latest_for_thread(*, thread_id: str, token: str) -> HarnessRunRecord | None:
    """Return the most-recently created harness run for a thread (any status).

    Used by D-05 gatekeeper-eligibility: gatekeeper only triggers when no
    active OR terminal run exists for the thread within a recency window.

    Args:
        thread_id: UUID of the thread to look up.
        token:     JWT access token for RLS-scoped client.

    Returns:
        The most recent HarnessRunRecord, or None if no runs exist for thread.
    """
    client = get_supabase_authed_client(token)
    result = (
        client.table("harness_runs")
        .select(
            "id, thread_id, user_id, harness_type, status, current_phase, "
            "phase_results, input_file_ids, error_detail, created_at, updated_at"
        )
        .eq("thread_id", thread_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    rows = result.data or []
    return rows[0] if rows else None


async def advance_phase(
    *,
    run_id: str,
    new_phase_index: int,
    phase_results_patch: dict[str, Any],
    token: str,
) -> bool:
    """Advance the harness to the next phase, merging phase_results.

    Transitions status to 'running' on first advance (pending → running).
    Transactional guard: .in_("status", ["pending", "running"]) ensures the
    update is rejected when the row has already reached a terminal state.

    Implementation note: Fetch current phase_results, deep-merge the patch
    (last-writer-wins on key collision), then write back. Phase 20 plan
    guarantees disjoint {phase_index: result_object} keys so no collision
    occurs in practice.

    Args:
        run_id:              UUID of the harness_runs row to update.
        new_phase_index:     New value for current_phase.
        phase_results_patch: Dict to merge into existing phase_results JSONB.
        token:               JWT access token for RLS-scoped client.

    Returns:
        True if update affected ≥1 row; False if 0 rows (race-guard triggered).
    """
    client = get_supabase_authed_client(token)

    # Fetch current phase_results for merge
    fetch_result = (
        client.table("harness_runs")
        .select("phase_results")
        .eq("id", run_id)
        .execute()
    )
    current_phase_results: dict[str, Any] = {}
    if fetch_result.data:
        current_phase_results = fetch_result.data[0].get("phase_results") or {}

    merged = {**current_phase_results, **phase_results_patch}

    result = (
        client.table("harness_runs")
        .update({
            "status": "running",
            "current_phase": new_phase_index,
            "phase_results": merged,
        })
        .eq("id", run_id)
        .in_("status", ["pending", "running"])  # transactional guard (T-20-02-01)
        .execute()
    )

    if not result.data:
        logger.warning(
            "advance_phase affected 0 rows run_id=%s — possibly already terminal",
            run_id,
        )
        return False
    return True


async def complete(
    *,
    run_id: str,
    user_id: str,
    user_email: str,
    token: str,
) -> bool:
    """Mark a harness run as completed.

    Transactional guard: .eq("status", "running") — only a running run can
    be completed. Returns False if 0 rows affected.

    Args:
        run_id:     UUID of the harness_runs row.
        user_id:    auth.users UUID for audit log.
        user_email: User's email for audit log.
        token:      JWT access token for RLS-scoped client.

    Returns:
        True if update succeeded; False if guard rejected (already terminal).
    """
    client = get_supabase_authed_client(token)
    result = (
        client.table("harness_runs")
        .update({"status": "completed"})
        .eq("id", run_id)
        .eq("status", "running")  # transactional guard
        .execute()
    )
    audit_service.log_action(
        user_id=user_id,
        user_email=user_email,
        action="harness_run_completed",
        resource_type="harness_runs",
        resource_id=run_id,
    )
    return bool(result.data)


async def fail(
    *,
    run_id: str,
    user_id: str,
    user_email: str,
    error_detail: str,
    token: str,
) -> bool:
    """Mark a harness run as failed and persist the (truncated) error detail.

    No transactional guard — failure can transition from any non-terminal state
    (pending/running/paused). error_detail is truncated to _ERROR_DETAIL_MAX
    chars before persistence (D-19 sanitization analog — caps accidental
    prompt/PII leak).

    Args:
        run_id:       UUID of the harness_runs row.
        user_id:      auth.users UUID for audit log.
        user_email:   User's email for audit log.
        error_detail: Error description; truncated to 500 chars.
        token:        JWT access token for RLS-scoped client.

    Returns:
        True if update succeeded; False if 0 rows affected.
    """
    truncated = error_detail[:_ERROR_DETAIL_MAX]  # D-19 / T-20-02-02 sanitization
    client = get_supabase_authed_client(token)
    result = (
        client.table("harness_runs")
        .update({
            "status": "failed",
            "error_detail": truncated,
        })
        .eq("id", run_id)
        .execute()
    )
    audit_service.log_action(
        user_id=user_id,
        user_email=user_email,
        action="harness_run_failed",
        resource_type="harness_runs",
        resource_id=run_id,
    )
    return bool(result.data)


async def cancel(
    *,
    run_id: str,
    user_id: str,
    user_email: str,
    token: str,
) -> bool:
    """Mark a harness run as cancelled.

    Transactional guard: .in_("status", ACTIVE_STATUSES) — only an active run
    can be cancelled. Returns False if 0 rows affected (already terminal).

    Args:
        run_id:     UUID of the harness_runs row.
        user_id:    auth.users UUID for audit log.
        user_email: User's email for audit log.
        token:      JWT access token for RLS-scoped client.

    Returns:
        True if update succeeded; False if guard rejected (already terminal).
    """
    client = get_supabase_authed_client(token)
    result = (
        client.table("harness_runs")
        .update({"status": "cancelled"})
        .eq("id", run_id)
        .in_("status", list(ACTIVE_STATUSES))  # transactional guard
        .execute()
    )
    audit_service.log_action(
        user_id=user_id,
        user_email=user_email,
        action="harness_run_cancelled",
        resource_type="harness_runs",
        resource_id=run_id,
    )
    return bool(result.data)


async def pause(
    *,
    run_id: str,
    user_id: str,
    user_email: str,
    token: str,
) -> HarnessRunRecord | None:
    """Mark a harness run as paused.

    Phase 21 / HIL-03: called by harness_engine LLM_HUMAN_INPUT dispatcher
    before yielding harness_complete{status=paused}. Transactional guard
    .in_("status", ["running"]) ensures we only pause an actually-running row;
    attempting to pause a pending/paused/terminal row returns None (caller
    should treat as a no-op signal).

    Args:
        run_id:     UUID of the harness_runs row.
        user_id:    auth.users UUID for audit log.
        user_email: User's email for audit log.
        token:      JWT access token for RLS-scoped client.

    Returns:
        The updated HarnessRunRecord on success; None if guard rejected.
    """
    client = get_supabase_authed_client(token)
    result = (
        client.table("harness_runs")
        .update({"status": "paused"})
        .eq("id", run_id)
        .in_("status", ["running"])  # transactional guard — only running can pause
        .execute()
    )
    if not result.data:
        logger.warning(
            "pause affected 0 rows run_id=%s — possibly not running",
            run_id,
        )
        return None
    audit_service.log_action(
        user_id=user_id,
        user_email=user_email,
        action="harness_run_paused",
        resource_type="harness_runs",
        resource_id=run_id,
    )
    return result.data[0]


async def resume_from_pause(
    *,
    run_id: str,
    new_phase_index: int,
    phase_results_patch: dict[str, Any],
    user_id: str,
    user_email: str,
    token: str,
) -> HarnessRunRecord | None:
    """Resume a paused harness run, advancing the phase and merging results.

    Phase 21 / HIL-04: called by chat.py HIL resume branch (Plan 21-04) after
    the user answers the paused question. Atomically transitions paused →
    running, sets current_phase = new_phase_index, and deep-merges
    phase_results_patch into existing phase_results JSONB.

    Transactional guard .in_("status", ["paused"]) ensures only paused rows
    can be resumed (defends against double-resume / status-drift races).

    Args:
        run_id:              UUID of the harness_runs row.
        new_phase_index:     Phase to resume FROM (typically pause_phase + 1).
        phase_results_patch: Dict to deep-merge into existing phase_results.
        user_id:             auth.users UUID for audit log.
        user_email:          User's email for audit log.
        token:               JWT access token for RLS-scoped client.

    Returns:
        The updated HarnessRunRecord on success; None if guard rejected.
    """
    client = get_supabase_authed_client(token)

    # Fetch current phase_results for merge (mirrors advance_phase pattern)
    fetch_result = (
        client.table("harness_runs")
        .select("phase_results")
        .eq("id", run_id)
        .execute()
    )
    current_phase_results: dict[str, Any] = {}
    if fetch_result.data:
        current_phase_results = fetch_result.data[0].get("phase_results") or {}

    merged = {**current_phase_results, **phase_results_patch}

    result = (
        client.table("harness_runs")
        .update({
            "status": "running",
            "current_phase": new_phase_index,
            "phase_results": merged,
        })
        .eq("id", run_id)
        .in_("status", ["paused"])  # transactional guard — only paused can resume
        .execute()
    )
    if not result.data:
        logger.warning(
            "resume_from_pause affected 0 rows run_id=%s — possibly not paused",
            run_id,
        )
        return None
    audit_service.log_action(
        user_id=user_id,
        user_email=user_email,
        action="harness_run_resumed",
        resource_type="harness_runs",
        resource_id=run_id,
    )
    return result.data[0]
