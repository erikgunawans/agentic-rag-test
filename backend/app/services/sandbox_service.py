"""SandboxService — Phase 10 / SANDBOX-01..06, 08.

Wraps llm-sandbox (Docker backend) with per-thread session persistence,
30-min TTL cleanup, per-call timeout, real-time stdout/stderr streaming,
and post-execution file upload to the sandbox-outputs Supabase bucket.

Decisions referenced:
  D-P10-01 — llm-sandbox library, Docker backend
  D-P10-04 — one container per thread, reused across calls
  D-P10-09 — sessions are ephemeral (in-memory dict only)
  D-P10-10 — 60s cleanup loop, 30-min idle TTL
  D-P10-11 — no per-user concurrent cap
  D-P10-12 — per-call execution timeout via asyncio.wait_for
  D-P10-13 — storage path {user_id}/{thread_id}/{execution_id}/{filename}
  D-P10-14 — signed URL TTL = 3600 seconds (1 hour)
  D-P10-08 — timeout/exception unify in stderr; exit_code distinguishes

llm-sandbox API notes (v0.3.39):
  - SandboxSession is a factory alias for create_session()
  - session.run() is SYNCHRONOUS — bridged via run_in_executor
  - StreamCallback = Callable[[str], None] (synchronous, runs in worker thread)
  - File access: session.execute_command("ls /sandbox/output/") +
    session.copy_from_runtime(container_path, local_path)
  - Session lifecycle: session.open() / session.close() (not context manager here
    because we keep sessions alive across multiple calls)
"""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Awaitable, Callable

from llm_sandbox import SandboxBackend, SandboxSession, SupportedLanguage

from app.config import get_settings
from app.database import get_supabase_client
from app.services.tracing_service import traced

logger = logging.getLogger(__name__)

# ── Module-level constants (D-P10-10, D-P10-14) ─────────────────────────────
_CLEANUP_INTERVAL_SECONDS = 60       # D-P10-10: cleanup runs every 60s
_SESSION_IDLE_TTL_MINUTES = 30       # D-P10-10: idle sessions evicted after 30min
_SIGNED_URL_TTL_SECONDS = 3600       # D-P10-14: 1-hour signed URL TTL
_OUTPUT_DIR = "/sandbox/output"      # Sandbox container output directory


@dataclass
class SandboxSession:
    """Per-thread sandbox state. `container` is the opaque llm-sandbox handle."""

    container: object       # llm-sandbox BaseSession instance (opened)
    last_used: datetime
    thread_id: str


class SandboxService:
    """Singleton service managing one Docker container per thread.

    The container is created on the first execute() call for a given thread_id
    and reused for all subsequent calls within that thread (D-P10-04 / SANDBOX-02
    variable persistence). Containers idle longer than 30 minutes are evicted by
    the background cleanup task (D-P10-10).
    """

    def __init__(self) -> None:
        # D-P10-09: purely in-memory; no DB persistence layer for session state
        self._sessions: dict[str, SandboxSession] = {}
        self._cleanup_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    # ── Session lifecycle ────────────────────────────────────────────────────

    async def _ensure_cleanup_task(self) -> None:
        """D-P10-10: lazy-spawn the 60s cleanup loop on first execute call."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def _cleanup_loop(self) -> None:
        """Close containers idle longer than 30 minutes.

        Runs forever in the background; never raises (errors are logged).
        """
        while True:
            try:
                await asyncio.sleep(_CLEANUP_INTERVAL_SECONDS)  # D-P10-10: every 60s
                cutoff = datetime.utcnow() - timedelta(minutes=_SESSION_IDLE_TTL_MINUTES)
                stale_ids = [
                    tid for tid, s in list(self._sessions.items())
                    if s.last_used < cutoff
                ]
                for tid in stale_ids:
                    sess = self._sessions.pop(tid, None)
                    if sess is None:
                        continue
                    try:
                        sess.container.close()
                    except Exception as exc:
                        logger.warning(
                            "sandbox cleanup close failed thread=%s err=%s", tid, exc
                        )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error("sandbox cleanup loop error: %s", exc, exc_info=True)
                # Loop continues — never let cleanup bring down the service.

    async def _get_or_create_session(self, thread_id: str) -> SandboxSession:
        """D-P10-04: one container per thread, lazy-create on first call.

        Uses asyncio.Lock to prevent race conditions when two concurrent requests
        for the same thread_id arrive simultaneously.
        """
        async with self._lock:
            sess = self._sessions.get(thread_id)
            if sess is not None:
                return sess
            container = self._create_container()
            sess = SandboxSession(
                container=container,
                last_used=datetime.utcnow(),
                thread_id=thread_id,
            )
            self._sessions[thread_id] = sess
            return sess

    def _create_container(self) -> object:
        """Construct and open an llm-sandbox session bound to settings.sandbox_image.

        D-P10-02: honors DOCKER_HOST env var for Railway socket mount.
        D-P10-01: Docker backend, Python language.

        Note on security posture (T-10-12): llm-sandbox creates an isolated Docker
        container. Backend env vars are NOT inherited by the sandbox container —
        the user's code cannot access secrets (D-P10-01 architectural decision).
        """
        settings = get_settings()
        # D-P10-02: set DOCKER_HOST so docker-py picks up the correct socket
        os.environ.setdefault("DOCKER_HOST", settings.sandbox_docker_host)

        # llm-sandbox v0.3.39: SandboxSession is a factory alias for create_session().
        # Use `keep_template=True` so the container is kept alive after each run()
        # call, enabling variable persistence (D-P10-04 / SANDBOX-02).
        container = SandboxSession(
            backend=SandboxBackend.DOCKER,
            lang=SupportedLanguage.PYTHON,
            image=settings.sandbox_image,
            keep_template=True,    # preserve container between run() calls
            verbose=False,
        )
        # Explicitly open the session so it's ready for run() calls.
        container.open()
        return container

    # ── Execution ────────────────────────────────────────────────────────────

    @traced(name="sandbox_execute")
    async def execute(
        self,
        *,
        code: str,
        thread_id: str,
        user_id: str,
        stream_callback: Callable[[str, str], Awaitable[None]] | None = None,
    ) -> dict:
        """Run `code` in the thread's sandbox container.

        Args:
            code: Python source to execute.
            thread_id: Identifies the per-thread container session (D-P10-04).
            user_id: Used for Storage path construction (D-P10-13).
            stream_callback: Optional async callable receiving (event_type, line).
                Invoked for each stdout/stderr chunk during execution (D-P10-05).

        Returns:
            {
                "stdout":       str,           # full captured stdout
                "stderr":       str,           # full captured stderr (incl. tracebacks)
                "exit_code":    int,           # 0=success, !=0=error, -1=timeout
                "error_type":   str | None,    # None | "timeout" | "exception"
                "execution_ms": int,
                "files":        list[dict],    # [{filename, size_bytes, signed_url, storage_path}]
                "execution_id": str,           # UUID for code_executions row + storage path
            }
        """
        await self._ensure_cleanup_task()
        session = await self._get_or_create_session(thread_id)
        session.last_used = datetime.utcnow()

        execution_id = str(uuid.uuid4())
        started = datetime.utcnow()
        stdout_buf: list[str] = []
        stderr_buf: list[str] = []

        # Build sync callbacks for llm-sandbox (StreamCallback = Callable[[str], None]).
        # These callbacks run in a worker thread (llm-sandbox threading model), so we
        # schedule async stream_callback invocations on the event loop.
        loop = asyncio.get_event_loop()

        def on_stdout_sync(chunk: str) -> None:
            stdout_buf.append(chunk)
            if stream_callback:
                asyncio.run_coroutine_threadsafe(
                    stream_callback("code_stdout", chunk), loop
                )

        def on_stderr_sync(chunk: str) -> None:
            stderr_buf.append(chunk)
            if stream_callback:
                asyncio.run_coroutine_threadsafe(
                    stream_callback("code_stderr", chunk), loop
                )

        exit_code = 0
        error_type: str | None = None

        settings = get_settings()

        try:
            # D-P10-12: per-call execution timeout via asyncio.wait_for.
            # run() is synchronous — bridge via run_in_executor so asyncio.wait_for works.
            result = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: session.container.run(
                        code,
                        on_stdout=on_stdout_sync,
                        on_stderr=on_stderr_sync,
                    ),
                ),
                timeout=settings.sandbox_max_exec_seconds,
            )
            exit_code = getattr(result, "exit_code", 0)
        except asyncio.TimeoutError:
            # D-P10-08: timeout unifies in stderr; exit_code distinguishes
            timeout_msg = f"Execution timed out after {settings.sandbox_max_exec_seconds}s\n"
            stderr_buf.append(timeout_msg)
            exit_code = -1
            error_type = "timeout"
            if stream_callback:
                try:
                    await stream_callback("code_stderr", timeout_msg)
                except Exception as exc:
                    logger.warning("stream_callback stderr error on timeout: %s", exc)
        except Exception as exc:
            # D-P10-08: unhandled exceptions unify in stderr
            err_msg = f"Execution failed: {exc}\n"
            stderr_buf.append(err_msg)
            exit_code = 1
            error_type = "exception"
            if stream_callback:
                try:
                    await stream_callback("code_stderr", err_msg)
                except Exception as cb_exc:
                    logger.warning("stream_callback stderr error on exception: %s", cb_exc)

        execution_ms = int(
            (datetime.utcnow() - started).total_seconds() * 1000
        )

        # D-P10-13/14: collect generated files, upload to Storage, sign URLs
        files = await self._collect_and_upload_files(
            session=session,
            user_id=user_id,
            thread_id=thread_id,
            execution_id=execution_id,
        )

        return {
            "stdout": "".join(stdout_buf),
            "stderr": "".join(stderr_buf),
            "exit_code": exit_code,
            "error_type": error_type,
            "execution_ms": execution_ms,
            "files": files,
            "execution_id": execution_id,
        }

    # ── File upload ──────────────────────────────────────────────────────────

    async def _collect_and_upload_files(
        self,
        *,
        session: SandboxSession,
        user_id: str,
        thread_id: str,
        execution_id: str,
    ) -> list[dict]:
        """List files in /sandbox/output/, upload each to Storage, return signed-URL list.

        Path scheme (D-P10-13): {user_id}/{thread_id}/{execution_id}/{filename}.
        Signed URL TTL (D-P10-14): 3600 seconds.

        Returns list of {filename, size_bytes, signed_url, storage_path}.

        Security note (T-10-19): _list_output_files returns flat filenames via
        os.listdir("/sandbox/output/"). No recursion — nested paths are NOT
        supported in v1 (file entry would have filename with '/' which is
        explicitly excluded by the flat-listing implementation).
        """
        try:
            file_list = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._list_output_files(session),
            )
        except Exception as exc:
            logger.warning("sandbox list output files failed: %s", exc)
            return []

        if not file_list:
            return []

        client = get_supabase_client()
        uploaded: list[dict] = []

        for filename, content in file_list:
            # D-P10-13: 4-segment path — user_id/thread_id/execution_id/filename
            storage_path = f"{user_id}/{thread_id}/{execution_id}/{filename}"
            try:
                client.storage.from_("sandbox-outputs").upload(
                    storage_path,
                    content,
                    {"content-type": "application/octet-stream"},
                )
                signed = client.storage.from_("sandbox-outputs").create_signed_url(
                    storage_path, _SIGNED_URL_TTL_SECONDS  # D-P10-14: 1-hour TTL
                )
                signed_url = (
                    signed.get("signedURL")
                    or signed.get("signed_url")
                    or ""
                )
                uploaded.append({
                    "filename": filename,
                    "size_bytes": len(content),
                    "signed_url": signed_url,
                    "storage_path": storage_path,
                })
            except Exception as exc:
                logger.warning(
                    "sandbox upload failed file=%s err=%s", filename, exc
                )

        return uploaded

    def _list_output_files(self, session: SandboxSession) -> list[tuple[str, bytes]]:
        """Return [(filename, content_bytes)] for files in /sandbox/output/.

        Uses execute_command("ls /sandbox/output/") to list files, then
        copy_from_runtime() to retrieve each file's bytes.

        Security note (T-10-19): flat listing only — no recursion. Files with
        '/' in their name are skipped to prevent storage path injection.
        """
        container = session.container
        try:
            ls_result = container.execute_command(f"ls {_OUTPUT_DIR}/")
            if ls_result.exit_code != 0 or not ls_result.stdout.strip():
                return []
        except Exception as exc:
            logger.debug("sandbox ls output dir failed: %s", exc)
            return []

        filenames = [
            f.strip()
            for f in ls_result.stdout.strip().splitlines()
            if f.strip() and "/" not in f.strip()  # T-10-19: no traversal
        ]

        result: list[tuple[str, bytes]] = []
        for filename in filenames:
            container_path = f"{_OUTPUT_DIR}/{filename}"
            with tempfile.TemporaryDirectory() as tmpdir:
                dest_path = os.path.join(tmpdir, filename)
                try:
                    container.copy_from_runtime(container_path, dest_path)
                    with open(dest_path, "rb") as fh:
                        content = fh.read()
                    result.append((filename, content))
                except Exception as exc:
                    logger.warning(
                        "sandbox copy_from_runtime failed file=%s err=%s", filename, exc
                    )

        return result


@lru_cache
def get_sandbox_service() -> SandboxService:
    """Return process-singleton SandboxService instance."""
    return SandboxService()
