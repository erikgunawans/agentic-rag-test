# Phase 2: Conversation-Scoped Registry & Round-Trip - Context

**Gathered:** 2026-04-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Ship the conversation-scoped real↔surrogate registry so the same real entity always maps to the same surrogate within a thread, the mapping survives a thread reload, and surrogates round-trip back to real values for user-facing display.

In scope:
- New `entity_registry` Postgres table (migration `029_pii_entity_registry.sql`) — system-level, service-role-only RLS.
- New `ConversationRegistry` class (Python) — per-thread in-memory wrapper backed by the table; `load(thread_id)` / `upsert_delta()` / `lookup(real_value)` / `forbidden_tokens()` API.
- Widening of Phase 1's `RedactionService.redact_text(text)` signature to `redact_text(text, registry: ConversationRegistry | None = None) -> RedactionResult` (D-14 was Phase 1's locked-in promise).
- New `de_anonymize_text(text: str, registry: ConversationRegistry) -> str` public function on `RedactionService` — placeholder-tokenized 1-phase implementation, forward-compatible with Phase 4's 3-pass upgrade.
- Per-thread async-lock keyed serialization (PERF-03) — in-memory `dict[thread_id -> asyncio.Lock]` with a master lock on dict mutation.
- Cross-turn surrogate-collision avoidance — Phase 1's per-call surname/first-name forbidden-token set (D-07) expanded to include all real values already in the thread registry.
- Pytest coverage for all 5 Phase 2 ROADMAP success criteria, including the async race-condition test.

Explicitly NOT in scope (deferred to later phases):
- Entity resolution / nickname clustering / Union-Find merging (Phase 3: RESOLVE-01..04).
- `LLM_PROVIDER` switch + pre-flight egress filter (Phase 3: PROVIDER-01..07).
- Fuzzy de-anonymization (Jaro-Winkler / LLM-mode) (Phase 4: DEANON-03..05).
- 3-phase placeholder pipeline (replace → fuzzy-match → resolve) — Phase 4 upgrades the Phase 2 `<<PH_xxxx>>` shape with the fuzzy middle step.
- Optional secondary missed-PII LLM scan (Phase 4: SCAN-01..05).
- Chat-loop integration: SSE buffering, `redaction_status` events, tool/sub-agent symmetric coverage (Phase 5: BUFFER-01..03, TOOL-01..04).
- Embedding-provider switch (Phase 6: EMBED-01..02).
- Postgres advisory locks for cross-process safety — Railway runs single-worker today; FUTURE-WORK note in Phase 6 hardening.
- Registry encryption at rest (PRD §10 future work).
- Admin UI to inspect what was redacted (PRD §10 future work).
- HTTP API surface for the registry — service-internal only in Phase 2.

</domain>

<decisions>
## Implementation Decisions

### Registry Storage Schema

- **D-21 (REG-01, REG-02):** Dedicated `entity_registry` Postgres table, **migration `029_pii_entity_registry.sql`** (next sequential after `028_global_folders.sql`). Rejected: JSONB column on `threads` (kills index path, makes audit-log impossible, full-blob rewrite per mutation); hybrid table+cache (premature). Use `/create-migration` skill to scaffold with the project's RLS template.
- **D-22 (REG-01, REG-03, REG-04, REG-05):** Table columns:
  - `id uuid primary key default gen_random_uuid()`
  - `thread_id uuid not null references public.threads(id) on delete cascade`
  - `real_value text not null` — original casing preserved for de-anon output
  - `real_value_lower text not null` — normalized lowercase, indexed lookup path for REG-03
  - `surrogate_value text not null`
  - `entity_type text not null` — Presidio entity type (PERSON, EMAIL_ADDRESS, PHONE_NUMBER, LOCATION, DATE_TIME, URL, IP_ADDRESS) so Phase 3/6 can filter without re-running NER
  - `source_message_id uuid null references public.messages(id) on delete set null` — backfilled by chat router after message commit (nullable because `redact_text` runs BEFORE the user-message row exists)
  - `created_at timestamptz not null default now()`
  - `updated_at timestamptz not null default now()` — wired to existing `handle_updated_at()` trigger
- **D-23 (REG-04):** **`UNIQUE(thread_id, real_value_lower)` constraint** — enforces "same real entity → same surrogate" at the DB layer rather than relying on application-side checks alone. Defense in depth against race conditions; the composite index also serves the case-insensitive lookup for REG-03.
- **D-24 (REG-05):** **Hard-redacts NEVER inserted** into the registry — REG-05 / FR-3.5. The `entity_map` returned from Phase 1 already excludes them (D-08), so Phase 2 just iterates that map; nothing special to filter at the registry layer.

### RLS & Access Control

- **D-25 (NFR-2):** **Service-role-only RLS.** Backend uses `get_supabase_client()` (service role) for all registry reads/writes. Policy:
  ```sql
  alter table public.entity_registry enable row level security;
  -- No user-facing policies. Only the service role bypasses RLS.
  ```
  No SELECT / INSERT / UPDATE / DELETE policies for `authenticated` or `anon`. End users have ZERO direct access to the registry — exactly what NFR-2 specifies. Matches the `system_settings` table pattern.
- **D-26:** **No HTTP route in Phase 2.** No `/admin/registry/*` endpoints. The registry is service-internal; Phase 5's chat-loop integration is the only consumer. Admin audit UI is PRD §10 future work.

### In-Memory Registry Object

- **D-27 (REG-02, NFR-1):** **`ConversationRegistry` class** at `backend/app/services/redaction/registry.py` — per-thread in-memory wrapper. Public API:
  - `async classmethod load(cls, thread_id: str) -> ConversationRegistry` — issues one `SELECT * FROM entity_registry WHERE thread_id = $1` and builds the in-memory dict. Called once per chat turn.
  - `lookup(real_value: str) -> str | None` — case-insensitive, hits the in-memory dict (O(1) on `casefold()`'d keys). Returns the existing surrogate or None.
  - `async upsert_delta(deltas: list[EntityMapping]) -> None` — issues one `INSERT ... ON CONFLICT (thread_id, real_value_lower) DO NOTHING`. Called from inside the asyncio.Lock critical section by `redact_text`. Empty list = no-op (no DB hop).
  - `forbidden_tokens() -> set[str]` — returns the union of first-name + surname tokens from every `real_value` in the thread (extracted via `nameparser`, same logic as Phase 1 D-07). Consumed by Phase 1's collision check, expanded to thread scope.
  - `entries() -> list[EntityMapping]` — read-only iteration for `de_anonymize_text`.
- **D-28:** **`EntityMapping` Pydantic model** with `real_value`, `real_value_lower`, `surrogate_value`, `entity_type`, `source_message_id`. Used both as the in-memory representation and the row-creation payload.

### Async Lock Strategy (PERF-03)

- **D-29 (PERF-03):** **Per-process `asyncio.Lock` keyed by `thread_id`.** Module-level state in `redaction_service.py`:
  ```python
  _thread_locks: dict[str, asyncio.Lock] = {}
  _thread_locks_master = asyncio.Lock()  # guards _thread_locks itself
  ```
  Helper `_get_thread_lock(thread_id)` acquires `_thread_locks_master` briefly, creates the per-thread lock if absent, returns it. Zero DB round-trip for the lock itself. Works correctly on Railway today (single Uvicorn worker).
- **D-30:** **Lock scope = the WHOLE `redact_text(text, registry)` call** — detection, surrogate generation, collision check, and `upsert_delta` all execute inside the critical section. Adds ~5–10ms wall-clock under contention (Phase 1 warm path is 2–3ms + the new ~5–10ms DB upsert hop). PRD invariant FR-3.4 (same real → same surrogate within a thread) holds trivially because no other coroutine can race in between detect and write. Rejected: smaller-CS variant (TOCTOU window — both coroutines generate different Faker surrogates for the same real entity; loser's already-anonymized text is wrong).
- **D-31 (FUTURE-WORK, Phase 6):** **Postgres advisory lock upgrade path.** The asyncio.Lock approach BREAKS under multi-worker Uvicorn or horizontally scaled Railway instances. When the deployment scales out, replace with `pg_advisory_xact_lock(hashtext($1))` keyed on `thread_id`. Note this clearly in the registry module docstring AND in the FUTURE-WORK section of `.planning/STATE.md` so Phase 6's hardening pass picks it up. NOT shipped in Phase 2.

### Persistence Timing

- **D-32 (REG-02, REG-04):** **Eager upsert per `redact_text` call** inside the asyncio.Lock critical section. Each call computes deltas (entries in `entity_map` not already in the loaded registry), then issues one `INSERT ... ON CONFLICT DO NOTHING` for the deltas. Highest durability; mid-turn crash loses zero mappings. Cost is acceptable given the warm-path budget. Rejected: end-of-turn batch (mid-turn crash loses mappings, breaks REG-04 across worker restarts); periodic flush (premature for Phase 2).
- **D-33 (PRD §3.2, NFR-1):** **Lazy load at start of each chat turn.** `ConversationRegistry.load(thread_id)` is called once by the chat router on the first redact call of a turn, then passed into every subsequent `redact_text` call within that turn. Discarded after the assistant response is committed. Per-turn lifecycle keeps memory bounded and avoids stale-cache risks across worker boundaries. Rejected: process-wide LRU cache (defer to Phase 6); eager preload on thread-open route (premature, frontend coupling).

### Round-Trip / De-Anonymization Mechanics

- **D-34 (DEANON-01, DEANON-02, DEANON-05 forward-compat):** **Placeholder-tokenized 1-phase de-anon** at `RedactionService.de_anonymize_text(text, registry)`:
  1. Sort registry entries by `len(surrogate_value)` descending — guarantees longest match wins, prevents partial-overlap corruption (e.g., surrogate "Bambang Sutrisno" replaced before surrogate "Bambang").
  2. For each entry, `re.sub(re.escape(surrogate), f"<<PH_{i:04d}>>", text, flags=re.IGNORECASE)` — DEANON-02 case-insensitivity comes from the regex flag.
  3. Resolve every `<<PH_xxxx>>` token back to its `real_value` (original casing preserved) in a final single pass.

  **Phase 4 forward-compat:** Phase 4 will insert its placeholder-tokenized fuzzy-match pass BETWEEN steps 2 and 3 — it operates on the placeholder'd text where real names are hidden and surrogates are tokens, exactly the FR-5.4 contract. No call-site rewrite needed.
- **D-35 (DEANON-05):** **Hard-redact placeholders pass through unchanged.** `[CREDIT_CARD]`, `[US_SSN]`, etc. are never in the registry (D-24), so they are never matched by step 2. They survive de-anon by construction. Phase 2 ships a pytest assertion that proves this.
- **D-36 (REG-03, DEANON-02):** **Case handling — normalize at the registry boundary, NOT per-call.** `real_value_lower` is computed once on insert (Python `str.casefold()`, NOT `str.lower()` — Unicode-correct fold; insurance for any future locale expansion even though Indonesian doesn't strictly need it). DB column has the index path. The de-anon pipeline uses `re.IGNORECASE` for surrogate matching; the resolved real value is the original-casing `real_value` column. One source of truth, no per-call lowercase work in the hot path.

### Cross-Turn Surrogate-Collision Avoidance

- **D-37 (extends Phase 1 D-07):** **Forbidden-token set is THREAD-WIDE, not call-wide.** When `RedactionService.redact_text(text, registry)` runs Faker generation:
  - Per-call set (D-07): first-name + surname tokens of every real value detected in THIS call's input.
  - Per-thread set (NEW): first-name + surname tokens of every real value already in `registry.entries()`.
  - Forbidden = union. Faker output rejected if its tokens overlap with either set.

  Prevents the cross-turn variant of PRD §7.5 corruption (turn 1 introduces "Aaron Thompson DDS" as Maria's surrogate; turn 3 mentions Margaret Thompson — Faker mustn't pick a surrogate whose surname is "Maria"). Same algorithm as D-07; just larger input set.
- **D-38:** **Per-PERSON only.** The cross-turn check applies to PERSON entities. Other types (emails, phones, URLs, IP addresses) are unique strings — collision risk is negligible and the cost of building a thread-wide forbidden set across all types is wasted. Email/phone surrogate collisions, if they ever occur, are caught by the Phase 1 10-retry budget (D-06) and the non-realistic-fallback hash placeholder.

### Service Composition / Wiring

- **D-39 (D-13, D-14):** **`RedactionService.redact_text(text, registry: ConversationRegistry | None = None) -> RedactionResult`** — Phase 2 widens the signature exactly as Phase 1 D-14 promised. When `registry is None`, behavior is identical to Phase 1 (stateless, fresh in-memory state). When `registry` is supplied, the call is wrapped in the per-thread asyncio.Lock and the registry is consulted before generation and updated after.
- **D-40:** **Helper signature surface** in `redaction_service.py`:
  - `async def redact_text(self, text: str, registry: ConversationRegistry | None = None) -> RedactionResult` — public.
  - `async def de_anonymize_text(self, text: str, registry: ConversationRegistry) -> str` — public.
  - `async def _get_thread_lock(self, thread_id: str) -> asyncio.Lock` — private.
  - `def _expand_forbidden_tokens(self, call_set: set[str], registry: ConversationRegistry) -> set[str]` — private; pure.
  Every public method retains the existing `@traced(name="redaction.<op>")` decorator (D-18).
- **D-41:** **Tracing span attributes** for the new methods — counts and timings only, NEVER real values:
  - `redaction.redact_text`: as Phase 1 + `registry_size_before`, `registry_size_after`, `registry_lock_wait_ms`, `registry_writes`.
  - `redaction.de_anonymize_text`: `text_len`, `surrogate_count`, `placeholders_resolved`, `latency_ms`.

### Testing

- **D-42:** **Pytest coverage for all 5 Phase 2 ROADMAP success criteria** at `backend/tests/api/test_redaction_registry.py` (and `backend/tests/unit/test_conversation_registry.py` if it grows). Each SC gets at least one test:
  - SC#1 (case-insensitive consistency within a turn) — call `redact_text` twice with different casings on the same `registry`; assert identical surrogate.
  - SC#2 (resume across restart) — write registry, drop the in-memory instance, `ConversationRegistry.load(thread_id)` again, assert mappings reproduce.
  - SC#3 (case-insensitive de-anon) — feed an LLM-style upper/title-case'd surrogate to `de_anonymize_text`; assert original real value with original casing is returned.
  - SC#4 (hard-redact placeholders not in registry, survive de-anon) — input with credit-card-like string; assert `[CREDIT_CARD]` in registry has zero rows for the thread AND survives a de-anon pass unchanged.
  - SC#5 (concurrent registry-write race) — `asyncio.gather(redact_text(text_a, registry), redact_text(text_b, registry))` on two payloads that both introduce the SAME new entity; assert one row in the DB and identical surrogates returned (PERF-03 verification).
- **D-43:** **Test DB fixture** — a `pytest_asyncio` fixture sets up the `entity_registry` table in a Supabase test schema (or mocks the supabase client with an in-memory equivalent for unit tests; integration tests hit the real DB via the existing test creds in CLAUDE.md). The race-condition test (SC#5) MUST hit the real DB to exercise the unique constraint, not a mock.
- **D-44:** **Faker `seed_instance(seed)` + `ConversationRegistry` empty-state fixture** — per-test reproducibility (Phase 1 D-20 carryover), plus a fresh `thread_id` per test to avoid cross-test pollution.

### Claude's Discretion

- Exact module split — whether `ConversationRegistry`, async-lock helper, and `EntityMapping` Pydantic live in one new `backend/app/services/redaction/registry.py` or split (`registry.py`, `locks.py`, `models.py`). Planner picks based on line-count.
- Whether the placeholder token format is `<<PH_0001>>` (zero-padded) or `<<PH_1>>` (variable) — both work; zero-padded sorts lexicographically which is helpful for tracing.
- Logging format for registry writes (DEBUG vs INFO; never include `real_value`, only counts and `entity_type`).
- Whether the in-memory `ConversationRegistry` exposes a sync or async `lookup` (sync is fine since data is already in memory; async is needed for `load`/`upsert_delta`).
- Whether `_thread_locks` cleanup is automatic (e.g., evict locks for threads idle > N seconds) or pinned for the worker lifetime. For Phase 2 simplicity: pin them; revisit if memory pressure shows up.
- Exact name for the new SQL migration — within the agreed `029_pii_entity_registry.sql` shape, the planner picks final wording.

### Folded Todos

(None — no pending project todos folded into Phase 2 scope.)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Source PRD (authoritative for v1.0 milestone)
- `docs/PRD-PII-Redaction-System-v1.1.md` §3.1 (Core Principle), §3.2 (Document Ingestion), §3.3 (Chat / Main Agent flow — registry steps 3 + 7), §3.6 (Auxiliary LLM Calls — pre-flight egress invariant), §4.FR-3 (Conversation-Scoped Registry), §4.FR-5.1 / §4.FR-5.2 / §4.FR-5.5 (Phase 2's slice of de-anon — exact match, case-insensitive, hard-redact survival), §4.FR-5.4 (placeholder-pipeline shape that Phase 2 implements as 1-phase and Phase 4 upgrades to 3-phase), §5.NFR-1 (Performance), §5.NFR-2 (Security — system-level table, RLS), §5.NFR-3 (Reliability — async lock for concurrent registry writes), §7.2 (Why Conversation-Scoped Registries — global vault rejected), §7.5 (Surname-Collision Corruption — drives D-37 cross-turn forbidden-tokens), §10 (Future Considerations — registry encryption, audit UI deferred)

### Project + Milestone Plan
- `.planning/PROJECT.md` "Current Milestone" + "Key Decisions" — v1.0 scope and architectural decisions adopted from PRD
- `.planning/REQUIREMENTS.md` "v1 Requirements" — REG-01..05, DEANON-01..02, PERF-03 are Phase 2's REQ-IDs
- `.planning/ROADMAP.md` "Phase 2: Conversation-Scoped Registry & Round-Trip" — goal, dependencies, success criteria
- `.planning/phases/01-detection-anonymization-foundation/01-CONTEXT.md` — D-13 / D-14 / D-07 / D-08 / D-18 / D-20 are explicit Phase-1-locks Phase 2 builds on (signature widening, hard-redact exclusion, surname x-check, no-real-PII-in-spans, Faker seeding)

### Codebase Map (existing patterns to follow / reuse)
- `.planning/codebase/CONVENTIONS.md` §"Code Style", §"Logging", §"FastAPI Dependency Patterns", §"LLM / Structured Output Pattern" — service-module shape, traceable decorator, Pydantic models, audit conventions
- `.planning/codebase/STRUCTURE.md` §"Where to Add New Code" → "New backend service" — directory and file conventions

### Concrete code to read before editing (Phase 2 will modify or wrap these)
- `backend/app/services/redaction_service.py` — Phase 1 `RedactionService` shipped on master at commit `0857bb2`. Phase 2 widens `redact_text(text)` → `redact_text(text, registry=None)`, adds `de_anonymize_text(text, registry)`, threads the asyncio-lock helper through.
- `backend/app/services/redaction/anonymization.py` — Phase 1 surrogate generator. Phase 2 expands the per-call forbidden-token set to thread-wide via `registry.forbidden_tokens()`. Function signature change.
- `backend/app/services/redaction/__init__.py` — re-exports; Phase 2 adds `ConversationRegistry`, `EntityMapping`, `de_anonymize_text` to the public surface.
- `backend/app/database.py` — `get_supabase_client()` (service-role) and `get_supabase_authed_client(token)` (RLS-scoped). Phase 2 uses service-role for ALL registry traffic per D-25.
- `backend/app/routers/threads.py` — existing thread CRUD. Phase 2 does NOT modify this router; the registry is invisible to thread routes. Phase 5 will wire chat-loop callers.
- `supabase/migrations/001_initial_schema.sql` — `threads` and `messages` table shape; Phase 2's `entity_registry.thread_id` FK + `source_message_id` FK references these. Also defines the `handle_updated_at()` trigger function Phase 2 reuses.
- `supabase/migrations/028_global_folders.sql` — last applied migration; Phase 2 ships `029_pii_entity_registry.sql`. CLAUDE.md gotcha: never edit applied migrations; use `/create-migration` skill.
- `backend/app/main.py` `lifespan` — Phase 2 does NOT touch lifespan. The registry is per-turn lazy-loaded; no startup warm-up needed.
- `backend/app/services/tracing_service.py` — `@traced` decorator (Phase 1 D-16). Phase 2 wraps every new public method with it (D-41).

### External docs (planner will fetch via context7 / web)
- Supabase service-role client patterns + RLS bypass behavior — confirm `get_supabase_client()` semantics
- Postgres `INSERT ... ON CONFLICT (composite) DO NOTHING RETURNING` semantics — confirm row visibility under concurrent writers
- Python `asyncio.Lock` semantics — re-entrancy (NOT re-entrant; the wrapper code must avoid double-acquire)
- `nameparser.HumanName` Indonesian-mononym handling — Phase 1 already verified it routes mononyms to `.first` (memory: 2669); confirm cross-call behavior is stable

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`get_supabase_client()` (`backend/app/database.py`)**: Service-role client. Phase 2 uses for ALL `entity_registry` traffic — bypasses RLS, matches NFR-2 ("system-level table, service-role only").
- **`handle_updated_at()` SQL trigger function (`supabase/migrations/001_initial_schema.sql`)**: Already defined; Phase 2's migration just wires the trigger to `entity_registry`.
- **`@traced(name=...)` decorator (`backend/app/services/tracing_service.py`)**: Phase 1 D-16. Phase 2's new public methods inherit the same span pattern.
- **Pydantic `BaseModel` + `ConfigDict(frozen=True)` for service I/O (`redaction_service.py` L78–84)**: Phase 1 `RedactionResult` is frozen. Phase 2's `EntityMapping` follows the same pattern.
- **Phase 1 `RedactionService` warm-up in `lifespan` (`backend/app/main.py`)**: Already loads Presidio + Faker + gender detector at startup. Phase 2 adds NO new warm-up — registry is per-turn lazy-loaded.
- **Phase 1 `entity_map: dict[str, str]` shape (`redaction_service.py` L82)**: Already the same `real → surrogate` shape Phase 2's persisted registry uses. Zero impedance mismatch on the deltas-to-upsert path.
- **Phase 1 D-07 surname/first-name cross-check (`backend/app/services/redaction/anonymization.py`)**: Already implemented as a per-call forbidden-token set built via `nameparser`. Phase 2 just expands the input to include thread-wide tokens via `registry.forbidden_tokens()`.

### Established Patterns
- **Service module layout**: `backend/app/services/<name>/...` for sub-packaged services. Phase 1 already created `backend/app/services/redaction/`. Phase 2 adds `registry.py` (and possibly `locks.py`, `models.py`) inside the same package.
- **Migration numbering**: Sequential, never edit applied (`/create-migration` enforces). Phase 2 → `029_pii_entity_registry.sql`.
- **RLS bypass pattern**: System-level tables (`system_settings`, audit-related) use service-role client + no user-facing policies. Phase 2's `entity_registry` follows.
- **Logging**: `logger = logging.getLogger(__name__)` per module; `%s` formatting; NEVER include real PII in log messages (D-18 / B4 from Phase 1).
- **Lifespan extension pattern (`backend/app/main.py`)**: Try/except wrapping for non-fatal init failures. Phase 2 does NOT touch lifespan — but the planner should add a `entity_registry` connectivity smoke check IF startup-time validation is wanted (Claude's Discretion).

### Integration Points
- **`backend/app/services/redaction/__init__.py`**: Re-export `ConversationRegistry`, `EntityMapping`, `de_anonymize_text`.
- **`backend/app/services/redaction_service.py`**: Widen `redact_text` signature; add `de_anonymize_text`; add `_thread_locks` module-level dict + `_get_thread_lock` helper.
- **`backend/app/services/redaction/anonymization.py`**: Add `registry: ConversationRegistry | None` parameter to `anonymize(...)` — used to expand the forbidden-token set when present.
- **NEW `backend/app/services/redaction/registry.py`**: `ConversationRegistry`, `EntityMapping`, `_load_rows`, `_upsert_deltas` helpers.
- **NEW `supabase/migrations/029_pii_entity_registry.sql`**: Schema + RLS + indexes + `handle_updated_at` trigger wire-up.
- **NEW `backend/tests/api/test_redaction_registry.py`** + **`backend/tests/unit/test_conversation_registry.py`**: Per-SC test coverage including the race-condition test.
- **NOT modified in Phase 2**: `backend/app/routers/chat.py` (Phase 5), `backend/app/routers/threads.py` (no schema change visible from this router), `backend/app/main.py` lifespan (no new warm-up).

</code_context>

<specifics>
## Specific Ideas

- **Single-worker today, multi-worker tomorrow** — Railway runs one Uvicorn worker. asyncio.Lock is correct for now; capture the advisory-lock upgrade path explicitly so Phase 6 (or a horizontal-scaling event) doesn't get surprised.
- **Phase 4 forward-compat is the central design goal of the de-anon shape** — Phase 2 ships `<<PH_xxxx>>` placeholders specifically so Phase 4 inserts its fuzzy step between the existing two passes with no rewrite. Don't shortcut this with `str.replace` even if it looks cheaper today.
- **`source_message_id` is nullable for a real reason** — `redact_text` runs on user input BEFORE the `messages` row is committed. The chat router (Phase 5) is the natural backfill point. Don't NOT-NULL it.
- **The race-condition test (SC#5) must hit the real DB** — the unique constraint is the actual serialization mechanism for cross-process correctness once asyncio.Lock is upgraded; the test must exercise that path, not a mock.
- **Tracing spans never log real values** — Phase 1 B4 invariant. The new `registry_size_before`/`_after` and `registry_writes` attributes are counts; never serialize `entries()`. Same for log lines.
- **PRD §7.5 corruption scenario is the test case D-37 prevents** — explicit pytest case with a turn-1 surrogate component that turn-3 input would otherwise overlap.

</specifics>

<deferred>
## Deferred Ideas

- **Postgres advisory locks for cross-worker correctness** (D-31) — Phase 6 hardening, or earlier if Railway scales horizontally before then.
- **Process-wide LRU cache of `ConversationRegistry`** — Phase 6 perf hardening if profiling shows per-turn `load()` dominating latency.
- **Eager preload on thread-open route** — would shave first-turn latency; premature, frontend coupling.
- **Audit columns / CDC log of registry writes** — Phase 6 OBS-02 picks this up via the standard debug log; a separate audit table is a future-work item.
- **Encryption-at-rest for `real_value`** — PRD §10 future work; out of milestone scope.
- **Admin UI to inspect what was redacted per thread** — PRD §10 future work.
- **Per-feature registry partitioning** (e.g., split PERSON vs EMAIL into separate tables) — not warranted at v1.0 scale.
- **Registry pruning / TTL** for archived threads — no current pressure; revisit if storage growth becomes a problem.
- **HTTP API for the registry** — service-internal in v1.0; admin endpoints out of scope.

### Reviewed Todos (not folded)

(None — no project todos surfaced for Phase 2 scope.)

</deferred>

---

*Phase: 02-conversation-scoped-registry-and-round-trip*
*Context gathered: 2026-04-26*
