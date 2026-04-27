---
phase: 1
plan_number: 04
title: "Redaction helpers: errors module, UUID pre-mask filter, honorific strip-and-reattach, name-token extraction"
wave: 2
depends_on: [03]
requirements: [PII-04]
files_modified:
  - backend/app/services/redaction/errors.py
  - backend/app/services/redaction/uuid_filter.py
  - backend/app/services/redaction/honorifics.py
  - backend/app/services/redaction/name_extraction.py
autonomous: true
must_haves:
  - "`uuid_filter.apply_uuid_mask(text)` replaces every standard 8-4-4-4-12 hex UUID with a sentinel `<<UUID_N>>` token; `restore_uuids(text, sentinels)` reverses the operation perfectly (round-trip identity for any text without literal `<<UUID_` substring)."
  - "`uuid_filter.apply_uuid_mask` raises `RedactionError` (imported from `app.services.redaction.errors`) if the input already contains the literal substring `<<UUID_` (D-11 sentinel collision check)."
  - "`honorifics.strip_honorific(name)` recognises `Pak`, `Bapak`, `Bu`, `Ibu`, `Sdr.`, `Sdri.` (case-insensitive, word-boundary anchored) and returns `(honorific_or_None, bare_name)`; `reattach_honorific(honorific, surrogate)` rebuilds the full form."
  - "`name_extraction.extract_name_tokens(real_names: list[str]) -> set[str]` yields the lower-cased set of every first-name and surname token across the input list, using the `nameparser` library, for D-07 cross-check."
  - "`RedactionError` lives in `app.services.redaction.errors` (NOT `app.services.redaction.__init__`) so importing it does not trigger package initialisation (avoids the circular import chain `__init__ → redaction_service → anonymization → detection → uuid_filter → __init__`)."
---

<objective>
Build four small, independently-testable helper modules that the Wave 2 detection module (Plan 05) and Wave 3 anonymization module (Plan 06) compose. Each helper has a sharply focused responsibility:

1. **`errors.py`** — Hosts `RedactionError`. Sits at the bottom of the package's import graph: it imports nothing from elsewhere in the package, so any other module (including `uuid_filter`) can `from app.services.redaction.errors import RedactionError` without re-entering the package's `__init__`. This is the explicit fix for the circular-import chain that would otherwise raise `ImportError: cannot import name 'RedactionError'` once Plan 06 lands.

2. **`uuid_filter.py`** — D-09, D-10, D-11. Pre-mask UUIDs with sentinels so Presidio NER never sees them; restore after anonymization. This is the bulletproof solution to PII-04 (UUID false-positive filter).

3. **`honorifics.py`** — D-02. Strip Indonesian honorifics (`Pak`, `Bapak`, `Bu`, `Ibu`, `Sdr.`, `Sdri.`) before NER, reattach after surrogate generation. Drives PII-04's "Indonesian-name detection accuracy" sub-goal and preserves cultural register in surrogates ("Pak Bambang" -> "Pak Joko Wijaya").

4. **`name_extraction.py`** — D-07. Extract first-name and surname tokens from a list of detected real PERSON entities, using `nameparser` (added in Plan 03). Plan 06's anonymization module uses this set to reject any Faker-generated surrogate whose name components overlap real ones (the surname-collision corruption fix from PRD §7.5).

Purpose: Each helper is independently unit-testable, has zero coupling to Presidio or Faker, and ships in <80 lines. Composing them in Plan 06 keeps `RedactionService` linear. Co-locating `RedactionError` in its own module guarantees the circular-import chain stays broken.

Output: Four new files in `backend/app/services/redaction/`. (`__init__.py` is NOT modified by this plan — it stays minimal until Plan 06 carefully re-exports `RedactionError` only.)
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/01-detection-anonymization-foundation/01-CONTEXT.md
@backend/app/services/redaction/__init__.py
@backend/app/services/redaction/gender_id.py

CONTEXT.md decisions consumed in this plan:
- D-02: Honorific strip-and-reattach. Recognized prefixes: `Pak`, `Bapak`, `Bu`, `Ibu`, `Sdr.`, `Sdri.` (case-insensitive, word-boundary-anchored).
- D-07: Strict surname / first-name cross-check using `nameparser`.
- D-09: UUID pre-input mask + post-NER restore.
- D-10: Standard 8-4-4-4-12 hex UUID regex `[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}` (case-insensitive). Bare 32-hex and numeric IDs explicitly NOT matched.
- D-11: Sentinel collision check — fail fast with `RedactionError` if input already contains literal `<<UUID_`.
- D-12: Phase 1 operates on plain text only; no structured tool-arg awareness.

Public API targets:
```python
# errors.py
class RedactionError(Exception): ...

# uuid_filter.py
def apply_uuid_mask(text: str) -> tuple[str, dict[str, str]]: ...
def restore_uuids(text: str, sentinels: dict[str, str]) -> str: ...

# honorifics.py
def strip_honorific(name: str) -> tuple[str | None, str]: ...
def reattach_honorific(honorific: str | None, name: str) -> str: ...

# name_extraction.py
def extract_name_tokens(real_names: list[str]) -> set[str]: ...
```

Why `errors.py` and not the package `__init__.py`:
The full Phase 1 import chain is `redaction/__init__.py → redaction_service.py → anonymization.py → detection.py → uuid_filter.py → (RedactionError)`. If `RedactionError` lives in `__init__.py`, then `uuid_filter.py`'s import line `from app.services.redaction import RedactionError` re-enters the package mid-load, before `__init__.py` finishes evaluating its top-level re-exports — Python raises `ImportError: cannot import name 'RedactionError'`. Putting the class in a leaf module (`errors.py`) that imports nothing else from the package eliminates the cycle.
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: Create errors.py and uuid_filter.py</name>
  <files>backend/app/services/redaction/errors.py, backend/app/services/redaction/uuid_filter.py</files>
  <read_first>
    - backend/app/services/redaction/__init__.py (created in Plan 03 — `__all__` is currently empty; do NOT modify it in this task)
    - .planning/phases/01-detection-anonymization-foundation/01-CONTEXT.md (D-09, D-10, D-11 are the exact contract; verbatim regex string mandated)
    - .planning/codebase/CONVENTIONS.md (logger pattern, type hints, snake_case)
  </read_first>
  <action>
**Step A: Create `backend/app/services/redaction/errors.py`**

```python
"""Redaction error types.

Lives in its own leaf module so that other redaction modules can import
`RedactionError` without triggering package initialisation. This breaks the
otherwise-cyclic import chain:

    __init__.py
      └─ redaction_service.py (Plan 06)
          └─ anonymization.py
              └─ detection.py
                  └─ uuid_filter.py
                      └─ RedactionError  (← would re-enter __init__ if hosted there)

Plan 06's `__init__.py` may re-export this symbol (only this symbol) for
external consumers; internal modules MUST import directly from
`app.services.redaction.errors`.
"""

from __future__ import annotations


class RedactionError(Exception):
    """Raised on unrecoverable redaction state.

    Concrete cases (Phase 1):
    - D-11 sentinel collision: input already contains literal `<<UUID_`
      substring before pre-masking.
    """
```

**Step B: Create `backend/app/services/redaction/uuid_filter.py`** with content:

```python
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
```

Notes for the executor:
- Use `re.IGNORECASE` (D-10 explicit "case-insensitive").
- Sentinels increment from 0 in text order; tests rely on this.
- `restore_uuids` uses `str.replace` not regex, because sentinels are literal substrings; this is safe because sentinels never overlap each other.
- `uuid_filter.py` MUST import `from app.services.redaction.errors import RedactionError` (NOT `from app.services.redaction import RedactionError`). The leaf-module path is the contract that keeps the cycle broken.
- DO NOT modify `__init__.py` in this task. Plan 06 owns the (minimal) `__init__.py` re-export.
  </action>
  <verify>
    <automated>cd backend &amp;&amp; source venv/bin/activate &amp;&amp; python -c "from app.services.redaction.errors import RedactionError; from app.services.redaction.uuid_filter import apply_uuid_mask, restore_uuids; m, s = apply_uuid_mask('Doc 6ba7b810-9dad-11d1-80b4-00c04fd430c8 sent to Sri'); assert '<<UUID_0>>' in m; assert restore_uuids(m, s) == 'Doc 6ba7b810-9dad-11d1-80b4-00c04fd430c8 sent to Sri'; print('OK')"</automated>
    <automated>cd backend &amp;&amp; source venv/bin/activate &amp;&amp; python -c "from app.services.redaction.errors import RedactionError; from app.services.redaction.uuid_filter import apply_uuid_mask; raised=False
try: apply_uuid_mask('a string with &lt;&lt;UUID_ literal inside')
except RedactionError: raised=True
assert raised, 'D-11 sentinel collision check did not fire'; print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `test -f backend/app/services/redaction/errors.py` exits 0.
    - `test -f backend/app/services/redaction/uuid_filter.py` exits 0.
    - `grep -q "class RedactionError" backend/app/services/redaction/errors.py` exits 0.
    - `grep -q "from app.services.redaction.errors import RedactionError" backend/app/services/redaction/uuid_filter.py` exits 0 (D-11 / cycle-break invariant).
    - `grep -c "from app.services.redaction import RedactionError" backend/app/services/redaction/uuid_filter.py` returns 0 (NEVER use the package-init path).
    - `grep -q '\[0-9a-f\]{8}-\[0-9a-f\]{4}-\[0-9a-f\]{4}-\[0-9a-f\]{4}-\[0-9a-f\]{12}' backend/app/services/redaction/uuid_filter.py` exits 0 (D-10 verbatim regex).
    - `grep -q "re.IGNORECASE" backend/app/services/redaction/uuid_filter.py` exits 0.
    - `grep -q "_SENTINEL_PREFIX = \"<<UUID_\"" backend/app/services/redaction/uuid_filter.py` exits 0.
    - Round-trip identity: `python -c "from app.services.redaction.uuid_filter import apply_uuid_mask, restore_uuids; t='id 6ba7b810-9dad-11d1-80b4-00c04fd430c8 and 550e8400-e29b-41d4-a716-446655440000'; m,s=apply_uuid_mask(t); assert restore_uuids(m,s)==t and len(s)==2; print('OK')"` prints `OK`.
    - `python -c "from app.services.redaction.uuid_filter import apply_uuid_mask; from app.services.redaction.errors import RedactionError; raised=False\ntry: apply_uuid_mask('contains <<UUID_ literally')\nexcept RedactionError: raised=True\nassert raised; print('OK')"` prints `OK` (D-11 fail-fast).
    - `grep -nE "logger\.(debug|info|warning|error|exception).*\.(text|group|match)" backend/app/services/redaction/uuid_filter.py` returns 0 matches (D-18: never log real values).
  </acceptance_criteria>
  <done>errors.py and uuid_filter.py created; RedactionError importable from leaf module; UUID round-trip identity holds; D-11 sentinel collision raises RedactionError; package-init import path is NOT used (cycle stays broken).</done>
</task>

<task type="auto" tdd="false">
  <name>Task 2: Create honorifics.py (D-02 strip-and-reattach)</name>
  <files>backend/app/services/redaction/honorifics.py</files>
  <read_first>
    - .planning/phases/01-detection-anonymization-foundation/01-CONTEXT.md (D-02 names the exact prefix list and the case-insensitive / word-boundary requirement)
    - backend/app/services/redaction/uuid_filter.py (created in Task 1 — same module-shape conventions: top docstring referencing the relevant D-XX, `from __future__ import annotations`, leaf-module imports only)
    - backend/app/services/redaction/gender_id.py (Plan 03 — same lightweight helper-module pattern; reuse the docstring/imports style)
  </read_first>
  <action>
Create `backend/app/services/redaction/honorifics.py` with content:

```python
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
```

Notes for the executor:
- Honorific list ORDER matters in the regex (`Bapak` before `Pak`, `Sdri.` before `Sdr.`) — longest-match-first.
- `re.IGNORECASE` is mandatory (D-02 "case-insensitive").
- `re.escape` on each entry handles the literal `.` in `Sdr.` / `Sdri.`.
- Anchors: `^` at start, `\s+` between prefix and name. No `$` because we want the regex to consume the prefix only and return the trailing name as `group(2)`.
- DO NOT log the input or matched groups (D-18). The module imports nothing from logging.
- DO NOT import `RedactionError` here — this module never raises (a non-match returns `(None, name)`).
  </action>
  <verify>
    <automated>cd backend &amp;&amp; source venv/bin/activate &amp;&amp; python -c "from app.services.redaction.honorifics import strip_honorific, reattach_honorific
cases = [('Pak Bambang', ('Pak','Bambang')), ('Bapak Joko Wijaya', ('Bapak','Joko Wijaya')), ('Bu Sri', ('Bu','Sri')), ('Ibu Dewi', ('Ibu','Dewi')), ('Sdr. Andi', ('Sdr.','Andi')), ('Sdri. Putri', ('Sdri.','Putri')), ('Bambang', (None,'Bambang')), ('PAK BUDI', ('PAK','BUDI')), ('Pakaian Bekas', (None,'Pakaian Bekas'))]
for inp, exp in cases:
    got = strip_honorific(inp)
    assert got == exp, f'{inp!r} -> {got!r}, expected {exp!r}'
assert reattach_honorific('Pak', 'Joko Wijaya') == 'Pak Joko Wijaya'
assert reattach_honorific(None, 'Joko Wijaya') == 'Joko Wijaya'
print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `test -f backend/app/services/redaction/honorifics.py` exits 0.
    - `grep -q "def strip_honorific" backend/app/services/redaction/honorifics.py` exits 0.
    - `grep -q "def reattach_honorific" backend/app/services/redaction/honorifics.py` exits 0.
    - `grep -q "Bapak" backend/app/services/redaction/honorifics.py` exits 0 AND `grep -q "Sdri\." backend/app/services/redaction/honorifics.py` exits 0 (D-02 prefix list complete).
    - `grep -q "re.IGNORECASE" backend/app/services/redaction/honorifics.py` exits 0.
    - `python -c "from app.services.redaction.honorifics import strip_honorific; assert strip_honorific('Pak Bambang') == ('Pak','Bambang'); assert strip_honorific('Pakaian Bekas') == (None,'Pakaian Bekas')"` exits 0 (longest-match-first invariant; "Pak" must NOT match the prefix of "Pakaian").
    - `python -c "from app.services.redaction.honorifics import strip_honorific, reattach_honorific; h,n = strip_honorific('Sdri. Putri'); assert reattach_honorific(h,n) == 'Sdri. Putri'"` exits 0 (round-trip identity for prefixed names).
    - `grep -c "logger\\." backend/app/services/redaction/honorifics.py` returns 0 (no logging in this leaf helper; D-18 conservative).
  </acceptance_criteria>
  <done>honorifics.py created; strip/reattach pair handles all 6 D-02 prefixes case-insensitively; longest-match-first prevents "Pak" from consuming "Pakaian"; round-trip identity verified.</done>
</task>

<task type="auto" tdd="false">
  <name>Task 3: Create name_extraction.py (D-07 surname/first-name token set)</name>
  <files>backend/app/services/redaction/name_extraction.py</files>
  <read_first>
    - .planning/phases/01-detection-anonymization-foundation/01-CONTEXT.md (D-07: "strict surname / first-name cross-check using `nameparser`"; PRD §7.5 surname-collision-corruption scenario is the regression target)
    - backend/requirements.txt (Plan 03 added `nameparser>=1.1.3` — verify it's importable before writing the module)
    - backend/app/services/redaction/honorifics.py (Task 2 — same leaf-module conventions: top docstring, `from __future__ import annotations`, no logging, no logging-imports)
  </read_first>
  <action>
Create `backend/app/services/redaction/name_extraction.py` with content:

```python
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
```

Notes for the executor:
- Imports `from nameparser import HumanName` — `nameparser>=1.1.3` is in `backend/requirements.txt` from Plan 03 Task 1. If the import fails, Plan 03 didn't run; halt and report.
- Honorific stripping is the CALLER's responsibility (Plan 06's anonymization module passes names through `honorifics.strip_honorific` before reaching this module). Do not strip honorifics here; that would couple two unrelated concerns.
- Lower-casing happens INSIDE this module; callers compare against a lower-cased set so case mismatches never cause false negatives.
- Mononym fallback (`if not first and not last`) handles the common Indonesian single-name case ("Bambang", "Sukarno"). `nameparser` sometimes routes mononyms to `.last` only and sometimes to `.first` only depending on capitalisation heuristics; the fallback guarantees we never lose a token.
- DO NOT log the names (D-18 — these are real PII values).
- DO NOT raise on invalid input — return an empty set. Plan 06 will simply produce no overlap rejections in that case.
  </action>
  <verify>
    <automated>cd backend &amp;&amp; source venv/bin/activate &amp;&amp; python -c "from app.services.redaction.name_extraction import extract_name_tokens
got = extract_name_tokens(['Bambang Sutrisno', 'Sri Mulyani'])
assert got == {'bambang','sutrisno','sri','mulyani'}, got
got = extract_name_tokens(['Bambang'])
assert 'bambang' in got, got
got = extract_name_tokens(['Margaret Thompson', 'Aaron Thompson DDS'])
assert 'thompson' in got and 'margaret' in got and 'aaron' in got, got
got = extract_name_tokens([])
assert got == set(), got
got = extract_name_tokens(['', '   ', 'Joko Wijaya'])
assert got == {'joko','wijaya'}, got
print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `test -f backend/app/services/redaction/name_extraction.py` exits 0.
    - `grep -q "def extract_name_tokens" backend/app/services/redaction/name_extraction.py` exits 0.
    - `grep -q "from nameparser import HumanName" backend/app/services/redaction/name_extraction.py` exits 0.
    - `python -c "from app.services.redaction.name_extraction import extract_name_tokens; assert extract_name_tokens(['Bambang Sutrisno','Sri Mulyani']) == {'bambang','sutrisno','sri','mulyani'}"` exits 0.
    - `python -c "from app.services.redaction.name_extraction import extract_name_tokens; assert 'bambang' in extract_name_tokens(['Bambang'])"` exits 0 (mononym fallback).
    - `python -c "from app.services.redaction.name_extraction import extract_name_tokens; t = extract_name_tokens(['Margaret Thompson','Aaron Thompson DDS']); assert 'thompson' in t"` exits 0 (PRD §7.5 regression target — surname token shared across two real names is captured).
    - `python -c "from app.services.redaction.name_extraction import extract_name_tokens; assert extract_name_tokens([]) == set() and extract_name_tokens(['','  ']) == set()"` exits 0 (empty / whitespace input is safe).
    - `grep -c "logger\\." backend/app/services/redaction/name_extraction.py` returns 0 (D-18 — no logging of real names).
    - `grep -nE "raise " backend/app/services/redaction/name_extraction.py` returns 0 matches (the module never raises; empty input returns empty set).
  </acceptance_criteria>
  <done>name_extraction.py created; extract_name_tokens returns the lower-cased union of first-name and surname tokens via nameparser.HumanName with mononym fallback; PRD §7.5 surname-overlap regression target verified.</done>
</task>

</tasks>

<verification>
After all three tasks complete, run:
```bash
cd backend && source venv/bin/activate
python -c "from app.services.redaction.errors import RedactionError; print('errors OK')"
python -c "from app.services.redaction.uuid_filter import apply_uuid_mask, restore_uuids; m,s = apply_uuid_mask('id 6ba7b810-9dad-11d1-80b4-00c04fd430c8'); assert restore_uuids(m,s) == 'id 6ba7b810-9dad-11d1-80b4-00c04fd430c8'; print('uuid_filter OK')"
python -c "from app.services.redaction.honorifics import strip_honorific, reattach_honorific; h,n = strip_honorific('Pak Bambang'); assert (h,n) == ('Pak','Bambang') and reattach_honorific(h,n) == 'Pak Bambang'; print('honorifics OK')"
python -c "from app.services.redaction.name_extraction import extract_name_tokens; assert extract_name_tokens(['Bambang Sutrisno','Sri Mulyani']) == {'bambang','sutrisno','sri','mulyani'}; print('name_extraction OK')"
python -c "from app.main import app; print('app boot OK')"
```

Backend boot must remain clean — all four helper modules sit at the leaf of the redaction package's import graph and must not pull in `redaction/__init__.py` transitively (verified by the round-2 cycle-break invariant in Plan 06 Step B).
</verification>

<success_criteria>
1. `backend/app/services/redaction/errors.py` defines `RedactionError(Exception)` and is importable as `from app.services.redaction.errors import RedactionError` (NOT via the package init).
2. `backend/app/services/redaction/uuid_filter.py` provides `apply_uuid_mask(text)` (returns `(masked_text, sentinels)`) and `restore_uuids(text, sentinels)` with: D-10 verbatim regex, D-11 sentinel-collision fail-fast raising `RedactionError`, round-trip identity on inputs without `<<UUID_` literal substring.
3. `backend/app/services/redaction/honorifics.py` provides `strip_honorific(name)` and `reattach_honorific(honorific, name)` recognising D-02 prefixes (`Pak`, `Bapak`, `Bu`, `Ibu`, `Sdr.`, `Sdri.`) case-insensitively with word-boundary anchoring; longest-match-first prevents prefix-of-word false matches; round-trip identity for prefixed names.
4. `backend/app/services/redaction/name_extraction.py` provides `extract_name_tokens(real_names) -> set[str]` returning the lower-cased union of first-name and surname tokens via `nameparser.HumanName`, with mononym fallback to whitespace-split tokens; PRD §7.5 surname-overlap (Margaret Thompson / Aaron Thompson) regression target captured.
5. None of the four files import `from app.services.redaction import ...` — every cross-module reference uses the leaf module path (`from app.services.redaction.errors import RedactionError`). This is the cycle-break invariant that lets Plan 06 land without `ImportError`.
6. None of the four files import or call `logger` (D-18 — no logging in these leaf helpers; the only Phase 1 logging happens at the service composition layer in Plan 06).
</success_criteria>

<output>
After completion, create `.planning/phases/01-detection-anonymization-foundation/01-04-SUMMARY.md` capturing:
- The four file paths created and their final line counts.
- Confirmation that the cycle-break invariant holds: `grep -rn "from app.services.redaction import" backend/app/services/redaction/` returns ZERO matches inside the package.
- Whether `nameparser` chose `.first` vs `.last` for the mononym test cases (record actual behaviour for future reference; the fallback should still produce the right token set).
- Any honorific edge cases observed (e.g., did `Pakaian` correctly NOT match `Pak`? did `BAPAK BUDI` round-trip cleanly?).
- Confirmation that backend boot (`from app.main import app`) still works after the four new files exist.
</output>