---
phase: 05-chat-loop-integration-buffering-sse-status-tool-sub-agent-co
plan: 01
subsystem: redaction-service
tags: [pii, redaction, batch, off-mode-gate, asyncio-lock, perf, phase-5, wave-1]
requires:
  - "Phase 1 D-13/D-14: redact_text(text, registry=None) public method"
  - "Phase 1 D-15: get_redaction_service() @lru_cache singleton"
  - "Phase 1 D-16: @traced decorator (tracing_service.py)"
  - "Phase 2 D-30: per-thread asyncio.Lock primitive (_get_thread_lock)"
  - "Phase 2 D-32: INSERT-ON-CONFLICT-DO-NOTHING upsert path (entity_registry)"
  - "Phase 2 D-33: ConversationRegistry per-turn lazy load contract"
  - "Phase 4 D-71: _redact_text_with_registry re-entrant under held lock (memory observation #3221)"
  - "Phase 1 config field: settings.pii_redaction_enabled (default True)"
provides:
  - "RedactionService.redact_text D-84 service-layer early-return gate (lock-free off-mode identity)"
  - "RedactionService.redact_text_batch(texts, registry) -> list[str] — single-lock-acquisition history-anon primitive"
  - "@traced span name redaction.redact_text_batch with batch_size / hard_redacted_total / latency_ms attributes (B4-clean)"
affects:
  - "backend/app/services/redaction_service.py (single file modified)"
  - "Phase 5 Plan 05-04 chat.py D-93 history-anon batch site (now unblocked)"
  - "Phase 5 Plan 05-02 tool_redaction.py walker (now unblocked — D-91 collect-then-batch leaf strategy)"
tech-stack:
  added: []
  patterns:
    - "Defense-in-depth gate: top-level branch (D-84 chat.py) + service-layer early-return (D-84 redaction_service.py)"
    - "Single-lock-acquisition batch primitive: one async with lock: spans N per-string redactions"
    - "Span instrumentation invariant (B4 + Phase 1 D-18 + Phase 2 D-41): counts/timings only, NEVER raw text"
key-files:
  created:
    - "backend/tests/unit/test_redaction_service_d84_gate.py (146 lines, 5 tests)"
    - "backend/tests/unit/test_redact_text_batch.py (333 lines, 14 tests)"
  modified:
    - "backend/app/services/redaction_service.py (+128 / -6 net; final 1171 lines)"
decisions:
  - "Kept the off-mode identity at BOTH redact_text AND redact_text_batch (D-84 alignment). The batch primitive's off-mode is a shallow `list(texts)` copy — defensive against caller mutation."
  - "Strict registry-required ValueError on the new batch primitive. redact_text keeps `registry=None` for back-compat with Phase 1's stateless path; the batch primitive is a NEW chokepoint API where None is always a programming error (Plan 05-04 always loads a registry)."
  - "Mirrored the existing `_redact_text_with_registry` opentelemetry try/except pattern for span attributes inside redact_text_batch — uniform tracing surface across the public methods."
  - "Single in-order for-loop inside the held lock — no asyncio.gather, no sorting. T-05-01-2 mitigation: D-93 history reassembly relies on `zip(history, anonymized[:-1])` index alignment."
  - "Lock-hold semantics for the batch (T-05-01-3 — accepted): no release-between-strings. Phase 6 PERF-02 owns that micro-optimization per CONTEXT.md Claude's Discretion."
metrics:
  duration: "~10 minutes"
  completed: "2026-04-27"
  tasks_completed: 2
  tasks_total: 2
  commits: 4
  tests_added: 19
  tests_passing: "154/154 (135 baseline + 5 D-84 + 14 D-92)"
---

# Phase 5 Plan 01: Service-Layer Redaction Gate + Batch Primitive — Summary

**One-liner:** Materialized the Phase 1 D-84 early-return TODO inside `RedactionService.redact_text` and added the new `RedactionService.redact_text_batch(texts, registry) -> list[str]` single-asyncio.Lock-acquisition primitive — Phase 5 Wave 1 chokepoint that every other Phase 5 plan depends on.

## What Shipped

### Task 1 — D-84 service-layer early-return gate (commits `867165e` RED → `02d8d91` GREEN)

**Splice point:** `backend/app/services/redaction_service.py` lines 387-393 (the existing Phase 1 TODO comment block immediately before the `if registry is None:` branch inside `async def redact_text`).

**Removed:** 6-line TODO comment block (`# TODO(Phase 5): gate ...`).

**Added:** 11-line live early-return + 7-line docstring update describing the D-84 contract.

```python
# Phase 5 D-84: lock-free off-mode early return.
# Defense-in-depth — chat.py top-level branch (Plan 05-04) also gates
# at the request boundary, but every other future caller of
# redact_text benefits automatically from this service-layer short-
# circuit. Runs BEFORE _get_thread_lock and BEFORE any logger /
# span attribute set, so off-mode produces zero log spam, zero
# contention, and zero observable PII (T-05-01-1 mitigation).
if not get_settings().pii_redaction_enabled:
    return RedactionResult(
        anonymized_text=text,
        entity_map={},
        hard_redacted_count=0,
        latency_ms=0.0,
    )
```

Behavior:
- `PII_REDACTION_ENABLED=true` (default): byte-identical to Phase 4 — all 135 baseline tests still pass.
- `PII_REDACTION_ENABLED=false`: identity `RedactionResult` for ALL three call shapes — `redact_text(text)`, `redact_text(text, registry=None)`, `redact_text(text, registry=<loaded>)`.
- Off-mode short-circuits BEFORE `_get_thread_lock`, BEFORE `detect_entities`, BEFORE any `logger.debug` call — no contention, no NER cost, no log spam, no observable PII (T-05-01-1).

**Tests added (TDD RED → GREEN):** 5 unit tests in `backend/tests/unit/test_redaction_service_d84_gate.py` covering stateless / explicit-None-registry / loaded-registry off-mode identity, NER-not-invoked verification, lock-not-acquired verification, and on-mode sanity.

### Task 2 — D-92 `redact_text_batch` primitive (commits `3ad058c` RED → `0f2ce3b` GREEN)

**Splice point:** `backend/app/services/redaction_service.py` directly below `redact_text` (after the registry-aware `return result`) and before the `_redact_text_stateless` private helper. Public methods cluster together; private helpers follow.

**Added:** 110-line public async method.

Signature exactly as specified by D-92 / planner:
```python
@traced(name="redaction.redact_text_batch")
async def redact_text_batch(
    self,
    texts: list[str],
    registry: ConversationRegistry,
) -> list[str]: ...
```

Behavior matrix:

| Input shape | Output | Side effects |
|---|---|---|
| `pii_redaction_enabled=False`, any registry | `list(texts)` (shallow copy) | None — D-84 alignment |
| `registry=None` (on-mode) | raises `ValueError` | None — strict primitive |
| `texts=[]` (on-mode) | `[]` | None — empty fast path, no lock acquisition |
| `texts=[s1,…,sN]` (on-mode) | `[r1,…,rN]` in input order | One asyncio.Lock acquire; N `_redact_text_with_registry` calls inside; one batched DB upsert path |

Span attributes emitted (B4-clean — counts/timings ONLY, never text):
- `batch_size: int` — `len(texts)`
- `hard_redacted_total: int` — sum of `RedactionResult.hard_redacted_count` across the batch
- `latency_ms: float` — wall-clock duration of the batch

Logger emit (B4-clean): `"redaction.redact_text_batch: thread_id=%s batch_size=%d hard_redacted_total=%d ms=%.2f"`.

**Tests added (TDD RED → GREEN):** 14 unit tests across 7 classes in `backend/tests/unit/test_redact_text_batch.py`:
- `TestD92Signature` — method exists / is async / params shape / return annotation `list[str]`
- `TestD92OffMode` — identity passthrough; shallow-copy semantics; NER not invoked
- `TestD92RegistryRequired` — `ValueError` on `registry=None` with the exact "redact_text_batch requires a loaded ConversationRegistry" message
- `TestD92EmptyInputFastPath` — `[]` returned with no lock acquisition and no NER call
- `TestD92SingleLockAcquisition` — verifies acquire-count == 1 for N=5 strings (the D-92 contract)
- `TestD92OrderPreservation` — `results[i]` is the redaction of `texts[i]`; off-mode also preserves order
- `TestD92TracedDecorator` — source contains `@traced(name="redaction.redact_text_batch")`

## Verification

### Acceptance gates (all green)

Task 1 grep gates:
- `live_gate_count=1` (live `if not get_settings().pii_redaction_enabled` outside comments)
- `phase5_d84_count=1` (decision-ID traceability comment present)
- `todo_remaining=0` (the placeholder TODO is gone)
- `old_todo_remaining=0` (the old `TODO(Phase 5): gate` text is gone)

Task 2 grep gates:
- `async def redact_text_batch(` count = 1
- `@traced(name="redaction.redact_text_batch")` count = 1
- `async with lock:` count = 2 (existing in `redact_text` + new in `redact_text_batch`)
- `_get_thread_lock(registry.thread_id)` count = 2 (same)
- `redact_text_batch requires a loaded ConversationRegistry` count = 1
- `set_attribute("batch_size"` count = 1
- `set_attribute("hard_redacted_total"` count = 1

AST gate (Task 1): `pii_redaction_enabled` reference appears INSIDE `async def redact_text` — confirmed via `ast.walk`.

Return-type annotation gate (Task 2): `inspect.signature(...).return_annotation` renders as `list[str]`.

### Test status

**Phase 1+2+3+4 regression: 135/135 still green** (no behavioral change for existing callers — the early-return only fires when redaction is explicitly off; the batch method has zero existing callers).

**New Phase 5 Plan 01 tests: 19/19 green** (5 D-84 + 14 D-92).

**Combined: 154/154 backend tests pass** (`pytest tests/ --tb=short -q` → `154 passed, 12 warnings in 57.85s`).

Backend import-check passes: `python -c "from app.main import app; print('OK')"` → `OK`.

## Deviations from Plan

**One process deviation, no behavioral deviations:**

1. **[Process] Worktree environment bootstrap.** The parallel-executor worktree at `.claude/worktrees/agent-afcbc3e0ba1866326/` did not have its own `backend/venv` or `backend/.env`. To run pytest against the worktree's `backend/` source tree (not the main repo's), I symlinked the main repo's `backend/venv/` and `backend/.env` into the worktree. Both targets are gitignored (`backend/venv/` matched by `.gitignore` line `backend/venv/`; `.env` matched by `**/.env`) so the symlinks are not staged. No source-tree change.

**No behavioral deviations.** Plan executed exactly as written: the TODO was materialized verbatim per the CONTEXT D-84 splice template; the batch method was added per the PATTERNS entry #4 splice template with the planner-specified empty-list fast path, registry-required ValueError, and B4-clean span instrumentation.

## Threat-Model Compliance

| Threat ID | Mitigation status | Verified by |
|---|---|---|
| T-05-01-1 (off-mode gate misfires; PII leaks via spans/logs) | Mitigated — early-return fires before any `logger.debug` or span attribute set; identity result has `entity_map={}` so downstream callers see no real or surrogate value. | `test_off_mode_does_not_invoke_detect_entities` + manual code-walk of the splice (no logger/span before the return). |
| T-05-01-2 (batch reordering — caller assumes index alignment) | Mitigated — single in-order for-loop inside the held lock; no asyncio.gather; no sorting. | `test_results_in_input_order` + `test_off_mode_preserves_order_and_length` (4-element and 10-element inputs verified by index). |
| T-05-01-3 (long batch holds lock; blocks concurrent same-thread turn) | Accepted — Phase 5 v1.0 acceptance per CONTEXT.md Claude's Discretion line 187. Documented in method docstring under "Lock-hold semantics". | N/A — explicit acceptance, deferred to Phase 6 PERF-02. |
| T-05-01-4 (raw PII in span attributes) | Mitigated — span attributes are `batch_size` (int), `hard_redacted_total` (int), `latency_ms` (float) ONLY. Try/except wrapper ensures tracing failures cannot affect functional behavior. | `grep -c 'set_attribute("batch_size"'` = 1, `grep -c 'set_attribute("hard_redacted_total"'` = 1; no `set_attribute` on text fields anywhere in the new method. |

## Commits

| Order | Hash | Message | Phase |
|---|---|---|---|
| 1 | `867165e` | `test(05-01): add failing tests for D-84 service-layer redaction gate` | RED — Task 1 |
| 2 | `02d8d91` | `feat(05-01): materialize D-84 service-layer redaction early-return gate` | GREEN — Task 1 |
| 3 | `3ad058c` | `test(05-01): add failing tests for D-92 redact_text_batch primitive` | RED — Task 2 |
| 4 | `0f2ce3b` | `feat(05-01): add D-92 redact_text_batch single-lock-acquisition primitive` | GREEN — Task 2 |

A 5th metadata commit will be added by the workflow to capture this SUMMARY.md.

## Downstream Plans Now Unblocked

- **Plan 05-04 (chat.py D-93 history-anon batch site):** can now call `redaction_service.redact_text_batch(history_strings + [user_message], registry)` at the top of `event_generator()` after the registry load and before `agent_start` emit.
- **Plan 05-02 (tool_redaction.py D-91 walker):** `anonymize_tool_output`'s collect-then-batch leaf strategy can call `redact_text_batch` on the collected list of strings extracted from a tool's JSON output.
- **Plan 05-04 SC#5 service-layer surface:** the D-84 gate is in place, so any future caller of `redact_text` automatically benefits from the off-mode short-circuit (defense-in-depth alongside the chat.py top-level branch Plan 05-04 will add).

## Files Touched

| File | Change | Net lines |
|---|---|---|
| `backend/app/services/redaction_service.py` | Modified — TODO replaced with live D-84 gate inside `redact_text` (+15/-6); new `redact_text_batch` method inserted between `redact_text` and `_redact_text_stateless` (+110/0) | +119/-6 (final 1171 lines, was 1049) |
| `backend/tests/unit/test_redaction_service_d84_gate.py` | Created — 5 D-84 unit tests | +146 |
| `backend/tests/unit/test_redact_text_batch.py` | Created — 14 D-92 unit tests across 7 classes | +333 |

Phase 5 Wave 1 — service-layer primitives — shipped.

## Self-Check: PASSED

Verified at end of execution:

**Created files (4/4 exist):**
- `backend/app/services/redaction_service.py` — modified (1171 lines)
- `backend/tests/unit/test_redaction_service_d84_gate.py` — 146 lines
- `backend/tests/unit/test_redact_text_batch.py` — 333 lines
- `.planning/phases/05-chat-loop-integration-buffering-sse-status-tool-sub-agent-co/05-01-SUMMARY.md` — this file

**Commits (4/4 present in git log):**
- `867165e` test(05-01): RED — D-84 gate tests
- `02d8d91` feat(05-01): GREEN — D-84 gate
- `3ad058c` test(05-01): RED — D-92 batch tests
- `0f2ce3b` feat(05-01): GREEN — D-92 redact_text_batch

**Test status:** 154/154 backend tests pass (135 baseline + 19 new).
