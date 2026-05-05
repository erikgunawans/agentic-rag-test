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
import json
import logging
import re
from enum import Enum
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
from app.services.openrouter_service import OpenRouterService
from app.services.redaction.egress import egress_filter
from app.services.workspace_service import WorkspaceService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CR-02 — Contract Classification structured output schema
# ---------------------------------------------------------------------------

# Canonical clause categories used by CR-04..CR-08 (keep verbatim — plan 22-07..09 reference this)
CLAUSE_CATEGORIES = [
    "Liability", "Indemnification", "IP", "Data Protection", "Confidentiality",
    "Warranties", "Term/Termination", "Governing Law", "Insurance",
    "Assignment", "Force Majeure", "Payment", "Other",
]

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
# CR-04 — Playbook Context output schema (D-22-06)
# ---------------------------------------------------------------------------

class PlaybookDoc(BaseModel):
    """Single playbook document entry returned by list_playbook_documents."""

    id: str = Field(..., min_length=1, description="Document UUID from list_playbook_documents results")
    title: str = Field(..., min_length=1, max_length=300)
    summary: str = Field(default="", max_length=300, description="<=300 char summary")
    source_priority: int = Field(
        default=2, ge=1, le=3,
        description=(
            "D-22-08 authority order: 1=user-workspace upload, "
            "2=regulatory_intel, 3=general document library"
        ),
    )


class PlaybookContext(BaseModel):
    """CR-04 structured output written to playbook-context.md (D-22-06).

    Plan 22-09 (CR-06/07 batch sub-agents) reads this file at runtime and
    validates the schema via PlaybookContext.model_validate_json().
    context_quality='unfounded' triggers the D-22-07 empty-playbook fallback
    in CR-08's executive summary prompt.
    """

    playbook_docs: list[PlaybookDoc] = Field(default_factory=list)
    clause_category_to_playbook: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Maps each of the 13 CLAUSE_CATEGORIES to a list of relevant doc IDs",
    )
    context_quality: str = Field(
        default="founded",
        description="'founded' (>=1 playbook doc found) or 'unfounded' (D-22-07 empty-playbook fallback)",
    )
    notes: str = Field(default="", max_length=2000)


# ---------------------------------------------------------------------------
# CR-05 — Clause Extraction schemas + constants
# ---------------------------------------------------------------------------

class Clause(BaseModel):
    """Single extracted clause (CR-05 output element)."""
    category: str = Field(..., description="One of CLAUSE_CATEGORIES; coerce to 'Other' if unrecognized")
    heading: str = Field(..., min_length=1, max_length=300)
    text: str = Field(..., min_length=1, max_length=10_000)
    position: int = Field(..., ge=0)


class ClauseExtractionResult(BaseModel):
    """LLM JSON output shape for a single chunk (CR-05)."""
    clauses: list[Clause] = Field(default_factory=list)
    chunk_index: int = Field(..., ge=0)
    total_chunks: int = Field(..., ge=1)


# ---------------------------------------------------------------------------
# CR-06/CR-07 — Risk Analysis + Redline Generation schemas (plan 22-09)
# REVIEW #2 closed: filter parses sub-agent terminal text via _parse_subagent_json_terminal
# REVIEW #3 closed: RedlineCandidate carries original_text joined from clauses.json
# ---------------------------------------------------------------------------

class RiskGrade(str, Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"


class ClauseRisk(BaseModel):
    """CR-06 LLM output per clause (validated from sub-agent terminal text by filter executor).

    REVIEW #2: filter extracts this from result.terminal.text (full LLM response string),
    NOT from a pre-parsed field on the engine's batch merge dict.
    """
    clause_index: int = Field(..., ge=0)
    clause_category: str
    clause_heading: str
    risk_grade: RiskGrade
    rationale: str = Field(..., min_length=20, max_length=2000)
    alternative_language: str | None = Field(None, max_length=4000)
    grounding_doc_ids: list[str] = Field(default_factory=list, max_length=10)


class RedlineCandidate(BaseModel):
    """REVIEW #3: ClauseRisk + original_text joined from clauses.json by clause_index.

    CR-07 sub-agent receives this shape so it has the verbatim clause body to rewrite.
    Rows that cannot be joined (clause_index not in clauses.json) are DROPPED — empty
    original_text NEVER reaches CR-07 (REVIEW #3 invariant).
    """
    clause_index: int = Field(..., ge=0)
    clause_category: str
    clause_heading: str
    original_text: str = Field(..., min_length=1, max_length=10_000)
    risk_grade: RiskGrade
    rationale: str
    alternative_language: str | None = None
    grounding_doc_ids: list[str] = Field(default_factory=list, max_length=10)


class Redline(BaseModel):
    """CR-07 LLM output per YELLOW/RED clause — a concrete redline with fallback positions."""
    clause_index: int = Field(..., ge=0)
    clause_category: str
    original_text: str = Field(..., min_length=1, max_length=10_000)
    proposed_text: str = Field(..., min_length=1, max_length=10_000)
    rationale: str = Field(..., min_length=20, max_length=2000)
    fallback_positions: list[str] = Field(default_factory=list, max_length=5)


# CR-05 chunking constants (plan 22-08)
CR05_CHUNK_CHARS = 180_000
CR05_CHUNK_OVERLAP_CHARS = 5_000
CR05_DEDUPE_RATIO = 0.85


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
# CR-05 executor — PROGRAMMATIC clause extraction with per-chunk egress_filter wrap
# ---------------------------------------------------------------------------

def _chunk_for_clause_extraction(text: str) -> list[str]:
    """Split `text` into overlapping chunks of CR05_CHUNK_CHARS with CR05_CHUNK_OVERLAP_CHARS overlap."""
    if len(text) <= CR05_CHUNK_CHARS:
        return [text]
    chunks: list[str] = []
    step = CR05_CHUNK_CHARS - CR05_CHUNK_OVERLAP_CHARS
    for start in range(0, len(text), step):
        end = min(start + CR05_CHUNK_CHARS, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
    return chunks


def _dedupe_clauses(clauses: list[Clause], ratio: float) -> list[Clause]:
    """Deduplicate by (category, text) fuzzy similarity. Different bodies → NOT deduped (ISSUE-10)."""
    from difflib import SequenceMatcher
    kept: list[Clause] = []
    for c in clauses:
        is_dup = False
        for k in kept:
            if k.category == c.category and SequenceMatcher(None, k.text, c.text).ratio() > ratio:
                is_dup = True
                break
        if not is_dup:
            kept.append(c)
    return kept


def _build_cr05_chunk_prompt(*, chunk_text: str, chunk_index: int, total_chunks: int) -> str:
    """Build the per-chunk extraction prompt for CR-05."""
    return (
        "You are extracting every distinct legal clause from a contract chunk. "
        f"This is chunk {chunk_index + 1} of {total_chunks}.\n\n"
        "For each clause you find, return a JSON object with fields:\n"
        "  category: one of these strings exactly — "
        f"{', '.join(CLAUSE_CATEGORIES)}\n"
        "  heading: section heading OR the first 80-100 chars of the clause\n"
        "  text: the clause's verbatim text (do not paraphrase)\n"
        "  position: approximate character offset in the chunk (integer)\n\n"
        "Return ONLY a JSON object of shape "
        "{\"clauses\": [...], \"chunk_index\": <int>, \"total_chunks\": <int>}.\n"
        f"Use chunk_index={chunk_index}, total_chunks={total_chunks}.\n"
        "Use 'Other' for clauses that don't fit any of the listed categories.\n\n"
        f"--- CONTRACT CHUNK ---\n{chunk_text}\n--- END CHUNK ---\n"
    )


async def _phase5_extract_clauses(
    *,
    inputs: dict[str, str],
    token: str,
    thread_id: str,
    harness_run_id: str,
    # REVIEW #4 / SEC-04 / B4 single-registry — engine passes these via plan 22-08 Task 1:
    registry=None,
    system_settings: dict | None = None,
    user_id: str | None = None,
    user_email: str | None = None,
    **_,  # forward-compat for any future engine kwargs
) -> dict:
    """CR-05: read contract-text.md; LLM-extract clauses (chunked if needed); dedupe; write clauses.md + clauses.json.

    REVIEW #4 invariant: every per-chunk LLM call is wrapped by egress_filter(payload, registry, None)
    BEFORE OpenRouterService is invoked. If the registry is None (e.g. unit test or harness invoked
    outside chat router), the wrap is skipped — but in production the chat router B4 single-registry
    always provides one.
    """
    import json as _j

    contract_text = (inputs or {}).get("contract-text.md", "")
    if not contract_text or not contract_text.strip():
        return {
            "error": "contract_text_missing",
            "code": "NO_CONTRACT",
            "detail": "Phase 5 invoked but inputs['contract-text.md'] is empty",
        }

    chunks = _chunk_for_clause_extraction(contract_text)
    total_chunks = len(chunks)
    logger.info(
        "CR-05: chunked harness_run=%s chars=%d chunks=%d",
        harness_run_id, len(contract_text), total_chunks,
    )

    all_clauses: list[Clause] = []
    chunks_failed = 0
    chunks_egress_blocked = 0

    for idx, chunk in enumerate(chunks):
        prompt = _build_cr05_chunk_prompt(
            chunk_text=chunk, chunk_index=idx, total_chunks=total_chunks
        )
        messages = [{"role": "system", "content": prompt}]

        # REVIEW #4 / SEC-04: egress filter pre-call. Mirrors harness_engine.py LLM_SINGLE pattern.
        if registry is not None:
            payload = _j.dumps(messages, ensure_ascii=False)
            er = egress_filter(payload, registry, None)
            if er.tripped:
                chunks_egress_blocked += 1
                chunks_failed += 1
                logger.warning(
                    "CR-05 chunk %d/%d egress-blocked harness_run=%s",
                    idx, total_chunks, harness_run_id,
                )
                continue  # skip this chunk; don't fail the whole phase

        try:
            or_svc = OpenRouterService()
            llm_result = await or_svc.complete_with_tools(
                messages=messages,
                tools=None,
                model=None,
                response_format={"type": "json_object"},
            )
            raw = llm_result.get("content", "")
            parsed = ClauseExtractionResult.model_validate(_j.loads(raw))
            for c in parsed.clauses:
                if c.category not in CLAUSE_CATEGORIES:
                    c.category = "Other"
            all_clauses.extend(parsed.clauses)
        except Exception as exc:
            chunks_failed += 1
            logger.warning(
                "CR-05 chunk %d/%d failed harness_run=%s: %s",
                idx, total_chunks, harness_run_id, exc, exc_info=True,
            )

    if chunks_failed == total_chunks:
        return {
            "error": "all_chunks_failed",
            "code": "CR05_FAILED",
            "detail": (
                f"All {total_chunks} chunks failed extraction "
                f"(egress_blocked={chunks_egress_blocked})"
            ),
        }

    deduped = _dedupe_clauses(all_clauses, ratio=CR05_DEDUPE_RATIO)

    clauses_json = _j.dumps([c.model_dump() for c in deduped], ensure_ascii=False, indent=2)
    markdown = (
        f"# Extracted Clauses\n\n"
        f"- **Total clauses:** {len(deduped)} (from {len(all_clauses)} pre-dedupe)\n"
        f"- **Chunks processed:** {total_chunks - chunks_failed}/{total_chunks}\n\n"
        f"```json\n{clauses_json}\n```\n"
    )

    # ISSUE-04 / ISSUE-25: also write clauses.json sibling for CR-06 LLM_BATCH_AGENTS consumption
    try:
        ws_inst = WorkspaceService(token=token)
        await ws_inst.write_text_file(
            thread_id,
            "clauses.json",
            clauses_json,
            source="harness",
        )
    except Exception as exc:
        logger.warning("CR-05 sibling clauses.json write failed: %s", exc)

    return {
        "content": markdown,
        "clause_count": len(deduped),
        "chunk_count": total_chunks,
        "chunks_failed": chunks_failed,
        "chunks_egress_blocked": chunks_egress_blocked,
    }


# ---------------------------------------------------------------------------
# CR-06 / CR-07 helpers — REVIEW #2 + #3
# ---------------------------------------------------------------------------

def _parse_subagent_json_terminal(terminal_text: str) -> dict | None:
    """REVIEW #2: extract a JSON object from a sub-agent's full LLM text terminal.

    run_sub_agent_loop yields {"_terminal_result": {"text": full_response}} where
    full_response is the LLM's entire text output. The CR-06 prompt asks for JSON
    inside a ```json``` code block; CR-07 likewise. This helper extracts that JSON.

    Strategy (in order):
      1. Try fenced ```json``` code block (canonical prompt output).
      2. Try fenced ``` (no language tag) code block.
      3. Find the first balanced { ... } span in the text.
      4. Full-text json.loads (bare JSON, no fencing).

    Returns None on unparseable input. Caller decides how to handle None (typically
    treat as a failed item and skip; increment skipped_unparseable counter).
    """
    if not isinstance(terminal_text, str) or not terminal_text.strip():
        return None
    # 1. Fenced ```json``` code block
    m = re.search(r"```json\s*(\{.*?\})\s*```", terminal_text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    # 2. Fenced ``` (no language tag) code block
    m2 = re.search(r"```\s*(\{.*?\})\s*```", terminal_text, re.DOTALL)
    if m2:
        try:
            return json.loads(m2.group(1))
        except Exception:
            pass
    # 3. First balanced { ... } span in the text
    first = terminal_text.find("{")
    last = terminal_text.rfind("}")
    if first != -1 and last > first:
        try:
            return json.loads(terminal_text[first:last + 1])
        except Exception:
            pass
    # 4. Full-text parse (bare JSON, no fencing)
    try:
        return json.loads(terminal_text)
    except Exception:
        return None


async def _phase_filter_redline_candidates(
    *,
    inputs: dict[str, str],
    token: str,
    thread_id: str,
    harness_run_id: str,
    **_,  # forward-compat for engine kwargs (registry, system_settings, user_id, user_email, etc.)
) -> dict:
    """REVIEW #2 + #3: parse risk-analysis.json (engine's batch merge of ClauseRisk JSONs
    embedded in sub-agent terminal text), validate, keep YELLOW/RED, and JOIN to clauses.json
    by clause_index to splice original_text into each row before writing redline-candidates.json.

    REVIEW #2: each risk-analysis.json row is the engine's CANONICAL merge shape:
      {"item_index": int, "status": "ok"|"failed",
       "result": {"text": str, "terminal": {"text": <full LLM response>}}}
    The filter extracts the ClauseRisk JSON from result.terminal.text via
    _parse_subagent_json_terminal — NOT from a fictional result.terminal.risk_grade key.

    REVIEW #3: ClauseRisk has no original_text field. The filter reads clauses.json (written
    by _phase5_extract_clauses; ISSUE-25) and joins by clause_index (array position) to
    splice the verbatim clause body into each RedlineCandidate row before forwarding to CR-07.
    Rows where clause_index has no match in clauses.json are DROPPED (logged); empty
    original_text NEVER reaches CR-07.
    """
    risk_text = (inputs or {}).get("risk-analysis.json", "")
    clauses_text = (inputs or {}).get("clauses.json", "")
    if not risk_text.strip():
        return {
            "error": "risk_analysis_missing",
            "code": "NO_RISK",
            "detail": "risk-analysis.json is empty",
        }
    if not clauses_text.strip():
        return {
            "error": "clauses_missing",
            "code": "NO_CLAUSES",
            "detail": "clauses.json is empty (CR-05 sibling write must have run first)",
        }

    try:
        risk_rows = json.loads(risk_text)
        clauses_arr = json.loads(clauses_text)
    except Exception as exc:
        return {
            "error": "filter_parse_failed",
            "code": "PARSE",
            "detail": str(exc)[:500],
        }
    if not isinstance(risk_rows, list) or not isinstance(clauses_arr, list):
        return {
            "error": "shape_invalid",
            "code": "SHAPE",
            "detail": "risk_rows and clauses must both be JSON arrays",
        }

    # REVIEW #3: build clause_index → clause dict lookup from clauses.json.
    # CR-05 writes clauses as a plain array; the array position IS the clause_index.
    clauses_by_idx: dict[int, dict] = {}
    for i, c in enumerate(clauses_arr):
        if isinstance(c, dict):
            clauses_by_idx[i] = c

    candidates: list[dict] = []
    skipped_unparseable = 0
    skipped_no_clause_match = 0
    skipped_green = 0

    # REVIEW #2: each row is the engine's merge shape — parse terminal.text for the ClauseRisk JSON
    for row in risk_rows:
        if not isinstance(row, dict) or row.get("status") != "ok":
            continue
        result = row.get("result") or {}
        terminal = result.get("terminal") or {}
        terminal_text = terminal.get("text", "") if isinstance(terminal, dict) else ""

        parsed_dict = _parse_subagent_json_terminal(terminal_text)
        if parsed_dict is None:
            skipped_unparseable += 1
            logger.warning(
                "CR-06 filter: failed to parse sub-agent terminal text item=%s harness_run=%s",
                row.get("item_index"), harness_run_id,
            )
            continue

        try:
            cr = ClauseRisk.model_validate(parsed_dict)
        except Exception as exc:
            skipped_unparseable += 1
            logger.warning(
                "CR-06 filter: ClauseRisk validation failed item=%s: %s",
                row.get("item_index"), exc,
            )
            continue

        # Keep YELLOW + RED only; skip GREEN
        if cr.risk_grade == RiskGrade.GREEN:
            skipped_green += 1
            continue

        # REVIEW #3: JOIN clause_index → original_text from clauses.json
        clause_match = clauses_by_idx.get(cr.clause_index)
        if not clause_match or not clause_match.get("text"):
            skipped_no_clause_match += 1
            logger.warning(
                "CR-06 filter: no clauses.json row matches clause_index=%d "
                "(REVIEW #3 — original_text join failed); dropping row to prevent "
                "empty original_text from reaching CR-07 harness_run=%s",
                cr.clause_index, harness_run_id,
            )
            continue

        candidate = {
            "clause_index": cr.clause_index,
            "clause_category": cr.clause_category,
            "clause_heading": cr.clause_heading,
            "original_text": clause_match["text"],   # REVIEW #3 — joined verbatim text
            "risk_grade": cr.risk_grade.value,
            "rationale": cr.rationale,
            "alternative_language": cr.alternative_language,
            "grounding_doc_ids": cr.grounding_doc_ids,
        }
        # Validate the assembled RedlineCandidate shape before forwarding
        try:
            RedlineCandidate.model_validate(candidate)
        except Exception as exc:
            logger.warning(
                "CR-06 filter: RedlineCandidate validation failed clause_index=%d: %s",
                cr.clause_index, exc,
            )
            continue

        candidates.append(candidate)

    return {
        "content": json.dumps(candidates, ensure_ascii=False, indent=2),
        "candidate_count": len(candidates),
        "total_risks": len(risk_rows),
        "skipped_green": skipped_green,
        "skipped_unparseable": skipped_unparseable,
        "skipped_no_clause_match": skipped_no_clause_match,
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
        # Phase 3 — CR-03 Gather Context (LLM_HUMAN_INPUT)
        # D-22-09: single combined free-form question (one HIL pause).
        # D-22-10: user reply persisted VERBATIM to review-context.md — no parse pass.
        # D-22-11: skip-tolerant — minimal answers ("just go", "...") are fully valid.
        PhaseDefinition(
            name="gather-context",
            description="Ask the user one combined question about review context; write reply to review-context.md.",
            phase_type=PhaseType.LLM_HUMAN_INPUT,
            system_prompt_template=(
                "You are gathering review context for a Contract Review run. The user just uploaded "
                "a contract and we have already classified it (see workspace input classification.md).\n\n"
                "Generate ONE combined free-form question (single paragraph, plain language) asking "
                "the user about all four topics in one breath:\n"
                "  1. Which party are you in this contract? (e.g. 'we are the buyer/customer/licensee')\n"
                "  2. Is there a deadline or pressure on this review?\n"
                "  3. Which clauses or risks should we focus on?\n"
                "  4. What's the broader deal context?\n\n"
                "Be conversational and concise (under 80 words). Acknowledge the user can answer "
                "any subset — minimal answers like 'just go' or '...' are fully valid. Respond as a JSON "
                "object {\"question\": \"<the single combined paragraph>\"}.\n"
            ),
            tools=[],
            workspace_inputs=["classification.md"],
            workspace_output="review-context.md",
            timeout_seconds=86_400,
        ),
        # Phase 4 — CR-04 Load Playbook (LLM_AGENT, max 10 rounds)
        # D-22-05: filter_tags=['playbook'] on search_documents calls.
        # D-22-06: JSON-structured per-category mapping in playbook-context.md.
        # D-22-07: context_quality='unfounded' when zero playbook docs found.
        # D-22-08: authority hierarchy — user-workspace > regulatory_intel > 3rd-party.
        # REVIEW #1 fix (22-REVIEWS.md): tools use list_playbook_documents (plan 22-02);
        #   the nonexistent tool that was listed before has been removed.
        PhaseDefinition(
            name="load-playbook",
            description=(
                "Discover playbook docs via list_playbook_documents; map 13 clause categories "
                "to relevant doc IDs; write playbook-context.md (D-22-06)."
            ),
            phase_type=PhaseType.LLM_AGENT,
            system_prompt_template=(
                "You are the playbook loader for a Contract Review run. Your job: discover playbook "
                "materials in the knowledge base and produce a structured JSON map from clause categories "
                "to relevant playbook document IDs.\n\n"
                "INPUTS (workspace files):\n"
                "  - classification.md : the contract type, parties, governing law, jurisdiction\n"
                "  - review-context.md : the user's stated perspective, deadline, focus areas\n\n"
                "TOOLS (curated for CR-04):\n"
                "  - list_playbook_documents(limit=50): START HERE. Returns all documents tagged 'playbook'\n"
                "    in the user's knowledge base as [{doc_id, title, summary}, ...]. Use this once at\n"
                "    the start to know what playbook surface exists.\n"
                "  - search_documents(query, filter_tags=['playbook'], top_k=8): D-22-05 — chunk-level\n"
                "    RAG inside the playbook scope. Use when you need passage-level grounding.\n"
                "  - search_documents_by_doc_ids(query, doc_ids, top_k=8): D-22-06 — chunk-level RAG\n"
                "    restricted to specific doc_ids returned by list_playbook_documents. Use sparingly\n"
                "    in CR-04; CR-06/CR-07 will rely on it heavily.\n\n"
                "PROCEDURE (max 10 rounds):\n"
                "  1. Call list_playbook_documents() ONCE to enumerate the playbook surface.\n"
                "     Skim each doc's summary; ignore docs that are clearly off-topic for this contract type.\n"
                "  2. For each of the 13 clause categories below, decide which subset of the listed playbook\n"
                "     docs cover that category. Use search_documents(filter_tags=['playbook']) sparingly when\n"
                "     a doc summary is ambiguous and you need a passage to verify category relevance.\n"
                "  3. AUTHORITY HIERARCHY (D-22-08): when multiple docs match, weight in order —\n"
                "     (a) user-workspace uploads first, (b) regulatory_intel docs second,\n"
                "     (c) general document library third. Use source_priority=1, 2, or 3 accordingly.\n"
                "  4. Build a clause_category_to_playbook dict. EVERY category must have a list (use\n"
                "     [] if no doc covers that category). All 13 categories must appear as keys.\n\n"
                "CLAUSE CATEGORIES (use exactly these strings as JSON keys):\n"
                "  Liability, Indemnification, IP, Data Protection, Confidentiality, Warranties,\n"
                "  Term/Termination, Governing Law, Insurance, Assignment, Force Majeure, Payment, Other\n\n"
                "EMPTY PLAYBOOK FALLBACK (D-22-07): if list_playbook_documents returns ZERO documents,\n"
                "set context_quality='unfounded' and emit empty playbook_docs [] + all 13 categories\n"
                "mapping to []. Add a notes field explaining the absence.\n\n"
                "OUTPUT: write a markdown file with header + JSON code block + prose summary, e.g.:\n"
                "  # Playbook Context\n"
                "  ```json\n"
                "  {\"playbook_docs\": [...], \"clause_category_to_playbook\": {...},\n"
                "   \"context_quality\": \"founded\", \"notes\": \"...\"}\n"
                "  ```\n"
                "  ## Notes\n"
                "  <free-form 2-3 sentences for downstream humans + sub-agents>\n\n"
                "Do NOT include the contract content in playbook-context.md. Only references to playbook docs."
            ),
            # REVIEW #1 (22-REVIEWS.md): three real tools for CR-04 (plan 22-02 + existing search_documents).
            tools=["list_playbook_documents", "search_documents", "search_documents_by_doc_ids"],
            workspace_inputs=["classification.md", "review-context.md"],
            workspace_output="playbook-context.md",
            timeout_seconds=600,
        ),
        # Phase 5 — CR-05 Clause Extraction (PROGRAMMATIC)  [plan 22-08]
        PhaseDefinition(
            name="extract-clauses",
            description=(
                "Chunk contract-text.md; per-chunk LLM extraction with egress_filter wrap (REVIEW #4); "
                "dedupe + write clauses.md + clauses.json sibling (ISSUE-04/ISSUE-25)."
            ),
            phase_type=PhaseType.PROGRAMMATIC,
            tools=[],
            workspace_inputs=["contract-text.md"],
            workspace_output="clauses.md",
            executor=_phase5_extract_clauses,
            timeout_seconds=600,
        ),
        # Phase 6 — CR-06 Risk Analysis (LLM_BATCH_AGENTS)  [plan 22-09]
        # REVIEW #1 (22-REVIEWS.md): tools=["search_documents_by_doc_ids"] ONLY (no legacy v1.0 tool aliases).
        # REVIEW #2 closed: sub-agents output JSON inside ```json``` fenced blocks; filter extracts
        #   via _parse_subagent_json_terminal from result.terminal.text (canonical merge shape).
        PhaseDefinition(
            name="risk-analysis",
            description=(
                "Per-clause risk assessment using playbook grounding. "
                "LLM_BATCH_AGENTS, batch_size=5. Sub-agents output ClauseRisk JSON "
                "inside ```json``` fenced blocks (REVIEW #2). "
                "REVIEW #1: tools=['search_documents_by_doc_ids'] only (no legacy v1.0 tool aliases)."
            ),
            phase_type=PhaseType.LLM_BATCH_AGENTS,
            system_prompt_template=(
                "You are assessing a single contract clause for risk against the user's playbook.\n\n"
                "INPUTS PER SUB-AGENT (one clause per agent):\n"
                "  - clause: the JSON object {clause_index, category, heading, text, position}\n"
                "  - playbook-context.md (workspace): includes clause_category_to_playbook map and\n"
                "    context_quality flag ('founded' or 'unfounded' per D-22-07).\n"
                "  - review-context.md (workspace): user's stated perspective, deadline, focus areas.\n\n"
                "TOOLS (curated — REVIEW #1):\n"
                "  - search_documents_by_doc_ids(query, doc_ids, top_k=8): D-22-06 — call this with\n"
                "    query=<clause.text> and doc_ids=<playbook_context.clause_category_to_playbook[clause.category]>\n"
                "    to retrieve precise grounding from the playbook docs that cover THIS category.\n\n"
                "EMPTY-PLAYBOOK FALLBACK (D-22-07):\n"
                "  If context_quality == 'unfounded' or doc_ids is empty for this clause's category:\n"
                "  assess against industry-standard legal expectations for the contract type.\n"
                "  Set grounding_doc_ids=[] and explicitly say 'unfounded — generic standards' in the rationale.\n\n"
                "GRADING RUBRIC:\n"
                "  GREEN  — clause matches playbook expectations or is benign for this party.\n"
                "  YELLOW — acceptable with caveats, or deviates from playbook but is negotiable.\n"
                "  RED    — materially adverse, conflicts with firm-line playbook position, or creates exposure.\n\n"
                "OUTPUT: respond with ONLY a JSON object inside a ```json``` code block (no prose around it).\n"
                "  ```json\n"
                "  {\"clause_index\": <int>, \"clause_category\": \"<one of 13>\", \"clause_heading\": \"<str>\",\n"
                "   \"risk_grade\": \"GREEN\"|\"YELLOW\"|\"RED\",\n"
                "   \"rationale\": \"<>=20 char explanation citing the playbook doc id(s) you grounded against>\",\n"
                "   \"alternative_language\": \"<for YELLOW/RED: a paragraph of suggested replacement; for GREEN: null>\",\n"
                "   \"grounding_doc_ids\": [\"<uuid-1>\", ...]}\n"
                "  ```\n"
                "Stay focused: ONE clause per sub-agent, ONE JSON object out, no surrounding prose."
            ),
            tools=["search_documents_by_doc_ids"],  # REVIEW #1: only this tool, no legacy v1.0 aliases
            workspace_inputs=["clauses.json", "playbook-context.md", "review-context.md"],
            workspace_output="risk-analysis.json",
            batch_size=5,
            timeout_seconds=1800,
        ),
        # Phase 7 — Filter Redline Candidates (PROGRAMMATIC — ISSUE-06 cost optimization)
        # Filters risk-analysis.json to YELLOW/RED clauses; writes redline-candidates.json.
        # This is an internal cost-optimization step, NOT a user-visible REQ.
        # CR-01..08 still map 1:1 to the 8 named user phases.
        # [plan 22-09 — REVIEW #2 + #3 implemented]
        PhaseDefinition(
            name="filter-redline-candidates",
            description=(
                "REVIEW #2 + #3: parse risk-analysis.json (engine batch merge — terminal.text), "
                "validate ClauseRisk, keep YELLOW/RED, JOIN original_text from clauses.json "
                "by clause_index; write redline-candidates.json for CR-07."
            ),
            phase_type=PhaseType.PROGRAMMATIC,
            tools=[],
            # REVIEW #3: filter needs BOTH risk-analysis.json AND clauses.json to join original_text
            workspace_inputs=["risk-analysis.json", "clauses.json"],
            workspace_output="redline-candidates.json",
            executor=_phase_filter_redline_candidates,
            timeout_seconds=30,
        ),
        # Phase 8 — CR-07 Redline Generation (LLM_BATCH_AGENTS)  [plan 22-09]
        # REVIEW #3 closed: prompt notes that original_text is provided by the filter join,
        #   so sub-agents do NOT need to re-fetch clause text.
        PhaseDefinition(
            name="redline-generation",
            description=(
                "Per-clause redline drafter for YELLOW/RED candidates (pre-filtered by phases[6]). "
                "LLM_BATCH_AGENTS, batch_size=5. REVIEW #3: original_text provided by filter join."
            ),
            phase_type=PhaseType.LLM_BATCH_AGENTS,
            system_prompt_template=(
                "You are drafting a precise redline for ONE problematic clause from the contract.\n\n"
                "FILTER: this phase processes ONLY redline candidates (YELLOW + RED, pre-filtered by\n"
                "the filter-redline-candidates PROGRAMMATIC step at phases[6]). GREEN clauses are\n"
                "already excluded.\n\n"
                "INPUTS PER SUB-AGENT (RedlineCandidate JSON object — REVIEW #3):\n"
                "  {clause_index, clause_category, clause_heading, original_text, risk_grade,\n"
                "   rationale, alternative_language, grounding_doc_ids}\n"
                "  Note: `original_text` is the VERBATIM clause body, joined from clauses.json by the\n"
                "  filter step. Use it directly — do NOT re-fetch clauses from the workspace.\n\n"
                "  Plus workspace files:\n"
                "  - playbook-context.md\n"
                "  - review-context.md\n\n"
                "TOOLS:\n"
                "  - search_documents_by_doc_ids — for re-grounding if alternative_language hint\n"
                "    needs refinement against specific playbook doc passages.\n\n"
                "PROCEDURE:\n"
                "  1. Read original_text + risk_grade + alternative_language hint from the input.\n"
                "  2. Draft a CONCRETE redline: original (echo input verbatim), proposed (precise\n"
                "     replacement), rationale (>=20 chars).\n"
                "  3. Provide UP TO 5 fallback_positions: ordered list of progressively-weaker concessions.\n"
                "  4. Style: plain English; preserve jurisdiction-appropriate legal phrasing.\n\n"
                "OUTPUT: ONLY a JSON object inside a ```json``` code block:\n"
                "  ```json\n"
                "  {\"clause_index\": <int>, \"clause_category\": \"<str>\",\n"
                "   \"original_text\": \"<verbatim from input>\",\n"
                "   \"proposed_text\": \"<verbatim replacement>\",\n"
                "   \"rationale\": \"<>=20 chars>\",\n"
                "   \"fallback_positions\": [\"<position 1>\", \"<position 2>\", ...]}\n"
                "  ```"
            ),
            tools=["search_documents_by_doc_ids"],
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
