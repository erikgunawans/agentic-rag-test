"""UUID pre-mask filter (D-09 / D-10 / D-11 / PII-04).

Strategy:
1. Pre-input mask: regex-find every standard 8-4-4-4-12 hex UUID in the input,
   replace each with a sentinel token <<UUID_N>>.
2. NER runs on the masked text (Presidio cannot touch UUIDs).
3. Post-anonymization, restore each sentinel back to the original UUID string.

D-10: only standard 8-4-4-4-12 hex with hyphens (case-insensitive). Bare 32-hex
and numeric IDs are NOT masked - they should be redacted by Presidio when they
look like phone numbers, account numbers, etc.

D-11: if the input already contains `<<UUID_`, raise RedactionError - we cannot
guarantee correctness if a real document quotes our sentinel format.
"""

from __future__ import annotations

import re

from app.services.redaction.errors import RedactionError

# D-10 verbatim: standard UUIDv4 8-4-4-4-12 hex, case-insensitive.
_UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)

# D-11 sentinel collision detector.
_SENTINEL_PREFIX = "<<UUID_"


def apply_uuid_mask(text: str) -> tuple[str, dict[str, str]]:
    """Replace UUIDs in `text` with sentinel tokens.

    Args:
        text: Raw input. Must NOT already contain the literal substring
            "<<UUID_" or RedactionError is raised (D-11).

    Returns:
        (masked_text, sentinels) where `sentinels` maps each
        sentinel token (`<<UUID_0>>`, `<<UUID_1>>`, ...) to the
        original UUID string at that position. Insertion order matches
        text order.
    """
    if _SENTINEL_PREFIX in text:
        raise RedactionError(
            "Input contains the reserved sentinel prefix '<<UUID_'. "
            "Refusing to mask to avoid silent corruption (D-11)."
        )

    sentinels: dict[str, str] = {}

    def _replace(match: re.Match[str]) -> str:
        token = f"<<UUID_{len(sentinels)}>>"
        sentinels[token] = match.group(0)
        return token

    masked = _UUID_RE.sub(_replace, text)
    return masked, sentinels


def restore_uuids(text: str, sentinels: dict[str, str]) -> str:
    """Reverse `apply_uuid_mask`.

    Args:
        text: Possibly-anonymized text containing sentinel tokens.
        sentinels: The mapping produced by `apply_uuid_mask`.

    Returns:
        Text with every `<<UUID_N>>` sentinel replaced by its original UUID.
    """
    if not sentinels:
        return text
    out = text
    for token, original in sentinels.items():
        out = out.replace(token, original)
    return out
