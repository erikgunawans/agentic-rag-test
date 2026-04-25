---
phase: 02-conversation-scoped-registry-and-round-trip
plan: 04
type: execute
wave: 3
depends_on: [02, 03]
files_modified:
  - backend/app/services/redaction/registry.py
  - backend/app/services/redaction/__init__.py
autonomous: true
requirements: [REG-01, REG-02, REG-03, REG-04, REG-05]
must_haves:
  truths:
    - "ConversationRegistry.load(thread_id) issues exactly one SELECT and returns a populated instance"
    - "ConversationRegistry.upsert_delta(deltas) issues one INSERT ... ON CONFLICT DO NOTHING for the deltas"
    - "Empty deltas list = no DB hop"
    - "Service-role client used for ALL registry traffic (no auth-scoped client) — D-25"
    - "Re-exports added to redaction/__init__.py: ConversationRegistry, EntityMapping (NOT de_anonymize_text — option b honored)"
  artifacts:
    - path: "backend/app/services/redaction/registry.py"
      provides: "DB-backed load + upsert_delta on ConversationRegistry"
      exports: ["EntityMapping", "ConversationRegistry"]
      min_lines: 130
    - path: "backend/app/services/redaction/__init__.py"
      provides: "Public re-exports of ConversationRegistry + EntityMapping"
      exports: ["RedactionError", "ConversationRegistry", "EntityMapping"]
  key_links:
    - from: "backend/app/services/redaction/registry.py"
      to: "app.database.get_supabase_client"
      via: "service-role read/write"
      pattern: "from app.database import get_supabase_client"
    - from: "backend/app/services/redaction/registry.py"
      to: "public.entity_registry table"
      via: "supabase-py client.table('entity_registry')"
      pattern: "client\\.table\\(['\"]entity_registry['\"]\\)"
---

<objective>
Add the DB-backed surface to `ConversationRegistry`: `load(thread_id)` classmethod and `upsert_delta(deltas)` method. Then re-export `ConversationRegistry` + `EntityMapping` from `backend/app/services/redaction/__init__.py`.

Purpose: Wave 3 — once the table exists (Wave 2 push complete), the registry's pure-data skeleton (Plan 02) needs the persistence path. This plan finishes the registry's public surface so Plan 05 (redaction_service.py wiring) can use it.

Output: Two file modifications. registry.py grows from ~80 lines to ~130 lines with the two async DB methods. `__init__.py` adds two names to `__all__`.

Resolution of the open question (CONTEXT.md "Integration Points" vs Phase 1 B2):
**Decision:** keep `de_anonymize_text` as a `RedactionService` method only — DO NOT re-export from `__init__.py`. (Option (b).) Rationale: matches Phase 1's documented circular-import-avoidance posture (B2 option B); callers access via `get_redaction_service().de_anonymize_text(...)`. CONTEXT.md "Claude's Discretion" §3 explicitly permits this choice.
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
@CLAUDE.md
@backend/app/database.py
@backend/app/services/system_settings_service.py
@backend/app/services/audit_service.py
@backend/app/services/redaction/registry.py
@backend/app/services/redaction/__init__.py
@supabase/migrations/029_pii_entity_registry.sql

<interfaces>
<!-- Existing primitives this plan calls. Read once; no codebase exploration needed. -->

From backend/app/database.py L1-8:
```python
from supabase import Client
def get_supabase_client() -> Client:
    """Service-role client — bypasses RLS for admin operations."""
```
This is the ONLY DB client this plan uses (D-25). NEVER use `get_supabase_authed_client(token)` here.

From backend/app/services/system_settings_service.py L1-20 (analog A — service-role read):
- Pattern: `client = get_supabase_client(); client.table(name).select('*').eq(col, val).execute()`
- supabase-py is sync; the call blocks the event loop. We wrap in `asyncio.to_thread(...)` so the lock-held coroutine doesn't starve other tasks.

From backend/app/services/audit_service.py L1-32 (analog B — service-role insert):
- Pattern: `client.table(name).insert([rows]).execute()`
- Audit IS fire-and-forget; registry is NOT. Registry writes MUST raise on failure (REG-04 invariant).

From migration 029 (Plan 01 output):
- Table: `public.entity_registry`
- Columns: `id`, `thread_id`, `real_value`, `real_value_lower`, `surrogate_value`, `entity_type`, `source_message_id`, `created_at`, `updated_at`
- Composite UNIQUE: `(thread_id, real_value_lower)`

From backend/app/services/redaction/__init__.py (current shape):
```python
from app.services.redaction.errors import RedactionError
__all__ = ["RedactionError"]
```
There is also a "B2 option B" rationale comment block in this file from Phase 1 — preserve it verbatim.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: Add async load() classmethod and upsert_delta() to ConversationRegistry</name>
  <files>backend/app/services/redaction/registry.py</files>
  <read_first>
    - backend/app/services/redaction/registry.py (Plan 02 output — current file; read in full so the executor diff-edits, not rewrites)
    - backend/app/database.py L1-30 (get_supabase_client signature)
    - backend/app/services/system_settings_service.py L1-25 (sync client + cache pattern; Phase 2 drops the cache, keeps the SELECT shape)
    - backend/app/services/audit_service.py L1-32 (insert + error handling pattern; Phase 2 swaps "fire and forget" for "raise on error")
    - .planning/phases/02-conversation-scoped-registry-and-round-trip/02-PATTERNS.md §"Pattern A — Service-role read with module-level cache" + §"Pattern B — Service-role insert"
    - .planning/phases/02-conversation-scoped-registry-and-round-trip/02-CONTEXT.md decisions D-25, D-27, D-32, D-33, D-36
  </read_first>
  <action>
EDIT (do not rewrite) `backend/app/services/redaction/registry.py` from Plan 02. Three changes only:

(A) Add new imports at the top of the file (after existing imports):
```python
import asyncio

from app.database import get_supabase_client
```

(B) Add new `async classmethod load` on `ConversationRegistry` — insert AFTER the `__init__` method, BEFORE the `thread_id` property:

```python
    @classmethod
    async def load(cls, thread_id: str) -> "ConversationRegistry":
        """Lazy-load the registry for a thread on the first redact call of a turn (D-33).

        One SELECT against `public.entity_registry`. Service-role client per D-25
        (RLS is enabled with no policies — only the service role can read).

        Returns an empty registry (rows=[]) for a brand-new thread; this is
        REG-01-compliant behaviour, not an error.
        """
        client = get_supabase_client()

        def _select() -> list[dict]:
            res = (
                client.table("entity_registry")
                .select("real_value,real_value_lower,surrogate_value,entity_type,source_message_id")
                .eq("thread_id", thread_id)
                .execute()
            )
            return list(res.data or [])

        raw_rows = await asyncio.to_thread(_select)
        rows: list[EntityMapping] = [EntityMapping(**r) for r in raw_rows]

        logger.debug(
            "registry.load: thread_id=%s rows=%d",
            thread_id,
            len(rows),
        )
        return cls(thread_id=thread_id, rows=rows)
```

(C) Add new `async def upsert_delta` method — insert AFTER `forbidden_tokens()`, BEFORE `__repr__`:

```python
    async def upsert_delta(self, deltas: list[EntityMapping]) -> None:
        """Persist newly-introduced mappings to the entity_registry table (D-32).

        Called from inside the asyncio.Lock critical section in
        `redaction_service.redact_text(text, registry)`. Empty list = no-op
        (zero DB hops). Successful inserts also update the in-memory state so
        subsequent `lookup()` calls in this turn see the new entries without
        re-querying the DB.

        Uses INSERT ... ON CONFLICT (thread_id, real_value_lower) DO NOTHING
        — the composite UNIQUE constraint (D-23) is the cross-process
        serialisation safety net; even if two workers race past asyncio.Lock,
        only one row lands.

        Raises any DB error (REG-04 invariant: a lost write would silently
        violate "same real → same surrogate"). Phase 1 audit_service is
        fire-and-forget; registry writes are NOT.
        """
        if not deltas:
            return  # zero-DB-hop fast path

        client = get_supabase_client()
        rows = [
            {
                "thread_id": self._thread_id,
                "real_value": m.real_value,
                "real_value_lower": m.real_value_lower,
                "surrogate_value": m.surrogate_value,
                "entity_type": m.entity_type,
                "source_message_id": m.source_message_id,
            }
            for m in deltas
        ]

        def _upsert() -> None:
            (
                client.table("entity_registry")
                .upsert(
                    rows,
                    on_conflict="thread_id,real_value_lower",
                    ignore_duplicates=True,
                )
                .execute()
            )

        try:
            await asyncio.to_thread(_upsert)
        except Exception as e:
            logger.error(
                "registry.upsert_delta failed: thread_id=%s deltas=%d error_type=%s",
                self._thread_id,
                len(deltas),
                type(e).__name__,
            )
            raise

        for m in deltas:
            if m.real_value_lower not in self._by_lower:
                self._rows.append(m)
                self._by_lower[m.real_value_lower] = m

        logger.debug(
            "registry.upsert_delta: thread_id=%s wrote=%d size_after=%d",
            self._thread_id,
            len(deltas),
            len(self._rows),
        )
```

Hard rules — verify after editing:

- `load` MUST be an `async classmethod` (returns `"ConversationRegistry"` self-ref string for forward-compat).
- `load` MUST use `asyncio.to_thread` to wrap the sync supabase-py call. Phase 2 spends time inside the asyncio.Lock — blocking the event loop there starves other coroutines.
- `load` MUST use `get_supabase_client()`. NEVER `get_supabase_authed_client(token)` (D-25 / D-26).
- `upsert_delta` MUST short-circuit on empty list: `if not deltas: return`.
- `upsert_delta` MUST use `on_conflict="thread_id,real_value_lower"` and `ignore_duplicates=True` — produces `INSERT ... ON CONFLICT DO NOTHING` (D-23 / D-32).
- `upsert_delta` MUST update `self._rows` and `self._by_lower` IN-MEMORY after the successful DB write. First-write-wins (don't overwrite existing entries) matches ON CONFLICT DO NOTHING semantics.
- `upsert_delta` MUST `raise` on DB exception (NOT swallow). Phase 1 `audit_service.log_action` swallows; registry writes do NOT — REG-04 invariant.
- All new debug logs MUST use `%s` / `%d` formatting and contain ZERO real values (B4 / D-18 / D-41). Counts, thread_id (UUID, not PII), and `type(e).__name__` only.

Bug to avoid: do NOT call `asyncio.to_thread(client.table(...).select(...).execute)` directly. Build the entire query inside the closure (the `_select` / `_upsert` functions), then `await asyncio.to_thread(_select)`. The supabase-py client builder chain is not thread-safe for concurrent chain construction.

After editing, run the import smoke test:
```bash
cd backend && source venv/bin/activate && python -c "from app.services.redaction.registry import ConversationRegistry, EntityMapping; print('IMPORT_OK')"
```
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && python -c "import inspect, asyncio; from app.services.redaction.registry import ConversationRegistry, EntityMapping; assert inspect.iscoroutinefunction(ConversationRegistry.load.__func__), 'load must be async'; assert inspect.iscoroutinefunction(ConversationRegistry.upsert_delta), 'upsert_delta must be async'; r = ConversationRegistry(thread_id='t-1', rows=[]); res = asyncio.run(r.upsert_delta([])); assert res is None, 'empty upsert_delta must short-circuit'; print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - File contains `async def load(cls, thread_id` (or equivalent classmethod signature).
    - File contains `async def upsert_delta(self, deltas`.
    - File imports `from app.database import get_supabase_client` (exactly once).
    - File contains `asyncio.to_thread(` (at least 2 occurrences — one in load, one in upsert_delta).
    - File contains `on_conflict="thread_id,real_value_lower"` AND `ignore_duplicates=True`.
    - File contains `if not deltas:` (empty-list fast path).
    - File contains `raise` inside the `upsert_delta` exception handler (NOT swallowed).
    - No occurrence of `get_supabase_authed_client` in the file.
    - The verify automated command prints `OK`.
    - Phase 1's tests still pass: `cd backend && source venv/bin/activate && pytest backend/tests/api/test_redaction.py -q` exits 0.
  </acceptance_criteria>
  <done>The `ConversationRegistry` is fully wired to the live DB. `load(thread_id)` returns a populated instance; `upsert_delta(deltas)` writes via INSERT ON CONFLICT DO NOTHING. Plan 05 can now import and use these.</done>
</task>

<task type="auto" tdd="false">
  <name>Task 2: Re-export ConversationRegistry and EntityMapping from redaction/__init__.py</name>
  <files>backend/app/services/redaction/__init__.py</files>
  <read_first>
    - backend/app/services/redaction/__init__.py (current — preserve the "B2 option B" rationale block in full; only ADD imports/__all__ entries)
    - backend/app/services/redaction/registry.py (Task 1 output — confirms the class names being re-exported)
    - .planning/phases/02-conversation-scoped-registry-and-round-trip/02-PATTERNS.md §"backend/app/services/redaction/__init__.py (MODIFY)"
    - .planning/phases/02-conversation-scoped-registry-and-round-trip/02-CONTEXT.md decisions D-27, D-28, "Integration Points"
  </read_first>
  <action>
EDIT `backend/app/services/redaction/__init__.py`. Two changes only.

1. Add a new import line. Place it AFTER the existing `from app.services.redaction.errors import RedactionError` line:

```python
from app.services.redaction.registry import ConversationRegistry, EntityMapping
```

2. Append two names to the `__all__` list. The final `__all__` MUST read:

```python
__all__ = [
    "RedactionError",
    "ConversationRegistry",
    "EntityMapping",
]
```

DO NOT:
- Add `de_anonymize_text` to either the imports or `__all__`. Per the open-question resolution (option (b)): `de_anonymize_text` is a `RedactionService` method only; callers reach it via `get_redaction_service().de_anonymize_text(...)`. Plan 05 implements `de_anonymize_text` as a method on `RedactionService` in `redaction_service.py`, NOT here.
- Modify the existing "B2 option B" rationale comment block. It must remain verbatim.
- Reorder existing imports/exports.

After editing, run the smoke tests:

```bash
cd backend && source venv/bin/activate && python -c "from app.services.redaction import RedactionError, ConversationRegistry, EntityMapping; print('REEXPORTS_OK')"
```

Negative check (de_anonymize_text not exported here):
```bash
cd backend && source venv/bin/activate && python -c "
import app.services.redaction as r
assert 'de_anonymize_text' not in r.__all__, 'de_anonymize_text MUST NOT be re-exported here'
print('NEGATIVE_CHECK_OK')
"
```
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && python -c "from app.services.redaction import RedactionError, ConversationRegistry, EntityMapping; import app.services.redaction as r; assert 'de_anonymize_text' not in r.__all__; assert set(r.__all__) == {'RedactionError', 'ConversationRegistry', 'EntityMapping'}; print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `backend/app/services/redaction/__init__.py` contains `from app.services.redaction.registry import ConversationRegistry, EntityMapping`.
    - `__all__` is exactly `["RedactionError", "ConversationRegistry", "EntityMapping"]` (set equality — order tolerant).
    - `de_anonymize_text` does NOT appear in `__all__`.
    - The existing "B2 option B" rationale comment block is preserved verbatim (line-by-line `git diff` shows zero changes to those lines).
    - The verify automated command prints `OK`.
    - Backend imports cleanly: `python -c "from app.main import app; print('OK')"`.
  </acceptance_criteria>
  <done>The `redaction` sub-package surface exposes the two new public names (ConversationRegistry, EntityMapping) without re-exporting the service method (option b honored). Plan 05 can now `from app.services.redaction import ConversationRegistry, EntityMapping` cleanly.</done>
</task>

</tasks>

<verification>
- `cd backend && source venv/bin/activate && python -c "from app.main import app; print('OK')"` — backend still imports.
- `cd backend && source venv/bin/activate && pytest backend/tests/api/test_redaction.py -q` — Phase 1's 20 tests still pass (this plan only adds DB methods + re-exports; does not change redact_text yet).
- `python -c "from app.services.redaction.registry import ConversationRegistry, EntityMapping"` succeeds.
- `python -c "from app.services.redaction import ConversationRegistry, EntityMapping, RedactionError"` succeeds.
- A live smoke (optional, requires DB up): construct a fresh thread row, call `await ConversationRegistry.load(<that id>)` — returns an empty registry without raising.
</verification>

<success_criteria>
- `ConversationRegistry.load` and `.upsert_delta` are async, type-correct, and use the service-role client (D-25).
- Empty-list `upsert_delta` is a no-op (zero DB hops).
- Re-exports surface the new names; `de_anonymize_text` deliberately omitted (option b honored).
- Phase 1 regression: 20/20 still pass.
</success_criteria>

<output>
Create `.planning/phases/02-conversation-scoped-registry-and-round-trip/02-04-SUMMARY.md` with:
- registry.py final line count + the two added methods + the imports added
- redaction/__init__.py diff (lines added; comment block untouched)
- Open-question resolution explicitly captured: "Option (b) chosen — de_anonymize_text NOT re-exported"
- Phase 1 regression check result
</output>
