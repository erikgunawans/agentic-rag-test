---
phase: 04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance
plan: 04
status: complete
completed: 2026-04-27
applied_by: gsd-executor (Tasks 1+2) + orchestrator (Task 3 — test recovery after worktree env-var collection failure)
subsystem: missed-pii-scan + auto-chain
tags: [pii, missed-scan, llm-provider, soft-fail, re-ner, observability, recursion-cap]
dependency_graph:
  requires:
    - "Plan 04-01 SHIPPED — Settings.fuzzy_deanon_mode (unused here) + pii_missed_scan_enabled (Phase 3 D-57) + pii_redact_entities"
    - "Plan 04-03 SHIPPED — de_anonymize_text 3-phase pipeline available; redaction_service.py is in working state"
    - "Phase 3 SHIPPED — LLMProviderClient with feature='missed_scan' Literal already in _Feature enum (D-49); egress filter (D-53..D-56)"
  provides:
    - "scan_for_missed_pii(anonymized_text, registry) → (text, replacement_count) — auto-chained inside _redact_text_with_registry"
    - "Pipeline shape: detect → anonymize → missed-scan → re-anonymize-if-replaced → return (D-75)"
    - "Single-re-run cap via _scan_rerun_done parameter (D-76 / FR-8.5)"
  affects:
    - "Plan 04-07 integration tests (TestSC4_MissedScan asserts auto-chain across all 3 entity-resolution modes)"
tech_stack:
  added: []
  patterns:
    - "soft-fail (D-78): triple-catch _EgressBlocked / ValidationError / Exception → WARNING log error_class only → return (input, 0)"
    - "substring-match (D-77): re.subn(re.escape(text), '[TYPE]', text) — handles multi-mention; type whitelist via Settings.pii_redact_entities"
    - "recursion cap: _scan_rerun_done: bool = False internal kwarg — second pass cannot trigger a third"
    - "@traced(name='redaction.missed_scan') (Phase 1 D-16 pattern)"
key_files:
  created:
    - backend/app/services/redaction/missed_scan.py
    - backend/tests/unit/test_missed_scan.py
    - .planning/phases/04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance/04-04-SUMMARY.md
  modified:
    - backend/app/services/redaction_service.py
decisions:
  - "Task 3 (unit tests) recovered by the orchestrator after the spawned executor's worktree could not collect tests — the worktree lacks backend/.env, so module-level Settings() validation in tracing_service.py:_resolve_provider() failed at import time. Solution: merge worktree commits into master first (where .env exists), then run tests from main repo. Test logic itself is identical to plan template; no semantic changes."
  - "Single-re-run cap implemented via internal _scan_rerun_done: bool = False kwarg on _redact_text_with_registry — convention prefix prevents accidental external use; first re-run sets True; second pass returns scan_replacements=0 unconditionally."
metrics:
  duration_seconds: 800  # approximate combined: spawned executor ~390s + orchestrator recovery ~410s
  tasks_completed: 3
  tasks_blocked: 0
  files_modified: 1
  files_created: 2
  completed_date: "2026-04-27"
requirements_addressed: [SCAN-01, SCAN-02, SCAN-03, SCAN-04, SCAN-05]
self_check: passed (Task 1 module shipped via executor commit c9cbd66; Task 2 auto-chain shipped via executor commit 7bb21c5; Task 3 tests shipped via orchestrator commit 5bd026f after env-recovery; 13/13 missed_scan unit tests pass; full unit suite 75/75 pass; backend imports clean)
---

# Phase 4 Plan 04: Missed-PII Scan + Auto-Chain — SUMMARY

## One-liner

`backend/app/services/redaction/missed_scan.py` adds an LLM-driven post-anonymize PII scan with substring-match replacement, type whitelist enforcement, and triple-catch soft-fail. Auto-chained inside `RedactionService._redact_text_with_registry` after the existing anonymize step (D-75); single-re-run cap (D-76) prevents unbounded recursion. 13 unit tests across 3 D-XX classes (D-75 gating, D-77 schema/replace, D-78 soft-fail + B4 log privacy) — full suite green at 75/75.

## Status: COMPLETE — 3/3 TASKS SHIPPED

| Task | Commit | Outcome |
|------|--------|---------|
| 1. `missed_scan.py` module | `c9cbd66` | LLM scan with Pydantic-validated `MissedScanResponse` schema, type whitelist, soft-fail |
| 2. Auto-chain in `_redact_text_with_registry` | `7bb21c5` | Pipeline gain: detect → anonymize → scan → re-anonymize-if-replaced |
| 3. Unit tests | `5bd026f` | 13 tests across `TestD75_Gating`, `TestD77_SchemaAndReplace`, `TestD78_SoftFail` |

## Tasks 1+2 — module + auto-chain (executor)

The spawned `gsd-executor` agent produced two atomic commits in its worktree:
- **`c9cbd66 feat(04-04): add missed_scan.py LLM scan module (D-75/D-77/D-78)`** — 130-line module with `MissedEntity` (extra=forbid, type 1..64 chars, text 1..1000 chars), `MissedScanResponse` (max 100 entities), `_valid_hard_redact_types()` reading from `Settings.pii_redact_entities`, and the public `scan_for_missed_pii(...)` async coroutine. Triple-catch (`_EgressBlocked` / `ValidationError` / `Exception`) returns `(input, 0)` on any failure. WARNING logs carry `error_class` only — never raw text or counts of unreplaced entities.
- **`7bb21c5 feat(04-04): auto-chain missed-scan in _redact_text_with_registry (D-75/D-76)`** — splices `scan_for_missed_pii` after the existing `restore_uuids(...)` step. New `_scan_rerun_done: bool = False` kwarg controls single-re-run cap (D-76). On replacement: `await self._redact_text_with_registry(scanned_text, registry, _scan_rerun_done=True)` — re-entrant call computes a fresh delta + upsert against the new surrogate positions. Span attributes (`missed_scan_enabled`, `missed_scan_replacements`, `scan_rerun_pass`) emitted via `try/except` on `opentelemetry.trace.get_current_span()` — tracing failures NEVER affect functional behavior (B4-adjacent invariant).

## Task 3 — unit tests (orchestrator recovery)

The executor's Task 3 was blocked at pytest collection: the worktree lacks `backend/.env`, so `tracing_service.py:_resolve_provider()` (called at module import time) failed Pydantic Settings validation when the test file imported `missed_scan` (which transitively imports `tracing_service`). Other unit tests in the worktree (`test_egress_filter.py`, `test_fuzzy_match.py`) collect fine because they don't transit `tracing_service`.

**Recovery path:** merged executor commits (`c9cbd66`, `7bb21c5`) into master via `git merge --ff-only worktree-agent-af9cc1542e564831b`, copied the worktree's draft test file to `backend/tests/unit/test_missed_scan.py`, ran tests from main repo backend dir (where `.env` lives), all 13 tests pass on first run.

**Test breakdown (13 tests, 3 classes):**
- `TestD75_Gating` (3) — `pii_missed_scan_enabled=False` → `(input, 0)`; LLMProviderClient never instantiated; empty `pii_redact_entities` also early-exits
- `TestD77_SchemaAndReplace` (6) — valid type replaced via `re.subn(re.escape(...), '[TYPE]', ...)`; invalid type silently dropped; mixed valid+invalid (only valid replaced); multi-mention via `subn` (count assertion); empty entities list returns unchanged; Pydantic `ValidationError` on missing `type` field → soft-fail
- `TestD78_SoftFail` (4) — `TimeoutError` → unchanged; `RuntimeError` → unchanged; `caplog` invariant: no raw PII (`Alice`, `Smith`, `555-0000`) in any log record; `_EgressBlocked` → unchanged

All async tests use `pytest.mark.asyncio` + `unittest.mock.AsyncMock` patching of `LLMProviderClient` — zero cloud egress in CI.

## Must-haves coverage (10 truths)

| Truth | Status |
|-------|--------|
| Module exposes `async def scan_for_missed_pii(anonymized_text, registry) -> tuple[str, int]` | ✅ |
| Gated by `Settings.pii_missed_scan_enabled` | ✅ |
| LLM dispatch via `LLMProviderClient.call(feature='missed_scan', ...)` | ✅ |
| Pydantic `MissedScanResponse` model `{entities: [{type, text}]}` | ✅ |
| Server validates `entity.type ∈ Settings.pii_redact_entities` (invalid silently dropped) | ✅ — `TestD77` |
| Server replaces via `re.subn(re.escape(text), f'[{type}]', anonymized_text)` | ✅ |
| Auto-chained in `_redact_text_with_registry` AFTER anonymize step | ✅ — line 543 |
| Re-run on replacement (D-76) with single-re-run cap | ✅ — `_scan_rerun_done=True` |
| Soft-fail (D-78) — triple-catch + B4 log invariant | ✅ — `TestD78` |
| `@traced(name='redaction.missed_scan')` | ✅ |

## Recursion-cap verification

`_redact_text_with_registry` accepts `_scan_rerun_done: bool = False`. First call: `_scan_rerun_done=False`, scans, may recurse with `_scan_rerun_done=True`. Recursive call: `_scan_rerun_done=True`, the `if not _scan_rerun_done:` guard at L538 skips the entire scan block — returns the result of the second anonymize pass. **No third pass possible.** This is verified structurally (single guard) rather than via test (a recursion-counting test would require state injection).

## Regression posture

- Phase 1 redaction tests: untouched
- Phase 2 round-trip tests (DEANON-01, DEANON-02): untouched (the auto-chain runs only when `pii_missed_scan_enabled=True`; Phase 2 tests do not enable the flag, so the splice is bypass)
- Phase 3 entity-resolution + LLM-provider tests: untouched
- Wave-2/3 unit tests (fuzzy_match: 23, prompt_guidance: 11): all pass
- New: 13 missed_scan unit tests
- **Aggregate:** 75/75 unit tests pass; `from app.main import app` clean

## Deviations

1. **Task 3 recovery deviation (Rule 3 — workaround for missing .env):** The executor's worktree could not collect tests due to missing `backend/.env`. Recovery: merged executor commits to master first, then ran tests from main repo. Test content is verbatim per plan template — no semantic changes. Future executor invocations should either (a) symlink `.env` into worktrees, or (b) accept that test execution happens post-merge.
2. **Span attribute robustness:** Span attributes wrapped in `try/except` to swallow OTel-not-installed / no-active-span errors (Rule 3 — gracefully degrade observability rather than break functional behavior). Documented in inline comment at `redaction_service.py:646`.

## Pointers

- Module: `backend/app/services/redaction/missed_scan.py:1`
- Auto-chain splice: `backend/app/services/redaction_service.py:534-553`
- Recursion-cap kwarg: `backend/app/services/redaction_service.py:471`
- Tests: `backend/tests/unit/test_missed_scan.py:1`
