"""TDD tests for WorkspaceService.register_uploaded_file — Phase 20 Plan 20-06 (UPL-01, UPL-02, OBS-02).

6 tests:
  1. Calls write_binary_file with correct bytes.
  2. Upserts workspace_files row with source='upload'.
  3. Audit-logs via audit_service.log_action with action='workspace_file_uploaded'.
  4. Invalid path raises WorkspaceValidationError without writing storage.
  5. write_binary_file failure returns {error: 'storage_write_failed'} without DB insert.
  6. DB insert failure returns {error: 'db_error'} (storage stays — GC deferred).

Run:
    cd backend && source venv/bin/activate && pytest tests/services/test_workspace_upload.py -v
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

THREAD_ID = "thread-abc"
USER_ID = "user-xyz"
USER_EMAIL = "test@test.com"
PDF_CONTENT = b"%PDF-1.4 fake content"
PDF_MIME = "application/pdf"
VALID_PATH = "contract.pdf"
TRAVERSAL_PATH = "../escape.pdf"


def _make_service(token: str = "tok") -> "WorkspaceService":
    from app.services.workspace_service import WorkspaceService
    with patch("app.services.workspace_service.get_supabase_authed_client"):
        svc = WorkspaceService(token=token)
    return svc


# ---------------------------------------------------------------------------
# Test 1: Calls write_binary_file with correct arguments
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_uploaded_file_calls_write_binary_file():
    """register_uploaded_file delegates storage to write_binary_file with the supplied bytes."""
    from app.services.workspace_service import WorkspaceService

    svc = _make_service()

    write_result = {
        "ok": True,
        "operation": "create",
        "size_bytes": len(PDF_CONTENT),
        "file_path": VALID_PATH,
        "storage_path": f"{USER_ID}/{THREAD_ID}/row-id/{VALID_PATH}",
    }

    with patch.object(svc, "write_binary_file", new=AsyncMock(return_value=write_result)) as mock_write, \
         patch("app.services.workspace_service.get_supabase_authed_client") as mock_client, \
         patch("app.services.workspace_service.audit_service") as mock_audit:

        # Mock DB upsert chain
        mock_table = MagicMock()
        mock_client.return_value.table.return_value = mock_table
        mock_table.upsert.return_value.execute.return_value = MagicMock(
            data=[{"id": "row-001"}]
        )

        result = await svc.register_uploaded_file(
            thread_id=THREAD_ID,
            file_path=VALID_PATH,
            content_bytes=PDF_CONTENT,
            mime_type=PDF_MIME,
            user_id=USER_ID,
            user_email=USER_EMAIL,
        )

    mock_write.assert_called_once()
    call_kwargs = mock_write.call_args
    # write_binary_file receives the original bytes
    assert call_kwargs.kwargs.get("content_bytes") == PDF_CONTENT or PDF_CONTENT in call_kwargs.args
    assert result.get("ok") is True


# ---------------------------------------------------------------------------
# Test 2: Upserts workspace_files row with source='upload'
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_uploaded_file_upserts_with_source_upload():
    """register_uploaded_file inserts workspace_files row with source='upload'."""
    from app.services.workspace_service import WorkspaceService

    svc = _make_service()

    write_result = {
        "ok": True,
        "operation": "create",
        "size_bytes": len(PDF_CONTENT),
        "file_path": VALID_PATH,
        "storage_path": f"{USER_ID}/{THREAD_ID}/row-id/{VALID_PATH}",
    }

    with patch.object(svc, "write_binary_file", new=AsyncMock(return_value=write_result)), \
         patch("app.services.workspace_service.get_supabase_authed_client") as mock_client, \
         patch("app.services.workspace_service.audit_service"):

        mock_table = MagicMock()
        mock_client.return_value.table.return_value = mock_table
        upsert_mock = MagicMock()
        mock_table.upsert.return_value = upsert_mock
        upsert_mock.execute.return_value = MagicMock(data=[{"id": "row-001"}])

        await svc.register_uploaded_file(
            thread_id=THREAD_ID,
            file_path=VALID_PATH,
            content_bytes=PDF_CONTENT,
            mime_type=PDF_MIME,
            user_id=USER_ID,
            user_email=USER_EMAIL,
        )

    # Verify upsert was called with source='upload'
    upsert_call = mock_table.upsert.call_args
    assert upsert_call is not None
    upsert_data = upsert_call.args[0] if upsert_call.args else upsert_call.kwargs.get("json", {})
    assert upsert_data.get("source") == "upload"
    assert upsert_data.get("thread_id") == THREAD_ID
    assert upsert_data.get("file_path") == VALID_PATH


# ---------------------------------------------------------------------------
# Test 3: Audit-logs workspace_file_uploaded
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_uploaded_file_audit_logs():
    """register_uploaded_file calls audit_service.log_action with action='workspace_file_uploaded'."""
    from app.services.workspace_service import WorkspaceService

    svc = _make_service()

    write_result = {
        "ok": True,
        "operation": "create",
        "size_bytes": len(PDF_CONTENT),
        "file_path": VALID_PATH,
        "storage_path": f"{USER_ID}/{THREAD_ID}/row-id/{VALID_PATH}",
    }

    with patch.object(svc, "write_binary_file", new=AsyncMock(return_value=write_result)), \
         patch("app.services.workspace_service.get_supabase_authed_client") as mock_client, \
         patch("app.services.workspace_service.audit_service") as mock_audit:

        mock_table = MagicMock()
        mock_client.return_value.table.return_value = mock_table
        mock_table.upsert.return_value.execute.return_value = MagicMock(data=[{"id": "row-001"}])

        await svc.register_uploaded_file(
            thread_id=THREAD_ID,
            file_path=VALID_PATH,
            content_bytes=PDF_CONTENT,
            mime_type=PDF_MIME,
            user_id=USER_ID,
            user_email=USER_EMAIL,
        )

    mock_audit.log_action.assert_called_once()
    audit_call = mock_audit.log_action.call_args
    assert audit_call.kwargs.get("action") == "workspace_file_uploaded"
    assert audit_call.kwargs.get("resource_type") == "workspace_files"
    assert audit_call.kwargs.get("user_id") == USER_ID
    assert audit_call.kwargs.get("user_email") == USER_EMAIL


# ---------------------------------------------------------------------------
# Test 4: Invalid path raises WorkspaceValidationError without writing storage
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_uploaded_file_invalid_path_no_storage_write():
    """register_uploaded_file with traversal path raises WorkspaceValidationError (no storage write)."""
    from app.services.workspace_service import WorkspaceService, WorkspaceValidationError

    svc = _make_service()

    with patch.object(svc, "write_binary_file", new=AsyncMock()) as mock_write, \
         patch("app.services.workspace_service.get_supabase_authed_client"), \
         patch("app.services.workspace_service.audit_service"):

        with pytest.raises(WorkspaceValidationError):
            await svc.register_uploaded_file(
                thread_id=THREAD_ID,
                file_path=TRAVERSAL_PATH,
                content_bytes=PDF_CONTENT,
                mime_type=PDF_MIME,
                user_id=USER_ID,
                user_email=USER_EMAIL,
            )

    # Storage must NOT have been written for an invalid path
    mock_write.assert_not_called()


# ---------------------------------------------------------------------------
# Test 5: write_binary_file failure → returns {error: 'storage_write_failed'}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_uploaded_file_storage_write_failure():
    """When write_binary_file returns error, register_uploaded_file returns storage_write_failed without DB insert."""
    from app.services.workspace_service import WorkspaceService

    svc = _make_service()

    write_error = {"error": "storage_error", "detail": "bucket not found", "file_path": VALID_PATH}

    with patch.object(svc, "write_binary_file", new=AsyncMock(return_value=write_error)), \
         patch("app.services.workspace_service.get_supabase_authed_client") as mock_client, \
         patch("app.services.workspace_service.audit_service") as mock_audit:

        mock_table = MagicMock()
        mock_client.return_value.table.return_value = mock_table

        result = await svc.register_uploaded_file(
            thread_id=THREAD_ID,
            file_path=VALID_PATH,
            content_bytes=PDF_CONTENT,
            mime_type=PDF_MIME,
            user_id=USER_ID,
            user_email=USER_EMAIL,
        )

    assert result.get("error") == "storage_write_failed"
    assert result.get("file_path") == VALID_PATH
    # DB insert must NOT have been attempted
    mock_table.upsert.assert_not_called()
    # Audit must NOT have fired
    mock_audit.log_action.assert_not_called()


# ---------------------------------------------------------------------------
# Test 6: DB insert failure → returns {error: 'db_error'} (storage not cleaned up)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_uploaded_file_db_error():
    """When DB upsert raises, register_uploaded_file returns db_error (storage stays — GC deferred)."""
    from app.services.workspace_service import WorkspaceService

    svc = _make_service()

    write_result = {
        "ok": True,
        "operation": "create",
        "size_bytes": len(PDF_CONTENT),
        "file_path": VALID_PATH,
        "storage_path": f"{USER_ID}/{THREAD_ID}/row-id/{VALID_PATH}",
    }

    with patch.object(svc, "write_binary_file", new=AsyncMock(return_value=write_result)), \
         patch("app.services.workspace_service.get_supabase_authed_client") as mock_client, \
         patch("app.services.workspace_service.audit_service") as mock_audit:

        mock_table = MagicMock()
        mock_client.return_value.table.return_value = mock_table
        mock_table.upsert.return_value.execute.side_effect = Exception("DB connection refused")

        result = await svc.register_uploaded_file(
            thread_id=THREAD_ID,
            file_path=VALID_PATH,
            content_bytes=PDF_CONTENT,
            mime_type=PDF_MIME,
            user_id=USER_ID,
            user_email=USER_EMAIL,
        )

    assert result.get("error") == "db_error"
    assert result.get("file_path") == VALID_PATH
    assert "DB connection refused" in result.get("detail", "")
    # Audit must NOT have fired on DB failure
    mock_audit.log_action.assert_not_called()
