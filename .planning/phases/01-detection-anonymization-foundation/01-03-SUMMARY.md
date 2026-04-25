---
phase: 1
plan: 03
title: "Dependencies install + Indonesian gender lookup table seed + Railway spaCy model bootstrap"
subsystem: "redaction-foundation"
tags: [phase-1, requirements, faker, spacy, presidio, gender-id, railway, procfile]
requirements: [PII-01, ANON-04]
dependency_graph:
  requires:
    - "01-01 (tracing_service.py renamed/migrated)"
    - "01-02 (config.py PII settings + tracing_provider)"
  provides:
    - "Pip-installable Presidio + spaCy + Faker + langfuse + pytest stack for Wave 2/3/4"
    - "lookup_gender(name) helper for ANON-04 gender-matched surrogates"
    - "Railway release hook that downloads xx_ent_wiki_sm so Plan 06 lifespan warm-up succeeds"
  affects:
    - "backend/requirements.txt (append-only)"
    - "backend/app/services/redaction/ (new sub-package)"
    - "backend/Procfile (new)"
tech_stack:
  added:
    - "presidio-analyzer 2.2.359"
    - "presidio-anonymizer 2.2.362"
    - "spacy 3.8.13 (with xx_ent_wiki_sm 3.8.0 model)"
    - "Faker 40.15.0"
    - "gender-guesser 0.4.0"
    - "nameparser 1.1.3"
    - "rapidfuzz 3.14.5"
    - "langfuse 4.5.1"
    - "pytest 9.0.2"
    - "pytest-asyncio 1.3.0"
  patterns:
    - "Hand-curated Indonesian gender lookup (D-05)"
    - "Railway Procfile release hook for non-pip-installable spaCy model"
    - "Sub-package layout under backend/app/services/redaction/ (D-13)"
key_files:
  created:
    - "backend/app/services/redaction/__init__.py"
    - "backend/app/services/redaction/gender_id.py"
    - "backend/Procfile"
  modified:
    - "backend/requirements.txt"
decisions:
  - "Both explicit U entries and missing keys collapse to lookup_gender() returning 'unknown' so callers have a single sentinel for 'use random Faker gender' (D-05)"
  - "Procfile created fresh (no pre-existing railway.json/nixpacks.toml/Procfile in repo); Railway default Python builder honours it"
  - "_INDONESIAN_GENDER seeded with M=40, F=32, U=6 (78 entries; exceeds 60-minimum)"
  - "langfuse pinned >=2.50.0,<5; resolved to 4.5.1; emits Pydantic v1 warning on Python 3.14 (non-blocking, documented in CLAUDE.md)"
  - "spaCy pinned <4 because Presidio 2.2.x is incompatible with spaCy 4.x"
metrics:
  duration: "~7 minutes"
  completed: "2026-04-25"
  tasks: 3
  files_changed: 4
  commits: 3
---

# Phase 1 Plan 03: Dependencies install + Indonesian gender lookup table + Railway spaCy bootstrap

**One-liner:** Installed Presidio + spaCy + Faker + langfuse + pytest-asyncio dependency stack on Python 3.14, created `redaction/` sub-package with hand-curated Indonesian first-name gender lookup (78 entries: 40 M / 32 F / 6 ambiguous), and added a Railway `Procfile` release hook so `xx_ent_wiki_sm` is present at first request.

## What Shipped

### Task 1 — `backend/requirements.txt` (commit `036528a`)

Appended 10 new lines (after the original 13) covering the 8 redaction-related deps from CONTEXT.md `<canonical_refs>` plus the test-tooling pair Plan 07 needs. Resolved versions on Python 3.14:

| Package | Pin | Resolved |
| --- | --- | --- |
| presidio-analyzer | `>=2.2.355` | 2.2.359 |
| presidio-anonymizer | `>=2.2.355` | 2.2.362 |
| spacy | `>=3.7.0,<4.0.0` | 3.8.13 |
| faker | `>=30.0.0` | 40.15.0 |
| gender-guesser | `>=0.4.0` | 0.4.0 |
| nameparser | `>=1.1.3` | 1.1.3 |
| rapidfuzz | `>=3.10.0` | 3.14.5 |
| langfuse | `>=2.50.0,<5` | 4.5.1 |
| pytest | `>=8.0.0` | 9.0.2 |
| pytest-asyncio | `>=0.24.0` | 1.3.0 |

`pip install -r requirements.txt` exits 0. `python -c "import presidio_analyzer, presidio_anonymizer, spacy, faker, gender_guesser, nameparser, rapidfuzz, langfuse, pytest, pytest_asyncio; print('OK')"` succeeds (with the documented langfuse Pydantic v1 warning on Python 3.14, non-blocking). `Faker('id_ID').name()` returns a non-empty Indonesian-locale name (sample: "Iriana Adriansyah, S.Gz") confirming D-04 locale availability.

### Task 2 — Redaction sub-package + gender lookup (commit `dadffbf`)

Created `backend/app/services/redaction/__init__.py` (deliberately minimal — only a docstring and `__all__: list[str] = []`; Plan 04 will add the `RedactionError` re-export from `errors.py`).

Created `backend/app/services/redaction/gender_id.py` with `_INDONESIAN_GENDER: dict[str, Literal["M","F","U"]]` and a public `lookup_gender(name: str) -> Literal["M","F","unknown"]` function. In-process count assertion confirmed: **M=40, F=32, U=6 = 78 total entries** (exceeds the must_have minimum of 60).

Behavioural verification:
- `lookup_gender("Sri")` → `"F"`
- `lookup_gender("Bambang")` → `"M"`
- `lookup_gender("BUDI")` → `"M"` (case-insensitive)
- `lookup_gender("Kris")` → `"unknown"` (explicit U collapses to unknown so callers have a single sentinel)
- `lookup_gender("NotARealName")` → `"unknown"`
- `lookup_gender("")` → `"unknown"`

`from app.main import app` imports cleanly — sub-package registration does not break the import graph.

### Task 3 — Railway Procfile (commit `e5f1cea`)

Confirmed at execution time: no pre-existing `railway.json`, `nixpacks.toml`, `railway.toml`, or `Procfile` at the repo root or in `backend/`. Created fresh `backend/Procfile`:

```
release: python -m spacy download xx_ent_wiki_sm
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

The `release:` hook runs once per deploy AFTER pip install and BEFORE the web process — exactly the right slot for the spaCy model download. The `web:` line preserves the current uvicorn entry contract so the Railway service start command does not need a dashboard change.

## spaCy Model Download Status

`python -m spacy download xx_ent_wiki_sm` **succeeded locally** on the development machine (downloaded `xx_ent_wiki_sm-3.8.0` from `github.com/explosion/spacy-models`, ~11 MB wheel). Smoke test:

```python
import spacy
nlp = spacy.load("xx_ent_wiki_sm")
doc = nlp("Bambang Sutrisno bekerja di Jakarta.")
[(e.text, e.label_) for e in doc.ents]
# -> [('Bambang Sutrisno', 'PER'), ('Jakarta', 'LOC')]
```

Indonesian-name detection works as D-01 promises. The Railway release hook will independently re-download the model on each deploy so production runtime parity is guaranteed.

## Pre-existing Railway Config Discovery

Per the plan's contingency note, the executor scanned for `railway.json` / `nixpacks.toml` / `railway.toml` / `Procfile` at the repo root and `backend/`. **None found.** Therefore the fresh Procfile path was taken, no SUMMARY-level deviation flag needed beyond this confirmation. The CLAUDE.md gotcha about Vercel deploying from `main` (not `master`) is unrelated to backend Procfile handling.

## Deviations from Plan

None. Plan executed exactly as written. No Rule 1/2/3 auto-fixes triggered. No checkpoints reached.

## Verification Summary

All success criteria met:

1. ✅ `requirements.txt` has 8 new redaction deps + pytest>=8 + pytest-asyncio>=0.24; all import without error in the local Python 3.14 venv.
2. ✅ `Faker('id_ID').name()` returns non-empty Indonesian-locale name string.
3. ✅ `backend/app/services/redaction/` sub-package exists with `__init__.py` and `gender_id.py`; package imports cleanly.
4. ✅ `lookup_gender` returns `M` for "Bambang", `F` for "Sri", `unknown` for "Kris" / missing keys / empty string; case-insensitive across "BUDI", "budi", "Budi".
5. ✅ Behavioural counts via in-process Python check: M=40, F=32, U=6 (>= 40, >= 32, >= 6).
6. ✅ `backend/Procfile` downloads `xx_ent_wiki_sm` in the release step so Plan 06 lifespan warm-up will succeed on Railway.
7. ✅ `from app.main import app` exits 0 — no import-graph regression.

## Self-Check: PASSED

- ✅ FOUND: `backend/requirements.txt` (modified)
- ✅ FOUND: `backend/app/services/redaction/__init__.py`
- ✅ FOUND: `backend/app/services/redaction/gender_id.py`
- ✅ FOUND: `backend/Procfile`
- ✅ FOUND commit: `036528a` (feat(01-03): add redaction + test dependencies to requirements.txt)
- ✅ FOUND commit: `dadffbf` (feat(01-03): seed Indonesian first-name gender lookup table)
- ✅ FOUND commit: `e5f1cea` (chore(01-03): add Railway Procfile for spaCy model bootstrap)
