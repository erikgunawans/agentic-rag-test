"""Phase 22 / Plan 22-02 / REVIEW #1 — list_playbook_documents tool tests.

7 tests covering registration gating, tag filter, shape, fallbacks, limits.

1.  test_list_playbook_documents_registered_when_flag_on
2.  test_list_playbook_documents_not_registered_when_flag_off
3.  test_handler_filters_by_playbook_tag
4.  test_handler_returns_doc_id_title_summary_shape
5.  test_handler_falls_back_to_empty_summary
6.  test_handler_caps_at_limit
7.  test_handler_returns_empty_when_no_playbook_docs
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_supabase_mock(rows: list) -> MagicMock:
    """Chain mock for client.table(...).select(...).eq(...).execute()."""
    client = MagicMock()
    execute_result = MagicMock()
    execute_result.data = rows
    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.execute.return_value = execute_result
    client.table.return_value = chain
    return client


def _make_doc(doc_id: str, filename: str, tags: list, summary: str | None = None,
              first_chunk: str | None = None) -> dict:
    meta: dict = {"tags": tags}
    if summary is not None:
        meta["summary"] = summary
    if first_chunk is not None:
        meta["first_chunk_text"] = first_chunk
    return {"id": doc_id, "filename": filename, "metadata": meta}


# ---------------------------------------------------------------------------
# Test 1 — registered when flag on
# ---------------------------------------------------------------------------

def test_list_playbook_documents_registered_when_flag_on():
    """Flag True → tool present in registry after module load."""
    from app.services import tool_registry as tr
    from app.services.tool_service import _register_playbook_tools, settings

    if not settings.tool_registry_enabled:
        # Simulate flag=True: call register directly with patched settings
        with patch("app.services.tool_service.settings") as mock_s:
            mock_s.tool_registry_enabled = True
            _register_playbook_tools()
    # After calling with flag=True, tool must be in _REGISTRY
    assert "list_playbook_documents" in tr._REGISTRY, (
        "list_playbook_documents must be registered when tool_registry_enabled=True"
    )


# ---------------------------------------------------------------------------
# Test 2 — NOT registered when flag off
# ---------------------------------------------------------------------------

def test_list_playbook_documents_not_registered_when_flag_off():
    """When TOOL_REGISTRY_ENABLED=False the register function is a no-op."""
    from app.services.tool_service import _register_playbook_tools
    from app.services import tool_registry as tr

    names_before = set(tr._REGISTRY.keys())

    with patch("app.services.tool_service.settings") as mock_settings:
        mock_settings.tool_registry_enabled = False
        _register_playbook_tools()

    names_after = set(tr._REGISTRY.keys())
    new_tools = names_after - names_before
    assert "list_playbook_documents" not in new_tools, (
        "_register_playbook_tools must be a no-op when tool_registry_enabled=False"
    )


# ---------------------------------------------------------------------------
# Test 3 — filters by playbook tag
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handler_filters_by_playbook_tag():
    """Mock supabase returns 3 docs with mixed tags; handler returns only 'playbook'-tagged."""
    from app.services.tool_service import _execute_list_playbook_documents

    canned_rows = [
        _make_doc("uuid-a", "Master Indemnity Playbook.pdf",
                  ["playbook", "indemnity"], summary="Indemnity rules."),
        _make_doc("uuid-b", "Random Memo.docx",
                  ["memo"], summary="Internal memo."),
        _make_doc("uuid-c", "Liability Playbook.pdf",
                  ["playbook"], first_chunk="Liability principles..."),
    ]
    client = _make_supabase_mock(canned_rows)

    with patch("app.services.tool_service.get_supabase_authed_client", return_value=client):
        result = await _execute_list_playbook_documents(
            arguments={}, user_id="u", context={}, token="tok"
        )

    ids = {r["doc_id"] for r in result["results"]}
    assert ids == {"uuid-a", "uuid-c"}, "must include only playbook-tagged docs"
    assert "uuid-b" not in ids, "memo-tagged doc must be excluded"


# ---------------------------------------------------------------------------
# Test 4 — result shape: doc_id, title, summary (<=300 chars)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handler_returns_doc_id_title_summary_shape():
    """Every result has doc_id, title, summary; summary is <= 300 chars."""
    from app.services.tool_service import _execute_list_playbook_documents

    long_summary = "X" * 500  # longer than cap
    canned_rows = [
        _make_doc("uuid-a", "Contract Playbook.pdf", ["playbook"], summary=long_summary),
    ]
    client = _make_supabase_mock(canned_rows)

    with patch("app.services.tool_service.get_supabase_authed_client", return_value=client):
        result = await _execute_list_playbook_documents(
            arguments={}, user_id="u", context={}, token="tok"
        )

    assert len(result["results"]) == 1
    item = result["results"][0]
    assert "doc_id" in item
    assert "title" in item
    assert "summary" in item
    assert item["doc_id"] == "uuid-a"
    assert item["title"] == "Contract Playbook.pdf"
    assert len(item["summary"]) <= 300, "summary must be capped at 300 chars"


# ---------------------------------------------------------------------------
# Test 5 — falls back to empty string when both summary fields absent
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handler_falls_back_to_empty_summary():
    """When metadata.summary and metadata.first_chunk_text both missing, summary is '' not error."""
    from app.services.tool_service import _execute_list_playbook_documents

    canned_rows = [
        {"id": "uuid-x", "filename": "Mystery Playbook.pdf",
         "metadata": {"tags": ["playbook"]}},  # no summary, no first_chunk_text
    ]
    client = _make_supabase_mock(canned_rows)

    with patch("app.services.tool_service.get_supabase_authed_client", return_value=client):
        result = await _execute_list_playbook_documents(
            arguments={}, user_id="u", context={}, token="tok"
        )

    assert len(result["results"]) == 1
    assert result["results"][0]["summary"] == ""


# ---------------------------------------------------------------------------
# Test 6 — caps results at limit (default 50, max 100)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handler_caps_at_limit():
    """When many docs match, results capped at limit (default 50, max 100)."""
    from app.services.tool_service import _execute_list_playbook_documents

    # 200 playbook docs
    canned_rows = [
        _make_doc(f"uuid-{i}", f"Playbook {i}.pdf", ["playbook"], summary=f"Summary {i}")
        for i in range(200)
    ]
    client = _make_supabase_mock(canned_rows)

    with patch("app.services.tool_service.get_supabase_authed_client", return_value=client):
        # Default limit (50)
        result = await _execute_list_playbook_documents(
            arguments={}, user_id="u", context={}, token="tok"
        )
        assert len(result["results"]) == 50, "default limit is 50"

        # Explicit limit=10
        result2 = await _execute_list_playbook_documents(
            arguments={"limit": 10}, user_id="u", context={}, token="tok"
        )
        assert len(result2["results"]) == 10, "explicit limit=10 must cap at 10"

        # Limit exceeding max (100) is capped at 100
        result3 = await _execute_list_playbook_documents(
            arguments={"limit": 999}, user_id="u", context={}, token="tok"
        )
        assert len(result3["results"]) == 100, "limit capped at max 100"


# ---------------------------------------------------------------------------
# Test 7 — returns empty when no playbook docs (D-22-07 fallback)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handler_returns_empty_when_no_playbook_docs():
    """When no docs tagged 'playbook', returns empty results array (not error)."""
    from app.services.tool_service import _execute_list_playbook_documents

    canned_rows = [
        _make_doc("uuid-a", "Memo.docx", ["memo"], summary="A memo."),
    ]
    client = _make_supabase_mock(canned_rows)

    with patch("app.services.tool_service.get_supabase_authed_client", return_value=client):
        result = await _execute_list_playbook_documents(
            arguments={}, user_id="u", context={}, token="tok"
        )

    assert result == {"results": []}, "must return empty results, not error"
