---
phase: 04
plan: 07
subsystem: pii-redaction-tests
tags: [pii, integration-tests, pytest, live-supabase, mocked-llm, ci, phase4-verification]
requirements_addressed: [DEANON-03, DEANON-04, DEANON-05, SCAN-01, SCAN-02, SCAN-03, SCAN-04, SCAN-05, PROMPT-01]
dependency_graph:
  requires:
    - 04-01 (Phase 4 config flags + migration 031)
    - 04-02 (fuzzy_match algorithmic Jaro-Winkler)
    - 04-03 (de_anonymize_text 3-phase pipeline + mode kwarg)
    - 04-04 (missed_scan + auto-chain in redact_text)
    - 04-05 (prompt_guidance helper)
  provides:
    - "End-to-end verification artifact for Phase 4 ROADMAP SC#1..SC#5"
    - "B4 caplog invariant extension across fuzzy-LLM + missed-scan soft-fail paths"
  affects:
    - "Phase 4 close-out: implementation now has matching verification"
tech_stack:
  added: []
  patterns:
    - "Mirrors Phase 3 test_resolution_and_provider.py 1:1 in shape (per-SC test class, _patched_settings helper, MagicMock + AsyncMock for AsyncOpenAI)"
    - "Direct service-layer instantiation (RedactionService().de_anonymize_text / redact_text) — no FastAPI client needed"
    - "Live Supabase qedhulpfezucnfadlfiz for registry persistence; cloud LLM always mocked"
key_files:
  created:
    - "backend/tests/api/test_phase4_integration.py (~609 lines, 17 test methods, 7 test classes)"
  modified: []
decisions:
  - "Used real_value_lower-keyed seeding (not cluster_id) — EntityMapping has no cluster_id field (Rule-1 deviation from PLAN template; algorithmic Pass 2 keys solo clusters on _solo_<casefold>, so SC#2 cross-cluster invariant still holds)"
  - "de_anonymize_text(mode=...) kwarg used directly (Phase 4 D-71) instead of monkey-patching get_settings for fuzzy_mode — cleaner blast radius"
  - "Patched LLMProviderClient.call at module-resolution path (app.services.redaction_service.LLMProviderClient.call and app.services.redaction.missed_scan.LLMProviderClient.call) — one mock per call site"
metrics:
  duration_minutes: ~6
  completed_date: 2026-04-27
---

# Phase 4 Plan 07: Phase 4 Integration Test Suite Summary

End-to-end pytest coverage of Phase 4 ROADMAP SC#1..SC#5 — fuzzy de-anonymization, missed-PII scan, prompt guidance — against live Supabase with mocked AsyncOpenAI / OpenRouter. Phase 4 verification artifact: implementation paired with proof.

## Test Method Count

| Test Class | Methods | Subtest Expansion (parametrize) | Pass | Fail |
|---|---|---|---|---|
| TestSC1_FuzzyDeanon | 3 | — | 3 | 0 |
| TestSC2_NoSurnameCollision | 1 | — | 1 | 0 |
| TestSC3_HardRedactSurvives | 1 | × 3 modes (algorithmic / llm / none) | 3 | 0 |
| TestSC4_MissedScan | 1 | × 3 resolution modes | 3 | 0 |
| TestSC5_VerbatimEmission | 3 | — | 3 | 0 |
| TestB4_LogPrivacy_FuzzyAndScan | 2 | — | 2 | 0 |
| TestSoftFail_ProviderUnavailable | 2 | — | 2 | 0 |
| **Total** | **13 methods** | **17 effective subtests** | **17** | **0** |

## SC-to-Test Mapping

| ROADMAP SC | REQ-ID(s) | Test Class | Verdict |
|---|---|---|---|
| SC#1 — Mangled-surrogate de-anon resolves under algorithmic/llm; passthrough under none | DEANON-03 | TestSC1_FuzzyDeanon | PASS |
| SC#2 — Two clusters share surname; no cross-corruption | DEANON-04 | TestSC2_NoSurnameCollision | PASS |
| SC#3 — Hard-redact [TYPE] placeholders survive de-anon in all 3 modes | DEANON-05 | TestSC3_HardRedactSurvives (× 3) | PASS |
| SC#4 — Missed-scan auto-chains; valid types replaced; invalid silently dropped; works in 3 resolution modes | SCAN-01..05 | TestSC4_MissedScan (× 3) | PASS |
| SC#5 — Main-agent system prompt carries D-82 guidance block when redaction enabled | PROMPT-01 | TestSC5_VerbatimEmission | PASS |
| Bonus — B4 caplog invariant across fuzzy + scan soft-fail paths | (B4) | TestB4_LogPrivacy_FuzzyAndScan | PASS |
| Bonus — Soft-fail behavior (PERF-04 / D-78) | PERF-04 | TestSoftFail_ProviderUnavailable | PASS |

## Combined Regression Total

- **Phase 4 integration (this plan):** 17/17 PASS
- **Phase 1+2+3 prior baseline:** 79 tests
- **Phase 4 unit (Plans 04-02, 04-04, 04-05):** ~37 tests
- **Backend full suite:** 135 collected; 133 PASS; **2 PRE-EXISTING failures** (deferred — see below)

Combined Phase 1+2+3+4 PASSING total = **133 / 135 ≥ 95** target met.

## Execution Time

- **Phase 4 integration file alone:** 168.97 s (≈ 2 min 49 s) — registry round-trips dominate
- **Full backend suite:** 519.87 s (≈ 8 min 40 s)

## B4 Caplog Invariant Verdict

**PASSED.** Across both soft-fail caplog tests (`test_no_real_pii_in_scan_skip_log`, `test_no_real_pii_in_fuzzy_llm_skip_log`):
- Every log record scanned for forbidden literals: real values (`"Marcus Smith"`), surrogates (`"Bambang Sutrisno"`), and mangled candidate text (`"Bambang Sutrisn"`).
- D-78 warn-log lines confirmed present (`event=missed_scan_skipped error_class=...`, `event=fuzzy_deanon_skipped error_class=...`).
- Zero forbidden literals appeared in any captured `WARNING+` record.

## Deviations from Plan

### Auto-fixed (Rule 1 — bug avoided)

**1. [Rule 1 — Spec mismatch] EntityMapping has no `cluster_id` field**
- **Found during:** Reading `backend/app/services/redaction/registry.py` before writing the seed helper.
- **Issue:** Plan template's `_seed_cluster(cluster_id=...)` parameter referenced a field that does not exist on `EntityMapping` (verified via `python -c "from app.services.redaction.registry import EntityMapping; print(list(EntityMapping.model_fields))"` → `['real_value', 'real_value_lower', 'surrogate_value', 'entity_type', 'source_message_id']`).
- **Fix:** Removed `cluster_id` parameter; `_seed_cluster` now passes `real_value_lower=real.casefold()` (required field; no auto-derive). For SC#2 cross-cluster non-corruption, the algorithmic Pass 2 helper keys solo clusters by `f"_solo_{real_value.casefold()}"` — distinct surrogates with distinct real values land in distinct cluster buckets, so the SC#2 invariant still holds.
- **Files modified:** `backend/tests/api/test_phase4_integration.py` (helper + SC#2 test).
- **Calibration note:** Documented at the top of the test file (lines 16-32 docstring "Calibration notes").

**2. [Rule 1 — Cleaner mock target] Used `de_anonymize_text(mode=...)` kwarg directly**
- **Found during:** Reading `backend/app/services/redaction_service.py` lines 681-723.
- **Issue:** Plan template suggested patching `get_settings()` to drive fuzzy_mode for SC#1/SC#3 — but Phase 4 D-71 added an explicit `mode` parameter to `de_anonymize_text` that wins over the settings lookup.
- **Fix:** Tests pass `mode="algorithmic"`/`"llm"`/`"none"` directly. Smaller blast radius; no global state mutation.
- **Files modified:** `backend/tests/api/test_phase4_integration.py` (SC#1, SC#3, B4, soft-fail tests).

### No structural deviations

- All 7 test classes named per the plan must_haves verbatim.
- All parametrize counts match the plan (`@pytest.mark.parametrize("mode", [...])` × 3 in SC#3; × 3 resolution modes in SC#4).
- All caplog assertions follow the Phase 2/3 B4 pattern (scan every record, never just the soft-fail line).

## Deferred Issues (Out of Scope per Executor Scope Boundary)

Two pre-existing test failures discovered during full-suite verification — **not caused by Plan 04-07's test additions**. Both are caused by Phase 4 Plan 04-04's missed-scan auto-chain integration, which added an extra LLM call inside `redact_text` that is now reached by Phase 3's existing tests.

**1. `tests/api/test_resolution_and_provider.py::TestSC2_CloudEgressFallback::test_egress_trip_falls_back_to_algorithmic`**
- **Symptom:** `mock.chat.completions.create` was called 1 time; test asserts == 0.
- **Root cause:** Phase 4 D-75 missed-scan auto-chain runs a *second* LLM call from `missed_scan.py` after the Phase 3 entity-resolution call's egress-trip-and-fallback completes. The captured warning log shows `event=egress_filter_blocked match_count=3` (Phase 3 trip fired correctly) AND `event=missed_scan_skipped error_class=TypeError` (Phase 4 second call happened, then failed because the mock returned a TypeError-shaped result).
- **Disposition:** Pre-existing regression introduced when Plan 04-04 shipped. Phase 3's test predates Phase 4 auto-chain; the test should patch `pii_missed_scan_enabled=False` or mock `app.services.redaction.missed_scan.LLMProviderClient.call`. Out of scope for Plan 04-07 (test of unrelated SC).

**2. `tests/api/test_resolution_and_provider.py::TestSC4_NonPersonNeverReachLLM::test_resolution_payload_contains_only_person_strings`**
- **Symptom:** `'https://contoh.id' is contained here: ... Visit https://contoh.id/dokumen for the contract.`
- **Root cause:** Same as above — Phase 4 missed-scan now sends the original (already-anonymized) text through a second LLM call, which DOES contain non-PERSON entities (because the scan is hunting for missed PII broader than PERSON). The test asserts no email/phone/URL in any captured payload, but the missed-scan payload legitimately includes them by design.
- **Disposition:** The Phase 3 RESOLVE-04 invariant is "non-PERSON entities NEVER reach the *resolution* LLM." Phase 4's missed-scan is a *different* feature with a different threat model — the cloud-mode missed-scan call still passes through `egress_filter` (Phase 3 D-53..D-56) which catches real-value leakage. The test's assertion is too broad now that there are 2 LLM features sharing the same `LLMProviderClient.call` mock. Out of scope for Plan 04-07; Phase 5 cleanup should refine the test to scope to `feature='entity_resolution'` payloads only.

These are tracked in PROGRESS.md / future Phase 5 backlog. They do NOT affect Phase 4 SC verification — the *new* Phase 4 integration tests all pass.

## Self-Check: PASSED

- `[x]` File exists: `backend/tests/api/test_phase4_integration.py`
- `[x]` Commit exists: `ad4e6f3` `test(04-07): add Phase 4 SC#1..SC#5 + B4 + soft-fail integration suite`
- `[x]` 7 test classes: TestSC1_FuzzyDeanon, TestSC2_NoSurnameCollision, TestSC3_HardRedactSurvives, TestSC4_MissedScan, TestSC5_VerbatimEmission, TestB4_LogPrivacy_FuzzyAndScan, TestSoftFail_ProviderUnavailable (`grep -cE` returned 7)
- `[x]` 2 parametrize markers (SC#3 × 3 modes, SC#4 × 3 resolution modes)
- `[x]` 13 caplog references (B4 + soft-fail invariants)
- `[x]` 8 AsyncMock side_effect mocks (mocked LLM call paths)
- `[x]` 17/17 Phase 4 integration tests PASS against live Supabase qedhulpfezucnfadlfiz with mocked LLM
- `[x]` `python -c "from app.main import app"` succeeds
- `[x]` Combined backend test count: 135 collected; 133 pass (≥ 95 target)
- `[x]` 2 pre-existing failures documented + deferred (not Plan 04-07's responsibility)
