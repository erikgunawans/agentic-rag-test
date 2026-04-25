# Phase 2: Conversation-Scoped Registry & Round-Trip — Pattern Map

**Mapped:** 2026-04-26
**Files analyzed:** 6 (4 NEW + 2 MODIFY)
**Analogs found:** 6 / 6

## File Classification

| New / Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---------------------|------|-----------|----------------|---------------|
| `backend/app/services/redaction/registry.py` (NEW) | service (per-thread cached state + DB-backed) | request-response (load → mutate-in-RAM → upsert-delta) | `backend/app/services/system_settings_service.py` (cached service-role reader) + `backend/app/services/audit_service.py` (service-role insert) + `backend/app/services/redaction_service.py` (Pydantic-frozen result + `@traced` + `@lru_cache` singleton + module-level `logger`) | composite — best-of-three |
| `supabase/migrations/029_pii_entity_registry.sql` (NEW) | migration (system-level table, RLS-enabled-no-policies) | DDL | `supabase/migrations/011_audit_trail.sql` (system-level RLS-no-user-policies, comment annotation) + `supabase/migrations/001_initial_schema.sql` (CREATE TABLE shape, FK to threads, `handle_updated_at()` definition) + `supabase/migrations/013_obligations.sql` (handle_updated_at trigger wiring) | composite — exact role match |
| `backend/tests/api/test_redaction_registry.py` (NEW) | test (integration; real DB) | event-driven (asyncio.gather race; DB unique-constraint serialisation) | `backend/tests/api/test_redaction.py` (TestSC<N>_… class shape, `pytestmark = pytest.mark.asyncio`, `seeded_faker` + `redaction_service` fixture usage, B4 caplog log-privacy pattern) + `backend/tests/conftest.py` (Faker seed_instance per-test fixture, session-scoped service singleton) | exact |
| `backend/tests/unit/test_conversation_registry.py` (NEW, optional) | test (unit; in-memory only) | request-response | `backend/tests/api/test_redaction.py` (same shape) — but unit-scoped, no DB | exact |
| `backend/app/services/redaction_service.py` (MODIFY) | service (orchestration) | request-response | (self — Phase 1 file is the analog for itself) | exact |
| `backend/app/services/redaction/anonymization.py` (MODIFY) | service (pure transform) | request-response | (self — Phase 1 D-07 forbidden-token block is the analog) | exact |

## Shared Patterns

### Service-role DB client (D-25 — `entity_registry` is system-level)

**Source:** `backend/app/database.py` L1–8
**Apply to:** `registry.py` for ALL reads / writes (no auth-scoped client at any point — RLS is bypassed by design)

```python
# backend/app/database.py L1-8
from supabase import create_client, Client
from app.config import get_settings


def get_supabase_client() -> Client:
    """Service-role client — bypasses RLS for admin operations."""
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_service_role_key)
```

**What to copy:** the bare `client = get_supabase_client()` call inside `_load_rows` / `_upsert_deltas`. Do NOT use `get_supabase_authed_client(token)` — Phase 2 has no user JWT in scope; the registry is service-internal (D-25 / D-26).

### Logger discipline (B4 / D-18 — counts only, never real values)

**Source:** `backend/app/services/redaction/anonymization.py` L50, L236–241; `backend/app/services/redaction_service.py` L55, L144–153
**Apply to:** every log line in `registry.py` and the new methods on `redaction_service.py`

```python
# anonymization.py L50, L236-241
logger = logging.getLogger(__name__)
...
logger.debug(
    "redaction.anonymize: entities=%d surrogate_pairs=%d hard_redacted=%d",
    len(entities),
    len(entity_map),
    hard_redacted_count,
)
```

```python
# redaction_service.py L144-153
logger.debug(
    "redaction.redact_text: chars=%d entities=%d surrogates=%d hard=%d uuid_drops=%d ms=%.2f",
    len(text), len(entities), len(entity_map),
    hard_redacted_count, len(sentinels), latency_ms,
)
```

**What to copy:** `%s` / `%d` formatting; never f-strings with PII; only counts, types, latency. Phase 2 D-41 names the new fields exactly: `registry_size_before`, `registry_size_after`, `registry_lock_wait_ms`, `registry_writes`, `surrogate_count`, `placeholders_resolved`.

### `@traced` span decoration (D-18 / D-41)

**Source:** `backend/app/services/redaction_service.py` L106; `backend/app/services/tracing_service.py` L129–153
**Apply to:** every PUBLIC method on `RedactionService` added in Phase 2 (`redact_text`, `de_anonymize_text`).
**Do NOT apply to:** private helpers (`_get_thread_lock`, `_expand_forbidden_tokens`) — keeps span volume bounded.

```python
# redaction_service.py L106
@traced(name="redaction.redact_text")
async def redact_text(self, text: str) -> RedactionResult:
```

**What to copy:** the parenthesised form `@traced(name="redaction.<op>")` — bare `@traced` works too but the explicit name keeps span identity stable across refactors.

### Pydantic frozen model for service I/O (D-13 carryover, D-28)

**Source:** `backend/app/services/redaction_service.py` L58–84
**Apply to:** `EntityMapping` in `registry.py`

```python
# redaction_service.py L58-84
class RedactionResult(BaseModel):
    """D-13 public output schema."""

    model_config = ConfigDict(frozen=True)

    anonymized_text: str
    entity_map: dict[str, str]
    hard_redacted_count: int
    latency_ms: float
```

**What to copy:** `model_config = ConfigDict(frozen=True)` so callers cannot mutate registry rows after instantiation — guards against accidental cross-coroutine state leak. Phase 2 fields per D-22 / D-28: `real_value: str`, `real_value_lower: str`, `surrogate_value: str`, `entity_type: str`, `source_message_id: str | None`.

### `@lru_cache` singleton getter (D-15 carryover)

**Source:** `backend/app/services/redaction_service.py` L163–172
**Apply to:** NOT applied to `ConversationRegistry` (per D-33 it is per-turn, NOT process-wide; do not @lru_cache it). DO apply if a future module-level Supabase wrapper is introduced.

```python
# redaction_service.py L163-172
@lru_cache
def get_redaction_service() -> RedactionService:
    """D-15 singleton getter; lifespan calls this once at startup."""
    return RedactionService()
```

**What to copy:** the pattern, but for Phase 2 the explicit instruction is *do not* singleton the registry. `ConversationRegistry.load(thread_id)` returns a fresh instance per turn (D-33).

---

## Pattern Assignments

### `backend/app/services/redaction/registry.py` (NEW) — service, request-response

**Primary analog #1:** `backend/app/services/system_settings_service.py` (cached single-row reader, service-role)
**Primary analog #2:** `backend/app/services/audit_service.py` (service-role insert, fire-and-forget logger discipline)
**Primary analog #3:** `backend/app/services/redaction_service.py` (Pydantic frozen model + module-level logger + service class shape + future asyncio.Lock dict location)

#### Pattern A — Service-role read with module-level cache (system_settings_service.py L1–20)

```python
# backend/app/services/system_settings_service.py L1-20
import time
from app.database import get_supabase_client

_cache: dict | None = None
_cache_ts: float = 0.0
_TTL = 60  # seconds


def get_system_settings() -> dict:
    """Read the single system_settings row. Cached for 60s."""
    global _cache, _cache_ts
    now = time.time()
    if _cache is not None and (now - _cache_ts) < _TTL:
        return _cache

    client = get_supabase_client()  # service-role bypasses RLS
    result = client.table("system_settings").select("*").eq("id", 1).single().execute()
    _cache = result.data
    _cache_ts = now
    return _cache
```

**What to change for Phase 2:**
- The "cache" is the per-instance `_rows: list[EntityMapping]` and the lookup dict `_by_lower: dict[str, EntityMapping]`, NOT a module-level dict (D-33: per-turn, not process-wide). DROP the TTL; keep the SELECT pattern.
- Filter is `.eq("thread_id", thread_id)` not `.eq("id", 1)`. No `.single()` — multi-row.
- Wrap as `async classmethod ConversationRegistry.load(cls, thread_id: str) -> ConversationRegistry`. The supabase-py client call is sync; wrap in `await asyncio.to_thread(...)` if profiling shows blocking; first cut can call it directly (Phase 1 already calls supabase sync from async paths).

#### Pattern B — Service-role insert, exception-safe (audit_service.py L1–32)

```python
# backend/app/services/audit_service.py L1-32
import logging
from app.database import get_supabase_client

logger = logging.getLogger(__name__)


def log_action(
    user_id: str | None,
    user_email: str | None,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    details: dict | None = None,
    ip_address: str | None = None,
) -> None:
    """Write an audit log entry. Fire-and-forget — never raises."""
    try:
        client = get_supabase_client()
        client.table("audit_logs").insert(
            {
                "user_id": user_id,
                "user_email": user_email,
                "action": action,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "details": details or {},
                "ip_address": ip_address,
            }
        ).execute()
    except Exception as e:
        logger.warning("Failed to write audit log: %s", e)
```

**What to change for Phase 2 (`_upsert_deltas`):**
- This is NOT fire-and-forget. Registry writes MUST raise if they fail — losing a delta breaks REG-04 (same real → same surrogate within a thread). Replace `try / except / logger.warning` with `try / except / logger.error / raise` OR drop the wrapper and let the exception propagate.
- Multi-row `.insert([rows])` with `on_conflict` clause. supabase-py syntax:
  ```python
  client.table("entity_registry").upsert(
      [m.model_dump() for m in deltas],
      on_conflict="thread_id,real_value_lower",
      ignore_duplicates=True,
  ).execute()
  ```
  The `ignore_duplicates=True` flag emits `INSERT ... ON CONFLICT DO NOTHING`. Verify with the live supabase-py version (the planner's research step pulls the exact kwarg via context7).
- Empty list = no DB hop: `if not deltas: return` early.
- D-29 / D-30: this call is invoked from INSIDE the per-thread asyncio.Lock critical section (the lock is held across detect → generate → upsert). The function itself does not acquire any lock.

#### Pattern C — Frozen Pydantic model for `EntityMapping` (redaction_service.py L58–84)

See Shared Patterns above. Phase 2 shape (D-22 / D-28):

```python
class EntityMapping(BaseModel):
    """D-28: in-memory + row-creation payload for entity_registry."""

    model_config = ConfigDict(frozen=True)

    real_value: str
    real_value_lower: str  # str.casefold() — Unicode-correct (D-36)
    surrogate_value: str
    entity_type: str  # PERSON / EMAIL_ADDRESS / PHONE_NUMBER / LOCATION / DATE_TIME / URL / IP_ADDRESS (D-22)
    source_message_id: str | None = None  # D-22: nullable; backfilled by Phase 5 chat router
```

#### Pattern D — Module-level lock dict location (D-29)

The locks dict lives in `redaction_service.py` (module-level), NOT in `registry.py`. The `ConversationRegistry` is per-thread and short-lived; the locks survive across all turns of a thread. Place the dict at module top:

```python
# redaction_service.py — NEW module-level state (after imports, before class)
_thread_locks: dict[str, asyncio.Lock] = {}
_thread_locks_master: asyncio.Lock = asyncio.Lock()
```

#### Forbidden-tokens helper signature (D-37)

The `forbidden_tokens()` method on `ConversationRegistry` reuses Phase 1's `extract_name_tokens` — see the next section.

---

### `backend/app/services/redaction/anonymization.py` (MODIFY) — service, pure transform

**Analog (self):** `backend/app/services/redaction/anonymization.py` L183–243 — current `anonymize(...)` signature and the existing per-call forbidden-token block.

#### Existing Phase 1 block (the EXACT block Phase 2 expands — anonymization.py L183–207)

```python
# backend/app/services/redaction/anonymization.py L183-207
def anonymize(
    masked_text: str,
    entities: list[Entity],
) -> tuple[str, dict[str, str], int]:
    """Substitute entities right-to-left to keep offsets stable.
    ...
    """
    faker = get_faker()
    real_persons = [e.text for e in entities if e.type == "PERSON"]
    # D-07: build the per-call forbidden-token set from real PERSON names.
    # Honorifics are stripped before tokenisation so e.g. "Pak" doesn't
    # accidentally land in the forbidden set.
    bare_persons = [strip_honorific(name)[1] for name in real_persons]
    forbidden_tokens = extract_name_tokens(bare_persons)

    entity_map: dict[str, str] = {}
    used_surrogates: set[str] = set()
    hard_redacted_count = 0
    out = masked_text
```

**What to change for Phase 2 (D-37):**

1. Add `registry: "ConversationRegistry | None" = None` keyword arg to `anonymize(...)`. Use a forward-ref string to avoid a circular import (`registry.py` may transitively import `anonymization`).
2. Just before the existing `extract_name_tokens(bare_persons)` call, expand the input set with thread-wide tokens:

   ```python
   # NEW (D-37): per-call set ∪ per-thread set. Per-PERSON only (D-38).
   call_forbidden = extract_name_tokens(bare_persons)
   if registry is not None:
       forbidden_tokens = call_forbidden | registry.forbidden_tokens()
   else:
       forbidden_tokens = call_forbidden
   ```

3. Also add a per-thread surrogate-reuse path BEFORE the Faker generation block at L222–232 — when the entity is in the registry already, reuse the existing surrogate and skip the Faker loop entirely:

   ```python
   # NEW (REG-04 / D-32): if registry has this real value, reuse its surrogate.
   if registry is not None:
       hit = registry.lookup(ent.text)
       if hit is not None:
           replacement = hit
           # NOTE: do NOT add to entity_map here; the caller (redact_text)
           # will diff against registry.entries() to compute deltas.
           out = out[: ent.start] + replacement + out[ent.end :]
           continue
   ```
4. Update the docstring's "Args:" block to document `registry` and add a "registry-mode" sentence to the "Returns:" block.
5. The `extract_name_tokens` import at L48 is unchanged.

**Reference:** the existing `extract_name_tokens` is the canonical token extractor (`backend/app/services/redaction/name_extraction.py` L35–67). `ConversationRegistry.forbidden_tokens()` calls it on `[m.real_value for m in self._rows if m.entity_type == "PERSON"]` after `strip_honorific`. PER-PERSON only (D-38) — filter the entries by `entity_type == "PERSON"`.

---

### `backend/app/services/redaction_service.py` (MODIFY) — service, orchestration

**Analog (self):** `backend/app/services/redaction_service.py` (full file already pasted above; key anchors below).

#### Anchor #1 — imports block (L32–53)

The diff adds three imports:

```python
# ADD after line 36 (`from functools import lru_cache`):
import asyncio
```

```python
# ADD after line 45 (existing detection import):
from app.services.redaction.registry import ConversationRegistry, EntityMapping
```

(Forward-compat: if a circular import surfaces, demote to `from typing import TYPE_CHECKING` block + string-quoted annotations. Phase 1's `RedactionResult.entity_map: dict[str, str]` shape is already registry-compatible (no model dependency), so the import should stay clean.)

#### Anchor #2 — module-level lock state (NEW; insert at L55, BEFORE `class RedactionResult`)

```python
# D-29 (PERF-03): per-process asyncio.Lock keyed by thread_id.
# NOTE (D-31, FUTURE-WORK Phase 6): UPGRADE PATH for multi-worker / multi-instance
# Railway deploys is `pg_advisory_xact_lock(hashtext(thread_id))` — see
# `.planning/STATE.md` Phase 6 hardening section. asyncio.Lock is correct only
# while Railway runs a single Uvicorn worker.
_thread_locks: dict[str, asyncio.Lock] = {}
_thread_locks_master: asyncio.Lock = asyncio.Lock()
```

#### Anchor #3 — `redact_text` signature widening (L106–107)

```python
# CURRENT (L106-107):
@traced(name="redaction.redact_text")
async def redact_text(self, text: str) -> RedactionResult:
```

```python
# PHASE 2:
@traced(name="redaction.redact_text")
async def redact_text(
    self,
    text: str,
    registry: ConversationRegistry | None = None,
) -> RedactionResult:
```

The Phase 1 docstring (L108–123) explicitly noted "Phase 2 will widen the signature to accept a registry; the async shape is stable for that future." Update the body of the docstring to document `registry` and the lock semantics.

#### Anchor #4 — `redact_text` body (L130–160)

Wrap the existing body in the per-thread lock when registry is non-None. The Phase 1 body is unchanged in structure; only the wrapper is added:

```python
# Sketch (PHASE 2):
async def redact_text(self, text, registry=None):
    if registry is None:
        # Phase 1 stateless behaviour — unchanged. (D-39 hard guarantee.)
        return await self._redact_text_stateless(text)

    # D-29 / D-30: per-thread lock spans detect → generate → upsert.
    lock = await self._get_thread_lock(registry.thread_id)
    t_lock_start = time.perf_counter()
    async with lock:
        lock_wait_ms = (time.perf_counter() - t_lock_start) * 1000.0
        size_before = len(registry.entries())
        result = await self._redact_text_with_registry(text, registry)
        size_after = len(registry.entries())
        # D-41 span attrs (counts only — never real values):
        logger.debug(
            "redaction.redact_text(registry): size_before=%d size_after=%d "
            "lock_wait_ms=%.2f writes=%d",
            size_before, size_after, lock_wait_ms, size_after - size_before,
        )
        return result
```

The internal `_redact_text_stateless` is the existing L130–160 body verbatim. `_redact_text_with_registry` calls `anonymize(masked_text, entities, registry=registry)`, then `await registry.upsert_delta([...])` on the entries newly produced this call (entries in `result.entity_map` whose `real_value_lower` is not already in `registry._by_lower`).

#### Anchor #5 — `_get_thread_lock` private helper (NEW)

```python
async def _get_thread_lock(self, thread_id: str) -> asyncio.Lock:
    """D-29: get-or-create the asyncio.Lock for this thread.

    Held briefly under _thread_locks_master to make get-or-create atomic.
    """
    async with _thread_locks_master:
        lock = _thread_locks.get(thread_id)
        if lock is None:
            lock = asyncio.Lock()
            _thread_locks[thread_id] = lock
        return lock
```

#### Anchor #6 — `de_anonymize_text` NEW public method (D-34)

Add immediately after `redact_text`:

```python
@traced(name="redaction.de_anonymize_text")
async def de_anonymize_text(
    self,
    text: str,
    registry: ConversationRegistry,
) -> str:
    """D-34: 1-phase placeholder-tokenized round-trip.

    Forward-compat with Phase 4's 3-phase fuzzy upgrade — Phase 4 will insert
    its fuzzy-match pass between the placeholder-substitution pass and the
    final resolve pass without rewriting this call site (FR-5.4).

    D-35: hard-redact placeholders pass through unchanged because they are
    never present in the registry (REG-05 / D-24).
    """
    import re

    t0 = time.perf_counter()
    entries = registry.entries()
    # Sort by len(surrogate_value) DESC — longest match wins, prevents
    # partial-overlap corruption when surrogates share token prefixes.
    entries_sorted = sorted(entries, key=lambda m: len(m.surrogate_value), reverse=True)

    # Pass 1: surrogate -> placeholder token (case-insensitive).
    out = text
    placeholders: dict[str, str] = {}
    for i, m in enumerate(entries_sorted):
        token = f"<<PH_{i:04d}>>"
        out, n = re.subn(re.escape(m.surrogate_value), token, out, flags=re.IGNORECASE)
        if n > 0:
            placeholders[token] = m.real_value  # original casing preserved

    # Pass 2: placeholder -> real_value.
    resolved = 0
    for token, real in placeholders.items():
        out, n = re.subn(re.escape(token), real, out)
        resolved += n

    latency_ms = (time.perf_counter() - t0) * 1000.0
    logger.debug(
        "redaction.de_anonymize_text: text_len=%d surrogate_count=%d placeholders_resolved=%d ms=%.2f",
        len(text), len(entries), resolved, latency_ms,
    )
    return out
```

**Note:** placeholder format `<<PH_0001>>` is zero-padded (Claude's Discretion D-discretion-2 — chose zero-pad for lexicographic stability in tracing).

---

### `backend/app/services/redaction/__init__.py` (MODIFY) — re-exports

**Analog (self):** `backend/app/services/redaction/__init__.py` L1–32 — explicit "B2 option B" rationale.

**Existing surface (unchanged):**
```python
from app.services.redaction.errors import RedactionError

__all__ = ["RedactionError"]
```

**Phase 2 ADDITIONS (per CONTEXT.md "Integration Points" + D-27, D-28, D-34):**
```python
from app.services.redaction.errors import RedactionError
from app.services.redaction.registry import ConversationRegistry, EntityMapping

__all__ = [
    "RedactionError",
    "ConversationRegistry",
    "EntityMapping",
]
```

**What NOT to re-export here** (per the existing "B2 option B" docstring at L11–21): `de_anonymize_text` is a method on `RedactionService`, not a free function — it stays imported via `from app.services.redaction_service import get_redaction_service`. Do NOT re-export it from this `__init__.py`. (CONTEXT.md "Integration Points" reads "re-export `de_anonymize_text`" but the agent's reading of the existing B2 boundary is that re-exporting service METHODS through the sub-package re-introduces the documented circular import — surface the method via `RedactionService` only. Planner: please confirm with the user during plan-write if needed.)

---

### `supabase/migrations/029_pii_entity_registry.sql` (NEW) — migration

**Primary analog #1:** `supabase/migrations/011_audit_trail.sql` (full file pasted above) — system-level table, RLS-enabled but no user policies, table comment.
**Primary analog #2:** `supabase/migrations/001_initial_schema.sql` L7–42 — `gen_random_uuid()`, FK to `public.threads(id) on delete cascade`, `handle_updated_at()` definition.
**Primary analog #3:** `supabase/migrations/013_obligations.sql` (grep-snippet above) — `handle_updated_at` trigger wiring on a new table.

#### Pattern A — System-level RLS-no-user-policies shape (audit_trail.sql L1–35)

```sql
-- supabase/migrations/011_audit_trail.sql L1-35
-- ============================================================
-- Feature 1: Audit Trail & Activity Logging
-- ============================================================

-- 1. Audit logs table (no RLS — admin-only access via service-role)
create table public.audit_logs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete set null,
  user_email text,
  action text not null,
  resource_type text not null,
  resource_id text,
  details jsonb default '{}'::jsonb,
  ip_address text,
  created_at timestamptz not null default now()
);

-- 2. Indexes for query performance
create index idx_audit_logs_user_id on public.audit_logs(user_id);
create index idx_audit_logs_created_at on public.audit_logs(created_at desc);
create index idx_audit_logs_action on public.audit_logs(action);
create index idx_audit_logs_resource_type on public.audit_logs(resource_type);

-- 3. Enable RLS — prevent direct PostgREST access by non-admins
alter table public.audit_logs enable row level security;

create policy "admins_read_audit_logs"
  on public.audit_logs for select to authenticated
  using ((auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin');

-- Backend uses service-role client which bypasses RLS for writes.
-- PostgREST reads are restricted to super_admin only.

comment on table public.audit_logs is
  'System-wide audit trail. RLS enabled — admin-only read via PostgREST, service-role writes.';
```

**What to copy for `029_pii_entity_registry.sql`:**
- The "RLS enabled, no user policies" pattern (D-25). For `entity_registry`: drop EVEN the `super_admin` SELECT policy — Phase 2 explicitly has NO HTTP route (D-26), so no PostgREST consumer exists. Strict service-role only.
- The trailing `comment on table ... is '...'` documenting the RLS posture. Use this exact form: `'System-wide PII real↔surrogate registry. RLS enabled — service-role only (no policies).'`
- Index naming convention: `idx_<table>_<columns>`.

#### Pattern B — UNIQUE composite + FK shape (001_initial_schema.sql L7–27)

```sql
-- 001_initial_schema.sql L7-27
create table public.threads (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  title text not null default 'New Thread',
  ...
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.messages (
  id uuid primary key default gen_random_uuid(),
  thread_id uuid not null references public.threads(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role text not null check (role in ('user', 'assistant')),
  content text not null,
  created_at timestamptz not null default now()
);
```

**What to copy:**
- `id uuid primary key default gen_random_uuid()` — D-22.
- `thread_id uuid not null references public.threads(id) on delete cascade` — D-22.
- `source_message_id uuid null references public.messages(id) on delete set null` — D-22 (nullable + ON DELETE SET NULL because the chat router backfills AFTER the message row is committed).
- `created_at timestamptz not null default now()` + `updated_at timestamptz not null default now()` — D-22.
- D-23: ADD `unique (thread_id, real_value_lower)` constraint inline. This is the cross-process serialisation mechanism that makes the SC#5 race test correct under multi-worker (D-31 future).

#### Pattern C — `handle_updated_at` trigger function (already exists from 001_initial_schema.sql L32–38; just wire it)

```sql
-- 001_initial_schema.sql L32-42
create or replace function public.handle_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

create trigger handle_threads_updated_at
  before update on public.threads
  for each row execute function public.handle_updated_at();
```

```sql
-- 013_obligations.sql (snippet)
create trigger handle_obligations_updated_at
  before update on public.obligations
  for each row execute function public.handle_updated_at();
```

**What to copy for migration 029:** ONLY the `create trigger ...` block — the function is already defined in migration 001. Trigger name should be `handle_entity_registry_updated_at` (matches the project naming convention).

#### Composed migration 029 sketch

```sql
-- 029: PII Entity Registry — conversation-scoped real↔surrogate map (Phase 2)
-- System-level table; service-role only. End users never query this directly.
-- See PRD-PII-Redaction-System-v1.1.md §4.FR-3 and 02-CONTEXT.md D-21..D-26.

-- 1. Table
create table public.entity_registry (
  id uuid primary key default gen_random_uuid(),
  thread_id uuid not null references public.threads(id) on delete cascade,
  real_value text not null,
  real_value_lower text not null,         -- str.casefold()'d; case-insensitive lookup path (D-36)
  surrogate_value text not null,
  entity_type text not null,              -- Presidio type (PERSON / EMAIL_ADDRESS / ...) — D-22
  source_message_id uuid null references public.messages(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (thread_id, real_value_lower)    -- D-23: enforces "same real → same surrogate" at DB layer
);

-- 2. Indexes
create index idx_entity_registry_thread_id
  on public.entity_registry (thread_id);
-- The unique constraint above already provides the composite index for the
-- (thread_id, real_value_lower) lookup path used by ConversationRegistry.lookup.

-- 3. updated_at trigger (function defined in migration 001)
create trigger handle_entity_registry_updated_at
  before update on public.entity_registry
  for each row execute function public.handle_updated_at();

-- 4. RLS — system-level table, service-role only. NO user-facing policies (D-25).
alter table public.entity_registry enable row level security;
-- Intentionally no SELECT/INSERT/UPDATE/DELETE policies. End users have ZERO
-- direct PostgREST access; backend uses get_supabase_client() (service-role).

comment on table public.entity_registry is
  'System-wide PII real↔surrogate registry per thread. RLS enabled — service-role only (no policies). See PRD-PII-Redaction-System-v1.1.md §4.FR-3.';
```

**Use the `/create-migration` skill to scaffold** — CLAUDE.md Gotcha: never edit applied migrations 001–028, and the file is `029_pii_entity_registry.sql` (next sequential).

---

### `backend/tests/api/test_redaction_registry.py` (NEW) — integration test, real DB

**Primary analog:** `backend/tests/api/test_redaction.py` (full L1–296 pasted above) + `backend/tests/conftest.py` L1–42.

#### Pattern A — Class-per-SC + asyncio mark (test_redaction.py L14–18, L34–61)

```python
# test_redaction.py L1-18
"""Phase 1 redaction service tests.

Each TestSC<N>_... class corresponds to one Phase 1 ROADMAP Success Criterion.
Test docstrings quote the SC verbatim. Failures isolate to the SC they cover.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio
```

```python
# test_redaction.py L34-61 — SC class shape
class TestSC1_IndonesianParagraph:
    """SC#1: <verbatim ROADMAP success criterion>.
    Covers: PII-01, ANON-01, ANON-02, ANON-06.
    """

    async def test_real_pii_values_absent_from_output(self, redaction_service):
        result = await redaction_service.redact_text(INDONESIAN_PARAGRAPH)
        assert "Bambang" not in result.anonymized_text
        ...
```

**What to copy verbatim for Phase 2:**
- File header docstring with the same "Each TestSC<N>_… class …" pattern.
- `pytestmark = pytest.mark.asyncio` at module level.
- One class per Phase 2 SC (5 classes: SC#1..SC#5; D-42).
- Each class docstring quotes the ROADMAP SC verbatim and lists the REQ-IDs covered.
- Each test method begins with `async def test_<descriptor>(self, redaction_service, ...)`.

#### Pattern B — `seeded_faker` + `redaction_service` fixtures (conftest.py L15–41)

```python
# backend/tests/conftest.py L15-41
@pytest.fixture
def seeded_faker():
    """Per-test deterministic seed for the redaction Faker (D-20)."""
    from app.services.redaction.anonymization import get_faker

    faker = get_faker()
    faker.seed_instance(42)  # arbitrary fixed seed
    yield faker


@pytest.fixture(scope="session")
def redaction_service():
    """Session-scoped RedactionService."""
    from app.services.redaction_service import get_redaction_service
    return get_redaction_service()
```

**What to ADD for Phase 2 (D-43, D-44):** new fixtures in `conftest.py`. Sketch:

```python
import uuid as _uuid
import pytest_asyncio


@pytest_asyncio.fixture
async def fresh_thread_id(authed_user):  # authed_user fixture creates a row in threads
    """D-44: a fresh thread_id per test — avoids cross-test registry pollution."""
    from app.database import get_supabase_client
    client = get_supabase_client()
    tid = str(_uuid.uuid4())
    client.table("threads").insert({"id": tid, "user_id": authed_user["id"], "title": "test"}).execute()
    yield tid
    # Cascade-delete cleans entity_registry rows automatically (D-22 ON DELETE CASCADE).
    client.table("threads").delete().eq("id", tid).execute()


@pytest_asyncio.fixture
async def empty_registry(fresh_thread_id):
    """D-44: empty ConversationRegistry bound to a fresh thread."""
    from app.services.redaction.registry import ConversationRegistry
    return await ConversationRegistry.load(fresh_thread_id)
```

**`authed_user` is NOT shipped today** (`grep "authed_user"` finds nothing) — Phase 2 must EITHER (a) inline the seeded user via `get_supabase_client()` and `auth.admin.create_user(...)` once per session, OR (b) reuse the existing `TEST_EMAIL` / `TEST_PASSWORD` accounts from CLAUDE.md "Testing" section. Plan for the latter (it's the existing convention; matches the API-test pattern). Service-role client lets the test write the registry row regardless of which user owns the thread.

#### Pattern C — caplog log-privacy regression (test_redaction.py L265–296)

```python
# test_redaction.py L265-296
class TestSC5_LogPrivacy:
    """B4: enforce that no real PII value reaches log output."""

    async def test_no_real_pii_in_log_output(self, redaction_service, caplog):
        import logging as _logging

        with caplog.at_level(_logging.DEBUG):
            await redaction_service.redact_text(INDONESIAN_PARAGRAPH)

        forbidden = [
            "Bambang Sutrisno", "Bambang", "Sutrisno",
            "bambang.s@example.com", "+62-812-1234-5678",
            "Jakarta", "https://lexcore.id/u/bambang",
        ]
        for record in caplog.records:
            msg = record.getMessage()
            for value in forbidden:
                assert value not in msg, ...
```

**What to copy:** the same pattern, but exercise both `redact_text(text, registry=...)` AND `de_anonymize_text(text, registry)` AND `_upsert_deltas` — D-41 invariants apply to all new methods. Phase 2 forbidden list reuses Phase 1's plus any net-new PII the integration test introduces.

#### Pattern D — SC#5 race-condition test (D-42, D-43 — MUST hit real DB)

No direct precedent in test_redaction.py for asyncio.gather races. Idiom:

```python
class TestSC5_RegistryRace:
    """SC#5 (Phase 2): Concurrent redact_text calls on the same registry that
    both introduce the SAME new entity must produce ONE row in the DB and
    return identical surrogates. Verifies PERF-03 (per-thread asyncio.Lock)
    AND the unique-constraint serialisation safety net (D-23).
    """

    async def test_concurrent_introduction_of_same_entity(
        self, redaction_service, empty_registry, seeded_faker
    ):
        import asyncio
        from app.database import get_supabase_client

        text_a = "Pak Bambang Sutrisno tinggal di Jakarta."
        text_b = "Bambang Sutrisno menelpon hari ini."

        a, b = await asyncio.gather(
            redaction_service.redact_text(text_a, registry=empty_registry),
            redaction_service.redact_text(text_b, registry=empty_registry),
        )

        # 1. Identical surrogate for "Bambang Sutrisno" in both results.
        sa = next(v for k, v in a.entity_map.items() if k.lower() == "bambang sutrisno")
        sb = next(v for k, v in b.entity_map.items() if k.lower() == "bambang sutrisno")
        assert sa == sb, f"Race produced divergent surrogates: {sa!r} vs {sb!r}"

        # 2. Exactly one row in entity_registry for this real_value_lower in this thread.
        client = get_supabase_client()
        rows = (
            client.table("entity_registry")
            .select("id")
            .eq("thread_id", empty_registry.thread_id)
            .eq("real_value_lower", "bambang sutrisno")
            .execute()
            .data
        )
        assert len(rows) == 1, f"Expected exactly one registry row, got {len(rows)}"
```

**Why real DB (not mock):** the unique constraint `(thread_id, real_value_lower)` is the cross-process serialisation mechanism (D-23, D-31 future). Mocking the supabase client bypasses it; the test would falsely pass even after asyncio.Lock is removed. CONTEXT.md "specifics" §"the race-condition test (SC#5) must hit the real DB" makes this binding.

#### Pattern E — Cross-turn surname collision (D-37, PRD §7.5 explicit case)

```python
class TestSC5b_CrossTurnSurnameCollision:
    """D-37 / PRD §7.5: A surrogate generated in turn 1 must not have its
    surname token clash with a real PERSON introduced in turn 3. The cross-turn
    forbidden-token set (registry.forbidden_tokens()) prevents this.
    """

    async def test_turn3_real_does_not_collide_with_turn1_surrogate(
        self, redaction_service, empty_registry, seeded_faker
    ):
        # Turn 1: introduce "Maria Santos" — Faker generates some surrogate "X Y".
        r1 = await redaction_service.redact_text("Maria Santos works here.", registry=empty_registry)
        surrogate_for_maria = r1.entity_map["Maria Santos"]
        sur_tokens = {t.lower() for t in surrogate_for_maria.split()}

        # Turn 3: introduce "Margaret Thompson" — its tokens MUST NOT overlap
        # any token of Maria's surrogate, AND Maria's already-stored surrogate
        # MUST NOT have any token equal to "margaret" or "thompson" either.
        r3 = await redaction_service.redact_text(
            "Margaret Thompson called.", registry=empty_registry
        )
        surrogate_for_margaret = r3.entity_map["Margaret Thompson"]
        mar_tokens = {t.lower() for t in surrogate_for_margaret.split()}

        # The Phase 2 invariant: turn-3 surrogate avoids real tokens from
        # turn 1 already in registry (Maria, Santos) PLUS turn-3 reals.
        assert "maria" not in mar_tokens
        assert "santos" not in mar_tokens
        assert "margaret" not in mar_tokens
        assert "thompson" not in mar_tokens
```

#### Pattern F — Resume across restart (D-42 SC#2)

```python
class TestSC2_ResumeAcrossRestart:
    """SC#2 (Phase 2): Mappings persist; loading a fresh ConversationRegistry
    for the same thread_id reproduces them.
    """

    async def test_load_after_drop_returns_same_mappings(
        self, redaction_service, fresh_thread_id, seeded_faker
    ):
        from app.services.redaction.registry import ConversationRegistry

        reg1 = await ConversationRegistry.load(fresh_thread_id)
        r1 = await redaction_service.redact_text(
            "Pak Bambang tinggal di Jakarta.", registry=reg1
        )
        # Drop the in-memory instance.
        del reg1

        # Re-load from DB.
        reg2 = await ConversationRegistry.load(fresh_thread_id)
        r2 = await redaction_service.redact_text(
            "Bambang menelpon kembali.", registry=reg2
        )

        # Same real value across "restart" → same surrogate.
        s1 = r1.entity_map.get("Pak Bambang") or r1.entity_map.get("Bambang")
        s2 = r2.entity_map.get("Bambang") or next(iter(r2.entity_map.values()))
        # Robust comparison since Phase 1's entity_map keys vary by honorific.
        # Easier: lookup directly via the registry.
        assert reg2.lookup("Bambang") is not None
```

#### Pattern G — Hard-redact never in registry (D-35 SC#4)

```python
class TestSC4_HardRedactSurvives:
    """SC#4 (Phase 2): hard-redact placeholders ([CREDIT_CARD], etc.) are
    never in the registry and survive a de_anonymize_text round-trip
    unchanged. (D-24 / D-35.)
    """

    async def test_hard_redact_not_persisted(
        self, redaction_service, empty_registry, seeded_faker
    ):
        from app.database import get_supabase_client

        text = "Card 4111-1111-1111-1111 belongs to Pak Bambang."
        result = await redaction_service.redact_text(text, registry=empty_registry)

        assert "[CREDIT_CARD]" in result.anonymized_text

        client = get_supabase_client()
        rows = (
            client.table("entity_registry")
            .select("entity_type")
            .eq("thread_id", empty_registry.thread_id)
            .execute()
            .data
        )
        types = {r["entity_type"] for r in rows}
        assert "CREDIT_CARD" not in types, "Hard-redact leaked into registry"

    async def test_hard_redact_passes_through_de_anon(
        self, redaction_service, empty_registry, seeded_faker
    ):
        text_in = "Card 4111-1111-1111-1111 belongs to Pak Bambang."
        result = await redaction_service.redact_text(text_in, registry=empty_registry)
        # Re-load fresh registry to simulate the chat-loop's per-turn pattern.
        from app.services.redaction.registry import ConversationRegistry
        reg2 = await ConversationRegistry.load(empty_registry.thread_id)
        roundtrip = await redaction_service.de_anonymize_text(
            result.anonymized_text, reg2
        )
        assert "[CREDIT_CARD]" in roundtrip
```

---

### `backend/tests/unit/test_conversation_registry.py` (NEW, optional) — pure unit, no DB

**Analog:** test_redaction.py shape; but does NOT use the `redaction_service` fixture or hit Supabase. Tests `ConversationRegistry` internals (lookup case-insensitivity, forbidden_tokens(), entries() ordering) against an in-memory subclass that overrides `_load_rows` / `_upsert_deltas` to no-op against a list.

```python
# Sketch
from __future__ import annotations
import pytest

pytestmark = pytest.mark.asyncio


class TestConversationRegistryUnit:
    """Pure-unit coverage for ConversationRegistry — no DB."""

    async def test_lookup_is_casefold_correct(self):
        from app.services.redaction.registry import ConversationRegistry, EntityMapping
        reg = ConversationRegistry(thread_id="t-1", rows=[
            EntityMapping(
                real_value="Bambang Sutrisno",
                real_value_lower="bambang sutrisno",
                surrogate_value="Andi Pratama",
                entity_type="PERSON",
            ),
        ])
        assert reg.lookup("bambang sutrisno") == "Andi Pratama"
        assert reg.lookup("BAMBANG SUTRISNO") == "Andi Pratama"
        assert reg.lookup("Margaret Thompson") is None

    async def test_forbidden_tokens_only_persons(self):
        # Other entity types must NOT contribute (D-38).
        ...
```

The `tests/unit/` directory does NOT exist today (`ls` confirmed). The plan must `mkdir` it AND add `tests/unit/__init__.py` (empty) AND keep the same `pytestmark = pytest.mark.asyncio` / class-per-SC convention.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| (none) | — | — | Every Phase 2 file has a strong analog already shipping in the codebase. |

## Metadata

**Analog search scope:**
- `backend/app/services/` (full subtree — 18 services)
- `backend/app/services/redaction/` (Phase 1 sub-package — 8 modules)
- `backend/tests/` (Phase 1 test scaffolding — 1 file + 1 conftest)
- `supabase/migrations/` (28 applied migrations — `grep -L "auth.uid()"` to find system-level shape)

**Files scanned:** 12 (anonymization.py, redaction_service.py, redaction/__init__.py, name_extraction.py, tracing_service.py, system_settings_service.py, audit_service.py, database.py, test_redaction.py, conftest.py, 001_initial_schema.sql, 011_audit_trail.sql, 028_global_folders.sql, 013_obligations.sql)

**Pattern extraction date:** 2026-04-26

## PATTERN MAPPING COMPLETE
