---
phase: 21-batched-parallel-sub-agents-human-in-the-loop
plan: 01
subsystem: api  # service-layer primitive consumed by harness engine
tags: [workspace, jsonl, asyncio, lock, atomic, append, batch, supabase]

# Dependency graph
requires:
  - phase: 18-workspace-virtual-filesystem
    provides: WorkspaceService (write_text_file, read_file, validate_workspace_path, MAX_TEXT_CONTENT_BYTES)
provides:
  - WorkspaceService.append_line() — atomic JSONL append primitive (per-key asyncio.Lock + 1 MB cap + first-write semantics)
  - WorkspaceService._get_append_lock() — class-level identity-stable lock cache keyed by (thread_id, file_path)
affects:
  - 21-03-batch-dispatcher  # asyncio.gather'd batch sub-agents call append_line per item
  - 21-04-batch-resume      # resume reads JSONL via read_file, computes done_set
  - 22-contract-review-harness  # downstream consumer of llm_batch_agents output

# Tech tracking
tech-stack:
  added: []  # no new libraries — reuses asyncio + existing supabase client
  patterns:
    - "Per-key asyncio.Lock cached on a class-level dict for in-process serialization"
    - "First-write-via-append: file_not_found short-circuits to empty content, no separate write_text_file call"
    - "Validation + size-cap + lock + read-modify-write composition over existing primitives"

key-files:
  created:
    - backend/tests/services/test_workspace_service_append_line.py
  modified:
    - backend/app/services/workspace_service.py

key-decisions:
  - "Option A (read-modify-write under per-(thread, path) asyncio.Lock) chosen over Option B (Postgres `content || $newline` UPDATE) — single-worker Railway scope (D-31 carryover); cross-process atomicity deferred to post-MVP via pg_advisory_xact_lock upgrade path."
  - "First-write semantics handled by treating read_file's `{error: 'file_not_found'}` contract as the empty-content case rather than requiring callers to pre-create the row. Verified at workspace_service.py line 293."
  - "source='harness' on the underlying write_text_file call — distinguishes append_line writes from direct agent writes in audit trails."
  - "Size-cap check uses cumulative `current_bytes + new_segment_bytes > MAX_TEXT_CONTENT_BYTES`, evaluated INSIDE the lock and BEFORE the write — no DB call when over cap."

patterns-established:
  - "Per-key asyncio.Lock pattern: `_get_append_lock(thread_id, file_path)` caches Lock instances in a class-level dict, keyed by tuple. Identity-stable per key — reusable for any future per-key serialization in WorkspaceService."
  - "Append primitive composition: `validate_path → lock → read_file → cap_check → write_text_file` — each step has structured error returns and never raises to the caller."

requirements-completed:
  - BATCH-05  # JSONL append-only output is the resume artifact (D-05)
  - BATCH-07  # Atomic per-line append is what makes mid-batch resume safe (D-07)

# Metrics
duration: ~25min
completed: 2026-05-04
---

# Phase 21 Plan 01: Workspace JSONL Append Helper Summary

**Atomic `WorkspaceService.append_line()` primitive — per-(thread, path) asyncio.Lock + 1 MB cap + first-write-via-append semantics, the foundational JSONL append for Phase 21's `llm_batch_agents` resume artifact (BATCH-05/D-05 + BATCH-07/D-07).**

## Performance

- **Duration:** ~25 min (single TDD task: RED → GREEN, no REFACTOR needed)
- **Started:** 2026-05-04T06:54:00Z (approx — worktree spawn)
- **Completed:** 2026-05-04T07:19:32Z
- **Tasks:** 1 / 1
- **Files modified:** 1 (workspace_service.py)
- **Files created:** 1 (test_workspace_service_append_line.py)

## Accomplishments

- New async method `WorkspaceService.append_line(thread_id, file_path, line)` that atomically appends `line + '\n'` to a workspace file's `content` column.
- Per-(thread_id, file_path) `asyncio.Lock` cache (`_append_locks` dict + `_get_append_lock` accessor) — concurrent appends within a single worker are serialized, file grows monotonically without overwrite.
- First-write-via-append: when `read_file` returns `{error: 'file_not_found'}`, append_line creates the row with `content = line + '\n'` — callers do NOT need to pre-write the file.
- Size-cap enforcement: `current_bytes + new_segment_bytes > MAX_TEXT_CONTENT_BYTES` returns `content_too_large` BEFORE issuing any DB write.
- 6 unit tests covering: first-write, append-existing, invalid path, size cap, db error path, and per-key lock identity + 5-way concurrent `gather()` serialization. All pass.
- Zero regression in pre-existing `test_workspace_service.py` (25/25 still pass).

## Task Commits

1. **Task 1: WorkspaceService.append_line atomic JSONL primitive (TDD: RED → GREEN)** — `65f68d9` (feat)

_Note: Single TDD commit — RED phase confirmed via `AttributeError: 'WorkspaceService' object has no attribute 'append_line'`; GREEN phase landed the method + per-key lock + tests in one atomic commit per the plan's RED→GREEN→commit sequence (no REFACTOR commit since the implementation matched plan spec verbatim)._

## Files Created/Modified

- `backend/app/services/workspace_service.py` — Added `import asyncio`, class-level `_append_locks: dict[tuple[str, str], asyncio.Lock]` map, `@classmethod _get_append_lock`, and `async def append_line` between `read_file` and `edit_file`. ~115 new lines, no edits to existing methods.
- `backend/tests/services/test_workspace_service_append_line.py` — New file. 6 tests, follows the `MagicMock` upsert/select fixture pattern from `test_workspace_service.py`. Stateful in-memory mock for the concurrency test (Test 6) so the per-key lock is exercised in real fan-in conditions.

## Decisions Made

- **Per-key asyncio.Lock (Option A) over Postgres atomic UPDATE (Option B)**: Plan recommended Option B but Option A keeps the implementation pure-Python and avoids depending on a custom RPC or a raw SQL execute path that the Supabase Python client doesn't expose ergonomically. Single-worker Railway today means in-process serialization is sufficient (D-31 carryover documented in STATE.md). Plan explicitly authorized Option A in `<action>` block lines 115-116 ("Option A from PATTERNS.md — simplest within v1.3 single-worker scope").
- **`source='harness'` for the underlying `write_text_file` call**: Distinguishes harness-engine-written rows from `source='agent'` direct writes in audit/debugging.
- **Lock check pattern**: Used `lock = cls._append_locks.get(key); if lock is None:` over `if key not in cls._append_locks:` — equivalent semantics, slightly fewer dict lookups, same correctness.

## Deviations from Plan

None — plan executed exactly as written. The implementation follows the plan's `<action>` block verbatim (signature, locking strategy, error-shape conventions, run order). The test file mirrors `<behavior>` Tests 1-6 one-for-one.

## Issues Encountered

None. RED phase produced the expected `AttributeError` immediately; GREEN phase passed all 6 tests on first run; regression check on `test_workspace_service.py` was clean.

## User Setup Required

None — no new env vars, no new dependencies, no migration. The method is purely additive on top of Phase 18's WorkspaceService.

## Next Phase Readiness

**Ready for Plan 21-03 (batch dispatcher).** The atomic JSONL primitive is in place — 21-03 can now invoke `await ws.append_line(thread_id, jsonl_path, json.dumps({...}))` from inside an `asyncio.gather()` over `run_sub_agent_loop` calls without worrying about overwrite races.

**Carry-forward concerns:**
- Cross-process atomicity is NOT provided (single-worker Railway today). When scale-out happens, upgrade to `pg_advisory_xact_lock(hashtext(thread_id || file_path))` per D-31 deferred plan — documented in STATE.md.
- `_append_locks` dict grows monotonically per-process (one Lock per unique (thread, path) ever seen). Not a concern for normal usage (bounded by active threads), but a future janitor could prune locks for threads completed >24h ago if memory becomes a concern. Out of scope for v1.3.

## Threat Flags

None. The new surface is a same-process primitive; trust boundaries are unchanged from Phase 18 (caller → WorkspaceService → Supabase RLS-scoped client). Threat register T-21-01-01..04 in the plan all have `mitigate` dispositions and the implementation honors each (path validation, size cap, per-key lock, structured non-leaky errors).

## Self-Check: PASSED

- [x] FOUND: `backend/app/services/workspace_service.py` (modified — `append_line` present, verified by `grep -c "async def append_line"` = 1)
- [x] FOUND: `backend/tests/services/test_workspace_service_append_line.py` (created — 6 tests collected and passing)
- [x] FOUND: Commit `65f68d9` (`git log --oneline -1` matches `feat(21-01): add WorkspaceService.append_line atomic JSONL primitive`)
- [x] Acceptance criteria from plan all pass:
  - `grep -c "async def append_line" backend/app/services/workspace_service.py` = 1 (>= 1) ✓
  - `grep -c "_get_append_lock\|_append_locks" backend/app/services/workspace_service.py` = 5 (>= 2) ✓
  - `grep -c "MAX_TEXT_CONTENT_BYTES" backend/app/services/workspace_service.py` = 6 (>= 2) ✓
  - `grep -c "validate_workspace_path" backend/app/services/workspace_service.py` = 9 (>= 2) ✓
  - `grep -c '"file_not_found"' backend/app/services/workspace_service.py` = 2 (>= 2) ✓
  - `pytest backend/tests/services/test_workspace_service_append_line.py` exit 0, 6 passed ✓
  - `pytest backend/tests/services/test_workspace_service.py` exit 0, 25 passed (no regression) ✓
  - `python -c "from app.services.workspace_service import WorkspaceService; assert hasattr(WorkspaceService, 'append_line'); print('OK')"` prints `OK` ✓
  - `python -c "from app.main import app; print('OK')"` prints `OK` (full import clean) ✓

---
*Phase: 21-batched-parallel-sub-agents-human-in-the-loop*
*Completed: 2026-05-04*
