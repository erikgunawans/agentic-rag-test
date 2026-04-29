---
phase: "06-embedding-provider-production-hardening"
plan: 8
plan_id: "06-08"
subsystem: "observability-tests"
title: "OBS-02 / OBS-03 thread_id + resolved-provider log coverage tests + final regression + CLAUDE.md doc note"
one_liner: "8 caplog regression tests (OBS-02 thread_id in 3 log paths, OBS-03 provider+thread_id in LLM audit logs, admin-toggle schema+runtime checks, B4 forbidden-tokens privacy invariant) + EMBED-02 gotcha note in CLAUDE.md; final phase regression 352/352 passed"
status: "complete"
tags: ["observability", "logging", "caplog", "thread_id", "obs-02", "obs-03", "embed-02", "b4-privacy", "phase-6-final"]
completed_at: "2026-04-29T07:45:01Z"
duration_seconds: 397
tasks_completed: 2
tasks_total: 2

dependency_graph:
  requires:
    - "06-04"  # thread_id correlation logging wiring
    - "06-05"  # title-gen template fallback
    - "06-06"  # PERF-02 latency regression test
    - "06-07"  # PERF-04 graceful-degradation tests
  provides:
    - "OBS-02 caplog coverage: thread_id in redact_text_batch + de_anonymize_text + egress_filter trip"
    - "OBS-03 caplog coverage: provider + thread_id in LLMProviderClient.call audit log"
    - "Admin-toggle schema default verification (Pydantic v2 model_fields)"
    - "B4 forbidden-tokens privacy regression gate (T-06-04-1 mitigation)"
    - "EMBED-02 deploy gotcha: EMBEDDING_PROVIDER switch does NOT auto re-embed"
  affects:
    - "backend/tests/services/redaction/test_thread_id_logging.py"
    - "CLAUDE.md"

tech_stack:
  added: []
  patterns:
    - "caplog.at_level(logging.DEBUG, logger=...) — captures structured log emissions for unit assertions"
    - "patch.object(ConversationRegistry, 'upsert_delta') — no-op to isolate logging path from DB I/O"
    - "Settings(**minimal_required_fields) — pydantic v2 instantiation with required fields to test schema default without env file"
    - "Real ConversationRegistry/EntityMapping constructor signatures (thread_id, rows) — no fabricated kwargs"
    - "Pydantic v2 Settings.model_fields[...].default — schema-layer default assertion (not v1 __fields__)"

key_files:
  created:
    - path: "backend/tests/services/redaction/test_thread_id_logging.py"
      purpose: "8 caplog tests: OBS-02 (3) + OBS-03 (2) + admin-toggle default (2) + B4 forbidden-tokens (1)"
  modified:
    - path: "CLAUDE.md"
      change: "Appended EMBED-02 gotcha bullet to Gotchas section (1 new bullet)"

decisions:
  - id: "D-P6-08-1"
    decision: "test_settings_default_is_true_at_runtime uses Settings(**required_fields) with env-var-pop for LLM_PROVIDER_FALLBACK_ENABLED to test schema default without _env_file=None (which fails on ValidationError for required fields)"

metrics:
  duration_seconds: 397
  completed_date: "2026-04-29"
  tests_before: 344
  tests_after: 352
  tests_added: 8
---

# Phase 06 Plan 08: OBS-02/OBS-03 Coverage Tests + Final Regression Summary

## One-liner

8 caplog regression tests (OBS-02 thread_id in 3 log paths, OBS-03 provider+thread_id in LLM audit logs, admin-toggle schema+runtime checks, B4 forbidden-tokens privacy invariant) + EMBED-02 gotcha note in CLAUDE.md; final phase regression 352/352 passed.

## What Was Built

### Task 1: OBS-02 / OBS-03 caplog tests + B4 regression + admin-toggle

Created `backend/tests/services/redaction/test_thread_id_logging.py` with 8 tests across 4 test classes:

| Class | Tests | Requirement |
|-------|-------|-------------|
| `TestThreadIdLogCoverage` | 3 | OBS-02 (D-P6-14..16): thread_id in redact_text_batch, de_anonymize_text, egress_filter trip logs |
| `TestResolvedProviderAuditLog` | 2 | OBS-03 (D-P6-17): provider + thread_id in LLMProviderClient.call audit log (success + error paths) |
| `TestAdminToggleOverridesFallbackDefault` | 2 | D-P6-09: llm_provider_fallback_enabled default=True at schema layer (model_fields) + runtime |
| `TestB4LogPrivacyForbiddenTokens` | 1 | T-06-04-1: no real_value or surrogate substring leaks into any log record across 4 call sites |

**pytest output (all 8):**
```
tests/services/redaction/test_thread_id_logging.py::TestThreadIdLogCoverage::test_thread_id_appears_in_redact_text_batch_log PASSED
tests/services/redaction/test_thread_id_logging.py::TestThreadIdLogCoverage::test_thread_id_appears_in_de_anonymize_text_log PASSED
tests/services/redaction/test_thread_id_logging.py::TestThreadIdLogCoverage::test_thread_id_appears_in_egress_filter_trip_log PASSED
tests/services/redaction/test_thread_id_logging.py::TestResolvedProviderAuditLog::test_resolved_provider_in_success_log PASSED
tests/services/redaction/test_thread_id_logging.py::TestResolvedProviderAuditLog::test_resolved_provider_in_error_log PASSED
tests/services/redaction/test_thread_id_logging.py::TestAdminToggleOverridesFallbackDefault::test_settings_default_is_true PASSED
tests/services/redaction/test_thread_id_logging.py::TestAdminToggleOverridesFallbackDefault::test_settings_default_is_true_at_runtime PASSED
tests/services/redaction/test_thread_id_logging.py::TestB4LogPrivacyForbiddenTokens::test_no_real_or_surrogate_substring_in_logs PASSED
8 passed, 1 warning in 3.67s
```

### Task 2: EMBED-02 Gotcha Note in CLAUDE.md

Appended 1 bullet to the `## Gotchas` section (line 152, immediately before `## Workflow`):

```
- **`EMBEDDING_PROVIDER` switch does NOT trigger re-embedding (Phase 6 / EMBED-02).**
  Setting `EMBEDDING_PROVIDER=local` and `LOCAL_EMBEDDING_BASE_URL=http://localhost:11434/v1`
  redirects FUTURE ingestions to the local endpoint (e.g., Ollama bge-m3 / nomic-embed-text).
  Existing document vectors stay in their original embedding space until manually re-ingested.
  RAG retrieval quality may degrade for queries that span both old and new chunks.
  Deployer-managed migration: re-ingest documents (drop + re-upload) when consolidating to a
  single provider.
```

### Task 3: Final Phase Regression (Auto-approved checkpoint)

⚡ Auto-approved: auto_advance=true configured in .planning/config.json

**Full non-slow regression:**
```
352 passed, 1 deselected, 591 warnings in 91.46s
```
(344 prior + 8 new = 352; 1 deselected = slow PERF-02 test excluded from run)

**PERF-02 slow test:**
```
tests/services/redaction/test_perf_latency.py::test_anonymization_under_500ms_dev_hardware SKIPPED
1 skipped, 2 warnings in 3.10s
```
Skipped on dev hardware (1939ms >= 500ms primary target); secondary 2000ms guard PASSED (not a regression per D-P6-07).

**Backend import check:**
```
python -c "from app.main import app; print('OK')"
OK
```

**Docs gate:**
```
grep -nE "EMBEDDING_PROVIDER" CLAUDE.md
152: - **`EMBEDDING_PROVIDER` switch does NOT trigger re-embedding (Phase 6 / EMBED-02).**...
```

**No-new-migration gate:**
```
find backend/migrations -name '*.sql' -newer .planning/phases/.../06-CONTEXT.md | wc -l
0
```

**Manual privacy-invariant inspection (B4 invariant):**
All log statements in `redaction_service.py` (lines 432, 517, 761, 924) and `llm_provider.py` (lines 193, 211, 222) contain only:
- `thread_id=%s` (Supabase UUID, non-PII)
- `batch_size=%d`, `hard_redacted_total=%d`, `ms=%.2f` (counts and timings)
- `feature=%s`, `provider=%s`, `source=%s`, `success=True/False`, `latency_ms=%d`, `error_type=%s` (metadata strings)

No raw `text`, `real_value`, or `surrogate_value` values are interpolated into any log line. B4 invariant holds.

## Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | OBS-02/OBS-03 caplog tests + B4 regression | 08ce7e4 | backend/tests/services/redaction/test_thread_id_logging.py |
| 2 | EMBED-02 CLAUDE.md gotcha note | d6a8c2a | CLAUDE.md |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Settings(_env_file=None) raises ValidationError for required fields**
- **Found during:** Task 1 (test_settings_default_is_true_at_runtime)
- **Issue:** `Settings(_env_file=None)` disables .env loading but 4 required fields (supabase_url, supabase_anon_key, supabase_service_role_key, openai_api_key) have no defaults. Raised `pydantic_core.ValidationError: 4 validation errors for Settings`.
- **Fix:** Changed to `Settings(**minimal_required_fields)` with dummy values for required fields + `os.environ.pop("LLM_PROVIDER_FALLBACK_ENABLED")` to temporarily clear any env override. Test still correctly verifies the schema default is used (not a hidden env var).
- **Files modified:** `backend/tests/services/redaction/test_thread_id_logging.py`
- **Commit:** 08ce7e4

## Known Stubs

None — all log assertions target the real implementation log lines from Plan 06-04. No placeholder logic.

## Threat Flags

None. No new network endpoints, auth paths, file access patterns, or schema changes introduced.
Test file only (Task 1) and documentation-only change (Task 2). Synthetic PII fixture strings
(Bambang Sutrisno, bambang.sutrisno@mitra-abadi.co.id, +62 812 3456 7890) match the existing
Plan 06-06 fixture set already committed to the repository (T-06-08-1 mitigation: no new realistic
PII strings introduced).

## Self-Check: PASSED

| File | Status |
|------|--------|
| backend/tests/services/redaction/test_thread_id_logging.py | FOUND |
| CLAUDE.md | FOUND (contains "Phase 6 / EMBED-02") |
| .planning/phases/06-embedding-provider-production-hardening/06-08-SUMMARY.md | FOUND |

| Commit | Message |
|--------|---------|
| 08ce7e4 | test(06-08): add OBS-02/OBS-03 caplog coverage tests + B4 forbidden-tokens regression |
| d6a8c2a | docs(06-08): add EMBED-02 gotcha note to CLAUDE.md (no auto-re-embedding on provider switch) |
