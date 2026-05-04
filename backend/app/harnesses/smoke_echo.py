"""Phase 20 / Plan 20-07 — Smoke-echo harness (D-16).

Phase 21 / Plan 21-06 extension — 4-phase smoke harness exercising every
PhaseType supported by the engine (PROGRAMMATIC, LLM_SINGLE, LLM_HUMAN_INPUT,
LLM_BATCH_AGENTS). Phase 1 is dual-writer: it emits echo.md (engine-written)
PLUS test-items.md (executor-written) so Phase 4 has input.

Stays in registry as developer/admin diagnostic; gated behind
settings.harness_smoke_enabled (default False in production, True in dev/test).
Purpose: provides the path the Phase 21 verifier traverses to E2E-validate
the pause-resume-batch flow before Phase 22 lands the Contract Review domain
harness.
"""
from __future__ import annotations

import json
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


# --- Phase 21 / Plan 21-06: synthetic items the batch phase consumes ---
# Static developer-defined data; no user input path. Three items at batch size 2
# yields 2 batches: [items 0,1] then [item 2].
SYNTHETIC_BATCH_ITEMS: list[dict] = [
    {"index": 0, "label": "alpha"},
    {"index": 1, "label": "beta"},
    {"index": 2, "label": "gamma"},
]


# --- Phase 1 executor: programmatic ---
async def _phase1_echo(
    *, inputs: dict[str, str], token: str, thread_id: str, harness_run_id: str
) -> dict:
    """List workspace files (uploads/), write echo.md with metadata, AND seed
    test-items.md so Phase 4 (batch-process) has input."""
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

    # Phase 21 / Plan 21-06 — seed the batch input file. This is INDEPENDENT of
    # echo.md (which the engine writes from result["content"]); we must write
    # test-items.md ourselves because the engine only writes ONE workspace_output
    # per phase.
    try:
        await ws.write_text_file(
            thread_id,
            "test-items.md",
            json.dumps(SYNTHETIC_BATCH_ITEMS, ensure_ascii=False),
            source="harness",
        )
    except Exception as exc:
        logger.warning(
            "smoke_echo phase1 test-items.md write failed harness_run=%s: %s",
            harness_run_id,
            exc,
        )

    return {
        "content": echo_content,  # engine writes this to PhaseDefinition.workspace_output
        "echo_count": len(uploads),
        "files": [
            {"path": f.get("file_path"), "size": f.get("size_bytes", 0)} for f in uploads
        ],
        "items_written": len(SYNTHETIC_BATCH_ITEMS),
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
            "Hi! This is the Smoke Echo harness — a 4-phase diagnostic that confirms "
            "the harness engine is wired correctly end-to-end. Upload any DOCX or PDF "
            "and I'll list its metadata, summarize via JSON, ask you for a label, and "
            "process a small batch of synthetic items in parallel."
        ),
    ),
    phases=[
        PhaseDefinition(
            name="echo",
            description="List workspace upload metadata, write echo.md, and seed test-items.md.",
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
        # Phase 21 — Plan 21-02 LLM_HUMAN_INPUT exercise.
        PhaseDefinition(
            name="ask-label",
            description="Ask the user what label to attach to the echo result.",
            phase_type=PhaseType.LLM_HUMAN_INPUT,
            system_prompt_template=(
                "You are a friendly assistant. Generate ONE short clarifying question "
                "(under 30 words) asking what label the user wants on the echo result. "
                "Respond as a JSON object {\"question\": \"...\"}."
            ),
            tools=[],
            workspace_inputs=["echo.md"],
            workspace_output="test-answer.md",
            timeout_seconds=86_400,  # 24h pause budget
        ),
        # Phase 21 — Plan 21-03 LLM_BATCH_AGENTS exercise.
        PhaseDefinition(
            name="batch-process",
            description="Process each synthetic item in parallel — echo back its label.",
            phase_type=PhaseType.LLM_BATCH_AGENTS,
            system_prompt_template=(
                "You are a focused worker. Echo back the item's label exactly as given. "
                "Respond with the label string only."
            ),
            tools=[],
            workspace_inputs=["test-items.md"],
            workspace_output="test-batch.json",
            batch_size=2,  # 3 items / batch_size=2 → 2 batches: [0,1] + [2]
            timeout_seconds=600,
        ),
    ],
)


# --- Gated registration ---
if get_settings().harness_smoke_enabled:
    register(SMOKE_ECHO)
    logger.info("smoke_echo: registered (HARNESS_SMOKE_ENABLED=True)")
else:
    logger.info("smoke_echo: NOT registered (HARNESS_SMOKE_ENABLED=False)")
