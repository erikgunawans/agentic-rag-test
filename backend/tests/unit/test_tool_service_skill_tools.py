"""Unit tests for the 3 Phase 8 skill tools in tool_service.py.

Covers: SKILL-08 (load_skill), SKILL-09 (save_skill), SFILE-02 (load_skill files
table), SFILE-03 (read_skill_file inline + binary metadata-only).
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest

from app.services.tool_service import ToolService


@pytest.fixture
def service():
    return ToolService()


def _mock_authed_client(skill_rows=None, file_rows=None, insert_data=None,
                        update_data=None, insert_error_code=None,
                        existing_id_for_conflict=None, file_bytes=None):
    """Build a MagicMock that mimics the chained .table().select().eq()...execute() API."""
    client = MagicMock()

    def _select_chain(rows):
        chain = MagicMock()
        chain.execute.return_value.data = rows
        chain.eq.return_value = chain
        chain.order.return_value = chain
        chain.limit.return_value = chain
        chain.select.return_value = chain
        return chain

    def _insert(payload):
        chain = MagicMock()
        if insert_error_code:
            from postgrest.exceptions import APIError as PostgrestAPIError
            err = PostgrestAPIError({"code": insert_error_code, "message": "duplicate", "details": "", "hint": ""})
            chain.execute.side_effect = err
        else:
            chain.execute.return_value.data = insert_data or []
        return chain

    def _update(payload):
        chain = MagicMock()
        chain.execute.return_value.data = update_data or []
        chain.eq.return_value = chain
        return chain

    def _table(name):
        t = MagicMock()
        if name == "skills":
            t.select.return_value = _select_chain(skill_rows or [])
            t.insert = _insert
            t.update = _update
        elif name == "skill_files":
            t.select.return_value = _select_chain(file_rows or [])
        return t

    client.table = _table
    # storage download
    storage = MagicMock()
    bucket = MagicMock()
    bucket.download.return_value = file_bytes or b""
    storage.from_.return_value = bucket
    client.storage = storage
    return client


# ── load_skill ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_load_skill_returns_full_skill_with_files(service):
    client = _mock_authed_client(
        skill_rows=[{
            "id": "skill-uuid", "name": "legal-review",
            "description": "Reviews NDAs", "instructions": "Step 1...",
            "enabled": True,
        }],
        file_rows=[
            {"filename": "clauses.md", "size_bytes": 1234, "mime_type": "text/markdown"},
            {"filename": "template.pdf", "size_bytes": 5000, "mime_type": "application/pdf"},
        ],
    )
    with patch("app.services.tool_service.get_supabase_authed_client", return_value=client):
        result = await service.execute_tool(
            "load_skill", {"name": "legal-review"}, user_id="u1", token="tok",
        )
    assert result["name"] == "legal-review"
    assert result["description"] == "Reviews NDAs"
    assert result["instructions"] == "Step 1..."
    assert isinstance(result["files"], list)
    assert len(result["files"]) == 2
    assert result["files"][0] == {
        "filename": "clauses.md", "size_bytes": 1234, "mime_type": "text/markdown",
    }


@pytest.mark.asyncio
async def test_load_skill_unknown_name_returns_error(service):
    client = _mock_authed_client(skill_rows=[])
    with patch("app.services.tool_service.get_supabase_authed_client", return_value=client):
        result = await service.execute_tool(
            "load_skill", {"name": "nonexistent"}, user_id="u1", token="tok",
        )
    assert result["error"] == "skill_not_found"
    assert result["name"] == "nonexistent"


@pytest.mark.asyncio
async def test_load_skill_no_token_returns_auth_error(service):
    result = await service.execute_tool(
        "load_skill", {"name": "any"}, user_id="u1", token=None,
    )
    assert result["error"] == "auth_required"


# ── save_skill ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_save_skill_create_success(service):
    client = _mock_authed_client(
        insert_data=[{
            "id": "new-uuid", "name": "n", "description": "d" * 25,
            "instructions": "i", "enabled": True,
        }],
    )
    with patch("app.services.tool_service.get_supabase_authed_client", return_value=client):
        result = await service.execute_tool(
            "save_skill",
            {"name": "my-skill", "description": "d" * 25, "instructions": "do x"},
            user_id="u1", token="tok",
        )
    assert result["skill_id"] == "new-uuid"
    assert result["message"] == "Skill saved successfully."
    assert result["enabled"] is True


@pytest.mark.asyncio
async def test_save_skill_name_conflict_returns_existing_id(service):
    # Configure: insert raises 23505; subsequent select returns existing_id row
    client = _mock_authed_client(
        insert_error_code="23505",
        skill_rows=[{"id": "existing-uuid"}],
    )
    with patch("app.services.tool_service.get_supabase_authed_client", return_value=client):
        result = await service.execute_tool(
            "save_skill",
            {"name": "legal-review", "description": "d" * 25, "instructions": "i"},
            user_id="u1", token="tok",
        )
    assert result["error"] == "name_conflict"
    assert result["existing_skill_id"] == "existing-uuid"
    assert "update=true" in result["hint"]


@pytest.mark.asyncio
async def test_save_skill_update_success(service):
    client = _mock_authed_client(
        update_data=[{
            "id": "ex-uuid", "name": "n", "description": "d" * 25,
            "instructions": "new", "enabled": True,
        }],
    )
    with patch("app.services.tool_service.get_supabase_authed_client", return_value=client):
        result = await service.execute_tool(
            "save_skill",
            {"name": "n", "description": "d" * 25, "instructions": "new",
             "update": True, "skill_id": "ex-uuid"},
            user_id="u1", token="tok",
        )
    assert result["skill_id"] == "ex-uuid"
    assert result["instructions"] == "new"
    assert result["message"] == "Skill saved successfully."


@pytest.mark.asyncio
async def test_save_skill_update_missing_skill_id(service):
    result = await service.execute_tool(
        "save_skill",
        {"name": "n", "description": "d" * 25, "instructions": "i", "update": True},
        user_id="u1", token="tok",
    )
    assert result["error"] == "missing_skill_id"


@pytest.mark.asyncio
async def test_save_skill_invalid_name_format(service):
    result = await service.execute_tool(
        "save_skill",
        {"name": "Bad Name!", "description": "d" * 25, "instructions": "i"},
        user_id="u1", token="tok",
    )
    assert result["error"] == "invalid_name"


# ── read_skill_file ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_read_skill_file_text_inline_under_cap(service):
    client = _mock_authed_client(
        file_rows=[{
            "filename": "notes.md", "size_bytes": 100,
            "mime_type": "text/markdown", "storage_path": "u1/s1/notes.md",
        }],
        file_bytes=b"# Hello world",
    )
    with patch("app.services.tool_service.get_supabase_authed_client", return_value=client):
        result = await service.execute_tool(
            "read_skill_file",
            {"skill_id": "s1", "filename": "notes.md"},
            user_id="u1", token="tok",
        )
    assert result["filename"] == "notes.md"
    assert result["content"] == "# Hello world"
    assert result["truncated"] is False
    assert result["message"] is None


@pytest.mark.asyncio
async def test_read_skill_file_text_truncated_at_8000(service):
    big = b"x" * 12000
    client = _mock_authed_client(
        file_rows=[{
            "filename": "big.txt", "size_bytes": 12000,
            "mime_type": "text/plain", "storage_path": "u1/s1/big.txt",
        }],
        file_bytes=big,
    )
    with patch("app.services.tool_service.get_supabase_authed_client", return_value=client):
        result = await service.execute_tool(
            "read_skill_file",
            {"skill_id": "s1", "filename": "big.txt"},
            user_id="u1", token="tok",
        )
    assert result["truncated"] is True
    assert len(result["content"]) == 8000
    assert result["total_bytes"] == 12000
    assert result["message"] == "Content truncated at 8000 chars."


@pytest.mark.asyncio
async def test_read_skill_file_binary_returns_metadata_only(service):
    client = _mock_authed_client(
        file_rows=[{
            "filename": "doc.pdf", "size_bytes": 142000,
            "mime_type": "application/pdf", "storage_path": "u1/s1/doc.pdf",
        }],
        file_bytes=b"%PDF...",
    )
    with patch("app.services.tool_service.get_supabase_authed_client", return_value=client):
        result = await service.execute_tool(
            "read_skill_file",
            {"skill_id": "s1", "filename": "doc.pdf"},
            user_id="u1", token="tok",
        )
    assert result["readable"] is False
    assert result["mime_type"] == "application/pdf"
    assert "content" not in result
    assert "Binary file" in result["message"]


@pytest.mark.asyncio
async def test_read_skill_file_unknown_filename(service):
    client = _mock_authed_client(file_rows=[])
    with patch("app.services.tool_service.get_supabase_authed_client", return_value=client):
        result = await service.execute_tool(
            "read_skill_file",
            {"skill_id": "s1", "filename": "missing.md"},
            user_id="u1", token="tok",
        )
    assert result["error"] == "file_not_found"
