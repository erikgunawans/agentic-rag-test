"""Phase 22 / ISSUE-02 — Unit tests for WorkspaceService.read_binary_file.

Tests 1-4 cover the four branches described in the plan:
  1. Valid binary row → returns bytes (round-trip via read_binary_file)
  2. Missing path → returns structured error dict (no raise)
  3. TEXT row (no storage_path / is_binary=False) → returns structured error
  4. Invalid path → validate_workspace_path rejects (returns dict)

All tests mock WorkspaceService.read_file so no DB/storage calls are made.
httpx.AsyncClient is patched for the happy-path download.

Run:
    cd backend && source venv/bin/activate && \\
        pytest tests/services/test_workspace_read_binary.py -v --tb=short
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.workspace_service import WorkspaceService, WorkspaceValidationError


# ---------------------------------------------------------------------------
# Test 1: valid binary row — read_file returns is_binary=True + signed_url
#         httpx download returns the expected bytes
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_read_binary_file_returns_bytes_for_binary_row():
    """Happy-path: read_file returns is_binary=True + signed_url; httpx fetches bytes."""
    expected_bytes = b"\x00\x01\x02contract content bytes"

    ws = WorkspaceService.__new__(WorkspaceService)

    # Mock read_file to return a binary-row meta dict
    ws.read_file = AsyncMock(return_value={
        "ok": True,
        "is_binary": True,
        "signed_url": "https://storage.example.com/signed/contract.docx?token=abc",
        "size_bytes": len(expected_bytes),
        "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "file_path": "contract.docx",
    })

    # Patch httpx.AsyncClient to return the expected bytes
    mock_response = MagicMock()
    mock_response.content = expected_bytes
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("app.services.workspace_service.httpx.AsyncClient", return_value=mock_client):
        result = await ws.read_binary_file("thread-123", "contract.docx")

    assert isinstance(result, bytes)
    assert result == expected_bytes


# ---------------------------------------------------------------------------
# Test 2: missing path — read_file returns error dict → read_binary_file
#         propagates it as-is (no raise)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_read_binary_file_returns_error_for_missing_file():
    """read_file returns file_not_found → read_binary_file returns that error dict."""
    ws = WorkspaceService.__new__(WorkspaceService)

    ws.read_file = AsyncMock(return_value={
        "error": "file_not_found",
        "file_path": "missing.docx",
    })

    result = await ws.read_binary_file("thread-123", "missing.docx")

    assert isinstance(result, dict)
    assert result["error"] == "file_not_found"
    assert result["file_path"] == "missing.docx"


# ---------------------------------------------------------------------------
# Test 3: TEXT row (is_binary=False) → structured error, not raise
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_read_binary_file_returns_error_for_text_row():
    """read_file returns is_binary=False → read_binary_file returns not_a_binary_file error."""
    ws = WorkspaceService.__new__(WorkspaceService)

    ws.read_file = AsyncMock(return_value={
        "ok": True,
        "is_binary": False,
        "content": "some text content",
        "size_bytes": 17,
        "mime_type": "text/plain",
        "file_path": "notes.md",
    })

    result = await ws.read_binary_file("thread-123", "notes.md")

    assert isinstance(result, dict)
    assert result["error"] == "not_a_binary_file"
    assert result["file_path"] == "notes.md"


# ---------------------------------------------------------------------------
# Test 4: invalid path → validate_workspace_path raises WorkspaceValidationError
#         inside read_file; read_binary_file propagates the error dict
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_read_binary_file_returns_error_for_invalid_path():
    """Invalid path (e.g. traversal) → read_file returns error dict; read_binary_file returns it."""
    ws = WorkspaceService.__new__(WorkspaceService)

    # Simulate what read_file returns for an invalid path
    ws.read_file = AsyncMock(return_value={
        "error": "path_invalid_traversal",
        "detail": "path contains '..' segment",
        "file_path": "../etc/passwd",
    })

    result = await ws.read_binary_file("thread-123", "../etc/passwd")

    assert isinstance(result, dict)
    assert "error" in result
    # Should NOT raise — must return structured dict
