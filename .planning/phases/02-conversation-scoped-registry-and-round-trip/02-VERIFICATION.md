---
phase: 02-conversation-scoped-registry-and-round-trip
verified: 2026-04-26T01:50:00Z
verified-by: Claude (gsd-verifier)
status: passed
score: 5/5 ROADMAP success criteria + 8/8 REQ-IDs validated
must_haves_passed: 23/23
plans_verified: 6/6
re_verification: false
overrides_applied: 0
roadmap_truths:
  - "Within a thread, same real entity (any casing) yields same surrogate; case-insensitive lookups"
  - "Resume across restart produces identical surrogates (DB persistence + reload)"
  - "Surrogates round-trip back to real values across LLM letter-case variations"
  - "Hard-redacted placeholders never appear as registry keys (one-way)"
  - "Concurrent same-thread same-entity introductions produce a single registry row (no race)"
requirements_validated:
  - REG-01
  - REG-02
  - REG-03
  - REG-04
  - REG-05
  - DEANON-01
  - DEANON-02
  - PERF-03
test_results:
  total: 39
  passed: 39
  failed: 0
  phase_1_regression: 20/20
  phase_2_integration: 15/15
  phase_2_unit: 4/4
live_db_verified: true
supabase_project: qedhulpfezucnfadlfiz
---

# Phase 2: Conversation-Scoped Registry & Round-Trip — Verification Report

**Phase Goal (from ROADMAP.md):**
> Ship the conversation-scoped real↔surrogate registry so the same real entity always maps to the same surrogate within a thread, the mapping survives a thread reload, and surrogates round-trip back to real values for user display.

**Verified:** 2026-04-26T01:50:00Z (Asia/Jakarta 08:50)
**Status:** PASSED
**Re-verification:** No — initial verification.

---

## Goal Achievement

### ROADMAP Success Criteria

| #  | Success Criterion | Status | Evidence |
|----|-------------------|--------|----------|
| SC#1 | Within a single thread, same real person/email/phone (any casing) yields same surrogate; case-insensitive lookups | VERIFIED | `backend/app/services/redaction/registry.py:126-135` (`lookup()` uses `.casefold()`); 3 tests in `TestSC1_CaseInsensitiveConsistency` pass against live DB; `test_only_one_registry_row_per_lower_value` confirms 1 row across 2 different-cased calls |
| SC#2 | Closing thread + restarting backend + resuming yields identical surrogates (registry persisted + reloaded) | VERIFIED | `ConversationRegistry.load(thread_id)` (`registry.py:83-119`) selects from live `entity_registry`; `upsert_delta` (`registry.py:166-236`) persists inside lock; 2 tests in `TestSC2_ResumeAcrossRestart` simulate restart via `del reg1` + fresh `load()` and assert identical surrogate |
| SC#3 | Surrogates round-trip back to real values across LLM letter-case variations | VERIFIED | `RedactionService.de_anonymize_text` (`redaction_service.py:323-390`) uses `re.IGNORECASE` (line 370) + 2-pass placeholder substitution; 3 tests in `TestSC3_DeAnonRoundTripCaseSensitive` exercise upper/lower/title case round-trips successfully |
| SC#4 | Hard-redacted placeholders (`[CREDIT_CARD]`, `[US_SSN]`, …) never appear as registry keys (one-way) | VERIFIED | `anonymize()` (`anonymization.py:240-242`) handles `bucket=="redact"` with `f"[{ent.type}]"` and never mutates `entity_map`; delta-loop in `_redact_text_with_registry` only iterates `entity_map.items()`; 3 tests in `TestSC4_HardRedactNotInRegistry` query live DB to confirm no `CREDIT_CARD` rows + `4111` substring absent + survives de-anon round-trip |
| SC#5 | Two simultaneous chat requests on same thread introducing same new entity → single registry row (no race, no duplicate surrogates) | VERIFIED | Per-thread `asyncio.Lock` via `_thread_locks` + `_thread_locks_master` (`redaction_service.py:68-69, 120-134`); composite UNIQUE `(thread_id, real_value_lower)` (migration 029 line 23, applied to live DB); 2 tests in `TestSC5_RegistryRace` use `asyncio.gather` and assert `len(rows) == 1` against live `entity_registry` table |

**Score:** 5/5 ROADMAP Success Criteria VERIFIED.

### Per-Plan Must-Haves Audit

| Plan | Must-Have | Status | Evidence |
|------|-----------|--------|----------|
| 02-01 | Migration file 029 exists & well-formed SQL | VERIFIED | `supabase/migrations/029_pii_entity_registry.sql` (45 lines) |
| 02-01 | `entity_registry` has all 8 D-22 columns with exact types | VERIFIED | Lines 13-24 of migration; live DB query confirmed `column_count=9` (8 + `id`) |
| 02-01 | Composite UNIQUE `(thread_id, real_value_lower)` present | VERIFIED | `unique (thread_id, real_value_lower)` at line 23 (inline) |
| 02-01 | thread_id FK ON DELETE CASCADE; source_message_id nullable + ON DELETE SET NULL | VERIFIED | Lines 15 + 20 of migration |
| 02-01 | RLS enabled with NO user-facing policies (D-25) | VERIFIED | Line 38 enables RLS; zero `create policy` statements; live verification: `relrowsecurity=true`, `policy_count=0` |
| 02-01 | `handle_entity_registry_updated_at` trigger wired | VERIFIED | Lines 33-35 of migration |
| 02-02 | `EntityMapping` Pydantic model with 5 fields, frozen | VERIFIED | `registry.py:47-62`, `model_config = ConfigDict(frozen=True)` |
| 02-02 | `ConversationRegistry` skeleton: `__init__(thread_id, rows)`, `lookup`, `entries`, `forbidden_tokens`, `thread_id` property | VERIFIED | `registry.py:65-164` |
| 02-02 | D-31 advisory-lock FUTURE-WORK note in module docstring | VERIFIED | `registry.py:15-20` |
| 02-03 | Migration 029 applied to live Supabase DB | VERIFIED | `python -c "client.table('entity_registry').select('id').limit(0).execute()"` returns successfully against project `qedhulpfezucnfadlfiz` |
| 02-03 | RLS enabled, zero policies on live DB | VERIFIED | FK-violation smoke test surfaces `foreign key` error (not RLS denial) — service-role bypasses RLS as designed |
| 02-03 | Composite UNIQUE queryable | VERIFIED | Tests SC#5 + SC#1 row-count assertions both succeed |
| 02-04 | `ConversationRegistry.load(thread_id)` async classmethod, one SELECT, populated instance | VERIFIED | `registry.py:83-119`; `inspect.iscoroutinefunction(ConversationRegistry.load.__func__)` returns True |
| 02-04 | `upsert_delta(deltas)` issues one INSERT…ON CONFLICT DO NOTHING for the deltas | VERIFIED | `registry.py:166-236` uses `on_conflict="thread_id,real_value_lower"`, `ignore_duplicates=True` (lines 205-206) |
| 02-04 | Empty deltas list = no DB hop | VERIFIED | `if not deltas: return` at line 184; smoke test confirms `await r.upsert_delta([])` returns None |
| 02-04 | Service-role client used for ALL registry traffic (D-25) | VERIFIED | `registry.py:31` imports `get_supabase_client` (service-role); zero references to `get_supabase_authed_client` |
| 02-04 | Re-exports added to `redaction/__init__.py`: `ConversationRegistry`, `EntityMapping` (NOT `de_anonymize_text` — option b honored) | VERIFIED | `__init__.py:30-36`; `de_anonymize_text` not re-exported |
| 02-05 | `redact_text(text)` (registry=None) behaves exactly as Phase 1 | VERIFIED | `redaction_service.py:174-176` dispatches to `_redact_text_stateless` (Phase 1 body unchanged); 20/20 Phase 1 tests still pass |
| 02-05 | `redact_text(text, registry=...)` reuses surrogates, expands forbidden tokens, persists deltas | VERIFIED | `_redact_text_with_registry` (`redaction_service.py:233-321`); `anonymization.py:227-260` registry short-circuit + forbidden-token union |
| 02-05 | Module-level `_thread_locks` + `_thread_locks_master` serialise concurrent writers per thread (PERF-03) | VERIFIED | `redaction_service.py:68-69`; `_get_thread_lock` at lines 120-134; SC#5 race test passes |
| 02-05 | `de_anonymize_text(text, registry)` round-trips, case-insensitive, longest-match-first, hard-redact passthrough | VERIFIED | `redaction_service.py:323-390`; sort by `len(surrogate_value)` reverse (lines 353-357); `re.IGNORECASE` (line 370); 3 SC#3 tests pass + 2 SC#4 hard-redact passthrough tests pass |
| 02-05 | All new code paths log counts only, never real values (B4 / D-18 / D-41) | VERIFIED | `TestSC6_LogPrivacy.test_no_real_pii_in_log_output_registry_path` passes — caplog assert against 6 forbidden real-PII strings |
| 02-06 | All 5 Phase 2 ROADMAP SCs have at least one test class each | VERIFIED | 7 test classes in `test_redaction_registry.py`: TestSC1..TestSC5 + TestSC5b (D-37) + TestSC6 (B4) |
| 02-06 | SC#5 race test hits the REAL Supabase DB (no mock) | VERIFIED | `tests/api/test_redaction_registry.py:368-401` uses `client.table("entity_registry")` SELECT after `asyncio.gather`; asserts `len(rows) == 1` |
| 02-06 | Cross-turn surname collision test (PRD §7.5 / D-37) passes | VERIFIED | `TestSC5b_CrossTurnSurnameCollision::test_turn3_real_does_not_collide_with_turn1_surrogate` passes |
| 02-06 | Hard-redact survival test (D-35 / SC#4) passes | VERIFIED | 3 tests in `TestSC4_HardRedactNotInRegistry` all pass (CC not persisted; CC survives de-anon; synthetic placeholders survive) |
| 02-06 | Phase 1's 20 existing tests still pass alongside Phase 2 tests | VERIFIED | Combined `pytest tests/ -q` → 39 passed (20 Phase 1 + 15 Phase 2 integration + 4 Phase 2 unit) |
| 02-06 | No real PII in caplog during any Phase 2 test (B4 invariant) | VERIFIED | `TestSC6_LogPrivacy` enforces; passes with full DEBUG logging captured |

**Must-Haves Score:** 23/23 across all 6 plans.

### Required Artifacts

| Artifact | Status | Details |
|----------|--------|---------|
| `supabase/migrations/029_pii_entity_registry.sql` | VERIFIED | 45 lines, applied to live DB; all 4 sections present (table, indexes, trigger, RLS) |
| `backend/app/services/redaction/registry.py` | VERIFIED | 241 lines; `EntityMapping` (frozen) + `ConversationRegistry` (init / load / lookup / entries / forbidden_tokens / upsert_delta / thread_id property / __repr__) |
| `backend/app/services/redaction/__init__.py` | VERIFIED | 37 lines; re-exports `ConversationRegistry`, `EntityMapping` (NOT `de_anonymize_text` per option b) |
| `backend/app/services/redaction/anonymization.py` | VERIFIED | 286 lines; `anonymize()` accepts `registry: "ConversationRegistry | None" = None` (forward-ref); registry short-circuit at line 255; forbidden-token union at lines 226-230 |
| `backend/app/services/redaction_service.py` | VERIFIED | 403 lines; `_thread_locks` + `_thread_locks_master` at module scope; `_get_thread_lock`, `redact_text(text, registry=None)`, `_redact_text_stateless`, `_redact_text_with_registry`, `de_anonymize_text` all present |
| `backend/tests/conftest.py` | VERIFIED | 170 lines; Phase 1 fixtures (`seeded_faker`, `redaction_service`) preserved verbatim; 4 new fixtures (`test_user_id`, `fresh_thread_id`, `empty_registry`, `_reset_thread_locks`) added |
| `backend/tests/api/test_redaction_registry.py` | VERIFIED | 512 lines; 7 test classes, 15 tests, all PASS against live DB |
| `backend/tests/unit/__init__.py` | VERIFIED | Empty marker file |
| `backend/tests/unit/test_conversation_registry.py` | VERIFIED | 96 lines; 1 class, 4 tests, all PASS (no DB) |

### Key Link Verification (Wiring)

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `029_pii_entity_registry.sql` | `public.threads(id)` | FK on `entity_registry.thread_id` | WIRED | `references public.threads(id) on delete cascade` (line 15) |
| `029_pii_entity_registry.sql` | `public.messages(id)` | Nullable FK on `entity_registry.source_message_id` | WIRED | `references public.messages(id) on delete set null` (line 20) |
| `029_pii_entity_registry.sql` | `public.handle_updated_at()` | trigger `handle_entity_registry_updated_at` | WIRED | `execute function public.handle_updated_at()` (line 35) |
| `registry.py::ConversationRegistry.load` | `app.database.get_supabase_client` | service-role read | WIRED | Line 31 imports; line 98 calls; `asyncio.to_thread(_select)` at line 111 |
| `registry.py::ConversationRegistry.upsert_delta` | `entity_registry` table | service-role insert with ON CONFLICT | WIRED | `client.table("entity_registry").upsert(rows, on_conflict="thread_id,real_value_lower", ignore_duplicates=True)` (lines 200-208) |
| `redaction_service.py::redact_text` | `_get_thread_lock(registry.thread_id)` | per-thread asyncio.Lock | WIRED | Line 179; lock acquired before `_redact_text_with_registry` and released after upsert |
| `redaction_service.py::_redact_text_with_registry` | `registry.upsert_delta(deltas)` | delta persistence inside lock | WIRED | Line 300 `await registry.upsert_delta(deltas)` |
| `anonymization.py::anonymize` | `registry.lookup(ent.text)` + `registry.forbidden_tokens()` | thread-wide collision avoidance + surrogate reuse | WIRED | Lines 227-228 (forbidden-token union), 255-260 (lookup short-circuit before within-call scan) |
| `__init__.py` | `registry.ConversationRegistry`, `registry.EntityMapping` | Public re-export | WIRED | Line 30 import; line 32-36 `__all__` |
| Test suite | live `entity_registry` table | service-role insert via `redact_text` + verification SELECT | WIRED | 4 occurrences of `client.table("entity_registry")` in `test_redaction_registry.py`; 2 `asyncio.gather` race tests |

### I-4 Ordering Invariant

`anonymization.py:255` (`if registry is not None:` registry-lookup short-circuit) appears BEFORE `anonymization.py:264` (`existing = entity_map.get(ent.text)` within-call scan). VERIFIED via `grep -n` line-number comparison: 255 < 264.

### W-2 Invariant

`grep -c "UNKNOWN" backend/app/services/redaction_service.py` returns 1 — that single occurrence is in a comment at line 282 explaining "do not mask with UNKNOWN". The delta loop uses an `entity_index: dict[str, "Entity"]` (line 270) and an `assert ent is not None` (lines 283-286) guard. No fragile `"UNKNOWN"` fallback in any executable code path.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `entity_registry` table queryable via service-role | `python -c "get_supabase_client().table('entity_registry').select('id').limit(0).execute()"` | succeeds | PASS |
| FK enforced + RLS bypassed by service role | Insert with bogus thread_id → FK violation (not RLS denial) | `FK_OK_RLS_BYPASSED_BY_SERVICE_ROLE` | PASS |
| Module imports clean | `python -c "from app.main import app; print('OK')"` | OK | PASS |
| Signature checks (redact_text, de_anonymize_text, load, upsert_delta, anonymize) | Inline `inspect.signature` + `iscoroutinefunction` | `SIGNATURES_OK` | PASS |
| Pure-data primitives (lookup, entries copy, forbidden_tokens) | Inline assertions | `PURE_DATA_OK` | PASS |
| Empty `upsert_delta([])` short-circuits | `await r.upsert_delta([])` returns None | `EMPTY_UPSERT_OK` | PASS |
| Phase 1 regression suite | `pytest tests/api/test_redaction.py -q` | 20 passed | PASS |
| Phase 2 integration (live DB) | `pytest tests/api/test_redaction_registry.py -v` | 15 passed | PASS |
| Phase 2 unit | `pytest tests/unit/test_conversation_registry.py -v` | 4 passed | PASS |
| Combined regression | `pytest tests/ -q` | 39 passed, 12 warnings, 13.43s | PASS |

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|----------------|-------------|--------|----------|
| **REG-01** | 02-01, 02-02, 02-03, 02-04 | One entity registry per conversation/thread (no cross-conversation sharing) (FR-3.1) | **VALIDATED** | `entity_registry` table has `thread_id` FK to `threads(id)`; `ConversationRegistry.load(thread_id)` filters by thread_id; SC#1 + SC#2 tests confirm per-thread isolation |
| **REG-02** | 02-01, 02-02, 02-03, 02-04 | Persists registry to DB and reloads on conversation resume (FR-3.2) | **VALIDATED** | Migration 029 applied to live DB; `upsert_delta` (registry.py:166) writes; `load` (registry.py:83) reads; `TestSC2_ResumeAcrossRestart` (2 tests) PASS |
| **REG-03** | 02-01, 02-02, 02-04 | Registry lookups are case-insensitive (FR-3.3) | **VALIDATED** | `real_value_lower` column (migration line 17); `lookup()` uses `.casefold()` (registry.py:134); `TestSC1::test_*_case_insensitive_consistency` + `test_lookup_is_casefold_correct` PASS |
| **REG-04** | 02-01, 02-02, 02-04, 02-05 | Same real entity always produces same surrogate within conversation (FR-3.4) | **VALIDATED** | Composite UNIQUE `(thread_id, real_value_lower)` at DB layer (migration line 23); `registry.lookup` short-circuit in `anonymize()` (anonymization.py:255-260); `TestSC1::test_only_one_registry_row_per_lower_value` + `TestSC5_RegistryRace` PASS |
| **REG-05** | 02-01, 02-02, 02-04 | Hard-redacted entities NOT stored in registry (FR-3.5) | **VALIDATED** | `entity_map` returned by `anonymize()` excludes `bucket=="redact"` entries (anonymization.py:240-242); delta loop iterates `entity_map.items()` only; 3 tests in `TestSC4_HardRedactNotInRegistry` confirm no `CREDIT_CARD` rows in DB and `[CREDIT_CARD]` survives de-anon |
| **DEANON-01** | 02-05 | Replace surrogates back to real values before user-facing display (FR-5.1) | **VALIDATED** | `de_anonymize_text` (redaction_service.py:323-390); 3 tests in `TestSC3_DeAnonRoundTripCaseSensitive` PASS |
| **DEANON-02** | 02-05 | Case-insensitive matching to handle LLM case-reformatting (FR-5.2) | **VALIDATED** | `re.IGNORECASE` flag in pass-1 substitution (redaction_service.py:370); `test_uppercased_surrogate_resolves_to_original_real`, `test_titlecased_person_surrogate_resolves_to_original_real`, `test_mixed_case_surrogate_round_trip` all PASS |
| **PERF-03** | 02-05 | Concurrent writes to same registry serialized via async lock (NFR-3) | **VALIDATED** | `_thread_locks: dict[str, asyncio.Lock]` + `_thread_locks_master` (redaction_service.py:68-69); `_get_thread_lock` (lines 120-134); `TestSC5_RegistryRace` (2 tests) PASS — `asyncio.gather` produces exactly 1 row in live DB |

**Requirements Score:** 8/8 VALIDATED. ZERO orphaned requirements (every Phase 2 REQ-ID from REQUIREMENTS.md is claimed by at least one plan; all are met by implementation).

**Note on REQUIREMENTS.md status flips:** The traceability table in REQUIREMENTS.md (lines 222, 224, 236) currently lists REG-01..05, DEANON-01..02, and PERF-03 as `☐ Pending`. Based on this verification, those checkboxes are now eligible to be flipped to `✓ Complete` (or `Validated`) — that update is the orchestrator's responsibility on phase close (per the gsd-workflow), not the verifier's. This report explicitly authorizes the flip.

### Anti-Patterns Found

None. Per-file scan:

| File | Pattern | Result |
|------|---------|--------|
| `redaction_service.py` | `TODO|FIXME|XXX|HACK` | One TODO at line 168 — explicitly forward-references Phase 5 chat-loop integration; intentional and documented in plan 02-05. INFO-level, not blocking. |
| `redaction_service.py` | `UNKNOWN` literal in delta loop | NONE in code; only in comment at line 282 explaining what NOT to do (W-2 invariant) |
| `redaction_service.py` | Empty handlers / placeholder returns | None |
| `registry.py` | `TODO|FIXME|placeholder|coming soon` | None |
| `anonymization.py` | Single-line wrong-source `strip_honorific` import (B-3 trap) | NOT present (uses two-line split) |
| `__init__.py` | `de_anonymize_text` re-export (option a regression) | NOT present (option b honored) |
| Migrations | Edits to applied migrations 001-028 | None — only `029_*` is new |
| Logging surfaces | Real PII in `logger.*` calls | Verified clean by `TestSC6_LogPrivacy` (no Bambang / Sutrisno / Jakarta / +62-* / bambang.s@example.com leak in caplog) |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `ConversationRegistry._rows` | `_rows` | populated by `__init__(rows)` and `upsert_delta` after live DB INSERT; re-loaded by `load()` from live `entity_registry` SELECT | YES (live DB round-trip in tests) | FLOWING |
| `ConversationRegistry._by_lower` | `_by_lower` | rebuilt from `_rows` at construction; appended in `upsert_delta` | YES | FLOWING |
| `RedactionService._redact_text_with_registry::deltas` | `deltas` | computed by diffing `entity_map` (from real Presidio detection + Faker) against `registry._by_lower`; passed to `await registry.upsert_delta` | YES | FLOWING |
| `de_anonymize_text::placeholders` | `placeholders` | populated from `registry.entries()` after pass-1 substitution match (n>0) | YES | FLOWING |

No HOLLOW or DISCONNECTED artifacts.

### Human Verification Required

None.

All Phase 2 success criteria are programmatically verifiable and verified — no UI/visual/UX/external-service surface in this phase. Phase 5 will introduce the chat-router integration and SSE `redaction_status` events that need human verification; Phase 2 is purely backend service + DB + tests.

---

## Phase 1 Regression Baseline

Phase 1 has no `01-VERIFICATION.md` on disk (the file does not exist), but Phase 1 was marked complete on master (`2b18f8f chore(state): mark Phase 1 (Detection & Anonymization Foundation) complete`) with 20/20 tests passing. Phase 2 verification re-confirms zero regression: `pytest tests/api/test_redaction.py -q` reports `20 passed` after every Phase 2 plan, including the final combined run.

---

## Gaps Summary

None.

All 5 ROADMAP success criteria are implemented and tested against the live Supabase DB (project `qedhulpfezucnfadlfiz`). All 8 phase requirement IDs (REG-01..05, DEANON-01..02, PERF-03) are validated. All 23 plan must-haves pass. The combined pytest suite is 39/39 green with 0 failures and only pre-existing dependency-deprecation warnings.

Phase 2 ships the full conversation-scoped registry surface needed for Phase 3 (entity resolution can read `EntityMapping` rows) and Phase 5 (chat router will load registry per turn, pass to `redact_text`, call `de_anonymize_text` on LLM output). The advisory-lock upgrade path for multi-worker scale-out (D-31) is documented in both the migration SQL header and the registry module docstring for Phase 6.

---

## Phase Verdict

**PASSED** — Phase 2 goal achieved. 5/5 ROADMAP SCs verified, 8/8 REQ-IDs validated, 23/23 must-haves met, 39/39 tests pass against live DB, zero gaps, zero human verification items, zero regressions to Phase 1.

---

*Verified: 2026-04-26T01:50:00Z*
*Verifier: Claude (gsd-verifier)*
*Live DB: Supabase project qedhulpfezucnfadlfiz (entity_registry table applied via MCP per Plan 02-03)*
