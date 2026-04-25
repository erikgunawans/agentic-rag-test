---
phase: 02-conversation-scoped-registry-and-round-trip
plan: 02

subsystem: redaction
tags: [pydantic, conversation-scoped-registry, pii-redaction, python, asyncio, casefold, indonesian-honorifics]

# Dependency graph
requires:
  - phase: 01-detection-anonymization-foundation
    provides: |
      strip_honorific helper (honorifics.py), extract_name_tokens helper
      (name_extraction.py), frozen-Pydantic-model precedent (RedactionResult
      in redaction_service.py L58-84), redaction sub-package layout, and the
      D-07 per-call forbidden-token algorithm that ConversationRegistry.
      forbidden_tokens() expands to thread scope.
provides:
  - "EntityMapping frozen Pydantic model — typed payload for entity_registry rows (D-22, D-28)"
  - "ConversationRegistry data-structure skeleton — per-thread in-memory wrapper (D-27)"
  - "lookup() — O(1) casefold-keyed case-insensitive lookup (REG-03 / D-36)"
  - "entries() — read-only copy of registry rows (defensive against caller mutation)"
  - "forbidden_tokens() — PERSON-only thread-wide token set for cross-turn collision avoidance (D-37 / D-38)"
  - "thread_id property — read-only binding identity"
  - "D-31 FUTURE-WORK note — pg_advisory_xact_lock upgrade path documented in module docstring"
affects:
  - 02-03 (migration-push wave 2)
  - 02-04 (registry DB methods — load() / upsert_delta() — added on top of this skeleton)
  - 02-05 (anonymization registry-mode + de_anonymize_text — consumes EntityMapping/lookup/forbidden_tokens)
  - 02-06 (pytest suite — uses ConversationRegistry(thread_id, rows=[...]) for unit-mode coverage)
  - phase-3 (entity-resolution will read EntityMapping rows)
  - phase-5 (chat router lifecycle — load-once-per-turn pattern documented in docstring)
  - phase-6 (advisory-lock upgrade path picked up from D-31 note)

# Tech tracking
tech-stack:
  added: []   # no new dependencies — pydantic + nameparser already in Phase 1
  patterns:
    - "Frozen Pydantic v2 model via ConfigDict(frozen=True) — extends Phase 1 RedactionResult precedent to EntityMapping"
    - "Per-turn (NOT singleton) class — explicitly NOT @lru_cache'd; constructor takes (thread_id, rows) for unit testing"
    - "Two-line split-import for honorifics + name_extraction helpers — mirrors anonymization.py L47-48 (avoids ImportError; B-3 diagnostic)"
    - "casefold-keyed dict for Unicode-correct case-insensitive lookup (D-36) — supersedes str.lower() in any future locale expansion"
    - "Defensive copy on entries() — list(self._rows) returns a fresh list each call so callers cannot mutate internal state"
    - "Counts-only __repr__ — never serialises real values (B4 / D-18 / D-41 invariant)"

key-files:
  created:
    - "backend/app/services/redaction/registry.py (127 lines)"
  modified: []

key-decisions:
  - "Skeleton-only landing — load() / upsert_delta() / async DB methods deliberately deferred to Plan 02-04 (after migration 029 is pushed in Plan 02-03). Lets Wave 2 + Wave 3 land in parallel without false coupling."
  - "TYPE_CHECKING block kept (with empty body) as a structural placeholder so future cross-module annotations land cleanly without re-introducing a circular import (Phase 1 B2 decision carries forward)."
  - "forbidden_tokens() pre-strips honorifics before extract_name_tokens — same algorithm as anonymization.py call site near L262, just larger input set (D-37). PERSON-only filter (D-38)."

patterns-established:
  - "Per-turn registry lifecycle (D-33): load → pass into every redact_text call → discard. Documented in class docstring; Plan 04 wires it."
  - "Defense-in-depth read-only API: lookup() / entries() / forbidden_tokens() / thread_id all expose data WITHOUT a setter; mutation only happens via __init__ (or the future load()/upsert_delta() in Plan 04)."
  - "Strict separation between data-structure plan (this one, Wave 1) and DB-IO plan (Plan 04, Wave 3) — keeps PR review surface tight, makes Wave 1+Wave 2 parallelism real."

requirements-completed: [REG-01, REG-02, REG-03, REG-04, REG-05]

# Metrics
duration: 2min
completed: 2026-04-26
---

# Phase 02 Plan 02: ConversationRegistry Skeleton + EntityMapping Model Summary

**Per-thread real↔surrogate registry data structure (frozen EntityMapping + ConversationRegistry skeleton) — DB-method-free; ready for Plan 04 to extend after migration 029 is pushed.**

## Performance

- **Duration:** ~2 min (plan was a single deterministic file write + verification)
- **Started:** 2026-04-25T23:05:00Z
- **Completed:** 2026-04-25T23:06:47Z
- **Tasks:** 1/1
- **Files modified:** 1 (1 created, 0 modified)

## Accomplishments

- `EntityMapping` frozen Pydantic model with all 5 fields per D-22/D-28 (`real_value`, `real_value_lower`, `surrogate_value`, `entity_type`, `source_message_id`) — `model_config = ConfigDict(frozen=True)` matches Phase 1 `RedactionResult` precedent.
- `ConversationRegistry` class skeleton with `__init__(thread_id, rows)` plus four pure (no-DB) methods: `lookup()`, `entries()`, `forbidden_tokens()`, and a read-only `thread_id` property.
- Module docstring captures the D-31 `pg_advisory_xact_lock` FUTURE-WORK upgrade path verbatim — Phase 6 hardening pass will pick it up via the existing STATE.md "Pending Items" entry.
- `lookup()` is `casefold()`-correct (Unicode-fold, NOT `str.lower()`) and returns `None` (not empty string) on miss; O(1) dict lookup against `_by_lower` built once at construction.
- `entries()` returns `list(self._rows)` — a fresh copy each call so callers cannot mutate internal state.
- `forbidden_tokens()` filters by `entity_type == "PERSON"` (D-38), pre-strips honorifics with `strip_honorific`, then reuses Phase 1's `extract_name_tokens` — same algorithm as `anonymization.py`, just thread-wide input set (D-37).
- `__repr__` returns counts only, never real values (B4 / D-18 / D-41 invariant).
- TWO-line split imports for `strip_honorific` (from `honorifics.py`) and `extract_name_tokens` (from `name_extraction.py`) — mirrors `anonymization.py` L47-48 and avoids the B-3 single-line ImportError trap.
- Methods deliberately deferred to Plan 02-04: `async classmethod load()` and `async def upsert_delta()` — both require migration 029 to be pushed (Wave 2 / Plan 02-03) before they can hit the DB.

## Task Commits

Each task was committed atomically:

1. **Task 1: Create registry.py with EntityMapping model and ConversationRegistry skeleton** — `26cf393` (feat)

_No metadata commit yet — STATE/ROADMAP updates batched at end of this summary._

## Files Created/Modified

- `backend/app/services/redaction/registry.py` (NEW, 127 lines) — `EntityMapping` frozen model + `ConversationRegistry` data-structure skeleton with `lookup`/`entries`/`forbidden_tokens` and a read-only `thread_id` property. NO DB calls; NO supabase imports; NO `async classmethod`. Imports `strip_honorific` from `honorifics.py` and `extract_name_tokens` from `name_extraction.py` on two separate lines (Phase 1 anonymization.py L47-48 shape).

## Decisions Made

None beyond what the plan specified. Followed the exact structure dictated in the plan's `<action>` block. The plan's "10 hard rules" + the inline smoke test left zero design discretion at the file level.

## Deviations from Plan

None — plan executed exactly as written. The single task landed on the first attempt; the inline smoke test passed without modification; backend import succeeded; all 20 Phase 1 tests still green; no auto-fixes required (Rules 1-3 not triggered); no architectural decisions needed (Rule 4 not triggered).

## Issues Encountered

None. The plan's `read_first` block + `<interfaces>` excerpt + B-3 diagnostic warning eliminated the only realistic failure mode (single-line wrong-source `strip_honorific` import).

## Verification Evidence

**File-level acceptance criteria (12/12 PASS):**

| # | Check | Result |
|---|-------|--------|
| 1 | File exists, ≥60 lines | PASS — 127 lines |
| 2 | `class EntityMapping(BaseModel):` + `model_config = ConfigDict(frozen=True)` | PASS — line 44 + 53 |
| 3 | `ConversationRegistry` with `__init__`/`thread_id`/`lookup`/`entries`/`forbidden_tokens` | PASS — all present |
| 4 | `from app.services.redaction.honorifics import strip_honorific` (line-precise) | PASS — line 35 |
| 5 | `from app.services.redaction.name_extraction import extract_name_tokens` (separate line) | PASS — line 36 |
| 6 | NEGATIVE: no `from app.services.redaction.name_extraction import.*strip_honorific` | PASS |
| 7 | NEGATIVE: no `async classmethod` / `async def load` / `async def upsert_delta` | PASS |
| 8 | NEGATIVE: no `from app.database` import | PASS — count = 0 |
| 9 | `D-31` literal present in module docstring | PASS — line 15 |
| 10 | Inline smoke test prints `OK` | PASS |
| 11 | `casefold` count >= 1 | PASS — count = 3 |
| 12 | Module imports cleanly without ImportError | PASS |

**Plan-level verification (4/4 PASS):**

- `python -c "from app.main import app; print('OK')"` → `OK` (no circular import introduced).
- Inline `verify` smoke test → `OK` (lookup case-insensitivity, entries copy semantics, forbidden_tokens correctness all pass).
- `grep "async classmethod load|async def upsert_delta|async def _load_rows|async def _upsert_deltas" backend/app/services/redaction/registry.py` → empty (deferred methods correctly absent).
- `pytest tests/api/test_redaction.py -q` → **20 passed in 1.16s** (no Phase 1 regression).

## User Setup Required

None — no external services, env vars, or migrations touched in this plan. Migration 029 was already written in Plan 02-01 (commit `f7a3ff5`); pushing it is Plan 02-03's job.

## Self-Check: PASSED

- Created file present: `backend/app/services/redaction/registry.py` — FOUND (127 lines).
- Commit `26cf393` exists in `git log --oneline --all` — FOUND.
- All 12 file-level acceptance criteria + 4 plan-level verification checks PASS.
- All 5 success criteria from `<success_criteria>` PASS.

## Next Phase Readiness

- **Wave 2 (Plan 02-03)** is now unblocked — schema push for migration 029. Will create the `entity_registry` table in Supabase that Plan 02-04's DB methods need.
- **Wave 3 (Plan 02-04)** is unblocked from this plan's side (also waits on Plan 02-03's DB push). Will add `async classmethod load()` + `async def upsert_delta()` directly onto the `ConversationRegistry` class shipped here. The `EntityMapping` model is the contract those methods will use — no impedance mismatch.
- **Wave 3 (Plan 02-05)** anonymization-mode upgrade can import `ConversationRegistry` and `EntityMapping` from this plan's file today; the `lookup()` and `forbidden_tokens()` methods are the only surface it needs from the registry.
- **No regressions** — Phase 1 surface (RedactionService, anonymization, etc.) is unchanged. The 20 existing tests still pass.

---
*Phase: 02-conversation-scoped-registry-and-round-trip*
*Completed: 2026-04-26*
