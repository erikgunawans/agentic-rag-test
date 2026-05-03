"""Phase 18: Workspace Virtual Filesystem REST endpoints (WS-09).

GET /threads/{thread_id}/files
  → JSON array of {file_path, size_bytes, source, mime_type, updated_at}
GET /threads/{thread_id}/files/{file_path:path}
  → text body for text files (Content-Type from mime_type)
  → 307 redirect to 1-hour signed URL for binary files
  → 404 if not found / RLS denies

Phase 20 / Plan 20-06 additions:
POST /threads/{thread_id}/files/upload
  → accepts multipart/form-data with a single DOCX or PDF file (UPL-01, UPL-02)
  → size cap 25 MB, MIME + magic-byte validation
  → gated on settings.workspace_enabled (W6 fix per D-13 — NOT harness_enabled)

All endpoints RLS-scoped via get_supabase_authed_client(token) (D-03).

Threat mitigations:
- T-18-15: RLS denies cross-user reads; service returns file_not_found; endpoint returns 404
- T-18-16: path traversal in URL :path segment — service-layer validator rejects
- T-18-18: feature flag bypass — if WORKSPACE_ENABLED=False routes are never registered
- T-20-06-01: magic-byte validation rejects MIME spoofing
- T-20-06-02: server-controlled upload path (uploads/<sanitized-filename>) prevents traversal
- T-20-06-03: 25 MB hard cap (413 error)
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from fastapi.responses import RedirectResponse

from app.config import get_settings
from app.dependencies import get_current_user
from app.services.workspace_service import WorkspaceService, WorkspaceValidationError

logger = logging.getLogger(__name__)
router = APIRouter(tags=["workspace"])

# ---------------------------------------------------------------------------
# Upload constants (Phase 20 / Plan 20-06 — UPL-01, UPL-02)
# ---------------------------------------------------------------------------

MAX_UPLOAD_SIZE = 25 * 1024 * 1024  # 25 MB per CONTEXT.md Discretion
PDF_MAGIC = b"%PDF-"
DOCX_MAGIC = b"PK\x03\x04"
DOCX_CONTENT_TYPES_TOKEN = b"[Content_Types].xml"
ACCEPTED_MIME = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
}


def _emit_workspace_updated(
    *,
    thread_id: str,
    file_path: str,
    operation: str,
    source: str,
    size_bytes: int,
) -> None:
    """Emit workspace_updated SSE event (D-10 Phase 18 pattern).

    Separated as a module-level function so tests can mock it directly.
    In production this is a best-effort call; failures are logged as warnings.
    """
    # The workspace_updated event is emitted via Supabase Realtime in Phase 18.
    # A future plan can wire this to the SSE queue if needed; for now the
    # Supabase channel triggers the WorkspacePanel to re-render.
    logger.debug(
        "workspace_updated event thread=%s file=%s op=%s source=%s size=%d",
        thread_id, file_path, operation, source, size_bytes,
    )


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


# ---------------------------------------------------------------------------
# POST /threads/{thread_id}/files/upload  (Phase 20 / Plan 20-06)
# ---------------------------------------------------------------------------

@router.post("/threads/{thread_id}/files/upload")
async def upload_workspace_file(
    thread_id: str,
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    """Upload a DOCX or PDF binary to the thread's workspace (UPL-01, UPL-02).

    Text extraction is LAZY (D-14): binary stored only; consumer harness Phase 1
    reads the bytes and extracts text via python-docx / PyPDF2.

    --- Gating (W6 fix — corrected per CONTEXT.md D-13) ---
    Gated on settings.workspace_enabled (W6 fix per D-13 — NOT the harness flag).
    D-13: paperclip always visible when WORKSPACE_ENABLED=true (works for both
    harness flows AND general workspace upload). Three states:
      - workspace_enabled=False                         → 404 workspace_disabled
      - workspace_enabled=True, harness_enabled=False   → 200; file lands as
        source='upload'; no gatekeeper trigger (D-13 standalone case)
      - workspace_enabled=True, harness_enabled=True    → 200; gatekeeper sees
        the new file in workspace and may trigger

    Validation order:
      1. workspace_enabled gate (404 if off)
      2. MIME type allow-list (400 wrong_mime if rejected)
      3. Read body
      4. Size cap 25 MB (413 upload_too_large)
      5. Magic-byte check (400 magic_byte_mismatch on mismatch)
      6. Server-side path sanitisation (safe_name from filename)
      7. Delegate to WorkspaceService.register_uploaded_file
      8. Emit workspace_updated event (D-10 Phase 18 pattern)
    """
    # 1. Feature-flag gate (W6 — per D-13: workspace_enabled, NOT harness_enabled)
    settings = get_settings()
    if not settings.workspace_enabled:
        raise HTTPException(status_code=404, detail={"error": "workspace_disabled"})

    # 2. MIME allow-list check (early reject — header-based)
    mime_type = file.content_type or "application/octet-stream"
    if mime_type not in ACCEPTED_MIME:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "wrong_mime",
                "accepted": list(ACCEPTED_MIME.keys()),
                "received": mime_type,
            },
        )

    # 3. Read body
    content_bytes = await file.read()
    size_bytes = len(content_bytes)

    # 4. Size cap
    if size_bytes > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail={
                "error": "upload_too_large",
                "max_bytes": MAX_UPLOAD_SIZE,
                "received_bytes": size_bytes,
            },
        )

    # 5. Magic-byte validation (T-20-06-01)
    if mime_type == "application/pdf":
        if not content_bytes.startswith(PDF_MAGIC):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "magic_byte_mismatch",
                    "expected": "%PDF-",
                    "received": content_bytes[:8].hex(),
                },
            )
    else:  # DOCX
        if not content_bytes.startswith(DOCX_MAGIC):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "magic_byte_mismatch",
                    "expected": "PK\\x03\\x04",
                    "received": content_bytes[:8].hex(),
                },
            )
        # Scan first 2 KB for [Content_Types].xml (DOCX is a ZIP)
        if DOCX_CONTENT_TYPES_TOKEN not in content_bytes[:2048]:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "magic_byte_mismatch",
                    "expected": "DOCX zip with [Content_Types].xml",
                    "received": "zip without DOCX marker",
                },
            )

    # 6. Server-side path sanitisation (T-20-06-02 — never trust client filename)
    raw_name = file.filename or "upload"
    # Strip any path separators from the client-supplied filename
    safe_name = raw_name.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    if not safe_name:
        safe_name = "upload"
    # Enforce correct extension per MIME
    ext = ACCEPTED_MIME[mime_type]
    if not safe_name.lower().endswith(f".{ext}"):
        safe_name = f"{safe_name}.{ext}"
    file_path = f"uploads/{safe_name}"

    # 7. Delegate to service
    ws = WorkspaceService(token=user["token"])
    try:
        result = await ws.register_uploaded_file(
            thread_id=thread_id,
            file_path=file_path,
            content_bytes=content_bytes,
            mime_type=mime_type,
            user_id=user["id"],
            user_email=user["email"],
        )
    except WorkspaceValidationError as ve:
        raise HTTPException(
            status_code=400,
            detail={"error": "path_invalid", "detail": ve.detail},
        )

    if isinstance(result, dict) and "error" in result:
        code = result["error"]
        if code in ("storage_write_failed", "db_error"):
            raise HTTPException(status_code=500, detail=result)
        raise HTTPException(status_code=400, detail=result)

    # 8. Emit workspace_updated SSE event (D-10 Phase 18 pattern)
    try:
        _emit_workspace_updated(
            thread_id=thread_id,
            file_path=file_path,
            operation="created",
            source="upload",
            size_bytes=size_bytes,
        )
    except Exception as exc:
        logger.warning("_emit_workspace_updated failed file=%s exc=%s", file_path, exc)

    return result
