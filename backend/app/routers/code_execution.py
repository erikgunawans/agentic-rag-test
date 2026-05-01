"""Code Execution router — Phase 10 / D-P10-17.

Read-only endpoint that exposes the immutable `code_executions` audit log to
authenticated users. RLS auto-filters to own rows; super_admin sees all
(D-P10-15). Signed URLs in the `files` JSONB are refreshed at read time
because their TTL is 1 hour (D-P10-14) and rows can be days old.

Used by Phase 11's Code Execution Panel UI to render execution history.

Trust boundaries (see 10-06-PLAN.md threat model):
  - T-10-31: thread_id is a NARROWING filter only; RLS gates row access by user_id
  - T-10-32: signed URL refresh only runs on rows already authorized by RLS
  - T-10-34: limit capped at 100 via Query(..., le=100) — 422 on violation
"""

from datetime import datetime
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from app.dependencies import get_current_user
from app.database import get_supabase_authed_client, get_supabase_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/code-executions", tags=["code_executions"])


# ---------------------------------------------------------------------------
# Pydantic response model
# ---------------------------------------------------------------------------


class CodeExecutionResponse(BaseModel):
    """Mirrors public.code_executions row shape (migration 036).

    All 12 fields declared per 10-06-PLAN acceptance criteria.
    """

    id: str
    user_id: str
    thread_id: str
    code: str
    description: str | None = None
    stdout: str
    stderr: str
    exit_code: int
    execution_ms: int
    status: str  # 'success' | 'error' | 'timeout'
    files: list[dict]  # [{filename, size_bytes, signed_url, storage_path}]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Signed URL refresh helper
# ---------------------------------------------------------------------------


def _refresh_signed_urls(files: list[dict]) -> list[dict]:
    """D-P10-14: regenerate signed URLs at read time (1-hour TTL).

    Iterates files[]; for each entry with a `storage_path`, replaces `signed_url`
    with a freshly-signed URL. Service-role client used because storage signed-URL
    generation requires admin privilege; SELECT RLS already gated row access.

    Failures are logged but do NOT block the response — stale URL is preferable
    to no response. Frontend can re-request if a URL 403s.

    T-10-32: Storage paths in rows are already user-scoped (D-P10-13 path scheme:
    {user_id}/{thread_id}/{execution_id}/{filename}). We only reach this function
    after RLS has validated row access.
    """
    if not files:
        return []
    svc = get_supabase_client()
    refreshed: list[dict] = []
    for f in files:
        new_f = dict(f)  # don't mutate the caller's dict
        path = f.get("storage_path")
        if path:
            try:
                signed = svc.storage.from_("sandbox-outputs").create_signed_url(path, 3600)
                # supabase-py 2.7.4 returns dict with key 'signedURL' (JS-style naming)
                # Fall back to 'signed_url' for future SDK changes.
                new_url = (
                    signed.get("signedURL")
                    or signed.get("signed_url")
                    or new_f.get("signed_url", "")
                )
                new_f["signed_url"] = new_url
            except Exception as exc:
                logger.warning(
                    "code_executions signed URL refresh failed path=%s err=%s",
                    path,
                    exc,
                )
                # keep stale URL — don't drop the file entry
        refreshed.append(new_f)
    return refreshed


# ---------------------------------------------------------------------------
# GET /code-executions — list endpoint
# ---------------------------------------------------------------------------


@router.get("", response_model=dict)
async def list_code_executions(
    thread_id: str = Query(..., description="UUID of the thread to fetch executions for"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
) -> dict:
    """List code executions for a thread.

    D-P10-15 RLS: own rows always visible; super_admin sees all rows.
    D-P10-17: this endpoint is the data source for Phase 11's Code Execution Panel.
    T-10-31: thread_id is a NARROWING filter — not an auth gate. RLS handles auth.

    Response envelope (matches Phase 7 skills.py:318):
        {"data": [CodeExecutionResponse, ...], "count": int}
    """
    client = get_supabase_authed_client(user["token"])
    try:
        result = (
            client.table("code_executions").select("*")
            .eq("thread_id", thread_id)
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )
    except Exception as exc:
        logger.error("code_executions list query failed: %s", exc)
        return {"data": [], "count": 0}

    rows = result.data or []
    enriched: list[dict] = []
    for row in rows:
        # D-P10-14: refresh signed URLs at read time (1-hour TTL)
        row["files"] = _refresh_signed_urls(row.get("files") or [])
        enriched.append(CodeExecutionResponse(**row).model_dump(mode="json"))
    return {"data": enriched, "count": len(enriched)}


# ---------------------------------------------------------------------------
# GET /code-executions/{execution_id} — single-row read (Phase 11 / D-P11-06)
# ---------------------------------------------------------------------------


@router.get("/{execution_id}", response_model=CodeExecutionResponse)
async def get_code_execution(
    execution_id: str,
    user: dict = Depends(get_current_user),
) -> CodeExecutionResponse:
    """Fetch a single code_executions row with refreshed signed URLs.

    Phase 11 D-P11-06: backs the Code Execution Panel's file-download
    button, which refreshes signed URLs on each download click because
    the row may be hours/days old (D-P10-14: 1-hour signed URL TTL).

    RLS (Phase 10 D-P10-15): user_id = auth.uid() OR super_admin.
    Cross-user requests therefore return 404 (the row is invisible to
    the caller — preferable to 403 because it does not confirm existence).

    T-11-03-1: signed URL refresh runs only on rows already authorized
    by RLS. Storage paths in row.files are user-scoped (D-P10-13:
    {user_id}/{thread_id}/{execution_id}/{filename}).
    """
    client = get_supabase_authed_client(user["token"])
    try:
        result = (
            client.table("code_executions")
            .select("*")
            .eq("id", execution_id)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        logger.error("code_executions get-by-id query failed: %s", exc)
        raise HTTPException(status_code=500, detail="Internal error")

    rows = result.data or []
    if not rows:
        # RLS-filtered or genuinely missing — both resolve to 404.
        raise HTTPException(status_code=404, detail="Code execution not found")

    row = rows[0]
    row["files"] = _refresh_signed_urls(row.get("files") or [])
    return CodeExecutionResponse(**row)
