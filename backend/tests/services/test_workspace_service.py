"""Unit tests for WorkspaceService — Phase 18 Plan 18-02 (TDD RED).

Tests cover:
- validate_workspace_path: 11 reject cases (parametrized) + 2 accept cases
- WorkspaceService.write_text_file: create, update, oversize rejection
- WorkspaceService.read_file: text hit, miss
- WorkspaceService.edit_file: success, not-found, ambiguous
- WorkspaceService.list_files: ordering
- RLS: authed client used (not service-role)

Run (unit only):
    cd backend && source venv/bin/activate && \\
        pytest tests/services/test_workspace_service.py -v --tb=short
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call

from app.services.workspace_service import (
    WorkspaceService,
    WorkspaceValidationError,
    validate_workspace_path,
)


# ---------------------------------------------------------------------------
# 1. validate_workspace_path — accept cases
# ---------------------------------------------------------------------------

def test_validate_path_accepts_simple():
    assert validate_workspace_path("notes/research.md") == "notes/research.md"


def test_validate_path_accepts_deep():
    assert validate_workspace_path("data/2026/q1.csv") == "data/2026/q1.csv"


# ---------------------------------------------------------------------------
# 2. validate_workspace_path — reject cases (parametrized)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path,code", [
    ("/abs/path", "path_invalid_leading_slash"),
    ("foo\\bar", "path_invalid_backslash"),
    ("foo/../etc", "path_invalid_traversal"),
    ("..", "path_invalid_traversal"),
    ("a/b/../c", "path_invalid_traversal"),
    ("a" * 501, "path_invalid_too_long"),
    ("", "path_invalid_empty"),
    ("   ", "path_invalid_empty"),
    ("foo/", "path_invalid_trailing_slash"),
    ("foo\x00bar", "path_invalid_control_chars"),
])
def test_validate_path_rejects(path, code):
    with pytest.raises(WorkspaceValidationError) as exc:
        validate_workspace_path(path)
    assert exc.value.code == code


# ---------------------------------------------------------------------------
# Helper: build a mock Supabase client for WorkspaceService
# ---------------------------------------------------------------------------

def _make_mock_client():
    """Return a MagicMock that simulates the Supabase Python client chain."""
    client = MagicMock()
    # Default: table().select().eq().eq().limit().execute() returns empty data
    table_mock = MagicMock()
    client.table.return_value = table_mock
    table_mock.select.return_value = table_mock
    table_mock.eq.return_value = table_mock
    table_mock.limit.return_value = table_mock
    table_mock.order.return_value = table_mock
    table_mock.upsert.return_value = table_mock
    table_mock.execute.return_value = MagicMock(data=[])
    return client


# ---------------------------------------------------------------------------
# 3. write_text_file — create path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestWriteTextFile:

    async def test_write_creates_new_file(self):
        """write_text_file returns {"ok": True, "operation": "create", ...}
        when no existing row is found."""
        mock_client = _make_mock_client()
        # No existing row → operation = "create"
        mock_client.table.return_value.execute.return_value = MagicMock(data=[])

        with patch(
            "app.services.workspace_service.get_supabase_authed_client",
            return_value=mock_client,
        ):
            svc = WorkspaceService("tok")
            result = await svc.write_text_file("thread-1", "x.md", "hello")

        assert result["ok"] is True
        assert result["operation"] == "create"
        assert result["size_bytes"] == 5  # len("hello".encode())
        assert result["file_path"] == "x.md"

    async def test_write_updates_existing_file(self):
        """write_text_file returns {"ok": True, "operation": "update", ...}
        when an existing row is found (SELECT returns data)."""
        mock_client = _make_mock_client()

        call_count = {"n": 0}

        def mock_execute():
            call_count["n"] += 1
            if call_count["n"] == 1:
                # First call: SELECT check → row exists
                return MagicMock(data=[{"id": "existing-id"}])
            # Second call: upsert
            return MagicMock(data=[{"id": "existing-id"}])

        mock_client.table.return_value.execute.side_effect = mock_execute

        with patch(
            "app.services.workspace_service.get_supabase_authed_client",
            return_value=mock_client,
        ):
            svc = WorkspaceService("tok")
            result = await svc.write_text_file("thread-1", "x.md", "hi")

        assert result["ok"] is True
        assert result["operation"] == "update"

    async def test_write_rejects_oversize_content(self):
        """write_text_file returns an error dict (no DB call) when content > 1 MB."""
        mock_client = _make_mock_client()

        with patch(
            "app.services.workspace_service.get_supabase_authed_client",
            return_value=mock_client,
        ):
            svc = WorkspaceService("tok")
            big = "x" * (1024 * 1024 + 1)
            result = await svc.write_text_file("thread-1", "huge.md", big)

        assert result["error"] == "text_content_too_large"
        assert result["limit_bytes"] == 1048576
        assert result["actual_bytes"] == 1048577
        # No DB upsert should have been called
        mock_client.table.return_value.upsert.assert_not_called()

    async def test_write_sets_source_agent_by_default(self):
        """write_text_file uses source='agent' by default."""
        mock_client = _make_mock_client()
        mock_client.table.return_value.execute.return_value = MagicMock(data=[])
        upsert_args = {}

        def capture_upsert(data, **kwargs):
            upsert_args.update(data)
            return mock_client.table.return_value

        mock_client.table.return_value.upsert.side_effect = capture_upsert

        with patch(
            "app.services.workspace_service.get_supabase_authed_client",
            return_value=mock_client,
        ):
            svc = WorkspaceService("tok")
            await svc.write_text_file("thread-1", "x.md", "hello")

        assert upsert_args.get("source") == "agent"

    async def test_write_sets_mime_type_for_markdown(self):
        """write_text_file detects text/markdown for .md files."""
        mock_client = _make_mock_client()
        mock_client.table.return_value.execute.return_value = MagicMock(data=[])
        upsert_args = {}

        def capture_upsert(data, **kwargs):
            upsert_args.update(data)
            return mock_client.table.return_value

        mock_client.table.return_value.upsert.side_effect = capture_upsert

        with patch(
            "app.services.workspace_service.get_supabase_authed_client",
            return_value=mock_client,
        ):
            svc = WorkspaceService("tok")
            await svc.write_text_file("thread-1", "x.md", "hello")

        assert upsert_args.get("mime_type") == "text/markdown"


# ---------------------------------------------------------------------------
# 4. read_file
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestReadFile:

    async def test_read_returns_text_content(self):
        """read_file returns the content for a text file (storage_path is None/absent)."""
        mock_client = _make_mock_client()
        mock_client.table.return_value.execute.return_value = MagicMock(data=[{
            "content": "hi",
            "storage_path": None,
            "storage_bucket": None,
            "size_bytes": 2,
            "mime_type": "text/markdown",
        }])

        with patch(
            "app.services.workspace_service.get_supabase_authed_client",
            return_value=mock_client,
        ):
            svc = WorkspaceService("tok")
            result = await svc.read_file("thread-1", "x.md")

        assert result["ok"] is True
        assert result["is_binary"] is False
        assert result["content"] == "hi"
        assert result["size_bytes"] == 2
        assert result["mime_type"] == "text/markdown"

    async def test_read_returns_not_found(self):
        """read_file returns error dict when no row exists."""
        mock_client = _make_mock_client()
        mock_client.table.return_value.execute.return_value = MagicMock(data=[])

        with patch(
            "app.services.workspace_service.get_supabase_authed_client",
            return_value=mock_client,
        ):
            svc = WorkspaceService("tok")
            result = await svc.read_file("thread-1", "missing.md")

        assert result["error"] == "file_not_found"
        assert result["file_path"] == "missing.md"


# ---------------------------------------------------------------------------
# 5. edit_file
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestEditFile:

    async def test_edit_succeeds(self):
        """edit_file replaces old_string with new_string exactly once.
        After edit, read_file returns updated content."""
        mock_client = _make_mock_client()

        # First call: read_file SELECT → content = "hi"
        # Second call: write_text_file SELECT → no existing row (doesn't matter for logic, will be "update" since we upsert)
        # Third call: write_text_file upsert

        calls = {"n": 0}

        def mock_execute():
            calls["n"] += 1
            if calls["n"] == 1:
                # read_file SELECT
                return MagicMock(data=[{
                    "content": "hi",
                    "storage_path": None,
                    "storage_bucket": None,
                    "size_bytes": 2,
                    "mime_type": "text/markdown",
                }])
            if calls["n"] == 2:
                # write_text_file SELECT check (existing row)
                return MagicMock(data=[{"id": "x"}])
            # write_text_file upsert
            return MagicMock(data=[])

        mock_client.table.return_value.execute.side_effect = mock_execute

        with patch(
            "app.services.workspace_service.get_supabase_authed_client",
            return_value=mock_client,
        ):
            svc = WorkspaceService("tok")
            result = await svc.edit_file("thread-1", "x.md", "hi", "bye")

        assert result["ok"] is True

    async def test_edit_returns_not_found_when_old_string_absent(self):
        """edit_file returns edit_old_string_not_found when old_string not in content."""
        mock_client = _make_mock_client()
        mock_client.table.return_value.execute.return_value = MagicMock(data=[{
            "content": "hello world",
            "storage_path": None,
            "storage_bucket": None,
            "size_bytes": 11,
            "mime_type": "text/plain",
        }])

        with patch(
            "app.services.workspace_service.get_supabase_authed_client",
            return_value=mock_client,
        ):
            svc = WorkspaceService("tok")
            result = await svc.edit_file("thread-1", "x.md", "missing", "x")

        assert result["error"] == "edit_old_string_not_found"

    async def test_edit_returns_not_found_for_missing_y(self):
        """edit_file returns edit_old_string_not_found when the content doesn't contain 'y'."""
        mock_client = _make_mock_client()
        mock_client.table.return_value.execute.return_value = MagicMock(data=[{
            "content": "hello",
            "storage_path": None,
            "storage_bucket": None,
            "size_bytes": 5,
            "mime_type": "text/plain",
        }])

        with patch(
            "app.services.workspace_service.get_supabase_authed_client",
            return_value=mock_client,
        ):
            svc = WorkspaceService("tok")
            result = await svc.edit_file("thread-1", "x.md", "y", "z")

        assert result["error"] == "edit_old_string_not_found"

    async def test_edit_returns_ambiguous_when_multiple_occurrences(self):
        """edit_file returns edit_old_string_ambiguous when old_string appears >1 time."""
        mock_client = _make_mock_client()
        mock_client.table.return_value.execute.return_value = MagicMock(data=[{
            "content": "abcabc",
            "storage_path": None,
            "storage_bucket": None,
            "size_bytes": 6,
            "mime_type": "text/plain",
        }])

        with patch(
            "app.services.workspace_service.get_supabase_authed_client",
            return_value=mock_client,
        ):
            svc = WorkspaceService("tok")
            result = await svc.edit_file("thread-1", "ambig.md", "abc", "x")

        assert result["error"] == "edit_old_string_ambiguous"
        assert result["occurrences"] == 2


# ---------------------------------------------------------------------------
# 6. list_files
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestListFiles:

    async def test_list_files_returns_ordered_rows(self):
        """list_files returns rows ordered by updated_at DESC."""
        rows = [
            {"file_path": "b.md", "size_bytes": 2, "source": "agent", "mime_type": "text/markdown", "updated_at": "2026-01-02T00:00:00Z"},
            {"file_path": "a.md", "size_bytes": 3, "source": "agent", "mime_type": "text/markdown", "updated_at": "2026-01-01T00:00:00Z"},
        ]
        mock_client = _make_mock_client()
        mock_client.table.return_value.execute.return_value = MagicMock(data=rows)

        with patch(
            "app.services.workspace_service.get_supabase_authed_client",
            return_value=mock_client,
        ):
            svc = WorkspaceService("tok")
            result = await svc.list_files("thread-1")

        assert len(result) == 2
        assert result[0]["file_path"] == "b.md"  # most recent first
        # Verify the query used .order("updated_at", desc=True)
        mock_client.table.return_value.order.assert_called_once_with("updated_at", desc=True)


# ---------------------------------------------------------------------------
# 7. RLS invariant: authed client is used (not service-role)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestRLSInvariant:

    async def test_workspace_service_uses_authed_client(self):
        """WorkspaceService.__init__ calls get_supabase_authed_client(token),
        NOT get_supabase_client() (service-role)."""
        mock_client = _make_mock_client()

        with patch(
            "app.services.workspace_service.get_supabase_authed_client",
            return_value=mock_client,
        ) as mock_authed, patch(
            "app.services.workspace_service.get_supabase_client",
        ) as mock_service_role:
            svc = WorkspaceService("mytoken")
            assert svc._client is mock_client
            mock_authed.assert_called_once_with("mytoken")
            mock_service_role.assert_not_called()
