---
phase: 03-entity-resolution-llm-provider-configuration
plan: 07
subsystem: test-coverage
tags: [phase-3, pytest, egress-filter, llm-provider, success-criteria, b4-invariant]
requires:
  - 03-01-tracing-service-migration
  - 03-02-config-env-vars
  - 03-03-egress-filter
  - 03-04-llm-provider-client
  - 03-05-redaction-service-wiring
  - 03-06-admin-settings-section
provides:
  - "D-66 exhaustive egress-filter unit matrix"
  - "D-65 LLMProviderClient unit suite (mocked AsyncOpenAI)"
  - "Phase 3 SC#1..SC#5 integration coverage against live Supabase"
  - "B4 / D-55 log-privacy invariant tests for Phase 3 surface"
affects:
  - .planning/ROADMAP.md (Phase 3 verification gate)
tech-stack:
  added: []
  patterns:
    - "table-driven pure-function unit tests (egress_filter)"
    - "AsyncMock + MagicMock at module-level _get_client patch point"
    - "patch app.services.redaction_service.get_settings to control entity_resolution_mode"
    - "live Supabase round-trip with cascade-delete cleanup via fresh_thread_id fixture"
    - "system_settings TTL-cache propagation test via sync update_system_settings"
key-files:
  created:
    - backend/tests/unit/test_egress_filter.py
    - backend/tests/unit/test_llm_provider_client.py
    - backend/tests/api/test_resolution_and_provider.py
  modified: []
decisions:
  - "Plan code path `await update_system_settings(...)` is a Rule-1 bug — the function is sync. Tests call the sync version directly."
  - "Use SimpleNamespace mirror of Settings to override entity_resolution_mode in patch context (smaller blast radius than monkeypatching @lru_cache'd Settings)."
  - "_resolve_provider integration test uses ENV-cleared + DB-PATCH path to exercise D-51 priorities 4 (global_db) and 2 (feature_db)."
  - "SC#4 vacuous-true semantics for empty captured_payloads is acceptable — RESOLVE-04 is a NEGATIVE invariant and is preserved if no LLM call is made."
metrics:
  tests_added: 40
  tests_passing: 79
  tests_failing: 0
  duration_minutes: 25
  completed_date: 2026-04-26
---

# Phase 3 Plan 07: Pytest Coverage Summary

D-65 + D-66 + D-64 — 40 new tests across three files closing the Phase 3 verification loop. Combined regression: 79/79 pass against live Supabase project `qedhulpfezucnfadlfiz`.

## What Shipped

Three test files (1,034 lines total):

| File | Lines | Tests | Role |
|------|-------|-------|------|
| `backend/tests/unit/test_egress_filter.py` | 210 | 15 | D-66 egress-filter exhaustive matrix (pure-function, no DB, no SDK) |
| `backend/tests/unit/test_llm_provider_client.py` | 381 | 17 | D-65 LLMProviderClient unit suite (mocked AsyncOpenAI, mocked _get_client) |
| `backend/tests/api/test_resolution_and_provider.py` | 443 | 8 | Phase 3 SC#1..SC#5 integration + B4 log-privacy (live Supabase + mocked cloud SDK) |

## SC ↔ File Mapping

| ROADMAP SC | Test class | File | Result |
|------------|------------|------|--------|
| SC#1 — algorithmic clustering of name variants | `TestSC1_AlgorithmicClustering` (2 tests) | `test_resolution_and_provider.py` | PASSED |
| SC#2 — cloud egress trip → algorithmic fallback | `TestSC2_CloudEgressFallback` (1 test) | `test_resolution_and_provider.py` | PASSED |
| SC#3 — local LLM mode bypasses egress filter | `TestSC3_LocalModeBypassesEgress` (1 test) | `test_resolution_and_provider.py` | PASSED |
| SC#4 — non-PERSON normalize-only (RESOLVE-04) | `TestSC4_NonPersonNeverReachLLM` (1 test) | `test_resolution_and_provider.py` | PASSED |
| SC#5 — admin-UI provider switch propagates within cache TTL | `TestSC5_AdminUIProviderPropagation` (2 tests) | `test_resolution_and_provider.py` | PASSED |

Bonus: `TestSC6_LogPrivacy` (1 test) extends Phase 2's caplog invariant to the Phase 3 cloud-egress-trip path.

## D-66 Egress-Filter Matrix Coverage

The plan's required D-66 matrix entries are all present:

| Plan Requirement | Test Method | PASSED |
|------------------|-------------|--------|
| exact-match casefold trip | `test_exact_match_casefold_trips` | yes |
| word-boundary preservation (Johnson vs John) | `test_word_boundary_johnson_does_not_trip_on_john` | yes |
| multi-word value substring match | `test_multi_word_value_trips_on_substring` | yes |
| registry-only path (no provisional) | `test_registry_only_path_no_provisional` | yes |
| provisional-only path (no registry rows) | `test_provisional_only_path_no_registry_rows` | yes |
| empty registry + empty provisional | `test_empty_inputs_no_trip` + `test_empty_provisional_dict_no_trip` | yes |
| log-content invariant (B4 / D-55) | `test_log_content_invariant_no_raw_values` + `test_log_content_no_warning_when_clean` | yes |
| 8-char SHA-256 hash format | `test_match_hashes_are_8char_sha256` | yes |
| multi-match aggregation | `test_multiple_distinct_matches_all_counted` | yes |
| provisional extends scope | `test_provisional_extends_registry_scope` | yes |
| `_EgressBlocked` carries result | `test_egress_blocked_carries_result` | yes |
| `EgressResult` is frozen | `test_result_is_frozen` | yes |
| empty real_value skipped | `test_skips_empty_real_value` | yes |

15 tests total — exceeds plan's "≥10" floor.

## D-65 LLMProviderClient Unit Suite Coverage

| Plan Requirement | Test Method | PASSED |
|------------------|-------------|--------|
| D-51 default (no env, no DB) | `test_default_local_when_nothing_set` | yes |
| D-51 feature_env wins | `test_feature_env_wins_over_db` | yes |
| D-51 feature_db wins over global_env | `test_feature_db_wins_over_global_env` | yes |
| D-51 global_env wins over global_db | `test_global_env_wins_over_global_db` | yes |
| D-51 global_db used when no env | `test_global_db_used_when_no_env` | yes |
| D-51 invalid enum fall-through (env) | `test_invalid_env_value_falls_through` | yes |
| D-51 invalid enum fall-through (DB) | `test_invalid_db_value_skipped` | yes |
| Local mode bypasses egress (FR-9.2) | `test_local_call_does_not_invoke_egress_filter` | yes |
| Cloud trip raises pre-SDK | `test_cloud_egress_trip_raises_egress_blocked_pre_call` | yes |
| Cloud clean payload passes | `test_cloud_clean_payload_passes_through` | yes |
| Cloud provisional in scope (D-56) | `test_cloud_provisional_surrogates_in_filter_scope` | yes |
| D-52 SDK exception propagates (cloud) | `test_5xx_propagates_to_caller` | yes |
| D-52 SDK exception propagates (local) | `test_local_5xx_propagates_to_caller` | yes |
| D-50 lazy cache same instance | `test_lazy_cache_returns_same_instance` | yes |
| D-50 cache separates providers | `test_lazy_cache_separates_providers` | yes |
| Non-JSON content wrapped safely | `test_non_json_response_wrapped_in_raw_key` | yes |
| None content wrapped safely | `test_none_content_returns_dict_with_empty_raw` | yes |

17 tests total — exceeds plan's "≥10" floor.

## Test Counts Per File

| File | Tests | Phase 3 share |
|------|-------|---------------|
| `tests/unit/test_egress_filter.py` (NEW) | 15 | new |
| `tests/unit/test_llm_provider_client.py` (NEW) | 17 | new |
| `tests/api/test_resolution_and_provider.py` (NEW) | 8 | new |
| `tests/unit/test_conversation_registry.py` (Phase 2) | 4 | regression |
| `tests/api/test_redaction.py` (Phase 1) | 20 | regression |
| `tests/api/test_redaction_registry.py` (Phase 2) | 15 | regression |
| **Total** | **79** | — |

Plan's combined-regression floor: ≥45. Actual: 79. Margin: +34.

## Combined Regression

Run from `/backend`:

```bash
set -a && . .env && set +a && source venv/bin/activate \
  && pytest tests/ -v --tb=short
```

Result: `79 passed, 12 warnings in 18.13s`.

All 39 Phase 1 + Phase 2 baseline tests still pass; 40 Phase 3 tests added; 0 failures.

## Rule-1 Deviation Applied

**Issue:** Plan code path used `await update_system_settings({"llm_provider": "cloud"})` in SC#5. The function is sync (`backend/app/services/system_settings_service.py` L23), so awaiting a non-awaitable would raise `TypeError`.

**Fix:** SC#5 tests call `update_system_settings(...)` directly without `await`. The cache invalidation behaviour (sync write → in-memory `_cache = None`) still satisfies the SC#5 propagation requirement.

**Files modified:** `backend/tests/api/test_resolution_and_provider.py` only — the live `system_settings_service.py` was not touched.

**Documented:** SC#5 test docstring explicitly notes the bug.

## B4 / D-55 Log-Privacy Invariant — Phase 3 Surface

| Layer | Test | Verified |
|-------|------|----------|
| `egress_filter()` WARNING line | `test_egress_filter.py::test_log_content_invariant_no_raw_values` | raw value ABSENT, 8-char SHA-256 hash PRESENT |
| `egress_filter()` no-trip silence | `test_egress_filter.py::test_log_content_no_warning_when_clean` | no WARNING when no trip |
| `redact_text()` cloud-fallback path | `test_resolution_and_provider.py::TestSC6_LogPrivacy` | no real PII in any caplog record across the cloud-trip flow |
| `redact_text()` cloud-trip path | `test_resolution_and_provider.py::TestSC2_CloudEgressFallback` (caplog assertion) | "John Doe" not in any captured log message |

Combined with the Phase 1 + Phase 2 caplog regression tests, the no-real-PII-in-logs invariant is enforced across the entire chat-time redaction pipeline.

## Threat Model Mitigations Verified

| Threat ID | Mitigation | Test |
|-----------|-----------|------|
| T-CI-01 (Info Disclosure) | Tests assert NEGATIVE invariants (`not in`) so passing tests don't echo PII | All log + payload assertions use `not in` form |
| T-DB-01 (Tampering — variant rows after test) | `fresh_thread_id` cascades delete via `entity_registry.thread_id` ON DELETE CASCADE (Phase 2 D-22) | All live-DB tests use `fresh_thread_id` |
| T-CACHE-01 (Tampering — system_settings pinned) | SC#5 wraps PATCH calls in try/finally that restores the original value | `test_provider_switch_propagates_within_cache_window` finally block |
| T-NETWORK-01 (Reliability — accidental cloud call) | Every cloud-mode test patches `_get_client` with a MagicMock — real `AsyncOpenAI` never instantiated | `test_cloud_egress_trip_raises_egress_blocked_pre_call`, `TestSC2_*`, `TestSC6_*` |

## What's NOT Covered (Intentionally Deferred)

- **End-to-end chat-loop SSE buffering and de-anonymized response delivery** — Phase 5 territory (BUFFER-01..03).
- **Cross-provider failover (cloud↔local crossover)** — D-52 ships the knob; behaviour deferred to Phase 6 (PERF-04).
- **Title generation / metadata extraction LLM provider switch** — pre-existing flows continue to use OpenRouter; Phase 4–6 picks up.
- **Output-side filter on cloud LLM responses** — PRD does not require it; FUTURE-WORK.
- **Postgres advisory locks for cross-process safety** — Phase 2 D-31; Phase 6 hardening.

## Self-Check: PASSED

- File `backend/tests/unit/test_egress_filter.py` exists (210 lines, ≥90 floor): FOUND
- File `backend/tests/unit/test_llm_provider_client.py` exists (381 lines, ≥120 floor): FOUND
- File `backend/tests/api/test_resolution_and_provider.py` exists (443 lines, ≥200 floor): FOUND
- Commit `e74dbf6` (Task 1, egress filter unit matrix): FOUND
- Commit `104e62c` (Task 2, LLM provider client unit suite): FOUND
- Commit `97d2684` (Task 3, SC#1..SC#5 integration): FOUND
- Combined regression `pytest tests/` returns 79 passed, 0 failed: VERIFIED

Phase 3 EXECUTION COMPLETE.
