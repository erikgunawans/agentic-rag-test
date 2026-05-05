"""Phase 22 / v1.3 — Contract Review harness (CR-01..08, DOCX-01..08; D-22-01..15).

9-phase deterministic Contract Review workflow exercising every phase type
end-to-end and producing a polished .docx executive report. The 9-phase
structure = 8 user-visible CR-XX phases + 1 PROGRAMMATIC filter step
(`filter-redline-candidates`) inserted between CR-06 and CR-07 for cost
optimization (ISSUE-06; ROADMAP success criterion 4). The filter is NOT a
user-visible REQ — CR-01..08 still map 1:1 to the 8 named user phases.

  Phase 1 (CR-01) — Document Intake (PROGRAMMATIC): extract text from
    uploaded DOCX/PDF via python-docx + PyPDF2; write contract-text.md.
  Phase 2 (CR-02) — Contract Classification (LLM_SINGLE):
    type/parties/dates/governing_law/jurisdiction; ContractClassification schema.
  Phase 3 (CR-03) — Gather Context (LLM_HUMAN_INPUT)            [stub — plan 22-07]
  Phase 4 (CR-04) — Load Playbook (LLM_AGENT, max 10 rounds)    [stub — plan 22-07]
  Phase 5 (CR-05) — Clause Extraction (PROGRAMMATIC)            [stub — plan 22-08]
  Phase 6 (CR-06) — Risk Analysis (LLM_BATCH_AGENTS, batch=5)   [stub — plan 22-09]
  Phase 7 (filter-redline-candidates) — PROGRAMMATIC YELLOW/RED filter [stub — plan 22-09]
  Phase 8 (CR-07) — Redline Generation (LLM_BATCH_AGENTS, batch=5) [stub — plan 22-09]
  Phase 9 (CR-08) — Executive Summary + DOCX (LLM_SINGLE + post_execute) [stub — plan 22-10]

Gated behind settings.harness_enabled AND settings.contract_review_enabled
(D-16 dark-launch invariant). CR-21-01 circular-import lesson preserved via
`from __future__ import annotations` + lazy-imported services inside executors.

ISSUE-09: contract_review_enabled=True requires tool_registry_enabled=True —
refusing to register without it (CR-06/07 need search_documents_by_doc_ids).

ISSUE-14 deploy-order: contract_review_enabled MUST remain False until plans
22-06..22-10 all land in production. CR-03..08 stubs would crash if reached
with real user traffic. Enable only after all 5 plans are deployed.
"""
from __future__ import annotations

import io
import logging
from typing import Any

from pydantic import BaseModel, Field

from app.config import get_settings
from app.harnesses.types import (
    HarnessDefinition,
    HarnessPrerequisites,
    PhaseDefinition,
    PhaseType,
)
from app.services.harness_registry import register
from app.services.workspace_service import WorkspaceService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CR-02 — Contract Classification structured output schema
# ---------------------------------------------------------------------------

class ContractClassification(BaseModel):
    """CR-02 LLM output. Enforced via response_format=json_schema (HARN-05).

    ROADMAP success criterion: parties has min_length=2, contract_type non-empty.
    """

    contract_type: str = Field(
        ..., min_length=1, max_length=200,
        description="Type of contract: MSA, NDA, SaaS, Employment, Distribution, etc.",
    )
    parties: list[str] = Field(
        ..., min_length=2, max_length=20,
        description="Named legal entities, e.g. ['Acme Corp', 'Beta Inc']. Min 2.",
    )
    effective_date: str | None = Field(
        None,
        description="ISO 8601 (YYYY-MM-DD) if present in contract, else null",
    )
    expiration_date: str | None = Field(
        None,
        description="ISO 8601 (YYYY-MM-DD) if present, else null",
    )
    governing_law: str = Field(
        ..., min_length=1, max_length=200,
        description="Jurisdiction name: 'Republic of Indonesia', 'New York State', etc.",
    )
    jurisdiction: str = Field(
        ..., min_length=1, max_length=200,
        description="Forum / venue: 'courts of Jakarta', 'arbitration in Singapore', etc.",
    )
    summary: str = Field(
        ..., min_length=20, max_length=1000,
        description="1-2 sentence neutral description of contract scope and parties",
    )


# ---------------------------------------------------------------------------
# CR-01 executor — PROGRAMMATIC text extraction from DOCX / PDF
# ---------------------------------------------------------------------------

async def _phase1_intake(
    *, inputs: dict[str, str], token: str, thread_id: str, harness_run_id: str
) -> dict:
    """CR-01: extract text from the user's uploaded DOCX/PDF; write contract-text.md.

    D-22-12: uses python-docx + PyPDF2 in the BACKEND process (UPL-03 path),
    NOT the sandbox. The sandbox is for DOCX writing (plan 22-10).
    T-22-06-02: 25 MB upload cap enforced upstream (UPL-02); exceptions caught.
    T-22-06-03: exc detail capped at 500 chars, logger.error only.
    """
    ws = WorkspaceService(token=token)
    try:
        files = await ws.list_files(thread_id)
    except Exception as exc:
        logger.error(
            "CR-01 list_files failed harness_run=%s: %s",
            harness_run_id, exc, exc_info=True,
        )
        return {"error": "list_files_failed", "code": "WS_LIST_ERROR", "detail": str(exc)[:500]}

    # Find the first user-uploaded file (one contract per run per D-22)
    uploads = [f for f in files if f.get("source") == "upload"]
    if not uploads:
        return {
            "error": "no_uploaded_file",
            "code": "NO_UPLOAD",
            "detail": (
                "No source='upload' file found in workspace; "
                "user must upload a contract DOCX or PDF first."
            ),
        }

    target = uploads[0]
    file_path = target.get("file_path", "")
    mime = (target.get("mime_type") or "").lower()

    # Fetch binary content from storage via ISSUE-02 method
    content_or_error = await ws.read_binary_file(thread_id, file_path)
    if isinstance(content_or_error, dict):
        # read_binary_file returned a structured error
        logger.error(
            "CR-01 read_binary_file failed for %s: %s",
            file_path, content_or_error,
        )
        return {
            "error": "read_failed",
            "code": "READ_FAILED",
            "detail": str(content_or_error.get("detail", content_or_error))[:500],
        }
    content_bytes: bytes = content_or_error

    # Extract text by mime type — lazy imports per CR-21-01 circular-import lesson
    try:
        if "wordprocessingml" in mime or file_path.lower().endswith(".docx"):
            from docx import Document  # python-docx — pre-installed per plan 22-01
            doc = Document(io.BytesIO(content_bytes))
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            text = "\n\n".join(paragraphs)
            page_count = max(1, len(paragraphs) // 30)  # rough estimate; DOCX has no pages
        elif "pdf" in mime or file_path.lower().endswith(".pdf"):
            from PyPDF2 import PdfReader  # pre-installed per plan 22-01
            reader = PdfReader(io.BytesIO(content_bytes))
            pages_text = [page.extract_text() or "" for page in reader.pages]
            text = "\n\n".join(pages_text)
            page_count = len(reader.pages)
        else:
            return {
                "error": "unsupported_mime",
                "code": "BAD_MIME",
                "detail": f"Expected DOCX or PDF; got {mime!r} for {file_path!r}",
            }
    except Exception as exc:
        logger.error(
            "CR-01 extraction failed for %s: %s",
            file_path, exc, exc_info=True,
        )
        return {
            "error": "extraction_failed",
            "code": "EXTRACT_FAILED",
            "detail": str(exc)[:500],
        }

    if not text.strip():
        return {
            "error": "empty_extraction",
            "code": "EMPTY_TEXT",
            "detail": (
                f"Extracted text is empty for {file_path!r}; "
                "file may be scanned-only or corrupted."
            ),
        }

    markdown = (
        f"# Contract Source\n\n"
        f"- **File:** `{file_path}`\n"
        f"- **MIME:** `{mime}`\n"
        f"- **Pages:** {page_count}\n"
        f"- **Characters:** {len(text)}\n\n"
        f"---\n\n"
        f"{text}\n"
    )

    return {
        "content": markdown,       # engine writes this to workspace_output (contract-text.md)
        "page_count": page_count,
        "char_count": len(text),
        "source_file": file_path,
    }


# ---------------------------------------------------------------------------
# Stub executor — CR-03..08 + filter-redline-candidates
# Subsequent plans (22-07..22-10) replace this in-place for each phase.
# Fails closed: returns a clear "not yet implemented" error so partial
# completion is detectable and plan progress is unambiguous.
# ---------------------------------------------------------------------------

async def _phase_stub_not_implemented(
    *, inputs: Any, token: str, thread_id: str, harness_run_id: str
) -> dict:
    """STUB — this phase body is a placeholder pending subsequent plans."""
    return {
        "error": "phase_not_implemented",
        "code": "STUB",
        "detail": (
            "This Contract Review phase is a Phase 22 stub. "
            "Subsequent plans 22-07..22-10 fill it in."
        ),
    }


# ---------------------------------------------------------------------------
# HarnessDefinition — 9-phase scaffold
# 8 user-visible CR-XX phases + 1 programmatic filter (ISSUE-06)
# ---------------------------------------------------------------------------

CONTRACT_REVIEW = HarnessDefinition(
    name="contract-review",
    display_name="Contract Review",
    prerequisites=HarnessPrerequisites(
        requires_upload=True,
        upload_description="your contract DOCX or PDF (one file)",
        accepted_mime_types=[
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ],
        min_files=1,
        max_files=1,
        harness_intro=(
            "Hi! I'm the Contract Review harness. Upload a contract (DOCX or PDF) "
            "and I'll classify it, gather your review context, load the playbook, "
            "extract every clause, grade each one for risk against the playbook, "
            "draft redlines for problematic clauses, and deliver an executive .docx report."
        ),
    ),
    phases=[
        # Phase 1 — CR-01 Document Intake (PROGRAMMATIC)
        PhaseDefinition(
            name="intake",
            description="Extract text from uploaded DOCX/PDF; write contract-text.md.",
            phase_type=PhaseType.PROGRAMMATIC,
            tools=[],
            workspace_inputs=[],
            workspace_output="contract-text.md",
            executor=_phase1_intake,
            timeout_seconds=120,
        ),
        # Phase 2 — CR-02 Contract Classification (LLM_SINGLE)
        PhaseDefinition(
            name="classify",
            description="Classify type/parties/dates/governing_law/jurisdiction (Pydantic-validated).",
            phase_type=PhaseType.LLM_SINGLE,
            system_prompt_template=(
                "You are classifying a legal contract. Read contract-text.md and produce "
                "a JSON object matching the ContractClassification schema:\n"
                "  - contract_type: short string (e.g. 'MSA', 'NDA', 'SaaS Subscription')\n"
                "  - parties: array of >=2 legal entity names (verbatim if possible)\n"
                "  - effective_date / expiration_date: ISO 8601 (YYYY-MM-DD) or null\n"
                "  - governing_law: jurisdiction name (e.g. 'Republic of Indonesia')\n"
                "  - jurisdiction: forum/venue clause (e.g. 'courts of Jakarta')\n"
                "  - summary: 1-2 sentence neutral description (20-1000 chars)\n"
                "Return ONLY the JSON object — no prose."
            ),
            tools=[],
            workspace_inputs=["contract-text.md"],
            workspace_output="classification.md",
            output_schema=ContractClassification,
            timeout_seconds=180,
        ),
        # Phase 3 — CR-03 Gather Context (LLM_HUMAN_INPUT)  [stub — plan 22-07]
        PhaseDefinition(
            name="gather-context",
            description="Stub — Plan 22-07 populates the HIL question prompt.",
            phase_type=PhaseType.LLM_HUMAN_INPUT,
            system_prompt_template="STUB",
            tools=[],
            workspace_inputs=["classification.md"],
            workspace_output="review-context.md",
            timeout_seconds=86_400,
        ),
        # Phase 4 — CR-04 Load Playbook (LLM_AGENT, max 10 rounds)  [stub — plan 22-07]
        PhaseDefinition(
            name="load-playbook",
            description="Stub — Plan 22-07 populates the RAG-agent prompt.",
            phase_type=PhaseType.LLM_AGENT,
            system_prompt_template="STUB",
            tools=["search_documents", "analyze_document"],
            workspace_inputs=["classification.md", "review-context.md"],
            workspace_output="playbook-context.md",
            timeout_seconds=600,
        ),
        # Phase 5 — CR-05 Clause Extraction (PROGRAMMATIC)  [stub — plan 22-08]
        PhaseDefinition(
            name="extract-clauses",
            description="Stub — Plan 22-08 populates the chunk-and-extract executor.",
            phase_type=PhaseType.PROGRAMMATIC,
            tools=[],
            workspace_inputs=["contract-text.md"],
            workspace_output="clauses.md",
            executor=_phase_stub_not_implemented,
            timeout_seconds=600,
        ),
        # Phase 6 — CR-06 Risk Analysis (LLM_BATCH_AGENTS)  [stub — plan 22-09]
        PhaseDefinition(
            name="risk-analysis",
            description="Stub — Plan 22-09 populates the per-clause risk assessment.",
            phase_type=PhaseType.LLM_BATCH_AGENTS,
            system_prompt_template="STUB",
            tools=["search_documents_by_doc_ids", "analyze_document"],
            workspace_inputs=["clauses.json", "playbook-context.md", "review-context.md"],
            workspace_output="risk-analysis.json",
            batch_size=5,
            timeout_seconds=1800,
        ),
        # Phase 7 — Filter Redline Candidates (PROGRAMMATIC — ISSUE-06 cost optimization)
        # Filters risk-analysis.json to YELLOW/RED clauses; writes redline-candidates.json.
        # This is an internal cost-optimization step, NOT a user-visible REQ.
        # CR-01..08 still map 1:1 to the 8 named user phases.
        # [stub — plan 22-09]
        PhaseDefinition(
            name="filter-redline-candidates",
            description="Stub — Plan 22-09 populates the YELLOW/RED filter executor.",
            phase_type=PhaseType.PROGRAMMATIC,
            tools=[],
            workspace_inputs=["risk-analysis.json"],
            workspace_output="redline-candidates.json",
            executor=_phase_stub_not_implemented,
            timeout_seconds=30,
        ),
        # Phase 8 — CR-07 Redline Generation (LLM_BATCH_AGENTS)  [stub — plan 22-09]
        PhaseDefinition(
            name="redline-generation",
            description="Stub — Plan 22-09 populates the per-clause redline drafter.",
            phase_type=PhaseType.LLM_BATCH_AGENTS,
            system_prompt_template="STUB",
            tools=["search_documents_by_doc_ids", "analyze_document"],
            workspace_inputs=["redline-candidates.json", "playbook-context.md", "review-context.md"],
            workspace_output="redlines.json",
            batch_size=5,
            timeout_seconds=1800,
        ),
        # Phase 9 — CR-08 Executive Summary + DOCX post_execute  [stub — plan 22-10]
        PhaseDefinition(
            name="executive-summary",
            description="Stub — Plan 22-10 populates the summary prompt + DOCX post_execute.",
            phase_type=PhaseType.LLM_SINGLE,
            system_prompt_template="STUB",
            tools=[],
            workspace_inputs=[
                "classification.md", "review-context.md", "playbook-context.md",
                "clauses.md", "risk-analysis.json", "redlines.json",
            ],
            workspace_output="contract-review-report.md",
            output_schema=None,      # Plan 22-10 sets ExecutiveSummary
            post_execute=None,       # Plan 22-10 sets _generate_docx_post_execute
            timeout_seconds=300,
        ),
    ],
)


# ---------------------------------------------------------------------------
# Gated registration — ISSUE-09 guard + D-16 off-mode invariant
# ---------------------------------------------------------------------------

if get_settings().harness_enabled and get_settings().contract_review_enabled:
    if not get_settings().tool_registry_enabled:
        logger.error(
            "contract_review: REFUSING to register — contract_review_enabled=True but "
            "tool_registry_enabled=False. CR-06/07 require search_documents_by_doc_ids "
            "(plan 22-02), which is gated on tool_registry_enabled. Enable both or neither."
        )
        raise RuntimeError(
            "ISSUE-09: contract_review_enabled requires tool_registry_enabled "
            "— refusing to register harness"
        )
    register(CONTRACT_REVIEW)
    logger.info(
        "contract_review: registered "
        "(HARNESS_ENABLED=True, CONTRACT_REVIEW_ENABLED=True, TOOL_REGISTRY_ENABLED=True)"
    )
else:
    logger.info(
        "contract_review: NOT registered (harness_enabled=%s, contract_review_enabled=%s)",
        get_settings().harness_enabled,
        get_settings().contract_review_enabled,
    )
