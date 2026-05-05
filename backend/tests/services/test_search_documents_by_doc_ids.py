"""Phase 22 / Plan 22-02 / REVIEW #10 — search_documents_by_doc_ids tool tests.

8 tests:
1.  test_registered_when_flag_on
2.  test_not_registered_when_flag_off
3.  test_handler_filters_results_by_doc_ids_python_side
4.  test_handler_rejects_empty_doc_ids
5.  test_handler_caps_doc_ids_at_50
6.  test_handler_caps_top_k_at_20
7.  test_protected_lines_unchanged  (CLAUDE.md invariant guard — sha256 pin)
8.  test_handler_does_not_pass_filter_doc_ids_kwarg  (REVIEW #10 anti-drift)
"""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# sha256 baseline of tool_service.py lines 1-1283, frozen before Phase 22
# (recorded at plan execution start — must match forever)
# ---------------------------------------------------------------------------
PROTECTED_HEAD_SHA256 = "cb63cf3e60d5f6380e2e41f63b1fe9122f58ab4648808b0f2114e452cd45ddb2"

_TOOL_SERVICE_PATH = Path(__file__).parent.parent.parent / "app" / "services" / "tool_service.py"


# ---------------------------------------------------------------------------
# Test 1 — registered when flag on
# ---------------------------------------------------------------------------

def test_registered_when_flag_on():
    """Flag True → search_documents_by_doc_ids present in registry."""
    from app.services import tool_registry as tr
    from app.services.tool_service import _register_playbook_tools, settings

    if not settings.tool_registry_enabled:
        with patch("app.services.tool_service.settings") as mock_s:
            mock_s.tool_registry_enabled = True
            _register_playbook_tools()

    assert "search_documents_by_doc_ids" in tr._REGISTRY, (
        "search_documents_by_doc_ids must be registered when tool_registry_enabled=True"
    )


# ---------------------------------------------------------------------------
# Test 2 — NOT registered when flag off
# ---------------------------------------------------------------------------

def test_not_registered_when_flag_off():
    """When TOOL_REGISTRY_ENABLED=False the register function is a no-op."""
    from app.services.tool_service import _register_playbook_tools
    from app.services import tool_registry as tr

    names_before = set(tr._REGISTRY.keys())

    with patch("app.services.tool_service.settings") as mock_settings:
        mock_settings.tool_registry_enabled = False
        _register_playbook_tools()

    names_after = set(tr._REGISTRY.keys())
    new_tools = names_after - names_before
    assert "search_documents_by_doc_ids" not in new_tools, (
        "_register_playbook_tools must be a no-op when tool_registry_enabled=False"
    )


# ---------------------------------------------------------------------------
# Test 3 — Python-side filter by doc_ids (REVIEW #10 anti-regression)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handler_filters_results_by_doc_ids_python_side():
    """REVIEW #10: retrieve is overfetched; Python-side filter keeps only matching doc_ids.

    Crucially: retrieve must be called with top_k=top_k*4 and NOT with a
    filter_doc_ids kwarg (which does not exist on HybridRetrievalService.retrieve).
    """
    from app.services.tool_service import _execute_search_documents_by_doc_ids

    canned_chunks = [
        {"document_id": "uuid-a", "content": "playbook A chunk 1"},
        {"document_id": "uuid-b", "content": "playbook B chunk 1"},
        {"document_id": "uuid-c", "content": "non-playbook chunk"},  # must be filtered out
        {"document_id": "uuid-a", "content": "playbook A chunk 2"},
    ]
    retrieve_mock = AsyncMock(return_value=canned_chunks)

    with patch("app.services.tool_service.HybridRetrievalService") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.retrieve = retrieve_mock
        mock_cls.return_value = mock_instance

        result = await _execute_search_documents_by_doc_ids(
            arguments={"query": "warranty", "doc_ids": ["uuid-a", "uuid-b"], "top_k": 4},
            user_id="u",
            context={},
            token="tok",
        )

    assert all(r["document_id"] in {"uuid-a", "uuid-b"} for r in result["results"])
    assert "uuid-c" not in [r["document_id"] for r in result["results"]]

    # REVIEW #10 anti-regression: retrieve called with overfetch top_k, NOT filter_doc_ids kwarg
    call = retrieve_mock.call_args
    assert call.kwargs.get("top_k") == 16, "must overfetch 4x (top_k * 4 = 4*4 = 16)"
    assert "filter_doc_ids" not in call.kwargs, (
        "REGRESSION: handler is passing filter_doc_ids kwarg, but "
        "HybridRetrievalService.retrieve() does NOT accept it. "
        "See review finding #10."
    )


# ---------------------------------------------------------------------------
# Test 4 — rejects empty doc_ids
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handler_rejects_empty_doc_ids():
    """Handler returns error dict (not raises) when doc_ids is empty."""
    from app.services.tool_service import _execute_search_documents_by_doc_ids

    result_empty_list = await _execute_search_documents_by_doc_ids(
        arguments={"query": "warranty", "doc_ids": []},
        user_id="u",
        context={},
    )
    assert result_empty_list["error"] == "invalid_doc_ids"
    assert result_empty_list["code"] == "INVALID_DOC_IDS"

    result_none = await _execute_search_documents_by_doc_ids(
        arguments={"query": "warranty", "doc_ids": None},
        user_id="u",
        context={},
    )
    assert result_none["error"] == "invalid_doc_ids"

    result_missing = await _execute_search_documents_by_doc_ids(
        arguments={"query": "warranty"},
        user_id="u",
        context={},
    )
    assert result_missing["error"] == "invalid_doc_ids"


# ---------------------------------------------------------------------------
# Test 5 — caps doc_ids at 50
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handler_caps_doc_ids_at_50():
    """Handler rejects doc_ids list longer than 50."""
    from app.services.tool_service import _execute_search_documents_by_doc_ids

    too_many_ids = [f"uuid-{i}" for i in range(51)]
    result = await _execute_search_documents_by_doc_ids(
        arguments={"query": "warranty", "doc_ids": too_many_ids},
        user_id="u",
        context={},
    )
    assert result["error"] == "invalid_doc_ids"
    assert result["code"] == "INVALID_DOC_IDS"
    assert "50" in result["detail"]


# ---------------------------------------------------------------------------
# Test 6 — caps top_k at 20
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handler_caps_top_k_at_20():
    """top_k is capped at 20; retrieve gets top_k*4 = 80 max overfetch."""
    from app.services.tool_service import _execute_search_documents_by_doc_ids

    retrieve_mock = AsyncMock(return_value=[])

    with patch("app.services.tool_service.HybridRetrievalService") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.retrieve = retrieve_mock
        mock_cls.return_value = mock_instance

        await _execute_search_documents_by_doc_ids(
            arguments={"query": "test", "doc_ids": ["uuid-a"], "top_k": 99},
            user_id="u",
            context={},
        )

    call = retrieve_mock.call_args
    # top_k should be min(99, 20) = 20; overfetch = 20 * 4 = 80
    assert call.kwargs.get("top_k") == 80, f"expected 80, got {call.kwargs.get('top_k')}"


# ---------------------------------------------------------------------------
# Test 7 — sha256 invariant guard (CLAUDE.md)
# ---------------------------------------------------------------------------

def test_protected_lines_unchanged():
    """CLAUDE.md: head -n 1283 tool_service.py sha256 must match pre-Phase-22 baseline.

    The sha256 is computed to match `head -n 1283 file | shasum -a 256`:
    - split on newlines, take first 1283 lines, rejoin with newlines + trailing newline.
    """
    lines = _TOOL_SERVICE_PATH.read_bytes().split(b"\n")
    # Reconstruct first 1283 lines + trailing newline (matching `head -n 1283 | shasum`)
    first_1283 = b"\n".join(lines[:1283]) + b"\n"
    digest = hashlib.sha256(first_1283).hexdigest()
    assert digest == PROTECTED_HEAD_SHA256, (
        f"INVARIANT VIOLATION: tool_service.py lines 1-1283 have been modified!\n"
        f"Expected sha256: {PROTECTED_HEAD_SHA256}\n"
        f"Actual sha256:   {digest}\n"
        f"Fix: revert any edits to lines 1-1283 of tool_service.py."
    )


# ---------------------------------------------------------------------------
# Test 8 — REVIEW #10 anti-drift hard guard
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handler_does_not_pass_filter_doc_ids_kwarg():
    """REVIEW #10 hard guard: retrieve() does not accept a doc-id filter kwarg;
    verify the handler ALWAYS uses Python-side filtering.

    This test prevents future drift where someone re-introduces the nonexistent
    kwarg. If it's ever added to HybridRetrievalService (requiring a migration),
    this test documents that this guard test would then need updating too.
    """
    from app.services.tool_service import _execute_search_documents_by_doc_ids

    retrieve_mock = AsyncMock(return_value=[])

    with patch("app.services.tool_service.HybridRetrievalService") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.retrieve = retrieve_mock
        mock_cls.return_value = mock_instance

        await _execute_search_documents_by_doc_ids(
            arguments={"query": "x", "doc_ids": ["a"], "top_k": 8},
            user_id="u",
            context={},
        )

    for call in retrieve_mock.call_args_list:
        assert "filter_doc_ids" not in (call.kwargs or {}), (
            "REGRESSION (REVIEW #10): handler passed filter_doc_ids to retrieve(), "
            "but HybridRetrievalService.retrieve() does NOT accept that kwarg."
        )
