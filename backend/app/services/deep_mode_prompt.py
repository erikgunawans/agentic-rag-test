"""Phase 17 / DEEP-05 + TODO-04 — Deep Mode system prompt builder.

Deterministic, KV-cache-friendly. No timestamps, no volatile state.
Todo state flows through write_todos/read_todos tools, NOT this prompt.

D-09 (CONTEXT.md): 5 deterministic sections appended to the base prompt:
  1. Planning instructions
  2. Recitation pattern (TODO-04)
  3. Sub-agent delegation (Phase 19 — task tool semantics)
  4. Asking the user (Phase 19 — ask_user tool semantics)
  5. Error recovery (Phase 19 — D-20 no-automatic-retry model)
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

Use the `task(description, context_files)` tool to delegate focused work to a sub-agent
with isolated context. The sub-agent shares your workspace (read+write) but has its own
message history. Use it for: scoped research, single-pass analysis, or any work where
isolating context would clarify the task. The sub-agent cannot recursively call task,
write_todos, or read_todos. Sub-agent failures are returned as structured tool errors
— your loop continues. Limit: 15 sub-agent rounds per delegation.

## Deep Mode — Asking the User

Use the `ask_user(question)` tool ONLY when you genuinely need user clarification to
proceed. The loop pauses; the user's next message is delivered as this tool's result,
verbatim. If their reply doesn't directly answer, you may call ask_user again or
proceed with what they said. Do not use for status updates or rhetorical pauses.

## Deep Mode — Error Recovery

When a tool call fails it returns a structured error result like
{"error": "...", "code": "...", "detail": "..."}. Read the error, then decide:
retry with different inputs, try an alternative tool, or escalate via ask_user.
There is no automatic retry. Every recovery decision is your choice and is visible
in the conversation transcript.
"""


def build_deep_mode_system_prompt(base_prompt: str) -> str:
    """Append 5 deterministic Deep Mode sections to the base system prompt.

    Deterministic: same input always produces same output (KV-cache stable).
    No timestamps, no volatile data. Todo state flows through tools, not here.

    Args:
        base_prompt: The base system prompt string.

    Returns:
        base_prompt (trailing whitespace stripped) + DEEP_MODE_SECTIONS.
    """
    return base_prompt.rstrip() + DEEP_MODE_SECTIONS
