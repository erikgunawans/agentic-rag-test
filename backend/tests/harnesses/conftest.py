"""Phase 22 / Plan 22-12 — Shared fixtures for Contract Review E2E tests.

Fixtures:
  sandbox_in_process_stub  — patches SandboxService.execute() to run
                             DOCX_GENERATION_SCRIPT_BODY in-process via subprocess,
                             returns canonical engine merge shape with file:// signed URL.
  phase_routed_llm_mock    — inspects system prompt to route canned LLM responses
                             per CR phase (classify, gather-context, load-playbook,
                             extract-clauses, risk-analysis, redline-generation,
                             executive-summary).

ISSUE-05 PIN: sandbox stub returns
  {exit_code, stdout, stderr, error_type, execution_ms, files, execution_id}
  files[i] = {filename, size_bytes, signed_url, storage_path}
  PINNED API only — no forbidden patterns.
"""
from __future__ import annotations

import asyncio
import io
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import textwrap
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Path to the test fixture DOCX
_DATA_DIR = pathlib.Path(__file__).parent.parent / "data"
_SYNTH_CONTRACT = _DATA_DIR / "synth-contract.docx"


# ---------------------------------------------------------------------------
# Canned LLM responses per phase (realistic-shape JSON)
# ---------------------------------------------------------------------------

_CLASSIFICATION_JSON = json.dumps({
    "contract_type": "MSA",
    "parties": ["Acme Corp", "Beta Inc"],
    "effective_date": "2026-01-01",
    "expiration_date": None,
    "governing_law": "Republic of Indonesia",
    "jurisdiction": "courts of Jakarta",
    "summary": (
        "Master Services Agreement between Acme Corp (Provider) and Beta Inc (Customer) "
        "governing service delivery and payment terms under Indonesian law."
    ),
})

_GATHER_CONTEXT_JSON = json.dumps({
    "question": (
        "Could you briefly tell me: (1) which party you represent — Provider or Customer? "
        "(2) Is there a deadline for this review? "
        "(3) Any clauses you'd like us to focus on? "
        "(4) Any other deal context? Minimal answers are perfectly fine."
    ),
})

_PLAYBOOK_CONTEXT_JSON = json.dumps({
    "playbook_docs": [],
    "clause_category_to_playbook": {
        "Liability": [], "Indemnification": [], "IP": [], "Data Protection": [],
        "Confidentiality": [], "Warranties": [], "Term/Termination": [], "Governing Law": [],
        "Insurance": [], "Assignment": [], "Force Majeure": [], "Payment": [], "Other": [],
    },
    "context_quality": "unfounded",
    "notes": "No playbook documents found; falling back to generic legal standards.",
})

_CLAUSE_EXTRACTION_JSON = json.dumps({
    "clauses": [
        {
            "category": "Liability",
            "heading": "1. LIABILITY",
            "text": (
                "Each party's total liability under this agreement shall not exceed USD 100,000. "
                "In no event shall either party be liable for any indirect, incidental, special, "
                "or consequential damages."
            ),
            "position": 0,
        },
        {
            "category": "Confidentiality",
            "heading": "2. CONFIDENTIALITY",
            "text": (
                "Each party shall hold the other party's confidential information in strict "
                "confidence for five (5) years following termination."
            ),
            "position": 1,
        },
        {
            "category": "Payment",
            "heading": "3. PAYMENT",
            "text": (
                "Customer shall pay Provider within thirty (30) days of receipt of invoice. "
                "Late payments shall accrue interest at 1.5% per month."
            ),
            "position": 2,
        },
    ],
    "chunk_index": 0,
    "total_chunks": 1,
})

# CR-06 sub-agent canned responses — one ClauseRisk JSON per clause
_RISK_TERMINAL_LIABILITY = json.dumps({
    "clause_index": 0,
    "clause_category": "Liability",
    "clause_heading": "1. LIABILITY",
    "risk_grade": "RED",
    "rationale": "USD 100,000 liability cap is materially low for an MSA; well below industry standard.",
    "alternative_language": "Each party's liability cap should be the total fees paid in the 12 months prior.",
    "grounding_doc_ids": [],
})
_RISK_TERMINAL_CONF = json.dumps({
    "clause_index": 1,
    "clause_category": "Confidentiality",
    "clause_heading": "2. CONFIDENTIALITY",
    "risk_grade": "YELLOW",
    "rationale": "5-year confidentiality period is shorter than playbook standard; acceptable with caveat.",
    "alternative_language": "Extend confidentiality to 7 years for trade-secret-adjacent obligations.",
    "grounding_doc_ids": [],
})
_RISK_TERMINAL_PAYMENT = json.dumps({
    "clause_index": 2,
    "clause_category": "Payment",
    "clause_heading": "3. PAYMENT",
    "risk_grade": "GREEN",
    "rationale": "Net-30 terms and 1.5%/month interest rate are standard for commercial MSA.",
    "alternative_language": None,
    "grounding_doc_ids": [],
})

# CR-07 sub-agent canned responses
_REDLINE_TERMINAL_LIABILITY = json.dumps({
    "clause_index": 0,
    "clause_category": "Liability",
    "original_text": (
        "Each party's total liability under this agreement shall not exceed USD 100,000."
    ),
    "proposed_text": (
        "Each party's total aggregate liability under this agreement shall not exceed "
        "the total fees paid by Customer to Provider in the twelve (12) months preceding "
        "the claim."
    ),
    "rationale": (
        "USD 100,000 cap is materially inadequate; fee-based cap aligns with "
        "standard commercial MSA practice."
    ),
    "fallback_positions": ["Cap at USD 500,000", "Cap at 2x total contract value"],
})
_REDLINE_TERMINAL_CONF = json.dumps({
    "clause_index": 1,
    "clause_category": "Confidentiality",
    "original_text": (
        "Each party shall hold the other party's confidential information in strict "
        "confidence for five (5) years following termination."
    ),
    "proposed_text": (
        "Each party shall hold the other party's confidential information in strict "
        "confidence for seven (7) years following termination of this agreement."
    ),
    "rationale": (
        "Extension from 5 to 7 years aligns with playbook standard for trade-secret "
        "protection under Indonesian law."
    ),
    "fallback_positions": ["Accept 5 years with annual right of review"],
})

_EXECUTIVE_SUMMARY_JSON = json.dumps({
    "overall_risk": "RED",
    "recommendation": (
        "No playbook materials found — risk grades reflect generic legal standards. "
        "This MSA carries elevated risk due to a materially low liability cap (RED). "
        "Immediate renegotiation of the liability clause is strongly recommended "
        "before execution."
    ),
    "key_findings": [
        "Liability cap of USD 100,000 is materially inadequate for an MSA.",
        "Confidentiality period of 5 years is below the 7-year playbook standard.",
        "Payment terms (Net-30, 1.5%/month) are within acceptable range.",
    ],
    "risk_breakdown": {"RED": 1, "YELLOW": 1, "GREEN": 1},
    "next_steps": [
        "Renegotiate liability cap to 12-month-fees basis.",
        "Extend confidentiality period to 7 years.",
        "Confirm governing law clause with Indonesian counsel.",
    ],
})


def _route_llm_response(messages: list, **_) -> dict:
    """Inspect system prompt to pick the right canned JSON response per phase.

    Called as side_effect for OpenRouterService.complete_with_tools mock.
    Returns {"content": <json string>, "usage": {}}.
    """
    sys_content = ""
    for msg in (messages or []):
        if isinstance(msg, dict) and msg.get("role") == "system":
            sys_content = msg.get("content", "").lower()
            break

    # Route by distinctive keywords in the system prompt.
    # Order matters — most specific checks first. Use phrases unique to each phase's
    # prompt to avoid cross-contamination (e.g. "classified" ⊃ "classif" → check
    # for the explicit classification task phrase first, then narrow HIL phrase).
    if "classifying a legal contract" in sys_content:
        content = _CLASSIFICATION_JSON
    elif "gathering review context" in sys_content:
        content = _GATHER_CONTEXT_JSON
    elif "playbook" in sys_content and "list_playbook_documents" in sys_content:
        content = _PLAYBOOK_CONTEXT_JSON
    elif "extracting every distinct legal clause" in sys_content:
        content = _CLAUSE_EXTRACTION_JSON
    elif "risk" in sys_content and "clause_index" in sys_content and "risk_grade" in sys_content:
        # CR-06 sub-agent — return per-clause risk based on item hint in user prompt
        user_content = ""
        for msg in (messages or []):
            if isinstance(msg, dict) and msg.get("role") == "user":
                user_content = msg.get("content", "").lower()
                break
        if "liability" in user_content:
            content = f"```json\n{_RISK_TERMINAL_LIABILITY}\n```"
        elif "confidentiality" in user_content:
            content = f"```json\n{_RISK_TERMINAL_CONF}\n```"
        else:
            content = f"```json\n{_RISK_TERMINAL_PAYMENT}\n```"
    elif "redline" in sys_content and "original_text" in sys_content:
        # CR-07 sub-agent — return per-clause redline based on item hint
        user_content = ""
        for msg in (messages or []):
            if isinstance(msg, dict) and msg.get("role") == "user":
                user_content = msg.get("content", "").lower()
                break
        if "liability" in user_content:
            content = f"```json\n{_REDLINE_TERMINAL_LIABILITY}\n```"
        else:
            content = f"```json\n{_REDLINE_TERMINAL_CONF}\n```"
    elif "executive summary" in sys_content:
        content = _EXECUTIVE_SUMMARY_JSON
    else:
        # Fallback: generic OK
        content = json.dumps({"ok": True})

    return {"content": content, "usage": {}, "model": "mocked"}


@pytest.fixture
def phase_routed_llm_mock():
    """Return a callable suitable for AsyncMock(side_effect=...) on complete_with_tools.

    Usage:
        with patch("app.services.openrouter_service.OpenRouterService.complete_with_tools",
                   AsyncMock(side_effect=phase_routed_llm_mock)):
            ...
    """
    async def _async_route(messages, **kwargs):
        return _route_llm_response(messages, **kwargs)
    return _async_route


# ---------------------------------------------------------------------------
# sandbox_in_process_stub
# ---------------------------------------------------------------------------

@pytest.fixture
def sandbox_in_process_stub():
    """Patch SandboxService.execute() to run DOCX_GENERATION_SCRIPT_BODY in-process.

    The fixture:
    1. Patches app.services.sandbox_service.get_sandbox_service to return a mock
       whose .execute() coroutine runs the DOCX_GENERATION_SCRIPT_BODY script body
       locally (via subprocess) in a temp dir.
    2. Also patches httpx.AsyncClient.get to intercept file:// signed_url returns
       and read the bytes directly from the filesystem.
    3. Returns canonical engine merge shape:
         {exit_code, stdout, stderr, error_type, execution_ms, files, execution_id}
         files[i] = {filename, size_bytes, signed_url, storage_path}
       ISSUE-05 PIN: pinned API only.
    """
    from app.harnesses.contract_review_docx import DOCX_GENERATION_SCRIPT_BODY

    # Shared store: fake-url → docx_bytes (populated inside the temp dir context)
    _docx_bytes_store: dict[str, bytes] = {}

    async def _run_docx_in_process(*, code: str, thread_id: str, user_id: str, token: str, **_):
        """Run the DOCX generation code in a subprocess and return sandbox-shaped result.

        Bytes are read INSIDE the tempdir context so they survive its cleanup.
        A stable fake signed URL is used instead of file:// to avoid path expiry.
        """
        import uuid as _uuid
        execution_id = str(_uuid.uuid4())
        fake_signed_url = f"file://sandbox-stub/{execution_id}/contract-review.docx"

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = os.path.join(tmp_dir, "sandbox", "output")
            os.makedirs(output_dir, exist_ok=True)

            # Inject JSON→Python shims: json.dumps emits 'null'/'true'/'false' which are
            # JSON literals, not valid Python. Prepend shim assignments so the INPUT_DATA
            # literal evaluates correctly in the subprocess.
            json_shims = "null = None\ntrue = True\nfalse = False\n"
            patched_code = json_shims + code.replace(
                "'/sandbox/output/contract-review.docx'",
                repr(os.path.join(output_dir, "contract-review.docx")),
            ).replace(
                "os.makedirs(os.path.dirname(out_path), exist_ok=True)",
                "pass  # already created by test stub",
            )

            script_file = os.path.join(tmp_dir, "run.py")
            with open(script_file, "w") as f:
                f.write(patched_code)

            result = subprocess.run(
                [sys.executable, script_file],
                capture_output=True,
                text=True,
                timeout=60,
            )

            docx_path = os.path.join(output_dir, "contract-review.docx")
            if result.returncode == 0 and os.path.exists(docx_path):
                # Read bytes INSIDE the context manager before the temp dir is deleted
                docx_bytes = open(docx_path, "rb").read()
                # Store in shared dict so the httpx fake client can serve them
                _docx_bytes_store[fake_signed_url] = docx_bytes
                return {
                    "exit_code": 0,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "error_type": None,
                    "execution_ms": 100,
                    "execution_id": execution_id,
                    "files": [
                        {
                            "filename": "contract-review.docx",
                            "size_bytes": len(docx_bytes),
                            "signed_url": fake_signed_url,
                            "storage_path": f"sandbox/{execution_id}/contract-review.docx",
                        }
                    ],
                }
            else:
                return {
                    "exit_code": result.returncode or 1,
                    "stdout": result.stdout,
                    "stderr": result.stderr or "subprocess failed",
                    "error_type": "exception",
                    "execution_ms": 100,
                    "execution_id": execution_id,
                    "files": [],
                }

    mock_sb = MagicMock()
    mock_sb.execute = AsyncMock(side_effect=_run_docx_in_process)

    class _FakeResponse:
        def __init__(self, content: bytes):
            self.content = content
            self.status_code = 200

        def raise_for_status(self):
            pass

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass  # accept timeout= and any other kwargs from httpx.AsyncClient(timeout=60)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url, **kwargs):
            if url in _docx_bytes_store:
                return _FakeResponse(_docx_bytes_store[url])
            raise ValueError(f"sandbox_in_process_stub: unexpected signed URL {url!r}")

    with patch("app.services.sandbox_service.get_sandbox_service", return_value=mock_sb):
        with patch("httpx.AsyncClient", _FakeAsyncClient):
            yield mock_sb
