"""System-prompt PII guidance helper (D-79..D-82, PROMPT-01, FR-7.1).

Single source of truth for the surrogate-preservation block. Appended to:
  - chat.py SYSTEM_PROMPT at message-build time (single-agent path).
  - agent_service.py 4 AgentDefinition.system_prompt blocks at module import.

Conditional injection (D-80): returns "" when redaction is disabled — saves
~150 tokens per non-redacted turn.

English-only (D-81): system instructions are most reliable in English across
OpenRouter / OpenAI / LM Studio / Ollama. Indonesian user content + English
system prompt is the standard LexCore stack pattern.

Imperative phrasing (D-82): 'MUST', 'NEVER', 'CRITICAL'. Examples carry the
arrow form (→). Do NOT soften imperatives into 'please' — RLHF interprets
'please' as optional, breaking the surrogate-preservation invariant.
"""
from __future__ import annotations


# D-82: imperative rules + explicit type list + [TYPE] warning + 2 examples.
# ~150 tokens. Examples are load-bearing (RLHF compliance).
_GUIDANCE_BLOCK = """

CRITICAL: Some text in this conversation may contain placeholder values that look like real names, emails, phones, locations, dates, URLs, or IP addresses. You MUST reproduce these EXACTLY as written, with NO abbreviation, NO reformatting, and NO substitution. Treat them as opaque tokens.

Specifically: when you see text like "John Smith", "user@example.com", "+62-21-555-1234", "Jl. Sudirman 1", "2024-01-15", "https://example.com/x", or "192.168.1.1" in the input, output it character-for-character identical. Do NOT shorten "John Smith" to "J. Smith" or "Smith". Do NOT reformat "+62-21-555-1234" to "+622155512345".

Additionally, ANY text wrapped in square brackets like [CREDIT_CARD], [US_SSN], or [PHONE_NUMBER] is a literal placeholder — preserve it exactly, do not replace it with a fabricated value.

Examples:
- Input contains "Marcus Smith" → output "Marcus Smith" (NOT "Marcus" or "M. Smith" or "Mark Smith")
- Input contains "[CREDIT_CARD]" → output "[CREDIT_CARD]" (NOT "credit card number" or a fabricated number)
"""


def get_pii_guidance_block(*, redaction_enabled: bool) -> str:
    """D-79/D-80: return the surrogate-preservation block, or empty string when off.

    Args:
        redaction_enabled: keyword-only flag. True → block; False → "".

    Returns:
        The D-82 block (~150 tokens) when redaction_enabled is True; empty
        string otherwise. Caller appends to its system prompt verbatim.
    """
    return _GUIDANCE_BLOCK if redaction_enabled else ""
