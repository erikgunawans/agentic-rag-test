"""Phase 20 / v1.3 — Post-Harness Summary LLM (POST-01..05, D-09, D-10, SEC-04).

Streams a ~500-token summary of harness phase_results as a separate assistant message
immediately after harness_complete (D-09 inline pattern). NOT a callback on the
PhaseDefinition — the engine itself owns the summary; harness definitions own
post_execute for things like DOCX (Phase 22).

Truncation per D-10 / POST-05: deterministic, no recursive LLM step.
  - max_chars = 30,000 (total JSON representation of phase_results)
  - Under threshold → return full JSON unchanged
  - Over threshold → phases 1..N-2 → name + first 200 chars + truncation marker
  - Phases N-1 and N (last two) → full content
  - Most-recent phases (decision-relevant) preserved; older phases preview only.

SEC-04 / B4 invariant: this function MUST receive the SAME parent ConversationRegistry
that the gatekeeper and engine used. The wrapper at chat.py:_gatekeeper_stream_wrapper
builds the registry once via _get_or_build_conversation_registry and forwards the
same instance to gatekeeper, run_harness_engine, and summarize_harness_run.
"""
from __future__ import annotations

import json
import logging
from typing import AsyncIterator

from app.harnesses.types import HarnessDefinition
from app.services import audit_service
from app.services.openrouter_service import OpenRouterService
from app.services.redaction.egress import egress_filter
from app.database import get_supabase_authed_client

logger = logging.getLogger(__name__)

# Module-level singleton so tests can monkeypatch
# app.services.post_harness.openrouter_service.client.chat.completions.create
openrouter_service = OpenRouterService()

# ---------------------------------------------------------------------------
# Constants (D-10 / POST-05)
# ---------------------------------------------------------------------------

PHASE_RESULTS_MAX_CHARS = 30_000
PREVIEW_LEN = 200
TRUNCATION_MARKER = "...[truncated, see workspace artifact]"
SUMMARY_GUIDANCE = (
    "Be concise — 3-5 short paragraphs. Reference workspace files by path. "
    "Highlight key findings, risks, and recommended next steps. "
    "Do not repeat phase content verbatim — summarize."
)

_EGRESS_REFUSAL = (
    "I cannot generate the summary — sensitive data detected in the run results. "
    "Please contact an admin."
)


# ---------------------------------------------------------------------------
# Truncation helper (D-10 / POST-05)
# ---------------------------------------------------------------------------

def _truncate_phase_results(
    phase_results: dict,
    max_chars: int = PHASE_RESULTS_MAX_CHARS,
) -> str:
    """Per D-10 / POST-05: phases 1..N-2 → preview + marker; phases N-1 and N → full.

    Args:
        phase_results: dict keyed by stringified phase index (e.g. {"0": {...}, "1": {...}})
        max_chars: character threshold for the full JSON dump (default 30,000)

    Returns:
        String representation: full JSON if under threshold; otherwise
        a markdown-formatted summary with previews for early phases and
        full content for the last two phases.
    """
    if not phase_results:
        return "{}"

    # Fast path: compute total size as a single JSON dump
    as_json = json.dumps(phase_results, ensure_ascii=False)
    if len(as_json) <= max_chars:
        return as_json

    # Sort by integer phase index (keys are stringified ints)
    try:
        ordered = sorted(phase_results.items(), key=lambda kv: int(kv[0]))
    except ValueError:
        ordered = sorted(phase_results.items(), key=lambda kv: kv[0])

    # Determine the maximum phase index value
    if ordered:
        last_key = ordered[-1][0]
        try:
            n_max = int(last_key)
        except ValueError:
            n_max = len(ordered) - 1
    else:
        return "{}"

    out_lines: list[str] = []
    for idx_str, result in ordered:
        try:
            idx = int(idx_str)
        except ValueError:
            # Fallback: use positional index
            idx = next(
                (i for i, (k, _) in enumerate(ordered) if k == idx_str),
                0,
            )

        phase_name = result.get("phase_name", f"phase_{idx}") if isinstance(result, dict) else f"phase_{idx}"
        output = result.get("output", "") if isinstance(result, dict) else result
        output_str = output if isinstance(output, str) else json.dumps(output, ensure_ascii=False)

        # Last 2 phases (indices N-1 and N) → full content
        if idx >= n_max - 1:
            out_lines.append(f"## Phase {idx}: {phase_name}\n{output_str}")
        else:
            # Earlier phases → preview + truncation marker
            preview = output_str[:PREVIEW_LEN]
            out_lines.append(f"## Phase {idx}: {phase_name}\n{preview}{TRUNCATION_MARKER}")

    return "\n\n".join(out_lines)


# ---------------------------------------------------------------------------
# Persistence helper
# ---------------------------------------------------------------------------

async def _persist_summary(
    *,
    thread_id: str,
    content: str,
    harness_name: str,
    token: str,
) -> str | None:
    """Insert a summary assistant message row with harness_mode tag.

    Args:
        thread_id:   Thread UUID.
        content:     Full summary text.
        harness_name: Value for messages.harness_mode (D-04, POST-03).
        token:       JWT for RLS-scoped Supabase client.

    Returns:
        The new row's id, or None if insert failed.
    """
    client = get_supabase_authed_client(token)
    try:
        result = client.table("messages").insert({
            "thread_id": thread_id,
            "role": "assistant",
            "content": content,
            "harness_mode": harness_name,
        }).execute()
        return (result.data or [{}])[0].get("id")
    except Exception as exc:
        logger.error(
            "post_harness: persist failed thread=%s exc=%s",
            thread_id,
            exc,
            exc_info=True,
        )
        return None


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------

async def summarize_harness_run(
    *,
    harness: HarnessDefinition,
    harness_run: dict,          # the just-completed harness_runs row
    thread_id: str,
    user_id: str,
    user_email: str,
    token: str,
    registry,                   # parent ConversationRegistry — SEC-04 / B4
) -> AsyncIterator[dict]:
    """Yield SSE-shaped dicts for the inline post-harness summary (D-09).

    Yields:
      {"type": "delta", "content": str}                          — streamed tokens
      {"type": "summary_complete", "assistant_message_id": str | None}  — final event

    The caller (chat.py _gatekeeper_stream_wrapper) forward-pipes these as SSE
    events in the SAME SSE stream as harness_complete — no dead air for the user.

    SEC-04 / B4: `registry` is the parent ConversationRegistry.
      - When None (redaction off) → egress_filter is skipped (OFF-mode no-op contract,
        byte-identical to pre-Phase-20 behavior — SC#5 invariant).
      - When non-None → egress_filter is called with the SAME instance the gatekeeper
        + engine used (B4 invariant — guards against divergent registry state).
    """
    phase_results = harness_run.get("phase_results") or {}
    results_summary = _truncate_phase_results(phase_results)

    system_prompt = (
        f"You are summarizing a completed run of the {harness.display_name} harness.\n\n"
        f"PHASE RESULTS:\n{results_summary}\n\n"
        f"GUIDANCE: {SUMMARY_GUIDANCE}\n"
        f"The user has just seen the harness phases progress. "
        f"Now provide a clear, concise wrap-up.\n"
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Please provide the summary."},
    ]

    # SEC-04 / B4: egress filter pre-call with parent ConversationRegistry.
    # Only called when registry is non-None (PII redaction ON).
    if registry is not None:
        er = egress_filter(json.dumps(messages, ensure_ascii=False), registry, None)
        if er.tripped:
            logger.warning(
                "post_harness: egress_blocked harness_run_id=%s",
                harness_run.get("id"),
            )
            audit_service.log_action(
                user_id=user_id,
                user_email=user_email,
                action="post_harness_egress_blocked",
                resource_type="harness_runs",
                resource_id=harness_run.get("id", ""),
            )
            yield {"type": "delta", "content": _EGRESS_REFUSAL}
            yield {"type": "summary_complete", "assistant_message_id": None}
            return

    # Stream the summary from the LLM
    buf: list[str] = []
    try:
        stream = await openrouter_service.client.chat.completions.create(
            messages=messages,
            model=openrouter_service.model,
            stream=True,
        )
        async for chunk in stream:
            delta = (
                chunk.choices[0].delta.content
                if chunk.choices and chunk.choices[0].delta
                else None
            )
            if not delta:
                continue
            buf.append(delta)
            yield {"type": "delta", "content": delta}
    except Exception as exc:
        logger.error(
            "post_harness: stream error harness_run_id=%s exc=%s",
            harness_run.get("id"),
            exc,
            exc_info=True,
        )
        err_msg = "Summary generation failed. The harness results are saved in the workspace."
        buf.append(err_msg)
        yield {"type": "delta", "content": err_msg}

    full = "".join(buf)
    msg_id = await _persist_summary(
        thread_id=thread_id,
        content=full,
        harness_name=harness.name,
        token=token,
    )
    yield {"type": "summary_complete", "assistant_message_id": msg_id}
