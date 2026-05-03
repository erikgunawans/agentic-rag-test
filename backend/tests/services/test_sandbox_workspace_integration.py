"""Integration tests for sandbox → workspace bridge — Phase 18 / Plan 18-05 (WS-05).

Tests that _collect_and_upload_files calls register_sandbox_files() after upload,
and validates all behavior requirements:

  Test 1: register_sandbox_files called once with correct args after two-file upload
  Test 2: returned uploaded list still has the v1.1 shape (backward compat)
  Test 3: when WORKSPACE_ENABLED=False, register_sandbox_files is NOT called
  Test 4: when register_sandbox_files raises, function still returns uploaded (non-fatal)
  Test 5: when uploaded is empty, register_sandbox_files is NOT called
  Test 6: each SandboxFileEntry.filename matches what came back from sandbox (no mutation)

Run:
    cd backend && source venv/bin/activate && \\
        pytest tests/services/test_sandbox_workspace_integration.py -v --tb=short
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_storage_stub(filenames: list[str], content: bytes = b"data") -> MagicMock:
    """Return a Supabase client stub that simulates sandbox-outputs bucket ops."""
    client = MagicMock()
    bucket = MagicMock()
    client.storage.from_.return_value = bucket
    bucket.upload.return_value = {}
    bucket.create_signed_url.return_value = {"signedURL": "https://example.com/signed"}
    return client


def _stub_session(filenames: list[str], content: bytes = b"\x89PNG") -> MagicMock:
    """Return a SandboxSession-like stub whose container returns the given filenames."""
    session = MagicMock()
    session.container = MagicMock()
    return session


# ---------------------------------------------------------------------------
# Test 1: register_sandbox_files called once with two SandboxFileEntry objects
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_collect_and_upload_calls_register_sandbox_files():
    """WS-05: each sandbox-uploaded file becomes a workspace_files row.

    Arranges a mock sandbox session with two output files, stubs storage upload
    to succeed, and asserts register_sandbox_files is awaited once with the
    correct thread_id, token, and two SandboxFileEntry objects.
    """
    from app.services.sandbox_service import SandboxService

    file_content = b"\x89PNG"
    mock_client = _make_storage_stub(["chart.png", "data.csv"])
    mock_register = AsyncMock(return_value=[{"ok": True}, {"ok": True}])

    with patch("app.services.sandbox_service.get_supabase_client", return_value=mock_client), \
         patch("app.services.sandbox_service.get_settings") as mock_settings, \
         patch("app.services.sandbox_service.SandboxService._list_output_files",
               return_value=[("chart.png", file_content), ("data.csv", b"a,b\n1,2")]), \
         patch("app.services.workspace_service.register_sandbox_files", mock_register):

        mock_settings.return_value = MagicMock(
            workspace_enabled=True,
            sandbox_image="lexcore-sandbox:latest",
            sandbox_docker_host="unix:///var/run/docker.sock",
        )

        svc = SandboxService()
        session = MagicMock()
        uploaded = await svc._collect_and_upload_files(
            session=session,
            user_id="u1",
            thread_id="t1",
            execution_id="e1",
            token="tok123",
        )

    assert len(uploaded) == 2, f"Expected 2 uploaded files, got {len(uploaded)}"
    mock_register.assert_awaited_once()
    call_kwargs = mock_register.await_args.kwargs
    assert call_kwargs["thread_id"] == "t1"
    assert call_kwargs["token"] == "tok123"
    assert len(call_kwargs["files"]) == 2
    filenames_in_entries = [e.filename for e in call_kwargs["files"]]
    assert "chart.png" in filenames_in_entries
    assert "data.csv" in filenames_in_entries


# ---------------------------------------------------------------------------
# Test 2: returned uploaded list still has the v1.1 shape (backward compat)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_uploaded_shape_preserved_after_workspace_registration():
    """WS-05: existing tool_result.output.files shape is unchanged after bridge.

    The upload loop already builds {filename, size_bytes, signed_url, storage_path}.
    Workspace registration must NOT mutate or replace this list.
    """
    from app.services.sandbox_service import SandboxService

    file_content = b"col1,col2\n1,2\n"
    mock_client = _make_storage_stub(["report.csv"])
    mock_register = AsyncMock(return_value=[{"ok": True}])

    with patch("app.services.sandbox_service.get_supabase_client", return_value=mock_client), \
         patch("app.services.sandbox_service.get_settings") as mock_settings, \
         patch("app.services.sandbox_service.SandboxService._list_output_files",
               return_value=[("report.csv", file_content)]), \
         patch("app.services.workspace_service.register_sandbox_files", mock_register):

        mock_settings.return_value = MagicMock(
            workspace_enabled=True,
            sandbox_image="lexcore-sandbox:latest",
            sandbox_docker_host="unix:///var/run/docker.sock",
        )
        svc = SandboxService()
        session = MagicMock()
        uploaded = await svc._collect_and_upload_files(
            session=session,
            user_id="u2",
            thread_id="t2",
            execution_id="e2",
            token="tok",
        )

    assert len(uploaded) == 1, "Expected 1 file in uploaded list"
    entry = uploaded[0]
    assert "filename" in entry, "v1.1 field 'filename' missing"
    assert "size_bytes" in entry, "v1.1 field 'size_bytes' missing"
    assert "signed_url" in entry, "v1.1 field 'signed_url' missing"
    assert "storage_path" in entry, "v1.1 field 'storage_path' missing"
    assert entry["filename"] == "report.csv"
    assert entry["size_bytes"] == len(file_content)
    assert entry["signed_url"] == "https://example.com/signed"


# ---------------------------------------------------------------------------
# Test 3: WORKSPACE_ENABLED=False — register_sandbox_files NOT called
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_workspace_disabled_skips_register():
    """WS-05 kill-switch: when workspace_enabled=False, register_sandbox_files never called.

    This preserves byte-identical behavior vs v1.1 when the feature flag is off.
    """
    from app.services.sandbox_service import SandboxService

    file_content = b"\x89PNG"
    mock_client = _make_storage_stub(["chart.png"])
    mock_register = AsyncMock(return_value=[{"ok": True}])

    with patch("app.services.sandbox_service.get_supabase_client", return_value=mock_client), \
         patch("app.services.sandbox_service.get_settings") as mock_settings, \
         patch("app.services.sandbox_service.SandboxService._list_output_files",
               return_value=[("chart.png", file_content)]), \
         patch("app.services.workspace_service.register_sandbox_files", mock_register):

        mock_settings.return_value = MagicMock(
            workspace_enabled=False,  # Feature flag OFF
            sandbox_image="lexcore-sandbox:latest",
            sandbox_docker_host="unix:///var/run/docker.sock",
        )
        svc = SandboxService()
        session = MagicMock()
        uploaded = await svc._collect_and_upload_files(
            session=session,
            user_id="u3",
            thread_id="t3",
            execution_id="e3",
            token="tok",
        )

    assert len(uploaded) == 1, "Expected uploaded list still returned"
    mock_register.assert_not_awaited(), "register_sandbox_files must NOT be called when workspace_enabled=False"


# ---------------------------------------------------------------------------
# Test 4: register_sandbox_files raises — function still returns uploaded (non-fatal)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_failure_is_non_fatal():
    """WS-05: workspace registration failure must NOT prevent returning uploaded list.

    The exception is caught and logged (warning level); the tool result shape
    is preserved so the frontend still receives signed URLs.
    """
    from app.services.sandbox_service import SandboxService

    file_content = b"data"
    mock_client = _make_storage_stub(["output.txt"])
    mock_register = AsyncMock(side_effect=RuntimeError("Supabase unreachable"))

    with patch("app.services.sandbox_service.get_supabase_client", return_value=mock_client), \
         patch("app.services.sandbox_service.get_settings") as mock_settings, \
         patch("app.services.sandbox_service.SandboxService._list_output_files",
               return_value=[("output.txt", file_content)]), \
         patch("app.services.workspace_service.register_sandbox_files", mock_register):

        mock_settings.return_value = MagicMock(
            workspace_enabled=True,
            sandbox_image="lexcore-sandbox:latest",
            sandbox_docker_host="unix:///var/run/docker.sock",
        )
        svc = SandboxService()
        session = MagicMock()
        # Must NOT raise even when register_sandbox_files raises
        uploaded = await svc._collect_and_upload_files(
            session=session,
            user_id="u4",
            thread_id="t4",
            execution_id="e4",
            token="tok",
        )

    assert len(uploaded) == 1, "uploaded list must be returned even when workspace registration fails"
    assert uploaded[0]["filename"] == "output.txt"


# ---------------------------------------------------------------------------
# Test 5: empty file list — register_sandbox_files NOT called
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_empty_file_list_skips_register():
    """WS-05: when no files are produced, register_sandbox_files must NOT be called.

    Guards against spurious workspace rows or empty-list DB calls.
    """
    from app.services.sandbox_service import SandboxService

    mock_client = _make_storage_stub([])
    mock_register = AsyncMock(return_value=[])

    # No output files — empty list simulates sandbox with no /sandbox/output/ contents
    with patch("app.services.sandbox_service.get_supabase_client", return_value=mock_client), \
         patch("app.services.sandbox_service.get_settings") as mock_settings, \
         patch("app.services.sandbox_service.SandboxService._list_output_files",
               return_value=[]), \
         patch("app.services.workspace_service.register_sandbox_files", mock_register):

        mock_settings.return_value = MagicMock(
            workspace_enabled=True,
            sandbox_image="lexcore-sandbox:latest",
            sandbox_docker_host="unix:///var/run/docker.sock",
        )
        svc = SandboxService()
        session = MagicMock()
        uploaded = await svc._collect_and_upload_files(
            session=session,
            user_id="u5",
            thread_id="t5",
            execution_id="e5",
            token="tok",
        )

    assert uploaded == [], "Expected empty list when no files produced"
    mock_register.assert_not_awaited(), "register_sandbox_files must NOT be called for empty file list"


# ---------------------------------------------------------------------------
# Test 6: SandboxFileEntry.filename matches sandbox listing (no path mutation)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sandbox_file_entry_filenames_not_mutated():
    """WS-05 (T-18-19): filename in SandboxFileEntry must be the raw sandbox filename.

    The _list_output_files call returns flat filenames from ls /sandbox/output/.
    The workspace bridge must pass those exact names to SandboxFileEntry.filename
    without any path prefix manipulation.
    """
    from app.services.sandbox_service import SandboxService

    file_content = b"\x89PNG"
    filenames_from_sandbox = ["analysis_chart.png", "results_2026.csv"]
    captured_entries: list = []

    async def capturing_register(*, token, thread_id, files):
        captured_entries.extend(files)
        return [{"ok": True}] * len(files)

    mock_client = _make_storage_stub(filenames_from_sandbox)

    with patch("app.services.sandbox_service.get_supabase_client", return_value=mock_client), \
         patch("app.services.sandbox_service.get_settings") as mock_settings, \
         patch("app.services.sandbox_service.SandboxService._list_output_files",
               return_value=[(f, file_content) for f in filenames_from_sandbox]), \
         patch("app.services.workspace_service.register_sandbox_files", capturing_register):

        mock_settings.return_value = MagicMock(
            workspace_enabled=True,
            sandbox_image="lexcore-sandbox:latest",
            sandbox_docker_host="unix:///var/run/docker.sock",
        )
        svc = SandboxService()
        session = MagicMock()
        uploaded = await svc._collect_and_upload_files(
            session=session,
            user_id="u6",
            thread_id="t6",
            execution_id="e6",
            token="tok",
        )

    assert len(captured_entries) == 2, f"Expected 2 entries, got {len(captured_entries)}"
    entry_filenames = [e.filename for e in captured_entries]
    for f in filenames_from_sandbox:
        assert f in entry_filenames, (
            f"Filename {f!r} from sandbox must appear unchanged in SandboxFileEntry.filename; "
            f"got {entry_filenames!r}"
        )
