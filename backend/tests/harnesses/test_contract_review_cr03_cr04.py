"""Phase 22 / Plan 22-07 — Unit tests for CR-03 (gather-context) and CR-04 (load-playbook).

8 test cases:
 1. CR-03 prompt non-empty and contains "Which party are you"
 2. CR-03 prompt does NOT mention parsing the response (D-22-10)
 3. CR-04 prompt contains "list_playbook_documents", max 10 rounds, all 13 clause categories
 4. CR-04 prompt instructs context_quality='unfounded' for empty playbook (D-22-07)
 5. CR-04 prompt instructs authority ordering (D-22-08: user-workspace > regulatory > 3rd-party)
 6. CR-04 tools list uses real tools only — REVIEW #1 fix (no analyze_document)
 7. PlaybookContext schema accepts empty-playbook case
 8. REVIEW #1 anti-regression: contract_review.py contains no "analyze_document" string

Run:
    cd backend && source venv/bin/activate && \\
        pytest tests/harnesses/test_contract_review_cr03_cr04.py -v --tb=short
"""
from __future__ import annotations

import importlib
import sys
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures / helpers (mirrors test_contract_review_skeleton.py pattern)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_registry():
    """Clear the harness registry before and after each test."""
    from app.services import harness_registry
    harness_registry._reset_for_tests()
    yield
    harness_registry._reset_for_tests()


def _reload_contract_review(
    harness_enabled: bool = True,
    contract_review_enabled: bool = True,
    tool_registry_enabled: bool = True,
):
    """Reload app.harnesses.contract_review under a patched settings object."""
    mock_settings = MagicMock()
    mock_settings.harness_enabled = harness_enabled
    mock_settings.contract_review_enabled = contract_review_enabled
    mock_settings.tool_registry_enabled = tool_registry_enabled

    mod_name = "app.harnesses.contract_review"
    sys.modules.pop(mod_name, None)

    with patch("app.config.get_settings", return_value=mock_settings):
        mod = importlib.import_module(mod_name)

    return mod


# ---------------------------------------------------------------------------
# Test 1: CR-03 prompt asks "Which party are you" (D-22-09)
# ---------------------------------------------------------------------------

def test_cr03_prompt_contains_which_party_question():
    """Test 1: CR-03 system_prompt_template is non-empty and contains 'Which party are you'."""
    mod = _reload_contract_review()
    cr03 = mod.CONTRACT_REVIEW.phases[2]
    assert cr03.name == "gather-context", f"Expected phases[2] = gather-context, got {cr03.name}"
    assert cr03.system_prompt_template != "STUB", "CR-03 system_prompt_template must not be STUB"
    assert len(cr03.system_prompt_template) > 50, "CR-03 prompt must be non-trivial"
    assert "Which party are you" in cr03.system_prompt_template, (
        "CR-03 prompt must ask 'Which party are you' per D-22-09 single combined question"
    )


# ---------------------------------------------------------------------------
# Test 2: CR-03 does NOT mention parsing the response (D-22-10 raw persistence)
# ---------------------------------------------------------------------------

def test_cr03_prompt_does_not_mention_parsing():
    """Test 2: CR-03 prompt must not instruct the user's response to be parsed (D-22-10)."""
    mod = _reload_contract_review()
    cr03 = mod.CONTRACT_REVIEW.phases[2]
    prompt = cr03.system_prompt_template.lower()
    # These keywords signal a parse pass — D-22-10 explicitly forbids a parse step
    for forbidden in ("extract field", "parse the response", "parse user", "structured extract"):
        assert forbidden not in prompt, (
            f"CR-03 prompt mentions parsing ('{forbidden}') — violates D-22-10 (raw text persistence). "
            "Remove the parsing instruction; downstream LLMs interpret the raw reply."
        )


# ---------------------------------------------------------------------------
# Test 3: CR-04 prompt has list_playbook_documents, max 10 rounds, all 13 categories
# ---------------------------------------------------------------------------

CLAUSE_CATEGORIES = [
    "Liability", "Indemnification", "IP", "Data Protection", "Confidentiality",
    "Warranties", "Term/Termination", "Governing Law", "Insurance",
    "Assignment", "Force Majeure", "Payment", "Other",
]


def test_cr04_prompt_structure():
    """Test 3: CR-04 prompt lists all 13 clause categories, mentions list_playbook_documents, max 10 rounds."""
    mod = _reload_contract_review()
    cr04 = mod.CONTRACT_REVIEW.phases[3]
    assert cr04.name == "load-playbook", f"Expected phases[3] = load-playbook, got {cr04.name}"
    assert cr04.system_prompt_template != "STUB", "CR-04 system_prompt_template must not be STUB"

    prompt = cr04.system_prompt_template
    assert "list_playbook_documents" in prompt, "CR-04 prompt must reference list_playbook_documents"
    assert "10" in prompt, "CR-04 prompt must reference max 10 rounds"

    for cat in CLAUSE_CATEGORIES:
        assert cat in prompt, (
            f"CR-04 prompt must mention all 13 clause categories; missing: '{cat}'"
        )


# ---------------------------------------------------------------------------
# Test 4: CR-04 prompt instructs context_quality='unfounded' for empty playbook (D-22-07)
# ---------------------------------------------------------------------------

def test_cr04_prompt_empty_playbook_fallback():
    """Test 4: CR-04 prompt instructs context_quality='unfounded' when zero docs returned (D-22-07)."""
    mod = _reload_contract_review()
    cr04 = mod.CONTRACT_REVIEW.phases[3]
    prompt = cr04.system_prompt_template
    assert "unfounded" in prompt, (
        "CR-04 prompt must instruct agent to set context_quality='unfounded' "
        "when list_playbook_documents returns zero results (D-22-07)"
    )


# ---------------------------------------------------------------------------
# Test 5: CR-04 prompt has authority hierarchy (D-22-08)
# ---------------------------------------------------------------------------

def test_cr04_prompt_authority_hierarchy():
    """Test 5: CR-04 prompt mentions authority hierarchy (D-22-08: user-workspace > regulatory > 3rd-party)."""
    mod = _reload_contract_review()
    cr04 = mod.CONTRACT_REVIEW.phases[3]
    prompt = cr04.system_prompt_template
    assert "AUTHORITY HIERARCHY" in prompt or "authority" in prompt.lower(), (
        "CR-04 prompt must describe the D-22-08 authority ordering "
        "(user-workspace > regulatory_intel > 3rd-party)"
    )
    # At least two tiers must be explicitly named
    assert "regulatory" in prompt.lower() or "regulatory_intel" in prompt, (
        "CR-04 prompt must name regulatory_intel as a tier in the authority ordering"
    )


# ---------------------------------------------------------------------------
# Test 6: CR-04 tools list uses real tools only — REVIEW #1 fix
# ---------------------------------------------------------------------------

def test_cr04_tools_list_uses_real_tools_only():
    """Test 6 (REVIEW #1 fix): CR-04 tools list must be exactly the three real tools.

    analyze_document does NOT exist in this codebase
    (grep -c "analyze_document" backend/app/services/tool_service.py returns 0).
    Plan 22-07 switched to list_playbook_documents (plan 22-02) as the playbook
    discovery surface.
    """
    mod = _reload_contract_review()
    tools = mod.CONTRACT_REVIEW.phases[3].tools
    assert tools == [
        "list_playbook_documents",
        "search_documents",
        "search_documents_by_doc_ids",
    ], (
        f"REVIEW #1: CR-04 tools must be the three real tools; got {tools}. "
        "Never reference analyze_document — it does not exist in tool_service.py."
    )
    assert "analyze_document" not in tools, (
        "analyze_document does not exist in this codebase — remove it from CR-04 tools"
    )


# ---------------------------------------------------------------------------
# Test 7: PlaybookContext schema accepts empty-playbook case
# ---------------------------------------------------------------------------

def test_playbook_context_empty_playbook():
    """Test 7: PlaybookContext schema can represent the D-22-07 empty-playbook case."""
    mod = _reload_contract_review()
    PlaybookContext = mod.PlaybookContext

    # Empty-playbook case: zero docs, all categories mapping to [], unfounded quality
    ctx = PlaybookContext(
        playbook_docs=[],
        clause_category_to_playbook={cat: [] for cat in CLAUSE_CATEGORIES},
        context_quality="unfounded",
        notes="No playbook materials found — risk grades reflect generic legal standards.",
    )
    assert ctx.context_quality == "unfounded"
    assert ctx.playbook_docs == []
    assert len(ctx.clause_category_to_playbook) == 13

    # Founded case: with some docs
    PlaybookDoc = mod.PlaybookDoc
    ctx_founded = PlaybookContext(
        playbook_docs=[
            PlaybookDoc(id="doc-001", title="Standard MSA Playbook", summary="Our standard MSA positions."),
        ],
        clause_category_to_playbook={"Liability": ["doc-001"], "Other": []},
        context_quality="founded",
        notes="Found 1 playbook document.",
    )
    assert ctx_founded.context_quality == "founded"
    assert len(ctx_founded.playbook_docs) == 1


# ---------------------------------------------------------------------------
# Test 8: REVIEW #1 anti-regression — no "analyze_document" anywhere in contract_review.py
# ---------------------------------------------------------------------------

def test_no_analyze_document_references_anywhere():
    """Test 8 (REVIEW #1 hard guard): analyze_document must NOT appear anywhere in contract_review.py.

    `analyze_document` does NOT exist as a tool in this codebase
    (verified: grep -c "analyze_document" backend/app/services/tool_service.py returns 0).
    Plan 22-07 uses list_playbook_documents (plan 22-02) and search_documents_by_doc_ids instead.
    Future regressions caught here.

    See review finding #1 in 22-REVIEWS.md.
    """
    import pathlib
    # Use the path relative to project root (works from backend/ or project root)
    candidates = [
        pathlib.Path("backend/app/harnesses/contract_review.py"),
        pathlib.Path("app/harnesses/contract_review.py"),
    ]
    text = None
    for p in candidates:
        if p.exists():
            text = p.read_text()
            break
    if text is None:
        # Absolute path fallback for CI / worktree contexts
        import os
        cwd = pathlib.Path(os.getcwd())
        for rel in candidates:
            abs_p = cwd / rel
            if abs_p.exists():
                text = abs_p.read_text()
                break
            # Try one level up
            abs_p2 = cwd.parent / rel
            if abs_p2.exists():
                text = abs_p2.read_text()
                break

    assert text is not None, (
        "Could not locate backend/app/harnesses/contract_review.py — "
        "run pytest from the backend/ or project root directory."
    )
    assert "analyze_document" not in text, (
        "REGRESSION: contract_review.py references the nonexistent `analyze_document` tool. "
        "Use `list_playbook_documents` (plan 22-02) and `search_documents_by_doc_ids` instead. "
        "See review finding #1 in 22-REVIEWS.md."
    )
