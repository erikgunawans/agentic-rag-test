"""Indonesian honorific strip-and-reattach (D-02 / PII-04).

Improves NER accuracy on Indonesian person names by removing the honorific
prefix before Presidio sees the text, then reattaching it to the surrogate.

Recognized prefixes (case-insensitive, word-boundary-anchored):
    Pak, Bapak, Bu, Ibu, Sdr., Sdri.

Examples:
    strip_honorific("Pak Bambang")    -> ("Pak", "Bambang")
    strip_honorific("Sdri. Sri")       -> ("Sdri.", "Sri")
    strip_honorific("Bambang")         -> (None, "Bambang")
    reattach_honorific("Pak", "Joko Wijaya") -> "Pak Joko Wijaya"
    reattach_honorific(None, "Joko Wijaya")  -> "Joko Wijaya"

The function pair is symmetric: reattach_honorific(*strip_honorific(s))
is identity for any s that begins with a recognized prefix.
"""

from __future__ import annotations

import re

# D-02 verbatim list. Order matters for the alternation: longer prefixes first
# so "Bapak" matches before "Pak" would otherwise consume only the leading "Bap"
# (regex alternation is greedy left-to-right; "Pak" first would wrongly match
# the "Pak" inside "Pakaian").
_HONORIFICS = ("Bapak", "Pak", "Ibu", "Bu", "Sdri.", "Sdr.")

# Word-boundary at start; prefix; whitespace; remainder.
# The trailing literal `.` in Sdr./Sdri. is escaped via re.escape.
_HONORIFIC_RE = re.compile(
    r"^\s*(" + "|".join(re.escape(h) for h in _HONORIFICS) + r")\s+(.+)$",
    re.IGNORECASE,
)


def strip_honorific(name: str) -> tuple[str | None, str]:
    """Split `name` into (honorific, bare_name).

    Args:
        name: Possibly-prefixed person name.

    Returns:
        (honorific, bare_name) where honorific is the matched prefix in its
        ORIGINAL casing (e.g. "Pak" not "PAK"), or None if no prefix matched.
        bare_name is the remainder with leading/trailing whitespace stripped.
    """
    m = _HONORIFIC_RE.match(name)
    if not m:
        return None, name.strip()
    return m.group(1), m.group(2).strip()


def reattach_honorific(honorific: str | None, name: str) -> str:
    """Inverse of `strip_honorific`.

    Args:
        honorific: The prefix returned by `strip_honorific`, or None.
        name: A surrogate (or original) bare name.

    Returns:
        `"{honorific} {name}"` if honorific is not None, else `name`.
    """
    if honorific is None:
        return name
    return f"{honorific} {name}"
