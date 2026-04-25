"""First-name / surname token extraction (D-07 / ANON-05).

Phase 1's anonymization module (Plan 06) uses this set to reject any
Faker-generated surrogate whose name components overlap real ones from the
same redaction call. This prevents the PRD §7.5 surname-collision corruption
scenario where, e.g., a surrogate "Aaron Thompson DDS" would corrupt a real
"Margaret Thompson" elsewhere in the same input.

The function takes a list of REAL names already detected as PERSON entities
(by Presidio in the same call) and returns the union of their lower-cased
first-name and surname tokens. The caller compares each candidate Faker
surrogate's tokens against this set and rejects any overlap.

Uses `nameparser.HumanName` for tokenisation: it handles single-token names
("Bambang"), Western-style "First Last" ("Margaret Thompson"), and titled
forms ("Joko Wijaya, S.H."), pulling out `.first` and `.last` consistently.
For names where `nameparser` returns empty fields (e.g. mononyms), we fall
back to whitespace split and treat every token as both candidate first-name
and surname (lower-bound: never under-include a real token).

Examples:
    extract_name_tokens(["Bambang Sutrisno", "Sri Mulyani"])
        -> {"bambang", "sutrisno", "sri", "mulyani"}
    extract_name_tokens(["Bambang"])
        -> {"bambang"}
    extract_name_tokens(["Pak Joko Wijaya"])  # caller must strip honorific first
        -> {"joko", "wijaya"}  # if honorific was stripped
"""

from __future__ import annotations

from nameparser import HumanName


def extract_name_tokens(real_names: list[str]) -> set[str]:
    """Return the union of lower-cased first-name and surname tokens.

    Args:
        real_names: List of bare person names (honorifics already stripped
            by the caller via `honorifics.strip_honorific`). May contain
            empty strings or whitespace-only entries; these are skipped.

    Returns:
        Set of lower-cased tokens. Never None. Empty set if `real_names`
        contains no usable entries.
    """
    tokens: set[str] = set()
    for raw in real_names:
        bare = raw.strip()
        if not bare:
            continue
        parsed = HumanName(bare)
        first = parsed.first.strip().lower()
        last = parsed.last.strip().lower()
        if first:
            tokens.add(first)
        if last:
            tokens.add(last)
        # Fallback: if nameparser produced no tokens (mononyms, atypical input),
        # whitespace-split and add every alphabetic token. Conservative — better
        # to over-include than miss a real surname.
        if not first and not last:
            for piece in bare.split():
                clean = piece.strip(".,;").lower()
                if clean.isalpha() and len(clean) >= 2:
                    tokens.add(clean)
    return tokens
