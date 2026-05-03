"""Phase 18: Workspace Virtual Filesystem REST endpoints (WS-09).

GET /threads/{thread_id}/files
  → JSON array of {file_path, size_bytes, source, mime_type, updated_at}
GET /threads/{thread_id}/files/{file_path:path}
  → text body for text files (Content-Type from mime_type)
  → 307 redirect to 1-hour signed URL for binary files
  → 404 if not found / RLS denies

All endpoints RLS-scoped via get_supabase_authed_client(token) (D-03).

Threat mitigations:
- T-18-15: RLS denies cross-user reads; service returns file_not_found; endpoint returns 404
- T-18-16: path traversal in URL :path segment — service-layer validator rejects
- T-18-18: feature flag bypass — if WORKSPACE_ENABLED=False routes are never registered
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import RedirectResponse

from app.dependencies import get_current_user
from app.services.workspace_service import WorkspaceService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["workspace"])


@router.get("/threads/{thread_id}/files")
async def list_workspace_files(
    thread_id: str,
    user: dict = Depends(get_current_user),
):
    """List all workspace files for a thread (RLS-scoped to the authenticated user)."""
    ws = WorkspaceService(token=user["token"])
    files = await ws.list_files(thread_id)
    return files


@router.get("/threads/{thread_id}/files/{file_path:path}")
async def read_workspace_file(
    thread_id: str,
    file_path: str,
    user: dict = Depends(get_current_user),
):
    """Read a workspace file by path.

    - Text files: returns body with detected MIME type.
    - Binary files: returns 307 redirect to a 1-hour signed URL.
    - Missing / RLS-denied: returns 404.
    - Invalid path: returns 400.
    """
    ws = WorkspaceService(token=user["token"])
    result = await ws.read_file(thread_id, file_path)

    if "error" in result:
        err = result["error"]
        if err == "file_not_found":
            raise HTTPException(status_code=404, detail=result)
        if err.startswith("path_invalid"):
            raise HTTPException(status_code=400, detail=result)
        # Unexpected service errors — 500
        raise HTTPException(status_code=500, detail=result)

    if result.get("is_binary"):
        signed_url = result.get("signed_url")
        if not signed_url:
            raise HTTPException(
                status_code=500,
                detail={"error": "signed_url_missing", "detail": "Service returned is_binary=True but no signed_url"},
            )
        return RedirectResponse(url=signed_url, status_code=307)

    # Text file — inline body with detected MIME type
    return Response(
        content=result.get("content", ""),
        media_type=result.get("mime_type") or "text/plain",
    )
