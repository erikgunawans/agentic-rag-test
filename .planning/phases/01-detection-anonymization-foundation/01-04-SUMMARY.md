---
phase: 1
plan: 04
subsystem: redaction
tags: [redaction, helpers, uuid, honorifics, nameparser, leaf-modules, cycle-break]
requires: [01-03]
provides: [errors.RedactionError, uuid_filter.apply_uuid_mask, uuid_filter.restore_uuids, honorifics.strip_honorific, honorifics.reattach_honorific, name_extraction.extract_name_tokens]
affects: [backend/app/services/redaction/]
tech-stack:
  added: []
  patterns: [leaf-module-imports, longest-match-first-regex, mononym-fallback]
key-files:
  created:
    - backend/app/services/redaction/errors.py
    - backend/app/services/redaction/uuid_filter.py
    - backend/app/services/redaction/honorifics.py
    - backend/app/services/redaction/name_extraction.py
  modified: []
decisions:
  - D-02 honorifics: longest-match-first alternation (Bapak before Pak, Sdri. before Sdr.) prevents prefix-of-word false matches
  - D-09/D-10/D-11 uuid_filter: standard 8-4-4-4-12 hex regex, sentinel `<<UUID_N>>`, fail-fast RedactionError on collision
  - D-07 name_extraction: nameparser.HumanName + mononym fallback (whitespace-split, alphabetic-only, len >= 2)
  - Cycle-break: errors.py is a true leaf module — no cross-package imports; uuid_filter imports it via leaf path only
metrics:
  duration_seconds: 187
  tasks_completed: 3
  files_created: 4
  total_lines: 240
  completed_date: 2026-04-25
---

# Phase 1 Plan 04: Redaction Helpers Summary

Built four leaf modules in `backend/app/services/redaction/` (errors, uuid_filter, honorifics, name_extraction) implementing the D-02 honorific strip-and-reattach, D-07 name-token cross-check, and D-09/D-10/D-11 UUID pre-mask filter — each independently unit-testable with zero coupling to Presidio/Faker, and cycle-break invariant verified at AST level (zero `from app.services.redaction import` statements anywhere inside the package).

## Files Created

| File | Lines | Public surface |
|------|------:|----------------|
| `backend/app/services/redaction/errors.py` | 28 | `RedactionError(Exception)` |
| `backend/app/services/redaction/uuid_filter.py` | 78 | `apply_uuid_mask(text)`, `restore_uuids(text, sentinels)` |
| `backend/app/services/redaction/honorifics.py` | 67 | `strip_honorific(name)`, `reattach_honorific(honorific, name)` |
| `backend/app/services/redaction/name_extraction.py` | 67 | `extract_name_tokens(real_names)` |
| **Total** | **240** | |

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | `3620312` | `feat(01-04): add RedactionError + UUID pre-mask filter` |
| 2 | `2bede63` | `feat(01-04): add Indonesian honorific strip-and-reattach (D-02)` |
| 3 | `baf3855` | `feat(01-04): add nameparser-based name token extraction (D-07)` |

## Cycle-Break Invariant: HOLDS

AST-level scan of `backend/app/services/redaction/` confirms **zero** `ImportFrom` nodes that target `app.services.redaction` (the package init). The only grep hit is line 8 of `__init__.py`, which is **inside the module docstring** describing the future post-Plan-06 public surface — not an actual import statement. Verified by:

```python
# AST-level: 0 violations
import ast, pathlib
for f in pathlib.Path('app/services/redaction').glob('*.py'):
    tree = ast.parse(f.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == 'app.services.redaction':
            print(f"VIOLATION: {f}:{node.lineno}")
# (no output — zero violations)
```

This means Plan 06 can land `redaction_service.py → anonymization.py → detection.py → uuid_filter.py → errors.py` without re-entering `__init__.py` mid-load. The chain terminates at `errors.py` (a true leaf — imports nothing from the package).

## D-18 Invariant: HOLDS

Zero `logger.` calls across all four new files. These are leaf helpers; logging happens at the service composition layer in Plan 06.

```text
errors.py:           0 logger calls
uuid_filter.py:      0 logger calls
honorifics.py:       0 logger calls
name_extraction.py:  0 logger calls
```

## nameparser Mononym Behavior (recorded for future reference)

For typical Indonesian mononyms, `nameparser.HumanName` consistently routes the single token to `.first` (NOT `.last`):

| Input | `.first` | `.last` |
|-------|----------|---------|
| `"Bambang"` | `"Bambang"` | `""` |
| `"Sukarno"` | `"Sukarno"` | `""` |
| `"Sri"` | `"Sri"` | `""` |
| `"Joko"` | `"Joko"` | `""` |

Implication: for these cases the mononym fallback (`if not first and not last`) does NOT fire — `parsed.first` is non-empty, so the token is captured directly. The fallback exists as a defensive lower bound for atypical inputs (punctuation, all-caps suffixes like `"PROF."`, etc.) where both `.first` and `.last` could end up empty.

## Honorific Edge Cases Observed

All recorded edge cases behaved as designed:

| Input | Result | Notes |
|-------|--------|-------|
| `"Pak Bambang"` | `("Pak", "Bambang")` | Standard match |
| `"Bapak Joko Wijaya"` | `("Bapak", "Joko Wijaya")` | Longest-match-first: "Bapak" matched before "Pak" alternative |
| `"PAK BUDI"` | `("PAK", "BUDI")` | Case-insensitive match preserves ORIGINAL casing |
| `"BAPAK BUDI"` | `("BAPAK", "BUDI")` round-trips to `"BAPAK BUDI"` | Symmetry holds across casings |
| `"Sdr. Andi"` | `("Sdr.", "Andi")` | Literal `.` correctly escaped via `re.escape` |
| `"Sdri. Putri"` | `("Sdri.", "Putri")` | "Sdri." matched before "Sdr." alternative |
| `"Pakaian Bekas"` | `(None, "Pakaian Bekas")` | **Critical:** "Pak" did NOT match because `\s+` after the prefix is required — `Pakaian` has no whitespace separating "Pak" from "aian". This is the longest-match-first invariant working as intended. |
| `"Bambang"` | `(None, "Bambang")` | No prefix → `None` honorific, full string returned as bare name |

The `"Pakaian"` case is the canonical false-positive guard: a real Indonesian word starting with "Pak" must NOT be stripped. Because the regex requires `\s+` between the prefix capture group and the remainder, and because the pattern is anchored at `^`, the whole-word constraint is enforced naturally.

## Backend Boot

`from app.main import app` exits 0 — all four new files sit at the leaf of the redaction package's import graph and do not pull `redaction/__init__.py` transitively. Verified post-Task-3:

```bash
cd backend && source venv/bin/activate && python -c "from app.main import app; print('app boot OK')"
# → app boot OK
```

## Smoke Test

```bash
python -c "from app.services.redaction.errors import RedactionError; \
  from app.services.redaction.uuid_filter import apply_uuid_mask, restore_uuids; \
  from app.services.redaction.honorifics import strip_honorific, reattach_honorific; \
  from app.services.redaction.name_extraction import extract_name_tokens; print('SMOKE OK')"
# → SMOKE OK
```

All five plan-level verification commands (errors / uuid_filter / honorifics / name_extraction / app boot) return their expected `OK` strings.

## Deviations from Plan

None — plan executed exactly as written. All three tasks shipped against their action specs verbatim; all acceptance criteria green on first pass; no Rule-1/2/3 deviations needed.

## Known Stubs

None. The four modules each have a single, sharply scoped responsibility and a fully working implementation. No placeholders, no mock data, no unwired references. Plan 06 will compose them into `RedactionService`.

## Self-Check: PASSED

All four files exist on disk. All three task commits present in `git log`. AST-level cycle-break check passes. Backend boot OK. Plan-level verification block (5 sub-checks) all green.
