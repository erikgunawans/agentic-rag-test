from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from fastapi.responses import JSONResponse

SKILLS_IMPORT_PATH = "/skills/import"
MAX_IMPORT_BYTES = 50 * 1024 * 1024  # 50 MB


class SkillsUploadSizeMiddleware(BaseHTTPMiddleware):
    """Cycle-2 review H6 fix: cap POST /skills/import body BEFORE Starlette
    buffers the multipart upload. Rejects via Content-Length header when present;
    rejects via streaming byte counter when absent (chunked transfer-encoding).
    """

    async def dispatch(self, request: Request, call_next):
        if request.method != "POST" or request.url.path.rstrip("/") != SKILLS_IMPORT_PATH:
            return await call_next(request)

        cl = request.headers.get("content-length")
        if cl is not None:
            try:
                if int(cl) > MAX_IMPORT_BYTES:
                    return JSONResponse(
                        {"detail": "ZIP exceeds 50 MB limit"}, status_code=413
                    )
            except ValueError:
                return JSONResponse(
                    {"detail": "Invalid Content-Length"}, status_code=400
                )

        # Chunked transfer-encoding: count bytes as they stream in; abort on overflow.
        # (Starlette streams the body; we wrap receive() to enforce the cap.)
        original_receive = request._receive
        total = {"n": 0, "overflow": False}

        async def capped_receive():
            msg = await original_receive()
            if msg["type"] == "http.request":
                total["n"] += len(msg.get("body", b""))
                if total["n"] > MAX_IMPORT_BYTES:
                    total["overflow"] = True
            return msg

        request._receive = capped_receive
        response = await call_next(request)
        if total["overflow"]:
            return JSONResponse({"detail": "ZIP exceeds 50 MB limit"}, status_code=413)
        return response
