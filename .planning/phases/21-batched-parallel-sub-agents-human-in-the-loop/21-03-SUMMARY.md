---
phase: 21-batched-parallel-sub-agents-human-in-the-loop
plan: 03
subsystem: harness-engine
tags: [batch, asyncio, queue, jsonl, resume, curation, sub-agent, sse]

# Dependency graph
requires:
  - 21-01  # WorkspaceService.append_line atomic JSONL primitive
  - 21-02  # EVT_BATCH_ITEM_* constants + start_phase_index + HumanInputQuestion
  - 20-*   # Phase 20 harness_engine + harness_runs_service foundation
  - 19-*   # Phase 19 sub_agent_loop (parent_tool_context inheritance channel)
provides:
  - "LLM_BATCH_AGENTS dispatch branch in harness_engine._dispatch_phase (BATCH-01..07)"
  - "asyncio.Queue fan-in concurrent execution (one create_task per item per batch)"
  - "Atomic per-item JSONL append via WorkspaceService.append_line"
  - "Mid-batch resume from JSONL state (done_set covers status='ok' AND status='failed')"
  - "Post-batch merge: <stem>.jsonl → sorted <stem>.json downstream artifact"
  - "Item-level SSE events (EVT_BATCH_ITEM_START / EVT_BATCH_ITEM_COMPLETE) with task_id correlation"
  - "phase.tools curation propagation via parent_tool_context['phase_tools']"
  - "sub_agent_loop honor hook: when phase_tools is supplied, sub_tools is filtered to that allow-list"
  - "_stem_paths(workspace_output) helper — derives jsonl + merged paths"
  - "_merge_jsonl_to_json(ws, thread_id, jsonl_path, json_path) helper"
  - "Additive harness_phase_complete fields: {partial: true, failed_count: N}"
affects:
  - backend/app/services/harness_engine.py
  - backend/app/services/sub_agent_loop.py
  - backend/tests/services/test_harness_engine.py (legacy fixture refresh)
  - backend/tests/services/test_harness_engine_batch.py

# Tech tracking
tech-stack:
  added: []  # uses asyncio + uuid + pathlib (stdlib)
  patterns:
    - "asyncio.Queue fan-in with sentinel _done events for completion accounting"
    - "Per-item task_id (uuid.uuid4) for nested SSE event correlation across concurrent sub-agents"
    - "Resume via JSONL line parse — done_set keyed on item_index covers both 'ok' and 'failed' (no auto-retry)"
    - "Curation passed once per phase, inherited across all batch items via parent_tool_context['phase_tools']"

key-files:
  created:
    - backend/tests/services/test_harness_engine_batch.py  # 8 new tests
  modified:
    - backend/app/services/harness_engine.py               # batch dispatcher + helpers
    - backend/app/services/sub_agent_loop.py               # phase_tools honor hook
    - backend/tests/services/test_harness_engine.py        # 2 legacy fixtures refreshed

key-decisions:
  - "Atomic per-task commit (single feat() commit covering dispatcher + sub_agent_loop hook + tests + legacy fixture refresh) — the BLOCKER-6 honor hook and the dispatcher that calls it MUST land together to prevent a half-implemented curation surface."
  - "Used `write_todos` (which IS in PANEL_LOCKED_EXCLUDED_TOOLS) for Test 8 instead of the plan's literal `task` example, because the plan's parenthetical claim ('where task is in PANEL_LOCKED_EXCLUDED_TOOLS') is incorrect — types.py:106 defines the set as {write_todos, read_todos} only. The test still proves curation works, with the correct-and-actually-locked tool."
  - "Stale legacy fixtures (test 10 + test 14 in test_harness_engine.py) were refreshed in the SAME atomic commit per CLAUDE.md rule: 'when adding/removing entries... update any matching count-based test fixtures in the same commit'. The PHASE21_PENDING contract for LLM_BATCH_AGENTS no longer exists; the new BATCH_NO_INPUT contract replaces it."
  - "Plan 21-03's `<truths>` block specified phase_tools propagation via parent_tool_context as the BLOCKER-6 fix. The honor hook on the sub_agent_loop side was conditionally required (plan said 'if not yet honored'); inspection at execution time confirmed it was NOT yet honored, so it was added — exactly as the plan provisioned."
  - "EVT_PHASE_COMPLETE event extended with additive `partial`/`failed_count` fields ONLY when the terminal output had partial=True. Existing consumers ignore unknown fields — preserves backward compatibility."

requirements-completed:
  - BATCH-01  # Items parsed from workspace_inputs[0]
  - BATCH-02  # Chunked into batches of batch_size, run concurrently via asyncio.create_task
  - BATCH-03  # batch_size from PhaseDefinition (default 5; min 1 enforced)
  - BATCH-04  # Real-time SSE streaming via asyncio.Queue (events yielded as they arrive)
  - BATCH-05  # Results accumulate to <stem>.jsonl (per item) + sorted <stem>.json final artifact
  - BATCH-06  # Each sub-agent reads only what it needs from workspace + emits item-level SSE
  - BATCH-07  # Mid-batch resume — JSONL state dictates remaining items (failed items NOT retried)

# Metrics
duration: ~25min
completed: 2026-05-04
---

# Phase 21 Plan 03: LLM_BATCH_AGENTS Dispatcher — Summary

**The harness engine's last reserved phase type is now real:** an `asyncio.Queue` fan-in batch dispatcher that processes a JSON array of items concurrently in chunks of `batch_size`, atomically appends per-item results to a JSONL resume artifact, isolates per-item failures, merges to a sorted JSON downstream artifact, surfaces partial completion via additive event fields, AND propagates `phase.tools` curation to every batch sub-agent via `parent_tool_context['phase_tools']` (BLOCKER-6 fix). Phase 21's engine work is COMPLETE after this plan.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Implement LLM_BATCH_AGENTS dispatcher (TDD: RED → GREEN, 8 tests) — input parse, resume detection, asyncio.Queue fan-in, JSONL atomic append, sorted-merge pass, item-level SSE, phase.tools curation propagation, and sub_agent_loop honor hook | `e99d853` | `backend/app/services/harness_engine.py`, `backend/app/services/sub_agent_loop.py`, `backend/tests/services/test_harness_engine_batch.py`, `backend/tests/services/test_harness_engine.py` |

## Verification

```
cd backend && pytest tests/services/test_harness_engine_batch.py \
  tests/services/test_harness_engine.py \
  tests/services/test_harness_engine_human_input.py \
  tests/services/test_harness_runs_service.py \
  tests/services/test_harness_runs_service_pause.py \
  tests/services/test_workspace_service.py \
  tests/services/test_workspace_service_append_line.py
```

Result: **78 passed** (8 new batch + 14 existing harness_engine + 6 HIL + 12 harness_runs_service + 5 pause + 25 workspace + 6 append_line + 2 legacy fixtures refreshed).

Additional: `pytest tests/integration/test_sub_agent_loop.py` → 21 passed (no regression from the phase_tools honor hook).

Backend import smoke: `python -c "from app.main import app; print('OK')"` → OK.

## Acceptance-Criteria Grep

| Pattern | Expected | Got |
|---------|----------|-----|
| `if phase.phase_type == PhaseType.LLM_BATCH_AGENTS` | 1 | 1 |
| `asyncio.Queue` | ≥1 | 2 |
| `asyncio.create_task` | ≥1 | 1 |
| `ws.append_line` | ≥1 | 1 |
| `_merge_jsonl_to_json` (definition + calls) | ≥2 | 4 |
| `EVT_BATCH_ITEM_START`/`EVT_BATCH_ITEM_COMPLETE` | ≥4 | 4 |
| `"code": "PHASE21_PENDING"` (runtime literal) | 0 | 0 |
| `_stem_paths` (definition + call) | ≥2 | 2 |
| `curated_tools` | ≥2 | 3 |
| `PANEL_LOCKED_EXCLUDED_TOOLS` | ≥2 | 3 |
| `"phase_tools"` in harness_engine | ≥1 | 1 |
| `phase_tools` honor in sub_agent_loop | ≥2 | 4 |

## SSE Event Contract — LLM_BATCH_AGENTS phase

```
harness_phase_start (phase_index=N, phase_type='llm_batch_agents')
todos_updated
[per batch:]
  harness_batch_start { batch_index, batch_size, items_total }
  [interleaved per concurrent item:]
    harness_batch_item_start { item_index, items_total, task_id, batch_index }
    [forwarded sub-agent events tagged with task_id + batch_index]
    harness_batch_item_complete { item_index, status, task_id, batch_index }
  harness_batch_complete { batch_index, failed_count }
harness_phase_complete { phase_index, phase_name [, partial, failed_count] }
```

The `partial: true, failed_count: N` fields appear on `harness_phase_complete` ONLY when at least one batch item failed — purely additive, existing consumers ignore unknown fields.

## Workspace Artifacts (per batch phase)

| Artifact | Purpose | Lifecycle |
|----------|---------|-----------|
| `<stem>.jsonl` | resume artifact (per-item append-only state) | grows monotonically; survives mid-batch crash |
| `<stem>.json` | downstream consumer artifact (sorted JSON array) | written once, after all batches finish (or all items skipped on resume) |

## Threat-Model Mitigations Implemented

| Threat ID | Disposition | Implementation |
|-----------|-------------|----------------|
| T-21-03-01 (DoS — unbounded create_task) | mitigate | Concurrency bounded by phase.batch_size (max(1, ...) enforced; default 5). Workspace 1 MB cap on input file bounds total items. |
| T-21-03-02 (DoS — recursive batches) | mitigate | sub_agent_loop strips `task` already (Phase 19 D-02 / D-09 EXCLUDED set); the new phase_tools honor hook is an additional allow-list filter — defense-in-depth. |
| T-21-03-03 (Tampering — malformed items file) | mitigate | json.loads in try/except → BATCH_INPUT_INVALID terminal; `isinstance(all_items, list)` check rejects non-array. |
| T-21-03-04 (Race / data corruption — concurrent appends) | mitigate | Plan 21-01's per-(thread, file_path) asyncio.Lock serializes appends within the worker. |
| T-21-03-05 (Information Disclosure — path traversal) | mitigate | `_stem_paths` only manipulates the stem of phase.workspace_output (developer-defined config); `validate_workspace_path` is enforced by `append_line` and `write_text_file`. |
| T-21-03-06 (Info Disclosure — PII in batch sub-agent payloads) | mitigate | Egress filter is enforced INSIDE `run_sub_agent_loop` (Phase 19 D-21). Dispatcher reuses parent registry. Privacy invariant preserved unchanged. |
| T-21-03-07 (Repudiation — which item failed why) | mitigate | JSONL line for failed items contains structured `{error, code, detail}` — full audit trail in workspace. |
| T-21-03-08 (Tampering — forged JSONL skips items) | accept | JSONL is RLS-scoped to user's own thread; only same user can write it. No cross-user attack surface. |
| T-21-03-09 (Elevation — sub-agent calls tool outside allow-list) | mitigate | `curated_tools` propagated via `parent_tool_context['phase_tools']`; sub_agent_loop honors the filter (BLOCKER-6 fix). PANEL_LOCKED_EXCLUDED_TOOLS removed unconditionally. |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] Updated stale legacy fixtures in test_harness_engine.py**

- **Found during:** GREEN-phase regression run after batch dispatcher landed.
- **Issue:** `test_run_harness_engine_phase21_types_return_not_implemented` and `test_phase21_events_are_documented_but_unimplemented` both assert that LLM_BATCH_AGENTS returns `{"code": "PHASE21_PENDING"}`. That contract was retired by this plan.
- **Fix:** Updated both tests to assert the new contract: a degenerate LLM_BATCH_AGENTS phase with no `workspace_inputs` surfaces `BATCH_NO_INPUT` instead. Per CLAUDE.md "RBAC / auth changes" pattern: ship the test fixture update with the feature commit.
- **Files modified:** `backend/tests/services/test_harness_engine.py` (2 test bodies, ~6 lines of assertion text changed; structure preserved)
- **Commit:** `e99d853` (atomic with the dispatcher implementation)

### Authentication Gates
None.

### Other Deviations
- **Test 8 substituted `write_todos` for `task`.** Plan-text said `phase.tools=["search_documents", "query_database", "task"]` (where task is in PANEL_LOCKED_EXCLUDED_TOOLS). Verified at types.py:106 that `PANEL_LOCKED_EXCLUDED_TOOLS = frozenset({"write_todos", "read_todos"})` — `task` is NOT in this set (it is excluded by sub_agent_loop's separate D-09 EXCLUDED set, but that filter happens inside sub_agent_loop, not via PANEL_LOCKED_EXCLUDED_TOOLS curation). Test uses `write_todos` to validate the actual locked-tools curation path. The behavioral assertion is identical to the plan's intent.

## Issues Encountered
None blocking. The two legacy-fixture failures were detected and fixed inline.

## User Setup Required
None — no new env vars, no new dependencies, no new migration.

## Next Phase Readiness

**Phase 21 engine work is COMPLETE.** Wave 4+ (downstream of this wave) — frontend `batchProgress` slice, `HarnessBanner` extensions, smoke harness extension, and chat.py HIL resume branch — can land independently.

Phase 22 Contract Review can now register `llm_batch_agents` phases for risk-analysis and redlines (CR-06 RAG access works because `phase.tools=["search_documents", ...]` is propagated through curation).

## Known Stubs

None. The only `PHASE21_PENDING` mention left in the codebase is the documentation block at `harness_engine.py` lines 19-27 (forward-compat docstring referring to the historical reserved-but-not-implemented state). All runtime stubs are gone.

## Threat Flags

None — no new security-relevant surface beyond the threat register entries above. The new phase_tools honor hook in sub_agent_loop.py is a STRICTER filter (allow-list intersection); it cannot grant access to a tool not already in `sub_tools`.

## Self-Check: PASSED

- [x] FOUND: `backend/app/services/harness_engine.py` (modified — LLM_BATCH_AGENTS branch + helpers present)
- [x] FOUND: `backend/app/services/sub_agent_loop.py` (modified — phase_tools honor hook in sub_tools build region)
- [x] FOUND: `backend/tests/services/test_harness_engine_batch.py` (created — 8 tests passing)
- [x] FOUND: `backend/tests/services/test_harness_engine.py` (modified — 2 legacy fixtures refreshed)
- [x] FOUND commit: `e99d853` (`git log --oneline -1` matches `feat(21-03): implement LLM_BATCH_AGENTS dispatcher with asyncio.Queue fan-in + JSONL resume + phase.tools curation`)
- [x] All acceptance-criteria grep counts pass (table above)
- [x] `pytest backend/tests/services/test_harness_engine_batch.py` → 8 passed
- [x] `pytest backend/tests/services/test_harness_engine.py backend/tests/services/test_harness_engine_human_input.py` → 22 passed (no regression)
- [x] `python -c "from app.main import app; print('OK')"` → OK

---
*Phase: 21-batched-parallel-sub-agents-human-in-the-loop*
*Completed: 2026-05-04*
