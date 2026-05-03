"""Phase 20 / v1.3 — Gatekeeper LLM (GATE-01..05, D-05, D-06, D-07, SEC-04).

Stateless conversational agent that:
  1. Runs ONLY when settings.harness_enabled AND a harness is registered
     AND no active/terminal harness_runs exists for the thread (D-05).
  2. Streams plain text from a single LLM call (per-harness system prompt baked
     from HarnessPrerequisites + harness_intro).
  3. Buffers the full stream and matches r"\\s*\\[TRIGGER_HARNESS\\]\\s*$" at end-of-stream.
  4. On match → strips sentinel from final flush, persists user_msg + assistant_reply
     to messages with harness_mode=<harness_name>, calls harness_runs_service.start_run,
     and yields a transition event the chat.py SSE generator uses to invoke run_harness_engine.
  5. On no-match → flushes full buffer; persists turns to messages with harness_mode=<harness_name>.

Multi-turn dialogue (GATE-03): the gatekeeper is stateless from the LLM's perspective,
but the BACKEND reconstructs prior gatekeeper turns by reading messages WHERE harness_mode = <harness_name>
AND no harness_runs exists yet — those are the prior turns of the current gatekeeper conversation.

Security:
  - SEC-04: egress_filter wraps every cloud-LLM payload using parent ConversationRegistry
  - egress-blocked → emit a generic refusal assistant message; do NOT trigger harness
  - Sentinel never reaches the client (stripped end-of-stream before flush)
"""
from __future__ import annotations

import json
import logging
import re
from typing import AsyncIterator

from app.config import get_settings
from app.harnesses.types import HarnessDefinition
from app.services import harness_runs_service, audit_service
from app.services.openrouter_service import OpenRouterService
from app.services.redaction.egress import egress_filter
from app.database import get_supabase_authed_client

logger = logging.getLogger(__name__)
settings = get_settings()

SENTINEL = "[TRIGGER_HARNESS]"
SENTINEL_RE = re.compile(r"\s*\[TRIGGER_HARNESS\]\s*$")

# Sliding-window size: len(SENTINEL) + 8 for trailing whitespace tolerance
# 12 + 8 = 20 chars
_WINDOW_SIZE = len(SENTINEL) + 8

_EGRESS_REFUSAL = (
    "I cannot process this request — sensitive data detected. "
    "Please remove it and retry."
)


# ---------------------------------------------------------------------------
# System prompt builder (per-harness, deterministic — KV-cache friendly)
# ---------------------------------------------------------------------------

def build_system_prompt(harness: HarnessDefinition) -> str:
    prereq = harness.prerequisites
    if prereq.requires_upload:
        upload_block = (
            f"BEFORE STARTING, the user must upload: {prereq.upload_description}\n"
            f"Accepted file types: "
            f"{', '.join(prereq.accepted_mime_types) if prereq.accepted_mime_types else 'any'}\n"
            f"Min files: {prereq.min_files}, max files: {prereq.max_files}\n"
        )
    else:
        upload_block = "No file uploads required to begin.\n"

    return (
        f"You are the gatekeeper for the {harness.display_name} harness.\n\n"
        f"INTRO: {prereq.harness_intro}\n\n"
        f"{upload_block}\n"
        f"GUIDANCE:\n"
        f"- Greet the user, explain what the harness will do, and check prerequisites.\n"
        f"- If prerequisites are met (e.g. required files are present in workspace), "
        f"END YOUR FINAL MESSAGE WITH the literal token {SENTINEL}\n"
        f"- The token must appear at the very end of your last message — it will be "
        f"stripped before display.\n"
        f"- If prerequisites are NOT met, ask the user (e.g. 'Please upload your "
        f"contract first'). Do NOT emit {SENTINEL} until everything is in place.\n"
        f"- Stay concise: 1-3 short paragraphs per turn.\n"
        f"- Do not perform the harness work yourself — only gate the trigger.\n"
    )


# ---------------------------------------------------------------------------
# Multi-turn history loader (D-08)
# ---------------------------------------------------------------------------

async def load_gatekeeper_history(
    *, thread_id: str, harness_name: str, token: str
) -> list[dict]:
    """Load prior gatekeeper turns: messages WHERE harness_mode=<harness_name>.

    D-08: gatekeeper turns persisted with harness_mode=<harness_name>; reload-safe.
    Returns OpenAI-shaped list of {role, content}.
    """
    client = get_supabase_authed_client(token)
    result = (
        client.table("messages")
        .select("role, content, created_at")
        .eq("thread_id", thread_id)
        .eq("harness_mode", harness_name)
        .order("created_at", desc=False)
        .execute()
    )
    rows = result.data or []
    return [{"role": r["role"], "content": r["content"]} for r in rows]


# ---------------------------------------------------------------------------
# Persist a turn (helper)
# ---------------------------------------------------------------------------

async def _persist_message(
    *, thread_id: str, role: str, content: str, harness_name: str, token: str
) -> str | None:
    """Insert a message row with harness_mode tag. Returns the row id."""
    client = get_supabase_authed_client(token)
    result = client.table("messages").insert({
        "thread_id": thread_id,
        "role": role,
        "content": content,
        "harness_mode": harness_name,
    }).execute()
    rows = result.data or []
    return rows[0]["id"] if rows else None


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------

async def run_gatekeeper(
    *,
    harness: HarnessDefinition,
    thread_id: str,
    user_id: str,
    user_email: str,
    user_message: str,
    token: str,
    registry,                              # parent ConversationRegistry
) -> AsyncIterator[dict]:
    """Yield SSE-shaped dicts. Last yielded event signals chat.py whether to invoke run_harness_engine.

    Yielded shapes:
      {"type": "delta", "content": str}                          # streamed token chunks
      {"type": "gatekeeper_complete",
       "triggered": bool,
       "user_message_id": str|None,
       "assistant_message_id": str|None,
       "harness_run_id": str|None,
       "phase_count": int}                                       # W8 fix — len(harness.phases)
    """
    phase_count = len(harness.phases)

    # --- 1. Persist user message with harness_mode tag ---
    user_msg_id = await _persist_message(
        thread_id=thread_id,
        role="user",
        content=user_message,
        harness_name=harness.name,
        token=token,
    )

    # --- 2. Load prior gatekeeper history ---
    history = await load_gatekeeper_history(
        thread_id=thread_id,
        harness_name=harness.name,
        token=token,
    )
    # The history will now include the user message we just persisted,
    # so reconstruct messages from history (which already includes current turn).
    # Build messages: [system] + history (includes current user msg we just inserted)
    messages = [
        {"role": "system", "content": build_system_prompt(harness)},
        *history,
    ]

    # --- 4. SEC-04 egress pre-check ---
    if registry is not None:
        payload_str = json.dumps(messages, ensure_ascii=False)
        egress_result = egress_filter(payload_str, registry, None)
        if egress_result.tripped:
            # Persist refusal as assistant message
            asst_msg_id = await _persist_message(
                thread_id=thread_id,
                role="assistant",
                content=_EGRESS_REFUSAL,
                harness_name=harness.name,
                token=token,
            )
            # Audit log
            audit_service.log_action(
                user_id=user_id,
                user_email=user_email,
                action="gatekeeper_egress_blocked",
                resource_type="gatekeeper",
                resource_id=thread_id,
            )
            yield {"type": "delta", "content": _EGRESS_REFUSAL}
            yield {
                "type": "gatekeeper_complete",
                "triggered": False,
                "user_message_id": user_msg_id,
                "assistant_message_id": asst_msg_id,
                "harness_run_id": None,
                "phase_count": phase_count,
            }
            return

    # --- 5. Open streaming completion ---
    or_svc = OpenRouterService()
    buf: list[str] = []
    # Sliding-window buffer: holds back last _WINDOW_SIZE chars to detect sentinel
    # without streaming it to the client.
    held_back = ""

    try:
        stream = await or_svc.client.chat.completions.create(
            messages=messages,
            model=settings.openrouter_model,
            stream=True,
        )

        async for chunk in stream:
            if not chunk.choices:
                continue
            text = chunk.choices[0].delta.content or ""
            if not text:
                continue

            buf.append(text)
            # Add to held_back buffer
            held_back += text

            # Flush the prefix that is safely beyond the sentinel window
            if len(held_back) > _WINDOW_SIZE:
                safe_len = len(held_back) - _WINDOW_SIZE
                safe_prefix = held_back[:safe_len]
                held_back = held_back[safe_len:]
                yield {"type": "delta", "content": safe_prefix}

    except Exception as exc:
        logger.error(
            "gatekeeper: LLM stream failed thread_id=%s exc=%s",
            thread_id,
            exc,
            exc_info=True,
        )
        # Persist error message and return no-trigger
        err_content = "I encountered an error. Please try again."
        asst_msg_id = await _persist_message(
            thread_id=thread_id,
            role="assistant",
            content=err_content,
            harness_name=harness.name,
            token=token,
        )
        yield {"type": "delta", "content": err_content}
        yield {
            "type": "gatekeeper_complete",
            "triggered": False,
            "user_message_id": user_msg_id,
            "assistant_message_id": asst_msg_id,
            "harness_run_id": None,
            "phase_count": phase_count,
        }
        return

    # --- 6. Stream complete: check for sentinel in full buffer ---
    full = "".join(buf)
    match = SENTINEL_RE.search(full)

    if match:
        # Strip sentinel from the clean text
        clean = SENTINEL_RE.sub("", full)

        # Check if held_back tail contains the sentinel to avoid emitting it
        held_match = SENTINEL_RE.search(held_back)
        if held_match:
            # Strip sentinel from held_back and flush only clean portion
            clean_held = SENTINEL_RE.sub("", held_back)
            if clean_held:
                yield {"type": "delta", "content": clean_held}
        else:
            # Flush held_back as-is (sentinel was in an earlier chunk)
            if held_back:
                yield {"type": "delta", "content": held_back}

        # Persist clean assistant message
        asst_msg_id = await _persist_message(
            thread_id=thread_id,
            role="assistant",
            content=clean,
            harness_name=harness.name,
            token=token,
        )

        # Start the harness run
        run_id = await harness_runs_service.start_run(
            thread_id=thread_id,
            user_id=user_id,
            user_email=user_email,
            harness_type=harness.name,
            input_file_ids=None,
            token=token,
        )

        yield {
            "type": "gatekeeper_complete",
            "triggered": True,
            "user_message_id": user_msg_id,
            "assistant_message_id": asst_msg_id,
            "harness_run_id": run_id,
            "phase_count": phase_count,
        }
    else:
        # No sentinel — flush held_back tail as final delta
        if held_back:
            yield {"type": "delta", "content": held_back}

        # Persist full response as assistant message
        asst_msg_id = await _persist_message(
            thread_id=thread_id,
            role="assistant",
            content=full,
            harness_name=harness.name,
            token=token,
        )

        yield {
            "type": "gatekeeper_complete",
            "triggered": False,
            "user_message_id": user_msg_id,
            "assistant_message_id": asst_msg_id,
            "harness_run_id": None,
            "phase_count": phase_count,
        }
