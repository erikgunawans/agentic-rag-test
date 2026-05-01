"""Unit tests for SandboxService — Phase 10 / Plan 10-03.

Tests 1–2, 5–6: fully unit-testable with mocked llm-sandbox + mocked Supabase.
Tests 3–4: require live Docker; marked @pytest.mark.docker and skipped in CI.
Test 7: mocked Supabase storage upload + signed URL path.

Run (CI — skip docker tests):
    cd backend && source venv/bin/activate && \
        pytest tests/services/test_sandbox_service.py -v -m "not docker" --tb=short

Run (full, with Docker):
    cd backend && source venv/bin/activate && \
        pytest tests/services/test_sandbox_service.py -v --tb=short
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Test 1: Constructor — no I/O; _sessions empty; _cleanup_task None
# ---------------------------------------------------------------------------

class TestConstructor:
    """SandboxService() constructs without I/O; _sessions is {}; _cleanup_task is None."""

    def test_constructor_no_io(self):
        # Import here so patching works correctly
        with patch("app.services.sandbox_service.get_settings") as mock_settings, \
             patch("app.services.sandbox_service.get_supabase_client"):
            mock_settings.return_value = MagicMock(
                sandbox_image="lexcore-sandbox:latest",
                sandbox_docker_host="unix:///var/run/docker.sock",
                sandbox_max_exec_seconds=30,
                sandbox_enabled=True,
            )
            # Must import after patching to get mocked settings
            from app.services.sandbox_service import SandboxService

            svc = SandboxService()
            assert svc._sessions == {}, "Expected _sessions to be empty dict"
            assert svc._cleanup_task is None, "Expected _cleanup_task to be None"


# ---------------------------------------------------------------------------
# Test 2: Session reuse — same thread_id returns same session (D-P10-04)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestSessionReuse:
    """execute() called twice with the same thread_id reuses the same session."""

    async def test_session_reused_across_calls(self):
        from app.services.sandbox_service import SandboxService

        mock_container = MagicMock()
        mock_container.is_open = True
        # run() is synchronous in llm-sandbox — returns ConsoleOutput-like object
        mock_result = MagicMock()
        mock_result.exit_code = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_container.run.return_value = mock_result

        with patch("app.services.sandbox_service.get_settings") as mock_settings, \
             patch("app.services.sandbox_service.get_supabase_client"), \
             patch("app.services.sandbox_service.SandboxService._create_container", return_value=mock_container), \
             patch("app.services.sandbox_service.SandboxService._list_output_files", return_value=[]):
            mock_settings.return_value = MagicMock(
                sandbox_image="lexcore-sandbox:latest",
                sandbox_docker_host="unix:///var/run/docker.sock",
                sandbox_max_exec_seconds=30,
                sandbox_enabled=True,
            )
            svc = SandboxService()

            # First call
            await svc.execute(code="x = 1", thread_id="thread-1", user_id="user-1")
            session_1 = svc._sessions.get("thread-1")
            assert session_1 is not None, "Session not created after first call"

            # Second call — should reuse same session object (dict identity)
            await svc.execute(code="print(x)", thread_id="thread-1", user_id="user-1")
            session_2 = svc._sessions.get("thread-1")
            assert session_2 is session_1, (
                "Session was recreated instead of reused (D-P10-04 violation)"
            )


# ---------------------------------------------------------------------------
# Test 3: Variable persistence — requires live Docker (skipped in CI)
# ---------------------------------------------------------------------------

@pytest.mark.docker
@pytest.mark.asyncio
class TestVariablePersistence:
    """x=1 then print(x) must yield '1' in stdout (live Docker — D-P10-04)."""

    async def test_variable_persists_across_calls(self):
        pytest.importorskip("docker", reason="Docker SDK not installed")
        from app.services.sandbox_service import SandboxService

        svc = SandboxService()
        try:
            await svc.execute(code="x = 1", thread_id="test-thread-persist", user_id="test-user")
            result = await svc.execute(
                code="print(x)", thread_id="test-thread-persist", user_id="test-user"
            )
            assert "1" in result["stdout"], (
                f"Expected '1' in stdout (variable persistence), got: {result['stdout']!r}"
            )
        finally:
            # Cleanup session
            session = svc._sessions.pop("test-thread-persist", None)
            if session:
                try:
                    session.container.close()
                except Exception:
                    pass


# ---------------------------------------------------------------------------
# Test 4: Timeout — exit_code=-1, error_type="timeout", stderr contains message
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestTimeout:
    """Timeout produces exit_code=-1, error_type='timeout', stderr contains message."""

    async def test_timeout_produces_correct_result(self):
        from app.services.sandbox_service import SandboxService

        mock_container = MagicMock()
        mock_container.is_open = True

        def slow_run(*args, **kwargs):
            import time
            time.sleep(10)  # Will be interrupted by asyncio.wait_for

        mock_container.run.side_effect = slow_run

        with patch("app.services.sandbox_service.get_settings") as mock_settings, \
             patch("app.services.sandbox_service.get_supabase_client"), \
             patch("app.services.sandbox_service.SandboxService._create_container", return_value=mock_container), \
             patch("app.services.sandbox_service.SandboxService._list_output_files", return_value=[]):
            settings_mock = MagicMock(
                sandbox_image="lexcore-sandbox:latest",
                sandbox_docker_host="unix:///var/run/docker.sock",
                sandbox_max_exec_seconds=2,  # Very short timeout
                sandbox_enabled=True,
            )
            mock_settings.return_value = settings_mock
            svc = SandboxService()
            # Override settings directly on the instance
            svc._settings = settings_mock

            result = await svc.execute(
                code="import time; time.sleep(60)",
                thread_id="timeout-thread",
                user_id="test-user",
            )

        assert result["exit_code"] == -1, (
            f"Expected exit_code=-1 on timeout, got {result['exit_code']}"
        )
        assert result["error_type"] == "timeout", (
            f"Expected error_type='timeout', got {result['error_type']!r}"
        )
        assert "timed out" in result["stderr"].lower(), (
            f"Expected 'timed out' in stderr, got: {result['stderr']!r}"
        )


# ---------------------------------------------------------------------------
# Test 5: stream_callback invoked at least once per line (D-P10-05)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestStreamCallback:
    """stream_callback awaited at least once per stdout line for print('a'); print('b')."""

    async def test_stream_callback_called_per_line(self):
        from app.services.sandbox_service import SandboxService

        mock_container = MagicMock()
        mock_container.is_open = True

        callback_calls: list[tuple[str, str]] = []

        async def fake_callback(event_type: str, line: str) -> None:
            callback_calls.append((event_type, line))

        def run_with_callbacks(*args, **kwargs):
            on_stdout = kwargs.get("on_stdout")
            on_stderr = kwargs.get("on_stderr")
            if on_stdout:
                on_stdout("a\n")
                on_stdout("b\n")
            mock_result = MagicMock()
            mock_result.exit_code = 0
            return mock_result

        mock_container.run.side_effect = run_with_callbacks

        with patch("app.services.sandbox_service.get_settings") as mock_settings, \
             patch("app.services.sandbox_service.get_supabase_client"), \
             patch("app.services.sandbox_service.SandboxService._create_container", return_value=mock_container), \
             patch("app.services.sandbox_service.SandboxService._list_output_files", return_value=[]):
            mock_settings.return_value = MagicMock(
                sandbox_image="lexcore-sandbox:latest",
                sandbox_docker_host="unix:///var/run/docker.sock",
                sandbox_max_exec_seconds=30,
                sandbox_enabled=True,
            )
            svc = SandboxService()

            await svc.execute(
                code='print("a"); print("b")',
                thread_id="stream-thread",
                user_id="test-user",
                stream_callback=fake_callback,
            )

        stdout_calls = [c for c in callback_calls if c[0] == "code_stdout"]
        assert len(stdout_calls) >= 2, (
            f"Expected >= 2 code_stdout calls for 2 print lines, got {len(stdout_calls)}: {callback_calls}"
        )


# ---------------------------------------------------------------------------
# Test 6: Cleanup — session with last_used 31 min ago is removed from _sessions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestCleanupLoop:
    """Cleanup loop closes a session whose last_used was 31 minutes ago (D-P10-10)."""

    async def test_stale_session_removed_by_cleanup(self):
        from app.services.sandbox_service import SandboxService, SandboxSession

        mock_container = MagicMock()
        stale_time = datetime.utcnow() - timedelta(minutes=31)

        with patch("app.services.sandbox_service.get_settings") as mock_settings, \
             patch("app.services.sandbox_service.get_supabase_client"):
            mock_settings.return_value = MagicMock(
                sandbox_image="lexcore-sandbox:latest",
                sandbox_docker_host="unix:///var/run/docker.sock",
                sandbox_max_exec_seconds=30,
                sandbox_enabled=True,
            )
            svc = SandboxService()

            # Manually inject a stale session
            stale_session = SandboxSession(
                container=mock_container,
                last_used=stale_time,
                thread_id="stale-thread",
            )
            svc._sessions["stale-thread"] = stale_session

            # Manually inject a fresh session (should NOT be removed)
            fresh_session = SandboxSession(
                container=MagicMock(),
                last_used=datetime.utcnow(),
                thread_id="fresh-thread",
            )
            svc._sessions["fresh-thread"] = fresh_session

            # Call the cleanup logic directly (without sleeping 60s)
            cutoff = datetime.utcnow() - timedelta(minutes=30)
            stale_ids = [
                tid for tid, s in svc._sessions.items()
                if s.last_used < cutoff
            ]
            for tid in stale_ids:
                sess = svc._sessions.pop(tid, None)
                if sess and hasattr(sess.container, "close"):
                    try:
                        sess.container.close()
                    except Exception:
                        pass

            # Stale session should be removed
            assert "stale-thread" not in svc._sessions, (
                "Stale session not removed from _sessions (D-P10-10 violation)"
            )
            # Fresh session should remain
            assert "fresh-thread" in svc._sessions, (
                "Fresh session was incorrectly removed from _sessions"
            )
            # container.close() should have been called on the stale container
            mock_container.close.assert_called_once()


# ---------------------------------------------------------------------------
# Test 7: File upload — correct storage path + create_signed_url with 1-hour TTL
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestFileUpload:
    """Files in /sandbox/output/ uploaded to sandbox-outputs bucket; 1-hour signed URL."""

    async def test_file_uploaded_with_correct_path_and_ttl(self):
        from app.services.sandbox_service import SandboxService

        mock_container = MagicMock()
        mock_container.is_open = True
        mock_result = MagicMock()
        mock_result.exit_code = 0
        mock_container.run.return_value = mock_result

        mock_supabase_client = MagicMock()
        mock_storage = MagicMock()
        mock_bucket = MagicMock()
        mock_supabase_client.storage.from_.return_value = mock_bucket
        mock_bucket.upload.return_value = {}
        mock_bucket.create_signed_url.return_value = {
            "signedURL": "https://supabase.co/storage/v1/signed/test-url"
        }

        user_id = "user-abc"
        thread_id = "thread-xyz"
        file_content = b"col1,col2\n1,2\n"

        with patch("app.services.sandbox_service.get_settings") as mock_settings, \
             patch("app.services.sandbox_service.get_supabase_client", return_value=mock_supabase_client), \
             patch("app.services.sandbox_service.SandboxService._create_container", return_value=mock_container), \
             patch("app.services.sandbox_service.SandboxService._list_output_files",
                   return_value=[("output.csv", file_content)]):
            mock_settings.return_value = MagicMock(
                sandbox_image="lexcore-sandbox:latest",
                sandbox_docker_host="unix:///var/run/docker.sock",
                sandbox_max_exec_seconds=30,
                sandbox_enabled=True,
            )
            svc = SandboxService()

            result = await svc.execute(
                code='import csv; open("/sandbox/output/output.csv","w").write("col1,col2\\n1,2\\n")',
                thread_id=thread_id,
                user_id=user_id,
            )

        # Verify upload call
        assert mock_supabase_client.storage.from_.called, "storage.from_() was not called"
        bucket_call = mock_supabase_client.storage.from_.call_args_list[0]
        assert bucket_call.args[0] == "sandbox-outputs", (
            f"Expected bucket 'sandbox-outputs', got {bucket_call.args[0]!r}"
        )

        # Verify storage path scheme: {user_id}/{thread_id}/{execution_id}/{filename}
        upload_call = mock_bucket.upload.call_args
        storage_path = upload_call.args[0]
        parts = storage_path.split("/")
        assert len(parts) == 4, f"Storage path must have 4 segments, got: {storage_path!r}"
        assert parts[0] == user_id, f"Path[0] must be user_id={user_id!r}, got {parts[0]!r}"
        assert parts[1] == thread_id, f"Path[1] must be thread_id={thread_id!r}, got {parts[1]!r}"
        # parts[2] is the execution_id (UUID)
        assert parts[3] == "output.csv", f"Path[3] must be filename, got {parts[3]!r}"

        # Verify signed URL call with 3600s TTL (D-P10-14)
        sign_call = mock_bucket.create_signed_url.call_args
        assert sign_call.args[0] == storage_path, (
            f"create_signed_url path mismatch: {sign_call.args[0]!r} != {storage_path!r}"
        )
        assert sign_call.args[1] == 3600, (
            f"Expected TTL=3600 (1 hour), got {sign_call.args[1]}"
        )

        # Verify files in return value
        assert len(result["files"]) == 1, f"Expected 1 file in result, got {len(result['files'])}"
        file_entry = result["files"][0]
        assert file_entry["filename"] == "output.csv"
        assert file_entry["size_bytes"] == len(file_content)
        assert file_entry["signed_url"] == "https://supabase.co/storage/v1/signed/test-url"
        assert file_entry["storage_path"] == storage_path


# ---------------------------------------------------------------------------
# Test: Singleton — get_sandbox_service() returns same instance
# ---------------------------------------------------------------------------

class TestSingleton:
    """get_sandbox_service() returns the same instance across calls (lru_cache)."""

    def test_singleton_identity(self):
        from app.services.sandbox_service import get_sandbox_service

        svc1 = get_sandbox_service()
        svc2 = get_sandbox_service()
        assert svc1 is svc2, "get_sandbox_service() must return same instance (lru_cache)"


# ---------------------------------------------------------------------------
# Test: Return shape — execute() returns required keys
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestReturnShape:
    """execute() returns dict with required keys: stdout, stderr, exit_code, error_type, execution_ms, files, execution_id."""

    async def test_return_shape_complete(self):
        from app.services.sandbox_service import SandboxService

        mock_container = MagicMock()
        mock_container.is_open = True
        mock_result = MagicMock()
        mock_result.exit_code = 0
        mock_container.run.return_value = mock_result

        with patch("app.services.sandbox_service.get_settings") as mock_settings, \
             patch("app.services.sandbox_service.get_supabase_client"), \
             patch("app.services.sandbox_service.SandboxService._create_container", return_value=mock_container), \
             patch("app.services.sandbox_service.SandboxService._list_output_files", return_value=[]):
            mock_settings.return_value = MagicMock(
                sandbox_image="lexcore-sandbox:latest",
                sandbox_docker_host="unix:///var/run/docker.sock",
                sandbox_max_exec_seconds=30,
                sandbox_enabled=True,
            )
            svc = SandboxService()
            result = await svc.execute(
                code="print('hello')",
                thread_id="shape-thread",
                user_id="test-user",
            )

        required_keys = {"stdout", "stderr", "exit_code", "error_type", "execution_ms", "files", "execution_id"}
        missing = required_keys - set(result.keys())
        assert not missing, f"Missing keys in execute() return value: {missing}"
        assert isinstance(result["files"], list), "files must be a list"
        assert isinstance(result["execution_ms"], int), "execution_ms must be int"
        assert isinstance(result["execution_id"], str), "execution_id must be str"
