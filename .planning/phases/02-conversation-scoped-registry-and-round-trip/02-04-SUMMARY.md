---
phase: 02-conversation-scoped-registry-and-round-trip
plan: 04
subsystem: backend/redaction
tags: [registry, db-methods, reexports, async, supabase, service-role]
dependency-graph:
  requires:
    - 02-02 (ConversationRegistry skeleton — EntityMapping + lookup/entries/forbidden_tokens)
    - 02-03 (live entity_registry table — pushed via Supabase MCP, commit 3c2e473)
  provides:
    - ConversationRegistry.load(thread_id) — async classmethod, one SELECT, populated instance
    - ConversationRegistry.upsert_delta(deltas) — async, INSERT...ON CONFLICT DO NOTHING, idempotent
    - Public re-exports: ConversationRegistry + EntityMapping from app.services.redaction
  affects:
    - 02-05 (redaction_service.py wiring — can now from app.services.redaction import ConversationRegistry, EntityMapping)
    - 02-06 (pytest suite — load + upsert_delta integration tests now possible)
tech-stack:
  added: []
  patterns:
    - "service-role supabase client for system-level table (D-25 — analog: system_settings_service.py)"
    - "asyncio.to_thread wrapper for sync supabase-py inside critical sections"
    - "INSERT ... ON CONFLICT DO NOTHING via supabase upsert(on_conflict, ignore_duplicates=True)"
    - "Counts-only logging discipline (B4 / D-18 / D-41) — never real_value, only counts + UUID thread_id + type(e).__name__"
key-files:
  created: []
  modified:
    - backend/app/services/redaction/registry.py (+113 lines; final 241 lines)
    - backend/app/services/redaction/__init__.py (+5 lines net; final 37 lines)
decisions:
  - "Option (b) honored: de_anonymize_text NOT re-exported from redaction/__init__.py — stays a RedactionService method per D-39 + Phase 1 B2-option-B circular-import posture"
  - "Closure-based query construction (_select / _upsert) — never pass a pre-built supabase-py chain to asyncio.to_thread (chain builder is not thread-safe)"
  - "First-write-wins in-memory update after successful upsert — matches ON CONFLICT DO NOTHING DB semantics"
  - "Live verified against real Supabase project qedhulpfezucnfadlfiz: load() of a fresh UUID returns empty registry without raising (REG-01-compliant)"
metrics:
  duration: "2m 14s"
  completed: "2026-04-26"
  tasks_completed: 2
  files_modified: 2
  commits: 2
---

# Phase 02 Plan 04: Registry DB Methods + Re-exports Summary

DB-backed `ConversationRegistry.load(thread_id)` + `upsert_delta(deltas)` added to the existing skeleton against the live `entity_registry` table; `ConversationRegistry` and `EntityMapping` re-exported from `app.services.redaction` (with `de_anonymize_text` deliberately NOT re-exported per D-39 option b).

## Objective Achieved

Added the DB-backed surface to `ConversationRegistry`:
- `async classmethod load(thread_id)` → one SELECT against `public.entity_registry`, returns a populated instance (or empty for a brand-new thread per REG-01).
- `async upsert_delta(deltas)` → one INSERT … ON CONFLICT (thread_id, real_value_lower) DO NOTHING; empty list = zero DB hops; raises on DB error.

Re-exported `ConversationRegistry` + `EntityMapping` from `backend/app/services/redaction/__init__.py`. Plan 02-05 (`redaction_service.py` wiring) can now import these via the sub-package surface cleanly.

## What Was Built

### Task 1 — `backend/app/services/redaction/registry.py` (commit `abe7c55`)

**Imports added (file top, after existing `from __future__`):**
```python
import asyncio
...
from app.database import get_supabase_client
```

**`ConversationRegistry.load` — new async classmethod, inserted after `__init__`, before the `thread_id` property:**
```python
@classmethod
async def load(cls, thread_id: str) -> "ConversationRegistry":
    client = get_supabase_client()                     # service-role per D-25

    def _select() -> list[dict]:
        res = (
            client.table("entity_registry")
            .select("real_value,real_value_lower,surrogate_value,entity_type,source_message_id")
            .eq("thread_id", thread_id)
            .execute()
        )
        return list(res.data or [])

    raw_rows = await asyncio.to_thread(_select)        # one DB call, one event-loop yield
    rows = [EntityMapping(**r) for r in raw_rows]
    logger.debug("registry.load: thread_id=%s rows=%d", thread_id, len(rows))
    return cls(thread_id=thread_id, rows=rows)
```

**`ConversationRegistry.upsert_delta` — new async method, inserted after `forbidden_tokens()`, before `__repr__`:**
```python
async def upsert_delta(self, deltas: list[EntityMapping]) -> None:
    if not deltas:
        return                                          # zero-DB-hop fast path

    client = get_supabase_client()
    rows = [{...} for m in deltas]                      # explicit dict per row

    def _upsert() -> None:
        (
            client.table("entity_registry")
            .upsert(rows, on_conflict="thread_id,real_value_lower", ignore_duplicates=True)
            .execute()
        )

    try:
        await asyncio.to_thread(_upsert)
    except Exception as e:
        logger.error("registry.upsert_delta failed: thread_id=%s deltas=%d error_type=%s",
                     self._thread_id, len(deltas), type(e).__name__)
        raise                                            # NOT fire-and-forget — REG-04 invariant

    # First-write-wins in-memory update
    for m in deltas:
        if m.real_value_lower not in self._by_lower:
            self._rows.append(m)
            self._by_lower[m.real_value_lower] = m

    logger.debug("registry.upsert_delta: thread_id=%s wrote=%d size_after=%d", ...)
```

**registry.py final stats:** 241 lines (was 128; min 130 satisfied).

### Task 2 — `backend/app/services/redaction/__init__.py` (commit `865cec2`)

**Diff (only the bottom of the file changed; the B2 option B comment block L1-25 preserved verbatim):**
```diff
 from app.services.redaction.errors import RedactionError
+from app.services.redaction.registry import ConversationRegistry, EntityMapping

-__all__ = ["RedactionError"]
+__all__ = [
+    "RedactionError",
+    "ConversationRegistry",
+    "EntityMapping",
+]
```

**__init__.py final stats:** 37 lines (was 32). Net +5 lines; the comment block above the imports is byte-for-byte identical.

## Open-Question Resolution

**Phase 2 CONTEXT.md "Integration Points" → option (b) chosen — `de_anonymize_text` NOT re-exported here.**

Rationale (carried forward from D-39 + the existing B2 option B docstring):
- `de_anonymize_text` is a **method** on `RedactionService`, not a free function — re-exporting service methods through the sub-package would re-introduce the documented circular import (`__init__ → redaction_service → anonymization → detection → uuid_filter → __init__`).
- Callers reach it via `get_redaction_service().de_anonymize_text(...)`, the same way they reach `redact_text(...)`.
- Plan 02-05 implements `de_anonymize_text` as a method on `RedactionService` in `redaction_service.py`, NOT here.
- Negative check enforced and passing: `'de_anonymize_text' not in app.services.redaction.__all__`.

CONTEXT.md "Claude's Discretion" §3 explicitly permits this resolution.

## Verification Results

| Check | Status | Evidence |
|---|---|---|
| `load` is `async classmethod` | PASS | `inspect.iscoroutinefunction(ConversationRegistry.load.__func__)` returned True |
| `upsert_delta` is async | PASS | `inspect.iscoroutinefunction(ConversationRegistry.upsert_delta)` returned True |
| Empty `upsert_delta` short-circuits | PASS | `await r.upsert_delta([])` returns None with zero DB calls (asserted in verify command) |
| Exactly one SELECT per `load()` | PASS | source: `_select` closure has one `.execute()`; live smoke confirms |
| Exactly one INSERT per non-empty `upsert_delta()` | PASS | source: `_upsert` closure has one `.execute()` |
| Service-role client only (no `get_supabase_authed_client`) | PASS | `grep -c get_supabase_authed_client backend/app/services/redaction/registry.py` → 0 |
| `on_conflict="thread_id,real_value_lower"` + `ignore_duplicates=True` | PASS | both literal strings present |
| Raises on DB error (not swallowed) | PASS | `raise` after `logger.error` inside `except` |
| Re-exports: `ConversationRegistry`, `EntityMapping` | PASS | `from app.services.redaction import ConversationRegistry, EntityMapping` succeeds |
| `de_anonymize_text` NOT re-exported | PASS | `'de_anonymize_text' not in r.__all__` asserted; `set(r.__all__) == {RedactionError, ConversationRegistry, EntityMapping}` asserted |
| B2 option B comment block preserved verbatim | PASS | L1-25 byte-identical (only L29-36 diff) |
| Backend imports cleanly | PASS | `python -c "from app.main import app; print('OK')"` returns OK |
| **Phase 1 regression (20 tests)** | **PASS — 20/20** | `pytest tests/api/test_redaction.py -q` → "20 passed, 12 warnings in 1.20s" |
| Live DB read smoke (read-only, non-destructive) | PASS | `await ConversationRegistry.load(<fresh UUID>)` returned empty registry against real Supabase project `qedhulpfezucnfadlfiz` |

## Deviations from Plan

None — plan executed exactly as written. All hard rules from the plan's `<action>` block satisfied (async classmethod load, asyncio.to_thread wrapper in BOTH methods, service-role client only, on_conflict + ignore_duplicates, empty-list short-circuit, raise on error, in-memory state updated after successful write, counts-only logging).

The optional bonus live smoke (load() against the real DB with a fresh UUID) succeeded — extra confidence beyond the plan's required automated verification.

## Files Changed

| File | Change | Final Lines | Commit |
|---|---|---|---|
| `backend/app/services/redaction/registry.py` | +113 lines (load + upsert_delta + 2 imports) | 241 | `abe7c55` |
| `backend/app/services/redaction/__init__.py` | +5 net lines (1 import + 4 __all__ entries) | 37 | `865cec2` |

## Commits

- `abe7c55` — `feat(02-04): add ConversationRegistry.load() and upsert_delta()`
- `865cec2` — `feat(02-04): re-export ConversationRegistry and EntityMapping`

## What's Next

Plan 02-05 (`redaction_service.py` wiring): Wave 4. Now unblocked.
- Widens `RedactionService.redact_text(text)` → `redact_text(text, registry: ConversationRegistry | None = None)`.
- Adds `RedactionService.de_anonymize_text(text, registry)` (placeholder-tokenized 1-phase per D-34).
- Adds module-level `_thread_locks: dict[str, asyncio.Lock]` + `_get_thread_lock` helper.
- Threads `registry` through `anonymize(...)` to expand the per-call forbidden-token set with `registry.forbidden_tokens()` (D-37).

Phase 2 progress: 4/6 plans complete (Waves 1+2+3 ✓; W4 + W5 remain).

## Self-Check: PASSED

Verified after writing this SUMMARY:
- FOUND: backend/app/services/redaction/registry.py (241 lines)
- FOUND: backend/app/services/redaction/__init__.py (37 lines)
- FOUND commit abe7c55: `feat(02-04): add ConversationRegistry.load() and upsert_delta()`
- FOUND commit 865cec2: `feat(02-04): re-export ConversationRegistry and EntityMapping`
- Phase 1 regression: 20/20 tests passing
- Live load() smoke against real Supabase: PASS
