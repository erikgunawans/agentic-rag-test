"""Indonesian-aware nickname → canonical first-name lookup (D-46, RESOLVE-02).

Why this exists:
- PRD FR-4.2 sub-surrogate derivation requires merging "Danny" into the same
  cluster as "Daniel"; an embedded Python dict gives O(1) lookup with zero
  runtime cost beyond the import.
- Indonesian-first coverage; small English block for completeness.

Conventions (mirror gender_id.py):
- Keys are lower-cased nicknames (no honorifics).
- Values are the canonical first name (lower-cased).
- Lookup is case-insensitive via the lookup_nickname() helper which casefolds.
- When a nickname has multiple plausible canonicals (rare; e.g., "Iwan"),
  the dict picks the FIRST match deterministically (Python dict-insertion order)
  and callers may log the ambiguity at DEBUG (D-46).
"""
from __future__ import annotations

# fmt: off
_INDONESIAN_NICKNAMES: dict[str, str] = {
    # Indonesian nicknames (Indonesian-first coverage per D-46)
    "bambs": "bambang",
    "bams": "bambang",
    "yoyok": "joko",
    "joko": "joko",
    "tini": "kartini",
    "wati": "watini",
    "iwan": "setiawan",
    "ucup": "yusuf",
    "udin": "saifuddin",
    "anto": "haryanto",
    "agus": "agustinus",
    "didi": "didik",
    "eko": "eko",
    "lia": "amalia",
    "rini": "rina",
    "yanti": "yantini",
    "yuli": "yuliana",
    "indra": "indra",
    "ayu": "ayu",
    "hari": "hariyanto",
    "har": "hariyanto",
    "tono": "sutono",
    "dik": "didik",
    "panji": "panji",
    "pandji": "panji",

    # English nicknames (small block for completeness — D-46)
    "danny": "daniel",
    "dan": "daniel",
    "bob": "robert",
    "rob": "robert",
    "robbie": "robert",
    "bill": "william",
    "billy": "william",
    "will": "william",
    "tom": "thomas",
    "tommy": "thomas",
    "mike": "michael",
    "mikey": "michael",
    "jim": "james",
    "jimmy": "james",
    "kate": "katherine",
    "katie": "katherine",
    "liz": "elizabeth",
    "beth": "elizabeth",
    "betty": "elizabeth",
    "jen": "jennifer",
    "jenny": "jennifer",
    "alex": "alexander",
    "andy": "andrew",
    "drew": "andrew",
    "tony": "anthony",
    "chris": "christopher",
    "joe": "joseph",
    "joey": "joseph",
}
# fmt: on


def lookup_nickname(nickname: str) -> str | None:
    """Return the canonical first name for a nickname, or None if absent.

    Lookup is case-insensitive (this function casefolds). On ambiguity the
    dict already encodes a deterministic first-match via insertion order;
    callers may log at DEBUG when a nickname maps multiple plausible canonicals
    (D-46). This module stays pure — no logging here.
    """
    return _INDONESIAN_NICKNAMES.get(nickname.casefold())
