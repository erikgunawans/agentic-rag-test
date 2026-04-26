---
phase: 02-conversation-scoped-registry-and-round-trip
plan: 05
status: complete
completed: 2026-04-26
---

# Plan 02-05: RedactionService wiring — SUMMARY

## What shipped

Two atomic commits widen the redaction surface from Phase 1's stateless model to Phase 2's conversation-scoped model, while preserving Phase 1's default behavior exactly (D-39 invariant: `registry=None` ⇒ no behavioural change).

**Commits:**

- `d0b8dc3` — `feat(02-05): widen anonymize() with registry-aware forbidden tokens + surrogate reuse`
- `9cc1f42` — `feat(02-05): widen RedactionService with registry + de_anonymize_text`

## Execution note

Task 2 was interrupted mid-plan by a usage-limit reset boundary; the executor agent had finished writing all source code but had not yet run the regression suite, committed Task 2, or written SUMMARY/STATE/ROADMAP updates. The orchestrator resumed by:

1. Inspecting the uncommitted diff in `redaction_service.py` (234 lines added across `_thread_locks`, `_get_thread_lock`, `redact_text`, `_redact_text_stateless`, `_redact_text_with_registry`, `de_anonymize_text`).
2. Running `pytest backend/tests/api/test_redaction.py -q` — 20/20 Phase 1 tests still pass.
3. Functional smoke testing `de_anonymize_text` against a pre-loaded registry — confirmed surrogate→real round-trip, hard-redact passthrough, and case-insensitive matching all work.
4. Grepping all `logger.*` call sites in `redaction_service.py` for `real_value` references — none in any log statement (B4 / D-18 / D-41 invariant preserved).
5. Committing Task 2 atomically with full context-restoring message.

## Files modified

- `backend/app/services/redaction/anonymization.py` (Task 1, commit `d0b8dc3`) — `anonymize()` accepts optional `registry` param; reuses existing surrogates via `registry.lookup()` and expands forbidden-token set with `registry.forbidden_tokens()` when provided.
- `backend/app/services/redaction_service.py` (Task 2, commit `9cc1f42`) — full RedactionService wiring (see commit message).

## Must-haves verified

| Must-have | Status | Evidence |
|-----------|--------|----------|
| `redact_text(text)` (Phase 1 default — `registry=None`) behaves exactly as before | ✓ | All 20 Phase 1 tests still green |
| `redact_text(text, registry=...)` reuses existing surrogates + expands forbidden tokens thread-wide + persists deltas | ✓ | `_redact_text_with_registry` calls `anonymize(..., registry=registry)` and `await registry.upsert_delta(deltas)` inside the per-thread lock |
| Module-level `_thread_locks` dict + `_thread_locks_master` lock serialise concurrent writers per thread | ✓ | Lines 67-69 + `_get_thread_lock` helper at line 120; PERF-03 satisfied |
| `de_anonymize_text(text, registry)` round-trips surrogates → real values, case-insensitive, longest-match-first; hard-redact passthrough | ✓ | Smoke test: `KAJEN HABIBI` → `Budi Santoso`; `[CREDIT_CARD]` / `[US_SSN]` unchanged |
| All new code paths log counts only — never real values | ✓ | grep confirmed: `real_value` appears only in EntityMapping construction, internal substitution variables, and an assertion message that uses `len(real_value)` |
| 20/20 Phase 1 regression tests still pass | ✓ | `pytest backend/tests/api/test_redaction.py -q` → "20 passed in 1.36s" |

## Smoke test (de_anonymize_text against pre-loaded registry)

```python
rows = [
    EntityMapping(real_value="Budi Santoso", real_value_lower="budi santoso",
                  surrogate_value="Kajen Habibi", entity_type="PERSON"),
    EntityMapping(real_value="budi@example.com", real_value_lower="budi@example.com",
                  surrogate_value="gmarbun@example.org", entity_type="EMAIL_ADDRESS"),
]
reg = ConversationRegistry(thread_id="...", rows=rows)

# Mixed case + hard-redact
out = await svc.de_anonymize_text(
    "Surat dari Kajen Habibi di gmarbun@example.org. [CREDIT_CARD] [US_SSN]",
    reg
)
# → "Surat dari Budi Santoso di budi@example.com. [CREDIT_CARD] [US_SSN]"

# Case-swapped surrogate
out2 = await svc.de_anonymize_text("KAJEN HABIBI emailed GMARBUN@EXAMPLE.ORG", reg)
# → "Budi Santoso emailed budi@example.com"
```

Both invariants hold.

## Architectural notes

**Placeholder-tokenized 2-pass over direct substitution**: the implementation chose `surrogate → <<PH_NNNN>> → real_value` over a single direct `surrogate → real_value` substitution. This is the safe pattern: it prevents the case where a real value happens to contain another surrogate as a substring (e.g. real "Bambang Sutrisno" contains surrogate "Sutrisno" from a different mapping). The plan called this "1-phase" in the sense of "no fuzzy matching pass" (the fuzzy phase is Phase 4 / DEANON-03..05); structurally it's already the right shape for Phase 4 to drop its fuzzy pass between the two existing passes without rewriting the call site.

**Per-thread asyncio.Lock + master lock**: `_thread_locks_master` guards the dict mutation when getting-or-creating a per-thread lock. The per-thread lock is held across `_redact_text_with_registry` so that the read-deltas-from-registry → write-to-DB → update-in-memory-state sequence is atomic at the asyncio level. The composite UNIQUE `(thread_id, real_value_lower)` constraint on `entity_registry` is the cross-process backstop (D-31 FUTURE-WORK Phase 6 will replace asyncio.Lock with `pg_advisory_xact_lock(hashtext(thread_id::text))` for multi-worker scale).

## Self-Check: PASSED

All 6 must-haves verified. Zero deviations from plan intent. Phase 1 regression suite green. Wave 5 (Plan 02-06 pytest coverage) is unblocked.
