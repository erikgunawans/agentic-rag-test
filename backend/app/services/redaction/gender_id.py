"""Indonesian first-name -> gender lookup (D-05).

Why this exists:
- gender-guesser (the English-biased fallback library) returns "unknown" for
  almost every Indonesian first name. Without this table, ANON-04
  (gender-matched surrogates) silently degrades to random selection.
- This is a SMALL hand-curated seed. Phase 4-6 may expand it from
  conversation-corpus data; never auto-extend without review.

Conventions:
- Keys are lower-cased, ASCII-folded first names (no honorifics, no surnames).
- Values are "M", "F", or "U" (ambiguous - explicit, never inferred).
- Lookup is case-insensitive; callers pass the raw first name unchanged.
"""

from __future__ import annotations

from typing import Literal

# fmt: off
_INDONESIAN_GENDER: dict[str, Literal["M", "F", "U"]] = {
    # Male - common Indonesian male first names
    "agus": "M", "ahmad": "M", "ali": "M", "andi": "M",
    "anton": "M", "arif": "M", "bambang": "M", "bayu": "M",
    "budi": "M", "darma": "M", "deny": "M", "dimas": "M",
    "djoko": "M", "edi": "M", "eko": "M", "endra": "M",
    "fajar": "M", "ferry": "M", "gunawan": "M", "hadi": "M",
    "harry": "M", "heru": "M", "iwan": "M", "joko": "M",
    "kurnia": "M", "made": "M", "muhammad": "M", "nugroho": "M",
    "rahmat": "M", "rizky": "M", "rudi": "M", "rudy": "M",
    "sigit": "M", "slamet": "M", "sulaiman": "M", "surya": "M",
    "sutrisno": "M", "teguh": "M", "wahyu": "M", "yusuf": "M",

    # Female - common Indonesian female first names
    "ani": "F", "anggi": "F", "anita": "F", "ayu": "F",
    "citra": "F", "dewi": "F", "diah": "F", "dian": "F",
    "dina": "F", "endah": "F", "eka": "F", "fitri": "F",
    "indah": "F", "intan": "F", "kartika": "F", "lina": "F",
    "lulu": "F", "maya": "F", "mega": "F", "novi": "F",
    "nur": "F", "puspa": "F", "putri": "F", "rina": "F",
    "ratna": "F", "siti": "F", "sri": "F", "susi": "F",
    "tari": "F", "wati": "F", "yanti": "F", "yuli": "F",

    # Ambiguous - names commonly used for both genders (explicit; D-05:
    # "ambiguous -> random")
    "kris": "U", "ade": "U", "mulia": "U", "indra": "U",
    "tika": "U", "rizki": "U",
}
# fmt: on


def lookup_gender(name: str) -> Literal["M", "F", "unknown"]:
    """Return the gender of an Indonesian first name.

    Args:
        name: A bare first name (no honorific, no surname). Casing ignored.

    Returns:
        "M" or "F" if the name is in the lookup table with a definite gender;
        "unknown" if the name is missing OR explicitly tagged "U" (ambiguous).
        D-05 specifies ambiguous originals -> random surrogate, so callers
        treat "unknown" as the "use random Faker gender" sentinel.
    """
    if not name:
        return "unknown"
    key = name.strip().lower()
    g = _INDONESIAN_GENDER.get(key)
    if g == "M":
        return "M"
    if g == "F":
        return "F"
    return "unknown"
