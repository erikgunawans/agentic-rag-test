---
phase: 02-conversation-scoped-registry-and-round-trip
plan: 02
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/app/services/redaction/registry.py
autonomous: true
requirements: [REG-01, REG-02, REG-03, REG-04, REG-05]
must_haves:
  truths:
    - "EntityMapping Pydantic model exists with all 5 fields from D-22/D-28 (frozen)"
    - "ConversationRegistry class skeleton exists with __init__ taking (thread_id, rows)"
    - "Module docstring captures D-31 advisory-lock FUTURE-WORK note"
    - "No supabase client calls yet — pure data structure (DB methods come in Plan 04 after schema is pushed)"
  artifacts:
    - path: "backend/app/services/redaction/registry.py"
      provides: "EntityMapping model + ConversationRegistry data structure skeleton"
      exports: ["EntityMapping", "ConversationRegistry"]
      min_lines: 60
  key_links:
    - from: "backend/app/services/redaction/registry.py"
      to: "pydantic.BaseModel + ConfigDict(frozen=True)"
      via: "EntityMapping subclass"
      pattern: "class EntityMapping\\(BaseModel\\)"
---

<objective>
Stand up the data-structure skeleton: `EntityMapping` Pydantic model + `ConversationRegistry` class with constructor and pure (no-DB) accessor methods.

Purpose: Give Wave 3 a concrete typed surface to import. We split this from Plan 04 (DB methods) because Plan 04 depends on Wave 2's `supabase db push`, but the typed model + non-DB methods can land in parallel with the migration in Wave 1.

Output: `backend/app/services/redaction/registry.py` — frozen `EntityMapping` model and a `ConversationRegistry` class with `__init__`, `lookup`, `entries`, `forbidden_tokens`, `thread_id` property. Database methods (`load`, `upsert_delta`) are deliberately NOT in this plan — Plan 04 adds them after the table exists.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/02-conversation-scoped-registry-and-round-trip/02-CONTEXT.md
@.planning/phases/02-conversation-scoped-registry-and-round-trip/02-PATTERNS.md
@.planning/phases/01-detection-anonymization-foundation/01-CONTEXT.md
@CLAUDE.md
@backend/app/services/redaction_service.py
@backend/app/services/redaction/__init__.py
@backend/app/services/redaction/name_extraction.py
@backend/app/services/redaction/honorifics.py
@backend/app/services/redaction/anonymization.py

<interfaces>
<!-- Existing primitives this plan uses. Read once; no codebase exploration needed. -->

From backend/app/services/redaction_service.py L58-84 (Phase 1 — frozen model precedent):
```python
class RedactionResult(BaseModel):
    """D-13 public output schema."""
    model_config = ConfigDict(frozen=True)
    anonymized_text: str
    entity_map: dict[str, str]
    hard_redacted_count: int
    latency_ms: float
```

From backend/app/services/redaction/name_extraction.py L35-67 (Phase 1 — token extractor):
- `extract_name_tokens(real_names: list[str]) -> set[str]` — for each bare name, parses with `nameparser.HumanName`, returns the union of lower-cased first + last tokens (with whitespace-split fallback for mononyms).

From backend/app/services/redaction/honorifics.py L38-52 (Phase 1 — Indonesian honorific splitter):
- `strip_honorific(name: str) -> tuple[str | None, str]` — returns (honorific or None, bare_name) pair. Recognised prefixes: Pak, Bapak, Bu, Ibu, Sdr., Sdri.

From backend/app/services/redaction/anonymization.py L47-48 (existing imports in Phase 1 — TWO separate lines):
```python
from app.services.redaction.honorifics import reattach_honorific, strip_honorific
from app.services.redaction.name_extraction import extract_name_tokens
```
NOTE: `strip_honorific` is in `honorifics.py`, NOT `name_extraction.py`. Phase 2 follows the same split-import shape.

These are the helpers `ConversationRegistry.forbidden_tokens()` reuses.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: Create registry.py with EntityMapping model and ConversationRegistry skeleton</name>
  <files>backend/app/services/redaction/registry.py</files>
  <read_first>
    - backend/app/services/redaction_service.py L1-90 (frozen model pattern + module-level logger pattern + imports style — Phase 1 D-13 carryover)
    - backend/app/services/redaction/honorifics.py L1-50 (strip_honorific signature: returns `tuple[str | None, str]`; CANONICAL location for this function)
    - backend/app/services/redaction/name_extraction.py L1-80 (extract_name_tokens signature; this file does NOT contain strip_honorific)
    - backend/app/services/redaction/anonymization.py L47-48, L183-207 (Phase 1 D-07 forbidden-token block; observe that strip_honorific is imported from honorifics.py and extract_name_tokens from name_extraction.py — TWO separate import lines. Phase 2 EXPANDS its input set; do NOT rewrite the algorithm)
    - backend/app/services/redaction/__init__.py (current re-export shape; Plan 04 will add to this — DO NOT touch in this plan)
    - .planning/phases/02-conversation-scoped-registry-and-round-trip/02-PATTERNS.md §"backend/app/services/redaction/registry.py (NEW)" + Pattern C
    - .planning/phases/02-conversation-scoped-registry-and-round-trip/02-CONTEXT.md decisions D-27, D-28, D-31, D-36, D-37, D-38
  </read_first>
  <action>
Create `backend/app/services/redaction/registry.py` with the following EXACT structure. Do NOT add DB methods (`load`, `upsert_delta`) — those come in Plan 04 after the schema is pushed.

```python
"""Conversation-scoped real↔surrogate registry (Phase 2).

Per-thread in-memory wrapper backed by the `entity_registry` Postgres table
(migration 029). The registry guarantees that within a thread, the same real
entity always maps to the same surrogate (REG-04 / FR-3.4) and that mappings
survive a backend restart (REG-02 / FR-3.2).

Lifecycle (D-33):
    1. Chat router calls `await ConversationRegistry.load(thread_id)` once per
       chat turn — issues a single SELECT to populate the in-memory dict.
    2. The instance is passed into every `redact_text(...)` call within that
       turn.
    3. The instance is discarded after the assistant response is committed.

D-31 (FUTURE-WORK Phase 6): the asyncio.Lock-keyed-by-thread_id strategy that
serialises concurrent writers (`redaction_service._thread_locks`) is correct
ONLY while Railway runs a single Uvicorn worker. Under multi-worker or
horizontally-scaled deploys, replace it with `pg_advisory_xact_lock(hashtext(
thread_id))`. The composite UNIQUE constraint `(thread_id, real_value_lower)`
on the table is the cross-process safety net until that upgrade lands.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

# IMPORTANT: strip_honorific lives in honorifics.py, NOT name_extraction.py.
# Phase 1's anonymization.py uses the SAME two-line split (L47 + L48). If you
# accidentally write a single-line import from name_extraction containing
# strip_honorific, Python will raise ImportError at module import time —
# confirm the import comes from honorifics.py before retrying (B-3 diagnostic).
from app.services.redaction.honorifics import strip_honorific
from app.services.redaction.name_extraction import extract_name_tokens

if TYPE_CHECKING:  # avoid runtime cycle if any caller threads this through
    pass

logger = logging.getLogger(__name__)


class EntityMapping(BaseModel):
    """In-memory + row-creation payload for the entity_registry table (D-28).

    Field shapes match migration 029 columns exactly. `real_value_lower` is
    `str.casefold()`'d at construction time (Unicode-correct; D-36).
    `source_message_id` is nullable because `redact_text` runs BEFORE the
    user-message row is committed; the chat router (Phase 5) backfills it.
    """

    model_config = ConfigDict(frozen=True)

    real_value: str
    real_value_lower: str
    surrogate_value: str
    entity_type: str  # PERSON / EMAIL_ADDRESS / PHONE_NUMBER / LOCATION / DATE_TIME / URL / IP_ADDRESS
    source_message_id: str | None = None


class ConversationRegistry:
    """Per-thread in-memory wrapper over `entity_registry` rows (D-27).

    NOT a singleton (D-33: per-turn lifecycle). Do NOT decorate with
    @lru_cache. Constructed by `ConversationRegistry.load(thread_id)`
    (added in Plan 04 once the table is pushed); tests may construct
    directly with `ConversationRegistry(thread_id=..., rows=[...])`
    for unit-mode coverage.
    """

    def __init__(self, thread_id: str, rows: list[EntityMapping] | None = None) -> None:
        self._thread_id: str = thread_id
        self._rows: list[EntityMapping] = list(rows or [])
        # Casefold-keyed dict for O(1) case-insensitive lookup (REG-03 / D-36).
        self._by_lower: dict[str, EntityMapping] = {
            m.real_value_lower: m for m in self._rows
        }

    @property
    def thread_id(self) -> str:
        """Read-only thread_id this registry is bound to."""
        return self._thread_id

    def lookup(self, real_value: str) -> str | None:
        """Case-insensitive lookup of an existing surrogate.

        Returns the existing `surrogate_value` if `real_value` (after
        `str.casefold()`) is already in the registry, else None. This is the
        hot path for "same real → same surrogate within thread" (REG-04 /
        FR-3.4); O(1) dict lookup.
        """
        hit = self._by_lower.get(real_value.casefold())
        return hit.surrogate_value if hit is not None else None

    def entries(self) -> list[EntityMapping]:
        """Read-only iteration of all registry entries.

        Used by `de_anonymize_text` (Phase 2 Plan 05) and by callers
        diffing the registry against new entity_map rows to compute deltas.
        Returns a NEW list each call so callers cannot mutate internal state.
        """
        return list(self._rows)

    def forbidden_tokens(self) -> set[str]:
        """Per-PERSON thread-wide forbidden-token set (D-37 / D-38).

        Returns the union of first-name + surname tokens of every PERSON
        entry currently in the registry. Phase 1 D-07's per-call check
        is expanded with this set so Faker never generates a surrogate
        whose tokens collide with a real PERSON name already mapped in
        this thread (PRD §7.5 cross-turn corruption case).

        D-38: PERSON-only. Email / phone / URL collisions are negligible
        and the cost of building a thread-wide forbidden set across all
        types is wasted.
        """
        person_reals = [m.real_value for m in self._rows if m.entity_type == "PERSON"]
        # Strip honorifics first — same as Phase 1 anonymization.py (L47 honorifics
        # import + the call site near L262) so e.g. "Pak" doesn't accidentally
        # land in the forbidden set.
        bare_names = [strip_honorific(name)[1] for name in person_reals]
        return extract_name_tokens(bare_names)

    def __repr__(self) -> str:  # pragma: no cover — debug aid only; never logs real values
        # B4 / D-18 / D-41: counts only, never real values.
        return f"ConversationRegistry(thread_id={self._thread_id!r}, size={len(self._rows)})"
```

Hard rules — verify after writing:

1. `EntityMapping` MUST be `frozen=True` via `ConfigDict(frozen=True)` (matches Phase 1 RedactionResult — D-13 carryover; prevents accidental cross-coroutine mutation).

2. `ConversationRegistry.__init__` MUST accept a `rows` list and build `_by_lower` from it. The dict key is `m.real_value_lower` (already casefold'd at insert time per D-36) — DO NOT casefold again here.

3. `lookup()` MUST use `.casefold()` (NOT `.lower()`) on the input — Unicode-correct fold per D-36. Returns `None` (not empty string) when not found.

4. `entries()` MUST return `list(self._rows)` (a copy) — not `self._rows` directly. Callers must not be able to mutate internal state.

5. `forbidden_tokens()` MUST filter by `entity_type == "PERSON"` (D-38: per-PERSON only). MUST call `strip_honorific` before `extract_name_tokens` — same algorithm as Phase 1 anonymization.py (call site near L262).

6. Module docstring MUST include the D-31 FUTURE-WORK upgrade-path note verbatim (so Phase 6 hardening picks it up; aligns with `.planning/STATE.md` Pending Items entry).

7. NO supabase client calls in this file in this plan. NO `async classmethod load`. NO `async def upsert_delta`. Plan 04 adds those after Wave 2 pushes the schema. The skeleton must be importable WITHOUT the table existing.

8. Logger initialised as `logger = logging.getLogger(__name__)` (Phase 1 module convention).

9. `__repr__` returns counts only, NEVER real values (B4 invariant).

10. **Imports**: TWO separate lines — `from app.services.redaction.honorifics import strip_honorific` AND `from app.services.redaction.name_extraction import extract_name_tokens`. Phase 1's `anonymization.py` L47 reads `from app.services.redaction.honorifics import reattach_honorific, strip_honorific` and L48 reads `from app.services.redaction.name_extraction import extract_name_tokens`. We mirror that shape. Do NOT collapse to a single `from app.services.redaction.name_extraction import extract_name_tokens, strip_honorific` — `strip_honorific` is NOT defined in `name_extraction.py` and the import will raise `ImportError` at module load.

**Executor diagnostic (B-3):** If `ImportError` surfaces for `strip_honorific`, confirm the import comes from `honorifics.py`, not `name_extraction.py` — that is the canonical Phase 1 location (verified by `grep -n "def strip_honorific" backend/app/services/redaction/*.py` returning only `honorifics.py`). The smoke-test command in `<verify>` below will fail at import time with this exact ImportError if the import is wrong; do NOT advance to the assertion line — fix the import first.
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && python -c "from app.services.redaction.registry import ConversationRegistry, EntityMapping; m = EntityMapping(real_value='Bambang Sutrisno', real_value_lower='bambang sutrisno', surrogate_value='Andi Pratama', entity_type='PERSON'); r = ConversationRegistry(thread_id='t-1', rows=[m]); assert r.lookup('BAMBANG SUTRISNO') == 'Andi Pratama', 'lookup must be casefold-correct'; assert r.lookup('not in registry') is None; assert r.thread_id == 't-1'; assert len(r.entries()) == 1; assert r.entries() is not r._rows, 'entries() must return a copy'; tokens = r.forbidden_tokens(); assert 'bambang' in tokens and 'sutrisno' in tokens, f'forbidden_tokens missing PERSON parts: {tokens}'; print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - File `backend/app/services/redaction/registry.py` exists.
    - File contains `class EntityMapping(BaseModel):` with `model_config = ConfigDict(frozen=True)`.
    - File contains `class ConversationRegistry:` with `__init__`, `thread_id` property, `lookup`, `entries`, `forbidden_tokens` methods.
    - File contains `from app.services.redaction.honorifics import strip_honorific` (line-precise grep match — strip_honorific is imported from honorifics.py NOT name_extraction.py).
    - File contains `from app.services.redaction.name_extraction import extract_name_tokens` (separate import line).
    - File does NOT contain `from app.services.redaction.name_extraction import.*strip_honorific` (negative grep — would be a wrong-source import that ImportErrors at load).
    - File does NOT contain `async classmethod` (no DB methods yet — those come in Plan 04).
    - File does NOT import `app.database` (no supabase client usage in this plan).
    - File contains the literal string `D-31` in the module docstring (FUTURE-WORK note present).
    - `python -c "from app.services.redaction.registry import ConversationRegistry, EntityMapping"` succeeds without ImportError.
    - The verify automated command prints `OK` (lookup case-insensitivity, entries copy, forbidden_tokens correctness all pass).
    - `grep -c "from app.database" backend/app/services/redaction/registry.py` returns 0.
    - `grep -c "casefold" backend/app/services/redaction/registry.py` returns >= 1 (D-36 honored).
  </acceptance_criteria>
  <done>The skeleton compiles, imports cleanly, the inline smoke test passes, and the module is ready for Plan 04 (DB methods) to extend it after the schema is live.</done>
</task>

</tasks>

<verification>
- `cd backend && source venv/bin/activate && python -c "from app.main import app; print('OK')"` — backend still imports (no circular import introduced).
- The inline verify command in Task 1 returns `OK`.
- `grep "async classmethod load\|async def upsert_delta\|async def _load_rows\|async def _upsert_deltas" backend/app/services/redaction/registry.py` returns nothing (those are deferred to Plan 04).
- Phase 1's existing 20 tests still pass: `cd backend && source venv/bin/activate && pytest backend/tests/api/test_redaction.py -q` (no signature change to redact_text yet — Plan 05 does that; this plan only adds a new file).
</verification>

<success_criteria>
- Skeleton `ConversationRegistry` and `EntityMapping` exist and are importable.
- The pure (no-DB) methods `lookup`, `entries`, `forbidden_tokens` work correctly per D-27, D-36, D-37, D-38.
- D-31 FUTURE-WORK note is in the module docstring.
- No regression to Phase 1 (this plan adds a new file; touches nothing else).
</success_criteria>

<output>
Create `.planning/phases/02-conversation-scoped-registry-and-round-trip/02-02-SUMMARY.md` with:
- Path of new file
- Methods present (lookup / entries / forbidden_tokens / thread_id property)
- Methods deliberately deferred to Plan 04 (load / upsert_delta)
- Confirm Phase 1's 20 tests still pass.
</output>
</content>
</invoke>