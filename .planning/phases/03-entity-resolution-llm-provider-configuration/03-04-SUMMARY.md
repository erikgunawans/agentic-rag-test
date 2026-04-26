---
phase: 03-entity-resolution-llm-provider-configuration
plan: 04
subsystem: llm-provider
tags: [llm-provider, egress-filter, async-openai, observability, security]
wave: 4
requires:
  - 03-02-config-env-vars (settings.local_llm_*, settings.cloud_llm_*, per-feature override fields, llm_provider_timeout_seconds, llm_provider_fallback_enabled)
  - 03-03-egress-filter (egress_filter, EgressResult, _EgressBlocked from app.services.redaction.egress)
  - phase-1 tracing_service (@traced parenthesised form)
  - phase-2 system_settings_service (get_system_settings 60s TTL cache)
provides:
  - LLMProviderClient (single class, async call() entry point for all 5 features)
  - _resolve_provider helper (D-51 5-step resolution order)
  - _get_client lazy AsyncOpenAI cache (D-50)
  - OBS-03 resolved-provider INFO audit log
affects:
  - 03-05 redaction_service wiring (consumer — wraps call() with algorithmic-fallback try/except)
  - phase-4 missed-PII scan, fuzzy de-anon (consumers via feature='missed_scan'|'fuzzy_deanon')
  - phase-5/6 title_gen, metadata (consumers via feature='title_gen'|'metadata')
tech-stack:
  added: []
  patterns:
    - lazy module-level singleton (dict keyed by provider literal)
    - @traced(name=...) decorator (Phase 1 D-16)
    - error_type=type(exc).__name__ (B4 invariant — never exc.str())
    - response_format={'type':'json_object'} (CLAUDE.md structured-output rule)
key-files:
  created:
    - backend/app/services/llm_provider.py (227 lines)
  modified: []
decisions:
  - "Used isinstance(db, dict) guard in _resolve_provider before .get() — defensive against test fixtures or DB hiccups returning None; D-51 says 'treat invalid as unset'."
  - "Cloud client api_key uses 'or \"missing-cloud-key\"' placeholder so AsyncOpenAI init never echoes the real key value through SDK error formatting (D-58 secret-hygiene). The actual call returns 401, which the caller's algorithmic-fallback wrapper catches (D-52)."
  - "Egress trip log line emitted from LLMProviderClient.call (in addition to egress.py's own WARNING) carries success=False latency_ms egress_tripped=True — keeps the OBS-03 resolved-provider audit format consistent across success and trip paths."
  - "json.dumps(messages, ensure_ascii=False) before egress scan — preserves non-ASCII Indonesian names in the haystack so casefold() comparisons match registry values."
metrics:
  duration_minutes: 7
  task_count: 2
  file_count: 1
  completed: 2026-04-26
---

# Phase 3 Plan 4: LLM Provider Client Summary

LLMProviderClient: single async class, egress-gated cloud path, D-51 5-step provider resolution, OBS-03 audit log emitted on every call.

## What Shipped

`backend/app/services/llm_provider.py` (227 lines, exceeds 180-line minimum).

### Public Exports

| Symbol | Kind | Purpose |
|--------|------|---------|
| `LLMProviderClient` | class | Single entry point for all 5 future auxiliary LLM features (entity_resolution, missed_scan, fuzzy_deanon, title_gen, metadata) — D-49 |
| `_resolve_provider(feature)` | function | D-51 resolution: feature_env > feature_db > global_env > global_db > default('local'); returns `(provider, source)` tuple |
| `_get_client(provider)` | function | Lazy AsyncOpenAI cache keyed by provider literal — D-50 |
| `_Feature` | Literal | 5-feature enum (entity_resolution / missed_scan / fuzzy_deanon / title_gen / metadata) |
| `_EgressBlocked` | exception (re-export) | Carries `EgressResult`; raised pre-cloud-call on egress trip — D-54 |

### Behavioural Invariants Verified

| Invariant | Decision | Test Evidence |
|-----------|----------|---------------|
| 5-step resolution order | D-51 | RESOLVE_OK smoke-test covers all 5 paths (default, feature_env, global_env, feature_db, global_db) + bad-enum-skipped |
| Cloud egress filter runs BEFORE SDK call | D-53/D-54/D-56 | Sentinel SDK stub never invoked when registry contains a value matching the payload; `_EgressBlocked` raised with `tripped=True`, `match_count=1`, `entity_types=['PERSON']` |
| Local mode bypasses egress filter | FR-9.2 | `egress_invoked=0` after local-mode call with a non-empty registry passed in |
| Lazy AsyncOpenAI cache | D-50 | `_get_client('local') is _get_client('local')` returns same instance |
| @traced(name="llm_provider.call") | D-49/D-63 | Decorator present on `async def call`; smoke test verifies via source-text grep |
| INFO audit log on every call | OBS-03/D-63 | Format: `event=llm_provider_call feature=... provider=... source=... success=... latency_ms=...` — emitted on success, trip, and exception paths |
| Error log uses class name only | B4/T-AUTH-01 | `error_type=%s` formatted from `type(exc).__name__`, never `str(exc)` |
| `response_format={'type':'json_object'}` | CLAUDE.md | Source-text grep verified |
| Cloud key placeholder | D-58 | `settings.cloud_llm_api_key or "missing-cloud-key"` — empty key never echoed through SDK init/error |

## Resolution-Order Test Results (5 Paths)

```
default          → ('local', 'default')           ✓
feature_env=cloud → ('cloud', 'feature_env')      ✓
global_env=cloud → ('cloud', 'global_env')        ✓
feature_db=local → ('local', 'feature_db')        ✓
global_db=cloud → ('cloud', 'global_db')          ✓
bad enum at all layers → ('local', 'default')     ✓ (defense in depth)
```

## Lazy-Cache Verification

```python
c1 = _get_client('local')
c2 = _get_client('local')
assert c1 is c2  # PASS — module-level dict cache reused
```

## Egress-Trip End-to-End Test

```python
# Setup: registry contains 'Bambang Sutrisno', payload mentions same value, provider=cloud
# Stub _clients['cloud'] with sentinel that asserts on any SDK call.
await client.call(feature='entity_resolution', messages=[...], registry=_FakeRegistry(), ...)
# → _EgressBlocked raised pre-SDK
# → e.result.tripped == True
# → e.result.match_count == 1
# → e.result.entity_types == ['PERSON']
# → e.result.match_hashes == ['36cd66ef']  # 8-char SHA-256, no raw values
# → SDK sentinel.create() NEVER invoked
```

WARNING log line emitted by egress.py (verified in stdout):
```
egress_filter_blocked event=egress_filter_blocked match_count=1 entity_types=['PERSON'] match_hashes=['36cd66ef']
```

INFO log line emitted by LLMProviderClient.call (verified):
```
llm_provider_call event=llm_provider_call feature=entity_resolution provider=cloud source=global_env success=False latency_ms=N egress_tripped=True
```

## Local-Mode Bypass Test

```python
# Setup: provider=local, registry contains 'Bambang Sutrisno', payload mentions raw real name.
# Wrap egress_filter to count invocations.
await client.call(feature='entity_resolution', messages=[...], registry=registry, ...)
# → egress_invoked['count'] == 0   ✓
# → result is the canned dict from local-LLM mock
```

FR-9.2 invariant holds: local mode operates on raw real content with no third-party egress.

## Phase 1 + Phase 2 Regression

py_compile syntax check passes:
```
PYCOMPILE_OK
```

Phase 1 + Phase 2 imports unaffected — `llm_provider.py` is a NEW file with NO modifications to existing modules. The only outbound dependency edges are:
- `from openai import AsyncOpenAI` (already in requirements.txt)
- `from app.config import get_settings` (Plan 03-01 added the new fields)
- `from app.services.redaction.egress import egress_filter, EgressResult, _EgressBlocked` (Plan 03-03)
- `from app.services.system_settings_service import get_system_settings` (Phase 2)
- `from app.services.tracing_service import traced` (Phase 1)

Plan 03-05 (redaction_service wiring) is now unblocked.

## Threat-Model Mitigations Verified

| Threat ID | Disposition | Verification |
|-----------|-------------|--------------|
| T-EGR-01 (Real PII reaches cloud LLM) | mitigate | Cloud branch ALWAYS calls egress_filter before SDK; on trip raises _EgressBlocked PRE-CALL. Sentinel SDK never invoked in trip test. |
| T-AUTH-01 (CLOUD_LLM_API_KEY exfiltration) | mitigate | Error log uses `error_type=type(exc).__name__` (class name only). Empty key replaced with `"missing-cloud-key"` placeholder. Source-text grep finds zero `str(exc)` or `repr(exc)` formatters. |
| T-EGR-02 (INFO audit log leaks payload) | mitigate | Log line includes only feature, provider, source, success, latency_ms. Source grep confirms NO `messages=` or `payload=` field in any logger call. |
| T-DOS-01 (Hung cloud call blocks asyncio.Lock) | mitigate | Both AsyncOpenAI instances pass `timeout=settings.llm_provider_timeout_seconds` (default 30s). |
| T-FALLBACK-01 (Cloud failure crashes chat loop) | mitigate | _EgressBlocked + generic Exception both PROPAGATE OUT of call(); LLMProviderClient itself never catches them. The redaction_service wrapper (Plan 03-05) owns the algorithmic fallback per D-52. |
| T-CONFIG-01 (Bad enum from env/DB) | mitigate | `_resolve_provider` validates against `_VALID_PROVIDERS = ("local", "cloud")` at every layer; invalid values are skipped (treated as unset). Verified via bad-enum smoke test. |

## Deviations from Plan

None — plan executed exactly as written. Both task action blocks were applied verbatim; smoke tests in the verify blocks pass; all acceptance criteria met.

## Self-Check: PASSED

- File `backend/app/services/llm_provider.py` exists (227 lines).
- Both commits exist in git log: `a54443c` (Task 1) and `cfdaf03` (Task 2).
- Source contains all required tokens: `egress_filter(`, `_EgressBlocked(result)`, `@traced(name="llm_provider.call")`, `event=llm_provider_call`, `response_format={"type": "json_object"}`, `from openai import AsyncOpenAI`, `from app.services.redaction.egress import`, `from app.services.system_settings_service import get_system_settings`, `_Feature = Literal[`, `class LLMProviderClient:`, `_clients: dict[Literal["local", "cloud"], AsyncOpenAI] = {}`.
- Smoke tests RESOLVE_OK + CLIENT_OK + EGRESS_BLOCK_OK + LOCAL_BYPASS_OK + PYCOMPILE_OK all printed.
