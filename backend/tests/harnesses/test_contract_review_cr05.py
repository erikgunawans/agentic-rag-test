"""Phase 22 / plan 22-08 — Unit tests for CR-05 clause extraction executor.

9 tests covering:
1.  test_small_contract_returns_clause_count — small contract, 1 chunk, returns clause_count
2.  test_large_contract_creates_multiple_chunks — >180k chars forces >=2 chunks
3.  test_dedupe_collapses_near_identical_clauses — same clause text in N and N+1 deduplicated
4.  test_unknown_categories_coerced_to_other — LLM-returned cats not in CLAUSE_CATEGORIES → "Other"
5.  test_empty_input_returns_error_dict — empty input → error dict (never raises)
6.  test_single_chunk_llm_exception_phase_continues — one chunk LLM error; phase continues if others succeed
7.  test_boilerplate_header_different_body_not_deduped — same heading, different body → NOT deduped (ISSUE-10)
8.  test_egress_filter_skips_chunk_when_tripped — REVIEW #4 egress wrap: tripped chunk skipped, phase continues
9.  test_executor_accepts_review_4_kwargs — REVIEW #4 signature: executor accepts registry, system_settings, etc.

RED phase: all tests that require _phase5_extract_clauses will fail until Task 2 GREEN.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_llm_response(clauses: list[dict], chunk_index: int = 0, total_chunks: int = 1) -> dict:
    """Build a mock OpenRouterService.complete_with_tools return value."""
    return {
        "content": json.dumps({
            "clauses": clauses,
            "chunk_index": chunk_index,
            "total_chunks": total_chunks,
        })
    }


def _make_clause(
    category: str = "Liability",
    heading: str = "Liability Cap",
    text: str = "The maximum liability shall be limited to $10,000.",
    position: int = 0,
) -> dict:
    return {"category": category, "heading": heading, "text": text, "position": position}


# ---------------------------------------------------------------------------
# Test 1: small contract → 1 chunk → returns clause_count and content
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_small_contract_returns_clause_count():
    """Small contract (<180k chars) → single chunk → clause_count matches extracted clauses."""
    from app.harnesses.contract_review import _phase5_extract_clauses

    contract_text = "This is a short contract.\n\nLiability: limited to $10k.\n"
    clauses_response = [_make_clause("Liability", "Liability Cap", "Liability limited to $10k.", 0)]

    with patch("app.harnesses.contract_review.OpenRouterService") as svc_cls:
        svc_inst = svc_cls.return_value
        svc_inst.complete_with_tools = AsyncMock(
            return_value=_make_llm_response(clauses_response, chunk_index=0, total_chunks=1)
        )
        with patch("app.harnesses.contract_review.WorkspaceService") as ws_cls:
            ws_inst = ws_cls.return_value
            ws_inst.write_text_file = AsyncMock(return_value={"ok": True})

            result = await _phase5_extract_clauses(
                inputs={"contract-text.md": contract_text},
                token="t", thread_id="thr", harness_run_id="r",
            )

    assert "error" not in result, f"Expected success, got: {result}"
    assert result.get("clause_count") == 1
    assert result.get("chunk_count") == 1
    assert result.get("chunks_failed") == 0
    assert "content" in result
    assert "Extracted Clauses" in result["content"]


# ---------------------------------------------------------------------------
# Test 2: large contract → multiple chunks (>=2)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_large_contract_creates_multiple_chunks():
    """Contract >180k chars must be split into >=2 chunks (CR05_CHUNK_CHARS=180_000)."""
    from app.harnesses.contract_review import _phase5_extract_clauses, CR05_CHUNK_CHARS

    # 250k chars → at least 2 chunks
    contract_text = "A" * 250_000

    call_count = {"n": 0}

    async def mock_complete(**kwargs):
        idx = call_count["n"]
        call_count["n"] += 1
        return _make_llm_response(
            [_make_clause("Payment", f"Payment {idx}", f"Pay clause {idx}.", idx * 1000)],
            chunk_index=idx,
            total_chunks=2,
        )

    with patch("app.harnesses.contract_review.OpenRouterService") as svc_cls:
        svc_inst = svc_cls.return_value
        svc_inst.complete_with_tools = mock_complete
        with patch("app.harnesses.contract_review.WorkspaceService") as ws_cls:
            ws_inst = ws_cls.return_value
            ws_inst.write_text_file = AsyncMock(return_value={"ok": True})

            result = await _phase5_extract_clauses(
                inputs={"contract-text.md": contract_text},
                token="t", thread_id="thr", harness_run_id="r",
            )

    assert "error" not in result, f"Expected success, got: {result}"
    assert result.get("chunk_count") >= 2, "250k char contract must produce >=2 chunks"
    assert result.get("clause_count") >= 1, "Must have at least 1 clause extracted"


# ---------------------------------------------------------------------------
# Test 3: dedupe collapses near-identical clauses (same category, same text)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dedupe_collapses_near_identical_clauses():
    """Same clause appearing in chunks N and N+1 is deduped (CR05_DEDUPE_RATIO=0.85).
    Clause must appear only once in the result.
    """
    from app.harnesses.contract_review import _phase5_extract_clauses

    # Force 2 chunks
    contract_text = "A" * 250_000
    identical_clause = _make_clause(
        "Confidentiality",
        "NDA clause",
        "The parties agree to keep all information confidential for 5 years.",
        0,
    )

    call_count = {"n": 0}

    async def mock_complete(**kwargs):
        call_count["n"] += 1
        # Both chunks return the IDENTICAL clause
        return _make_llm_response(
            [identical_clause], chunk_index=call_count["n"] - 1, total_chunks=2
        )

    with patch("app.harnesses.contract_review.OpenRouterService") as svc_cls:
        svc_inst = svc_cls.return_value
        svc_inst.complete_with_tools = mock_complete
        with patch("app.harnesses.contract_review.WorkspaceService") as ws_cls:
            ws_inst = ws_cls.return_value
            ws_inst.write_text_file = AsyncMock(return_value={"ok": True})

            result = await _phase5_extract_clauses(
                inputs={"contract-text.md": contract_text},
                token="t", thread_id="thr", harness_run_id="r",
            )

    assert "error" not in result, f"Expected success, got: {result}"
    # Pre-dedupe we'd have 2 identical clauses; post-dedupe should be 1
    assert result.get("clause_count") == 1, (
        f"Expected 1 deduped clause, got {result.get('clause_count')}. "
        "Near-identical clauses from overlapping chunks must be collapsed."
    )


# ---------------------------------------------------------------------------
# Test 4: unknown categories coerced to "Other"
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unknown_categories_coerced_to_other():
    """If LLM returns a category not in CLAUSE_CATEGORIES, it must be coerced to 'Other'."""
    from app.harnesses.contract_review import _phase5_extract_clauses, CLAUSE_CATEGORIES

    contract_text = "Short contract for category test."
    # LLM returns unknown category
    bad_clause = _make_clause("SomeFictionalCategory", "Weird heading", "weird clause text", 0)

    with patch("app.harnesses.contract_review.OpenRouterService") as svc_cls:
        svc_inst = svc_cls.return_value
        svc_inst.complete_with_tools = AsyncMock(
            return_value=_make_llm_response([bad_clause])
        )
        with patch("app.harnesses.contract_review.WorkspaceService") as ws_cls:
            ws_inst = ws_cls.return_value
            ws_inst.write_text_file = AsyncMock(return_value={"ok": True})

            result = await _phase5_extract_clauses(
                inputs={"contract-text.md": contract_text},
                token="t", thread_id="thr", harness_run_id="r",
            )

    assert "error" not in result, f"Expected success, got: {result}"
    # The category must be coerced
    assert result.get("clause_count") == 1
    # Parse the JSON from content to verify category
    content = result["content"]
    # Extract JSON from markdown code block
    import re
    json_match = re.search(r"```json\n(.*?)\n```", content, re.DOTALL)
    assert json_match, "content must contain a JSON code block"
    clauses = json.loads(json_match.group(1))
    assert len(clauses) == 1
    assert clauses[0]["category"] == "Other", (
        f"Expected 'Other' but got '{clauses[0]['category']}'. "
        "Unknown categories must be coerced to 'Other'."
    )


# ---------------------------------------------------------------------------
# Test 5: empty input → error dict, never raises
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_empty_input_returns_error_dict():
    """Empty contract text → structured error dict, never raises."""
    from app.harnesses.contract_review import _phase5_extract_clauses

    # Test both empty string and whitespace-only
    for contract_text in ["", "   \n\t  "]:
        result = await _phase5_extract_clauses(
            inputs={"contract-text.md": contract_text},
            token="t", thread_id="thr", harness_run_id="r",
        )
        assert isinstance(result, dict), "Must return a dict, not raise"
        assert result.get("error") == "contract_text_missing", (
            f"Expected error='contract_text_missing' for input={contract_text!r}, got: {result}"
        )
        assert "code" in result

    # Missing key entirely
    result = await _phase5_extract_clauses(
        inputs={},
        token="t", thread_id="thr", harness_run_id="r",
    )
    assert isinstance(result, dict)
    assert result.get("error") == "contract_text_missing"


# ---------------------------------------------------------------------------
# Test 6: single chunk LLM exception caught; phase continues if other chunks succeed
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_single_chunk_llm_exception_phase_continues():
    """If one chunk's LLM call raises, that chunk is counted as failed but the
    phase continues with remaining chunks. Result includes 'content' from good chunks.
    """
    from app.harnesses.contract_review import _phase5_extract_clauses

    # 250k chars → 2 chunks
    contract_text = "B" * 250_000
    call_count = {"n": 0}

    async def mock_complete(**kwargs):
        idx = call_count["n"]
        call_count["n"] += 1
        if idx == 0:
            raise RuntimeError("LLM API timeout on chunk 0")
        # Second chunk succeeds
        return _make_llm_response(
            [_make_clause("Insurance", "Insurance coverage", "Insurance must be maintained.", 5000)],
            chunk_index=1,
            total_chunks=2,
        )

    with patch("app.harnesses.contract_review.OpenRouterService") as svc_cls:
        svc_inst = svc_cls.return_value
        svc_inst.complete_with_tools = mock_complete
        with patch("app.harnesses.contract_review.WorkspaceService") as ws_cls:
            ws_inst = ws_cls.return_value
            ws_inst.write_text_file = AsyncMock(return_value={"ok": True})

            result = await _phase5_extract_clauses(
                inputs={"contract-text.md": contract_text},
                token="t", thread_id="thr", harness_run_id="r",
            )

    assert "error" not in result, (
        f"Phase must not bail entirely when only one chunk fails. Got: {result}"
    )
    assert result.get("chunks_failed") == 1, "One failed chunk must be counted"
    assert result.get("clause_count") == 1, "Clause from second chunk must appear"
    assert "content" in result


# ---------------------------------------------------------------------------
# Test 7: ISSUE-10 — boilerplate header, different bodies → NOT deduped
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_boilerplate_header_different_body_not_deduped():
    """Two clauses with same heading but different dollar amounts / numbers
    must NOT be deduped — they are distinct obligations (ISSUE-10).
    """
    from app.harnesses.contract_review import _phase5_extract_clauses

    # 250k chars → 2 chunks
    contract_text = "C" * 250_000

    clause_a = _make_clause("Payment", "Payment Terms", "Buyer shall pay $10,000 within 30 days.", 0)
    clause_b = _make_clause("Payment", "Payment Terms", "Buyer shall pay $50,000 within 60 days.", 1000)

    call_count = {"n": 0}

    async def mock_complete(**kwargs):
        idx = call_count["n"]
        call_count["n"] += 1
        if idx == 0:
            return _make_llm_response([clause_a], chunk_index=0, total_chunks=2)
        return _make_llm_response([clause_b], chunk_index=1, total_chunks=2)

    with patch("app.harnesses.contract_review.OpenRouterService") as svc_cls:
        svc_inst = svc_cls.return_value
        svc_inst.complete_with_tools = mock_complete
        with patch("app.harnesses.contract_review.WorkspaceService") as ws_cls:
            ws_inst = ws_cls.return_value
            ws_inst.write_text_file = AsyncMock(return_value={"ok": True})

            result = await _phase5_extract_clauses(
                inputs={"contract-text.md": contract_text},
                token="t", thread_id="thr", harness_run_id="r",
            )

    assert "error" not in result, f"Expected success, got: {result}"
    assert result.get("clause_count") == 2, (
        f"Two distinct clauses (different dollar amounts) must NOT be deduped. "
        f"Got clause_count={result.get('clause_count')}. "
        "ISSUE-10: dedupe must use text similarity, not just heading equality."
    )


# ---------------------------------------------------------------------------
# Test 8 (REVIEW #4 — egress wrap): egress_filter trips on chunk → chunk skipped,
# phase continues with remaining chunks
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_egress_filter_skips_chunk_when_tripped():
    """REVIEW #4: when registry is provided AND egress_filter trips for a chunk,
    that chunk is counted as failed (egress-blocked) but the phase continues.
    The result must include chunks_egress_blocked >= 1 and 'content' from good chunks.
    """
    from app.harnesses.contract_review import _phase5_extract_clauses

    # Force 2 chunks
    big_text = "x" * 250_000
    call_count = {"n": 0}

    def fake_egress_filter(payload, registry, _):
        call_count["n"] += 1
        er = MagicMock()
        er.tripped = call_count["n"] == 1  # trip FIRST chunk only
        return er

    mock_registry = MagicMock()

    with patch("app.harnesses.contract_review.egress_filter", side_effect=fake_egress_filter):
        with patch("app.harnesses.contract_review.OpenRouterService") as svc_cls:
            svc_inst = svc_cls.return_value
            svc_inst.complete_with_tools = AsyncMock(
                return_value=_make_llm_response(
                    [_make_clause("Liability", "Liability Cap", "Limited to $5k.", 0)],
                    chunk_index=1,
                    total_chunks=2,
                )
            )
            with patch("app.harnesses.contract_review.WorkspaceService") as ws_cls:
                ws_inst = ws_cls.return_value
                ws_inst.write_text_file = AsyncMock(return_value={"ok": True})

                result = await _phase5_extract_clauses(
                    inputs={"contract-text.md": big_text},
                    token="t", thread_id="thr", harness_run_id="r",
                    registry=mock_registry,
                    system_settings={},
                    user_id="u",
                    user_email="e@x",
                )

    assert result.get("chunks_egress_blocked") == 1, (
        f"Expected chunks_egress_blocked=1, got: {result.get('chunks_egress_blocked')}. "
        "REVIEW #4: egress-blocked chunk must be counted in result."
    )
    assert result.get("chunks_failed") >= 1, (
        f"chunks_failed must be >= 1 when egress blocked a chunk. Got: {result.get('chunks_failed')}"
    )
    # Phase did not bail entirely — second chunk succeeded and produced content
    assert "content" in result, (
        "Phase must produce content from the non-blocked chunk. Got only error: {result}"
    )


# ---------------------------------------------------------------------------
# Test 9 (REVIEW #4 — signature test): executor accepts new kwargs without TypeError
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_executor_accepts_review_4_kwargs():
    """REVIEW #4: executor signature MUST accept registry, system_settings, user_id, user_email.
    Calling with these kwargs must not raise TypeError. Empty contract → error path is fine;
    the signature is what we are verifying here.
    """
    from app.harnesses.contract_review import _phase5_extract_clauses

    # Must not raise TypeError — just go to the empty-contract path
    result = await _phase5_extract_clauses(
        inputs={"contract-text.md": ""},
        token="t",
        thread_id="thr",
        harness_run_id="r",
        registry=None,
        system_settings=None,
        user_id=None,
        user_email=None,
    )
    # Empty contract → error dict (never raises)
    assert isinstance(result, dict), "Must return a dict, never raise"
    assert result.get("error") == "contract_text_missing", (
        f"Empty contract must return error='contract_text_missing'. Got: {result}"
    )
