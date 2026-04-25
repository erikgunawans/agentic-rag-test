---
phase: 02-conversation-scoped-registry-and-round-trip
plan: 05
type: execute
wave: 4
depends_on: [02, 04]
files_modified:
  - backend/app/services/redaction/anonymization.py
  - backend/app/services/redaction_service.py
autonomous: true
requirements: [REG-04, DEANON-01, DEANON-02, PERF-03]
must_haves:
  truths:
    - "redact_text(text) (Phase 1 default — registry=None) behaves exactly as before"
    - "redact_text(text, registry=...) reuses existing surrogates from registry, expands forbidden tokens thread-wide, and persists deltas"
    - "Module-level _thread_locks dict + _thread_locks_master serialise concurrent writers per thread_id (PERF-03)"
    - "de_anonymize_text(text, registry) round-trips surrogates → real values, case-insensitive, longest-match-first, hard-redact placeholders pass through"
    - "All new code paths log counts only — never real values (B4 / D-18 / D-41)"
  artifacts:
    - path: "backend/app/services/redaction/anonymization.py"
      provides: "anonymize() now accepts registry param for thread-wide forbidden tokens + per-thread surrogate reuse"
    - path: "backend/app/services/redaction_service.py"
      provides: "Widened redact_text signature, new de_anonymize_text method, _thread_locks state, _get_thread_lock helper"
      exports: ["RedactionService", "RedactionResult", "get_redaction_service"]
  key_links:
    - from: "backend/app/services/redaction_service.py"
      to: "backend/app/services/redaction/registry.ConversationRegistry"
      via: "redact_text + de_anonymize_text accept registry param"
      pattern: "registry: ConversationRegistry"
    - from: "backend/app/services/redaction_service.py"
      to: "module-level _thread_locks dict"
      via: "_get_thread_lock(thread_id)"
      pattern: "_thread_locks\\[thread_id\\]"
    - from: "backend/app/services/redaction/anonymization.py"
      to: "registry.lookup + registry.forbidden_tokens"
      via: "thread-wide collision avoidance + surrogate reuse"
      pattern: "registry\\.(lookup|forbidden_tokens)"
---

<objective>
Wire the registry into Phase 1's `RedactionService` and `anonymize()` function. Three discrete additions:

1. `anonymization.py` — accept a `registry` keyword argument; expand forbidden tokens thread-wide; reuse existing surrogate when registry already has the real value.
2. `redaction_service.py` — module-level `_thread_locks` dict + master lock; `_get_thread_lock` helper; widen `redact_text` to `(text, registry=None)`; add `de_anonymize_text(text, registry)`.
3. Preserve Phase 1 behaviour exactly when `registry is None` (D-39: registry=None ⇒ stateless legacy path; the existing 20 tests must still pass).

Purpose: This is the heart of Phase 2. After this plan lands, the redaction pipeline is round-trip capable and the registry is the single source of truth for "same real → same surrogate".

Output: Two file modifications. anonymization.py grows by ~30 lines (forbidden-token expansion + lookup-first branch). redaction_service.py grows by ~80 lines (module state + 2 new helpers + de_anonymize_text method + restructured redact_text).

**Wave-4 dependency note (B-1):** This plan depends on BOTH Plan 02 (skeleton — provides `ConversationRegistry.__init__`, `lookup`, `entries`, `forbidden_tokens`) AND Plan 04 (DB methods — provides `ConversationRegistry.load(thread_id)` classmethod and `await registry.upsert_delta(deltas)` method). The wiring code below calls BOTH `await registry.upsert_delta(deltas)` (added by Plan 04) AND uses the skeleton members (added by Plan 02), so this plan cannot run before Plan 04 has landed.
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
@backend/app/services/redaction/anonymization.py
@backend/app/services/redaction/registry.py
@backend/app/services/redaction/name_extraction.py
@backend/app/services/tracing_service.py

<interfaces>
<!-- Existing primitives this plan calls. Read once; no codebase exploration needed. -->

From backend/app/services/redaction/registry.py (Plan 02 + Plan 04):
```python
class EntityMapping(BaseModel):
    real_value: str
    real_value_lower: str
    surrogate_value: str
    entity_type: str  # PERSON / EMAIL_ADDRESS / PHONE_NUMBER / LOCATION / DATE_TIME / URL / IP_ADDRESS
    source_message_id: str | None = None

class ConversationRegistry:
    @property
    def thread_id(self) -> str: ...
    @classmethod
    async def load(cls, thread_id: str) -> "ConversationRegistry": ...   # added by Plan 04
    def lookup(self, real_value: str) -> str | None: ...
    def entries(self) -> list[EntityMapping]: ...
    def forbidden_tokens(self) -> set[str]: ...
    async def upsert_delta(self, deltas: list[EntityMapping]) -> None: ...   # added by Plan 04
```

From backend/app/services/redaction/anonymization.py L183-243 (Phase 1 — block to expand):
```python
def anonymize(masked_text: str, entities: list[Entity]) -> tuple[str, dict[str, str], int]:
    faker = get_faker()
    real_persons = [e.text for e in entities if e.type == "PERSON"]
    bare_persons = [strip_honorific(name)[1] for name in real_persons]
    forbidden_tokens = extract_name_tokens(bare_persons)
    entity_map: dict[str, str] = {}
    used_surrogates: set[str] = set()
    hard_redacted_count = 0
    out = masked_text
    # ... iteration (right-to-left), Faker generation with retry budget ...
```

From backend/app/services/redaction_service.py (Phase 1 anchors):
- L32-53: imports block
- L58-84: `class RedactionResult(BaseModel)` (frozen Pydantic)
- L106: `@traced(name="redaction.redact_text")`
- L106-107: `async def redact_text(self, text: str) -> RedactionResult:` (the signature Phase 1 D-14 promised would widen)
- L130-160: redact_text body (entity detection → anonymize → assemble RedactionResult)
- L163-172: `@lru_cache` `get_redaction_service()` singleton getter

From backend/app/services/tracing_service.py L129-153:
- `@traced(name="...")` decorator pattern; `time.perf_counter()` for latency capture
</interfaces>
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: Extend anonymize() in anonymization.py with registry-aware forbidden tokens and surrogate reuse</name>
  <files>backend/app/services/redaction/anonymization.py</files>
  <read_first>
    - backend/app/services/redaction/anonymization.py L1-260 (full Phase 1 file — read in one pass; the executor edits L183-243 specifically)
    - backend/app/services/redaction/registry.py (Plan 04 output — confirms `lookup()` returns `str | None` and `forbidden_tokens()` returns `set[str]`)
    - backend/app/services/redaction/name_extraction.py L35-67 (extract_name_tokens / strip_honorific signatures — unchanged in Phase 2)
    - .planning/phases/02-conversation-scoped-registry-and-round-trip/02-PATTERNS.md §"backend/app/services/redaction/anonymization.py (MODIFY)"
    - .planning/phases/02-conversation-scoped-registry-and-round-trip/02-CONTEXT.md decisions D-37, D-38, D-39, REG-04 / D-32 (surrogate reuse)
    - .planning/phases/01-detection-anonymization-foundation/01-CONTEXT.md D-07 (per-call surname/first-name forbidden token check — Phase 2 EXPANDS this; do NOT rewrite)
  </read_first>
  <action>
EDIT `backend/app/services/redaction/anonymization.py`. Make THREE surgical changes (do not rewrite the function — diff-edit the specific blocks).

(A) Function signature — change L183-186 to accept a forward-ref `registry` keyword:

```python
# CURRENT (Phase 1):
def anonymize(
    masked_text: str,
    entities: list[Entity],
) -> tuple[str, dict[str, str], int]:
```

becomes:

```python
# PHASE 2:
def anonymize(
    masked_text: str,
    entities: list[Entity],
    registry: "ConversationRegistry | None" = None,
) -> tuple[str, dict[str, str], int]:
```

The forward-ref string `"ConversationRegistry | None"` is INTENTIONAL — it avoids a runtime import cycle if `registry.py` ever transitively imports `anonymization.py`. Do NOT add a top-level `from app.services.redaction.registry import ConversationRegistry`. If a TYPE_CHECKING import is desired for IDE accuracy, add it under `if TYPE_CHECKING:`:

```python
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.services.redaction.registry import ConversationRegistry
```

Update the docstring "Args:" block to document the new parameter — same wording as registry.py:
"`registry` — when supplied, the per-thread cross-call collision check expands its forbidden-token set with `registry.forbidden_tokens()` and existing real-value surrogates are reused (REG-04 / D-32 / D-37)."

(B) Forbidden-tokens expansion — locate the existing line near L207 that reads (verbatim Phase 1):
```python
forbidden_tokens = extract_name_tokens(bare_persons)
```

Replace that single line with this 5-line block (D-37 / D-38):

```python
# D-07 / D-37: per-call ∪ per-thread forbidden-token set. Per-PERSON only (D-38).
call_forbidden = extract_name_tokens(bare_persons)
if registry is not None:
    forbidden_tokens = call_forbidden | registry.forbidden_tokens()
else:
    forbidden_tokens = call_forbidden
```

DO NOT modify the existing Faker generation/retry block downstream — the `forbidden_tokens` variable name is preserved so the existing collision-check logic at L222-232 (Phase 1) keeps working unchanged.

(C) Per-thread surrogate reuse — find the per-entity iteration loop (the `for ent in ...` block where Faker generates a surrogate). IMMEDIATELY BEFORE the `if ent.type == "PERSON":` Faker-generation branch (Phase 1 anonymization.py L222-232 area), add a registry-lookup short-circuit:

```python
# REG-04 / D-32: if the registry already has this real value, reuse the
# existing surrogate and skip Faker generation entirely. Add to entity_map
# so the caller (redact_text) can still observe what was substituted in
# THIS call, but the delta computation will exclude it (real_value already
# in registry._by_lower).
if registry is not None:
    hit = registry.lookup(ent.text)
    if hit is not None:
        entity_map[ent.text] = hit
        out = out[: ent.start] + hit + out[ent.end :]
        continue
```

Place this `if registry is not None:` block at the TOP of the per-entity iteration body (right after the entity_type filtering / honorific handling that Phase 1 does, BEFORE Faker is called). The `continue` skips all Phase 1 logic for that entity.

Critical: the `entity_map[ent.text] = hit` line uses the EXISTING `entity_map` shape Phase 1 returns (`dict[str, str]`). Plan 05 Task 2 (redaction_service.py) computes the delta against `registry.entries()` to figure out what to upsert. Don't try to mark "registry hits" separately here — the delta is computed in the caller.

**Post-condition invariant for Task 2 to rely on (W-2):** After `anonymize(masked_text, entities, registry=...)` returns, EVERY key in `entity_map` is precisely `Entity.text` for some `Entity` in the input `entities` list. Phase 1's anonymize() already maintains this — Phase 2 preserves it because the new short-circuit also assigns via `entity_map[ent.text] = hit` (using `ent.text` as the key). This invariant is what makes the `entity_map` → `Entity.type` lookup in Task 2 deterministic.

After all three edits, run the smoke test:
```bash
cd backend && source venv/bin/activate && python -c "from app.services.redaction.anonymization import anonymize; import inspect; sig = inspect.signature(anonymize); assert 'registry' in sig.parameters; assert sig.parameters['registry'].default is None; print('SIG_OK')"
```

And confirm Phase 1 still passes (registry default is None ⇒ identical behaviour):
```bash
cd backend && source venv/bin/activate && pytest backend/tests/api/test_redaction.py -q
```
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && python -c "from app.services.redaction.anonymization import anonymize; import inspect; sig = inspect.signature(anonymize); assert 'registry' in sig.parameters; assert sig.parameters['registry'].default is None; print('OK')" && cd backend && pytest tests/api/test_redaction.py -q --tb=short 2>&1 | tail -5</automated>
  </verify>
  <acceptance_criteria>
    - `anonymize()` signature includes `registry: "ConversationRegistry | None" = None` (or equivalent forward-ref string with default None).
    - File contains literal `call_forbidden = extract_name_tokens(bare_persons)` AND a union expression `call_forbidden | registry.forbidden_tokens()`.
    - File contains literal `registry.lookup(ent.text)` (per-thread surrogate reuse).
    - File contains literal `entity_map[ent.text] = hit` followed by `continue` (skips Faker for registry hits).
    - File does NOT contain a top-level `from app.services.redaction.registry import ConversationRegistry` (forward-ref only — break-import-cycle invariant).
    - Phase 1 tests still pass: `pytest backend/tests/api/test_redaction.py -q` exits 0 with 20 passed.
    - The verify automated command prints `OK` and the pytest summary line shows `20 passed` (or higher if Plan 02/04 added imports — but no NEW failures).
  </acceptance_criteria>
  <done>The `anonymize()` function is registry-aware. Phase 1 default behaviour preserved (registry=None ⇒ identical legacy path). Plan 05 Task 2 can now thread `registry` through from redact_text.</done>
</task>

<task type="auto" tdd="false">
  <name>Task 2: Wire ConversationRegistry into redaction_service.py — locks, redact_text widening, de_anonymize_text</name>
  <files>backend/app/services/redaction_service.py</files>
  <read_first>
    - backend/app/services/redaction_service.py L1-180 (full file — read in one pass to see the orchestration shape; do not re-read)
    - backend/app/services/redaction/registry.py (Plan 04 — confirms ConversationRegistry / EntityMapping public surface)
    - backend/app/services/redaction/anonymization.py (Task 1 output — confirms the new `registry` parameter exists)
    - backend/app/services/tracing_service.py L129-153 (@traced decorator + perf_counter idiom)
    - .planning/phases/02-conversation-scoped-registry-and-round-trip/02-PATTERNS.md §"backend/app/services/redaction_service.py (MODIFY)" — Anchors #1 through #6 with exact insertion points
    - .planning/phases/02-conversation-scoped-registry-and-round-trip/02-CONTEXT.md decisions D-29, D-30, D-31, D-34, D-35, D-39, D-40, D-41
  </read_first>
  <action>
EDIT `backend/app/services/redaction_service.py`. SIX surgical changes:

(A) Imports — add at the top of the imports block (after `from functools import lru_cache`):
```python
import asyncio
import re
```
And add (alongside other `app.services.redaction.*` imports):
```python
from app.services.redaction.registry import ConversationRegistry, EntityMapping
```

If the linter complains about `re` being only used inside `de_anonymize_text`, leave it module-scoped anyway — it's a stdlib import and the latency win is real.

(B) Module-level state — insert AFTER the imports block, BEFORE `class RedactionResult` (around L55):

```python
# D-29 (PERF-03): per-process asyncio.Lock keyed by thread_id.
# NOTE (D-31, FUTURE-WORK Phase 6): UPGRADE PATH for multi-worker / multi-instance
# Railway deploys is `pg_advisory_xact_lock(hashtext(thread_id))` — see
# `.planning/STATE.md` "Pending Items" → "Async-lock cross-process upgrade".
# asyncio.Lock is correct only while Railway runs a single Uvicorn worker.
_thread_locks: dict[str, asyncio.Lock] = {}
_thread_locks_master: asyncio.Lock = asyncio.Lock()
```

CRITICAL: do NOT instantiate `_thread_locks_master` lazily inside a function. Module-level instantiation is correct because the module is imported under the running asyncio loop in FastAPI's lifespan; instantiating an `asyncio.Lock` at module load time binds it to the current loop. (For pytest-asyncio, each test creates a fresh loop — Plan 06's autouse fixture clears `_thread_locks` AND rebinds `_thread_locks_master` to the per-test loop so this is harmless.)

(C) `_get_thread_lock` private helper — add as a method on `RedactionService` (NOT a free function — keeps `self` available for the @traced span context); insert after the existing `__init__` / before `redact_text`:

```python
    async def _get_thread_lock(self, thread_id: str) -> asyncio.Lock:
        """D-29: get-or-create the asyncio.Lock for this thread.

        Held briefly under `_thread_locks_master` to make get-or-create atomic
        across coroutines. Returned lock is acquired by the caller.
        """
        async with _thread_locks_master:
            lock = _thread_locks.get(thread_id)
            if lock is None:
                lock = asyncio.Lock()
                _thread_locks[thread_id] = lock
            return lock
```

(D) Widen `redact_text` signature — change L106-107:

CURRENT:
```python
@traced(name="redaction.redact_text")
async def redact_text(self, text: str) -> RedactionResult:
```

PHASE 2:
```python
@traced(name="redaction.redact_text")
async def redact_text(
    self,
    text: str,
    registry: ConversationRegistry | None = None,
) -> RedactionResult:
```

Refactor the body to dispatch based on `registry`:

```python
    @traced(name="redaction.redact_text")
    async def redact_text(
        self,
        text: str,
        registry: ConversationRegistry | None = None,
    ) -> RedactionResult:
        """Detect + anonymize PII in `text`. (Phase 1: D-13 / D-14; Phase 2: D-39.)

        When `registry is None`, behaviour is identical to Phase 1 — stateless,
        fresh in-memory state per call.

        When `registry` is supplied, the call is wrapped in a per-thread
        asyncio.Lock (D-29 / D-30) and:
          - existing real values reuse their stored surrogate (REG-04)
          - Faker generation honours both per-call AND per-thread forbidden
            tokens (D-37)
          - newly-introduced mappings are upserted to the entity_registry
            table inside the critical section (D-32)
        """
        if registry is None:
            # D-39: stateless legacy path. Phase 1 body unchanged.
            return await self._redact_text_stateless(text)

        # D-29 / D-30: lock spans detect → generate → upsert.
        lock = await self._get_thread_lock(registry.thread_id)
        t_lock_start = time.perf_counter()
        async with lock:
            lock_wait_ms = (time.perf_counter() - t_lock_start) * 1000.0
            size_before = len(registry.entries())
            result = await self._redact_text_with_registry(text, registry)
            size_after = len(registry.entries())
            logger.debug(
                "redaction.redact_text(registry): thread_id=%s size_before=%d size_after=%d lock_wait_ms=%.2f writes=%d",
                registry.thread_id,
                size_before,
                size_after,
                lock_wait_ms,
                size_after - size_before,
            )
            return result
```

(E) Extract Phase 1 body into `_redact_text_stateless` and add new `_redact_text_with_registry`. The Phase 1 body of `redact_text` (currently L130-160 verbatim — entity detection, anonymize call, RedactionResult assembly) is moved into a new private helper `_redact_text_stateless(self, text)` with NO behavioural change. Then add the new `_redact_text_with_registry`:

**Variables in scope at the delta-computation point (W-2 explicit list):** Inside `_redact_text_with_registry`, before the delta loop runs, the following local variables MUST be defined (they are produced by mirroring the stateless detection + anonymize body):
- `t0: float` — `time.perf_counter()` captured at function entry (used for `latency_ms`).
- `entities: list[Entity]` — output of the same detection step the stateless path uses (Presidio detect → Entity list).
- `masked_text: str` — masked-text intermediate produced by the detection step.
- `anonymized_text: str` — first element of the tuple returned by `anonymize(masked_text, entities, registry=registry)`.
- `entity_map: dict[str, str]` — second element; keys are real values (precisely `Entity.text` for some Entity in `entities` — invariant established by Task 1).
- `hard_redacted_count: int` — third element.
- `sentinels` (only if Phase 1's stateless body uses it; named here for parity — preserve whatever name the stateless path uses, do NOT rename).

If the executor refactors detection into a shared `_detect_and_anonymize`, these same variables MUST flow out of that helper into `_redact_text_with_registry` (e.g. as a tuple return).

```python
    async def _redact_text_stateless(self, text: str) -> RedactionResult:
        """Phase 1 stateless redact path — body unchanged from L130-160."""
        # ... EXACTLY the existing Phase 1 body, renamed; do not modify ...

    async def _redact_text_with_registry(
        self,
        text: str,
        registry: ConversationRegistry,
    ) -> RedactionResult:
        """Registry-aware redact path. Caller holds the per-thread lock.

        Calls `anonymize(text, entities, registry=registry)` so that:
          - existing surrogates are reused via `registry.lookup()`
          - forbidden tokens for Faker honour `registry.forbidden_tokens()`
        Then computes the delta (entries in entity_map whose real_value_lower
        is not already in registry._by_lower) and persists it via
        `await registry.upsert_delta(deltas)`.

        IMPORTANT: this method imports the SAME entity-detection helpers the
        stateless path uses — only the anonymize() call is swapped. Do NOT
        duplicate detection logic; refactor the shared body into a private
        helper if needed.
        """
        # ... mirror the body of _redact_text_stateless, but pass registry= to anonymize() ...

        # === Delta computation (W-2 explicit) ===
        # entity_map keys are real values; per Task 1's post-condition every key
        # is precisely `Entity.text` for some Entity in `entities`.  Build a
        # text→Entity index ONCE so the delta loop is O(n) instead of O(n*m).
        entity_index: dict[str, "Entity"] = {e.text: e for e in entities}

        deltas: list[EntityMapping] = []
        for real_value, surrogate in entity_map.items():
            real_lower = real_value.casefold()
            if real_lower in registry._by_lower:
                continue  # already persisted (registry.lookup() hit during anonymize)
            ent = entity_index.get(real_value)
            # Invariant: anonymize() never produces an entity_map key that isn't
            # an Entity.text in `entities`. If this assertion fires, anonymize()
            # has regressed (Phase 1 D-07 contract violation) — surface, do not
            # mask with "UNKNOWN".
            assert ent is not None, (
                f"anonymize() produced entity_map key with no matching Entity: "
                f"thread_id={registry.thread_id!r} key_len={len(real_value)}"
            )
            deltas.append(
                EntityMapping(
                    real_value=real_value,
                    real_value_lower=real_lower,
                    surrogate_value=surrogate,
                    entity_type=ent.type,
                    source_message_id=None,  # Phase 5 chat router backfills
                )
            )
        if deltas:
            await registry.upsert_delta(deltas)
        return RedactionResult(
            anonymized_text=anonymized_text,
            entity_map=entity_map,
            hard_redacted_count=hard_redacted_count,
            latency_ms=(time.perf_counter() - t0) * 1000.0,
        )
```

The placeholder comments (`# ... mirror the body ...`) MUST be replaced with actual code copied/adapted from `_redact_text_stateless`. The detection step yields `entities` (a list of `Entity` instances) and `masked_text`; the anonymize call is the ONLY changed line. Sketch of the actual body:

```python
        t0 = time.perf_counter()
        # Same detection step as _redact_text_stateless (mirror the Phase 1 body).
        # Look at L130-160 of the existing file and copy the detection / masked_text
        # construction verbatim. The ONLY swap is:
        #     anonymized_text, entity_map, hard_redacted_count = anonymize(masked_text, entities)
        # becomes:
        #     anonymized_text, entity_map, hard_redacted_count = anonymize(
        #         masked_text, entities, registry=registry,
        #     )
```

If the executor finds the duplication awkward, an acceptable alternative is to add a single private `_detect_and_anonymize(text, registry)` that both paths call, with `_redact_text_stateless` passing `registry=None`. Either shape is fine; the invariants are: (1) Phase 1's stateless behaviour identical when `registry is None`, (2) registry-aware path passes `registry=` to `anonymize()`, (3) deltas computed against `registry._by_lower` and persisted via `await registry.upsert_delta(deltas)`, (4) every delta's `entity_type` matches `Entity.type` from the same `redact_text` call (NEVER the literal `"UNKNOWN"` — Phase 1's anonymize-contract guarantees the index lookup succeeds for non-empty entity_map).

(F) `de_anonymize_text` — NEW public method (D-34). Add immediately after the `_redact_text_with_registry` helper:

```python
    @traced(name="redaction.de_anonymize_text")
    async def de_anonymize_text(
        self,
        text: str,
        registry: ConversationRegistry,
    ) -> str:
        """D-34: 1-phase placeholder-tokenized round-trip.

        Forward-compat with Phase 4's 3-phase fuzzy upgrade — Phase 4 will
        insert its fuzzy-match pass between the placeholder-substitution
        pass and the final resolve pass without rewriting this call site
        (FR-5.4).

        D-35: hard-redact placeholders pass through unchanged because they
        are never present in the registry (REG-05 / D-24).
        """
        t0 = time.perf_counter()
        entries = registry.entries()
        # Sort by len(surrogate_value) DESC — longest match wins, prevents
        # partial-overlap corruption when surrogates share token prefixes.
        entries_sorted = sorted(
            entries,
            key=lambda m: len(m.surrogate_value),
            reverse=True,
        )

        # Pass 1: surrogate -> placeholder token (case-insensitive per DEANON-02).
        out = text
        placeholders: dict[str, str] = {}
        for i, m in enumerate(entries_sorted):
            token = f"<<PH_{i:04d}>>"
            out, n = re.subn(
                re.escape(m.surrogate_value),
                token,
                out,
                flags=re.IGNORECASE,
            )
            if n > 0:
                placeholders[token] = m.real_value  # original casing preserved (D-36)

        # Pass 2: placeholder -> real_value.
        resolved = 0
        for token, real in placeholders.items():
            out, n = re.subn(re.escape(token), real, out)
            resolved += n

        latency_ms = (time.perf_counter() - t0) * 1000.0
        logger.debug(
            "redaction.de_anonymize_text: text_len=%d surrogate_count=%d placeholders_resolved=%d ms=%.2f",
            len(text),
            len(entries),
            resolved,
            latency_ms,
        )
        return out
```

Hard rules — verify after editing:

- `redact_text` signature is `(self, text: str, registry: ConversationRegistry | None = None) -> RedactionResult` (NOT positional-only; must accept keyword).
- When `registry is None`, the call dispatches to `_redact_text_stateless` and the Phase 1 body is unchanged (verify: pytest_phase1 must still pass).
- When `registry is not None`, the lock-then-process flow is in place. The lock is acquired BEFORE detection AND released AFTER upsert (D-30 lock-spans-everything invariant).
- `de_anonymize_text` MUST sort entries by `len(surrogate_value)` DESC before the regex pass.
- `de_anonymize_text` MUST use `re.IGNORECASE` (DEANON-02).
- `de_anonymize_text` MUST use the placeholder format `<<PH_xxxx>>` zero-padded width 4 (Claude's Discretion §2 — chose zero-pad for lexicographic stability).
- All new logger lines use `%s` / `%d` / `%.2f` and contain ZERO real values (B4 / D-18 / D-41).
- BOTH new public methods (`redact_text` is widened; `de_anonymize_text` is new) carry the `@traced(name="redaction.<op>")` decorator (D-18 / D-41). Private helpers (`_get_thread_lock`, `_redact_text_stateless`, `_redact_text_with_registry`) do NOT — keeps span volume bounded.
- The `redaction_service.RedactionService` class must remain compatible with `@lru_cache get_redaction_service()` — do NOT remove the singleton getter at L163-172.
- **W-2 invariant: every delta written by `_redact_text_with_registry` has `entity_type == ent.type` for the corresponding `Entity` in `entities`. The delta loop MUST use the `entity_index` (or equivalent dict-built-from-entities) — never the linear `next((e.type for e in entities if e.text == real_value), "UNKNOWN")` scan.**

After editing, run BOTH:
1. Backend imports cleanly: `cd backend && source venv/bin/activate && python -c "from app.main import app; print('IMPORT_OK')"`
2. Phase 1 regression: `cd backend && source venv/bin/activate && pytest backend/tests/api/test_redaction.py -q` — MUST be 20 passed.
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && python -c "from app.services.redaction_service import RedactionService, get_redaction_service; import inspect; sig = inspect.signature(RedactionService.redact_text); assert 'registry' in sig.parameters and sig.parameters['registry'].default is None, 'redact_text must accept registry kwarg with default None'; assert hasattr(RedactionService, 'de_anonymize_text'), 'de_anonymize_text must exist'; assert inspect.iscoroutinefunction(RedactionService.de_anonymize_text), 'de_anonymize_text must be async'; print('OK')" && cd backend && pytest tests/api/test_redaction.py -q --tb=short 2>&1 | tail -5</automated>
  </verify>
  <acceptance_criteria>
    - `redaction_service.py` contains `_thread_locks: dict[str, asyncio.Lock] = {}` at module scope.
    - `redaction_service.py` contains `_thread_locks_master: asyncio.Lock = asyncio.Lock()` at module scope.
    - `redaction_service.py` contains literal `D-31` in a comment (FUTURE-WORK note present at the locks declaration).
    - `RedactionService.redact_text` signature accepts `registry: ConversationRegistry | None = None`.
    - `RedactionService.de_anonymize_text` exists and is `async`.
    - `RedactionService.de_anonymize_text` is decorated with `@traced(name="redaction.de_anonymize_text")`.
    - File contains literal `<<PH_` (placeholder format used).
    - File contains `re.IGNORECASE` (DEANON-02 honored).
    - File contains `key=lambda m: len(m.surrogate_value)` AND `reverse=True` (longest-match-first).
    - `_get_thread_lock` exists as a method on `RedactionService` and uses `_thread_locks_master`.
    - File contains `await registry.upsert_delta(deltas)` (delta persistence inside lock).
    - File contains a dict-keyed entity-index expression matching `\{[^}]*e\.text\s*:\s*e[^}]*\}` (entity_index pattern; W-2 — replaces the `next(...)` linear scan).
    - File does NOT contain the substring `"UNKNOWN"` in the delta-loop region (W-2 — fragile fallback removed).
    - **W-2 acceptance criterion**: For every delta written, `entity_type` matches the corresponding `Entity.type` from the same `redact_text` call (no `'UNKNOWN'` unless the entity-map key genuinely has no matching Entity — which never happens for non-empty entity_map under Phase 1's `anonymize()` contract; an `assert ent is not None` guards this invariant).
    - Phase 1 tests still pass: `pytest backend/tests/api/test_redaction.py -q` ⇒ 20 passed.
    - Backend imports cleanly: `python -c "from app.main import app"` ⇒ no exception.
    - The verify automated command prints `OK` and Phase 1 pytest summary shows `20 passed`.
  </acceptance_criteria>
  <done>The redaction service is fully Phase-2-capable. Stateless path preserves Phase 1 behaviour exactly; registry-aware path serialises via per-thread asyncio.Lock, reuses existing surrogates, persists deltas with correct entity_type per W-2, and exposes `de_anonymize_text` for round-trip. Plan 06 (tests) can now exercise the full surface.</done>
</task>

</tasks>

<verification>
- `cd backend && source venv/bin/activate && python -c "from app.main import app; print('OK')"` — backend imports cleanly (no circular dep introduced).
- `cd backend && source venv/bin/activate && pytest backend/tests/api/test_redaction.py -q` — Phase 1 regression: 20 passed (registry default of None preserves Phase 1 behaviour exactly per D-39).
- `grep -n "_thread_locks" backend/app/services/redaction_service.py` — at least 3 occurrences (declaration + master + helper usage).
- `grep -n "@traced" backend/app/services/redaction_service.py` — covers `redact_text` AND `de_anonymize_text` (2 new + Phase 1 carryover).
- `grep -n "registry: ConversationRegistry" backend/app/services/redaction_service.py` — at least 2 occurrences (redact_text signature + de_anonymize_text signature).
- `grep -n "UNKNOWN" backend/app/services/redaction_service.py` — returns 0 (W-2: fragile fallback removed; entity_index assertion replaces it).
</verification>

<success_criteria>
- D-29 / D-30 honored: per-thread asyncio.Lock spans detect→generate→upsert.
- D-34: de_anonymize_text uses placeholder-tokenized 1-phase pipeline forward-compatible with Phase 4.
- D-35: hard-redact placeholders pass through unchanged (will be tested in Plan 06; the design ensures this trivially because they are never in the registry).
- D-37 / D-38: thread-wide forbidden tokens flow through `anonymize(...registry=...)` correctly.
- D-39: registry=None ⇒ Phase 1 behaviour exactly. 20/20 Phase 1 tests still pass.
- D-41: spans + logs carry counts only, no real values.
- W-2: every persisted delta carries the correct Presidio `entity_type` derived from the same call's `entities` list (no `"UNKNOWN"` magic-string fallback).
</success_criteria>

<output>
Create `.planning/phases/02-conversation-scoped-registry-and-round-trip/02-05-SUMMARY.md` with:
- anonymization.py: signature change + 2 inline edits (forbidden expansion, lookup short-circuit)
- redaction_service.py: 6 changes (imports, module-locks, _get_thread_lock, redact_text widen + dispatcher, _redact_text_stateless extraction, _redact_text_with_registry, de_anonymize_text)
- Confirm 20/20 Phase 1 tests still pass.
- Note any structural choice: e.g. did the executor refactor detection into a shared `_detect_and_anonymize` helper, or duplicate the body? (Either is fine.)
- Confirm W-2 satisfied: entity_index dict used; no `"UNKNOWN"` literal in delta loop; assertion guards the invariant.
</output>
</content>
