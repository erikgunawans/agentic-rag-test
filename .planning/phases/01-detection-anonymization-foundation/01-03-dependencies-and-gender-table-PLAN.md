---
phase: 1
plan_number: 03
title: "Dependencies install + Indonesian gender lookup table seed (gender_id.py) + Railway spaCy model bootstrap"
wave: 1
depends_on: []
requirements: [PII-01, ANON-04]
files_modified:
  - backend/requirements.txt
  - backend/app/services/redaction/__init__.py
  - backend/app/services/redaction/gender_id.py
  - backend/Procfile
autonomous: true
must_haves:
  - "Backend `pip install -r requirements.txt` succeeds with the new redaction packages on Python 3.14 (Railway runtime parity)."
  - "spaCy model `xx_ent_wiki_sm` downloads successfully via `python -m spacy download xx_ent_wiki_sm` (wired into the Railway release hook via `backend/Procfile`)."
  - "`gender_id.py` exports `lookup_gender(name: str) -> Literal['M', 'F', 'unknown']` seeded with at least 60 Indonesian first names spanning M/F/ambiguous (D-05)."
  - "`pytest>=8` and `pytest-asyncio>=0.24.0` are present in requirements.txt so Plan 07's async test suite can run."
---

<objective>
Lay the foundational dependencies, Indonesian gender-detection helper, AND Railway build hook that downstream Wave 2 plans (Detection module, Anonymization module) and Wave 4 (pytest suite) require to function. Four outputs:

1. Append the 8 new redaction packages from CONTEXT.md canonical_refs ("Phase 1 adds: presidio-analyzer, presidio-anonymizer, spacy, faker, gender-guesser, nameparser, rapidfuzz, langfuse") plus the test-tooling pair (`pytest>=8`, `pytest-asyncio>=0.24.0`) to `backend/requirements.txt` with version pins that work on Python 3.14 (Railway runtime).

2. Create `backend/app/services/redaction/gender_id.py` — the hand-curated Indonesian first-name to gender lookup table that D-05 mandates because `gender-guesser` is English-biased and unreliable on Indonesian names. Establish the `backend/app/services/redaction/` sub-package layout (D-13).

3. Create `backend/Procfile` with a `release` hook that runs `python -m spacy download xx_ent_wiki_sm` so the multilingual NER model is present at first request on Railway.

Purpose: Without these dependencies installed, no Wave 2 task can `import presidio_analyzer` or `import faker`. Without `pytest-asyncio`, Plan 07's async suite cannot execute. Without `gender_id.py`, ANON-04 cannot work for Indonesian names. Without the spaCy model bootstrap, Plan 06's lifespan warm-up fails on Railway with `OSError: [E050] Can't find model 'xx_ent_wiki_sm'`.

Output: Updated `requirements.txt`, new `redaction/` sub-package with `__init__.py` + `gender_id.py`, new `backend/Procfile`. Sub-package is the seed for Wave 2's `honorifics.py`, `uuid_filter.py`, and Wave 3's `redaction_service.py`.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/phases/01-detection-anonymization-foundation/01-CONTEXT.md
@backend/requirements.txt

Existing requirements.txt is 13 lines: fastapi, uvicorn, supabase, openai, pydantic-settings, python-dotenv, langsmith, httpx, python-multipart, pymupdf, tiktoken, python-docx, beautifulsoup4. Append-only edit.

Target sub-package layout (D-13):
- `backend/app/services/redaction/__init__.py` — this plan
- `backend/app/services/redaction/gender_id.py` — this plan
- `backend/app/services/redaction/honorifics.py` — Plan 04
- `backend/app/services/redaction/uuid_filter.py` — Plan 04
- `backend/app/services/redaction/name_extraction.py` — Plan 04
- `backend/app/services/redaction/errors.py` — Plan 04 (`RedactionError` lives here to avoid circular imports)
- `backend/app/services/redaction/detection.py` — Plan 05
- `backend/app/services/redaction/anonymization.py` — Plan 06

Public API of `gender_id.py`: a single function `lookup_gender(name: str) -> Literal["M", "F", "unknown"]`.

Railway deploy mechanism (per quick grep at planning time): no `railway.json`, no `nixpacks.toml`, no existing `Procfile` in repo root. Railway defaults to its Python builder. Adding `backend/Procfile` with explicit `release` and `web` processes is the simplest, most explicit path; the Railway Python builder honours Procfiles automatically.
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: Append redaction + test dependencies to requirements.txt</name>
  <files>backend/requirements.txt</files>
  <read_first>
    - backend/requirements.txt (current 13-line manifest — append-only edit)
    - .planning/phases/01-detection-anonymization-foundation/01-CONTEXT.md (canonical_refs section names exactly the 8 redaction packages: presidio-analyzer, presidio-anonymizer, spacy, faker, gender-guesser, nameparser, rapidfuzz, langfuse)
  </read_first>
  <action>
Append a new section to `backend/requirements.txt` containing exactly these lines (in this order, with version pins compatible with Python 3.14):

```
# PII Redaction (milestone v1.0 — Phase 1)
presidio-analyzer>=2.2.355
presidio-anonymizer>=2.2.355
spacy>=3.7.0,<4.0.0
faker>=30.0.0
gender-guesser>=0.4.0
nameparser>=1.1.3
rapidfuzz>=3.10.0
langfuse>=2.50.0

# Test tooling (Plan 07 async pytest suite)
pytest>=8.0.0
pytest-asyncio>=0.24.0
```

Notes for the executor:
- `presidio-analyzer` and `presidio-anonymizer` are sibling packages from Microsoft Presidio; both required (PII-01, ANON-01).
- `spacy>=3.7.0,<4.0.0` — Presidio 2.2.x is incompatible with spaCy 4.x as of this plan's date. Pin upper bound.
- `faker>=30.0.0` — provides the `id_ID` locale for D-04.
- `gender-guesser` is the English-fallback engine; the Indonesian lookup table in Task 2 of this plan is the primary path.
- `nameparser` — used in Plan 04 for surname / first-name token extraction (D-07 cross-check).
- `rapidfuzz` — Phase 4 Jaro-Winkler dependency; CONTEXT.md `<canonical_refs>` lists it now to bundle install in one Railway redeploy. Phase 1 ships it but does not yet use it.
- `langfuse` — D-17 ("Phase 1 ships both langsmith and langfuse adapters"). Plan 01's `tracing_service.py` imports it inside the langfuse branch.
- `pytest>=8.0.0` — explicit pin so Plan 07 can rely on pytest's modern collection / fixture semantics regardless of what was installed transitively before.
- `pytest-asyncio>=0.24.0` — Plan 07 declares `pytestmark = pytest.mark.asyncio` and writes async tests; without this package those tests are silently skipped or fail with "async def function and no async plugin installed".

Do NOT modify the existing 13 lines. They stay at their current pins.

After editing, install locally to validate:
```bash
cd backend && source venv/bin/activate && pip install -r requirements.txt
python -m spacy download xx_ent_wiki_sm
```

If the spaCy model download fails on the local machine (network firewall etc.), the executor must record the failure in the SUMMARY but should NOT fail this task — the model is required at deploy time on Railway, and Task 3 wires the Railway release hook to download it there.
  </action>
  <verify>
    <automated>cd backend &amp;&amp; source venv/bin/activate &amp;&amp; pip install -r requirements.txt &amp;&amp; python -c "import presidio_analyzer, presidio_anonymizer, spacy, faker, gender_guesser, nameparser, rapidfuzz, pytest, pytest_asyncio; print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "presidio-analyzer" backend/requirements.txt` returns 1.
    - `grep -c "presidio-anonymizer" backend/requirements.txt` returns 1.
    - `grep -c "^spacy" backend/requirements.txt` returns 1.
    - `grep -c "^faker" backend/requirements.txt` returns 1.
    - `grep -c "gender-guesser" backend/requirements.txt` returns 1.
    - `grep -c "nameparser" backend/requirements.txt` returns 1.
    - `grep -c "rapidfuzz" backend/requirements.txt` returns 1.
    - `grep -c "^langfuse" backend/requirements.txt` returns 1.
    - `grep -c "^pytest>" backend/requirements.txt` returns 1.
    - `grep -c "^pytest-asyncio" backend/requirements.txt` returns 1.
    - `cd backend && source venv/bin/activate && pip install -r requirements.txt` exits 0.
    - `cd backend && source venv/bin/activate && python -c "import presidio_analyzer, presidio_anonymizer, spacy, faker, gender_guesser, nameparser, rapidfuzz, langfuse, pytest, pytest_asyncio; print('OK')"` exits 0 and prints OK.
    - `cd backend && source venv/bin/activate && python -c "from faker import Faker; f = Faker('id_ID'); print(f.name())"` exits 0 and prints a non-empty Indonesian name.
    - The original 13 dependency lines are still present in `requirements.txt` (unchanged).
  </acceptance_criteria>
  <done>requirements.txt extended with 8 new redaction dependencies + pytest/pytest-asyncio; all importable in the local venv; Faker `id_ID` locale verified.</done>
</task>

<task type="auto" tdd="false">
  <name>Task 2: Create redaction sub-package skeleton + Indonesian gender lookup table</name>
  <files>backend/app/services/redaction/__init__.py, backend/app/services/redaction/gender_id.py</files>
  <read_first>
    - .planning/phases/01-detection-anonymization-foundation/01-CONTEXT.md (D-05 mandates the Indonesian lookup table seeded with common names; D-13 establishes the sub-package layout)
    - .planning/codebase/CONVENTIONS.md (project Python conventions — type hints on every function, snake_case, double quotes, modern `str | None` union syntax)
    - backend/app/services/openrouter_service.py (sample existing service for the docstring + logger pattern)
  </read_first>
  <action>
File 1: `backend/app/services/redaction/__init__.py`

Create with content:
```python
"""Redaction sub-package.

Phase 1 milestone v1.0 — Detection & Anonymization Foundation.
See .planning/phases/01-detection-anonymization-foundation/01-CONTEXT.md for the
locked architectural decisions (D-01..D-20) that shape this module.

Public surface (after all Phase 1 plans land):
    from app.services.redaction import RedactionError
    from app.services.redaction_service import (
        RedactionResult, RedactionService, get_redaction_service,
    )

Note: To avoid the circular import chain
    __init__.py → redaction_service.py → anonymization.py → detection.py →
    uuid_filter.py → __init__.py
this package's `__init__.py` re-exports ONLY `RedactionError`. The service
classes live in `app.services.redaction_service` and must be imported from
that module directly.
"""

from __future__ import annotations

# Re-exports populated as Wave 2 / Wave 3 plans land. Keep this minimal.
# Plan 04 will create errors.py and re-export RedactionError below.

__all__: list[str] = []
```

File 2: `backend/app/services/redaction/gender_id.py`

Create with content (the lookup table itself is the substance):

```python
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
```

Counts: 40 male + 32 female + 6 ambiguous = 78 entries (exceeds the 60-minimum from must_haves).

Do NOT add any test fixtures, mocks, or imports beyond `typing.Literal` and `__future__.annotations`. The table is data; Plan 06's RedactionService imports `lookup_gender` and calls it before generating Faker person surrogates.
  </action>
  <verify>
    <automated>cd backend &amp;&amp; source venv/bin/activate &amp;&amp; python -c "from app.services.redaction.gender_id import lookup_gender; assert lookup_gender('Bambang') == 'M'; assert lookup_gender('Sri') == 'F'; assert lookup_gender('Kris') == 'unknown'; assert lookup_gender('NotARealName') == 'unknown'; assert lookup_gender('BUDI') == 'M'; print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `backend/app/services/redaction/__init__.py` exists.
    - `backend/app/services/redaction/gender_id.py` exists.
    - `grep -n "def lookup_gender" backend/app/services/redaction/gender_id.py` returns at least 1 match.
    - `cd backend && source venv/bin/activate && python -c "from app.services.redaction.gender_id import _INDONESIAN_GENDER as t; m=sum(1 for v in t.values() if v=='M'); f=sum(1 for v in t.values() if v=='F'); u=sum(1 for v in t.values() if v=='U'); assert m>=40 and f>=32 and u>=6, f'M={m} F={f} U={u}'; print(f'OK M={m} F={f} U={u}')"` exits 0 (behavioural count check on the dict itself; immune to seed-formatting choices that group multiple entries per line).
    - `cd backend && source venv/bin/activate && python -c "from app.services.redaction.gender_id import lookup_gender; assert lookup_gender('Bambang') == 'M'; assert lookup_gender('Sri') == 'F'; assert lookup_gender('Kris') == 'unknown'; assert lookup_gender('') == 'unknown'; print('OK')"` exits 0 and prints OK.
    - `cd backend && source venv/bin/activate && python -c "from app.main import app; print('OK')"` exits 0 (sub-package registration does not break import graph).
  </acceptance_criteria>
  <done>redaction/ sub-package created with __init__.py + gender_id.py; lookup_gender is callable, case-insensitive, and returns the correct M/F/unknown values for the seeded names.</done>
</task>

<task type="auto" tdd="false">
  <name>Task 3: Add Railway Procfile so spaCy xx_ent_wiki_sm downloads on every deploy</name>
  <files>backend/Procfile</files>
  <read_first>
    - Repo root listing — confirm there is NO existing `railway.json`, `nixpacks.toml`, `railway.toml`, or `Procfile` in the repo root or `backend/`. The deploy currently uses Railway's default Python builder.
    - .planning/phases/01-detection-anonymization-foundation/01-CONTEXT.md (D-01 — `xx_ent_wiki_sm` is the multilingual model fed into Presidio)
    - backend/app/main.py (current uvicorn entry point used by Railway)
  </read_first>
  <action>
The PRD requires the multilingual spaCy model `xx_ent_wiki_sm` at runtime. It is NOT installable via pip — it must be downloaded with `python -m spacy download xx_ent_wiki_sm` after pip install. Without a release hook, Plan 06's lifespan warm-up will fail on Railway with `OSError: [E050] Can't find model 'xx_ent_wiki_sm'`.

Create `backend/Procfile` with EXACTLY this content (two lines, no trailing blank line is required but harmless):

```
release: python -m spacy download xx_ent_wiki_sm
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Why Procfile (and not `railway.json` or `nixpacks.toml`):
- The repo currently has no Railway-specific config files. Procfile is the simplest, most explicit option and is honoured by Railway's default Python builder.
- A `release` process runs once per deploy AFTER pip install and BEFORE the web process starts — exactly the right slot for `spacy download`.
- The `web:` line preserves the current uvicorn entry contract so the existing Railway service does not need its start command changed in the dashboard.

If at execution time the executor discovers a pre-existing `railway.json` / `nixpacks.toml` / `railway.toml` / Procfile (i.e., the planning-time grep was stale), the executor must:
1. Read whatever config does exist.
2. Add `python -m spacy download xx_ent_wiki_sm` to the appropriate build/release step in that file instead of creating a new Procfile.
3. Note the deviation in the SUMMARY.

If the executor cannot determine the deploy mechanism non-interactively at all, fall back to creating the Procfile above and flag the SUMMARY: "Procfile created assuming Railway default Python builder; verify Railway dashboard does not override start command."
  </action>
  <verify>
    <automated>test -f backend/Procfile &amp;&amp; grep -q "spacy download xx_ent_wiki_sm" backend/Procfile &amp;&amp; grep -q "uvicorn app.main:app" backend/Procfile &amp;&amp; echo OK</automated>
  </verify>
  <acceptance_criteria>
    - `test -f backend/Procfile` exits 0.
    - `grep -q "release: python -m spacy download xx_ent_wiki_sm" backend/Procfile` exits 0 (or `grep -q "spacy download xx_ent_wiki_sm" backend/Procfile` if the executor used a different release-hook syntax in a railway.json fallback).
    - `grep -q "uvicorn app.main:app" backend/Procfile` exits 0.
    - The Procfile (or the alternative deploy config touched) is the ONLY new file from this task — no other files modified.
  </acceptance_criteria>
  <done>Railway release hook downloads xx_ent_wiki_sm on every deploy so Plan 06 lifespan warm-up succeeds; web process unchanged.</done>
</task>

</tasks>

<verification>
After all three tasks complete, run:
```bash
cd backend && source venv/bin/activate
pip install -r requirements.txt
python -c "import presidio_analyzer, presidio_anonymizer, spacy, faker, gender_guesser, nameparser, rapidfuzz, langfuse, pytest, pytest_asyncio; print('OK')"
python -c "from app.services.redaction.gender_id import lookup_gender; print(lookup_gender('Sri'), lookup_gender('Bambang'), lookup_gender('Kris'))"
# Expected: F M unknown
python -c "from app.main import app; print('OK')"
test -f backend/Procfile && grep "spacy download xx_ent_wiki_sm" backend/Procfile
```
</verification>

<success_criteria>
1. `requirements.txt` has 8 new redaction-related dependencies + pytest>=8 + pytest-asyncio>=0.24 appended; all import without error in the local venv.
2. `Faker('id_ID').name()` returns a non-empty Indonesian-locale name string (proves D-04 locale availability).
3. `backend/app/services/redaction/` sub-package exists with `__init__.py` and `gender_id.py`; the package imports cleanly via `from app.services.redaction.gender_id import lookup_gender`.
4. `lookup_gender` returns `M` for "Bambang", `F` for "Sri", `unknown` for "Kris" and missing keys; case-insensitive across "BUDI", "budi", "Budi". Behavioural counts: M>=40, F>=32, U>=6 (verified via in-process Python check, not grep -c).
5. `backend/Procfile` (or equivalent Railway config) downloads `xx_ent_wiki_sm` in the release/build step so Plan 06's lifespan warm-up does not fail on Railway.
</success_criteria>

<output>
After completion, create `.planning/phases/01-detection-anonymization-foundation/01-03-SUMMARY.md` capturing:
- Pinned versions of the 8 new redaction packages + pytest + pytest-asyncio (record exact resolved versions from `pip install` output for reproducibility).
- Whether `python -m spacy download xx_ent_wiki_sm` succeeded locally; if it failed, note that the Railway release hook in Procfile will handle it on deploy.
- Total entry count in `_INDONESIAN_GENDER` (>= 60 required; current target is 78).
- Confirmation that backend boot (`from app.main import app`) is clean.
- Whether a pre-existing Railway config file was found and modified (vs. fresh Procfile created).
</output>
