import re

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from fastapi.responses import JSONResponse

_IMPORT_MAX_BYTES = 50 * 1024 * 1024   # 50 MB (Phase 7 D-P7-08 ZIP cap)
_PER_FILE_MAX_BYTES = 10 * 1024 * 1024  # 10 MB (Phase 7 D-P7-08 per-file cap)

# Legacy constant kept for backwards-compatibility with any imports
SKILLS_IMPORT_PATH = "/skills/import"
MAX_IMPORT_BYTES = _IMPORT_MAX_BYTES

_IMPORT_RE = re.compile(r"^/skills/import$")
_FILES_UPLOAD_RE = re.compile(r"^/skills/[^/]+/files$")


class SkillsUploadSizeMiddleware(BaseHTTPMiddleware):
    """Cycle-2 review H6 fix: cap POST /skills/import body BEFORE Starlette
    buffers the multipart upload. Rejects via Content-Length header when present;
    rejects via streaming byte counter when absent (chunked transfer-encoding).

    Phase 8 extension: also caps POST /skills/{id}/files at 10 MB (D-P7-08
    per-file limit), using the same pre-parse Content-Length + streaming-counter
    mechanism as the /import 50 MB cap.
    """

    async def dispatch(self, request: Request, call_next):
        if request.method != "POST":
            return await call_next(request)

        path = request.url.path.rstrip("/")

        # Determine which cap applies (if any)
        if _IMPORT_RE.match(path):
            limit = _IMPORT_MAX_BYTES
            detail_msg = "ZIP exceeds 50 MB limit"
        elif _FILES_UPLOAD_RE.match(path):
            limit = _PER_FILE_MAX_BYTES
            detail_msg = "skill file exceeds 10 MB limit"
        else:
            return await call_next(request)

        # Content-Length fast path
        cl = request.headers.get("content-length")
        if cl is not None:
            try:
                if int(cl) > limit:
                    return JSONResponse(
                        {"detail": detail_msg}, status_code=413
                    )
            except ValueError:
                return JSONResponse(
                    {"detail": "Invalid Content-Length"}, status_code=400
                )

        # Chunked transfer-encoding: count bytes as they stream in; abort on overflow.
        # (Starlette streams the body; we wrap receive() to enforce the cap.)
        original_receive = request._receive
        total = {"n": 0, "overflow": False}
        limit_val = limit  # capture for closure

        async def capped_receive():
            msg = await original_receive()
            if msg["type"] == "http.request":
                total["n"] += len(msg.get("body", b""))
                if total["n"] > limit_val:
                    total["overflow"] = True
            return msg

        request._receive = capped_receive
        response = await call_next(request)
        if total["overflow"]:
            return JSONResponse({"detail": detail_msg}, status_code=413)
        return response
