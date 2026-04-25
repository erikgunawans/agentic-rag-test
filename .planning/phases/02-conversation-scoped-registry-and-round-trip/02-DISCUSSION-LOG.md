# Phase 2: Conversation-Scoped Registry & Round-Trip - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-26
**Phase:** 02-conversation-scoped-registry-and-round-trip
**Areas discussed:** Registry storage shape, Async-lock strategy (PERF-03), Persistence timing, Round-trip mechanics

---

## Gray-Area Selection

| Option | Description | Selected |
|--------|-------------|----------|
| Registry storage shape | Dedicated `entity_registry` table vs. JSONB on `threads`; RLS scope. Migration #029. | ✓ |
| Async-lock strategy (PERF-03) | Per-process asyncio.Lock vs. Postgres advisory lock vs. optimistic upsert. | ✓ |
| Persistence timing | Eager per-call vs. end-of-turn batch vs. write-through cache. | ✓ |
| Round-trip mechanics | Placeholder-tokenized 1-phase vs. plain str.replace vs. word-boundary regex; cross-turn collision. | ✓ |

**User's choice:** All four areas selected (multi-select).
**Notes:** Phase 2 carries 8 REQ-IDs and 5 ROADMAP success criteria; user opted to discuss the full surface rather than skip any area.

---

## Registry Storage Shape

### Where the registry lives

| Option | Description | Selected |
|--------|-------------|----------|
| Dedicated `entity_registry` table | One row per mapping, indexes, audit-friendly, FK to threads. | ✓ |
| JSONB column on `threads` | Single atomic update; no new table. Kills index path; full-blob rewrite per mutation. | |
| Hybrid table + cached snapshot | Source-of-truth table + JSONB cache on threads. More moving parts; defer. | |

**User's choice:** Dedicated `entity_registry` table.
**Notes:** Aligns with PRD NFR-2 ("system-level table") and unblocks Phase 6 OBS-02 audit logging without rework.

### RLS scope

| Option | Description | Selected |
|--------|-------------|----------|
| Service-role only | No user-facing policies; backend service-role client only. Matches `system_settings` pattern. | ✓ |
| User-scoped via thread ownership | `auth.uid() = thread.user_id` policy as defense-in-depth. | |
| Both (service + user-scoped read) | Premature; admin audit UI is PRD §10 future work. | |

**User's choice:** Service-role only.
**Notes:** Strict NFR-2 compliance — registry is invisible to the API surface in v1.0.

### Table columns (multi-select)

| Option | Description | Selected |
|--------|-------------|----------|
| `real_value_lower` indexed | Case-insensitive lookup index path; UNIQUE(thread_id, real_value_lower). | ✓ |
| `entity_type` | Presidio entity type stored per row; enables Phase 3/6 filtering. | ✓ |
| `updated_at` + auto-trigger | Reuse existing `handle_updated_at()` trigger function. | ✓ |
| `source_message_id` FK | Nullable FK to messages; backfilled by chat router. | ✓ |

**User's choice:** ALL FOUR columns.
**Notes:** Discussion captured the nullability constraint — `redact_text` runs before the user-message row is committed, so source_message_id must be nullable (D-22).

### Migration sequencing

| Option | Description | Selected |
|--------|-------------|----------|
| 029_pii_entity_registry.sql | Single migration. | ✓ |
| 029 + 030 split (schema + indexes) | Cleaner if CONCURRENTLY indexes are needed. | |

**User's choice:** Single migration `029_pii_entity_registry.sql`.

---

## Async-Lock Strategy (PERF-03)

### Lock kind

| Option | Description | Selected |
|--------|-------------|----------|
| Per-process `asyncio.Lock` keyed by thread_id | Zero DB hop; correct on Railway today (single worker). FUTURE-WORK note for advisory upgrade. | ✓ |
| Postgres advisory lock | `pg_advisory_xact_lock(hashtext(thread_id))`; cross-process safe; +1 DB hop. | |
| Optimistic upsert + read-back | No lock; relies on MVCC. Doesn't compose with cross-row invariants like cross-turn collision check. | |
| Hybrid asyncio + advisory | Both layers; only worth it if multi-worker imminent. | |

**User's choice:** Per-process `asyncio.Lock` keyed by thread_id.
**Notes:** Ship pragmatic solution; capture upgrade path in CONTEXT D-31 + STATE.md FUTURE-WORK so Phase 6 picks it up.

### Lock scope

| Option | Description | Selected |
|--------|-------------|----------|
| Whole `redact_text(text, registry)` call | Detect + Faker + collision-check + upsert all inside critical section. Slowest under contention, simplest correctness. | ✓ |
| Registry-write-only (smaller CS) | Detection + generation lock-free; only persist step locked. TOCTOU window — losing coroutine has stale anonymized text. | |

**User's choice:** Whole `redact_text` call.
**Notes:** TOCTOU rejection was decisive — the loser's anonymized text is wrong if Faker generation isn't inside the lock.

---

## Persistence Timing

### Write timing

| Option | Description | Selected |
|--------|-------------|----------|
| Eager — upsert per `redact_text` call | Highest durability; ~5–10ms DB hop per call inside the lock. | ✓ |
| End-of-turn batch | One flush after assistant response commits. Mid-turn crash loses mappings. | |
| Write-through cache + periodic flush | Background drain. Premature for Phase 2. | |

**User's choice:** Eager per-call upsert.
**Notes:** Durability over micro-latency. Mid-turn crash recovery is the critical concern.

### Load timing

| Option | Description | Selected |
|--------|-------------|----------|
| Lazy — `ConversationRegistry.load(thread_id)` per chat turn | Per PRD §3.2; one SELECT per turn; discarded after. | ✓ |
| Process-wide LRU cache | Faster repeated turns; stale-cache risk under multi-worker. Defer. | |
| Eager preload on thread-open route | Frontend coupling; trims first-turn latency. Premature. | |

**User's choice:** Lazy per-turn load.
**Notes:** Matches PRD §3.2 wording ("loaded from DB on first use, kept in memory for the duration of the request").

---

## Round-Trip Mechanics

### De-anonymization algorithm

| Option | Description | Selected |
|--------|-------------|----------|
| Placeholder-tokenized 1-phase | `<<PH_xxxx>>` token pass + resolve pass. Phase 4 inserts fuzzy step BETWEEN with no rewrite. | ✓ |
| Plain str.replace (longest-first, IGNORECASE) | Simplest. Vulnerable to surname-collision corruption when Phase 4 adds fuzzy. Forces rewrite. | |
| Word-boundary regex per surrogate | Breaks for emails/URLs with non-word chars. Mixed bag. | |

**User's choice:** Placeholder-tokenized 1-phase.
**Notes:** Phase 4 forward-compat was the deciding factor — same call site, just a new middle pass.

### Cross-turn collision avoidance

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — expand forbidden tokens to all thread real values | Phase 1 D-07 algorithm extended thread-wide. Prevents PRD §7.5 cross-turn variant. | ✓ |
| No — within-call only; rely on Phase 4 fuzzy de-anon | Cheaper; cross-turn collisions are rare. | |
| Yes, PERSON-only | Limit thread-wide check to PERSON. | (Implicitly adopted — see D-38) |

**User's choice:** Yes — expand forbidden tokens.
**Notes:** D-38 narrows the implementation to PERSON entities (other types collide rarely; cost not worth it).

### Case handling

| Option | Description | Selected |
|--------|-------------|----------|
| Normalize at registry boundary (`real_value_lower` column + `re.IGNORECASE`) | One source of truth; index path for lookups; original casing preserved for de-anon output. | ✓ |
| Case-folded keys (`str.casefold`) | Unicode-correct fold; cheap insurance even though Indonesian doesn't strictly need it. | (Folded into recommended choice — see D-36) |
| Application-side dict lookup (no DB normalization) | Avoids the column; kills index path; slow on large registries. | |

**User's choice:** Normalize at registry boundary.
**Notes:** D-36 specifies `str.casefold()` rather than `str.lower()` as the normalization function, combining both recommended choices.

---

## Closeout

| Option | Description | Selected |
|--------|-------------|----------|
| I'm ready for context | Write CONTEXT.md + DISCUSSION-LOG.md; chain to plan-phase. | ✓ |
| Explore more gray areas | Surface additional areas (test strategy, registry pruning, error handling). | |

**User's choice:** Ready for context.

## Claude's Discretion

- Module split inside `backend/app/services/redaction/` (single `registry.py` vs. `registry.py + locks.py + models.py`).
- Placeholder format (`<<PH_0001>>` zero-padded vs. `<<PH_1>>`).
- Logging format / level for registry writes (DEBUG vs. INFO; counts only, never real values).
- Whether `ConversationRegistry.lookup` is sync or async (sync is fine; in-memory).
- `_thread_locks` cleanup strategy (pinned vs. evicted-by-idle-time) — pinned for now.
- Final wording of the migration filename within the agreed `029_pii_entity_registry.sql` shape.

## Deferred Ideas

- Postgres advisory locks (Phase 6 hardening or horizontal-scale event)
- Process-wide LRU cache of registries (Phase 6)
- Eager preload on thread-open route
- Audit table / CDC log for registry writes (Phase 6 OBS-02)
- Encryption-at-rest for `real_value` (PRD §10 future work)
- Admin UI for redaction inspection (PRD §10)
- Per-feature registry partitioning
- Registry pruning / TTL for archived threads
- HTTP API for the registry (service-internal in v1.0)
