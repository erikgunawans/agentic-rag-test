"""TDD tests for POST /threads/{thread_id}/files/upload — Phase 20 Plan 20-06 (UPL-01, UPL-02, SEC-04).

9 tests (W6: 8 → 9 with standalone-workspace test):
  1. Valid PDF (magic bytes %PDF-) → 200 with {ok: True, file_path, size_bytes, source: 'upload'}
  2. Valid DOCX (PK\\x03\\x04 + [Content_Types].xml in first 2 KB) → 200
  3. File >25 MB → 413 with {error: 'upload_too_large', max_bytes, received_bytes}
  4. content-type application/pdf but body NOT starting with %PDF- → 400 {error: 'magic_byte_mismatch'}
  5. content-type application/zip → 400 {error: 'wrong_mime', accepted: [...]}
  6. (W6) workspace_enabled=False → 404 {error: 'workspace_disabled'}
  7. file_path traversal from filename → 400 {error: 'path_invalid'} (server-side path validation)
  8. Successful POST emits workspace_updated SSE event
  9. (W6 NEW) workspace_enabled=True AND harness_enabled=False with valid PDF → 200

Run:
    cd backend && source venv/bin/activate && pytest tests/routers/test_workspace_upload_endpoint.py -v
"""

from __future__ import annotations

import io
import struct
import zipfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers for building valid file bytes
# ---------------------------------------------------------------------------

PDF_BYTES = b"%PDF-1.4 fake content for testing"


def _make_docx_bytes() -> bytes:
    """Build a minimal in-memory ZIP with [Content_Types].xml so magic-byte check passes."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types></Types>')
        zf.writestr("word/document.xml", '<w:document></w:document>')
    return buf.getvalue()


DOCX_BYTES = _make_docx_bytes()
THREAD_ID = "thread-test-abc"
PDF_MIME = "application/pdf"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

# Fake user returned by get_current_user dependency
FAKE_USER = {"id": "user-001", "email": "test@test.com", "token": "fake-token", "role": "user"}


def _make_app(workspace_enabled: bool = True, harness_enabled: bool = True) -> FastAPI:
    """Build a minimal FastAPI test app with the workspace router mounted."""
    app = FastAPI()

    # Override settings so we can control the feature flags per test
    from app.config import Settings

    mock_settings = MagicMock(spec=Settings)
    mock_settings.workspace_enabled = workspace_enabled
    mock_settings.harness_enabled = harness_enabled

    with patch("app.routers.workspace.get_settings", return_value=mock_settings):
        from app.routers.workspace import router
        app.include_router(router)

    # Override the dependency
    from app.dependencies import get_current_user
    app.dependency_overrides[get_current_user] = lambda: FAKE_USER

    # Patch get_settings inline at route-call time (not just at import)
    app.state.mock_settings = mock_settings

    return app


def _client(workspace_enabled: bool = True, harness_enabled: bool = True) -> TestClient:
    app = _make_app(workspace_enabled=workspace_enabled, harness_enabled=harness_enabled)
    return TestClient(app, raise_server_exceptions=False)


def _success_register_result() -> dict:
    return {
        "ok": True,
        "id": "row-001",
        "file_path": f"uploads/contract.pdf",
        "size_bytes": len(PDF_BYTES),
        "storage_path": f"user-001/{THREAD_ID}/row-001/contract.pdf",
        "mime_type": PDF_MIME,
        "source": "upload",
    }


# ---------------------------------------------------------------------------
# Test 1: Valid PDF → 200
# ---------------------------------------------------------------------------

def test_upload_valid_pdf_returns_200():
    """POST with valid PDF magic bytes returns 200 with ok=True payload."""
    success = _success_register_result()

    with patch("app.routers.workspace.get_settings") as mock_gs, \
         patch("app.routers.workspace.WorkspaceService") as MockWS:

        settings = MagicMock()
        settings.workspace_enabled = True
        mock_gs.return_value = settings

        ws_instance = MagicMock()
        ws_instance.register_uploaded_file = AsyncMock(return_value=success)
        MockWS.return_value = ws_instance

        app = FastAPI()
        from app.routers.workspace import router
        from app.dependencies import get_current_user
        app.include_router(router)
        app.dependency_overrides[get_current_user] = lambda: FAKE_USER

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            f"/threads/{THREAD_ID}/files/upload",
            files={"file": ("contract.pdf", PDF_BYTES, PDF_MIME)},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body.get("ok") is True
    assert body.get("source") == "upload"


# ---------------------------------------------------------------------------
# Test 2: Valid DOCX → 200
# ---------------------------------------------------------------------------

def test_upload_valid_docx_returns_200():
    """POST with valid DOCX (PK magic + [Content_Types].xml) returns 200."""
    docx_success = {
        "ok": True,
        "id": "row-002",
        "file_path": "uploads/agreement.docx",
        "size_bytes": len(DOCX_BYTES),
        "storage_path": f"user-001/{THREAD_ID}/row-002/agreement.docx",
        "mime_type": DOCX_MIME,
        "source": "upload",
    }

    with patch("app.routers.workspace.get_settings") as mock_gs, \
         patch("app.routers.workspace.WorkspaceService") as MockWS:

        settings = MagicMock()
        settings.workspace_enabled = True
        mock_gs.return_value = settings

        ws_instance = MagicMock()
        ws_instance.register_uploaded_file = AsyncMock(return_value=docx_success)
        MockWS.return_value = ws_instance

        app = FastAPI()
        from app.routers.workspace import router
        from app.dependencies import get_current_user
        app.include_router(router)
        app.dependency_overrides[get_current_user] = lambda: FAKE_USER

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            f"/threads/{THREAD_ID}/files/upload",
            files={"file": ("agreement.docx", DOCX_BYTES, DOCX_MIME)},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body.get("ok") is True


# ---------------------------------------------------------------------------
# Test 3: File >25 MB → 413
# ---------------------------------------------------------------------------

def test_upload_too_large_returns_413():
    """POST with file exceeding 25 MB returns 413 with structured error."""
    oversize_bytes = b"x" * (25 * 1024 * 1024 + 1)
    # Prepend PDF magic so MIME check passes first, then size check triggers
    content = b"%PDF-" + oversize_bytes

    with patch("app.routers.workspace.get_settings") as mock_gs:
        settings = MagicMock()
        settings.workspace_enabled = True
        mock_gs.return_value = settings

        app = FastAPI()
        from app.routers.workspace import router
        from app.dependencies import get_current_user
        app.include_router(router)
        app.dependency_overrides[get_current_user] = lambda: FAKE_USER

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            f"/threads/{THREAD_ID}/files/upload",
            files={"file": ("big.pdf", content, PDF_MIME)},
        )

    assert resp.status_code == 413
    body = resp.json()
    detail = body.get("detail", body)
    assert detail.get("error") == "upload_too_large"
    assert "max_bytes" in detail
    assert "received_bytes" in detail


# ---------------------------------------------------------------------------
# Test 4: MIME matches PDF but magic bytes wrong → 400 magic_byte_mismatch
# ---------------------------------------------------------------------------

def test_upload_pdf_mime_wrong_magic_bytes_returns_400():
    """POST with content-type=application/pdf but body not starting with %PDF- → 400."""
    fake_content = b"FAKECONTENT not a real pdf"

    with patch("app.routers.workspace.get_settings") as mock_gs:
        settings = MagicMock()
        settings.workspace_enabled = True
        mock_gs.return_value = settings

        app = FastAPI()
        from app.routers.workspace import router
        from app.dependencies import get_current_user
        app.include_router(router)
        app.dependency_overrides[get_current_user] = lambda: FAKE_USER

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            f"/threads/{THREAD_ID}/files/upload",
            files={"file": ("fake.pdf", fake_content, PDF_MIME)},
        )

    assert resp.status_code == 400
    body = resp.json()
    detail = body.get("detail", body)
    assert detail.get("error") == "magic_byte_mismatch"
    assert "expected" in detail
    assert "received" in detail


# ---------------------------------------------------------------------------
# Test 5: Wrong MIME (application/zip) → 400 wrong_mime
# ---------------------------------------------------------------------------

def test_upload_wrong_mime_returns_400():
    """POST with content-type=application/zip → 400 wrong_mime."""
    with patch("app.routers.workspace.get_settings") as mock_gs:
        settings = MagicMock()
        settings.workspace_enabled = True
        mock_gs.return_value = settings

        app = FastAPI()
        from app.routers.workspace import router
        from app.dependencies import get_current_user
        app.include_router(router)
        app.dependency_overrides[get_current_user] = lambda: FAKE_USER

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            f"/threads/{THREAD_ID}/files/upload",
            files={"file": ("archive.zip", b"PK\x03\x04fake", "application/zip")},
        )

    assert resp.status_code == 400
    body = resp.json()
    detail = body.get("detail", body)
    assert detail.get("error") == "wrong_mime"
    assert "accepted" in detail
    assert PDF_MIME in detail["accepted"]


# ---------------------------------------------------------------------------
# Test 6 (W6): workspace_enabled=False → 404 workspace_disabled
# ---------------------------------------------------------------------------

def test_upload_workspace_disabled_returns_404():
    """POST when workspace_enabled=False → 404 with error='workspace_disabled'."""
    with patch("app.routers.workspace.get_settings") as mock_gs:
        settings = MagicMock()
        settings.workspace_enabled = False
        mock_gs.return_value = settings

        app = FastAPI()
        from app.routers.workspace import router
        from app.dependencies import get_current_user
        app.include_router(router)
        app.dependency_overrides[get_current_user] = lambda: FAKE_USER

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            f"/threads/{THREAD_ID}/files/upload",
            files={"file": ("contract.pdf", PDF_BYTES, PDF_MIME)},
        )

    assert resp.status_code == 404
    body = resp.json()
    detail = body.get("detail", body)
    assert detail.get("error") == "workspace_disabled"


# ---------------------------------------------------------------------------
# Test 7: Traversal filename → 400 path_invalid (server-side sanitisation)
# ---------------------------------------------------------------------------

def test_upload_traversal_filename_returns_400():
    """POST with a traversal filename (../escape.pdf) → service raises WorkspaceValidationError → 400."""
    from app.services.workspace_service import WorkspaceValidationError

    with patch("app.routers.workspace.get_settings") as mock_gs, \
         patch("app.routers.workspace.WorkspaceService") as MockWS:

        settings = MagicMock()
        settings.workspace_enabled = True
        mock_gs.return_value = settings

        ws_instance = MagicMock()
        ws_instance.register_uploaded_file = AsyncMock(
            side_effect=WorkspaceValidationError("path_invalid_traversal", ".. segments are forbidden")
        )
        MockWS.return_value = ws_instance

        app = FastAPI()
        from app.routers.workspace import router
        from app.dependencies import get_current_user
        app.include_router(router)
        app.dependency_overrides[get_current_user] = lambda: FAKE_USER

        client = TestClient(app, raise_server_exceptions=False)
        # The client sends a traversal path as filename; server sanitizes but if
        # service still raises we get 400
        resp = client.post(
            f"/threads/{THREAD_ID}/files/upload",
            files={"file": ("../escape.pdf", PDF_BYTES, PDF_MIME)},
        )

    assert resp.status_code == 400
    body = resp.json()
    detail = body.get("detail", body)
    assert detail.get("error") == "path_invalid"


# ---------------------------------------------------------------------------
# Test 8: Successful POST emits workspace_updated SSE event
# ---------------------------------------------------------------------------

def test_upload_success_emits_workspace_updated():
    """Successful upload triggers workspace_updated emission (verified via mock call)."""
    success = _success_register_result()

    with patch("app.routers.workspace.get_settings") as mock_gs, \
         patch("app.routers.workspace.WorkspaceService") as MockWS, \
         patch("app.routers.workspace._emit_workspace_updated") as mock_emit:

        settings = MagicMock()
        settings.workspace_enabled = True
        mock_gs.return_value = settings

        ws_instance = MagicMock()
        ws_instance.register_uploaded_file = AsyncMock(return_value=success)
        MockWS.return_value = ws_instance

        mock_emit.return_value = None

        app = FastAPI()
        from app.routers.workspace import router
        from app.dependencies import get_current_user
        app.include_router(router)
        app.dependency_overrides[get_current_user] = lambda: FAKE_USER

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            f"/threads/{THREAD_ID}/files/upload",
            files={"file": ("contract.pdf", PDF_BYTES, PDF_MIME)},
        )

    assert resp.status_code == 200
    mock_emit.assert_called_once()
    call_kwargs = mock_emit.call_args.kwargs if mock_emit.call_args else {}
    assert call_kwargs.get("thread_id") == THREAD_ID
    assert call_kwargs.get("operation") == "created"
    assert call_kwargs.get("source") == "upload"


# ---------------------------------------------------------------------------
# Test 9 (W6 NEW): workspace_enabled=True, harness_enabled=False → 200 (D-13)
# ---------------------------------------------------------------------------

def test_upload_succeeds_when_workspace_enabled_harness_disabled():
    """D-13: when workspace_enabled=True AND harness_enabled=False, upload still succeeds.

    Files land as source='upload' workspace files — the standalone workspace use case.
    Harness gatekeeper never triggers (no active harness run), but upload itself is fine.
    """
    success = _success_register_result()

    with patch("app.routers.workspace.get_settings") as mock_gs, \
         patch("app.routers.workspace.WorkspaceService") as MockWS:

        settings = MagicMock()
        settings.workspace_enabled = True
        settings.harness_enabled = False  # harness OFF — should NOT affect upload
        mock_gs.return_value = settings

        ws_instance = MagicMock()
        ws_instance.register_uploaded_file = AsyncMock(return_value=success)
        MockWS.return_value = ws_instance

        app = FastAPI()
        from app.routers.workspace import router
        from app.dependencies import get_current_user
        app.include_router(router)
        app.dependency_overrides[get_current_user] = lambda: FAKE_USER

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            f"/threads/{THREAD_ID}/files/upload",
            files={"file": ("contract.pdf", PDF_BYTES, PDF_MIME)},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body.get("ok") is True
    assert body.get("source") == "upload"
