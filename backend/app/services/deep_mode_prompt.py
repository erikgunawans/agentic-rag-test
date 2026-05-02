"""Phase 17 / DEEP-05 + TODO-04 — Deep Mode system prompt builder.

Deterministic, KV-cache-friendly. No timestamps, no volatile state.
Todo state flows through write_todos/read_todos tools, NOT this prompt.

D-09 (CONTEXT.md): 4 deterministic sections appended to the base prompt:
  1. Planning instructions
  2. Recitation pattern (TODO-04)
  3. Sub-agent delegation stub (Phase 19 placeholder)
  4. Ask-user stub (Phase 19 placeholder)
"""
from __future__ import annotations

DEEP_MODE_SECTIONS = """\

## Deep Mode — Planning

You can plan multi-step work via the write_todos and read_todos tools.
Use write_todos to set the FULL updated todo list at once (full-replacement semantic, max 50 items).
Each todo has content (the step) and status: pending, in_progress, or completed.
Set status to in_progress before starting a step; set it to completed when the step is done.

## Deep Mode — Recitation Pattern

After completing each step, call read_todos to confirm your plan and progress before
deciding the next action. This prevents drift during long sessions.

## Deep Mode — Sub-Agent Delegation

Sub-agent delegation tools (`task`) will be available in a future release.
For now, do all work in the main loop.

## Deep Mode — Asking the User

If you need clarification, the user will provide it in a follow-up message.
Do not pause mid-loop — finish your current plan or summarize and stop, then the user can reply.
"""


def build_deep_mode_system_prompt(base_prompt: str) -> str:
    """Append 4 deterministic Deep Mode sections to the base system prompt.

    Deterministic: same input always produces same output (KV-cache stable).
    No timestamps, no volatile data. Todo state flows through tools, not here.

    Args:
        base_prompt: The base system prompt string.

    Returns:
        base_prompt (trailing whitespace stripped) + DEEP_MODE_SECTIONS.
    """
    return base_prompt.rstrip() + DEEP_MODE_SECTIONS
