---
phase: 06-embedding-provider-production-hardening
verified: 2026-04-29T08:30:00Z
status: human_needed
score: 4/5 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Run `pytest tests/services/redaction/test_perf_latency.py -m slow -v --tb=short` on hardware capable of < 500ms Presidio call (i.e., not the dev machine used in the summary which measured 1939ms)"
    expected: "1 passed — elapsed_ms < 500 printed in output"
    why_human: "The test uses pytest.skip (not assert) for the 500ms primary assertion. On dev hardware it SKIPPED at 1939ms. SC#2 requires the latency is actually under 500ms, not merely that a test file exists. This requires execution on appropriate hardware (CI or faster dev machine) to confirm the PERF-02 budget is met in practice."
gaps:
  - truth: "Anonymization completes in under 500ms for a typical chat message (< 2000 tokens) — measured by a latency-budget regression test"
    status: partial
    reason: "The regression test exists and is correctly structured (real Presidio, session-warm-up fixture, @pytest.mark.slow). However, the test SKIPPED on dev hardware (1939ms >= 500ms). The plan changed the primary assertion from a hard `assert elapsed_ms < 500` to `pytest.skip()` at >= 500ms to accommodate hardware variability. SC#2 demands the latency IS under 500ms — not just that a test harness exists. The 2000ms secondary guard passed, but that is only a gross-regression guard, not proof of the PERF-02 budget."
    artifacts:
      - path: "backend/tests/services/redaction/test_perf_latency.py"
        issue: "Primary assertion (elapsed_ms < 500) replaced with pytest.skip() at line 357-364. Test SKIPPED at 1939ms on dev hardware (06-06-SUMMARY.md). SC#2 is unverified until run on hardware that passes the < 500ms gate."
    missing:
      - "Run the slow test on a faster machine (ideally CI) and confirm 1 passed with elapsed_ms < 500ms. Update SUMMARY with the passing timing record."
---

# Phase 6: Embedding Provider & Production Hardening Verification Report

**Phase Goal:** Ship the `EMBEDDING_PROVIDER` switch, the v1.0 latency target, the graceful provider-failure degradation paths, and the full debug + audit logging — closing out the milestone with a production-ready, observable, resilient redaction system.
**Verified:** 2026-04-29T08:30:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `EMBEDDING_PROVIDER=cloud` preserves existing OpenAI flow; `EMBEDDING_PROVIDER=local` routes to OpenAI-API-compatible local endpoint; switching does NOT trigger re-embedding | ✓ VERIFIED | `embedding_service.py` L16-24: branch on `settings.embedding_provider`; cloud path `AsyncOpenAI(api_key=...)` byte-identical; local path `AsyncOpenAI(base_url=..., api_key="not-needed")`; `config.py` L60-61 adds fields env-var only (no migration); CLAUDE.md L152 documents EMBED-02 no-auto-re-embed |
| 2 | Anonymization completes in under 500ms for a typical chat message (< 2000 tokens) — measured by a latency-budget regression test | ? UNCERTAIN | Test file exists with correct structure (real Presidio, session-warm-up, `@pytest.mark.slow`). Primary assertion changed to `pytest.skip()` instead of hard fail. SKIPPED at 1939ms on dev hardware per 06-06-SUMMARY.md. 2000ms secondary guard passed. SC#2 unverified until < 500ms confirmed on capable hardware. |
| 3 | When LLM_PROVIDER unavailable: entity resolution falls back to algorithmic, missed-PII scan is skipped, title/metadata uses 6-word template fallback — failures logged, never crash loop, never leak PII | ✓ VERIFIED | `redaction_service.py`: `_resolve_clusters_via_llm` catches `_EgressBlocked` + `Exception`; returns `algorithmic_clusters, True, reason, egress_tripped`. `missed_scan.py` L102-121: 3 except branches return `(anonymized_text, 0)`. `chat.py` L640-651: `except Exception:` replaced with 6-word template fallback using `" ".join(anonymized_message.split()[:6]) or "New Thread"`, de-anons via `mode="none"`, persists + SSE-emits. Test coverage: `test_perf04_degradation.py` 5 tests pass. |
| 4 | Debug-level logs capture per-operation: entities detected, surrogates assigned, fuzzy matches, missed-PII scan results, UUID-filter drops, resolved LLM provider per call, pre-flight egress-filter results — all verifiable by inspecting a single chat turn's log block | ✓ VERIFIED | `detection.py` L213-216: `thread_id: str \| None = None` param; conditional debug log with `thread_id=` field. `redaction_service.py` L433, L518, L762, L925: `thread_id=%s` in 4 debug log call sites. `egress.py` L120-123: `thread_id=%s` in WARNING log. `missed_scan.py` L104-120: `thread_id=%s` in all 3 soft-fail WARNING paths. `llm_provider.py` L183: `thread_id = registry.thread_id if registry is not None else "-"` + L195,213,224: `thread_id=%s` in all 3 logger.info audit calls. Test coverage: `test_thread_id_logging.py` 8 caplog tests pass. |
| 5 | Every LLM call records its resolved provider for audit; production smoke-test suite extends to full anonymize → resolve → buffer → de-anonymize round-trip without raw-PII leakage | ✓ VERIFIED | `llm_provider.py` L213: `"thread_id=%s feature=%s provider=%s source=%s success=True..."` — resolved provider logged in all 3 paths. `test_thread_id_logging.py::TestResolvedProviderAuditLog` (2 tests) asserts `provider=local\|cloud` + `thread_id` in audit log. Round-trip coverage: `test_phase5_integration.py::test_no_pii_in_any_llm_payload` + `test_no_pii_in_logs_happy_path` (pre-existing Phase 5 smoke tests) exercise the full anonymize→resolve→buffer→de-anonymize path. |

**Score:** 4/5 truths verified (SC#2 UNCERTAIN — pending hardware confirmation)

### Key Decision Verification

| Decision | Status | Evidence |
|----------|--------|----------|
| D-P6-01: EMBEDDING_PROVIDER env-var only, no system_settings column | ✓ VERIFIED | `config.py` L60: `embedding_provider: Literal["local", "cloud"] = "cloud"` (pydantic-settings field); no migration added |
| D-P6-04: Switching provider does NOT trigger re-embedding | ✓ VERIFIED | No batch-re-embed script; no migration; CLAUDE.md L152 documents the deployer-managed approach |
| D-P6-09: `llm_provider_fallback_enabled` default flipped to True | ✓ VERIFIED | `config.py` L102: `llm_provider_fallback_enabled: bool = True  # Phase 6 D-P6-09` |
| D-P6-12: Title-gen fallback formula `" ".join(anonymized_message.split()[:6])`, empty → "New Thread" | ✓ VERIFIED | `chat.py` L643: `stub = " ".join(anonymized_message.split()[:6]) or "New Thread"` |
| D-P6-15: `detect_entities()` has backward-compatible optional `thread_id: str \| None = None` | ✓ VERIFIED | `detection.py` L213-216: `def detect_entities(text: str, thread_id: str \| None = None)` |
| D-P6-16: redaction_service debug logs carry `thread_id` from `registry.thread_id` | ✓ VERIFIED | `redaction_service.py` L433,518,762,925 all include `registry.thread_id` |
| D-P6-17: `LLMProviderClient.call()` audit log includes `thread_id` when registry supplied | ✓ VERIFIED | `llm_provider.py` L183: sentinel "-" when `registry is None`; all 3 logger.info calls include `thread_id` |
| CR-02 fix: `model_validator` raises at startup when `EMBEDDING_PROVIDER=local` + empty `LOCAL_EMBEDDING_BASE_URL` | ✓ VERIFIED | `config.py` L128-136: `@model_validator(mode="after")` `_validate_local_embedding()` raises `ValueError` |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/config.py` | 2 new settings + 1 default flip | ✓ VERIFIED | `embedding_provider`, `local_embedding_base_url`, `llm_provider_fallback_enabled=True` |
| `backend/pyproject.toml` | `[tool.pytest.ini_options]` with `slow` marker | ✓ VERIFIED | Only markers block; no build-system sections |
| `backend/app/services/embedding_service.py` | Provider branch in `__init__` | ✓ VERIFIED | L16-24: `if settings.embedding_provider == "local": ...` |
| `backend/app/services/redaction/detection.py` | Optional `thread_id` param + conditional log | ✓ VERIFIED | L213-216, L301-327 |
| `backend/app/services/redaction_service.py` | `thread_id` in 4 debug logs; `detect_entities` call passes `thread_id=registry.thread_id` | ✓ VERIFIED | L433,518,623,762,925 |
| `backend/app/services/redaction/egress.py` | `thread_id` in trip log | ✓ VERIFIED | L120-123 |
| `backend/app/services/redaction/missed_scan.py` | `thread_id` in all 3 soft-fail WARNING calls | ✓ VERIFIED | L104-120 |
| `backend/app/services/llm_provider.py` | `thread_id` in all 3 audit log paths | ✓ VERIFIED | L183,L195,L213,L224 |
| `backend/app/routers/chat.py` | 6-word template fallback replacing `except Exception: pass` | ✓ VERIFIED | L640-651: template + de-anon + persist + SSE |
| `backend/tests/services/redaction/test_perf_latency.py` | `@pytest.mark.slow` PERF-02 test with real Presidio | ✓ VERIFIED (structure) / ? UNCERTAIN (timing) | Exists with correct structure; SKIPPED at 1939ms on dev hardware |
| `backend/tests/services/redaction/test_perf04_degradation.py` | 3 test classes, 5 tests | ✓ VERIFIED | 5 tests covering entity-resolution, missed-scan, title-gen fallbacks |
| `backend/tests/services/redaction/test_thread_id_logging.py` | 4 test classes, 8 caplog tests | ✓ VERIFIED | 8 tests: OBS-02 (3) + OBS-03 (2) + admin-toggle (2) + B4 (1) |
| `backend/tests/unit/test_embedding_provider_branch.py` | 3 unit tests | ✓ VERIFIED | 3 tests: cloud branch, local branch, batch serial check |
| `CLAUDE.md` | EMBED-02 gotcha note | ✓ VERIFIED | L152: bullet added to Gotchas section |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `embedding_service.py:__init__` | `settings.embedding_provider`, `settings.local_embedding_base_url` | `get_settings()` at module-level | ✓ WIRED | Module-level `settings = get_settings()`; branch reads `settings.embedding_provider` |
| `redaction_service.py:_redact_text_with_registry` | `detection.py:detect_entities` | `detect_entities(text, thread_id=registry.thread_id)` | ✓ WIRED | L623: confirmed |
| `egress.py:egress_filter` | `registry.thread_id` | `logger.warning` kwarg | ✓ WIRED | L122: `registry.thread_id` as second arg |
| `llm_provider.py:LLMProviderClient.call` | `registry.thread_id` | sentinel or registry lookup | ✓ WIRED | L183: `thread_id = registry.thread_id if registry is not None else "-"` |
| `chat.py:event_generator` | `anonymized_message.split()[:6]` | title-gen except handler | ✓ WIRED | L643: formula present; L644-648: de-anon + persist + SSE |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `embedding_service.py` | `self.client` | `settings.embedding_provider` branch | Yes — real AsyncOpenAI construction | ✓ FLOWING |
| `chat.py` title-gen fallback | `stub` | `anonymized_message.split()[:6]` (outer-scope var) | Yes — first 6 words of real turn | ✓ FLOWING |
| `redaction_service.py` debug logs | `registry.thread_id` | `ConversationRegistry` instance | Yes — Supabase UUID per thread | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Settings defaults correct | `python -c "from app.config import get_settings; s=get_settings(); assert s.embedding_provider=='cloud' and s.local_embedding_base_url=='' and s.llm_provider_fallback_enabled is True; print('OK')"` | OK (06-01 SUMMARY) | ✓ PASS |
| Backend imports cleanly | `python -c "from app.main import app; print('OK')"` | OK (06-08 SUMMARY) | ✓ PASS |
| Slow test excluded from default CI | `pytest tests/unit -m 'not slow' -q` | 352 passed, 1 deselected (06-08 SUMMARY) | ✓ PASS |
| PERF-02 slow test actual timing | `pytest tests/services/redaction/test_perf_latency.py -m slow -v --tb=short` | SKIPPED at 1939ms on dev hardware (06-06 SUMMARY) | ? UNCERTAIN — needs faster hardware |
| No new migrations | `find backend/migrations -name '*.sql' -newer 06-CONTEXT.md` | 0 (06-08 SUMMARY) | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|------------|------------|-------------|--------|----------|
| EMBED-01 | 06-01, 06-03 | `EMBEDDING_PROVIDER=local\|cloud` switch | ✓ SATISFIED | `config.py` + `embedding_service.py` + 3 unit tests |
| EMBED-02 | 06-01, 06-03, 06-08 | Local endpoint, no auto-re-embed | ✓ SATISFIED | Local branch in `embedding_service.py`; `CLAUDE.md` gotcha note; no migration introduced |
| OBS-02 | 06-04, 06-08 | Debug logs capture all redaction-pipeline events with `thread_id` | ✓ SATISFIED | `thread_id` in 7 log call sites across 5 files; `test_thread_id_logging.py` 3 OBS-02 caplog tests pass |
| OBS-03 | 06-04, 06-08 | Each LLM call logs resolved provider | ✓ SATISFIED | `llm_provider.py` L183-226: `provider` + `thread_id` in all 3 audit paths; 2 OBS-03 caplog tests pass |
| PERF-02 | 06-02, 06-06 | < 500ms anonymization on < 2000 tokens | ? UNCERTAIN | Test harness exists; SKIPPED at 1939ms; 500ms assertion is `pytest.skip()` not hard fail on this hardware |
| PERF-04 | 06-01, 06-05, 06-07 | Graceful degradation for all 3 failure modes | ✓ SATISFIED | `_resolve_clusters_via_llm` fallback; `missed_scan.py` soft-fail; `chat.py` 6-word template; 5 regression tests pass; fallback default=True |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `chat.py` | 640 | `except Exception:` (bare, no `as exc`) | Info | Title-gen fallback cannot log `error_class` as the plan specified. The log line (`L649`) omits `error_class=%s` that Plan 06-05 documented. Not a functional blocker — fallback still fires and logs `thread_id`; the `error_class` omission is cosmetic. |
| `chat.py` | 650 | `except Exception: pass` (nested fallback swallows silently) | Info | No log on nested-fallback failure (plan intended a `logger.warning(..."title_gen_fallback_failed"...)` line). Not a blocker — NFR-3 preserved. |

### Human Verification Required

**1. PERF-02 Latency Budget — Primary Assertion**

**Test:** Run `cd backend && source venv/bin/activate && pytest tests/services/redaction/test_perf_latency.py -m slow -v --tb=short 2>&1` on faster hardware (CI runner or production server) after Presidio NER warm-up.

**Expected:** `1 passed` with elapsed_ms printed below 500.0 in the assertion message or test output.

**Why human:** The test SKIPPED on dev hardware (1939ms). The primary assertion is `pytest.skip()` not a hard `assert` — so this cannot be confirmed without running on capable hardware. SC#2 requires the latency IS under 500ms, not merely that a regression test file exists.

### Gaps Summary

**One gap blocking full PASS:** SC#2 (PERF-02 latency budget) is UNCERTAIN. The regression test file exists, uses real Presidio, and is correctly structured — but on the dev machine used during phase execution it took 1939ms and SKIPPED rather than PASSed. The plan changed the primary assertion from a hard `assert elapsed_ms < 500` to a `pytest.skip()` call, making it impossible to confirm SC#2 programmatically without running on appropriate hardware.

The secondary 2000ms guard (always a hard assert) passed at 1939ms, confirming there is no catastrophic regression, but the 500ms production target remains unconfirmed.

**Minor deviations (not blockers):**
- `chat.py` title-gen except handler: bare `except Exception:` (no `as exc`), so the `error_class` field planned for the fallback log line is absent. The fallback still fires and logs `thread_id` — NFR-3 is preserved.
- `chat.py` nested fallback: `except Exception: pass` (silently) instead of the planned `logger.warning("...title_gen_fallback_failed...")` line. Thread is never crashed; title stays "New Thread".

---

_Verified: 2026-04-29T08:30:00Z_
_Verifier: Claude (gsd-verifier)_
