"""Unit tests for WorkspaceService.append_line — Phase 21 Plan 21-01.

Phase 21 BATCH-05/D-05 + BATCH-07/D-07 — atomic JSONL append primitive used by
`llm_batch_agents` to record each completed sub-agent on its own newline.

Tests cover (per plan 21-01 acceptance):
1. test_append_line_first_write              — no existing row, creates with content = "foo\\n"
2. test_append_line_appends_to_existing      — existing "a\\n", appends "b" → "a\\nb\\n"
3. test_append_line_rejects_invalid_path     — path traversal → invalid_path error, no DB
4. test_append_line_enforces_size_cap        — would exceed 1 MB → content_too_large, no write
5. test_append_line_db_error                 — write_text_file raises → db_error dict
6. test_append_line_serializes_via_per_key_lock
   - sub-test a: lock identity (same key → same Lock instance)
   - sub-test b: 5 concurrent gather()'d appends produce 5 lines, no overwrite

Run:
    cd backend && source venv/bin/activate && \
        pytest tests/services/test_workspace_service_append_line.py -v --tb=short
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from app.services.workspace_service import (
    MAX_TEXT_CONTENT_BYTES,
    WorkspaceService,
)


# ---------------------------------------------------------------------------
# Helper: build a mock Supabase client (mirrors test_workspace_service.py)
# ---------------------------------------------------------------------------

def _make_mock_client():
    """Return a MagicMock that simulates the Supabase Python client chain."""
    client = MagicMock()
    table_mock = MagicMock()
    client.table.return_value = table_mock
    table_mock.select.return_value = table_mock
    table_mock.eq.return_value = table_mock
    table_mock.limit.return_value = table_mock
    table_mock.order.return_value = table_mock
    table_mock.upsert.return_value = table_mock
    table_mock.execute.return_value = MagicMock(data=[])
    return client


@pytest.fixture(autouse=True)
def _clear_append_lock_map():
    """Clear the class-level lock map between tests to avoid leakage."""
    yield
    # Best-effort: tolerate the attribute not existing yet on RED.
    if hasattr(WorkspaceService, "_append_locks"):
        WorkspaceService._append_locks.clear()


# ---------------------------------------------------------------------------
# 1. First-write semantics — file does not yet exist
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_append_line_first_write():
    """append_line creates the row when read_file returns file_not_found.

    Expected: returned dict ok=True, operation='append', size_bytes=4,
    file_path='x.jsonl' (the line 'foo' becomes 'foo\\n', 4 bytes).
    """
    mock_client = _make_mock_client()
    # Read returns "no row" (file_not_found path); write upserts cleanly.
    mock_client.table.return_value.execute.return_value = MagicMock(data=[])

    with patch(
        "app.services.workspace_service.get_supabase_authed_client",
        return_value=mock_client,
    ):
        svc = WorkspaceService("tok")
        result = await svc.append_line("thread-1", "x.jsonl", "foo")

    assert result["ok"] is True
    assert result["operation"] == "append"
    assert result["size_bytes"] == 4  # len("foo\n".encode())
    assert result["file_path"] == "x.jsonl"


# ---------------------------------------------------------------------------
# 2. Append to existing content
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_append_line_appends_to_existing():
    """append_line concatenates `line + "\\n"` to existing content.

    Pre-state: row content = "a\\n" (size 2). Action: append_line('b').
    Post-state: returned size_bytes = 4 (a + \\n + b + \\n).
    """
    mock_client = _make_mock_client()

    calls = {"n": 0}

    def mock_execute():
        calls["n"] += 1
        if calls["n"] == 1:
            # read_file SELECT → returns existing content
            return MagicMock(data=[{
                "content": "a\n",
                "storage_path": None,
                "storage_bucket": None,
                "size_bytes": 2,
                "mime_type": "application/octet-stream",
            }])
        if calls["n"] == 2:
            # write_text_file existing-row SELECT
            return MagicMock(data=[{"id": "row-1"}])
        # write_text_file upsert
        return MagicMock(data=[{"id": "row-1"}])

    mock_client.table.return_value.execute.side_effect = mock_execute

    with patch(
        "app.services.workspace_service.get_supabase_authed_client",
        return_value=mock_client,
    ):
        svc = WorkspaceService("tok")
        result = await svc.append_line("thread-1", "x.jsonl", "b")

    assert result["ok"] is True
    assert result["operation"] == "append"
    assert result["size_bytes"] == 4
    assert result["file_path"] == "x.jsonl"


# ---------------------------------------------------------------------------
# 3. Path validation — invalid path rejected, no DB call
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_append_line_rejects_invalid_path():
    """Path traversal must return error dict and skip all DB calls."""
    mock_client = _make_mock_client()

    with patch(
        "app.services.workspace_service.get_supabase_authed_client",
        return_value=mock_client,
    ):
        svc = WorkspaceService("tok")
        result = await svc.append_line("thread-1", "../escape.jsonl", "evil")

    assert "error" in result
    assert result["error"] == "path_invalid_traversal"
    assert result["file_path"] == "../escape.jsonl"
    # Defensive: no upsert was issued
    mock_client.table.return_value.upsert.assert_not_called()


# ---------------------------------------------------------------------------
# 4. Size-cap enforcement — would exceed MAX_TEXT_CONTENT_BYTES
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_append_line_enforces_size_cap():
    """When current_bytes + new_segment_bytes > 1 MB, return content_too_large.

    Pre-state: existing content size = MAX_TEXT_CONTENT_BYTES - 1 bytes.
    Action: append_line('foo') would add 4 bytes ('foo\\n') → exceeds cap.
    Expected: error 'content_too_large', limit_bytes 1048576, no upsert.
    """
    mock_client = _make_mock_client()

    big_existing = "x" * (MAX_TEXT_CONTENT_BYTES - 1)

    calls = {"n": 0}

    def mock_execute():
        calls["n"] += 1
        if calls["n"] == 1:
            # read_file SELECT → returns near-full content
            return MagicMock(data=[{
                "content": big_existing,
                "storage_path": None,
                "storage_bucket": None,
                "size_bytes": MAX_TEXT_CONTENT_BYTES - 1,
                "mime_type": "application/octet-stream",
            }])
        # No further calls expected — cap check happens BEFORE write
        return MagicMock(data=[])

    mock_client.table.return_value.execute.side_effect = mock_execute

    with patch(
        "app.services.workspace_service.get_supabase_authed_client",
        return_value=mock_client,
    ):
        svc = WorkspaceService("tok")
        result = await svc.append_line("thread-1", "huge.jsonl", "foo")

    assert result["error"] == "content_too_large"
    assert result["limit_bytes"] == MAX_TEXT_CONTENT_BYTES
    assert result["file_path"] == "huge.jsonl"
    mock_client.table.return_value.upsert.assert_not_called()


# ---------------------------------------------------------------------------
# 5. DB error path — read_file or write_text_file raises
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_append_line_db_error():
    """When the underlying DB call raises, return structured db_error dict.

    Mock the read_file SELECT to raise — append_line must convert to
    {error: 'db_error', detail: <str>, file_path: ...}.
    """
    mock_client = _make_mock_client()

    def boom():
        raise RuntimeError("simulated db down")

    mock_client.table.return_value.execute.side_effect = boom

    with patch(
        "app.services.workspace_service.get_supabase_authed_client",
        return_value=mock_client,
    ):
        svc = WorkspaceService("tok")
        result = await svc.append_line("thread-1", "x.jsonl", "foo")

    assert result["error"] == "db_error"
    assert "detail" in result
    assert isinstance(result["detail"], str)
    assert result["file_path"] == "x.jsonl"


# ---------------------------------------------------------------------------
# 6. Per-key lock identity + concurrent serialization
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_append_line_serializes_via_per_key_lock():
    """Two assertions in one test:

    a) Lock identity: _get_append_lock returns the SAME asyncio.Lock for the
       same (thread_id, file_path) tuple — proves the cache map keys correctly.

    b) Concurrent gather(): 5 parallel append_line('x') calls against the same
       (thread, path) produce a final content of 'x\\n' * 5 (5 lines, no
       overwrite). Stateful read/write mock simulates the DB row.
    """
    # ---- (a) Lock identity ------------------------------------------------
    lock_a = WorkspaceService._get_append_lock("t", "p.jsonl")
    lock_b = WorkspaceService._get_append_lock("t", "p.jsonl")
    assert lock_a is lock_b, "per-key lock must be identity-stable"
    assert isinstance(lock_a, asyncio.Lock), "must be an asyncio.Lock"

    # Different key → different lock instance
    lock_other = WorkspaceService._get_append_lock("t", "other.jsonl")
    assert lock_other is not lock_a

    # ---- (b) Concurrent serialization ------------------------------------
    # Stateful in-memory "DB" — closure captures content under serialization.
    state: dict[str, str | None] = {"content": None}

    async def fake_read_file(thread_id: str, file_path: str) -> dict:
        # Simulate a tiny await so other coroutines get scheduled (forces
        # interleaving without the lock — and the lock prevents that).
        await asyncio.sleep(0)
        if state["content"] is None:
            return {"error": "file_not_found", "file_path": file_path}
        return {
            "ok": True,
            "is_binary": False,
            "content": state["content"],
            "size_bytes": len(state["content"].encode("utf-8")),
            "mime_type": "application/octet-stream",
            "file_path": file_path,
        }

    async def fake_write_text_file(
        thread_id: str, file_path: str, content: str, source: str = "agent"
    ) -> dict:
        await asyncio.sleep(0)  # yield control — exposes lock if absent
        state["content"] = content
        return {
            "ok": True,
            "operation": "update",
            "size_bytes": len(content.encode("utf-8")),
            "file_path": file_path,
        }

    mock_client = _make_mock_client()
    with patch(
        "app.services.workspace_service.get_supabase_authed_client",
        return_value=mock_client,
    ):
        svc = WorkspaceService("tok")
        # Patch the two read/write methods on this instance only
        svc.read_file = fake_read_file  # type: ignore[assignment]
        svc.write_text_file = fake_write_text_file  # type: ignore[assignment]

        results = await asyncio.gather(*[
            svc.append_line("thread-1", "concurrent.jsonl", "x")
            for _ in range(5)
        ])

    # All 5 calls must have succeeded
    assert all(r.get("ok") is True for r in results), results
    # Final content must be exactly 5 newline-terminated 'x' lines
    assert state["content"] == "x\nx\nx\nx\nx\n"
