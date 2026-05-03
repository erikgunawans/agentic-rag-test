"""Phase 20 / Plan 20-07 — Smoke-echo harness (D-16).

2-phase developer/admin diagnostic.
Phase 1 (programmatic): list workspace files, write metadata to echo.md.
Phase 2 (llm_single): summarize echo.md as JSON via Pydantic schema.

Stays in registry as developer/admin diagnostic; gated behind
settings.harness_smoke_enabled (default False in production, True in dev/test).
Purpose: provides the path Phase 20's verifier traverses to E2E-validate
gatekeeper → engine → phase_results → post-harness summary BEFORE Phase 22
lands the Contract Review domain harness.
"""
from __future__ import annotations

import logging

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


# --- Pydantic schema for Phase 2 structured output ---
class EchoSummary(BaseModel):
    echo_count: int = Field(..., ge=0, description="Number of files referenced in echo.md")
    summary: str = Field(..., min_length=1, max_length=2000, description="One-paragraph summary")


# --- Phase 1 executor: programmatic ---
async def _phase1_echo(
    *, inputs: dict[str, str], token: str, thread_id: str, harness_run_id: str
) -> dict:
    """List workspace files (uploads/), write echo.md with metadata."""
    ws = WorkspaceService(token=token)
    try:
        files = await ws.list_files(thread_id)
    except Exception as exc:
        logger.error(
            "smoke_echo phase1 list_files error harness_run=%s exc=%s",
            harness_run_id,
            exc,
            exc_info=True,
        )
        return {"error": "list_files_failed", "code": "WS_LIST_ERROR", "detail": str(exc)[:500]}

    # Filter to uploaded files only
    uploads = [f for f in files if f.get("source") == "upload"]
    lines = ["# Smoke Echo — Workspace Snapshot", ""]
    lines.append(f"Total uploaded files: {len(uploads)}")
    lines.append("")
    for f in uploads:
        lines.append(
            f"- `{f.get('file_path', '?')}` — {f.get('size_bytes', 0)} bytes ({f.get('mime_type', '?')})"
        )
    if not uploads:
        lines.append("- (no uploaded files in workspace)")
    echo_content = "\n".join(lines) + "\n"

    return {
        "content": echo_content,  # engine writes this to PhaseDefinition.workspace_output
        "echo_count": len(uploads),
        "files": [
            {"path": f.get("file_path"), "size": f.get("size_bytes", 0)} for f in uploads
        ],
    }


# --- Build the HarnessDefinition ---
SMOKE_ECHO = HarnessDefinition(
    name="smoke-echo",
    display_name="Smoke Echo",
    prerequisites=HarnessPrerequisites(
        requires_upload=True,
        upload_description="any DOCX or PDF file (used for engine smoke-test only — content not analyzed)",
        accepted_mime_types=[
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ],
        min_files=1,
        max_files=1,
        harness_intro=(
            "Hi! This is the Smoke Echo harness — a 2-phase diagnostic that confirms "
            "the harness engine is wired correctly end-to-end. Upload any DOCX or PDF "
            "and I'll list its metadata and summarize via JSON."
        ),
    ),
    phases=[
        PhaseDefinition(
            name="echo",
            description="List workspace upload metadata and write echo.md.",
            phase_type=PhaseType.PROGRAMMATIC,
            tools=[],
            workspace_inputs=[],  # programmatic phase reads workspace via service directly
            workspace_output="echo.md",
            executor=_phase1_echo,
            timeout_seconds=60,
        ),
        PhaseDefinition(
            name="summarize",
            description="Read echo.md and produce a JSON summary via Pydantic schema (HARN-05).",
            phase_type=PhaseType.LLM_SINGLE,
            system_prompt_template=(
                "You are summarizing a workspace snapshot from the Smoke Echo harness.\n"
                "Read the workspace input echo.md and produce a JSON object matching\n"
                "the EchoSummary schema:\n"
                "  - echo_count: integer >= 0 — count of files referenced\n"
                "  - summary: 1 short paragraph (<=500 chars) describing the workspace\n"
                "Return ONLY the JSON object — no prose."
            ),
            tools=[],
            workspace_inputs=["echo.md"],
            workspace_output="summary.json",
            output_schema=EchoSummary,
            timeout_seconds=120,
        ),
    ],
)


# --- Gated registration ---
if get_settings().harness_smoke_enabled:
    register(SMOKE_ECHO)
    logger.info("smoke_echo: registered (HARNESS_SMOKE_ENABLED=True)")
else:
    logger.info("smoke_echo: NOT registered (HARNESS_SMOKE_ENABLED=False)")
