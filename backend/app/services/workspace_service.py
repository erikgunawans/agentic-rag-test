"""Phase 18: Workspace Virtual Filesystem service layer.

Implements WS-01..WS-04 + WS-06 storage primitives consumed by:
- LLM tools (Plan 18-03)
- REST endpoints (Plan 18-04)
- Sandbox post-processing (Plan 18-05)

All public methods return structured dicts (no exceptions to the LLM).
RLS is enforced by Supabase via get_supabase_authed_client(token).
Sub-agents (Phase 19) inherit access through thread-ownership scope.

Threat mitigations (T-18-06 through T-18-10):
- T-18-06: validate_workspace_path rejects every '..' segment (traversal)
- T-18-07: 1 MB text cap rejected before any DB hit
- T-18-08: authed client enforces RLS predicate on threads.user_id
- T-18-09: service constructs storage_bucket literal; CHECK constraint in DB
- T-18-10: all exceptions converted to {error: code, detail: str(exc)}
"""

from __future__ import annotations

import asyncio
import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import Any

from app.database import get_supabase_authed_client, get_supabase_client
from app.services import audit_service

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_PATH_LENGTH = 500
MAX_TEXT_CONTENT_BYTES = 1024 * 1024  # 1 MB per WS-03 / D-06
SIGNED_URL_TTL_SECONDS = 3600         # 1 hour — mirrors sandbox_service._SIGNED_URL_TTL_SECONDS
WORKSPACE_BUCKET = "workspace-files"
SANDBOX_BUCKET = "sandbox-outputs"

_CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f]")


# ---------------------------------------------------------------------------
# Path validation
# ---------------------------------------------------------------------------

class WorkspaceValidationError(Exception):
    """Raised internally by validate_workspace_path.

    Service methods CATCH and convert to structured-error dict so the LLM
    can recover without crashing the loop (STATUS-02 / D-05 invariant).
    """

    def __init__(self, code: str, detail: str, **fields: Any) -> None:
        self.code = code
        self.detail = detail
        self.fields = fields
        super().__init__(f"[{code}] {detail}")


def validate_workspace_path(path: str) -> str:
    """Validate and normalise a workspace-relative file path.

    Returns the validated path (stripped of surrounding whitespace).
    Raises WorkspaceValidationError with a structured code for any violation.

    Validation rules (D-05):
    1. Empty / whitespace-only → path_invalid_empty
    2. Length > 500 → path_invalid_too_long
    3. Leading '/' → path_invalid_leading_slash
    4. Contains '\\' → path_invalid_backslash
    5. Control characters / NUL → path_invalid_control_chars
    6. Ends with '/' → path_invalid_trailing_slash
    7. Any segment equals '..' → path_invalid_traversal
    """
    if not isinstance(path, str):
        raise WorkspaceValidationError("path_invalid_empty", "path must be a string")

    p = path.strip()

    if not p:
        raise WorkspaceValidationError(
            "path_invalid_empty",
            "path is empty or whitespace-only",
        )

    if len(p) > MAX_PATH_LENGTH:
        raise WorkspaceValidationError(
            "path_invalid_too_long",
            f"path exceeds {MAX_PATH_LENGTH} characters",
            limit=MAX_PATH_LENGTH,
            actual=len(p),
        )

    if p.startswith("/"):
        raise WorkspaceValidationError(
            "path_invalid_leading_slash",
            "path must be relative (no leading /)",
        )

    if "\\" in p:
        raise WorkspaceValidationError(
            "path_invalid_backslash",
            "use forward slashes only (no backslashes)",
        )

    if _CONTROL_CHAR_RE.search(p):
        raise WorkspaceValidationError(
            "path_invalid_control_chars",
            "control characters and NUL are not allowed",
        )

    if p.endswith("/"):
        raise WorkspaceValidationError(
            "path_invalid_trailing_slash",
            "paths must not end with / (no directory writes)",
        )

    segments = p.split("/")
    if any(seg == ".." for seg in segments):
        raise WorkspaceValidationError(
            "path_invalid_traversal",
            ".. segments are forbidden in workspace paths",
        )

    return p


# ---------------------------------------------------------------------------
# MIME-type detection heuristic (D-15 / Claude's discretion)
# ---------------------------------------------------------------------------

def _detect_mime_type(file_path: str) -> str:
    """Best-effort MIME type from file extension. Defaults to text/markdown."""
    lower = file_path.lower()
    if lower.endswith(".md"):
        return "text/markdown"
    if lower.endswith(".csv"):
        return "text/csv"
    if lower.endswith(".json"):
        return "application/json"
    if lower.endswith(".txt"):
        return "text/plain"
    if lower.endswith(".html") or lower.endswith(".htm"):
        return "text/html"
    if lower.endswith(".py"):
        return "text/x-python"
    if lower.endswith(".js") or lower.endswith(".ts"):
        return "text/javascript"
    # Default for agent-written text files: text/markdown (D-15)
    return "text/markdown"


# ---------------------------------------------------------------------------
# Sandbox file registry entry (for plan 18-05 handover)
# ---------------------------------------------------------------------------

@dataclass
class SandboxFileEntry:
    """Descriptor for a sandbox-generated file to register in workspace_files."""

    filename: str          # e.g. "chart.png"
    size_bytes: int
    storage_path: str      # 4-segment path in sandbox-outputs bucket
    mime_type: str | None = None


# ---------------------------------------------------------------------------
# WorkspaceService
# ---------------------------------------------------------------------------

class WorkspaceService:
    """CRUD service for the workspace_files virtual filesystem.

    All operations use the RLS-scoped authed client (D-03b):
      WorkspaceService(token)  →  get_supabase_authed_client(token)

    All public methods return structured dicts — no exceptions propagate to
    the caller (LLM tool dispatcher).
    """

    def __init__(self, token: str) -> None:
        self._token = token
        self._client = get_supabase_authed_client(token)

    # ------------------------------------------------------------------
    # write_text_file
    # ------------------------------------------------------------------

    async def write_text_file(
        self,
        thread_id: str,
        file_path: str,
        content: str,
        source: str = "agent",
    ) -> dict:
        """Upsert a text file row.

        Returns:
            {"ok": True, "operation": "create"|"update", "size_bytes": N, "file_path": str}
            or {"error": code, ...} for any failure.
        """
        try:
            file_path = validate_workspace_path(file_path)
        except WorkspaceValidationError as e:
            return {"error": e.code, "detail": e.detail, "file_path": file_path, **e.fields}

        size_bytes = len(content.encode("utf-8"))
        if size_bytes > MAX_TEXT_CONTENT_BYTES:
            return {
                "error": "text_content_too_large",
                "limit_bytes": MAX_TEXT_CONTENT_BYTES,
                "actual_bytes": size_bytes,
                "file_path": file_path,
            }

        mime_type = _detect_mime_type(file_path)

        # Determine create vs update via a lightweight SELECT (D-06).
        try:
            existing = (
                self._client.table("workspace_files")
                .select("id")
                .eq("thread_id", thread_id)
                .eq("file_path", file_path)
                .limit(1)
                .execute()
            )
        except Exception as exc:
            logger.warning("workspace write_text_file select error: %s", exc)
            return {"error": "db_error", "detail": str(exc), "file_path": file_path}

        operation = "update" if existing.data else "create"

        try:
            self._client.table("workspace_files").upsert(
                {
                    "thread_id": thread_id,
                    "file_path": file_path,
                    "content": content,
                    "storage_path": None,
                    "storage_bucket": None,
                    "source": source,
                    "size_bytes": size_bytes,
                    "mime_type": mime_type,
                },
                on_conflict="thread_id,file_path",
            ).execute()
        except Exception as exc:
            logger.warning("workspace write_text_file upsert error: %s", exc)
            return {"error": "db_error", "detail": str(exc), "file_path": file_path}

        return {
            "ok": True,
            "operation": operation,
            "size_bytes": size_bytes,
            "file_path": file_path,
        }

    # ------------------------------------------------------------------
    # read_file
    # ------------------------------------------------------------------

    async def read_file(self, thread_id: str, file_path: str) -> dict:
        """Read a file from workspace_files.

        Returns:
            Text: {"ok": True, "is_binary": False, "content": str, "size_bytes": N, "mime_type": str}
            Binary: {"ok": True, "is_binary": True, "signed_url": str, "size_bytes": N, "mime_type": str}
            Error: {"error": code, "file_path": str, ...}
        """
        try:
            file_path = validate_workspace_path(file_path)
        except WorkspaceValidationError as e:
            return {"error": e.code, "detail": e.detail, "file_path": file_path, **e.fields}

        try:
            res = (
                self._client.table("workspace_files")
                .select("content,storage_path,storage_bucket,size_bytes,mime_type")
                .eq("thread_id", thread_id)
                .eq("file_path", file_path)
                .limit(1)
                .execute()
            )
        except Exception as exc:
            return {"error": "db_error", "detail": str(exc), "file_path": file_path}

        if not res.data:
            return {"error": "file_not_found", "file_path": file_path}

        row = res.data[0]

        if row.get("storage_path"):
            # Binary file — generate a signed URL
            bucket = row.get("storage_bucket") or WORKSPACE_BUCKET
            try:
                signed = self._client.storage.from_(bucket).create_signed_url(
                    row["storage_path"], SIGNED_URL_TTL_SECONDS
                )
                signed_url = signed.get("signedURL") or signed.get("signed_url") or ""
            except Exception as exc:
                return {"error": "storage_error", "detail": str(exc), "file_path": file_path}

            return {
                "ok": True,
                "is_binary": True,
                "signed_url": signed_url,
                "size_bytes": row.get("size_bytes") or 0,
                "mime_type": row.get("mime_type") or "application/octet-stream",
                "file_path": file_path,
            }

        return {
            "ok": True,
            "is_binary": False,
            "content": row.get("content") or "",
            "size_bytes": row.get("size_bytes") or 0,
            "mime_type": row.get("mime_type") or "text/plain",
            "file_path": file_path,
        }

    # ------------------------------------------------------------------
    # append_line  (Phase 21 / Plan 21-01 — BATCH-05/D-05 + BATCH-07/D-07)
    # ------------------------------------------------------------------

    # Class-level lock map — keyed by (thread_id, file_path). Per v1.0 D-31
    # carryover, this is single-worker only; cross-process atomicity will be
    # added when scale-out happens (deferred to post-MVP per .planning/STATE.md).
    _append_locks: dict[tuple[str, str], asyncio.Lock] = {}

    @classmethod
    def _get_append_lock(cls, thread_id: str, file_path: str) -> asyncio.Lock:
        """Return the (identity-stable) asyncio.Lock for this (thread, path)."""
        key = (thread_id, file_path)
        lock = cls._append_locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            cls._append_locks[key] = lock
        return lock

    async def append_line(
        self,
        thread_id: str,
        file_path: str,
        line: str,
    ) -> dict:
        """Atomically append `line + "\\n"` to the workspace text file at file_path.

        Phase 21 BATCH-05/D-05: each batch sub-agent appends one JSON object per
        line. Concurrent appends to the same (thread_id, file_path) are
        serialized via a per-key asyncio.Lock so the file grows monotonically
        without overwrite. First-write semantics: when no row exists yet, the
        line itself becomes the file's content (no separate write_text_file
        call needed before the first append).

        Returns:
            {"ok": True, "operation": "append", "size_bytes": int, "file_path": str}
            or {"error": <code>, "detail": str, "file_path": str}.

        Note: cross-process atomicity is NOT provided. v1.3 deploys a single
        worker on Railway (D-31 carryover). The pg_advisory_xact_lock upgrade
        path is documented in STATE.md.
        """
        # 1. Path validation (mirrors write_text_file convention)
        try:
            file_path = validate_workspace_path(file_path)
        except WorkspaceValidationError as e:
            return {"error": e.code, "detail": e.detail, "file_path": file_path, **e.fields}

        # 2. Construct newline-terminated segment (idempotent if caller already
        #    supplied the trailing newline)
        new_segment = line if line.endswith("\n") else line + "\n"
        new_segment_bytes = len(new_segment.encode("utf-8"))

        # 3. Acquire per-key lock — serializes concurrent appends within this worker
        lock = self._get_append_lock(thread_id, file_path)
        async with lock:
            # 4. Read existing content (file_not_found = empty-content case;
            #    other errors propagate as db_error)
            try:
                existing = await self.read_file(thread_id, file_path)
            except Exception as exc:
                logger.warning("workspace append_line read error: %s", exc)
                return {"error": "db_error", "detail": str(exc), "file_path": file_path}

            if "error" in existing:
                if existing["error"] == "file_not_found":
                    current_content = ""
                else:
                    return {
                        "error": existing.get("error", "db_error"),
                        "detail": existing.get("detail", "read failed"),
                        "file_path": file_path,
                    }
            else:
                current_content = existing.get("content", "") or ""

            current_bytes = len(current_content.encode("utf-8"))
            new_total = current_bytes + new_segment_bytes

            # 5. Size-cap check BEFORE write — consistent with write_text_file
            if new_total > MAX_TEXT_CONTENT_BYTES:
                return {
                    "error": "content_too_large",
                    "limit_bytes": MAX_TEXT_CONTENT_BYTES,
                    "file_path": file_path,
                    "detail": (
                        f"append would produce {new_total} bytes "
                        f"(limit {MAX_TEXT_CONTENT_BYTES})"
                    ),
                }

            # 6. Write via existing write_text_file (preserves source, RLS,
            #    mime-type detection, audit). source='harness' marks the row
            #    as harness-engine-written so post-mortem can distinguish from
            #    direct agent writes.
            new_content = current_content + new_segment
            try:
                write_result = await self.write_text_file(
                    thread_id, file_path, new_content, source="harness"
                )
            except Exception as exc:
                logger.warning("workspace append_line write error: %s", exc)
                return {"error": "db_error", "detail": str(exc), "file_path": file_path}

            if "error" in write_result:
                return {
                    "error": write_result["error"],
                    "detail": write_result.get("detail", "write failed"),
                    "file_path": file_path,
                }

            return {
                "ok": True,
                "operation": "append",
                "size_bytes": new_total,
                "file_path": file_path,
            }

    # ------------------------------------------------------------------
    # edit_file
    # ------------------------------------------------------------------

    async def edit_file(
        self,
        thread_id: str,
        file_path: str,
        old_string: str,
        new_string: str,
    ) -> dict:
        """Exact-string replacement on a text file.

        old_string must appear EXACTLY ONCE. Returns structured error for:
        - file_not_found
        - is_binary_file
        - edit_old_string_not_found
        - edit_old_string_ambiguous (occurrences > 1)
        """
        read = await self.read_file(thread_id, file_path)
        if "error" in read:
            return read
        if read.get("is_binary"):
            return {"error": "is_binary_file", "file_path": file_path}

        content: str = read["content"]
        occurrences = content.count(old_string)
        if occurrences == 0:
            return {"error": "edit_old_string_not_found", "file_path": file_path}
        if occurrences > 1:
            return {
                "error": "edit_old_string_ambiguous",
                "occurrences": occurrences,
                "file_path": file_path,
            }

        new_content = content.replace(old_string, new_string, 1)
        return await self.write_text_file(thread_id, file_path, new_content, source="agent")

    # ------------------------------------------------------------------
    # list_files
    # ------------------------------------------------------------------

    async def list_files(self, thread_id: str) -> list[dict]:
        """Return all workspace files for a thread, ordered by updated_at DESC.

        Returns list of dicts: [{file_path, size_bytes, source, mime_type, updated_at}]
        Returns [] on DB error (non-fatal; logs warning).
        """
        try:
            res = (
                self._client.table("workspace_files")
                .select("file_path,size_bytes,source,mime_type,updated_at")
                .eq("thread_id", thread_id)
                .order("updated_at", desc=True)
                .execute()
            )
        except Exception as exc:
            logger.warning("workspace list_files error: %s", exc)
            return []
        return res.data or []

    # ------------------------------------------------------------------
    # write_binary_file
    # ------------------------------------------------------------------

    async def write_binary_file(
        self,
        thread_id: str,
        file_path: str,
        content_bytes: bytes,
        mime_type: str,
        user_id: str,
        source: str = "upload",
    ) -> dict:
        """Upload a binary file to the workspace-files bucket + insert a row.

        Storage path (4-segment): {user_id}/{thread_id}/{row_id}/{filename}

        Returns:
            {"ok": True, "operation": "create", "size_bytes": N, "file_path": str, "storage_path": str}
            or {"error": code, ...}
        """
        try:
            file_path = validate_workspace_path(file_path)
        except WorkspaceValidationError as e:
            return {"error": e.code, "detail": e.detail, "file_path": file_path, **e.fields}

        # 4-segment storage path: {user_id}/{thread_id}/{row_id}/{filename}
        row_id = str(uuid.uuid4())
        filename = file_path.rsplit("/", 1)[-1]
        storage_path = f"{user_id}/{thread_id}/{row_id}/{filename}"

        try:
            self._client.storage.from_(WORKSPACE_BUCKET).upload(
                storage_path,
                content_bytes,
                {"content-type": mime_type or "application/octet-stream"},
            )
        except Exception as exc:
            return {"error": "storage_error", "detail": str(exc), "file_path": file_path}

        try:
            self._client.table("workspace_files").upsert(
                {
                    "id": row_id,
                    "thread_id": thread_id,
                    "file_path": file_path,
                    "content": None,
                    "storage_path": storage_path,
                    "storage_bucket": WORKSPACE_BUCKET,
                    "source": source,
                    "size_bytes": len(content_bytes),
                    "mime_type": mime_type,
                },
                on_conflict="thread_id,file_path",
            ).execute()
        except Exception as exc:
            return {"error": "db_error", "detail": str(exc), "file_path": file_path}

        return {
            "ok": True,
            "operation": "create",
            "size_bytes": len(content_bytes),
            "file_path": file_path,
            "storage_path": storage_path,
        }

    # ------------------------------------------------------------------
    # register_uploaded_file  (Phase 20 / Plan 20-06 — UPL-01, UPL-02, OBS-02)
    # ------------------------------------------------------------------

    async def register_uploaded_file(
        self,
        *,
        thread_id: str,
        file_path: str,          # workspace-relative path (no leading /)
        content_bytes: bytes,
        mime_type: str,
        user_id: str,
        user_email: str,
    ) -> dict:
        """Store binary in WORKSPACE_BUCKET + metadata row in workspace_files (source='upload').

        Sibling of register_sandbox_files — same upsert-on-conflict pattern,
        source='upload' discriminator, audit-logged.

        Returns {ok: True, file_path, size_bytes, storage_path, ...} on success
        or raises WorkspaceValidationError for invalid path,
        or returns {error: code, detail: str, file_path} on storage/DB failure.
        """
        # 1. Validate path (raises WorkspaceValidationError — caller catches)
        validate_workspace_path(file_path)

        # 2. Storage write (delegates to existing write_binary_file)
        write_result = await self.write_binary_file(
            thread_id=thread_id,
            file_path=file_path,
            content_bytes=content_bytes,
            mime_type=mime_type,
            user_id=user_id,
            source="upload",
        )
        if isinstance(write_result, dict) and "error" in write_result:
            return {"error": "storage_write_failed", "detail": write_result.get("detail", ""), "file_path": file_path}

        storage_path = write_result.get("storage_path") or f"{user_id}/{thread_id}/{file_path}"
        size_bytes = len(content_bytes)

        # 3. Metadata upsert with source='upload' (idempotent — reinforces discriminator)
        client = get_supabase_authed_client(self._token)
        try:
            insert_result = client.table("workspace_files").upsert(
                {
                    "thread_id": thread_id,
                    "file_path": file_path,
                    "content": None,
                    "storage_path": storage_path,
                    "storage_bucket": WORKSPACE_BUCKET,
                    "source": "upload",
                    "size_bytes": size_bytes,
                    "mime_type": mime_type,
                },
                on_conflict="thread_id,file_path",
            ).execute()
            row_id = (insert_result.data or [{}])[0].get("id", "")
        except Exception as exc:
            logger.error(
                "register_uploaded_file db error file=%s thread=%s exc=%s",
                file_path, thread_id, exc,
            )
            return {"error": "db_error", "detail": str(exc)[:500], "file_path": file_path}

        # 4. Audit log (OBS-02 thread_id correlation via resource_id)
        audit_service.log_action(
            user_id=user_id,
            user_email=user_email,
            action="workspace_file_uploaded",
            resource_type="workspace_files",
            resource_id=row_id or file_path,
        )

        return {
            "ok": True,
            "id": row_id,
            "file_path": file_path,
            "size_bytes": size_bytes,
            "storage_path": storage_path,
            "mime_type": mime_type,
            "source": "upload",
        }


# ---------------------------------------------------------------------------
# register_sandbox_files (consumed by plan 18-05 sandbox integration)
# ---------------------------------------------------------------------------

async def register_sandbox_files(
    *,
    token: str,
    thread_id: str,
    files: list[SandboxFileEntry],
) -> list[dict]:
    """Insert workspace_files rows referencing existing sandbox-outputs storage paths.

    Idempotent: upserts on (thread_id, file_path) — retried sandbox executions
    update the row rather than error.

    Used by sandbox_service after _collect_and_upload_files completes (Plan 18-05).
    Each row gets:
        file_path    = f"sandbox/{filename}"
        storage_path = entry.storage_path  (existing object in sandbox-outputs bucket)
        storage_bucket = 'sandbox-outputs'
        source       = 'sandbox'
    """
    if not files:
        return []

    client = get_supabase_authed_client(token)
    out: list[dict] = []

    for entry in files:
        wp = f"sandbox/{entry.filename}"
        try:
            validate_workspace_path(wp)
        except WorkspaceValidationError as e:
            logger.warning(
                "workspace register_sandbox_files: skipping %s: %s", wp, e.detail
            )
            out.append({"error": e.code, "file_path": wp})
            continue

        try:
            client.table("workspace_files").upsert(
                {
                    "thread_id": thread_id,
                    "file_path": wp,
                    "content": None,
                    "storage_path": entry.storage_path,
                    "storage_bucket": SANDBOX_BUCKET,
                    "source": "sandbox",
                    "size_bytes": entry.size_bytes,
                    "mime_type": entry.mime_type or "application/octet-stream",
                },
                on_conflict="thread_id,file_path",
            ).execute()
            out.append({"ok": True, "file_path": wp, "operation": "registered"})
        except Exception as exc:
            logger.warning(
                "workspace register_sandbox_files db error file=%s: %s", wp, exc
            )
            out.append({"error": "db_error", "detail": str(exc), "file_path": wp})

    return out
